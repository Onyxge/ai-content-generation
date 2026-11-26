# 01 — Plan

Architecture, build order and risks for The Heritage Short. Decisions marked ADR-nnn are in `decisions.md`; requirements are in `00-requirements.md`.

Revised 2026-11-25 (build-log Entry 1): the build starts on Wednesday 25 November, not Tuesday, so the schedule and priorities were re-cut; compute is Kaggle plus Colab; the film is bilingual. Updated after Entry 2: decisions locked and the story-agnostic core built. Revised again Wed 25 Nov, 22:00 (Entry 3): the agent layer grows from a lean director into a team that explores, judges and pins under measured autonomy (ADR-017 to ADR-019), and the schedule and units are re-cut.

## 1. Goal

A small studio in code. One file, `storyboard.json`, describes the film. A story agent drafts it, six rendering stages turn it into a film, and a team of agents explores and judges the pictures and proposes every choice as an edit to the contract. English narration must exist and Amharic is wanted, so language is a dimension of the pipeline: pictures and music are shared, and only narration and assembly run per language (ADR-015). Every model call is cached, logged and costed, and anyone can rebuild the film with one command. The deadline is Thu 26 Nov, 23:59 EAT, about a day and a half after the build starts, so we aim to submit by 21:00 and cut scope before we cut quality.

## 2. Principle: the pipeline renders, agents decide

Two different agents are involved. Claude Code is the coding agent that writes the pipeline. The movie agent is part of the pipeline: a team of specialists that drafts the story, explores and judges the pictures, and proposes every choice as an edit to the contract. This section is about the movie agent.

The rubric pays for determinism: a validated contract, a cache that regenerates only what changed, a rebuild from a clean clone, and a live demo where one edit produces one new model call. Y's goal pays for orchestration: this studio is the reference for how TRP2 trainees should build a movie-making agent, and we make our own film with it. One rule serves both. `make film` is a pure function of storyboard.json and the cache, and only values pinned in the contract reach the film (ADR-017). Agents may spend quota exploring candidates, within a budget, but they never write an artifact and never run inside `make film`. A candidate reaches the film when its seed or id is pinned in storyboard.json. Candidates are archived under the key the real render would compute, so the pin costs no new call.

Three more rules keep a team of agents honest:
- Each agent may change only the storyboard paths it owns. Every change is a proposal that passes the schema, the lint, the consent gate and `film plan` before anyone sees it (ADR-018).
- Every proposal, approval and automatic application is a line in decisions.jsonl, with its evidence.
- The orchestration itself is code. The showrunner is a phase machine with gates where Y approves, the producer is the quota ledger, and autonomy is a setting per decision type that changes only when a measurement allows it (ADR-019).

ADR-002, now superseded, compared plan-and-judge, a fully autonomous loop and pipeline-first. This design is plan-and-judge, growing towards the autonomous loop one decision type at a time.

## 3. Architecture

```
 docs/story/brief.md + DESIGN.md intent + user-test notes
        │
        ▼
 ┌───────────────────── decision plane: agents (ADR-017 to ADR-019) ─────────────────────┐
 │ showrunner: phase machine, code       producer: quota ledger and budgets, code         │
 │ story chain · look-dev · cinematographer (one per shot) · critic (vision) · composer   │
 └───────┬────────────────────────────────────────────────────────────────▲───────────────┘
         │ proposal: a JSON Patch inside the agent's paths, plus evidence │ explore · critique · plan · measure
         ▼                                                                │
 film propose: ownership · schema · lint · consent gate · price           │
         │  Y approves at gates, or the autonomy setting applies it       │
         ▼                                                                │
 storyboard.json ─────────────────────────────────────────────────────────┘
        │  make film (agents never run here)
        ├─► references ──► keyframes ──► shots: Wan 2.2 via the GPU runner, or Ken Burns locally
        ├─► narration (one WAV per shot per language) ──► timeline per language
        ├─► music (cue → three candidates → pinned pick)
        ▼
     assemble (FFmpeg), per language and orientation:
     fit picture to voice, duck, subtitles, loudnorm, end card
        ▼
     film_en_9x16.mp4 · film_en_16x9.mp4 · film_am_9x16.mp4 · film_am_16x9.mp4 · .srt files

 every model call → runs.jsonl (with its actor) · every stage → stages.jsonl
 every decision → decisions.jsonl · every artifact → sidecar .json
```

