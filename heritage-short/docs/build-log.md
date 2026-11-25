# Build log

A dated record of what we did, what we learned and what we decided, written as we go. It feeds the report, ARCHITECTURE.md and the interview. Newest entries at the bottom; times in EAT.

## Practice ledger

The report asks for one suggested practice that beat our instinct and one that didn't, each with evidence. To keep that honest, Y writes down an instinct for each practice before we test anything.

| Suggested practice | Y's instinct, before testing | How we test it | Evidence | Verdict |
|---|---|---|---|---|
| One JSON contract between all stages | | Count changes that needed a code edit vs only a contract edit | | |
| Reference sheet before keyframes | | E4: references on vs off, same seeds | | |
| Log every model call | | Did the logs answer questions we had later (costs, failures, the interview)? | | |
| Let the agent write stage scripts while we design and review | | Time per unit; how many agent-written bugs reached a real run | | |
| Radio cut before any pictures | | How much of the storyboard changed after test 1 | | |
| Draft at low resolution | | E7: 480p vs 720p GPU cost and quality | | |
| One change per experiment, seed fixed | | Could we explain every result afterwards? | | |
| Narration generated one line per shot | | Retakes and timing edits per line vs regenerating the whole script | | |

## 2026-11-25 (Wed) — Entry 0: requirements and plan

Who: Y (direction) and Claude in claude.ai (analysis and planning). No code yet and no model calls yet.

What we did. Read both versions of the brief side by side. The PDF, printed from tenx on 24 Nov, is newer than the text copy and stricter in five places (the deadline, three testers for each of two tests, walkthrough evidence, the submission format), so we follow the PDF. Before designing around the stack, we checked each tool against current documentation and community reports, because the brief warns that parts of it will be out of date. Then we wrote `00-requirements.md` (every deliverable traced to the evidence that proves it), `01-plan.md` (architecture, schedule, units of work, spikes, experiments, risks), `decisions.md` (ADR-001 to ADR-014, mostly still proposed) and `CLAUDE.md` for Claude Code.

What changed our minds:

| Finding | What it changed |
|---|---|
| Gemini 3.8 TTS reads its input verbatim, so a style hint typed into the text may be spoken | Separate fields for spoken words and voice style in the schema (ADR-001); E1 tests it |
| Daily TTS caps are reported as low as 10–100 requests, resetting at 11:00 EAT | TTS, not GPU, is the scarce resource: quota-aware planning and a per-line cache (ADR-008) |
| The official Wan 2.2 TI2V-5B 720p run needs at least 24 GB; free-T4 reports point to a distilled build at 480p, about 8 minutes per clip | Ken Burns path first, Wan as an upgrade, spike S1 before committing GPU time (ADR-005, ADR-006) |
| FLUX.2 klein takes up to four reference images, each under 512×512 | Reference sheet designed as at most four small images |
| Kaggle's CLI gives a P100 unless told otherwise, and current PyTorch can't use it | Accelerator named explicitly in the job runner |
| claude.ai's sandbox can't reach the providers | Claude Code executes on Y's machine (ADR-012) |

Open. Story and subject, narration language, consent, compute, agent autonomy (`01-plan.md` §19). Testers need recruiting today.

Next. Once Y signs off: write audience and intent into DESIGN.md, then U0–U3 in Claude Code, and launch spike S1 on Kaggle.

## 2026-11-25 (Wed) — Entry 1: date correction, compute and language

What happened. Entry 0 and the first plan assumed the build started on Tuesday; it started on Wednesday. The PDF's print date (24 Nov) had been taken for today's date. That removed a day from the schedule, so `01-plan.md` §13 was re-cut for Wednesday to Thursday, the submission target moved to 21:00 on Thursday, and scope was re-prioritised: the critic and the Kaggle CLI push became Coulds, and the MCP server moved to after the deadline. Dates in the ADR log were corrected.

Decisions. Compute: Kaggle T4s and Colab; no local GPU and no frontier key (ADR-006 revised: one runner script for both, launched by hand, results brought in with `film ingest`). Language: Amharic would be nice, English has to be available (ADR-015 proposed: both narrations from one storyboard, English first, the user tests pick the main version). Agent autonomy: Y asked for the options to be explained; the comparison is now in ADR-002, and the choice is pending.

What we learned. A wrong date is a planning bug like any other. Every schedule now states the day it starts from, and every log entry is checked against the clock.

Next. Y: keys and accounts, the story and consent, testers for both rounds, audience and intent in DESIGN.md, and the two pending choices. Claude Code: U0–U3 as soon as the keys exist.

## 2026-11-25 (Wed) — Entry 2: decisions locked, story-agnostic core built

