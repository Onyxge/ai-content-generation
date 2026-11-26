"""ACE-Step 1.5, the GPU runner's `music` backend.

Checked 2026-11-26 (docs/build-log.md, Entry 12):
- ACE-Step 1.5 needs Python <3.13 and transformers <4.58; Kaggle's image is Python 3.13 with
  transformers 5.x. So it gets its own environment: the repo is cloned and `uv sync`ed with
  Python 3.12 once per session, and each job runs `runner_acestep_job.py` inside it as a
  subprocess. The PyPI package `ace-step` is the old v1; don't use it.
- DiT only (the turbo model, 8 steps): the optional language-model planner rides on an engine
  that needs FlashAttention, which a T4 doesn't have. On pre-Ampere GPUs ACE-Step picks fp16 itself.
- Output is 48 kHz stereo WAV. Model and outputs are MIT; outputs may be used commercially.

Untested on a T4 when written: spike S2 is its first run (docs/01-plan.md §15)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = "https://github.com/ACE-Step/ACE-Step-1.5"
ACE_DIR = Path(os.environ.get("ACESTEP_DIR", "/tmp/ACE-Step-1.5"))
HELPER = Path(__file__).with_name("runner_acestep_job.py")


def _uv() -> str:
    found = shutil.which("uv")
    if found:
        return found
    subprocess.run(["pip", "install", "-q", "uv"], check=True)
    return shutil.which("uv") or "uv"


class AceStep:
    name = "acestep"
    precision = "fp16 on pre-Ampere GPUs (ACE-Step's own choice), DiT only"

    def __init__(self, gpu: int):
        self.gpu, self.uv = gpu, _uv()
        if not (ACE_DIR / ".venv").exists():
            if not ACE_DIR.exists():
                subprocess.run(["git", "clone", "--depth", "1", REPO, str(ACE_DIR)], check=True)
            subprocess.run([self.uv, "sync", "--python", "3.12"], cwd=ACE_DIR, check=True)

    def run(self, job: dict, root: Path, out: Path) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "job.json"
            spec.write_text(json.dumps(job, ensure_ascii=False))
            # Kaggle's notebook sets MPLBACKEND to its inline backend, which ACE-Step's own environment
            # can't import: run 2 failed on exactly that (FAILURES.md F8).
            env = {**os.environ, "CUDA_VISIBLE_DEVICES": str(self.gpu), "MPLBACKEND": "Agg"}
            done = subprocess.run([self.uv, "run", "--project", str(ACE_DIR), "python", str(HELPER),
                                   str(ACE_DIR), str(spec), str(out)],
                                  cwd=ACE_DIR, env=env, capture_output=True, text=True)
            if done.returncode != 0:
                raise RuntimeError(f"ACE-Step failed: {(done.stderr or done.stdout)[-400:]}")
            info = json.loads(done.stdout.strip().splitlines()[-1])
        return {"model": "ACE-Step-1.5 (acestep-v15-turbo, DiT only)", "steps": job["steps"], **info}
