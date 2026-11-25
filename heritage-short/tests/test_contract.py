from pipeline.contract import consent_ids, lint, schema_errors

CONSENT_ROW = "| C1 | Father (main character) | Father, in person | likeness and the script's words | 2026-11-25 | voice note in private/ |"


def test_example_is_valid(storyboard):
    assert schema_errors(storyboard) == []
    report = lint(storyboard)
    assert report.ok, report.errors


def test_every_shot_needs_a_reason(storyboard):
    del storyboard["shots"][0]["reason"]
    assert any("reason" in e for e in schema_errors(storyboard))


def test_the_brief_wants_eight_to_twelve_shots(storyboard):
    storyboard["shots"] = storyboard["shots"][:7]
    storyboard["music"]["cues"][0]["to"] = "s07"
    assert any("8–12 shots" in e for e in lint(storyboard).errors)


def test_consent_gate_blocks_a_real_person_without_a_record(storyboard):
    storyboard["characters"][0].update(real_person=True, consent_id="C1")
    assert any("C1" in e for e in lint(storyboard, "# Ethics\n").errors)
    placeholder = "| C1 | … | … | … | … | … |"
    assert any("C1" in e for e in lint(storyboard, placeholder).errors)
    assert lint(storyboard, CONSENT_ROW).ok


def test_a_real_person_needs_a_consent_id(storyboard):
    storyboard["characters"][0]["real_person"] = True
    assert any("consent_id" in e for e in lint(storyboard, CONSENT_ROW).errors)


def test_consent_ids_ignores_placeholder_rows():
    assert consent_ids(CONSENT_ROW + "\n| C2 | … | … | … | … | … |") == {"C1"}


def test_primary_must_be_one_of_the_languages(storyboard):
    storyboard["meta"]["languages"] = ["en"]
    storyboard["meta"]["primary"] = "am"
    assert any("meta.primary" in e for e in lint(storyboard).errors)


def test_narration_exists_in_every_language_or_none(storyboard):
    storyboard["shots"][0]["narration"]["am"] = ""
    assert any("every language or in none" in e for e in lint(storyboard).errors)


def test_runtime_must_fit_the_brief(storyboard):
    for shot in storyboard["shots"]:
        shot["duration_s"] = 12
    assert any("runtime" in e for e in lint(storyboard).errors)


def test_text_in_images_is_flagged(storyboard):
    storyboard["shots"][5]["image_prompt"] += ", a hand-painted sign reading RADIO REPAIR"
    assert any("text" in w for w in lint(storyboard).warnings)


def test_at_most_four_reference_images(storyboard):
    refs = storyboard["references"]
    for i in range(4):
        refs.append({"id": f"ref_extra{i}", "kind": "place", "prompt": "a place", "seeds": [1], "selected": 1})
    storyboard["shots"][1]["references"] = [f"ref_extra{i}" for i in range(4)]
    assert any("at most 4" in e for e in lint(storyboard).errors)


def test_subtitle_cards_respect_line_length_and_two_lines():
    from pipeline.subtitles import chunks
    text = "He grew up in Dessie, listening to the radio every evening. Then one day it stopped."
    for width in (28, 42):
        cards = chunks(text, max_chars=width, max_lines=2)
        assert all(len(line) <= width for card in cards for line in card.split("\n"))
        assert all(card.count("\n") <= 1 for card in cards)
        assert " ".join(card.replace("\n", " ") for card in cards) == text
        assert all(len(card.replace("\n", " ")) >= 8 for card in cards)   # no orphan words
