# Decisions (ADR log)

One entry per design decision. Status is Proposed until Y accepts it, Accepted after, and Superseded when a later ADR replaces it. Entries are never deleted; the history is evidence for the report and the interview. The In code column says where a decision already lives in the code. Dates are EAT.

| ADR | Decision | Status | In code |
|---|---|---|---|
| 001 | storyboard.json is the only contract; the hand-written schema also constrains the director agent | Accepted (contract); schema reuse checked in U4 | `schema/`, `pipeline/contract.py` |
| 002 | Agents plan and judge; the pipeline executes | Accepted 2026-11-25 (lean) | director in U4, critic in U10 |
| 003 | Authoring sits outside `make film` | Proposed | `make film` starts from storyboard.json |
| 004 | Per-unit content-hash cache; outputs committed; no key depends on whole-film values | Proposed | `pipeline/engine/` |
| 005 | Ken Burns first; Wan is a per-shot upgrade | Proposed | `pipeline/shots.py`, assembly fallback |
| 006 | One GPU runner for Kaggle and Colab; manual launch and ingest first, CLI push later | Proposed (revised 2026-11-25), confirm after spike S1 | U3 |
| 007 | Two logs: runs.jsonl for model calls, stages.jsonl for stages | Proposed | `pipeline/engine/logs.py`, runner |
| 008 | Quota-aware execution: plan before spending | Proposed | `film plan`; the daily ledger comes with U3 |
| 009 | Seeds: explore, pick, pin | Proposed | pinned seeds; `--explore` comes with U5 |
| 010 | Narration-first timing; music cues anchored to shots | Proposed | `pipeline/assemble.py` |
| 011 | Aspect strategy | Open, decide when spike S1 returns | the default (vertical master, blurred fill) |
| 012 | Toolchain and roles | Proposed; amended 2026-11-25 | `pyproject.toml`, `Makefile` |
| 013 | Privacy boundary for family material | Proposed | `.gitignore`, `docs/story/brief.template.md` |
| 014 | Consent gate enforced in code | Proposed | lint reads ETHICS.md's consent table |
| 015 | Bilingual narration from one storyboard | Accepted 2026-11-25 | per-language narration, timelines, subtitles, exports |
| 016 | What is committed, what is rebuilt, where mocks live | Accepted 2026-11-25 | `.gitignore`, `build/mock/` |

## ADR-001 — storyboard.json is the only contract

Status: Accepted 2026-11-25 for the contract, which the brief requires. Proposed for reusing the schema as the agent's output constraint.

Context. Every stage must read one file, and the brief asks for a JSON Schema validated before each run. JSON Schema alone can't check cross-field rules such as total runtime or whether references resolve.

Decision. Hand-write `schema/storyboard.schema.json` (draft 2020-12) as the single definition of the contract, add a Python lint step for cross-field rules, and pass the same schema to Gemini's structured output when the director drafts a storyboard. Spoken narration and voice style are separate fields, because Gemini 3.8 TTS reads its input verbatim.

Consequences. Humans, code and agents share one definition, and an invalid draft can't reach the pipeline. The schema must stay within what Gemini accepts, or we generate a reduced copy for the agent (checked in U1). Schema changes bump the storyboard `version`.

Alternatives. Pydantic models with an exported schema give better typing in code, but the schema becomes a by-product when the brief treats it as the artifact. No schema at all is graded down, so no.

## ADR-002 — Agents plan and judge; the pipeline executes

Status: Accepted 2026-11-25. Y chose the lean version: the director now, the critic only if the rough cut is finished early.

Context. Y wants an agent that makes the movie, built from modular parts. Two agents are in play: Claude Code writes the pipeline's code, and the movie agent runs inside the pipeline. This ADR is about the movie agent. The rubric rewards determinism: a validated contract, regenerating only what changed, a rebuild from a clean clone, and a demo where one edit causes one new model call.

Options. Take one problem: in shot 7, the character's face no longer matches the reference. Plan and judge: the critic flags shot 7 and proposes two new seeds, Y picks one, the pick is written into storyboard.json, and `make film` regenerates only shot 7, with one new logged call. Fully autonomous: the agent regenerates shot 7, perhaps rewrites prompts or redoes neighbouring shots, and loops until its own judge is satisfied; impressive, but a rerun gives a different film unless every choice is written back, and each loop spends the daily image and speech allowances. Pipeline first, agent later: Y spots shot 7 in the rough cut and changes the seed by hand; as repeatable as plan and judge, but all drafting and judging is Y's until the agent is added. The autonomous loop is plan and judge with approval pressed automatically, so the plan-and-judge design can grow into it one decision at a time.

