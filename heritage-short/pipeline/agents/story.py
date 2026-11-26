"""The story agent (unit A2, ADR-019): a prompt chain from Y's brief to a complete first storyboard.

Five steps, each a unit in the same runner as every other model call, so each is cached by
its inputs and logged in runs.jsonl with actor "story". Each writes a draft Y can read and
edit in docs/story/drafts/:

  1 outline      brief + intent  → title, logline, treatment, cast, look, music idea
  2 beats        outline         → three to five beats
                 ── gate G1: Y reads the outline and the beats, edits them if needed, approves ──
  3 shots        outline + beats → 8–12 shots with reasons, sizes, durations, first prompts
  4 narration    shots           → one English line per shot, inside a word budget
  5 translation  narration       → Amharic, for a native speaker to check

Code, not a model, then assembles storyboard.draft.json and validates it. Y adopts it as v1
at gate G2 (`film storyboard --adopt`); from then on every change is a proposal (ADR-018).

Two rules make the chain safe to steer by hand. A draft Y has edited is kept, backed up and
logged, and only the steps after it rerun. And an answer that parses but breaks a rule the
code checks (too few shots, a line over budget) is sent back once with the problems listed:
each repair is its own logged attempt."""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from .. import contract
from ..engine.cache import read_sidecar, sidecar
from ..engine.retry import RepairableError
from ..engine.runner import Stage, Unit
from ..engine.workspace import sha256_file, sha256_text
from .decisions import HUMAN, Decisions, Policy

PROMPTS = Path(__file__).parent / "prompts"
SIZES = ["extreme wide", "wide", "medium", "medium close-up", "close-up", "extreme close-up", "insert"]
ID = {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}
TEXT = {"type": "string", "minLength": 1}
FILES = {"outline": "01-outline.json", "beats": "02-beats.json", "shots": "03-shots.json",
         "narration": "04-narration.json", "translation": "05-translation.json"}
DRAFT = "storyboard.draft.json"


# ---------- what each step must return ----------

def schemas(cfg: dict) -> dict[str, dict]:
    found = _schemas(cfg)
    for step, sch in found.items():
        sch["title"] = f"story_{step}"
    return found


def _schemas(cfg: dict) -> dict[str, dict]:
    st = cfg["story"]
    obj = lambda props, req=None: {"type": "object", "properties": props, "required": req or list(props)}  # noqa: E731
    return {
        "outline": obj({
            "title": TEXT, "logline": TEXT, "treatment": TEXT,
            "cast": {"type": "array", "items": obj({
                "id": ID, "role": TEXT, "description": TEXT, "real_person": {"type": "boolean"},
                "consent_id": {"type": "string", "pattern": "^C[0-9]+$"}},
                ["id", "role", "description", "real_person"])},
            "look": TEXT, "music": TEXT, "feeling": TEXT}),
        "beats": obj({"beats": {"type": "array", "minItems": 3, "maxItems": 5, "items": obj({
            "id": {"type": "string", "pattern": "^b[0-9]+$"}, "summary": TEXT, "feeling": TEXT, "picture": TEXT})}}),
        "shots": obj({"shots": {"type": "array", "minItems": st["min_shots"], "maxItems": st["max_shots"],
                                "items": obj({
            "id": {"type": "string", "pattern": "^s[0-9]{2}$"}, "beat": TEXT,
            "reason": {"type": "string", "minLength": 10}, "size": {"enum": SIZES},
            "duration_s": {"type": "integer", "minimum": 4, "maximum": 10},
            "characters": {"type": "array", "items": ID}, "image_prompt": TEXT,
            "motion": obj({"mode": {"enum": ["kenburns", "i2v", "still"]}, "prompt": TEXT,
                           "zoom": {"enum": ["in", "out", "none"]}, "pan": {"enum": ["none", "left", "right"]}},
                          ["mode", "prompt"])})}}),
        "narration": obj({"lines": {"type": "array", "items": obj({"shot": TEXT, "en": {"type": "string"}})}}),
        "translation": obj({"lines": {"type": "array", "items": obj({"shot": TEXT, "am": {"type": "string"}})},
                            "notes": {"type": "array", "items": {"type": "string"}}}),
    }


def word_budget(duration_s: float, wps: float) -> int:
    """Words a line may have: the brief's 2–2.5 words a second, less one second for breath."""
    return max(0, math.floor((duration_s - 1.0) * wps))


