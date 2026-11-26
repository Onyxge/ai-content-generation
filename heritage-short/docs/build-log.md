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

## 2026-11-25 (Wed) 23:25 — Entry 4: decision core built, real providers written

Who: Y (direction) and Claude Code (code). No model calls yet: `.env` is still empty.

What we built.
- **A1, the decision core** (`pipeline/agents/patches.py`, `decisions.py`, `config/agents.toml`, the commands `film propose`, `proposals`, `approve`, `reject` and `revert`). Agents' patches address items by id; every change is checked against its owner, the Y-only fields, the schema, the lint and the consent gate; it is priced with a dry run; and it waits, applies or is refused according to its kind's autonomy. Every step is a line in `decisions.jsonl`, and refused proposals are kept as evidence. 17 tests, including the cases trainees will meet: an agent editing another agent's field, an agent touching consent, an agent adding a person, a proposal that breaks the 8–12-shot rule, a stale proposal, and revert.
- **U3, mostly.** Gemini adapters for structured text, vision and TTS; a Cloudflare adapter for FLUX.2 klein and FLUX.1 schnell; `actor` on every runs.jsonl line; `.env` loading; `film smoke`, which makes one tiny logged call per provider once a day; and a check that FFmpeg has all 16 filters we use. 14 offline tests cover error mapping, WAV handling, the TTS request shape and the Cloudflare multipart fields. The GPU runner, bundle and ingest are still to do.

What we learned.
- **The brief's stack had already moved.** A subagent checked the official docs, and its findings changed the adapters:
  - Gemini's docs now live at aistudio.google.com.
  - There is no 3.8 Flash-Lite text model; we use `gemini-3.5-flash-lite`.
  - 3.8 TTS takes its style as `speech_metadata` on the part, not in the text, and returns a complete WAV. We had planned to wrap raw PCM.
  - Amharic has no allowed `language_code`, so we let the model detect the language.
  - Gemini silently drops `pattern` and `minLength` from structured-output schemas, so we validate every answer ourselves.
  - The SDK retries on its own; we turned that off so the engine logs every attempt.
  - Cloudflare's daily-allowance error is code 3036, not the 4006 we had guessed.
- **The image allowance, not the GPU, may bind the agents.** At about 26 neurons per 512-pixel tile, a 1080×1920 keyframe costs 200–310 of the 10,000 daily neurons, so one round of three candidates for ten shots uses most of a day. The producer has to budget in neurons. Keyframe size is a new open decision (01-plan §19).
- **Moving to Y's Mac surfaced a tool problem the sandbox had hidden.** Homebrew's FFmpeg has no `subtitles` filter (FAILURES.md F2).

Decisions touched: ADR-018 amended (patches address items by id). FAILURES.md F2.

Next.
- Y: put the Gemini key and the Cloudflare account ID and token in `.env`, then run `make smoke`. Write the story brief, the audience and intent in DESIGN.md, and the consent rows.
- Claude Code: A2, the story chain and the radio cut, then the GPU runner (bundle and ingest), then A3.

## 2026-11-25 (Wed) 23:50 — Entry 5: the story agent, built while Y writes the story

Who: Claude Code (code), while Y writes the brief. No real model calls: everything ran on mock providers with canned answers taken from the example story.

What we built. A2's story chain (`pipeline/agents/story.py`, five prompt files in `pipeline/agents/prompts/`, `film storyboard`):
- **The steps.** Outline (title, logline, treatment, cast, look, music idea) → beats → gate G1 → shots → English narration within a word budget per shot → Amharic. Each step is a unit in the same runner as every other model call, so it is cached by its inputs and logged in runs.jsonl with actor `story`.
- **Gate G1 is real.** The steps after the beats are blocked until `film storyboard --approve-beats` records the outline's and the beats' hashes in decisions.jsonl. If Y edits either afterwards, the gate closes again.
- **Y's edits win.** An edited draft is backed up, re-signed and logged as `hand_edit`; only the steps after it rerun.
- **Repairs are logged.** An answer that parses but breaks a rule the code checks (8–12 shots, runtime 60–90 s, ids, a cast the shots must use, a line over its word budget, brackets in spoken text) is sent back with the problems listed. Each repair is its own runs.jsonl line, with status `repair`.
- **Code assembles the draft storyboard, not a model.** Languages, the main version, runtime and voices come from Y's config, and who is real comes from the outline Y approved. `film storyboard --adopt` (gate G2) makes it storyboard.json v1, with a snapshot and a decisions.jsonl line. It refuses to replace an existing storyboard without `--replace`, and refuses a draft with a real person and no consent.
- **Eight tests,** including one for each rule above.

