"""The GPU runner (ADR-006). It runs one bundle made by `film bundle` on any machine with a GPU,
such as a Kaggle notebook (GPU T4 x2) or Colab, and needs nothing from the repo but itself.

    python runner.py --bundle /kaggle/input/<dataset> --out /kaggle/working/out [--gpu 0 --shards 2]

- Every output is written the moment its job finishes, and one line is appended to
  out/results.jsonl per job, failures included, with GPU seconds and peak memory.
  A session that dies loses only the job it was on.
- Re-running with the same --out skips jobs already done, so a session can resume.
- With two GPUs, start two processes: `--gpu 0 --shards 2` and `--gpu 1 --shards 2`. Each
  takes every other job.
- Back in the repo, `film ingest <out or its zip>` brings the results into the cache.

Backends: `wan` (Wan 2.2 TI2V-5B image-to-video), `acestep` (ACE-Step 1.5 music) and `mock`
(placeholder files, no GPU, for tests). The model code is imported only when needed."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def env_name() -> str:
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or Path("/kaggle").exists():
        return "kaggle"
    if "google.colab" in sys.modules or os.environ.get("COLAB_RELEASE_TAG"):
        return "colab"
    return "local"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_bundle(path: Path) -> tuple[dict, Path]:
    """A bundle is a zip or a folder (Kaggle unzips an uploaded zip into a dataset folder)."""
    if path.is_file():
        target = path.with_suffix("")
        with zipfile.ZipFile(path) as z:
            z.extractall(target)
        path = target
    hits = list(path.rglob("manifest.json"))
    if not hits:
        sys.exit(f"no manifest.json under {path}")
    root = hits[0].parent
    return json.loads((root / "manifest.json").read_text(encoding="utf-8")), root


def done_ids(results: Path) -> set[str]:
    if not results.exists():
        return set()
    return {json.loads(l)["id"] for l in results.read_text(encoding="utf-8").splitlines()
            if l.strip() and json.loads(l).get("status") == "ok"}


# ---------- backends ----------

class Mock:
    """Placeholder outputs with no GPU: a short clip of the still, a silent WAV."""
    name, precision = "mock", "none"

    def run(self, job: dict, root: Path, out: Path) -> dict:
        if job["kind"] == "i2v":
            w, h = job["size"]
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1",
                            "-i", str(root / job["image"]), "-t", str(job["frames"] / job["fps"]),
                            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=yuv420p",
                            "-r", str(job["fps"]), str(out)], check=True)
        else:
            with wave.open(str(out), "wb") as f:
                f.setnchannels(2), f.setsampwidth(2), f.setframerate(48000)
                f.writeframes(b"\x00\x00\x00\x00" * int(48000 * job["length_s"]))
        return {"model": f"mock ({job['model']})", "steps": 0}


def backend_for(kind: str, name: str, gpu: int, jobs: list[dict]):
    """Backends see all their jobs up front: Wan encodes every prompt once, then frees its
    11 GB text encoder before the transformer needs the memory (FAILURES.md F8)."""
    if name == "mock":
        return Mock()
    if kind == "i2v":
        from runner_wan import Wan          # noqa: E402  (next to this file in the bundle, see gpu/)
        return Wan(gpu, jobs)
    from runner_acestep import AceStep      # noqa: E402
    return AceStep(gpu)


# ---------- the loop ----------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--gpu", type=int, default=0, help="which GPU this process uses")
    ap.add_argument("--shards", type=int, default=1, help="how many processes share the bundle")
    ap.add_argument("--backend", choices=["auto", "mock"], default="auto")
    ap.add_argument("--limit", type=int, default=0, help="run at most this many jobs (spike S1: 1)")
    args = ap.parse_args(argv)

    manifest, root = load_bundle(args.bundle)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    outputs = args.out / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    results = args.out / ("results.jsonl" if args.shards == 1 else f"results-{args.gpu}.jsonl")
    finished = set().union(*(done_ids(p) for p in args.out.glob("results*.jsonl")))
    mine = [j for i, j in enumerate(manifest["jobs"]) if i % args.shards == args.gpu % args.shards]
    todo = [j for j in mine if j["id"] not in finished]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{manifest['bundle']}: {len(manifest['jobs'])} jobs, {len(mine)} for this process, "
          f"{len(todo)} to do on GPU {args.gpu} ({env_name()})", flush=True)

    backends: dict[str, object] = {}
    for job in todo:
        record = {"ts": now(), "id": job["id"], "key": job["key"], "out": job["out"], "seed": job.get("seed"),
                  "bundle": manifest["bundle"], "env": env_name(), "device": f"cuda:{args.gpu}"}
        with open(results, "a", encoding="utf-8") as f:     # if the OS kills us mid-job, this line says so
            f.write(json.dumps({**record, "status": "started"}, ensure_ascii=False) + "\n")
        t0 = time.perf_counter()
        try:
            if job["kind"] not in backends:          # loading weights is timed apart from the job (load_s)
                backends[job["kind"]] = backend_for(job["kind"], args.backend, args.gpu,
                                                    [j for j in todo if j["kind"] == job["kind"]])
                record["load_s"] = round(time.perf_counter() - t0, 2)
                t0 = time.perf_counter()
            backend = backends[job["kind"]]
            _reset_peak(args.gpu)
            target = outputs / job["out"]
            part = target.with_name(f".part-{target.name}")
            info = backend.run(job, root, part)
            part.replace(target)
            record.update(status="ok", **info)
        except Exception as e:                       # noqa: BLE001 - every failure becomes a logged result
            traceback.print_exc()
            record.update(status="error", error=f"{type(e).__name__}: {e}"[:500], model=job.get("model"))
        seconds = round(time.perf_counter() - t0, 2)
        record.update(seconds=seconds, gpu_s=seconds if args.backend != "mock" else 0.0,
                      peak_vram_gb=_peak(args.gpu), precision=getattr(backends.get(job["kind"]), "precision", None))
        with open(results, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"  {job['id']}: {record['status']} in {seconds}s"
              + (f", peak {record['peak_vram_gb']} GB" if record["peak_vram_gb"] else ""), flush=True)
    return 0


def _reset_peak(gpu: int) -> None:
    """Peak memory is only measurable for backends that use the GPU in this process (Wan).
    ACE-Step runs in a subprocess; asking about a GPU this process never touched raises
    "Invalid device argument : did you call init?", which failed every music job of the first
    Kaggle run (FAILURES.md F7). So measuring is best effort and can never fail a job."""
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.is_initialized():
            torch.cuda.reset_peak_memory_stats(gpu)
    except (ImportError, RuntimeError):
        pass


def _peak(gpu: int):
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.is_initialized():
            return round(torch.cuda.max_memory_allocated(gpu) / 2**30, 2)
    except (ImportError, RuntimeError):
        pass
    return None


if __name__ == "__main__":
    raise SystemExit(main())