# ---------- the rules the code checks after the schema ----------

def rule_problems(step: str, data: dict, earlier: dict[str, dict], cfg: dict) -> list[str]:
    st = cfg["story"]
    problems: list[str] = []
    if step == "outline":
        ids = [c["id"] for c in data["cast"]]
        problems += [f"cast: duplicate id '{i}'" for i in sorted({i for i in ids if ids.count(i) > 1})]
    elif step == "beats":
        ids = [b["id"] for b in data["beats"]]
        if ids != [f"b{n}" for n in range(1, len(ids) + 1)]:
            problems.append(f"beats: ids must be b1, b2… in order, got {ids}")
    elif step == "shots":
        shots = data["shots"]
        ids = [s["id"] for s in shots]
        if ids != [f"s{n:02d}" for n in range(1, len(ids) + 1)]:
            problems.append(f"shots: ids must be s01, s02… in order, got {ids}")
        beats = {b["id"] for b in earlier["beats"]["beats"]}
        cast = {c["id"]: c for c in earlier["outline"]["cast"]}
        for s in shots:
            if s["beat"] not in beats:
                problems.append(f"{s['id']}: beat '{s['beat']}' is not one of {sorted(beats)}")
            for c in s["characters"]:
                if c not in cast:
                    problems.append(f"{s['id']}: character '{c}' is not in the cast {sorted(cast)}")
                elif cast[c]["real_person"] and not cast[c].get("consent_id"):
                    # The consent gate, applied while drafting (ADR-014): a real person with no
                    # consent may be spoken about, never put in a frame.
                    problems.append(f"{s['id']}: '{c}' is a real person with no recorded consent and must not "
                                    "appear in any shot; show them only through others, objects or the room")
        total = sum(s["duration_s"] for s in shots) + st["end_card_s"]
        lo, hi = st["runtime_s"]
        if not lo <= total <= hi:
            problems.append(f"shots: durations plus the {st['end_card_s']} s end card add up to {total} s; "
                            f"they must add up to {lo}–{hi} s")
        i2v = [s["id"] for s in shots if s["motion"]["mode"] == "i2v"]
        if len(i2v) > st["max_i2v"]:
            problems.append(f"shots: {len(i2v)} shots use i2v ({', '.join(i2v)}); at most {st['max_i2v']}")
    elif step == "narration":
        shots = {s["id"]: s for s in earlier["shots"]["shots"]}
        got = [line["shot"] for line in data["lines"]]
        if got != list(shots):
            problems.append(f"lines: one line per shot, in order {list(shots)}; got {got}")
        for line in data["lines"]:
            if line["shot"] in shots:
                budget = word_budget(shots[line["shot"]]["duration_s"], st["wps"])
                words = len(line["en"].split())
                if words > budget:
                    problems.append(f"{line['shot']}: {words} words, over its budget of {budget}")
                if any(ch in line["en"] for ch in "()[]*"):
                    problems.append(f"{line['shot']}: spoken words only; remove stage directions and brackets")
    elif step == "translation":
        en = {line["shot"]: line["en"].strip() for line in earlier["narration"]["lines"]}
        am = {line["shot"]: line["am"].strip() for line in data["lines"]}
        if list(am) != list(en):
            problems.append(f"lines: one line per shot, in order {list(en)}; got {list(am)}")
        for shot, text in en.items():
            if bool(text) != bool(am.get(shot, "")):
                problems.append(f"{shot}: the Amharic line must be empty exactly when the English one is")
    return problems


# ---------- the stage ----------

def drafts_dir(ctx) -> Path:
    return ctx.ws.base / "docs" / "story" / "drafts"


def read_brief(root: Path) -> tuple[str, str]:
    brief = root / "docs" / "story" / "brief.md"
    design = root / "DESIGN.md"
    text = brief.read_text(encoding="utf-8") if brief.exists() else ""
    intent = ""
    if design.exists():
        lines, keep = design.read_text(encoding="utf-8").splitlines(), False
        for line in lines:
            if line.startswith("## "):
                keep = line.strip().lower() == "## audience and intent"
                continue
            if keep:
                intent += line + "\n"
    return text.strip(), intent.strip()


def _written(text: str) -> bool:
    """False for an empty section or one still holding the template's placeholders."""
    return bool(text) and "To be written by Y" not in text and text.count("…") < 3