| Layer | Job | Where it lives |
|---|---|---|
| Contract | Schema, the storyboard itself, cross-field lint | `schema/storyboard.schema.json`, `storyboard.json`, `pipeline/contract.py` |
| Engine | Dependency order, cache, logs, retries, quota ledger, dry-run plan, archive promotion | `pipeline/engine/` |
| Stages | One script per stage, each runnable alone | `pipeline/{references,keyframes,shots,narration,music,assemble}.py` |
| Providers | Thin adapters behind one interface, picked by config, so swapping a model is a config change | `pipeline/providers/` (gemini_text, gemini_tts, cf_flux, gpu_jobs, ffmpeg, mock) |
| GPU runner | One script that runs a job bundle on Kaggle or Colab and writes each result as it finishes | `gpu/runner.py`, launcher notebooks in `gpu/` |
| Decisions | Proposals, ownership check, autonomy, decision log | `pipeline/agents/patches.py`, `proposals/`, `decisions.jsonl` |
| Agents | Showrunner and producer (code); story, look-dev, cinematographer, critic, composer (Gemini structured output) | `pipeline/agents/`, `pipeline/agents/prompts/`, `config/agents.toml` |
| Interfaces | `film` CLI and Makefile; an MCP server over the same commands after the rough cut | `pipeline/cli.py`, `Makefile`, `pipeline/mcp.py` |

## 4. Stages

| Stage | Unit | Reads from the storyboard | Needs | Writes | Primary → fallback | Runs on |
|---|---|---|---|---|---|---|
| story¹ | film | nothing yet: the brief, the DESIGN.md intent and test notes | — | proposals: logline, beats, shot list, narration, translation | Gemini 3.8 Flash → current Flash-Lite | Gemini API |
| references | option | style block, character descriptions | — | `outputs/references/` | FLUX.2 klein 4B → FLUX.1 schnell | Cloudflare |
| keyframes | shot | image prompt, characters, seed | references | `outputs/keyframes/` | klein 4B with up to four references → schnell, text only | Cloudflare |
| shots | shot | motion prompt, mode, seed | keyframe | `outputs/shots/` | Wan 2.2 TI2V-5B → Ken Burns | Kaggle T4 (or Colab) through the runner; Ken Burns locally |
| narration | shot × language | spoken line and voice for that language | — | `outputs/narration/<lang>/` | 3.8 Flash TTS → 3.8 Flash-Lite TTS | Gemini API |
| music | cue × seed | caption, bpm, key, length | — | `outputs/music/` | ACE-Step 1.5 → synthetic drone (temp track only) | Colab (or Kaggle) through the runner |
| assemble | language × orientation | everything | all of the above | `outputs/final/` | FFmpeg | local |

¹ The story agent's chain (§9), run by `film next` or `make storyboard`. It's an authoring step, never part of `make film` (ADR-003, ADR-018).

Remote GPU work goes through one runner script (ADR-006). `film bundle shots` packs the uncached jobs into a bundle (a manifest plus keyframes). We run it by hand on Kaggle as a saved version with both T4s, so it keeps going after the browser closes, or on Colab. `film ingest` brings the results into the cache with timings measured on the GPU. Until a clip comes back, assembly uses the Ken Burns fallback, so `make film` always produces a complete film. Pushing bundles to Kaggle from the CLI is a stretch goal (U11).

## 5. The contract

The schema is hand-written and is also handed to Gemini as the structured-output constraint when the story agent drafts, so the agent can't produce an invalid contract (ADR-001). A first sketch, finalised in unit U1:

```json
{
  "version": 1,
  "meta": { "title": "…", "languages": ["en", "am"], "primary": "en", "runtime_s": [60, 90] },
  "style": { "block": "warm hand-painted gouache, soft golden-hour light, light film grain",
             "avoid": "text, letters, logos, extra fingers" },
  "characters": [{ "id": "grandmother", "real_person": true, "consent_id": "C1",
                   "description": "…", "reference": "ref_grandmother" }],
  "references": [{ "id": "ref_grandmother", "prompt": "…", "seeds": [41, 42, 43, 44], "selected": 42 }],
  "voices": {
    "en": { "model": "gemini-3.8-flash-tts", "voice": "…", "style": "warm, unhurried, intimate" },
    "am": { "model": "gemini-3.8-flash-tts", "voice": "…", "style": "warm, unhurried, intimate" }
  },
  "shots": [{
    "id": "s01",
    "reason": "Show the village at dawn so the walk to the market has a place to start.",
    "beat": "opening", "size": "extreme wide", "duration_s": 6, "characters": [],
    "image_prompt": "…", "keyframe_seed": 1001,
    "motion": { "mode": "i2v", "fallback": "kenburns", "prompt": "slow push-in, mist drifting", "seed": 2001 },
    "narration": { "en": "…spoken words only…", "am": "…" }
  }],
  "music": { "cues": [{ "id": "m1", "from": "s01", "to": "s12", "caption": "…", "instrumental": true,
                        "bpm": 70, "key": "D minor", "length_s": 100,
                        "seeds": [11, 12, 13], "selected": 12, "why": "…" }] },
  "end_card": { "lines": ["Made with AI", "…"], "duration_s": 3 }
}
```

