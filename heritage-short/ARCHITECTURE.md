# ARCHITECTURE

How the studio is put together. The reasoning behind each choice is in `docs/decisions.md` (ADR-nnn below); this page describes what the code does.

## One contract

`storyboard.json` is the only thing the stages share (ADR-001). Before anything runs, it is validated against `schema/storyboard.schema.json` and then linted by `pipeline/contract.py` for rules a schema can't express:
- 8–12 shots, and a 60–90 s runtime for every language.
- Ids that resolve, and at most four reference images per keyframe.
- Narration present in every language or in none.
- Subtitle reading speed.
- The consent gate: a character marked `real_person` can't be generated until ETHICS.md records that person's consent (ADR-014).

Nothing runs on an invalid storyboard.

## Seven stages

| Stage | Script | Unit | Makes | Provider |
|---|---|---|---|---|
| story | `pipeline/agents/story.py` | the film | logline, beat sheet, shot list, narration and translation, each step a proposal for review; authoring only, never part of `make film` (ADR-003, ADR-018) | Gemini 3.8 Flash (A2) |
| references | `pipeline/references.py` | reference × seed | reference-sheet options to pick from | FLUX.2 klein |
| keyframes | `pipeline/keyframes.py` | shot | the still each shot starts from, conditioned on the pinned references | FLUX.2 klein |
| narration | `pipeline/narration.py` | shot × language | one WAV per spoken line | Gemini 3.8 TTS |
| music | `pipeline/music.py` | cue × seed | score candidates | ACE-Step 1.5 on the GPU runner |
| shots | `pipeline/shots.py` | shot | Ken Burns clips per orientation; a Wan clip where the shot asks for motion | FFmpeg; Wan 2.2 on the GPU runner |
| assemble | `pipeline/assemble.py` | language × orientation | the films, the radio cut, timelines and subtitles | FFmpeg |

Each stage script runs on its own: `uv run python -m pipeline.keyframes`. The `film` CLI (`pipeline/cli.py`) runs them in dependency order.

Two languages share one set of pictures and one score. Narration, timing, subtitles and assembly run per language (ADR-015). The English script is the single source of meaning. It is spoken in the English film and becomes the English subtitles of the Amharic film.

## Caching

Every generative unit has a cache key (`pipeline/engine/cache.py`). The key is the sha256 of canonical JSON holding:
- the stage and its version;
- the provider and model;
- the unit's resolved spec: the prompt with its style block and character descriptions, the seed, the size and so on;
- the file hashes of the upstream artifacts the unit uses.

The key and the artifact's own hash sit in a sidecar next to the artifact (`s04.png.json`). A unit is skipped when its sidecar key matches and the file still hashes the same. Each artifact is written to a temporary name and renamed only once it's complete, so a crash never leaves a file that looks cached.

A change cascades only along real dependencies. A new keyframe prompt regenerates that keyframe and that shot's clips, and nothing else. No key depends on whole-film values: clip lengths and the score's length come from the storyboard, never from the measured narration. That's why editing one narration line costs one speech call and never regenerates music or video. Fitting picture to voice happens in assembly, which is cheap and always reruns (ADR-004, ADR-010).

`film plan` evaluates every unit without building anything. It prints what would be generated and how many model calls that costs. It's the dry run before anything that spends quota (ADR-008). The test suite checks it end to end: after one keyframe edit, the plan names exactly that keyframe and its three clips, and rendering logs exactly two model calls.

## Assembly

For each language, assembly builds a timeline from the measured narration (`outputs/timeline/<lang>.json`). Each shot lasts at least its storyboard length, or longer if its line needs 0.4 s lead-in, the line itself and a 0.6 s tail. Lengths are rounded to whole frames, so picture and sound never drift.

Each shot uses its Wan clip if one is cached; otherwise it uses its Ken Burns clip. A vertical Wan clip in the horizontal film sits on a blurred fill (ADR-011).

The narration is placed on the timeline. The score is ducked under it with sidechain compression, starting from the brief's values (threshold 0.02, ratio 6, attack 300 ms, release 1500 ms). The mix is then loudness-normalised to −14 LUFS with a −1 dBTP ceiling.