Decision. Agents never call generation models. The director proposes storyboard drafts and the critic writes verdicts; both pass through validation and Y's approval; the pipeline renders whatever the contract says. Every agent decision ends up in storyboard.json as data (a prompt, a seed, a selected option), so the film rebuilds identically without the agent. Under the deadline we build the lean version: the director now, since the brief's script stage needs a Gemini call anyway, and the critic only if the rough cut is finished early.

Consequences. The agent layer stays thin and swappable: Gemini today, any MCP-capable coding agent later. Autonomy can be granted per decision through config, such as automatic keyframe retries within a budget of three, while the storyboard stays under Y's approval.

Alternatives. The fully autonomous loop: unrepeatable, hard to cost, quota-hungry, and too much to build before Thursday. Pipeline first is a close second; with the director doubling as the script stage, the difference is about an hour of work.

## ADR-003 — Authoring sits outside `make film`

Status: Proposed 2026-11-25.

Context. The script stage drafts the storyboard. If `make film` re-ran it, each build would overwrite our edits and the film would change between runs.

Decision. `make storyboard` runs the director, lints the draft and shows a diff; we commit what we approve. `make film` always starts from the committed storyboard.json.

Consequences. `pipeline/script.py` exists and is logged and cached like any stage, but it sits upstream of the reproducible build.

Alternatives. Caching the script stage by brief hash inside `make film`: any edit to the brief would still overwrite hand edits.

## ADR-004 — Per-unit content-hash cache; outputs committed

Status: Proposed 2026-11-25.

Context. Re-runs must regenerate only what changed, a stranger must be able to rebuild from a clean clone, and the walkthrough must show one shot regenerating.

Decision. Every unit (a reference option, a keyframe, a clip, a narration line, a music candidate) is keyed by the sha256 of canonical JSON: stage, stage version, provider, model, parameters, seed, resolved prompt, and the hashes of the upstream files it uses. Each artifact sits beside a sidecar JSON with its key, run id and its own hash. No key may depend on whole-film values such as total runtime or measured narration lengths; music length and clip frame counts come from the storyboard, and fitting happens in assembly. Current artifacts are committed.

Consequences. A clean clone rebuilds with no keys or GPU because everything hits the cache, and CI proves it on every push. The repo carries an estimated 100–200 MB of media, so audio is stored as FLAC and clips at sensible bitrates. Keys must be identical on every operating system (sorted keys, relative POSIX paths), which CI also tests.

Alternatives. File timestamps are fragile. Git LFS hits whoever clones with bandwidth limits. Leaving outputs out of git means a clean clone needs keys and a GPU.

## ADR-005 — Ken Burns first; Wan is a per-shot upgrade

Status: Proposed 2026-11-25.

Context. The official Wan 2.2 TI2V-5B run at 720p needs at least 24 GB of VRAM; Kaggle's T4s have about 15 GB usable; the reported free-T4 route is a distilled build at 480p, about 8 minutes per 5-second clip. The brief accepts a narrated, scored, subtitled sequence of stills as a film.

Decision. Build the Ken Burns renderer (FFmpeg zoompan, both orientations) first, so a complete film always exists. Each shot declares `motion.mode: i2v` with `fallback: kenburns`; assembly uses the best cached artifact and logs which one it used.

Consequences. GPU trouble lowers quality but never blocks delivery.

Alternatives. Wan first, which would let the riskiest stage block everything.

## ADR-006 — One GPU runner for Kaggle and Colab

Status: Proposed 2026-11-25 and revised the same day, after Y confirmed the compute: Kaggle T4s and Colab, no local GPU, no frontier key. Confirm after spike S1.

Context. Moving shots and music need a GPU, and Y's laptop has none. Kaggle's CLI can push and run a kernel; Colab has no comparable CLI, its free GPUs aren't guaranteed, and idle sessions time out. The clean-clone rebuild needs no GPU at all, because a fresh clone hits the cache.