Narration holds only the spoken words, because Gemini 3.8 TTS reads its input verbatim; voice and style live in `voices`. The English script is the single source of meaning: it is the English narration and also the English subtitle track of the Amharic film, and a shot can override it with `subtitle_en` when a faithful subtitle should differ from what is spoken. `meta.primary` names the version we submit as main; it starts as English and may change after the user tests (ADR-015). Music cues point at shot ids, not seconds, so they survive timing changes in either language. The lint step covers what JSON Schema can't: 8–12 shots; a runtime of 60–90 s for every language; unique ids and references that resolve; the consent gate (ADR-014); narration length against shot length (about 2–2.5 words per second for English until measured; Amharic measured from the radio cut); subtitle chunks of at most two lines of about 40 characters; and a warning when a prompt asks for text inside the image.

## 6. Caching, and how "only that shot regenerates" works

Each unit's cache key is the sha256 of canonical JSON (sorted keys, relative POSIX paths) of: stage, stage version, provider, model, parameters, seed, the fully resolved prompt, and the file hashes of the upstream artifacts it uses. The artifact is written next to a sidecar JSON holding the key, run id, model, parameters and the artifact's own hash. A unit is skipped when the sidecar's key matches and the file's hash checks out (ADR-004). Narration units are keyed per language, so an English edit never touches the Amharic audio, and the other way round.

Two rules make the walkthrough work. Changes cascade only along real dependencies, because a downstream key includes upstream file hashes. And no key depends on whole-film values: music length and clip frame counts come from the storyboard, never from measured narration or total runtime, so fitting everything together happens in assembly, which is cheap and always reruns.

Example: change the image prompt of shot 4. Its keyframe key changes, so one image is generated. Shot 4's clip key includes that image's hash, so one clip is regenerated (by Wan through the runner, or by a free Ken Burns render). Narration, music and the other eleven shots hit the cache, and assembly reruns. `film plan` predicts exactly that before anything is spent, and runs.jsonl gains one or two lines. Change an English narration line instead and you get one TTS call plus the English assemblies.

Current artifacts are committed, so a fresh clone with no keys and no GPU rebuilds the film from the cache; CI proves it on every push. Explored but unpicked variants go to a gitignored archive.

## 7. Logs and measurement

Every model-call attempt appends one line to `runs.jsonl` (ADR-007). An illustrative line, pretty-printed here, with made-up numbers:

```json
{"ts": "2026-11-25T21:14:03+03:00", "run_id": "r-20261125-2112", "stage": "keyframes",
 "unit": "s04", "attempt": 1, "actor": "pipeline", "provider": "cloudflare",
 "model": "@cf/black-forest-labs/flux-2-klein-4b",
 "params": {"width": 704, "height": 1280, "refs": ["ref_grandmother#42"]}, "seed": 1004,
 "prompt_sha": "9f2c…", "cache_key": "3b7e…", "status": "ok",
 "latency_ms": 2140, "gpu_s": null, "cost_usd_list": 0.0, "cost_basis": "see config/pricing.yaml",
 "quota": {"day": "2026-11-25", "used_today": 38},
 "output": "outputs/keyframes/s04.png", "output_sha": "c81d…", "error": null}
```

`stages.jsonl` gets one line per stage per run: cache hits and misses, wall time, and the measurements that prove what graders can't see or hear (narration durations per language, loudness and true peak per stem and for the final mix, how far the music dips under the voice, export runtimes and sizes). `film costs` turns both logs into COSTS.md tables: calls, median and p95 latency, and GPU minutes per stage, free-tier use against the caps we actually hit, and a list-price equivalent from a pricing file that records each price's source and date.

## 8. When things fail

| Failure | Example | What the pipeline does |
|---|---|---|
| Transient | Per-minute 429, 5xx, timeout | Exponential backoff with jitter, honours Retry-After, up to four attempts, every attempt logged |
| Daily quota | TTS or image allowance used up | Stops calling that provider, marks the remaining units deferred, uses the configured fallback if allowed, exits in a resumable state, logs the cap from the error body |
| Bad input | Invalid storyboard, 400 | Fails before any model call, naming the field |
| Safety block | Prompt refused | Marks the unit "needs prompt edit" and carries on with the others |
| Remote job | Out of memory, timeout, Kaggle or Colab session killed | The runner saves each output as it finishes; we ingest what came back and rebundle only what's missing |
| Quality | Critic or Y rejects a keyframe or clip | New seed, at most three attempts per shot, then the fallback and a FAILURES.md entry |
| Agent output | A patch outside the agent's paths, an invalid storyboard, malformed JSON from Gemini | The proposal is refused before anyone sees it, naming the path or rule; one retry with the error fed back, then the step is flagged for Y |
| Agent out of budget | Three rounds without an acceptable keyframe; the producer's reserve reached | The shot is flagged in `film status`; Y picks, rewrites the prompt, or keeps the best candidate under Ken Burns |