English subtitles are cut into cards of at most two lines. Vertical frames get 28 characters per line and horizontal frames 42, which keeps vertical text inside the safe area. Cards break preferably after commas, and no word is left alone on a card. Subtitles are burned in with the bundled DejaVu font, so every machine renders the same text.

A 2–3 s end card states the film was made with AI and names the models. Every export's runtime, integrated loudness and true peak are measured and logged.

`film radio` builds the user-test prototype: narration over a synthetic drone on black, with the same subtitles.

## Logs

`runs.jsonl` gets one line per model-call attempt, failures and retries included (ADR-007). Each line records:
- stage, unit, attempt and actor (`pipeline`, or the agent that asked for the call);
- provider, model, parameters and seed;
- prompt hash and cache key;
- status and latency;
- GPU seconds and cost;
- output hash and error.

Cache hits and local FFmpeg renders never write there. `stages.jsonl` gets one line per stage per run (hits, misses, wall time) and the assembly measurements.

`decisions.jsonl` gets one line per proposal, approval, rejection, automatic application or revert (ADR-018). Each line records who acted, the kind of decision, the JSON Patch, its evidence (candidates, critic verdicts, run ids, tester rows) and the storyboard hash before and after.

## Failure handling

Provider adapters raise one of five errors (`pipeline/engine/retry.py`):
- **Transient** (per-minute limits, 5xx, timeouts): retried with exponential backoff and jitter, honouring Retry-After, up to four attempts, each logged.
- **Daily quota**: stops calls to that provider for the rest of the run and leaves its units deferred. The run exits with code 75 and can be resumed after the provider's reset.
- **Bad request** and **safety block**: the unit fails and the run carries on with the others.
- **Remote GPU work**: reported as pending, and assembly uses the Ken Burns clip until the Wan clip is ingested (ADR-005, ADR-006).

## Workspaces

Real runs write to `outputs/`, `runs.jsonl` and `stages.jsonl`. Model outputs are committed with their sidecars. Local renders and final exports are rebuilt by FFmpeg and not committed. `--mock` runs every stage on placeholder providers under `build/mock/`, which is never committed (ADR-016). Candidates from `film explore` go to `outputs/_archive/`, which is gitignored. Each one is stored under the cache key a real render of that seed would have, so pinning it moves it into `outputs/` without a model call (ADR-017).

## Agents

The pipeline renders; agents decide (ADR-017 to ADR-019). `make film` never runs an agent. It renders whatever storyboard.json says, so the film rebuilds without them. This layer is being built in units A1–A5 (`docs/01-plan.md` §14).

- **What agents may do.** Read the contract, the artifacts and the measurements. Render candidates with `film explore`, within the producer's budget. Ask the critic to rank them. Propose patches. A pin (a seed or a `selected` value) is the only way a candidate reaches the film, and because candidates are archived under the real cache key, a pin is a cache promotion, not a new call.
- **Who may change what.** Each agent owns a set of storyboard paths in `config/agents.toml`. `film propose` refuses a patch outside those paths, or one that fails the schema, the lint or the consent gate. Only Y can change consent, voices, languages or the main version.
- **Who decides.** Autonomy is set per decision type: `propose` waits for Y, `veto` applies and can be reverted, `auto` applies. Story, narration, the golden reference and the music pick always wait for Y. Keyframe pins move from `propose` to `veto` only if the critic agreed with Y's blind picks on 8 of the first 10 shots (E13).
- **Who runs them.** The showrunner is code, not an LLM. It's a phase machine (brief → story → look → shots and music → edit) with gates where Y approves, and it reads its state from the contract, decisions.jsonl and the files, so it resumes after any crash. The producer is the quota ledger and the budgets. The specialists are Gemini structured-output calls: story (a prompt chain from logline to translation), look-dev, cinematographer (one worker per shot), critic (vision) and composer.
- **What they leave behind.** Every decision is a line in decisions.jsonl with its evidence. The agents' own LLM calls are units like any other: cached by input hash and logged in runs.jsonl with their actor.

After the rough cut, `film mcp` exposes the same commands as MCP tools, so any coding agent can drive the studio without getting around the checks.
