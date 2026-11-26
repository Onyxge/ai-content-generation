"""The decision plane's guardrails (ADR-018, ADR-019): agents edit the storyboard only through
proposals, only where they own it, and only into a valid storyboard; every step is logged."""
import json

import pytest

from pipeline.agents import patches
from pipeline.agents.decisions import DecisionError, Decisions
from pipeline.cli import main
from pipeline.engine.logs import read_jsonl


@pytest.fixture
def studio(mock_root):
    return Decisions(mock_root, mock_root / "storyboard.json", mock=True)


def sb_of(studio):
    return json.loads(studio.storyboard.read_text(encoding="utf-8"))


def shot(sb, sid):
    return next(s for s in sb["shots"] if s["id"] == sid)


# ---------- patches over the id-keyed view ----------

def test_keyed_view_round_trips(storyboard):
    assert patches.from_keyed(patches.to_keyed(storyboard)) == storyboard


def test_patch_addresses_items_by_id(storyboard):
    after = patches.apply(storyboard, [{"op": "replace", "path": "/shots/s04/image_prompt", "value": "x"}])
    assert shot(after, "s04")["image_prompt"] == "x"
    assert storyboard["shots"][3]["image_prompt"] != "x"           # the input is untouched


def test_add_reorder_and_remove_items(storyboard):
    new = {**shot(storyboard, "s08"), "id": "s09", "reason": "a coda"}
    ids = [s["id"] for s in storyboard["shots"]]
    after = patches.apply(storyboard, [
        {"op": "add", "path": "/shots/s09", "value": new},
        {"op": "replace", "path": "/shots/@order", "value": ["s09", *ids]},
        {"op": "remove", "path": "/shots/s02"},
    ])
    assert [s["id"] for s in after["shots"]] == ["s09", *[i for i in ids if i != "s02"]]


@pytest.mark.parametrize("op, message", [
    ({"op": "replace", "path": "/shots/s99/beat", "value": "x"}, "no such location"),
    ({"op": "test", "path": "/meta/title", "value": "wrong"}, "test failed"),
    ({"op": "replace", "path": "/shots/@order", "value": ["s01"]}, "reordering"),
    ({"op": "move", "path": "/meta/title", "from": "/meta/logline"}, "supported operations"),
])
def test_bad_patches_are_explained(storyboard, op, message):
    with pytest.raises(patches.PatchError, match=message):
        patches.apply(storyboard, [op])


# ---------- ownership ----------

def test_owner_proposal_waits_for_y_with_a_price(mock_root, studio):
    assert main(["render", "--stage", "references", "--stage", "keyframes", "--mock", "--root", str(mock_root)]) == 0
    p = studio.propose("cinematographer", [{"op": "replace", "path": "/shots/s04/image_prompt",
                                            "value": "the workbench at dusk, a single bulb"}],
                       rationale="the dusk light carries the turn in the story")
    assert p["status"] == "pending" and p["autonomy"] == "propose" and p["kinds"] == ["cinematographer"]
    assert p["price"]["model_calls"]["image"] == 1               # one keyframe, nothing else
    assert shot(sb_of(studio), "s04")["image_prompt"] != "the workbench at dusk, a single bulb"
    assert [w["id"] for w in studio.waiting()] == [p["id"]]


def test_agent_cannot_edit_another_agents_field(studio):
    p = studio.propose("story", [{"op": "replace", "path": "/shots/s04/image_prompt", "value": "x"}])
    assert p["status"] == "refused"
    assert p["errors"] == ["/shots/s04/image_prompt: not story's to change (owned by cinematographer)"]
    assert read_jsonl(studio.log_path)[-1]["event"] == "refused"
    assert (studio.proposals_dir / f"{p['id']}.json").exists()   # refusals are kept as evidence


@pytest.mark.parametrize("path, value", [
    ("/characters/father/real_person", True),
    ("/voices/en/voice", "another-voice"),
    ("/meta/primary", "am"),
])
def test_only_y_changes_consent_voices_and_languages(studio, path, value):
    p = studio.propose("lookdev", [{"op": "replace", "path": path, "value": value}])
    assert p["status"] == "refused" and "only Y may change this" in p["errors"][0]


def test_agents_cannot_add_people(studio):
    person = {"id": "aunt", "real_person": False, "description": "an older woman"}
    p = studio.propose("lookdev", [{"op": "add", "path": "/characters/aunt", "value": person}])
    assert p["status"] == "refused"
    assert any("may not add, remove or reorder items in /characters" in e for e in p["errors"])


def test_a_proposal_must_leave_a_valid_storyboard(studio):
    p = studio.propose("story", [{"op": "remove", "path": f"/shots/s0{i}"} for i in (1, 2, 3)])
    assert p["status"] == "refused"
    assert any("8–12 shots" in e for e in p["errors"])


# ---------- approve, autonomy, revert ----------