Before any run that spends quota, `film plan` lists misses per stage, projected calls, GPU minutes and what's left of each daily allowance (ADR-008).

## 9. The agent layer

Seven roles, two of them code. Each LLM role has a prompt file in `pipeline/agents/prompts/`, an output schema and a set of owned paths in `config/agents.toml`. Its LLM calls go through the runner as units of their own: cached by input hash and logged in runs.jsonl with its actor. Re-running an agent on unchanged inputs spends nothing.

| Role | LLM? | Pattern | May change (ADR-018) | Spends |
|---|---|---|---|---|
| Showrunner | No: a phase machine | Supervisor with gates | Nothing; applies approved patches | Nothing |
| Producer | No: the ledger and budgets | Refuses spending beyond a budget or into the reserve | Nothing | Nothing |
| Story | Gemini 3.8 Flash | Prompt chain: logline and treatment → beat sheet (3–5 beats) → shot list (8–12 shots, reasons, sizes, durations) → English narration with a word budget per shot → Amharic translation | Title and logline, the shot list, and per shot the beat, reason, size, duration, characters, narration and subtitle_en; the end card | Text calls |
| Look-dev | Gemini 3.8 Flash | Writes the style block, the characters and the reference prompts → explores 4 seeds per reference → the critic ranks them → Y picks the golden reference | Style, character descriptions, references | Images |
| Cinematographer | Flash-Lite, one worker per shot | From a shared bible (the style block and the characters): image prompt and motion prompt → explores 3 keyframe seeds → the critic ranks them → pin. At most 3 rounds, then the shot is flagged for Y | Per shot: image_prompt, references, motion | Images |
| Critic | Gemini 3.8 Flash (vision) | Ranks candidates against the golden reference with a fixed rubric: identity, style, hands and faces, stray text, composition centred enough for both crops. Order shuffled and logged | Nothing; writes verdicts | Vision calls |
| Composer | Flash-Lite | Spotting note → ACE-Step caption, bpm, key and length → 3 candidates on the GPU runner → Y picks by ear | Music cues, except `selected` | GPU minutes |

The story chain keeps every intermediate step (logline, beats, shot list) in `docs/story/drafts/`. That lets Y correct the story where it's cheapest, at the beat sheet, and lets graders see how the storyboard came to be. The chain reads only the public brief and DESIGN.md (ADR-013). A native speaker checks the Amharic text before any Amharic speech is generated. After each user test, the story agent turns the tester rows in DESIGN.md into a proposal whose evidence cites the rows it acts on. That makes "the storyboard visibly changed by what they said" traceable line by line.

Gates (ADR-019):

| Gate | Passes when | Who |
|---|---|---|
| G0 | DESIGN.md audience and intent, the public brief and the consent rows are written | Y |
| G1 | The beat sheet is approved | Y |
| G2 | Storyboard v1 is approved and the Amharic text is checked | Y and a native speaker |
| G3 | Test 1 is written up and v2 approved | Y |
| G4 | The golden reference is picked | Y, always |
| G5 | The rough cut has a picture for every shot and the chosen score | Y |
| G6 | Test 2 is written up and v3 approved: picture lock | Y |

Autonomy is set per decision type in `config/agents.toml`:
- `propose` waits for Y;
- `veto` is applied now and listed in `film status` for Y to revert;
- `auto` is applied without asking and still logged.

Everything starts at `propose` except motion prompts, which start at `veto`. Keyframe pins move to `veto` only if the critic agreed with Y's blind picks on at least 8 of the first 10 shots (E13).

Commands:
- `film status`: the phase, the gate, what waits for Y and the budget left.
- `film next`: runs the current phase's agents up to the next gate.
- `film explore <stage> <unit> -n N` and `film critique <unit>`.
- `film proposals` and `film approve|reject|revert <id>`.
- `film pick --blind <unit>`: Y's blind pick, for the calibration in E13.

After the rough cut, `film mcp` exposes the same commands as MCP tools, so any coding agent can drive the studio while the checks stay in the code underneath.

Seeds still follow explore, pick, pin (ADR-009, amended by ADR-017). The critic can do the picking when autonomy allows, and a pin is a cache promotion.

## 10. Two aspect ratios from one generation (open)

The vertical file is the main submission, so it has to look best, and we can't afford two Wan runs per shot. Wan's image-to-video output follows the input image's aspect ratio, which leaves three options. A square master can be centre-cropped both ways, so one clip serves both, at the cost of strictly centred composition and an upscale of about 1.33× at 720p (2× at 480p). A vertical master gives native quality where it matters, with the horizontal version built as a blurred-fill pillarbox, which reads as a social repost. Separate generations per orientation double the GPU bill, so that one is out. The default is the vertical master; we test the square one with two clips during spike S1 and decide when S1 returns (ADR-011, E9). Ken Burns shots don't have this problem: they're rendered natively in both orientations from a keyframe generated with room to crop.

