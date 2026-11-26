"""`film`, the single entry point. Every Make target wraps one of these subcommands.

Exit codes: 0 ok, 1 something failed, 2 the storyboard is invalid, 75 a daily quota ran
out and the run can be resumed later (ADR-008)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from . import assemble, contract, media, providers
from .agents.decisions import DecisionError, Decisions, describe
from .agents.patches import MISSING as MISSING_CELL
from .config import load_config
from .env import load_dotenv
from .engine.logs import RunLog, read_jsonl
from .engine.runner import Ctx, Outcome, execute
from .engine.workspace import Workspace, sha256_file
from .registry import STAGES, stages
LANGS = ("en", "am")
OK, FAILED, INVALID, DEFERRED = 0, 1, 2, 75


def _stages():
    return stages()


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def _storyboard_path(args) -> Path:
    root = Path(args.root).resolve()
    return Path(args.storyboard).resolve() if args.storyboard else root / "storyboard.json"


def _check(args) -> contract.Report | None:
    path = _storyboard_path(args)
    if not path.exists():
        _err(f"No storyboard at {path}. The director drafts one with `make storyboard` (U4); "
             "`make mock` runs the example.")
        return None
    report = contract.check(path, Path(args.root).resolve() / "ETHICS.md")
    for w in report.warnings:
        _err(f"warning: {w}")
    for e in report.errors:
        _err(f"error: {e}")
    return report


def _context(args) -> Ctx | None:
    report = _check(args)
    if report is None or not report.ok:
        return None
    root = Path(args.root).resolve()
    cfg = load_config(root)
    if not args.mock:
        load_dotenv(root)
    ws = Workspace.create(root, mock=args.mock)
    return Ctx(ws=ws, sb=contract.load(_storyboard_path(args)), cfg=cfg,
               providers=providers.load(cfg, args.mock), log=RunLog(ws))


def cmd_validate(args) -> int:
    report = _check(args)
    if report is None or not report.ok:
        return INVALID
    print(f"{_storyboard_path(args).name} is valid ({len(report.warnings)} warnings).")
    return OK


def cmd_plan(args) -> int:
    ctx = _context(args)
    if ctx is None:
        return INVALID
    ctx.langs = tuple(args.lang) if args.lang else None
    outcomes = execute(ctx, _stages(), dry=True)
    if args.json:
        print(json.dumps([o.as_dict() for o in outcomes], ensure_ascii=False))
        return OK
    cached = Counter(o.unit.stage for o in outcomes if o.state == "hit")
    todo = [o for o in outcomes if o.state != "hit"]
    where = "mock workspace (build/mock/)" if ctx.ws.mock else "real workspace"
    print(f"Plan for '{ctx.sb['meta']['title']}' v{ctx.sb['version']} in the {where}")
    print("  cached: " + (", ".join(f"{s} {n}" for s, n in cached.items()) or "nothing yet"))
    if not todo:
        print("  nothing to generate; assembly will rebuild the films from the cache")
        return OK
    for o in todo:
        what = o.note or (f"model call ({o.unit.provider})" if o.unit.provider else "local render (FFmpeg)")
        print(f"  {o.unit.stage:<11}{o.unit.id:<15}{o.state:<10}{what}")
    pending = [o for o in todo if o.state in ("miss", "upstream")]
    calls = Counter(o.unit.provider for o in pending if o.unit.provider)
    local = sum(1 for o in pending if not o.unit.provider)
    by_provider = f" ({', '.join(f'{p} {n}' for p, n in calls.items())})" if calls else ""
    print(f"Model calls if you render now: {sum(calls.values())}{by_provider}. Local renders: {local}. "
          f"Blocked: {sum(1 for o in todo if o.state == 'blocked')}. Assembly always reruns.")
    return OK


def _report(outcomes: list[Outcome], ctx: Ctx) -> int:
    counts = Counter(o.state for o in outcomes)
    print("Render: " + ", ".join(f"{state} {n}" for state, n in sorted(counts.items())))
    for o in outcomes:
        if o.state in ("failed", "deferred", "pending", "blocked"):
            print(f"  {o.unit.stage}:{o.unit.id} {o.state}: {o.note}")
    print(f"Model calls are logged in {ctx.ws.rel(ctx.ws.runs_log)}.")
    if counts.get("failed"):
        return FAILED
    return DEFERRED if counts.get("deferred") else OK


def cmd_render(args) -> int:
    ctx = _context(args)
    if ctx is None:
        return INVALID
    ctx.langs = tuple(args.lang) if args.lang else None
    return _report(execute(ctx, _stages(), only=set(args.stage) if args.stage else None), ctx)


def _print_records(records: list[dict]) -> None:
    for r in records:
        pictures = f"  pictures {r['pictures']}" if "pictures" in r else ""
        print(f"  {r['output']}  {r['duration_s']:.1f}s  {r['integrated_lufs']} LUFS  "
              f"true peak {r['true_peak_db']} dB{pictures}")


def _assemble(ctx: Ctx, outcomes: list[Outcome], args) -> int:
    try:
        records = assemble.assemble(ctx, outcomes, langs=args.lang, orients=args.orient)
    except assemble.AssemblyError as e:
        _err(f"error: {e}")
        return FAILED
    print("Assembled:")
    _print_records(records)
    return OK


def _ffmpeg_ready() -> bool:
    missing = media.missing_filters()
    if missing:
        _err(f"error: this FFmpeg build lacks {', '.join(missing)}. On macOS install `ffmpeg-full` "
             "(Homebrew's slim `ffmpeg` has no libass, so no subtitles); see FAILURES.md F2.")
    return not missing


def cmd_assemble(args) -> int:
    if not _ffmpeg_ready():
        return FAILED
    ctx = _context(args)
    if ctx is None:
        return INVALID
    return _assemble(ctx, execute(ctx, _stages(), dry=True), args)


def cmd_radio(args) -> int:
    if not _ffmpeg_ready():
        return FAILED
    ctx = _context(args)
    if ctx is None:
        return INVALID
    try:
        records = assemble.radio(ctx, execute(ctx, _stages(), dry=True), langs=args.lang)
    except assemble.AssemblyError as e:
        _err(f"error: {e}")
        return FAILED
    print("Radio cut:")
    _print_records(records)
    return OK


def cmd_build(args) -> int:
    if not _ffmpeg_ready():
        return FAILED
    ctx = _context(args)
    if ctx is None:
        return INVALID
    outcomes = execute(ctx, _stages())
    rendered = _report(outcomes, ctx)
    assembled = _assemble(ctx, outcomes, args)
    return FAILED if FAILED in (rendered, assembled) else max(rendered, assembled)


def cmd_smoke(args) -> int:
    """One tiny call per hosted provider, logged like any other call. No storyboard needed."""
    from .smoke import Smoke

    root = Path(args.root).resolve()
    cfg = load_config(root)
    if not args.mock:
        load_dotenv(root)
    ws = Workspace.create(root, mock=args.mock)
    ctx = Ctx(ws=ws, sb={}, cfg=cfg, providers=providers.load(cfg, args.mock), log=RunLog(ws))
    outcomes = execute(ctx, [Smoke()])
    for o in outcomes:
        line = next((r for r in reversed(read_jsonl(ws.runs_log)) if r.get("stage") == "smoke"
                     and r.get("unit") == o.unit.id), None) if o.state == "built" else None
        latency = f"  {line['latency_ms']} ms  {line['model']}" if line else ""
        print(f"  {o.unit.id:<7} {o.state:<8}{latency}{('  ' + o.note) if o.note else ''}")
    missing = media.missing_filters()
    print("  ffmpeg  " + ("ok" if not missing else f"missing filters: {', '.join(missing)} (FAILURES.md F2)"))
    failed = [o for o in outcomes if o.state not in ("built", "hit")]
    return FAILED if failed or missing else OK


# ---------- the story agent (A2) ----------

def _print_story_drafts(ctx, story) -> None:
    d = story.drafts_dir(ctx)
    outline_p, beats_p = d / story.FILES["outline"], d / story.FILES["beats"]
    if outline_p.exists():
        o = json.loads(outline_p.read_text(encoding="utf-8"))
        print(f"\n  {o['title']}: {o['logline']}")
        print("  Cast (only you decide who is real and their consent; check every row):")
        for c in o["cast"]:
            if not c["real_person"]:
                real = "not a real person"
            elif c.get("consent_id"):
                real = f"REAL person, consent {c['consent_id']}"
            else:
                real = "REAL person, no consent: may be spoken about, never shown (the shot step enforces it)"
            print(f"    {c['id']:<24} {c['role']:<26} {real}")
        print(f"  Look:  {o['look']}\n  Music: {o['music']}\n  Feeling at the end: {o['feeling']}")
    if beats_p.exists():
        print("  Beats:")
        for b in json.loads(beats_p.read_text(encoding="utf-8"))["beats"]:
            print(f"    {b['id']}  {b['summary']}  ({b['feeling']})")


def cmd_storyboard(args) -> int:
    from .agents import story

    root = Path(args.root).resolve()
    cfg = load_config(root)
    if not args.mock:
        load_dotenv(root)
    ws = Workspace.create(root, mock=args.mock)
    ctx = Ctx(ws=ws, sb={}, cfg=cfg, providers=providers.load(cfg, args.mock), log=RunLog(ws), actor="story")
    chain = story.StoryChain()
    try:
        for step in story.keep_hand_edits(ctx, chain.units(ctx)):
            print(f"Kept your edit to the {step} draft (a copy is in docs/story/drafts/edits/); the steps after it will rerun.")
    except ValueError as e:
        _err(f"error: {e}")
        return INVALID

    if args.keep:
        steps = [s.strip() for s in args.keep.split(",") if s.strip()]
        try:
            for step in story.keep_drafts(ctx, chain, steps):
                print(f"Kept the {step} draft for the current brief without regenerating it (logged in decisions.jsonl).")
        except ValueError as e:
            _err(f"error: {e}")
            return INVALID

    if args.adopt:
        try:
            record = story.adopt(ctx, _storyboard_path(args), replace=args.replace, amharic_checked=args.amharic_checked)
        except ValueError as e:
            _err(f"error: {e}")
            return INVALID
        print(f"Adopted the draft as {record['storyboard']} (gate G2); snapshot {record['snapshot']}.")
        if not args.amharic_checked:
            print("The Amharic text hasn't been checked by a native speaker yet; check it before voicing it.")
        print("From now on every change is a proposal (`film proposals`). Next: `film plan`, then narration and the radio cut.")
        return OK

    if args.approve_beats:
        d = story.drafts_dir(ctx)
        paths = [d / story.FILES["outline"], d / story.FILES["beats"]]
        if not all(p.exists() for p in paths):
            _err("error: there is no outline and beat sheet to approve yet; run `film storyboard` first")
            return INVALID
        Decisions(root, _storyboard_path(args), mock=args.mock).record(
            "gate", gate="G1", actor="Y", by="Y", drafts={p.name: sha256_file(p)[:12] for p in paths})
        print("Gate G1 passed: the outline and beats are approved as they are now.")

    outcomes = execute(ctx, [chain])
    for o in outcomes:
        print(f"  {o.unit.id:<12} {o.state:<9}{o.note}")
    states = {o.unit.id: o.state for o in outcomes}
    if any(s == "failed" for s in states.values()):
        print(f"A step failed; every attempt is in {ws.rel(ws.runs_log)}.")
        return FAILED
    if any(s == "deferred" for s in states.values()):
        return DEFERRED
    if states.get("beats") in ("built", "hit") and states.get("shots") == "blocked":
        _print_story_drafts(ctx, story)
        print("\nRead docs/story/drafts/01-outline.json and 02-beats.json. Edit them if the story isn't right "
              "(your edits are kept), then run `film storyboard --approve-beats` (gate G1).")
        return OK
    if all(s in ("built", "hit") for s in states.values()):
        _, report = story.write_draft(ctx)
        print(f"\nDraft storyboard: {ws.rel(story.draft_path(ctx))}")
        for w in report.warnings:
            print(f"  warning: {w}")
        for e in report.errors:
            print(f"  to fix before adopting: {e}")
        if report.ok:
            print("It validates. Read it, have a native speaker check the Amharic lines, then run "
                  "`film storyboard --adopt` (gate G2).")
    return OK


# ---------- the GPU round trip (ADR-006) ----------

def cmd_bundle(args) -> int:
    from . import gpu

    ctx = _context(args)
    if ctx is None:
        return INVALID
    path, jobs, left_out = gpu.bundle(ctx, args.stage)
    for why in left_out:
        print(f"  left out {why}")
    if path is None:
        print(f"Nothing to bundle for {args.stage}: every GPU unit is cached or blocked.")
        return OK
    print(f"Bundled {len(jobs)} {args.stage} job(s): {ctx.ws.rel(path)}")
    for j in jobs:
        print(f"  {j['id']:<14} key {j['key'][:12]}  {j.get('prompt') or j.get('caption')}")
    print("Upload the zip to Kaggle as a dataset and run gpu/kaggle_runner.ipynb on GPU T4 x2 "
          "(see gpu/README.md); then `film ingest <downloaded output>`.")
    return OK


def cmd_ingest(args) -> int:
    from . import gpu

    ctx = _context(args)
    if ctx is None:
        return INVALID
    try:
        report = gpu.ingest(ctx, Path(args.source))
    except (ValueError, OSError) as e:
        _err(f"error: {e}")
        return FAILED
    for unit, verdict, note in report:
        print(f"  {unit:<14} {verdict:<17}{note}")
    print(f"Every result, failures included, is logged in {ctx.ws.rel(ctx.ws.runs_log)}. "
          "Shots still without a clip keep their Ken Burns fallback.")
    return OK


def _latest_bundles(root: Path) -> list[Path]:
    """The newest real (not mock) bundle of each stage."""
    found = []
    for stage in ("shots", "music"):
        zips = sorted((root / "build" / "bundles").glob(f"{stage}-*.zip"), key=lambda p: p.stat().st_mtime_ns)
        if zips:
            found.append(zips[-1])
    return found


def cmd_kaggle(args) -> int:
    from . import gpu, kaggle_jobs

    root = Path(args.root).resolve()
    load_dotenv(root)
    try:
        if args.action == "push":
            bundles = [Path(b) for b in args.bundle] if args.bundle else _latest_bundles(root)
            record = kaggle_jobs.push(root, bundles, limit=args.limit, timeout_s=args.timeout)
            print(f"Launched {record['kernel']} with {', '.join(record['bundles'])}.")
            print("Check it with `film kaggle status`; when it says complete, `film kaggle pull`.")
            return OK
        if args.action == "status":
            print(kaggle_jobs.status())
            return OK
        source = kaggle_jobs.pull(root)
        print(f"Downloaded the run's output to {source.relative_to(root)}; ingesting…")
    except kaggle_jobs.KaggleError as e:
        _err(f"error: {e}")
        return FAILED
    args.source = str(source)
    return cmd_ingest(args)


def cmd_costs(args) -> int:
    from . import costs

    body = costs.write(Path(args.root).resolve())
    print(body)
    print("COSTS.md updated between its markers.")
    return OK


# ---------- decisions (ADR-018) ----------

def _decisions(args) -> Decisions | None:
    path = _storyboard_path(args)
    if not path.exists():
        _err(f"No storyboard at {path}.")
        return None
    return Decisions(Path(args.root), path, mock=args.mock)


def _print_proposal(p: dict, detail: bool = False) -> None:
    confirmed = " (applied, waiting for Y to confirm or revert)" if p["status"] == "applied" and not p.get("confirmed") else ""
    print(f"{p['id']} {p['status']}{confirmed}  by {p['actor']}  kinds {', '.join(p['kinds']) or '-'}  "
          f"autonomy {p['autonomy']}")
    if detail and p.get("rationale"):
        print(f"  why: {p['rationale']}")
    if detail and p.get("evidence"):
        print(f"  evidence: {describe(p['evidence'], 200)}")
    for c in p["changes"]:
        before = describe(MISSING_CELL if c["before"].get("missing") else c["before"]["value"])
        after = describe(MISSING_CELL if c["after"].get("missing") else c["after"]["value"])
        print(f"  {c['path']}: {before} -> {after}")
    for e in p.get("errors", []):
        print(f"  refused: {e}")
    if "price" in p:
        calls = p["price"]["model_calls"]
        print(f"  price: {sum(calls.values())} model calls"
              + (f" ({', '.join(f'{k} {v}' for k, v in calls.items())})" if calls else "")
              + f", {p['price']['local_renders']} local renders")


def cmd_propose(args) -> int:
    studio = _decisions(args)
    if studio is None:
        return INVALID
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    actor = args.actor or data.get("actor")
    if not actor:
        _err("error: say who proposes this, with --actor or an \"actor\" field")
        return INVALID
    p = studio.propose(actor, data.get("patch"), rationale=data.get("rationale", ""), evidence=data.get("evidence"))
    _print_proposal(p)
    return INVALID if p["status"] == "refused" else OK


def cmd_proposals(args) -> int:
    studio = _decisions(args)
    if studio is None:
        return INVALID
    shown = studio.all() if args.all else studio.waiting()
    if not shown:
        print("Nothing is waiting for Y." if not args.all else "No proposals yet.")
    for p in shown:
        _print_proposal(p, detail=True)
    return OK


def _verb(fn_name: str):
    def run(args) -> int:
        studio = _decisions(args)
        if studio is None:
            return INVALID
        try:
            p = getattr(studio, fn_name)(args.id, why=args.why or "")
        except DecisionError as e:
            _err(f"error: {e}")
            return FAILED
        _print_proposal(p)
        return OK
    return run


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="repository root (default: the current directory)")
    common.add_argument("--storyboard", help="storyboard to use (default: <root>/storyboard.json)")
    common.add_argument("--mock", action="store_true",
                        help="placeholder providers; everything is written under build/mock/")

    parser = argparse.ArgumentParser(prog="film", description="Render the Heritage Short from storyboard.json.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", parents=[common], help="schema, lint and consent gate").set_defaults(fn=cmd_validate)
    p = sub.add_parser("plan", parents=[common], help="dry run: what would be generated, and how many model calls")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--lang", action="append", choices=LANGS, help="only this language's narration")
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("render", parents=[common], help="generate whatever changed")
    p.add_argument("--stage", action="append", choices=[cls.name for cls in STAGES], help="limit to a stage")
    p.add_argument("--lang", action="append", choices=LANGS, help="only this language's narration")
    p.set_defaults(fn=cmd_render)
    for name, fn, help_text in (("assemble", cmd_assemble, "build the films from the cache"),
                                ("build", cmd_build, "render whatever changed, then assemble everything")):
        p = sub.add_parser(name, parents=[common], help=help_text)
        p.add_argument("--lang", action="append", choices=LANGS)
        p.add_argument("--orient", action="append", choices=list(assemble.ORIENTS))
        p.set_defaults(fn=fn)
    p = sub.add_parser("radio", parents=[common], help="narration over a temp drone on black, with subtitles")
    p.add_argument("--lang", action="append", choices=LANGS)
    p.set_defaults(fn=cmd_radio)

    p = sub.add_parser("storyboard", parents=[common], help="the story agent: brief → drafts → storyboard v1 (A2)")
    p.add_argument("--approve-beats", action="store_true", help="gate G1: approve the outline and beats as they are")
    p.add_argument("--keep", metavar="STEPS", help="keep these drafts (e.g. outline,beats) after the brief changed, "
                                                   "instead of regenerating them; logged as Y's decision")
    p.add_argument("--adopt", action="store_true", help="gate G2: adopt the assembled draft as storyboard.json")
    p.add_argument("--replace", action="store_true", help="with --adopt: replace an existing storyboard.json")
    p.add_argument("--amharic-checked", action="store_true", help="with --adopt: a native speaker checked the Amharic")
    p.set_defaults(fn=cmd_storyboard)
    p = sub.add_parser("bundle", parents=[common], help="pack uncached GPU jobs for Kaggle or Colab (ADR-006)")
    p.add_argument("stage", choices=["shots", "music"])
    p.set_defaults(fn=cmd_bundle)
    p = sub.add_parser("ingest", parents=[common], help="bring GPU results back into the cache and the logs")
    p.add_argument("source", help="the runner's output folder, or a zip of it")
    p.set_defaults(fn=cmd_ingest)
    p = sub.add_parser("kaggle", parents=[common], help="push bundles to a private Kaggle run, check it, pull results")
    p.add_argument("action", choices=["push", "status", "pull"])
    p.add_argument("--bundle", action="append", help="bundle zip to push (default: the newest of each stage)")
    p.add_argument("--limit", type=int, default=0, help="jobs per bundle (1 for a spike; 0 = all)")
    p.add_argument("--timeout", type=int, default=0, help="stop the run after this many seconds")
    p.set_defaults(fn=cmd_kaggle)
    sub.add_parser("costs", parents=[common], help="regenerate COSTS.md's tables from the logs (U9)").set_defaults(fn=cmd_costs)
    sub.add_parser("smoke", parents=[common], help="one tiny logged call per provider, once a day").set_defaults(fn=cmd_smoke)
    p = sub.add_parser("propose", parents=[common], help="check an agent's proposal and file it (ADR-018)")
    p.add_argument("file", help="JSON with actor, rationale, evidence and patch (paths address items by id)")
    p.add_argument("--actor", help="who proposes it, if the file doesn't say")
    p.set_defaults(fn=cmd_propose)
    p = sub.add_parser("proposals", parents=[common], help="what is waiting for Y")
    p.add_argument("--all", action="store_true", help="every proposal, including refused and settled ones")
    p.set_defaults(fn=cmd_proposals)
    for verb, help_text in (("approve", "apply a pending proposal, or confirm one applied under veto"),
                            ("reject", "turn down a pending proposal (an applied one is reverted)"),
                            ("revert", "undo an applied proposal")):
        p = sub.add_parser(verb, parents=[common], help=help_text)
        p.add_argument("id", help="proposal id, such as P-0007")
        p.add_argument("--why", help="the reason, for decisions.jsonl")
        p.set_defaults(fn=_verb(verb))

    args = parser.parse_args(argv)
    return args.fn(args)
