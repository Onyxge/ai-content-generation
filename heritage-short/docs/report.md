# Report: The Heritage Short, "The Last Pour"

*Draft prepared from the repository's logs on Thu 26 Nov 2026. Everything in [brackets] is for Y to write or confirm. The report should be Y's own account; every number here can be checked in the files cited.*

## What I set out to make, and for whom

A 60–90 second film, *The Last Pour*, inspired by a story my grandmother tells about a man who poured honey wine at an emperor's palace. In the film, the server, Tesfaye, is mocked by a guest, then called by his name and toasted by the emperor for one night. It's for Ethiopians on social media, at home and in the diaspora, watching on a phone, often with the sound off. I wanted them to leave with "the dignity of the people history doesn't name" (DESIGN.md, written before the first story call).

It exists in Amharic (76.7 s, the main version, because all three testers in the second test would send it to family) and English (73.8 s), each in 9:16 and 16:9. It has English subtitles, an original score ducked under the voice, and an end card saying it was made with AI, that it is inspired by a family story, and that some scenes are imagined.

I'm also the tutor for TRP2, so I built the studio as the reference for how trainees should orchestrate a movie-making agent. The architecture is the second thing I set out to make (ADR-017 to ADR-019):
- `make film` is a pure function of `storyboard.json` and a content-hash cache.
- Agents never render; they propose JSON Patches, which code checks for ownership, schema, lint and consent.
- A person approves at gates, and every decision is a line in `decisions.jsonl`.

## What my audience told me, and what changed

[Test 1, the radio cut, played to at least three people from the audience: who they were, what they said in their own words, and what changed in the storyboard because of it. Each change should cite the tester row in DESIGN.md and the proposal that made it.]

Test 2, the near-final cut, went to three people from the audience (DESIGN.md has their answers word for word):
- **What landed.** The ending stayed with all three, and all three would forward the film: to family, to friends interested in Ethiopian culture, and to younger relatives "as a conversation starter". All three would send the Amharic version.
- **What didn't.** None of their one-sentence summaries named the server, the emperor or the name: they took away "heritage" and "memory", not this story. One said, "I wanted a little more context near the beginning."
- **Two changes for the final cut.** The opening line now says where we are, "in his palace in Addis Ababa", in both languages (P-0009, two narration calls). Two testers found the subtitles small, so they're about 11% larger, the most that fits two lines on a phone frame (FAILURES.md F11).
- **What I left alone.** The slow middle and the abrupt cuts. Fixing them would shift picture against voice and needs another round of testing. [Y: what you'd do about them.]

One judgement from listening came before the formal tests. I chose score take m1.13 by ear, and a colleague agreed. My measurements had marked it the worst of the three because it drops out twice, but those silences fall under the grandmother line and the last words. That's E10 in EXPERIMENTS.md, and decision P-0001.

## The hardest problem, and how I solved it

[Choose one and tell it in your own words. Evidence for each:]

- **Getting Wan 2.2 to run on a free Kaggle T4** (FAILURES.md F7–F9; EXPERIMENTS.md, S1/E7):
  - The brief's documented route doesn't run there: the official repo needs FlashAttention 2, which Turing GPUs lack, and rejects 480p.
  - Each of the first three runs failed on a different limit:
    - run 1 ran out of GPU memory, because model offloading kept the 11 GB text encoder on the GPU while it loaded the VAE;
    - run 2 was killed by the OS for using too much host RAM;
    - run 3 crashed in our glue code (ACE-Step's key signature, the notebook's summary cell).
  - The fourth worked: about 29 GPU minutes per 5 s clip at 480×832, peak 5.75 GB.
  - Each failed run cost a few GPU minutes and left a logged traceback.
- **The emperor and the consent gate** (ETHICS.md, DESIGN.md):
  - The story involves a real head of state who died in 1975.
  - The brief zeroes the film if a real person appears without consent, and makes no exception for the dead or for public figures.
  - He became "the great emperor": unnamed, fictional, never voiced, never in close-up.
  - When the story agent put him in the cast as a real person, a code-level check at the shot step stopped him from entering a frame.

## A suggested practice that beat my instinct, and one that didn't

[Write your instinct first, honestly; the build log's practice ledger was meant to hold it before testing.]

- **Beat my instinct: [log every model call / one JSON contract].**
  - Every hard failure this week was diagnosed from a logged line, not from re-running:
    - the Addis AI response shape (F4);
    - the Gemini daily cap (F5);
    - the Kaggle runs (F7–F9).
  - The contract made eight decisions reversible and auditable.
  - The walkthrough's one-edit-one-call demo is a test (`tests/test_pipeline.py`).
- **Didn't, as given: [a reference sheet before keyframes].**
  - Conditioning every keyframe on the whole three-view character sheet made FLUX paint the same man two or three times in one frame (F10).
  - The practice only worked once keyframes were conditioned on the sheet's front view alone.
  - Naming the features explicitly mattered more than the sheet: with the same seeds, Tesfaye went from 1 in 4 options reading as Habesha to 4 in 4 (E22).
- [Or: **Let the agent write the stage scripts.** The agent wrote all of the code, and 82 tests pass. But the two visual bugs, the triplets and the heads cut off in 16:9, were invisible to the tests and caught only by looking at frames. Reviewing output, not just code, was the part that mattered.]

## Curiosity beyond the floor

- **Amharic with a model built for Amharic.** Addis Voices 2 voiced the ten Amharic lines in 44 s, with no daily cap, while Gemini's free TTS was capped at about 10 calls a day. The blind Gemini-versus-Addis comparison (E21) is not done.
- **The same meaning in two languages** (E15). Amharic runs 6% longer overall, and up to 29% longer per line. That moved the score's silence off the line it was chosen for, and led to a per-language music anchor (P-0006). It's a small idea that every bilingual edit needs.
- **An agent architecture with measured guardrails.**
  - Ownership by path, so agents can't touch consent or the voices.
  - Proposals addressed by id, so they survive edits.
  - Autonomy per decision type.
  - Kept hand edits and carried-over drafts (`--keep`).
  - A deterministic showrunner design.
  - All of it on the real film: eight proposals, one of them rejected.
- **Wan on people** (EXPERIMENTS.md). Of four clips, the two that asked for one gentle movement with a static camera worked. The two that asked for a camera move toward a face invented an object or a new face.

## What I'd build next

- **The critic, A3:** a vision call that ranks keyframe candidates against the golden reference, calibrated against my blind picks (E13), before it is allowed to pin anything on its own.
- **The MCP server, A5,** so trainees can drive the studio from their own coding agent with the guardrails intact.
- **A per-language music anchor for every cue,** and a composer agent that writes the cue's tempo and key, which ACE-Step needed and the story agent never gave it.
- **A second Wan pass for s08 and s10** with a static camera, one small action and no new objects.
