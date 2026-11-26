"""The GPU round trip (ADR-006): `film bundle` → gpu/runner.py on Kaggle or Colab → `film ingest`.

Moving shots (Wan 2.2) and the score (ACE-Step 1.5) need a GPU that Y's laptop doesn't have.
They are units like any other, with cache keys computed here, but they're rendered elsewhere:

- `bundle` packs every uncached GPU unit of a stage into a self-contained zip: a manifest
  with each job's spec and cache key, the input images, and the runner script itself.
- The runner (gpu/runner.py) works anywhere with a GPU, writes each output the moment it's
  done, and appends one line per job to results.jsonl, failures included, with GPU seconds.
- `ingest` reads that back. A result enters the cache only if its key still matches what
  the storyboard asks for now; a result for an edited shot is stale and is skipped. Every
  result, failed or not, becomes a runs.jsonl line, so GPU time is measured like API time.

Until a clip is ingested, assembly uses the Ken Burns fallback (ADR-005)."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from .engine.cache import is_fresh, write_sidecar
from .engine.logs import read_jsonl
from .engine.runner import Ctx, execute
from .engine.workspace import sha256_file, utc_now
from .registry import stages

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "gpu" / "runner.py"
PROVIDER_FOR = {"shots": "video", "music": "music"}


def bundles_dir(ctx: Ctx) -> Path:
    return ctx.ws.root / "build" / "bundles"


def gpu_outcomes(ctx: Ctx, stage: str, everything: list | None = None):
    """Every GPU unit of a stage, evaluated against the cache without building anything."""
    provider = PROVIDER_FOR[stage]
    everything = everything if everything is not None else execute(ctx, stages(), dry=True)
    return [o for o in everything if o.unit.stage == stage and o.unit.provider == provider]


def job_of(outcome, ctx: Ctx) -> dict:
    u, s = outcome.unit, outcome.unit.spec
    job = {"id": u.id, "key": outcome.key, "out": u.out.name}
    if u.stage == "shots":
        job.update(kind="i2v", model=ctx.cfg["video"]["i2v_model"], image=f"inputs/{u.id}.png",
                   prompt=s["prompt"], seed=s["seed"], size=s["size"], frames=s["frames"], fps=s["fps"],
                   steps=s["steps"])
    else:
        job.update(kind="music", model=ctx.cfg["music"]["model"], caption=s["caption"], seed=s["seed"],
                   length_s=s["length_s"], bpm=s.get("bpm"), key_signature=s.get("key"),
                   instrumental=s.get("instrumental", True), steps=s["steps"])
    return job


def bundle(ctx: Ctx, stage: str) -> tuple[Path | None, list[dict], list[str]]:
    """Pack the stage's uncached GPU jobs. Returns (zip path or None, jobs, reasons units were left out)."""
    jobs, left_out = [], []
    inputs: dict[str, Path] = {}
    everything = execute(ctx, stages(), dry=True)
    by_ref = {o.unit.ref: o for o in everything}
    for o in gpu_outcomes(ctx, stage, everything):
        if o.state == "hit":
            continue
        if o.state != "miss":
            left_out.append(f"{o.unit.id}: {o.state} ({o.note})")
            continue
        jobs.append(job_of(o, ctx))
        if stage == "shots":
            inputs[f"inputs/{o.unit.id}.png"] = by_ref[o.unit.deps[0]].unit.out      # the shot's keyframe
    if not jobs:
        return None, [], left_out
    name = f"{'mock-' if ctx.ws.mock else ''}{stage}-{ctx.ws.run_id}"
    out = bundles_dir(ctx)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.zip"
    manifest = {"bundle": name, "created": utc_now(), "stage": stage, "jobs": jobs}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for script in sorted(RUNNER.parent.glob("runner*.py")):     # the runner and its model backends
            z.write(script, script.name)
        for arc, src in inputs.items():
            z.write(src, arc)
    return path, jobs, left_out


def _results_files(source: Path, tmp: Path) -> list[Path]:
    """Every results*.jsonl under the runner's output folder, or under a zip of it (as Kaggle's
    download gives you). One Kaggle session can hold several bundles, each in its own folder."""
    if not source.is_dir():
        with zipfile.ZipFile(source) as z:
            z.extractall(tmp)
        source = tmp
    found = sorted(source.rglob("results*.jsonl"))
    if not found:
        raise ValueError(f"no results.jsonl in {source}")
    return found


def ingest(ctx: Ctx, source: Path) -> list[tuple[str, str, str]]:
    """Bring GPU results into the cache and the logs. Returns (unit, verdict, note) per result."""
    tmp = ctx.ws.root / "build" / "ingest-tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        last: dict[str, tuple] = {}                  # the final line per job; "started" alone means it died
        for f in _results_files(Path(source), tmp):
            for r in read_jsonl(f):
                last[r["id"]] = (f.parent, r)
        results = []
        for root, r in last.values():
            if r.get("status") == "started":
                r = {**r, "status": "error", "error": "the runner died during this job and wrote no result "
                                                       "(killed, e.g. out of host memory: see the run's log)"}
            results.append((root, r))
        everything = execute(ctx, stages(), dry=True)
        current = {}
        for stage in PROVIDER_FOR:
            current.update({o.unit.id: o for o in gpu_outcomes(ctx, stage, everything)})
        report = []
        for root, r in results:
            o = current.get(r["id"])
            base = dict(stage=o.unit.stage if o else r.get("stage", "?"), unit=r["id"], attempt=r.get("attempt", 1),
                        actor=ctx.actor, provider=f"gpu-runner ({r.get('env', '?')})", model=r.get("model"),
                        params={k: r[k] for k in ("device", "precision", "offload", "steps", "size", "frames", "guidance",
                                                  "peak_vram_gb", "load_s", "bundle") if k in r},
                        seed=r.get("seed"), cache_key=(r.get("key") or "")[:12],
                        latency_ms=int(1000 * (r.get("seconds") or 0)), gpu_s=r.get("gpu_s"))
            if r.get("status") != "ok":
                ctx.log.model_call(**base, status="error", output=None, output_sha=None,
                                   error=str(r.get("error"))[:300])
                report.append((r["id"], "failed", str(r.get("error"))[:120]))
                continue
            if o is None or o.key != r.get("key"):
                report.append((r["id"], "stale", "the storyboard changed since this job was bundled; not ingested"))
                continue
            if is_fresh(o.unit.out, o.key):
                report.append((r["id"], "already in cache", ""))
                continue
            produced = root / "outputs" / r["out"]
            if not produced.exists():
                report.append((r["id"], "missing", f"results.jsonl says ok but {r['out']} isn't there"))
                continue
            o.unit.out.parent.mkdir(parents=True, exist_ok=True)
            part = o.unit.out.with_name(f".tmp-{o.unit.out.name}")
            shutil.copy(produced, part)
            part.replace(o.unit.out)
            write_sidecar(o.unit.out, o.key, {"stage": o.unit.stage, "unit": o.unit.id, "run_id": ctx.ws.run_id,
                                              "provider": base["provider"], "model": r.get("model"),
                                              "seed": r.get("seed"), "gpu_s": r.get("gpu_s")})
            ctx.log.model_call(**base, status="ok", output=ctx.ws.rel(o.unit.out),
                               output_sha=sha256_file(o.unit.out)[:12], error=None)
            report.append((r["id"], "ingested", f"{r.get('gpu_s')} GPU s on {r.get('device', '?')}"))
        return report
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