What we learned. Content-hash caching cuts reruns short. When Y edited a beat, the shot step reran, but when its answer came back byte for byte the same, narration and translation stayed cached, because their keys depend on the shot file's bytes, not on the fact that it reran. The first version of the test expected all three later steps to rerun; the cache was right and the test was wrong.

Decisions touched: ADR-018 amended (v1 is adopted at G2, not proposed).

Next.
- Y: the brief, the intent and the consent rows, then the Gemini key.
- Claude Code: run the chain on the real story; Addis AI as a second Amharic voice once its API is confirmed; the GPU runner; A3.

## 2026-11-25 (Wed) 23:55 — Entry 6: Addis AI as a second Amharic voice; the full FFmpeg is in

Who: Claude Code, with a subagent checking Addis AI's docs. Y created an Addis AI key; nothing called it yet.

What we built.
- **`pipeline/providers/addis.py`, an adapter for Addis Voices 2,** written from Addis AI's docs and its official Python SDK. It posts the documented JSON body, downloads the signed audio URL without the key, and converts anything that isn't WAV with FFmpeg. It sends an idempotency key derived from the line, so a retry isn't billed twice. Its errors map to ours: 402 (out of credit) is a quota, 429 and 409 are retried.
- **`SpeechRouter`.** A voice whose model is `addis-voices-2` is spoken by Addis AI; any other by Gemini. Swapping the Amharic voice is one Y edit to `voices.am`, and the cache regenerates only the Amharic lines.
- **The log records who actually spoke each line.** runs.jsonl now takes the provider from the adapter's answer, and records Addis AI's ETB cost per call.
- **Five offline tests,** for the request body, the signed-URL download, error mapping, refusing English, and routing with a stable idempotency key.

What we learned.
- **Addis AI's FAQ and its Terms disagree about training on API inputs, and the Terms bind.** Only narration lines go there (ETHICS.md).
- **There are no daily quotas, but there is a prepaid ETB wallet:** a full Amharic narration costs about 6 ETB.
- **A blind comparison against Gemini's Amharic is E21,** the brief's "real benchmark" and "more languages" ceiling at once.
- **Running E21 cleanly needs A3's archive.** Today, swapping the voice overwrites the other version's files, and swapping back costs the calls again. A3 keeps every candidate under its cache key, so both versions survive.

FFmpeg. The `ffmpeg-full` install was stopped at its very end by the app, but Homebrew had already installed it. It's keg-only, so the pipeline now finds it there (FAILURES.md F2, updated). With it, all 72 tests pass, including both full mock builds, which had been skipped. A full-size mock build took 36 s on Y's Mac, and the frames from both orientations look right.

Next.
- Y: the brief, the intent, the consent rows, and the keys in `.env` (Gemini, Cloudflare, `ADDIS_AI_API_KEY`).
- Claude Code: the story chain on the real story, `make smoke`, then the GPU runner and A3.

## 2026-11-26 (Thu) 00:05 — Entry 7: first real calls

Who: Y ran `make smoke` with real keys; Claude Code read the logs.

What happened. All three providers answered, and runs.jsonl has six lines.
- **Gemini text failed three times before it worked.** It got 503 UNAVAILABLE three times, then succeeded after 131 s. The retry policy did its job without help, and every attempt is logged (FAILURES.md F3).
- **Gemini TTS took 4.2 s** and returned a proper WAV (24 kHz mono 16-bit, 1.71 s). That length, for three words, suggests the style text wasn't spoken; Y should still confirm it by ear.
- **Cloudflare FLUX.2 klein took 9.5 s** for a 256×256 PNG.
- **Addis AI wasn't tested:** `ADDIS_AI_API_KEY` isn't in `.env` yet.

What we changed. The Gemini client had no timeout, so a hung call would have hung the run. It now has 240 s, after which the call is a transient error that is retried and logged.

What we learned. The model ids and request shapes that came from the docs check work against production: `gemini-3.8-flash`, `gemini-3.8-flash-tts` with the style as speech metadata, and klein as multipart. Gemini's availability, not its quota, was the first thing to bite.

