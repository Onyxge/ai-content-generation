"""End-to-end on mock providers: the walkthrough demo as a test. One edit to the storyboard
must regenerate exactly that unit and its dependants, and nothing else."""
import json

import pytest

from pipeline.cli import main
from pipeline.media import missing_filters
from pipeline.engine.logs import read_jsonl

needs_ffmpeg = pytest.mark.skipif(bool(missing_filters()),
                                  reason="FFmpeg is missing or lacks filters the pipeline uses (FAILURES.md F2)")


def film(root, *args):
    return main([*args, "--mock", "--root", str(root)])


def changes(root, capsys):
    capsys.readouterr()
    assert film(root, "plan", "--json") == 0
    units = json.loads(capsys.readouterr().out)
    return {(u["stage"], u["unit"]): u["state"] for u in units if u["state"] != "hit"}


def edit(root, change):
    path = root / "storyboard.json"
    sb = json.loads(path.read_text(encoding="utf-8"))
    change(sb)
    path.write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")


@needs_ffmpeg
def test_build_then_one_edit_means_one_call(mock_root, capsys):
    mock = mock_root / "build" / "mock"
    runs = mock / "runs.jsonl"

    assert film(mock_root, "build") == 0
    first = read_jsonl(runs)
    # 2 reference options + 8 keyframes + 16 narration lines (2 languages) + 2 score candidates + 3 Wan clips
    assert len(first) == 31
    assert {r["status"] for r in first} == {"ok"}
    assert changes(mock_root, capsys) == {}

    finals = sorted(p.name for p in (mock / "outputs" / "final").glob("*.mp4"))
    assert finals == ["film_am_16x9.mp4", "film_am_9x16.mp4", "film_en_16x9.mp4", "film_en_9x16.mp4"]
    exports = [s for s in read_jsonl(mock / "stages.jsonl") if s["stage"] == "assemble"]
    assert len(exports) == 4
    for e in exports:
        assert 60 <= e["duration_s"] <= 90
        assert abs(e["integrated_lufs"] - (-14.0)) <= 1.5
        assert e["pictures"] == {"kenburns": 5, "i2v": 3}
    assert (mock / "outputs" / "subtitles" / "am_9x16.en.srt").read_text(encoding="utf-8").startswith("1\n")

    # Walkthrough demo 1: change one keyframe prompt.
    edit(mock_root, lambda sb: sb["shots"][3].update(image_prompt=sb["shots"][3]["image_prompt"] + ", late afternoon"))
    assert changes(mock_root, capsys) == {("keyframes", "s04"): "miss", ("shots", "s04.kb.v"): "upstream",
                                          ("shots", "s04.kb.h"): "upstream", ("shots", "s04.i2v"): "upstream"}
    assert film(mock_root, "render") == 0
    new = read_jsonl(runs)[len(first):]
    assert [(r["stage"], r["unit"]) for r in new] == [("keyframes", "s04"), ("shots", "s04.i2v")]

    # Walkthrough demo 2: change one English narration line. Amharic, music and pictures stay cached.
    edit(mock_root, lambda sb: sb["shots"][2]["narration"].update(en="One day, the radio went quiet."))
    assert changes(mock_root, capsys) == {("narration", "s03.en"): "miss"}
    before = len(read_jsonl(runs))
    assert film(mock_root, "render") == 0
    assert [(r["stage"], r["unit"]) for r in read_jsonl(runs)[before:]] == [("narration", "s03.en")]


@needs_ffmpeg
def test_radio_cut_needs_only_narration(mock_root):
    assert film(mock_root, "render", "--stage", "narration") == 0
    assert film(mock_root, "radio", "--lang", "am") == 0
    radio = mock_root / "build" / "mock" / "outputs" / "radio" / "radio_am.mp4"
    assert radio.exists() and radio.stat().st_size > 0


def test_real_mode_without_keys_fails_clearly(mock_root, capsys, monkeypatch):
    """A clean real workspace with no cache and no keys must say which key is missing, not crash."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert main(["render", "--stage", "narration", "--root", str(mock_root)]) == 1
    assert "add GEMINI_API_KEY to .env" in capsys.readouterr().out


def test_smoke_logs_one_call_per_provider_once_a_day(mock_root):
    assert film(mock_root, "smoke") in (0, 1)              # 1 only if this FFmpeg lacks filters
    runs = [r for r in read_jsonl(mock_root / "build" / "mock" / "runs.jsonl") if r["stage"] == "smoke"]
    assert sorted(r["unit"] for r in runs) == ["image", "speech", "speech_am", "text"]
    assert {r["actor"] for r in runs} == {"pipeline"} and all(r["latency_ms"] >= 0 for r in runs)
    film(mock_root, "smoke")
    assert len([r for r in read_jsonl(mock_root / "build" / "mock" / "runs.jsonl") if r["stage"] == "smoke"]) == 4


@needs_ffmpeg
def test_radio_cut_uses_the_pinned_score_once_rendered(mock_root):
    assert film(mock_root, "render", "--stage", "narration", "--lang", "en") == 0
    assert film(mock_root, "radio", "--lang", "en") == 0
    assert film(mock_root, "render", "--stage", "music") == 0
    assert film(mock_root, "radio", "--lang", "en") == 0
    radios = [s for s in read_jsonl(mock_root / "build" / "mock" / "stages.jsonl") if s.get("unit") == "radio.en"]
    assert [r["music"] for r in radios] == ["temp drone (no score rendered yet)", "m1.12"]   # m1.12 is the pinned take


def test_music_anchor_shifts_the_score_per_language(storyboard):
    """A take's quiet moment stays on its shot even when one language runs longer (E15)."""
    from pipeline.assemble import music_offset
    sb = {**storyboard, "music": {"cues": [{**storyboard["music"]["cues"][0], "anchor": {"shot": "s03", "at_s": 10.0}}]}}
    en = {"shots": [{"id": "s01", "start": 0.0}, {"id": "s02", "start": 6.0}, {"id": "s03", "start": 9.5}]}
    am = {"shots": [{"id": "s01", "start": 0.0}, {"id": "s02", "start": 7.0}, {"id": "s03", "start": 11.25}]}
    assert music_offset(sb, en) == -0.5 and music_offset(sb, am) == 1.25
    assert music_offset(storyboard, am) == 0.0                     # no anchor, no shift