Decisions. Y chose the lean plan-and-judge agent (ADR-002, accepted) and both languages from one storyboard, English first (ADR-015, accepted). ADR-016 records what gets committed and where mock runs live. ADR-012 is amended: the core was built in claude.ai, offline, while the story and the keys are being prepared, and Claude Code takes over from U3.

What we built. Four units, all on mock providers:
- U0: the project, the `film` CLI, the Makefile, hygiene files and skeletons of the required root documents.
- U1: schema v1 with two languages, and the lint with its consent gate.
- U2: the cache with sidecars, the logs, the retry policy, the `film plan` dry run and the mock providers.
- Most of U8, built early: per-language timelines, clip choice with the Ken Burns fallback, the blurred fill for vertical clips in 16:9, sidechain ducking, loudness normalisation, burned-in subtitles, the end card and the radio cut.

That's about 1,550 lines of pipeline code and 230 lines of tests. All 20 tests pass in about 25 s, including a full mock build. A full-size mock build ran 47 units in 87 s and produced four 67-second exports. They measured −14.6 to −14.7 LUFS, with true peaks of −4.6 to −5.3 dB.

The walkthrough, rehearsed. We edited shot 4's image prompt, and `film plan` listed exactly four changes: the keyframe s04 as a miss and its three clips as upstream changes. It predicted 2 model calls, and `film render` appended exactly those two lines to runs.jsonl. Editing one English narration line predicted and made exactly one call. Both runs are now tests.

What we learned. Tests that check numbers can't see pixels. Every test passed while the vertical subtitles ran to three lines (F1, E17). Looking at a rendered frame is now part of reviewing any change to assembly.

Evidence for the practice ledger ("let the agent write the stage scripts"). The agent wrote the code in this entry. Review caught one logic bug before anything ran: a meaningless `finally` block in the runner. Only looking at the output caught the visual bug (F1). Y fills in the verdict.

Next.
- Y: keys and accounts (a Gemini key; a Cloudflare account ID plus a Workers AI token; a phone-verified Kaggle account; Colab). Then the story brief (`docs/story/brief.template.md`), consent in ETHICS.md, audience and intent in DESIGN.md, and testers for both rounds.
- Claude Code (U3): real providers for Gemini text, Gemini TTS and Cloudflare FLUX; `make smoke`; the GPU runner with `film bundle` and `film ingest`; then spike S1.
- Then U4: the director drafts storyboard v1, which becomes the radio cut.

## 2026-11-25 (Wed) 22:00 — Entry 3: the agent layer becomes the point

Who: Y (direction) and Claude Code (review and planning). No code changed and no model calls.

What we did. We moved the project from claude.ai into Claude Code, unpacked it, re-read the brief end to end and reviewed the plan against Y's goal. Y is the tutor for TRP2. Y is building this studio both to make our film and as the reference for how trainees should orchestrate a movie-making agent. Under ADR-002 the movie agent was a one-shot director and an optional critic, so every judgement fell on Y and there was little agent to learn from.

Decisions.
- ADR-017 supersedes ADR-002. Agents may explore with generation models within a budget, but only values pinned in storyboard.json reach the film. Candidates are archived under the real cache key, so a pin costs no call.
- ADR-018: agents change the storyboard only through proposals limited to the paths they own, checked before anyone sees them and recorded in decisions.jsonl. Consent stays Y's alone.
- ADR-019: the showrunner and the producer are code; the specialists are Gemini structured-output calls; autonomy is set per decision type. Keyframe pins are delegated only if the critic agrees with Y's blind picks on 8 of 10 shots.
- ADR-003 and ADR-009 are amended to match.

What changed in the plan. §2, §3, §9, §13 and §14 were rewritten. New units A1–A5: A2 replaces U4, A3 replaces U10, and A5 was U12. E18–E20 were added, and E13 went from "only if built" to the rule that sets autonomy. Risks and open decisions were updated. The submission target moved from 21:00 to 22:00 on Thursday.

What we learned. ADR-002's worry, that an agent calling a model makes the film unrepeatable, was about where the agent's output lands, not about whether it calls a model. If a pin in the contract is the only way into the film, every rubric property survives and the agents can still do the work.

Setup found on Y's laptop. FFmpeg, uv and Python 3.12 are missing; Python 3.9.6, git and Homebrew are present. The Kaggle account is ready. Still needed: a Gemini API key, a Cloudflare account ID and Workers AI token, Colab, and a public GitHub repository.

Next.
- Y: install the tools, put the keys in `.env`, write the story brief, the audience and intent, and the consent rows, and recruit testers.
- Claude Code: U3 and A1, then A2 and the radio cut.

---

Template for new entries:

    ## YYYY-MM-DD (Day) HH:MM — Entry N: <title>
    What we did.
    What we learned.
    Decisions touched: ADR-…
    Experiments: E… (run ids)
    Failures: …
    Next.
