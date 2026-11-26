"""The story agent (A2): the chain stops at gate G1, keeps Y's hand edits, repairs answers
that break the code's rules, and only reaches storyboard.json when Y adopts it (G2)."""
import copy
import json
from pathlib import Path

import pytest

from pipeline.cli import main
from pipeline.engine.logs import read_jsonl
from pipeline.providers.mock import MockText

BRIEF = """# Story brief (public version)

## The story in three to five sentences

My father grew up in Dessie listening to the radio every evening. When it went silent he opened it
and taught himself how it worked. Soon the whole neighbourhood brought him their radios.

## Who is in it

My father, as a young man. In the film he is drawn, not a likeness; fictional for this example.

## The place

Dessie, on the hills, tin roofs, evening light.

## The moment it should land on

His saying: listen first, then fix.

## Words that must be said, or must not be

Dessie (DEH-see).
"""

INTENT = """# DESIGN

## Audience and intent

Who watches: my cousins abroad, on their phones, in the family group.
What they should feel at the end: proud, and close to a grandfather they barely knew.

## Why each shot exists
"""


def answers_from(example: dict) -> dict:
    beat_of = {s["id"]: f"b{min(4, 1 + i // 2)}" for i, s in enumerate(example["shots"])}
    return {
        "story_outline": {
            "title": "Listen First", "logline": example["meta"]["logline"],
            "treatment": "A boy in Dessie loves the radio. It falls silent. He opens it and learns. "
                         "The neighbourhood comes to him. He passes on his rule: listen first.",
            "cast": [{"id": "father", "role": "the narrator's father", "real_person": False,
                      "description": example["characters"][0]["description"]}],
            "look": example["style"]["block"], "music": example["music"]["cues"][0]["caption"],
            "feeling": "proud and close"},
        "story_beats": {"beats": [
            {"id": "b1", "summary": "Evenings by the radio in Dessie", "feeling": "warm", "picture": "the hills"},
            {"id": "b2", "summary": "The radio goes silent and he opens it", "feeling": "curious", "picture": "wires"},
            {"id": "b3", "summary": "He learns, night after night", "feeling": "patient", "picture": "a lamp"},
            {"id": "b4", "summary": "The neighbourhood comes; his rule", "feeling": "proud", "picture": "radios"}]},
        "story_shots": {"shots": [
            {"id": s["id"], "beat": beat_of[s["id"]], "reason": s["reason"], "size": s["size"],
             "duration_s": s["duration_s"], "characters": s.get("characters", []), "image_prompt": s["image_prompt"],
             "motion": {"mode": s["motion"]["mode"], "prompt": s["motion"]["prompt"],
                        **s["motion"].get("kenburns", {})}} for s in example["shots"]]},
        "story_narration": {"lines": [{"shot": s["id"], "en": s["narration"]["en"]} for s in example["shots"]]},
        "story_translation": {"lines": [{"shot": s["id"], "am": s["narration"]["am"]} for s in example["shots"]],
                              "notes": ["check the pronunciation of Dessie"]},
    }


class StoryRoot(type(Path())):
    """The test repo root, carrying the canned answers and a queue of one-off answers."""


@pytest.fixture
def story_root(mock_root, storyboard, monkeypatch):
    (mock_root / "docs" / "story").mkdir(parents=True)
    (mock_root / "docs" / "story" / "brief.md").write_text(BRIEF, encoding="utf-8")
    (mock_root / "DESIGN.md").write_text(INTENT, encoding="utf-8")
    answers = answers_from(storyboard)
    queue: dict[str, list] = {}

    def generate_json(self, *, prompt, schema, system="", images=(), temperature=0.4):
        title = schema["title"]
        if queue.get(title):
            return queue[title].pop(0), {"params": {}}
        return copy.deepcopy(answers[title]), {"params": {}}

    monkeypatch.setattr(MockText, "generate_json", generate_json)
    root = StoryRoot(mock_root)
    root.answers, root.queue = answers, queue
    return root


def film(root, *args):
    return main([*args, "--mock", "--root", str(root)])


def story_calls(root):
    return [(r["unit"], r["status"]) for r in read_jsonl(root / "build" / "mock" / "runs.jsonl") if r["stage"] == "story"]