## 11. Testing and CI

Unit tests cover schema fixtures, cache-key stability across operating systems, lint rules, subtitle chunking, timeline maths and the FFmpeg filter-graph builder. Mock providers produce labelled placeholder images, tones and clips, so `make film MOCK=1` runs the whole pipeline offline in seconds. CI runs on every push: tests, the mock film, gitleaks, and a reproduce job that clones fresh, runs `make film` with no keys, and asserts zero new lines in runs.jsonl and exports of 60–90 s. Those CI logs are text the graders can read.

## 12. User tests

Two rounds, each with at least three people from the intended audience: the radio cut on Wednesday evening and the near-final cut early on Thursday afternoon. Recruit both rounds now; sending the cut to someone's phone works. Prefer bilingual testers: they can hear both versions, and they count for whichever becomes the main. Play it once with no introduction, then ask three questions: in one sentence, what was it about; which moment stayed with you; where were you lost or bored. Round two adds: would you forward it, and to whom; could you read the subtitles on your phone; and, for bilingual testers, which version they would send to family.

Before each round the storyboard is snapshotted to `docs/storyboard-history/vN.json`. Afterwards DESIGN.md gets one row per tester:

| Tester (initials, relation to audience) | Version heard | Channel | What they said, in their words | Insight | Change (storyboard version, shot) |
|---|---|---|---|---|---|

## 13. Schedule

Re-cut Wed 25 Nov at 22:00 EAT (build-log Entry 3), about 26 hours before the deadline. The agent layer adds about a day of building, so the target moves from 21:00 to 22:00 on Thursday, and nothing below Must starts before the rough cut.

| When (EAT) | Y | Claude Code | Checkpoint |
|---|---|---|---|
| Wed 22:00–00:30 | Install FFmpeg and uv; keys in `.env`; story, audience and intent in DESIGN.md; consent rows; recruit testers for both rounds | U3 providers and `make smoke`; A1 proposals, ownership and decisions.jsonl | Smoke test logged; DESIGN.md committed before the first story call |
| Wed 00:30–02:30 | Approve the beat sheet (G1), then storyboard v1 (G2) | A2 story chain; English narration; radio cut | Radio cut ready to send first thing Thursday |
| Overnight | Launch spike S1 on Kaggle before bed | — | S1 timings in the morning |
| Thu 08:00–11:30 | Send the radio cut; test 1 with three or more people; approve v2 (G3); pick the golden reference (G4) | U5 look-dev and keyframes through A3 (explore, critic, pin); E13 blind picks; Amharic narration after the 11:00 quota reset | Test 1 in DESIGN.md with the v1 → v2 diff |
| Thu 11:30–15:00 | Review the pins; pick the score | Wan batch on Kaggle and ACE-Step on Colab; ingest; A4 `film status` and `film next`; U8 finishing | Rough cut (G5) by 15:00 |
| Thu 15:00–18:00 | Test 2 with three or more people | U9 costs tables, CI, clean-clone check; README, ARCHITECTURE, ETHICS | Feedback in by 18:00 |
| Thu 18:00–21:30 | Apply test 2 (G6); record the walkthrough; public post with the AI label on; write the report | Final exports; A5 MCP server only if everything above is on time | v2 → v3 diff in DESIGN.md |
| Thu 22:00 | Submit both assignments | — | Two hours of buffer before 23:59 |

## 14. Units of work for Claude Code

Re-cut Wed 25 Nov at 22:00 (Entry 3). The A-units are the agent layer (ADR-017 to ADR-019). Musts come first; Shoulds wait for the rough cut unless the schedule is on time.

