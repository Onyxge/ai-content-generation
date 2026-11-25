"""The contract (ADR-001): load storyboard.json, validate it against the JSON Schema, then
lint the rules a schema can't express, including the consent gate (ADR-014)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "schema" / "storyboard.schema.json"

SPEECH_WPS = {"en": 2.4}      # rough English rate (the brief says 2–2.5 words/s); Amharic is measured, not guessed
LEAD_IN_S, TAIL_S = 0.4, 0.6
MAX_CPS = 17                  # comfortable subtitle reading speed, characters per second
TEXT_IN_IMAGE = re.compile(
    r"\b(signs?|signboard|text|letters?|lettering|written|writing|caption|logo|headline)\b", re.IGNORECASE)
PLACEHOLDERS = {"", "…", "...", "-", "—", "tbd", "todo"}
CONSENT_ROW = re.compile(r"^\|\s*(C\d+)\s*\|(.*)\|\s*$")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def schema_errors(sb: dict) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    found = sorted(Draft202012Validator(schema).iter_errors(sb), key=lambda e: [str(p) for p in e.absolute_path])
    return [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in found]


def consent_ids(ethics_text: str) -> set[str]:
    """Ids in ETHICS.md's consent table whose person, giver, scope and date cells are all filled in."""
    found = set()
    for line in ethics_text.splitlines():
        m = CONSENT_ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) >= 4 and all(c.lower() not in PLACEHOLDERS for c in cells[:4]):
            found.add(m.group(1))
    return found


def shot_references(sb: dict, shot: dict) -> list[str]:
    """Reference ids a keyframe is conditioned on: explicit ones first, then each character's sheet."""
    ids = list(shot.get("references", []))
    chars = {c["id"]: c for c in sb["characters"]}
    for cid in shot.get("characters", []):
        rid = chars.get(cid, {}).get("reference")
        if rid and rid not in ids:
            ids.append(rid)
    return ids


def lint(sb: dict, ethics_text: str = "") -> Report:
    r = Report()
    meta, shots = sb["meta"], sb["shots"]
    langs = meta["languages"]
    chars = {c["id"]: c for c in sb["characters"]}
    refs = {x["id"]: x for x in sb["references"]}
    shot_ids = [s["id"] for s in shots]

    if not 8 <= len(shots) <= 12:
        r.errors.append(f"shots: the brief asks for 8–12 shots; this storyboard has {len(shots)}")
    for kind, items in (("shots", shots), ("characters", sb["characters"]),
                        ("references", sb["references"]), ("music.cues", sb["music"]["cues"])):
        ids = [item["id"] for item in items]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            r.errors.append(f"{kind}: duplicate id '{dup}'")

    if meta["primary"] not in langs:
        r.errors.append(f"meta.primary: '{meta['primary']}' is not one of meta.languages {langs}")
    for lang in langs:
        if lang not in sb["voices"]:
            r.errors.append(f"voices: no voice for language '{lang}'")

    for ref in sb["references"]:
        if "selected" in ref and ref["selected"] not in ref["seeds"]:
            r.errors.append(f"references/{ref['id']}: selected {ref['selected']} is not one of its seeds {ref['seeds']}")
        for cid in ref.get("characters", []):
            if cid not in chars:
                r.errors.append(f"references/{ref['id']}: unknown character '{cid}'")

    consented = consent_ids(ethics_text)
    for c in sb["characters"]:
        if c.get("reference") and c["reference"] not in refs:
            r.errors.append(f"characters/{c['id']}: unknown reference '{c['reference']}'")
        if c["real_person"]:
            cid = c.get("consent_id")
            if not cid:
                r.errors.append(f"characters/{c['id']}: a real person needs a consent_id recorded in ETHICS.md "
                                "before anything of them is generated (ADR-014)")
            elif cid not in consented:
                r.errors.append(f"characters/{c['id']}: consent '{cid}' is missing or incomplete in "
                                "ETHICS.md's consent table (ADR-014)")

    planned = 0.0
    for s in shots:
        where = f"shots/{s['id']}"
        planned += s["duration_s"]
        for cid in s.get("characters", []):
            if cid not in chars:
                r.errors.append(f"{where}: unknown character '{cid}'")
        conditioning = shot_references(sb, s)
        for rid in conditioning:
            if rid not in refs:
                r.errors.append(f"{where}: unknown reference '{rid}'")
        if len(conditioning) > 4:
            r.errors.append(f"{where}: {len(conditioning)} reference images; FLUX.2 klein takes at most 4")
        texts = {lang: (s["narration"].get(lang) or "").strip() for lang in langs}
        voiced = [lang for lang, text in texts.items() if text]
        if voiced and len(voiced) != len(langs):
            r.errors.append(f"{where}: narration must exist in every language or in none (has {voiced}, needs {langs})")
        subtitle = (s.get("subtitle_en") or s["narration"].get("en") or "").strip()
        if voiced and not subtitle:
            r.errors.append(f"{where}: English subtitle text is missing (narration.en or subtitle_en)")
        for lang, text in texts.items():
            if text and lang in SPEECH_WPS:
                need = len(text.split()) / SPEECH_WPS[lang] + LEAD_IN_S + TAIL_S
                if need > s["duration_s"] + 0.5:
                    r.warnings.append(f"{where}: the {lang} line needs about {need:.1f}s but the shot is "
                                      f"{s['duration_s']}s; assembly will lengthen the shot")
        if subtitle:
            cps = len(subtitle) / max(s["duration_s"] - LEAD_IN_S - TAIL_S, 1.0)
            if cps > MAX_CPS:
                r.warnings.append(f"{where}: subtitles need {cps:.0f} characters/s; aim for {MAX_CPS} or fewer")
        if TEXT_IN_IMAGE.search(s["image_prompt"]):
            r.warnings.append(f"{where}: the image prompt asks for text; generated lettering usually garbles, "
                              "so add words in code")
        if s["motion"]["mode"] == "i2v" and "seed" not in s["motion"]:
            r.warnings.append(f"{where}: motion.seed is missing; pin one so the clip is reproducible")

    runtime = planned + sb["end_card"]["duration_s"]
    for cue in sb["music"]["cues"]:
        where = f"music/{cue['id']}"
        if cue["from"] not in shot_ids or cue["to"] not in shot_ids:
            r.errors.append(f"{where}: from and to must be shot ids")
        elif shot_ids.index(cue["from"]) > shot_ids.index(cue["to"]):
            r.errors.append(f"{where}: '{cue['from']}' comes after '{cue['to']}'")
        if "selected" in cue and cue["selected"] not in cue["seeds"]:
            r.errors.append(f"{where}: selected {cue['selected']} is not one of its seeds {cue['seeds']}")
        if cue["length_s"] < runtime:
            r.warnings.append(f"{where}: the score ({cue['length_s']}s) is shorter than the planned film "
                              f"({runtime:.0f}s) and will end early")
    if len(sb["music"]["cues"]) > 1:
        r.warnings.append("music: assembly currently scores the film with the first cue only")

    lo, hi = meta["runtime_s"]
    if not lo <= runtime <= hi:
        r.errors.append(f"meta.runtime_s: planned runtime is {runtime:.1f}s (shots plus end card), outside {lo}–{hi}s")
    return r


def check(path: Path | str, ethics_path: Path | str | None = None) -> Report:
    sb = load(path)
    errors = schema_errors(sb)
    if errors:
        return Report(errors=errors)
    ethics = ""
    if ethics_path and Path(ethics_path).exists():
        ethics = Path(ethics_path).read_text(encoding="utf-8")
    return lint(sb, ethics)