Next.
- Y: add `ADDIS_AI_API_KEY` to `.env`; write the brief, the intent and the consent rows.
- Claude Code: run the story chain as soon as the brief is in.

## 2026-11-26 (Thu) 00:30 — Entry 8: the real story goes in; the consent gate catches the agent

Who: Y (the story and the decisions) and Claude Code.

What we did.
- **Fixed Addis AI** (FAILURES.md F4). Production answers 201 with the WAV inline. The smoke test now passes for all four providers, and the retry reused the same clip.
- **Turned Y's script "The Last Pour" into the brief.** It's inspired by a story Y's grandmother tells: a man who served honey wine at Emperor Haile Selassie's palace is, for one night, called by his name. Y's decisions:
  - Tesfaye is fictional, inspired by the family story.
  - The audience is Ethiopians on social media, who should feel "the dignity of the people history doesn't name".
  - The emperor is never shown or voiced. The brief makes no exception for historical or deceased people, and his consent can't be recorded. He is present through the narration and the room.
  - Dialogue is retold by the narrator for now; character voices may be tested later.
  - These are in DESIGN.md and ETHICS.md, and the end card now says the film is inspired by a family story and that some scenes are imagined.
- **Ran the story agent for real**, to gate G1. The outline and the beats are good. Gemini struggled: a 504 after 239 s, two 503s, then answers in 66 s and 120 s, 7 min 16 s in all. Every attempt is logged.

What the agent got wrong, and what caught it. The outline put the emperor and the grandmother in the cast as real people with no consent. The prompt asked for everyone who "should appear or be spoken about", so it did that. Nothing had been generated, and the lint would have refused to adopt such a draft. But the right fix is earlier:
- **Who becomes a character.** Only people who appear in a shot become characters; someone only spoken about gets no character sheet and needs no consent.
- **A gate at the shot step.** The step now refuses any shot that puts a real person without consent in the frame, and sends it back with the reason.

These are code changes, so the outline and beats stay cached. Two tests cover them: a real person spoken about but never shown passes; one put in a shot is repaired, and if every answer shows him, the step fails and there is nothing to adopt.

What we learned. The consent gate sits best at the earliest step where a person could enter a frame, not only at the end. As a tutor's note, the brief is silent on deceased relatives and historical figures, which heritage stories will often involve. Trainees will need a ruling.

Next.
- Y: read `docs/story/drafts/01-outline.json` and `02-beats.json`, then run `film storyboard --approve-beats` (G1). Confirm the grandmother is happy for her story to be used.
- Claude Code: shots, narration and translation, then the English radio cut.

## 2026-11-26 (Thu) 00:40 — Entry 9: "the great emperor", keeping approved drafts, gate G1

Who: Y (decisions) and Claude Code.

Decisions.
- **The emperor is "the great emperor".** Y decided he is never named: a fictional ruler, a short elderly man with an upright posture. Claude Code proposed, and Y can reverse, keeping him unvoiced and never in close-up, so the picture stays about Tesfaye and can't become a portrait. ETHICS.md records the residual risk: a viewer may still read him as Haile Selassie. Y will check every keyframe of him.
- **The beats are approved,** with the emperor renamed in the outline's cast and treatment and in beat b3.

What we built. Changing the brief changes the key of every story step, so the runner would have regenerated the outline and the beats Y had just approved. `film storyboard --keep outline,beats` now carries approved drafts over to the new brief. It re-keys their sidecars and logs a `kept_draft` decision with the old and new keys, so the record says plainly that these drafts weren't made from the new brief. One test covers it. Y's edits to the drafts were also logged as `hand_edit`.

What we learned. A cache keyed by inputs needs a human override, or every upstream wording change throws away approved work. The override has to be logged: the log is the only thing that tells a carried-over draft from a fresh one.

Next. Shots, narration and translation are running. Then Y reads the draft and adopts it (G2); then narration, the radio cut, and the Kaggle GPU runner.

## 2026-11-26 (Thu) 00:50 — Entry 10: the draft storyboard, and the GPU round trip

Who: Claude Code, on Y's go-ahead to follow the recommended sequence.