| Unit | Priority | Scope | Done when |
|---|---|---|---|
| U0 Repo and hygiene | Must, done | uv project, `film` CLI, Makefile, `.env.example`, `.gitignore`, gitleaks pre-commit, skeletons of the root docs | Done (Entry 2) |
| U1 Contract | Must, done | Schema v1 with languages; lint, consent gate; fixtures; `film validate` | Done; Gemini's acceptance of the schema is checked in A2 |
| U2 Engine | Must, done | Cache keys, sidecars, dependency order, logs, retries, `film plan`, mock providers | Done; the quota ledger comes with U3 |
| U3 Providers, smoke test, GPU runner | Must | Gemini text with structured output and image input (for the critic), Gemini TTS, Cloudflare FLUX, FFmpeg check; `actor` in runs.jsonl; the quota ledger; `make smoke`; `gpu/runner.py` with `film bundle` and `film ingest` | One runs.jsonl line per provider with its latency; S1 running on Kaggle |
| A1 Decision core | Must, done | Proposals as RFC 6902 JSON Patch; ownership from `config/agents.toml`; Y-only fields; the check (ownership, schema, lint, consent, price from `film plan`); `film proposals`, `approve`, `reject`, `revert`; decisions.jsonl; autonomy per decision type | A patch outside an agent's paths is refused, naming the path; an approved patch lands in decisions.jsonl with the hashes before and after; tests |
| A2 Story chain and radio cut | Must (replaces U4); chain built, radio cut waits for the real story | Logline → beat sheet → shot list → narration → translation, each step a structured-output call that is validated, kept in `docs/story/drafts/` and ends in proposals; TTS per shot and language; timeline; radio cut over the temp drone | Storyboard v1 validates and arrived as approved proposals; the English radio cut plays end to end |
| U5 References and keyframes | Must | Look-dev and cinematographer prompts; reference options; golden pick (G4); keyframes conditioned on it, through A3 | Every shot has a pinned keyframe; faces and hands checked |
| A3 Explore, critique, pin | Must (replaces U10) | `film explore` renders N seeds into the archive under the real key; a pin promotes without a call; critic rubric and ranking, order shuffled; producer budgets and reserve; three rounds, then flag; `film pick --blind`; agreement computed | Pinning an explored seed renders with zero new calls (a test); verdicts in decisions.jsonl; agreement measured on at least 10 shots (E13) |
| U6 Shots | Must | Ken Burns in both orientations (done); Wan through the runner with ingest | Rough cut with a picture per shot; Wan clips ingested through the cache |
| U7 Music | Must | Cue spec → three ACE-Step candidates on Colab → Y's pick with a reason; the composer agent drafts the caption (Should) | Candidates logged; the pick written into the storyboard |
| U8 Assembly | Must, mostly done | Two-pass loudnorm and a measured ducking depth are still to do | All exports 60–90 s; loudness within 1 LU of target; ducking depth logged |
| A4 Showrunner | Should | Phase read from the contract, decisions.jsonl and the files; gates G0–G6; storyboard snapshots when a gate passes; `film status`, `film next` | `film status` names the phase and what waits for Y; `film next` stops at the next gate |
| U9 Reporting and CI | Must | `film costs` → COSTS.md, with agent calls as their own rows; storyboard diffs for DESIGN.md; CI with the tests, the mock film and a clean-clone rebuild | Tables regenerate from the logs; CI green on a fresh clone |
| A5 MCP server | Should, after the rough cut (was U12) | The studio's commands as MCP tools over the same code, checks included | A coding agent completes one explore → critique → propose → approve round through MCP |
| U11 Kaggle push from the CLI | Done (Entry 13) | `film kaggle push / status / pull`: a private dataset of bundles, a private notebook on GPU T4 x2 with internet, the output downloaded and ingested | One bundle round-trips without opening a browser |

Progress at submission (Thu 26 Nov, 19:15): U0–U3, U5–U9, U11, A1 and A2 are done. A3 is partial: `film explore` and the critic weren't built, and Claude Code reviewed frames by hand and filed proposals. A4 and A5 weren't built. The film is complete in both languages and both orientations.

## 15. Spikes to run first

| Spike | Question | How | Decision it feeds |
|---|---|---|---|
| S1 Wan on a Kaggle T4 | Can we get motion at all, how fast, at what resolution? | **Answered 2026-11-26, 13:54: yes; 1,737 GPU s per 5 s clip at 480×832, 50 steps, peak 5.75 GB (EXPERIMENTS.md, F7–F9). Wan for all four i2v shots, about 2 GPU hours.** Bundled 2026-11-26 01:12: one real job, s02.i2v (the honey-wine pour), 480×832, 121 frames, 50 steps, through diffusers in fp16 (`gpu/kaggle_runner.ipynb`, `LIMIT = 1`). It records seconds per clip, model-load time and peak VRAM. If it's too slow, rerun with fewer steps or frames; FastWan and GGUF are unconfirmed on a T4 | At 12 minutes or less per 5 s clip, Wan for 6–8 shots; otherwise 2–3 and Ken Burns elsewhere (ADR-005, 006, 011) |
| S2 ACE-Step on Kaggle (GPU 1, next to S1) | How long does an 86 s instrumental take, and does ACE-Step's own environment build on Kaggle? | The music bundle (3 candidates) through `gpu/kaggle_runner.ipynb` with `LIMIT = 1` | Whether all three candidates run in one session; Colab is the fallback |
| S3 TTS in both languages | How do both TTS models handle English and Amharic, including names, and what is our real daily cap? | Two lines per language through each model; one native listen | Voice, model split and quota plan (E1, E3, E16) |
| S4 Reference conditioning | Does klein keep the character with one reference image? | Two shots, references on and off, same seeds | Reference-sheet design (E4) |

## 16. Experiment backlog