Decision. One environment-agnostic runner script takes a job bundle (a manifest plus input images) and writes each output as soon as it finishes, with timings measured on the GPU. `film bundle <stage>` packs the uncached jobs. We run the bundle by hand on Kaggle (GPU T4 x2, one process per GPU, never the P100, as a saved version so it keeps running after the browser closes) or on Colab (saving to Drive as it goes). `film ingest <zip>` brings the results into the cache and writes one runs.jsonl line per job with its GPU seconds. Kaggle takes the Wan batch; Colab takes the ACE-Step candidates and any overflow. Until a clip comes back, assembly uses the Ken Burns fallback. Pushing bundles with `kaggle kernels push` is a stretch goal (U11).

Consequences. Every GPU minute is still measured and logged, an interrupted session loses only unfinished jobs, and two GPU providers can work in parallel. The price is a manual step, which the README documents. Weight downloads (about 18 GB per Kaggle session) may dominate short jobs; S1 measures this.

Alternatives. CLI push only: Kaggle-only, and more to build before we know Wan works at all. Notebooks with pasted inputs: no cache and no logs.

## ADR-007 — runs.jsonl for model calls, stages.jsonl for stages

Status: Proposed 2026-11-25.

Context. The brief wants one line per model call with model, parameters, seed, latency and cost, and accepts logs that show a single new call as walkthrough evidence.

Decision. runs.jsonl is append-only, with one line per model-call attempt, including failures, retries and remote jobs (with GPU seconds). stages.jsonl holds one line per stage per run: cache hits and misses, wall time, and measurements such as durations, loudness, true peak and ducking depth.

Consequences. After the live demo, the tail of runs.jsonl shows exactly the new calls. COSTS.md is generated from both files.

Alternatives. One mixed log, where stage lines would bury the demo's single call.

## ADR-008 — Quota-aware execution

Status: Proposed 2026-11-25.

Context. Free tiers bind before money does: TTS caps reported between 10 and 100 requests a day, resetting at 11:00 EAT; Cloudflare's daily image allowance; about 30 Kaggle GPU hours a week.

Decision. `film plan` runs before anything spends: misses per stage, projected calls, GPU minutes, and what's left of each daily allowance, from a ledger computed out of runs.jsonl and each provider's reset time. A run that would exceed a cap stops unless explicitly allowed. A daily-quota error defers the remaining units, exits in a resumable state, and logs the cap from the error body.

Consequences. Spending is deliberate and visible, and COSTS.md gets its free-tier section from the ledger.

## ADR-009 — Seeds: explore, pick, pin

Status: Proposed 2026-11-25.

Context. Diffusion output depends on the seed; consistency comes from choosing good candidates; reproducibility needs fixed seeds.

Decision. `--explore N` renders N seeds for a unit into a gitignored archive, with every call logged. Y, helped by the critic, picks one, and the pick is written into storyboard.json. Normal runs use pinned seeds only.

Consequences. Exploration is visible in runs.jsonl and EXPERIMENTS.md while the contract stays deterministic.

## ADR-010 — Narration-first timing; music cues anchored to shots

Status: Proposed 2026-11-25.

Context. Professionals cut picture to the voice; narration length depends on language and voice; editing one line mustn't regenerate music or video.

Decision. The storyboard holds target durations. The narration stage measures the real ones into a derived `outputs/timeline.json`, and assembly fits picture to voice by trimming, holding, or extending a slow Ken Burns tail. Music cues reference shot ids rather than seconds, are generated at a fixed length longer than the film, and are trimmed and faded in assembly.

Consequences. A narration edit costs one TTS call plus assembly.

## ADR-011 — Aspect strategy

Status: Open; decide when spike S1 returns (E9).

Context. One generation must feed 9:16, which is the main submission, and 16:9, and we can't afford two Wan runs per shot. Wan's image-to-video output takes the input image's aspect ratio.

Options. A square master centre-cropped both ways lets one clip serve both, but demands strictly centred composition and an upscale of about 1.33× at 720p (2× at 480p). A vertical master gives native quality where it matters, with the horizontal version as a blurred-fill pillarbox. Separate generations per orientation double the GPU bill and are rejected.

Current default. The vertical master. Ken Burns shots are rendered natively in both orientations either way.

## ADR-012 — Toolchain and roles

Status: Proposed 2026-11-25.

