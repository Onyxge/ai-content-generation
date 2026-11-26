"""`film kaggle push | status | pull`: the GPU round trip without opening a browser (U11, ADR-006).

- push: uploads the chosen bundles as a **private** dataset (`<you>/heritage-short-bundles`,
  a new version each time) and runs gpu/kaggle_runner.ipynb as a **private** notebook on
  GPU T4 x2 with internet on, with that dataset attached.
- status: the notebook's run state (queued, running, complete, error).
- pull: downloads the run's output and hands it to `film ingest`.

Uses the Kaggle CLI 2.x with KAGGLE_API_TOKEN from .env (FAILURES.md F6). Nothing is public."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NOTEBOOK = REPO / "gpu" / "kaggle_runner.ipynb"
DATASET_SLUG = "heritage-short-bundles"
KERNEL_SLUG = "heritage-short-gpu-runner"


class KaggleError(RuntimeError):
    pass


def kaggle(*args: str, check: bool = True) -> str:
    done = subprocess.run([sys.executable, "-m", "kaggle", *args], capture_output=True, text=True)
    out = (done.stdout + done.stderr).strip()
    if check and done.returncode != 0:
        raise KaggleError(f"kaggle {' '.join(args[:2])} failed: {out[-500:]}")
    return out


def owner() -> str:
    name = os.environ.get("KAGGLE_USERNAME")
    if not name:
        raise KaggleError("add KAGGLE_USERNAME to .env (your Kaggle handle) alongside KAGGLE_API_TOKEN")
    return name


def ids() -> tuple[str, str]:
    return f"{owner()}/{DATASET_SLUG}", f"{owner()}/{KERNEL_SLUG}"


def work_dir(root: Path) -> Path:
    return root / "build" / "kaggle"


def push(root: Path, bundles: list[Path], limit: int, timeout_s: int = 0, say=print) -> dict:
    if not os.environ.get("KAGGLE_API_TOKEN"):
        raise KaggleError("add KAGGLE_API_TOKEN to .env (kaggle.com/settings/api → Generate New Token)")
    if not bundles:
        raise KaggleError("no bundles to push; make them with `film bundle shots` / `film bundle music`")
    dataset_id, kernel_id = ids()
    base = work_dir(root)

    # 1. The bundles as a private dataset, a new version on every push.
    data = base / "dataset"
    shutil.rmtree(data, ignore_errors=True)
    data.mkdir(parents=True)
    for b in bundles:
        shutil.copy(b, data / b.name)
    (data / "dataset-metadata.json").write_text(json.dumps(
        {"title": DATASET_SLUG, "id": dataset_id, "licenses": [{"name": "CC0-1.0"}]}, indent=2))
    exists = "ready" in kaggle("datasets", "status", dataset_id, check=False).lower()
    if exists:
        say(f"New version of private dataset {dataset_id} with {len(bundles)} bundle(s)…")
        kaggle("datasets", "version", "-p", str(data), "-m", f"bundles: {', '.join(b.name for b in bundles)}", "-q")
    else:
        say(f"Creating private dataset {dataset_id} with {len(bundles)} bundle(s)…")
        kaggle("datasets", "create", "-p", str(data), "-q")
    for _ in range(60):                                  # wait until Kaggle has processed the upload
        if "ready" in kaggle("datasets", "status", dataset_id, check=False).lower():
            break
        time.sleep(5)
    else:
        raise KaggleError(f"dataset {dataset_id} wasn't ready after 5 minutes; try `film kaggle push` again")

    # 2. The runner notebook as a private kernel on GPU T4 x2, with the dataset attached.
    kern = base / "kernel"
    shutil.rmtree(kern, ignore_errors=True)
    kern.mkdir(parents=True)
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    for cell in nb["cells"]:
        if cell["cell_type"] == "code" and any(line.startswith("LIMIT =") for line in cell["source"]):
            cell["source"] = [f"LIMIT = {limit}          # set by `film kaggle push --limit`\n" if line.startswith("LIMIT =")
                              else line for line in cell["source"]]
    (kern / NOTEBOOK.name).write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    (kern / "kernel-metadata.json").write_text(json.dumps({
        "id": kernel_id, "title": KERNEL_SLUG, "code_file": NOTEBOOK.name, "language": "python",
        "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "enable_tpu": False,
        "enable_internet": True, "machine_shape": "NvidiaTeslaT4", "dataset_sources": [dataset_id],
        "competition_sources": [], "kernel_sources": [], "model_sources": []}, indent=2))
    args = ["kernels", "push", "-p", str(kern), "--accelerator", "NvidiaTeslaT4"]
    if timeout_s:
        args += ["-t", str(timeout_s)]
    say(f"Running private notebook {kernel_id} on GPU T4 x2 (LIMIT = {limit})…")
    out = kaggle(*args)
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "dataset": dataset_id, "kernel": kernel_id,
              "bundles": [b.name for b in bundles], "limit": limit, "push": out[-300:]}
    with open(base / "launches.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def status() -> str:
    return kaggle("kernels", "status", ids()[1])


def pull(root: Path) -> Path:
    dest = work_dir(root) / "out"
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    kaggle("kernels", "output", ids()[1], "-p", str(dest), "-o", "-q")
    zipped = list(dest.rglob("heritage-gpu-out.zip"))
    if zipped:
        return zipped[0]
    if list(dest.rglob("results*.jsonl")):
        return dest
    logs = sorted(dest.rglob("*.log")) + sorted(dest.rglob("*.ipynb"))
    raise KaggleError(f"the run produced no results; look at {', '.join(str(p) for p in logs) or dest}")