The story agent finished. Shots, narration and translation took 6 min 38 s, with four more 503s, each retried and logged. `docs/story/drafts/storyboard.draft.json` validates with no warnings:
- **Ten shots, 71 s** including the end card; four of them use Wan for real motion (the pour, Tesfaye lowering his eyes, his tears, the last sip).
- **The great emperor appears in two shots,** always at a distance, in profile or from behind, as the brief asks.
- **The translation step flagged three things for a native speaker:** how "Tesfaye" is spoken, the honorific plural for the emperor, and the phrase for "the man behind the tray".
- It waits for Y at G2.

What we built. The GPU round trip (U3's last part):
- **`film bundle shots|music`** packs every uncached GPU unit into a self-contained zip: a manifest with each job's spec and cache key, the keyframes, and the runner scripts.
- **`gpu/runner.py`** runs the bundle anywhere with a GPU. It writes each output the moment it's done and appends a results line per job, failures included. It resumes after a crash, and with `--gpu N --shards 2` it splits jobs across Kaggle's two T4s.
- **`film ingest`** puts a result in the cache only if its key still matches the storyboard; a clip for a shot edited after bundling is stale and stays out. Every result becomes a runs.jsonl line with its GPU seconds.
- **Two tests,** run end to end with the runner's mock backend: the round trip, a stale result, a failed job, ingesting twice, resuming, and sharding.

The model backends (Wan 2.2 and ACE-Step 1.5) wait for a research check of how they run on a T4.

## 2026-11-26 (Thu) 01:00 — Entry 11: v1 adopted; first narration and references

Who: Y (adopted v1, said go) and Claude Code.

What happened.
- **Y adopted the draft as storyboard v1** (G2, logged, with a snapshot). Narration gained a `--lang` option so English could be voiced before a native speaker checks the Amharic.
- **English narration: 9 of 10 lines.** s10 hit Gemini TTS's daily cap, which is about 10 calls (FAILURES.md F5). It's deferred until the 11:00 EAT reset, and the radio cut waits for it. The measured lines run at 1.9–2.7 words a second, against our planning figure of 2.4.
- **References: all 12 options rendered.** They're on contact sheets in `build/review/`. The great emperor came out as a generic elderly man in a black cloak with no beard, not a likeness of Haile Selassie, which is what ETHICS.md asks Y to check.

What we noticed. Most options for all three characters drifted away from Ethiopian features: Tesfaye looks South Asian or Latin in three of four seeds, and the guest looks Mediterranean in all four. Only Tesfaye's seed 103 reads clearly as Habesha. The descriptions say "Ethiopian" once, and the model's defaults win. For an Ethiopian audience that would sink the film, so E22 tests it: explicit features and dress against the current wording, same seeds. The descriptions belong to look-dev (ADR-018), so the change is Y's call or a look-dev proposal.

Next.
- Y: pick, or re-render, the references (G4); decide whether Amharic moves to Addis AI (E21) to save Gemini's TTS quota for English.
- At 11:00 EAT: voice s10, then build the radio cut and send it to testers.

## 2026-11-26 (Thu) 01:15 — Entry 12: the GPU backends, and spike S1 ready to launch

Who: Claude Code, with a subagent checking how Wan 2.2 and ACE-Step 1.5 run on a T4.

What the check found. The brief's stack doesn't run as documented on a free T4:
- **Wan's official repo is out.** It asserts on FlashAttention 2, which Turing GPUs can't run, and rejects 480p. Diffusers' `WanImageToVideoPipeline` runs on PyTorch SDPA at any multiple of 32.
- **bf16 costs about 11x on a T4,** so we use fp16 with the VAE in fp32.
- **Kaggle's image is now Python 3.13 with transformers 5.x,** which ACE-Step 1.5 rejects, so ACE-Step gets its own Python 3.12 environment.
- **Weights are big:** Wan's are about 34 GB a session, ACE-Step's about 10 GB.
- **There's no published T4 timing for 121-frame clips.** S1 is the first.

What we built.
- **`gpu/runner_wan.py`** (fp16, fp32 VAE, CPU offload, tiled decode) and **`gpu/runner_acestep.py`** with its job script (DiT only, in its own environment).
- **Model loading is timed apart from GPU time** (`load_s`).
- **The step count is now part of each GPU unit's cache key.**
- **`gpu/kaggle_runner.ipynb`** finds the bundles, runs Wan on GPU 0 and ACE-Step on GPU 1 at the same time, prints each job's time and peak memory, and zips the output for `film ingest`. **`gpu/README.md`** has the steps.
- **Ingest now reads several bundles' results from one download.**

Two keyframes with no people in them (s02, s09) were rendered for the spike; both look right. Two bundles are ready in `build/bundles/`: shots (s02.i2v, the pour) and music (three takes, 86 s each). ADR-006 is amended.

Next. Y uploads both zips to Kaggle and runs the notebook with `LIMIT = 1` before sleeping (S1 and S2). Its timings decide steps, frames and how many shots get Wan.

## 2026-11-26 (Thu) 12:15 — Entry 13: Kaggle from the command line; s10 voiced; the radio cut exists

Who: Y (the Kaggle token, the go-ahead) and Claude Code.

What we built. `film kaggle push / status / pull` (U11, `pipeline/kaggle_jobs.py`):
- **push** uploads the newest shots and music bundles as a private dataset (`<kaggle-user>/heritage-short-bundles`). It then runs `gpu/kaggle_runner.ipynb` as a private notebook (`<kaggle-user>/heritage-short-gpu-runner`) on `--accelerator NvidiaTeslaT4` with internet on, the dataset attached, and a 3-hour timeout.
- **pull** downloads the output and runs `film ingest`.
- Each launch is recorded in `build/kaggle/launches.jsonl`.
- A read-only call checked the token first (FAILURES.md F6 explains why the old key pair stopped working).

Launched at 12:09: spikes S1 and S2 in one session, with all four jobs (the s02 Wan clip and three ACE-Step takes). It was queued at first; a background watcher checks it every minute.

The radio cut. The TTS quota reset at 11:00, so s10.en was voiced (one call, 4.6 s). `film radio --lang en` built `outputs/radio/radio_en.mp4`: 71.8 s, 720×1280, narration over the temp drone on black, with two-line subtitles inside the safe area (checked on five frames). It measures −14.5 LUFS, with a true peak of −0.9 dB, 0.1 dB over our −1 dB ceiling. The two-pass loudnorm in U8 will fix that before the final export.

Behind schedule. Test 1 was planned for 08:00–11:30; it starts now. The radio cut goes to three or more testers, and their notes go into DESIGN.md.

## 2026-11-26 (Thu) 12:20 — Entry 14: the radio cut will carry the real score

Y asked for background music. The score was already planned: three ACE-Step takes are in the Kaggle run, which is still queued at 12:20. Until now the radio cut always used the synthetic temp drone. It now picks its music the way the film does: the pinned take (`music.cues[0].selected`) if it's rendered, otherwise the first take, and the drone only until a take exists. A test checks the switch. Next: listen to the three takes under the narration at low volume, pin one with a reason (E10), and rebuild the radio cut.

## 2026-11-26 (Thu) 14:00 — Entry 15: the first Wan clip

After three Kaggle runs, each stopped by a different real limit (the GPU, host RAM, then our own glue; FAILURES.md F7–F9), Wan 2.2 made s02: honey wine pouring into a berele. That's 121 frames at 480×832, in 1,737 GPU seconds, with a peak of 5.75 GB. It's ingested, so the film now uses it for s02 instead of the Ken Burns still. Spike S1 has its answer: all four i2v shots are affordable, about two GPU hours. Each run cost a few GPU minutes, and every failure is a logged traceback, which is the troubleshooting evidence the brief asks for.

The music relaunched alone at 13:55. ACE-Step loaded and ran on the T4, then crashed on our missing key signature (F9), now fixed.

## 2026-11-26 (Thu) 14:10 — Entry 16: the score takes are in

The music-only run (launched 13:55) made all three ACE-Step takes in 100, 27 and 26 GPU seconds, and all three are ingested. Each is 86 s of 48 kHz stereo; measurements are in EXPERIMENTS.md (E10). One radio cut per take is in `build/review/`, built with the take pinned in memory only; the storyboard is unchanged until Y picks. `outputs/radio/radio_en.mp4` now carries the first take, m1.11, because nothing is pinned yet.

Spike S2 has its answer. ACE-Step 1.5 runs on a Kaggle T4 in fp16, DiT only, from its own Python 3.12 environment, at about 3× real time.

Next. Y listens and picks (E10), and the pick lands as a Y decision (`music_pick`), with its reason in `why`. Then the reference faces (G4), then keyframes and the three remaining Wan clips.

## 2026-11-26 (Thu) 16:20 — Entry 17: the score is chosen

Y picked m1.13, and a colleague agreed. It went in through the decision layer as proposal P-0001: actor Y, kind `music_pick`, the three radio cuts and the measurements as evidence, and storyboard hashes 73bc45348315 → 3ec21f55d085. It's the first change to the storyboard since v1. The radio cut is rebuilt with the score: −14.8 LUFS, −1.0 dB true peak (inside the ceiling this time), 71.8 s.

The take's two quiet stretches land under the grandmother line and the last words, which is why it works (E10). The measurement had counted those gaps against it.

Next: the reference faces (G4), then keyframes and the three remaining Wan clips.

## 2026-11-26 (Thu) 16:25 — Entry 18: reference faces re-rendered (E22)

On Y's go-ahead, the three character descriptions were rewritten with explicit features and period dress. That went in as decision P-0002, and all 12 reference options were re-rendered with the same seeds (2 min, 12 calls). Tesfaye and the great emperor now read clearly as Habesha in every option, and the guest in 2 of 4 (E22). The before/after sheets are in `build/review/`. Next: Y picks the golden reference for each character (G4, always Y). Then the eight keyframes with people, then the three remaining Wan clips on Kaggle.

## 2026-11-26 (Thu) 17:00 — Entry 19: keyframes, a rough cut, and three Wan clips running

- **G4.** Y picked Tesfaye 103, the guest 202 and the emperor 302 (P-0003).
- **Keyframes.** All eight with people rendered, then re-rendered after the triplet problem (F10): they now condition on the sheet's front view.
- **P-0004** (the s07 prompt) waits for Y. The current s07 already shows the emperor from behind.
- **Kaggle.** s06, s08 and s10 launched at 16:48, about 1.5 GPU hours plus the queue.
- **Rough cut (G5).** `film assemble --lang en` built both orientations: 71.8 s, −14.8 LUFS, −1.0 dB true peak, nine Ken Burns shots and one Wan shot.
- **16:9.** Sampled frames showed centre-cropped faces, so the horizontal film now uses blurred fill for every shot (ADR-011 accepted).

## 2026-11-26 (Thu) 17:30 — Entry 20: Amharic narration by Addis AI

- **Voice.** Y chose Addis AI for the Amharic (P-0005, voice am-loza). All ten lines took 44 s, ten calls, none failing.
- **Radio cut.** The Amharic radio cut is 74.8 s.
- **E15.** Amharic runs 6% longer overall, and five shots grew. That moved the score's quiet stretch off s09.
- **Anchor.** Added an optional cue `anchor` (schema, lint, assembly `music_offset`, composer ownership, a test), and filed the anchor as composer proposal P-0006 for Y.
- **Native check.** The Amharic text hasn't been checked by a native speaker yet; Y can now check it by ear on `radio_am.mp4`.
- **Kaggle.** The three Wan clips are still running.

## 2026-11-26 (Thu) 17:35 — Entry 21: the score is anchored; true peak fixed

- **Anchor.** Y approved P-0006, the first agent proposal approved through the gate. The radio cuts are rebuilt, with the score shifted −0.008 s in English and +1.742 s in Amharic.
- **True peak.** One-pass loudnorm had been overshooting to −0.9 dB, so it now aims at −1.5 dB. Both radio cuts measure under the ceiling: English −14.8 LUFS / −1.5 dB TP, Amharic −13.7 LUFS / −1.4 dB TP.
- **Kaggle.** The Wan run is still going.

## 2026-11-26 (Thu) 19:00 — Entry 22: the near-final cut

- **Wan clips.** The three Wan clips came back at 18:51, about 34 GPU minutes each. On review, s06 is kept; s08 invented a second person's hand and an object, and s10's face drifted (EXPERIMENTS, "Wan on people"). Y approved falling back to Ken Burns for both (P-0007).
- **The build.** `film build` made all four films with zero model calls ("nothing to generate"):
  - English: 71.8 s, −14.8 LUFS, −1.5 dB true peak;
  - Amharic: 74.8 s, −13.7 LUFS, −1.4 dB true peak;
  - pictures: two Wan shots (s02, s06) and eight Ken Burns.
- **Checks.** Sampled frames of all four: English subtitles on the Amharic film, blurred fill in 16:9, the end card present.
- **The end card was wrong.** It still credited only Gemini TTS for the voice; the fix is proposal P-0008, waiting for Y.
- **Next.** Test 2 with the near-final cut; then README, report, walkthrough and post.

## 2026-11-26 (Thu) 19:10 — Entry 23: finished for submission

Y approved P-0008, the end card's two voices; all four films are rebuilt. The rejected Wan clips (s08, s10) moved to `outputs/_archive/rejected/`, which is gitignored.

Built:
- **`film costs` (U9):** COSTS.md's tables now regenerate from runs.jsonl and stages.jsonl, priced from `config/pricing.toml`, where only checked prices appear (two tests).
- **Docs:** each shot's reason is in DESIGN.md. ETHICS, ARCHITECTURE and the README say plainly what is built and what isn't (A3's automatic critic and explore loop, A4 and A5 are not). There's a root README for the repo, a walkthrough script (`docs/walkthrough.md`), and a report draft (`docs/report.md`) for Y to finish in Y's own voice.
- **Privacy:** before committing, every file to be committed was checked against the values in `.env`. No key appeared; Y's Kaggle handle had been written into the build log and is replaced with a placeholder.

The clean-clone check, as the brief asks. Only the files git would commit were copied into an empty folder, with no `.env` and the API keys unset in the shell. `make setup && make film` rebuilt all four films in 63 s, and runs.jsonl went from 106 lines to 106: zero model calls.

Waiting on Y: the test 1 and test 2 notes in DESIGN.md, the report in Y's voice, the walkthrough recording, the public post with the AI label, and the go-ahead to commit and push.

## 2026-11-26 (Thu) 20:00 — Entry 24: user test 2, and what changed

Three testers watched the near-final cut; their answers are in DESIGN.md word for word, with insights. The ending lands, all three would forward it, and all three would send the Amharic version. But none of their summaries names the server, the emperor or the name, and T2 wanted more context at the start.

Changes:
- **Subtitles.** Vertical subtitles are larger (FontSize 9 → 10; F11 for why not 11). All four films are rebuilt.
- **The opening.** s01's line now says where we are, in both languages, and the shot is 2 s longer (P-0009, story, pending Y).
- **The main version.** Amharic is recommended as the main version; that's `meta.primary`, which only Y can change.
- **Not changed.** The slow middle and the abrupt cuts (T1, T3): crossfades or shorter shots would need another test round.

Gap. Test 1's (radio cut) replies aren't recorded in DESIGN.md yet, and the brief asks for at least three testers for it as well.

## 2026-11-26 (Thu) 20:05 — Entry 25: the final cut

Y approved P-0009. s01.en (Gemini, 6.9 s) and s01.am (Addis AI, 7.3 s) were voiced, two calls; s01's Ken Burns clip was re-rendered for its 9 s length. The music anchor moved the score with the longer opening (offset +1.99 s in English, +3.62 s in Amharic), so its silence is still under s09.

After the rebuild, the English export measured −15.2 LUFS, because one-pass loudnorm falls short when it also holds the true-peak ceiling. `settle_loudness` now measures each export and, if it's more than 0.5 LU off, applies the missing gain with a limiter, copying the video. Final exports:

| Export | Length | Integrated | True peak |
|---|---|---|---|
| English 9:16 and 16:9 | 73.8 s | −14.0 LUFS (+1.2 dB second pass) | −1.2 dB |
| Amharic 9:16 and 16:9 | 76.7 s | −13.9 LUFS (no second pass) | −1.4 dB |

82 tests pass. Decisions this film went through: P-0001 to P-0009 (one rejected, P-0004).

## 2026-11-26 (Thu) 20:18 — Entry 26: Amharic is the main version

Y made Amharic primary (P-0010), the outcome ADR-015 left to the user tests: all three testers in test 2 would send the Amharic version to family. The main submission is `outputs/final/film_am_9x16.mp4`; the English films are the second version. No rebuild was needed, since `film plan` reported nothing to generate.

---

Template for new entries:

    ## YYYY-MM-DD (Day) HH:MM — Entry N: <title>
    What we did.
    What we learned.
    Decisions touched: ADR-…
    Experiments: E… (run ids)
    Failures: …
    Next.