Decision. Python 3.12 with uv and a lockfile; a `film` CLI wrapped by a Makefile and runnable as `uv run film …` where make isn't available; FFmpeg as a system dependency checked at startup; pytest; gitleaks; GitHub Actions. Planning happens in claude.ai. Claude Code writes and runs the code on Y's machine from CLAUDE.md, under Y's direction and review.

Why. claude.ai's sandbox can't reach Gemini, Cloudflare or Kaggle, and Y already works this way. Y's laptop has no GPU, so GPU work runs on Kaggle and Colab (ADR-006).

Notes. This is the brief's "let the agent write the stage scripts" practice, which we evaluate honestly in the report. The brief names free agents and describes Claude Code as paid without ruling it out; the README and ETHICS.md will name the coding agent we used.

Amended 2026-11-25. Claude in claude.ai built and tested the story-agnostic core offline on mock providers, because none of it needs keys and the sandbox has FFmpeg: U0, U1, U2, and most of U8 (assembly and the radio cut), built early. Claude Code takes over on Y's laptop from U3, where live keys and the GPU providers are needed.

## ADR-013 — Privacy boundary for family material

Status: Proposed 2026-11-25.

Context. The repo will be public, and several free endpoints may use what we send them.

Decision. Full family notes and consent evidence live in `private/`, which is gitignored and never sent to a model. `docs/story/brief.md` holds only what we'd publish. Prompts use roles and first names, and no family photo is uploaded unless the person agrees to that use. The repo's history is scanned before it goes public, and ETHICS.md lists what was sent to which endpoint.

## ADR-014 — Consent gate enforced in code

Status: Proposed 2026-11-25.

Context. A real person shown or voiced without recorded consent zeroes the film.

Decision. Characters carry `real_person` and `consent_id`. The lint refuses to run references, keyframes or narration involving a real person unless that consent id exists in ETHICS.md's consent table.

Consequences. The gate can't be forgotten, and graders can see it in the code.

## ADR-015 — Bilingual narration from one storyboard

Status: Accepted 2026-11-25. Y chose both languages from one storyboard, English first.

Context. Y: Amharic would be nice, but English has to be available. The brief asks for narration in a language of our choice plus English subtitles, and its ceiling list includes testing more languages. Speech quota is counted per project and per model, and Amharic is where text-to-speech is most likely to stumble.

Decision. Language is a dimension of the pipeline, not a fork of it. The storyboard holds narration and a voice per language (`narration.en`, `narration.am`); pictures and music are shared; narration, timeline, subtitles and assembly run per language. English is built first as the guaranteed version. The English script is the single source of meaning: it is the English narration and also the English subtitle track of the Amharic film, and a shot can override it with `subtitle_en`. The director drafts the Amharic text, and a native speaker checks it before any Amharic speech is generated. Both versions go to testers; their response, plus a native-speaker check of the Amharic audio, decides which becomes the main submission, and the other is linked from the post and the report. If the daily speech cap is tight, English moves to Flash-Lite TTS so Flash's quota goes to Amharic retakes.

Consequences. Four exports instead of two (language × orientation), all from the same cache. A narration edit in one language never touches the other. Runtime and timing are checked per language, because the same meaning won't take the same time in both. The comparison becomes our ceiling work at almost no extra build cost (E15, E16).

Alternatives. English only: safest, but drops the version Y wants and our cheapest ceiling. Amharic narration with English subtitles only: meets the brief, but leaves no English-narrated film if the Amharic speech disappoints.

## ADR-016 — What is committed, what is rebuilt, where mocks live

Status: Accepted 2026-11-25, decided while building U2.

Context. ADR-004 commits generated assets so a clean clone can rebuild the film without keys. Not every artifact is worth committing, and mock runs must never mix with real ones: the real runs.jsonl should start with our first real model call, after DESIGN.md is written.

Decision. Model outputs (references, keyframes, narration, score candidates, Wan clips) are committed with their sidecars, because remaking them costs quota. Local renders are gitignored, and FFmpeg rebuilds them on demand: Ken Burns clips, radio cuts and final exports. Timelines and subtitle files are committed, because they're small text that graders can read. Mock runs write everything, including their own runs.jsonl and stages.jsonl, under `build/mock/`, which is gitignored.

Consequences. On a clean clone, `make film` makes zero model calls, then spends a minute or two on local renders and assembly. The final films are shared as links, not stored in git.