def _prompt_file(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def gate_g1(ctx) -> str:
    """Empty when Y approved the outline and beats as they are now; otherwise why the chain waits."""
    d = drafts_dir(ctx)
    paths = [d / FILES["outline"], d / FILES["beats"]]
    if not all(p.exists() for p in paths):
        return "gate G1: the outline and beats come first"
    shas = {p.name: sha256_file(p)[:12] for p in paths}
    studio = Decisions(ctx.ws.root, ctx.ws.root / "storyboard.json", mock=ctx.ws.mock)
    approved = [r for r in studio.history() if r.get("event") == "gate" and r.get("gate") == "G1"]
    if approved and approved[-1].get("drafts") == shas:
        return ""
    return ("gate G1: Y reads docs/story/drafts/01-outline.json and 02-beats.json, edits them if needed, "
            "then runs `film storyboard --approve-beats`")


class StoryChain(Stage):
    name = "story"
    version = 1

    def __init__(self):
        self._feedback: dict[str, tuple] = {}

    def units(self, ctx):
        d, st = drafts_dir(ctx), ctx.cfg["story"]
        brief, intent = read_brief(ctx.ws.root)
        missing = "" if _written(brief) and _written(intent) else (
            "write docs/story/brief.md (from brief.template.md) and the Audience and intent section of DESIGN.md first")
        base = f"# The brief\n\n{brief}\n\n# Audience and intent\n\n{intent}"
        system = _prompt_file("story_system")
        sch = schemas(ctx.cfg)
        extra = {"shots": dict(min_shots=st["min_shots"], max_shots=st["max_shots"], sizes=", ".join(SIZES),
                               min_runtime=st["runtime_s"][0], max_runtime=st["runtime_s"][1],
                               end_card=st["end_card_s"], max_i2v=st["max_i2v"])}
        deps = {"outline": (), "beats": ("outline",), "shots": ("outline", "beats"),
                "narration": ("outline", "shots"), "translation": ("narration",)}
        g1 = gate_g1(ctx)
        units = []
        for step, file in FILES.items():
            template = _prompt_file(f"story_{step}")
            if step in extra:
                template = template.format(**extra[step])
            contract_sha = sha256_text(system + template + json.dumps(sch[step], sort_keys=True))[:12]
            blocked = missing or (g1 if step in ("shots", "narration", "translation") else "")
            units.append(Unit(self.name, step, d / file,
                              {"step": step, "prompt": f"{template}\n\n{base}", "contract": contract_sha},
                              tuple((self.name, s) for s in deps[step]), provider="text", blocked=blocked))
        return units

    def render(self, unit, ctx, inputs, out):
        step, st = unit.spec["step"], ctx.cfg["story"]
        sch = schemas(ctx.cfg)[step]
        earlier = {k.split(":", 1)[1]: json.loads(Path(p).read_text(encoding="utf-8")) for k, p in inputs.items()}
        prompt = unit.spec["prompt"]
        for name, data in earlier.items():
            prompt += f"\n\n# Earlier step: {name}\n\n{json.dumps(data, ensure_ascii=False, indent=2)}"
        if step == "narration":
            budgets = "\n".join(f"- {s['id']} ({s['duration_s']} s): at most {word_budget(s['duration_s'], st['wps'])} words"
                                for s in earlier["shots"]["shots"])
            prompt = prompt.replace("{budgets}", budgets).replace("{wps}", str(st["wps"]))
        if unit.id in self._feedback:
            answer, problems = self._feedback.pop(unit.id)
            prompt += ("\n\n# Your previous answer broke these rules. Answer again, fixing all of them.\n\n"
                       + "\n".join(f"- {p}" for p in problems))
            if answer is not None:
                prompt += f"\n\nYour previous answer:\n{json.dumps(answer, ensure_ascii=False)}"
        try:
            data, info = ctx.providers["text"].generate_json(prompt=prompt, schema=sch,
                                                             system=_prompt_file("story_system"))
        except RepairableError as e:
            self._feedback[unit.id] = (getattr(e, "answer", None), e.problems)
            raise
        problems = contract.json_problems(data, sch) or rule_problems(step, data, earlier, ctx.cfg)
        if problems:
            self._feedback[unit.id] = (data, problems)
            raise RepairableError(problems)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return info


# ---------- Y's hand edits ----------

def keep_hand_edits(ctx, units: list[Unit]) -> list[str]:
    """A draft whose bytes no longer match its sidecar was edited by Y. Keep it: back it up,
    re-sign the sidecar so the runner treats it as current, and log the edit. Steps after it
    see a new upstream hash and rerun; the step itself doesn't."""
    studio = Decisions(ctx.ws.root, ctx.ws.root / "storyboard.json", mock=ctx.ws.mock)
    kept = []
    for unit in units:
        meta = read_sidecar(unit.out)
        if not (meta and unit.out.exists()):
            continue
        now = sha256_file(unit.out)
        if now == meta.get("output_sha"):
            continue
        try:
            json.loads(unit.out.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"{ctx.ws.rel(unit.out)} isn't valid JSON after editing: {e}") from e
        backup = unit.out.parent / "edits" / f"{unit.out.stem}.{now[:8]}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(unit.out, backup)
        sidecar(unit.out).write_text(json.dumps({**meta, "output_sha": now, "edited_by": HUMAN}, indent=2,
                                                sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        studio.record("hand_edit", actor=HUMAN, draft=ctx.ws.rel(unit.out), sha=now[:12], backup=ctx.ws.rel(backup))
        kept.append(unit.id)
    return kept


def keep_drafts(ctx, chain: "StoryChain", steps: list[str]) -> list[str]:
    """Y keeps drafts across a change upstream, such as an edit to the brief after the beats
    were approved: each kept draft becomes current for the new inputs without being
    regenerated. Its sidecar is re-keyed and the decision is logged with both keys, so the
    record shows the draft was carried over, not made from the new brief."""
    from ..engine.runner import execute

    studio = Decisions(ctx.ws.root, ctx.ws.root / "storyboard.json", mock=ctx.ws.mock)
    kept = []
    for step in steps:                              # in chain order: a later key depends on earlier files
        outcome = {o.unit.id: o for o in execute(ctx, [chain], dry=True)}.get(step)
        if outcome is None:
            raise ValueError(f"'{step}' is not a story step ({', '.join(FILES)})")
        if outcome.state == "hit":
            continue
        meta = read_sidecar(outcome.unit.out)
        if outcome.state != "miss" or not meta or not outcome.unit.out.exists():
            raise ValueError(f"{step}: there is no draft to keep ({outcome.state} {outcome.note})".strip())
        now = sha256_file(outcome.unit.out)
        sidecar(outcome.unit.out).write_text(json.dumps(
            {**meta, "cache_key": outcome.key, "output_sha": now, "kept_by": HUMAN,
             "kept_from_key": meta.get("cache_key")}, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        studio.record("kept_draft", actor=HUMAN, step=step, draft=ctx.ws.rel(outcome.unit.out), sha=now[:12],
                      old_key=(meta.get("cache_key") or "")[:12], new_key=outcome.key[:12])
        kept.append(step)
    return kept


# ---------- from drafts to storyboard v1 ----------

def assemble_draft(ctx) -> dict:
    """Code, not a model: turn the five drafts into a complete storyboard. Fields only Y decides
    (languages, the main version, runtime, voices) come from config/pipeline.toml [story];
    who is real and their consent come from the outline Y approved at G1."""
    d, st = drafts_dir(ctx), ctx.cfg["story"]
    load = lambda step: json.loads((d / FILES[step]).read_text(encoding="utf-8"))  # noqa: E731
    outline, shots, narration, translation = load("outline"), load("shots"), load("narration"), load("translation")
    budgets = Policy.load(ctx.ws.root).budgets
    n_refs, n_music = budgets.get("reference_candidates", 4), budgets.get("music_candidates", 3)
    en = {line["shot"]: line["en"].strip() for line in narration["lines"]}
    am = {line["shot"]: line["am"].strip() for line in translation["lines"]}

    # Only people who appear in a shot become characters. Someone the story only speaks about
    # (a real person never shown, the grandmother who tells it) gets no character sheet and
    # needs no consent; anyone who does appear passes the lint's consent gate.
    on_screen = {cid for s in shots["shots"] for cid in s["characters"]}
    characters, references = [], []
    for i, c in enumerate(c for c in outline["cast"] if c["id"] in on_screen):
        rid = f"ref_{c['id']}"
        person = {"id": c["id"], "description": c["description"], "real_person": c["real_person"], "reference": rid}
        if c.get("consent_id"):
            person["consent_id"] = c["consent_id"]
        characters.append(person)
        references.append({"id": rid, "kind": "character", "characters": [c["id"]],
                           "prompt": f"character sheet of the same person: front view, three-quarter view and "
                                     f"profile, neutral expression, plain light background",
                           "seeds": [100 * (i + 1) + k for k in range(1, n_refs + 1)]})

    sb_shots = []
    for i, s in enumerate(shots["shots"], 1):
        m = s["motion"]
        motion = {"mode": m["mode"], "prompt": m["prompt"]}
        if m["mode"] == "i2v":
            motion.update(fallback="kenburns", seed=2000 + i)
        if m["mode"] in ("kenburns", "i2v"):
            motion["kenburns"] = {"zoom": m.get("zoom", "in"), "pan": m.get("pan", "none")}
        line = {lang: text for lang, text in (("en", en.get(s["id"], "")), ("am", am.get(s["id"], "")))
                if lang in st["languages"]}
        sb_shots.append({"id": s["id"], "reason": s["reason"], "beat": s["beat"], "size": s["size"],
                         "duration_s": s["duration_s"], "characters": s["characters"],
                         "image_prompt": s["image_prompt"], "keyframe_seed": 1000 + i, "motion": motion,
                         "narration": line})
    runtime = sum(s["duration_s"] for s in sb_shots) + st["end_card_s"]
    return {
        "version": 1,
        "meta": {"title": outline["title"], "logline": outline["logline"], "languages": st["languages"],
                 "primary": st["primary"], "runtime_s": st["runtime_s"]},
        "style": {"block": outline["look"]},
        "characters": characters,
        "references": references,
        "voices": {lang: dict(st["voices"][lang]) for lang in st["languages"]},
        "shots": sb_shots,
        "music": {"cues": [{"id": "m1", "from": sb_shots[0]["id"], "to": sb_shots[-1]["id"],
                            "caption": outline["music"], "instrumental": True,
                            "length_s": min(240, math.ceil(runtime + 15)),
                            "seeds": list(range(11, 11 + n_music))}]},
        "end_card": {"lines": list(st["end_card"]), "duration_s": st["end_card_s"]},
    }


def draft_path(ctx) -> Path:
    return drafts_dir(ctx) / DRAFT


def write_draft(ctx) -> tuple[dict, contract.Report]:
    sb = assemble_draft(ctx)
    path = draft_path(ctx)
    path.write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = contract.schema_errors(sb)
    if errors:
        return sb, contract.Report(errors=errors)
    ethics = ctx.ws.root / "ETHICS.md"
    return sb, contract.lint(sb, ethics.read_text(encoding="utf-8") if ethics.exists() else "")


def adopt(ctx, storyboard: Path, *, replace: bool = False, amharic_checked: bool = False) -> dict:
    """Gate G2: Y adopts the assembled draft as storyboard v1. Refused unless G1 still holds,
    the draft is complete and valid, and (if a storyboard exists) Y said --replace."""
    g1 = gate_g1(ctx)
    if g1:
        raise ValueError(g1)
    path = draft_path(ctx)
    if not path.exists():
        raise ValueError("there is no draft yet; run `film storyboard` until all five steps are done")
    sb, report = write_draft(ctx)
    if report.errors:
        raise ValueError("the draft isn't valid yet:\n  " + "\n  ".join(report.errors))
    if storyboard.exists() and not replace:
        raise ValueError(f"{storyboard.name} already exists; adopting would replace it. Add --replace if you mean it")
    storyboard.write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    history = ctx.ws.base / "docs" / "storyboard-history"
    history.mkdir(parents=True, exist_ok=True)
    version = len(list(history.glob("v*.json"))) + 1
    snapshot = history / f"v{version}.json"
    shutil.copy(storyboard, snapshot)
    studio = Decisions(ctx.ws.root, storyboard, mock=ctx.ws.mock)
    return studio.record("adopted", gate="G2", actor=HUMAN, by=HUMAN, draft_sha=sha256_file(path)[:12],
                         storyboard=ctx.ws.rel(storyboard), snapshot=ctx.ws.rel(snapshot),
                         amharic_checked=amharic_checked, warnings=report.warnings)
