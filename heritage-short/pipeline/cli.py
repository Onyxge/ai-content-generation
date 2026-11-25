"""`film`, the single entry point. Every Make target wraps one of these subcommands.

Exit codes: 0 ok, 1 something failed, 2 the storyboard is invalid, 75 a daily quota ran
out and the run can be resumed later (ADR-008)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from . import assemble, contract, providers
from .config import load_config
from .engine.logs import RunLog
from .engine.runner import Ctx, Outcome, execute
from .engine.workspace import Workspace
from .keyframes import Keyframes
from .music import Music
from .narration import Narration
from .references import References
from .shots import Shots

STAGES = (References, Keyframes, Narration, Music, Shots)
LANGS = ("en", "am")
OK, FAILED, INVALID, DEFERRED = 0, 1, 2, 75


def _stages():
    return [cls() for cls in STAGES]


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


def cmd_assemble(args) -> int:
    ctx = _context(args)
    if ctx is None:
        return INVALID
    return _assemble(ctx, execute(ctx, _stages(), dry=True), args)


def cmd_radio(args) -> int:
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
    ctx = _context(args)
    if ctx is None:
        return INVALID
    outcomes = execute(ctx, _stages())
    rendered = _report(outcomes, ctx)
    assembled = _assemble(ctx, outcomes, args)
    return FAILED if FAILED in (rendered, assembled) else max(rendered, assembled)


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
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("render", parents=[common], help="generate whatever changed")
    p.add_argument("--stage", action="append", choices=[cls.name for cls in STAGES], help="limit to a stage")
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

    args = parser.parse_args(argv)
    return args.fn(args)