def drafts(root):
    return root / "build" / "mock" / "docs" / "story" / "drafts"


def test_without_a_brief_nothing_is_called(mock_root, capsys):
    assert film(mock_root, "storyboard") == 0
    assert "write docs/story/brief.md" in capsys.readouterr().out
    assert not (mock_root / "build" / "mock" / "runs.jsonl").exists()


def test_template_placeholders_dont_count_as_a_brief(story_root, capsys):
    (story_root / "DESIGN.md").write_text("## Audience and intent\n\n*To be written by Y before any generation.*\n")
    assert film(story_root, "storyboard") == 0
    assert story_calls(story_root) == []


def test_chain_stops_at_g1_then_finishes_after_approval(story_root, capsys):
    assert film(story_root, "storyboard") == 0
    out = capsys.readouterr().out
    assert "father" in out and "not a real person" in out and "--approve-beats" in out
    assert story_calls(story_root) == [("outline", "ok"), ("beats", "ok")]
    runs = read_jsonl(story_root / "build" / "mock" / "runs.jsonl")
    assert {r["actor"] for r in runs} == {"story"}

    assert film(story_root, "storyboard", "--approve-beats") == 0
    assert story_calls(story_root)[2:] == [("shots", "ok"), ("narration", "ok"), ("translation", "ok")]
    draft = json.loads((drafts(story_root) / "storyboard.draft.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in draft["shots"]] == [f"s0{i}" for i in range(1, 9)]
    assert draft["voices"]["am"]["model"] == "gemini-3.8-flash-tts"          # Y's config, not the model's choice
    assert "It validates" in capsys.readouterr().out

    assert film(story_root, "storyboard") == 0                               # everything cached: no new calls
    assert len(story_calls(story_root)) == 5


def test_hand_edit_is_kept_reopens_g1_and_reruns_only_later_steps(story_root, capsys):
    film(story_root, "storyboard")
    film(story_root, "storyboard", "--approve-beats")
    beats_path = drafts(story_root) / "02-beats.json"
    beats = json.loads(beats_path.read_text(encoding="utf-8"))
    beats["beats"][1]["summary"] = "The radio goes silent the night before a match"
    beats_path.write_text(json.dumps(beats, indent=2), encoding="utf-8")

    assert film(story_root, "storyboard") == 0
    assert "Kept your edit to the beats draft" in capsys.readouterr().out
    assert json.loads(beats_path.read_text())["beats"][1]["summary"].endswith("before a match")
    assert len(story_calls(story_root)) == 5                                 # G1 is closed again: nothing ran
    history = read_jsonl(story_root / "build" / "mock" / "decisions.jsonl")
    assert [h["event"] for h in history] == ["gate", "hand_edit"]

    # The new beats reach the shot step; its changed answer reaches narration. The narration
    # comes back word for word the same, so the translation stays cached.
    reshot = copy.deepcopy(story_root.answers["story_shots"])
    reshot["shots"][2]["reason"] = "The silence before the match is the turn in the story."
    story_root.queue["story_shots"] = [reshot]
    assert film(story_root, "storyboard", "--approve-beats") == 0
    assert [u for u, _ in story_calls(story_root)[5:]] == ["shots", "narration"]
    assert list((drafts(story_root) / "edits").glob("02-beats.*.json"))


def test_a_step_that_answers_the_same_stops_the_cascade(story_root):
    """Content-hash caching cuts off early: if a rerun step writes identical bytes, the steps
    after it stay cached, because their key depends on those bytes, not on the rerun."""
    film(story_root, "storyboard")
    film(story_root, "storyboard", "--approve-beats")
    beats_path = drafts(story_root) / "02-beats.json"
    beats = json.loads(beats_path.read_text(encoding="utf-8"))
    beats["beats"][0]["feeling"] = "warm, slow"
    beats_path.write_text(json.dumps(beats, indent=2), encoding="utf-8")
    film(story_root, "storyboard")
    film(story_root, "storyboard", "--approve-beats")
    assert [u for u, _ in story_calls(story_root)[5:]] == ["shots"]


def test_rule_breaking_answer_is_repaired_and_each_attempt_logged(story_root):
    film(story_root, "storyboard")
    too_long = copy.deepcopy(story_root.answers["story_narration"])
    too_long["lines"][2]["en"] = " ".join(["word"] * 40)
    story_root.queue["story_narration"] = [too_long]
    assert film(story_root, "storyboard", "--approve-beats") == 0
    calls = story_calls(story_root)
    assert calls[2:] == [("shots", "ok"), ("narration", "repair"), ("narration", "ok"), ("translation", "ok")]
    repair = [r for r in read_jsonl(story_root / "build" / "mock" / "runs.jsonl") if r["status"] == "repair"][0]
    assert "over its budget" in repair["error"]


def test_adopt_is_gate_g2_and_never_silently_replaces(story_root, capsys):
    film(story_root, "storyboard")
    film(story_root, "storyboard", "--approve-beats")
    assert film(story_root, "storyboard", "--adopt") == 2                     # storyboard.json already exists
    assert "--replace" in capsys.readouterr().err
    assert film(story_root, "storyboard", "--adopt", "--replace") == 0
    sb = json.loads((story_root / "storyboard.json").read_text(encoding="utf-8"))
    assert sb["meta"]["title"] == "Listen First" and sb["references"][0]["seeds"] == [101, 102, 103, 104]
    adopted = read_jsonl(story_root / "build" / "mock" / "decisions.jsonl")[-1]
    assert (adopted["event"], adopted["gate"], adopted["by"]) == ("adopted", "G2", "Y")
    assert (story_root / "build" / "mock" / "docs" / "storyboard-history" / "v1.json").exists()
    assert film(story_root, "validate") == 0


def test_real_person_without_consent_never_reaches_a_shot(story_root, capsys):
    """The main character marked real with no consent: every shot answer that shows him is sent
    back; after four attempts the step fails, so there's no draft to adopt."""
    story_root.answers["story_outline"]["cast"][0]["real_person"] = True
    film(story_root, "storyboard")
    assert film(story_root, "storyboard", "--approve-beats") == 1
    assert [s for u, s in story_calls(story_root) if u == "shots"] == ["repair"] * 4
    assert film(story_root, "storyboard", "--adopt", "--replace") == 2
    assert "no draft yet" in capsys.readouterr().err


def test_real_person_spoken_about_but_never_shown_needs_no_consent(story_root, capsys):
    """The emperor case: a real person in the story's cast with no consent. He may be spoken
    about; a shot that puts him in frame is sent back; the draft gives him no character."""
    story_root.answers["story_outline"]["cast"].append(
        {"id": "emperor", "role": "the emperor", "description": "never shown", "real_person": True})
    film(story_root, "storyboard")
    assert "may be spoken about, never shown" in capsys.readouterr().out
    in_frame = copy.deepcopy(story_root.answers["story_shots"])
    in_frame["shots"][6]["characters"] = ["father", "emperor"]
    story_root.queue["story_shots"] = [in_frame]
    assert film(story_root, "storyboard", "--approve-beats") == 0
    repair = [r for r in read_jsonl(story_root / "build" / "mock" / "runs.jsonl") if r["status"] == "repair"][0]
    assert "real person with no recorded consent" in repair["error"]
    draft = json.loads((drafts(story_root) / "storyboard.draft.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in draft["characters"]] == ["father"]
    assert film(story_root, "storyboard", "--adopt", "--replace") == 0


def test_keep_carries_approved_drafts_across_a_brief_change(story_root, capsys):
    """Y changes the brief after approving the beats and keeps the approved drafts: nothing is
    regenerated, the carry-over is logged with both keys, and the later steps run on them."""
    film(story_root, "storyboard")
    brief = story_root / "docs" / "story" / "brief.md"
    brief.write_text(brief.read_text().replace("My father", "My grandfather"), encoding="utf-8")
    capsys.readouterr()
    assert film(story_root, "storyboard", "--keep", "outline,beats", "--approve-beats") == 0
    assert "Kept the outline draft" in capsys.readouterr().out
    assert [u for u, _ in story_calls(story_root)] == ["outline", "beats", "shots", "narration", "translation"]
    kept = [d for d in read_jsonl(story_root / "build" / "mock" / "decisions.jsonl") if d["event"] == "kept_draft"]
    assert [k["step"] for k in kept] == ["outline", "beats"] and all(k["old_key"] != k["new_key"] for k in kept)