def test_approve_lands_the_change_and_logs_hashes(mock_root, studio, capsys):
    p = studio.propose("critic", [{"op": "replace", "path": "/shots/s04/keyframe_seed", "value": 1043}],
                       evidence={"candidates": [1041, 1042, 1043], "critic": {"winner": 1043}})
    assert p["kinds"] == ["keyframe_pin"] and p["status"] == "pending"
    studio.approve(p["id"], why="closest to the golden reference")
    assert shot(sb_of(studio), "s04")["keyframe_seed"] == 1043
    events = [(d["event"], d["proposal"]) for d in read_jsonl(studio.log_path)]
    assert events == [("proposed", p["id"]), ("approved", p["id"])]
    approved = read_jsonl(studio.log_path)[-1]
    assert approved["by"] == "Y" and approved["storyboard_sha"]["before"] != approved["storyboard_sha"]["after"]
    assert studio.waiting() == []
    with pytest.raises(DecisionError, match="not pending"):
        studio.approve(p["id"])


def test_veto_applies_now_and_can_be_reverted(studio):
    before = shot(sb_of(studio), "s05")["motion"]["prompt"]
    p = studio.propose("cinematographer", [{"op": "replace", "path": "/shots/s05/motion/prompt",
                                            "value": "the camera holds still; steam rises"}])
    assert p["autonomy"] == "veto" and p["status"] == "applied"
    assert shot(sb_of(studio), "s05")["motion"]["prompt"] == "the camera holds still; steam rises"
    assert [w["id"] for w in studio.waiting()] == [p["id"]]       # applied, but Y still has to look
    studio.revert(p["id"], why="the steam reads as smoke")
    assert shot(sb_of(studio), "s05")["motion"]["prompt"] == before
    assert [d["event"] for d in read_jsonl(studio.log_path)] == ["proposed", "applied", "reverted"]


def test_strictest_kind_wins(studio):
    p = studio.propose("cinematographer", [
        {"op": "replace", "path": "/shots/s05/motion/prompt", "value": "slow pan left"},     # veto
        {"op": "replace", "path": "/shots/s05/image_prompt", "value": "the same room, wider"},  # propose
    ])
    assert p["autonomy"] == "propose" and p["status"] == "pending"


def test_stale_proposal_is_refused_at_approval(studio):
    a = studio.propose("cinematographer", [{"op": "replace", "path": "/shots/s02/image_prompt", "value": "a"}])
    b = studio.propose("cinematographer", [{"op": "replace", "path": "/shots/s02/image_prompt", "value": "b"}])
    studio.approve(a["id"])
    with pytest.raises(DecisionError, match="stale"):
        studio.approve(b["id"])


def test_unrelated_edits_do_not_make_a_proposal_stale(studio):
    a = studio.propose("cinematographer", [{"op": "replace", "path": "/shots/s02/image_prompt", "value": "a"}])
    b = studio.propose("story", [{"op": "replace", "path": "/shots/s02/beat", "value": "the first repair"}])
    studio.approve(b["id"])
    studio.approve(a["id"])
    s02 = shot(sb_of(studio), "s02")
    assert (s02["image_prompt"], s02["beat"]) == ("a", "the first repair")


def test_story_adds_a_shot_and_revert_removes_it(studio):
    sb = sb_of(studio)
    new = {**shot(sb, "s08"), "id": "s09", "reason": "a coda on the quiet radio", "duration_s": 3}
    sb_shots = [s["id"] for s in sb["shots"]]
    sb["shots"][0]["duration_s"] -= 3                            # keep the runtime inside 60–90 s
    p = studio.propose("story", [
        {"op": "replace", "path": "/shots/s01/duration_s", "value": sb["shots"][0]["duration_s"]},
        {"op": "add", "path": "/shots/s09", "value": new},
    ])
    assert p["status"] == "pending", p.get("errors")
    studio.approve(p["id"])
    assert [s["id"] for s in sb_of(studio)["shots"]] == [*sb_shots, "s09"]
    studio.revert(p["id"])
    assert [s["id"] for s in sb_of(studio)["shots"]] == sb_shots


def test_y_edits_apply_directly_and_are_logged(studio):
    p = studio.propose("Y", [{"op": "replace", "path": "/meta/primary", "value": "am"}],
                       rationale="testers preferred the Amharic version")
    assert p["status"] == "applied" and sb_of(studio)["meta"]["primary"] == "am"
    assert read_jsonl(studio.log_path)[-1]["by"] == "Y"


# ---------- CLI ----------

def test_cli_round_trip(mock_root, capsys):
    proposal = mock_root / "p.json"
    proposal.write_text(json.dumps({"actor": "critic", "rationale": "identity holds best",
                                    "patch": [{"op": "replace", "path": "/shots/s03/keyframe_seed", "value": 7}]}))
    assert main(["propose", str(proposal), "--mock", "--root", str(mock_root)]) == 0
    assert "P-0001 pending" in capsys.readouterr().out
    assert main(["proposals", "--mock", "--root", str(mock_root)]) == 0
    assert "/shots/s03/keyframe_seed" in capsys.readouterr().out
    assert main(["approve", "P-0001", "--why", "agreed", "--mock", "--root", str(mock_root)]) == 0
    assert shot(json.loads((mock_root / "storyboard.json").read_text()), "s03")["keyframe_seed"] == 7

    proposal.write_text(json.dumps({"actor": "story", "patch": [
        {"op": "add", "path": "/characters/father/consent_id", "value": "C9"}]}))
    assert main(["propose", str(proposal), "--mock", "--root", str(mock_root)]) == 2
    assert "only Y may change this" in capsys.readouterr().out