The brief asks for at least ten. Each changes one thing, keeps the seed fixed, and cites its run ids. Under the deadline we favour the cheap ones: E11, E12, E14 and E15 cost no quota, E7 and E9 come out of spike S1, and E13, E18, E19 and E20 come out of building the agent layer for a few calls each.

| ID | Hypothesis | The one change | Measure | Cost |
|---|---|---|---|---|
| E1 | Style words typed into the narration get spoken by 3.8 TTS; the style field doesn't | Inline style prefix vs style field, same line and voice | Native listen | 2 TTS calls |
| E2 | A style instruction improves narration more than switching voices | Three voices with one style vs one voice with and without style | Native preference | 4 TTS calls |
| E3 | Flash-Lite TTS is good enough for the English version | Same line through Flash and Flash-Lite | Rating, latency | 2 TTS calls |
| E4 | Conditioning on the golden reference keeps the character recognisable | References on vs off, same prompts and seeds, four shots | Y's blind pick (and the critic's score, if built) | 8 images |
| E5 | klein 9B looks better than 4B by enough to accept its non-commercial licence | 4B vs 9B, same seeds | Blind preference, latency | 6 images |
| E6 | A fixed style block drifts less than describing the style per shot | Shared block vs per-shot wording | Side-by-side judgment | 8 images |
| E7 | 480p drafts save most of the GPU time for an acceptable loss | 480p vs 720p, same keyframe and seed | Seconds per clip, peak VRAM, side by side | 2 clips |
| E8 | Motion-only prompts beat re-describing the subject in image-to-video | Motion and camera only vs full description | Morphing and identity notes | 2 clips |
| E9 | A square master can serve both orientations | Square vs vertical master | Crop quality in both exports | 2 clips |
| E10 | The quietest of three score candidates works best under the voice | Three ACE-Step candidates | Listening under narration at low volume, reasons written | 3 tracks |
| E11 | The brief's ducking defaults suit our voice | Threshold and ratio variants | Measured music dip under the voice, in dB | FFmpeg only |
| E12 | Normalising each stem first makes mixing a creative choice rather than a repair | With vs without per-stem loudness normalisation | Loudness spread, listening notes | FFmpeg only |
| E13 | The critic agrees with Y's blind picks often enough to delegate keyframe pins | Critic ranking vs Y's blind picks on the same candidates | Agreement on at least 10 shots, and where they disagree; 8 of 10 moves keyframe pins to `veto` | About 10–20 vision calls |
| E14 | Viewers prefer real motion for people but not for places | Wan vs Ken Burns per shot in test 2 | Tester picks | No compute |
| E15 | The same meaning runs longer in Amharic than in English | Same script in both languages, same voice settings | Measured seconds per shot and in total, words per second | No extra calls |
| E16 | Respelling a name phonetically fixes an Amharic mispronunciation | Original vs respelled name in one line | Native listen | 2 TTS calls |
| E18 | A staged story chain needs fewer corrections than drafting the storyboard in one call | One call vs the chain, same brief | Lint errors, and how many fields Y changed before approving | About 6 text calls |
| E19 | The critic's ranking depends on the order the candidates are shown in | Same candidates, order reversed | How often the winner changes | About 10 vision calls |
| E21 | Addis Voices 2, built for Amharic, beats Gemini 3.8 TTS for the Amharic narration | The same Amharic lines, with only `voices.am` swapped from `gemini-3.8-flash-tts` to `addis-voices-2` (a narration voice such as `am-dawit` or `am-yohanes-calm`) | Blind preference of at least three native listeners; names they hear mispronounced; and a round-trip check, transcribing each line back with Addis speech-to-text and counting words that differ from the script | About 16 Addis lines (about 6 ETB) and a few STT calls; the Gemini side is the radio cut we make anyway |
| E20 | Feeding the critic's reasons back to the cinematographer raises the next round's acceptance | Round 2 with vs without the critic's reasons in the prompt, same seeds | Critic score and Y's acceptance of round 2 | About 12 images |

## 17. Ceiling

The brief judges ceiling work on insight, not volume, and our clock is short, so the ceiling should be work we're doing anyway, measured properly. Making the film in English and Amharic from one storyboard is the brief's "more languages" direction. We measure where Amharic speech fails against English (names, numbers, prosody), how much longer the same meaning runs in each language (E15), whether respelling fixes names (E16), and which version lands with which part of the audience (both user tests). The second ceiling is the agent layer itself (ADR-017 to ADR-019): a studio that a team of agents drives under measured autonomy. Its evidence is E13, E18, E19 and E20, plus decisions.jsonl. If the MCP server (A5) is built, it's also the brief's "a tool for others"; if not, it goes into the report's "what we'd build next".

## 18. Risks

