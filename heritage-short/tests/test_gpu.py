"""The GPU round trip on mock providers: bundle the uncached Wan and ACE-Step jobs, run the real
runner script with its mock backend, ingest the results. A result for a shot edited after
bundling is stale and stays out of the cache; every result, failed or not, is logged."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from pipeline.cli import main
from pipeline.engine.logs import read_jsonl
from pipeline.media import missing_filters

RUNNER = Path(__file__).parent.parent / "gpu" / "runner.py"
needs_ffmpeg = pytest.mark.skipif(bool(missing_filters()), reason="FFmpeg missing or lacks filters")


def film(root, *args):
    return main([*args, "--mock", "--root", str(root)])


def run_runner(bundle: Path, out: Path):
    subprocess.run([sys.executable, str(RUNNER), "--bundle", str(bundle), "--out", str(out), "--backend", "mock"],
                   check=True, capture_output=True, text=True)


def gpu_lines(root):
    return [r for r in read_jsonl(root / "build" / "mock" / "runs.jsonl") if str(r.get("provider", "")).startswith("gpu-runner")]


def finished(path):
    """The runner writes a "started" line before each job, then its result; these are the results."""
    return [r for r in read_jsonl(path) if r["status"] != "started"]


def bundles(root):
    return sorted((root / "build" / "bundles").glob("mock-*.zip"), key=lambda p: p.stat().st_mtime_ns)


@needs_ffmpeg
def test_round_trip_and_stale_results(mock_root, monkeypatch, tmp_path):
    # Real providers stand in for nothing here: render references and keyframes on mocks, but leave
    # the GPU units uncached by making the mock video and music providers "pending", as in real mode.
    from pipeline import providers
    real_load = providers.load

    def load(cfg, mock):
        p = real_load(cfg, mock)
        p["video"] = providers.Unavailable("gpu-runner", cfg["video"]["i2v_model"], "pending", pending=True)
        p["music"] = providers.Unavailable("gpu-runner", cfg["music"]["model"], "pending", pending=True)
        return p

    monkeypatch.setattr(providers, "load", load)
    assert film(mock_root, "render", "--stage", "references", "--stage", "keyframes") == 0

    assert film(mock_root, "bundle", "shots") == 0
    shots_zip = bundles(mock_root)[-1]
    with zipfile.ZipFile(shots_zip) as z:
        names = set(z.namelist())
        manifest = json.loads(z.read("manifest.json"))
    assert {"manifest.json", "runner.py"} <= names
    assert [j["id"] for j in manifest["jobs"]] == ["s02.i2v", "s04.i2v", "s07.i2v"]
    assert all(f"inputs/{j['id']}.png" in names for j in manifest["jobs"])

    out = tmp_path / "kaggle-out"
    run_runner(shots_zip, out)
    results = finished(out / "results.jsonl")
    assert [r["status"] for r in results] == ["ok"] * 3

    # Y edits shot 4's motion prompt after bundling: its clip is now stale.
    sb_path = mock_root / "storyboard.json"
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    sb["shots"][3]["motion"]["prompt"] = "the camera holds; dust drifts in the light"
    sb_path.write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")

    assert film(mock_root, "ingest", str(out)) == 0
    lines = gpu_lines(mock_root)
    assert sorted(l["unit"] for l in lines) == ["s02.i2v", "s07.i2v"]          # the stale one isn't logged as ingested
    assert all(l["status"] == "ok" and l["gpu_s"] == 0.0 for l in lines)
    assert (mock_root / "build" / "mock" / "outputs" / "shots" / "s02.i2v.mp4").exists()
    assert not (mock_root / "build" / "mock" / "outputs" / "shots" / "s04.i2v.mp4").exists()

    # Ingesting twice changes nothing; the next bundle holds only the stale shot.
    assert film(mock_root, "ingest", str(out)) == 0
    assert len(gpu_lines(mock_root)) == 2
    assert film(mock_root, "bundle", "shots") == 0
    with zipfile.ZipFile(bundles(mock_root)[-1]) as z:
        assert [j["id"] for j in json.loads(z.read("manifest.json"))["jobs"]] == ["s04.i2v"]

    # Music needs no pictures; a failed job is logged as a failure and not cached.
    assert film(mock_root, "bundle", "music") == 0
    music_zip = bundles(mock_root)[-1]
    music_out = tmp_path / "music-out"
    run_runner(music_zip, music_out)
    lines = read_jsonl(music_out / "results.jsonl")
    first_result = next(l for l in lines if l["status"] == "ok")
    first_result.update(status="error", error="CUDA out of memory")
    (music_out / "results.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines))
    assert film(mock_root, "ingest", str(music_out)) == 0
    music = [l for l in gpu_lines(mock_root) if l["stage"] == "music"]
    assert [l["status"] for l in music] == ["error", "ok"]
    assert "out of memory" in music[0]["error"]


def test_runner_resumes_and_shards(tmp_path):
    bundle = tmp_path / "b"
    (bundle / "inputs").mkdir(parents=True)
    jobs = [{"id": f"m1.{s}", "key": f"k{s}", "out": f"m1.{s}.wav", "kind": "music", "model": "ACE-Step-1.5",
             "caption": "strings", "seed": s, "length_s": 1, "bpm": 70, "key_signature": "D minor",
             "instrumental": True} for s in (11, 12, 13)]
    (bundle / "manifest.json").write_text(json.dumps({"bundle": "t", "stage": "music", "jobs": jobs}))
    out = tmp_path / "o"
    subprocess.run([sys.executable, str(RUNNER), "--bundle", str(bundle), "--out", str(out), "--backend", "mock",
                    "--gpu", "0", "--shards", "2"], check=True, capture_output=True)
    assert [r["id"] for r in finished(out / "results-0.jsonl")] == ["m1.11", "m1.13"]
    subprocess.run([sys.executable, str(RUNNER), "--bundle", str(bundle), "--out", str(out), "--backend", "mock"],
                   check=True, capture_output=True)
    assert [r["id"] for r in finished(out / "results.jsonl")] == ["m1.12"]          # the rest were already done


def test_a_job_killed_mid_run_is_logged_as_a_failure(mock_root, tmp_path):
    """Kaggle's OOM killer leaves no traceback and no result, only the "started" line (F8)."""
    out = tmp_path / "killed"
    (out / "outputs").mkdir(parents=True)
    (out / "results.jsonl").write_text(json.dumps(
        {"id": "m1.11", "key": "k", "out": "m1.11.wav", "status": "started", "env": "kaggle"}) + "\n")
    assert film(mock_root, "ingest", str(out)) == 0
    line = gpu_lines(mock_root)[-1]
    assert line["unit"] == "m1.11" and line["status"] == "error" and "died during this job" in line["error"]