| Risk | Likelihood | Impact | Mitigation | Early warning |
|---|---|---|---|---|
| The compressed timeline: about a day and a half | High | High | Musts before Coulds; manual GPU launch; critic, CLI push and MCP cut to Could or Next; submit by 21:00 | Radio cut not sent by Wed 22:00 |
| Wan won't fit or is too slow on a T4 | High | Medium | Spike S1 first; 480p; distilled or quantised build; HunyuanVideo 1.5 as the alternative; Ken Burns floor | Out of memory, or more than 15 min per clip |
| The TTS daily cap blocks narration | Medium | High | Per-line cache; `film plan` before spending; quotas are per model, so English can move to Flash-Lite; if the cap is tiny, voice the radio cut in one request per language and go per line once lines are stable; post-test fixes land after Thursday's 11:00 reset | A 429 with a daily quota in its body |
| Missing consent zeroes the film | Low | Critical | Consent before generation; the lint refuses to run without it | A character with `real_person: true` and no `consent_id` |
| Amharic speech or translation isn't good enough | Medium | Medium | Native check of the text before TTS and of the audio after; respell names; English is the guaranteed version | A native listener rejects a line |
| Character drifts between shots | Medium | Medium | Reference sheet, style block in every prompt, klein reference images, one main character; critic if built | Faces differ at a glance across keyframes |
| Testers late or unavailable | Medium | High | Recruit both rounds now; async on phones; bilingual testers; Slack colleagues as extra voices | No replies to the radio cut by Thu 09:00 |
| Scope creep from agent and ceiling ideas | High | High | Ceiling is the bilingual comparison we're building anyway; Coulds wait for the rough cut | Rough cut not done by Thu 09:00 |
| GPU friction: wrong GPU, session limits, about 18 GB of weights per Kaggle session, Colab without a GPU | Medium | Medium | GPU T4 x2 chosen explicitly; download time measured in S1; Kaggle primary, Colab second lane; outputs saved as they finish | S1 timings; Colab refuses a GPU |
| Private family details leak into the public repo or a training set | Low | High | private/ gitignored; prompts use roles and first names; history scanned before the repo goes public | gitleaks or a manual review flags it |
| Model names or endpoints change mid-build | Medium | Low | Adapters and config; smoke test; FAILURES.md entry | Smoke test fails |
| Daily image allowance runs out | Medium | Medium | References and keyframes this evening, before the overnight Wan batch; exploration capped; schnell fallback | Ledger shows under 20% left |
| The agent layer eats the schedule | High | High | A1–A3 are small Musts; the showrunner and MCP are Shoulds; every agent decision can still be made by hand with `film approve` and a pin | A3 not done by Thu 11:30 |
| The critic is unreliable (order bias, misses identity drift) | Medium | Medium | Fixed rubric, shuffled order, E19; keyframe pins stay at `propose` unless E13 reaches 8 of 10 | Agreement under 6 of 10 |
| Agents spend the daily image or text allowance | Medium | High | Producer budgets and a reserve for re-renders after the tests; agent calls cached by input hash | Ledger under 30% before noon |

## 19. Open decisions

| Decision | Options | Recommendation | Status |
|---|---|---|---|
| Story, subject and consent | Y's call | One person, one place, three to five beats, consent recorded first | Needed now |
| Narration languages | English only; both, English first; Amharic main with English second | Both from one storyboard, English first, the tests pick the main (ADR-015) | Decided 2026-11-25 |
| Agent autonomy | Plan and judge; fully autonomous; pipeline first | Agents explore, judge and pin; autonomy per decision type, moved by measurement (ADR-017, ADR-019). Supersedes the lean choice in ADR-002 | Decided 2026-11-25, 22:00 |
| Who orchestrates | An LLM supervisor; a coding agent over MCP; code | A showrunner in code with gates; MCP as an interface over it (ADR-019) | Decided 2026-11-25, 22:00 |
| Compute | — | Kaggle T4 x2 for video, Colab for music and overflow; no local GPU, no frontier key (ADR-006) | Decided 2026-11-25 |
| Aspect strategy | Square master; vertical master with blurred fill | Vertical by default, square tested in S1 (ADR-011) | When S1 returns |
| Keyframe size against the image allowance | 1080×1920 (room to crop 16:9, about 200–310 neurons each, so 30–50 a day); 720×1280 (native vertical, about 90–155 neurons); explore small, then render the pin at full size (one extra call per shot, so the pin is no longer free) | Measure real neurons per keyframe in the smoke test and the first keyframes on the Cloudflare dashboard, then let the producer budget in neurons (A3) | Open; decide before U5 |
| Ceiling direction | Bilingual comparison; agent-ready studio; consistency measurement; a tool for the family | Bilingual comparison and the agent layer, both measured | Decided 2026-11-25, 22:00 |
| Deadline | — | Hard: Thu 23:59 EAT, submit by 22:00 | Decided; target moved 2026-11-25 |
