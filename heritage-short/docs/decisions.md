# Decisions (ADR log)

One entry per design decision. Status is Proposed until Y accepts it, Accepted after, and Superseded when a later ADR replaces it. Entries are never deleted; the history is evidence for the report and the interview. The In code column says where a decision already lives in the code. Dates are EAT.

| ADR | Decision | Status | In code |
|---|---|---|---|
| 001 | storyboard.json is the only contract; the hand-written schema also constrains the director agent | Accepted (contract); schema reuse checked in U4 | `schema/`, `pipeline/contract.py` |
| 002 | Agents plan and judge; the pipeline executes | Superseded 2026-11-25 by ADR-017 | — |
| 003 | Authoring sits outside `make film` | Proposed; amended 2026-11-25 by ADR-018 | `make film` starts from storyboard.json |
| 004 | Per-unit content-hash cache; outputs committed; no key depends on whole-film values | Proposed | `pipeline/engine/` |
| 005 | Ken Burns first; Wan is a per-shot upgrade | Proposed | `pipeline/shots.py`, assembly fallback |
| 006 | One GPU runner for Kaggle and Colab; manual launch and ingest first, CLI push later | Proposed (revised 2026-11-25), confirm after spike S1 | U3 |
| 007 | Two logs: runs.jsonl for model calls, stages.jsonl for stages | Proposed | `pipeline/engine/logs.py`, runner |
| 008 | Quota-aware execution: plan before spending | Proposed | `film plan`; the daily ledger comes with U3 |
| 009 | Seeds: explore, pick, pin | Proposed; amended 2026-11-25 by ADR-017 | pinned seeds; `film explore` comes with A3 |
| 010 | Narration-first timing; music cues anchored to shots | Proposed | `pipeline/assemble.py` |
| 011 | Aspect strategy | Accepted 2026-11-26: vertical master; 16:9 = blurred fill for every shot | `assemble._shot_chain`, `delivery.horizontal_kenburns` |
| 012 | Toolchain and roles | Proposed; amended 2026-11-25 | `pyproject.toml`, `Makefile` |
| 013 | Privacy boundary for family material | Proposed | `.gitignore`, `docs/story/brief.template.md` |
| 014 | Consent gate enforced in code | Proposed | lint reads ETHICS.md's consent table |
| 015 | Bilingual narration from one storyboard | Accepted 2026-11-25 | per-language narration, timelines, subtitles, exports |
| 016 | What is committed, what is rebuilt, where mocks live | Accepted 2026-11-25 | `.gitignore`, `build/mock/` |
| 017 | Agents explore, judge and pin; only pinned contract values reach the film | Accepted 2026-11-25 | A3: `film explore`, archive promotion |
| 018 | Proposals, ownership and the decision log | Accepted 2026-11-25 | A1: `pipeline/agents/patches.py`, `config/agents.toml`, `decisions.jsonl` |
| 019 | A deterministic showrunner with gates, budgets and autonomy per decision type | Accepted 2026-11-25 | A2–A5: `pipeline/agents/` |

## ADR-001 — storyboard.json is the only contract

Status: Accepted 2026-11-25 for the contract, which the brief requires. Proposed for reusing the schema as the agent's output constraint.

Context. Every stage must read one file, and the brief asks for a JSON Schema validated before each run. JSON Schema alone can't check cross-field rules such as total runtime or whether references resolve.

Decision. Hand-write `schema/storyboard.schema.json` (draft 2020-12) as the single definition of the contract, add a Python lint step for cross-field rules, and pass the same schema to Gemini's structured output when the director drafts a storyboard. Spoken narration and voice style are separate fields, because Gemini 3.8 TTS reads its input verbatim.

Consequences. Humans, code and agents share one definition, and an invalid draft can't reach the pipeline. The schema must stay within what Gemini accepts, or we generate a reduced copy for the agent (checked in U1). Schema changes bump the storyboard `version`.

Alternatives. Pydantic models with an exported schema give better typing in code, but the schema becomes a by-product when the brief treats it as the artifact. No schema at all is graded down, so no.

## ADR-002 — Agents plan and judge; the pipeline executes

Status: Superseded 2026-11-25 (22:00) by ADR-017. Accepted earlier the same day in its lean version: the director now, the critic only if the rough cut is finished early. Kept below as the record of why we first chose it.

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

Amended 2026-11-25 by ADR-018. The director is now the story agent's chain, and its drafts arrive as proposals that Y approves at gates G1 and G2. Authoring still sits outside `make film`.

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

Amended 2026-11-26 (01:15), from a check of the current docs and code (build-log Entry 12):
- **Wan runs through diffusers' `WanImageToVideoPipeline`, not the official repo.** The repo's attention asserts on FlashAttention 2, which a T4 (Turing) can't run, and its size check rejects 480p.
- **Precision is fp16 with the VAE in fp32,** because a T4 emulates bf16 at about 11x the cost. Model CPU offload and tiled VAE decoding keep it in 15 GB.
- **ACE-Step 1.5 runs in its own Python 3.12 `uv` environment as a subprocess.** It needs Python <3.13 and transformers <4.58, and Kaggle's image is Python 3.13 with transformers 5.x. It runs DiT only.
- **One Kaggle session takes both bundles:** Wan on GPU 0, ACE-Step on GPU 1, because the two GPUs share 29 GB of host RAM.
- **The steps count (`i2v_steps`, `music.steps`) is now part of each GPU unit's cache key,** so if spike S1 changes it, every affected clip is regenerated and nothing stale is reused.
- **The P100 has been retired on Kaggle.** "Never the P100" no longer needs guarding in code, but the notebook still checks the GPU.

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

Amended 2026-11-25 by ADR-017. Candidates are archived under the cache key a real render of that seed would have, so a pin is a cache promotion with no new call. The picker may be the critic when the autonomy setting allows it (ADR-019).

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

Accepted 2026-11-26 (17:00). Vertical master; the 16:9 film shows every shot on a blurred fill, Ken Burns shots included. The first rough cut centre-cropped the Ken Burns shots to 16:9, which keeps only the middle third of a 9:16 keyframe: Tesfaye, the guest and the emperor lost their heads in five of six sampled frames. The Wan clips were already on blurred fill. `delivery.horizontal_kenburns = "fill"` reuses the vertical Ken Burns clip, so the horizontal Ken Burns renders aren't made at all any more. The square-master test (E9) isn't needed.

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

## ADR-017 — Agents explore, judge and pin; only pinned contract values reach the film

Status: Accepted 2026-11-25 (22:00). Supersedes ADR-002; amends ADR-009.

Context. Y's goal changed how much the agent layer matters. Y is the tutor for TRP2, and this studio is the reference for how trainees should orchestrate a movie-making agent; we also produce our own film with it. Under ADR-002 the movie agent was a one-shot director and an optional critic, so every judgement (reference picks, seeds, keyframes, music) fell on Y, and there was little agent to study. ADR-002 rested on one worry: an agent that calls generation models makes the film unrepeatable and spends quota where nobody sees it. That worry is about where an agent's output lands, not about whether the agent calls a model.

Decision. The rule becomes: `make film` is a pure function of the committed storyboard.json and the cache. Agents never run inside it and never write an artifact. Agents may call generation models only through `film explore`. It renders candidates for one unit within a budget the producer grants (ADR-019) and logs every call in runs.jsonl with `actor`. It stores each candidate in `outputs/_archive/` under the cache key a real render of that seed would compute. Choosing a candidate is a pin: a patch to storyboard.json that sets a seed or a `selected` value. On the next render the runner finds the archived artifact under the same key and promotes it, so a pin costs no model call. The agents' own LLM calls (the story chain, the critic) go through the same runner as units of their own: cached by input hash and logged. Re-running an agent on unchanged inputs therefore spends nothing.

Consequences. Everything ADR-002 protected still holds. A clean clone rebuilds with zero calls. In the walkthrough, one storyboard edit still causes one new call, because agents aren't part of the build. Agents can now do most of the work, and every choice they made is visible as a pin in the contract with its evidence in decisions.jsonl (ADR-018). Exploration spends quota, so the producer's budgets matter. The archive is gitignored: candidates that weren't picked survive only as lines in the logs.

Alternatives. Keep ADR-002: repeatable, but there's no agent to learn from. A free-running loop that regenerates until its own judge is satisfied: unrepeatable unless every choice is written back to the contract, and writing it back is this ADR.

## ADR-018 — Proposals, ownership and the decision log

Status: Accepted 2026-11-25 (22:00).

Context. Several agents now edit one file. Without limits, one agent's edit overwrites another's, and nothing records why a choice was made or by whom: runs.jsonl records calls, not decisions. The design-thinking criterion also asks for the storyboard to be "visibly changed" by what testers said, which needs a trail from a tester's words to an edit.

Decision. Agents never write storyboard.json directly. Each one produces a proposal: an RFC 6902 JSON Patch, a rationale and evidence (candidate ids, critic verdicts, run ids, tester rows in DESIGN.md). `film propose` checks a proposal before anyone sees it:
- every path must be one the agent owns in `config/agents.toml`;
- the patched storyboard must pass the schema, the lint and the consent gate;
- `film plan` prices it.

Then the autonomy setting (ADR-019) decides whether the proposal waits for Y or is applied. Every proposal, approval, rejection, automatic application and revert appends one line to `decisions.jsonl`, which is committed. The line records who acted, the kind of decision, the patch, the evidence, the verdict and the storyboard hash before and after. A storyboard version (vN) is a snapshot taken when a gate passes.

| Who | May change |
|---|---|
| story | `meta.title`, `meta.logline`; the shot list (add, remove, reorder); for each shot `beat`, `reason`, `size`, `duration_s`, `characters`, `narration`, `subtitle_en`; `end_card` |
| lookdev | `style`; `characters[*].description` and `.reference`; `references` (prompts and seed lists) |
| cinematographer | for each shot `image_prompt`, `references`, `motion` (mode, prompt, Ken Burns) |
| composer | `music.cues`, except `selected` |
| pin (an operation, subject to autonomy) | `keyframe_seed`, `motion.seed`, `references[*].selected`, `music.cues[*].selected` |
| Y only | `real_person`, `consent_id`, `voices`, `meta.languages`, `meta.primary`, `meta.runtime_s` |

Consequences. Agents can work in parallel without collisions, on different shots or different fields. Graders can read the reasoning behind each choice, and the interview can be prepared from decisions.jsonl. No agent can touch consent. The cost is a patch layer and one validation pass per proposal, which needs no model calls.

Amended 2026-11-25 (23:00) while building A1. Patches address shots, characters, references and music cues by id, not by array index: `/shots/s04/image_prompt`, with `/shots/@order` for the order. Indices shift whenever a shot is added or removed, which would make an approved proposal edit the wrong shot, and an LLM miscounts indices more easily than it copies an id. A proposal records each change as a path with its value before and after. Approval re-checks those values, so a proposal still applies after unrelated edits, and a stale one is refused with the path that changed.

Amended 2026-11-25 (23:45) while building A2. Before v1 there is no storyboard to own a part of, so the first version doesn't arrive as a proposal. The story chain drafts a complete storyboard, and code assembles it, taking languages, the main version, runtime and voices from Y's config. Y adopts it at gate G2 (`film storyboard --adopt`), which is logged as Y's decision with the draft's hash and a v1 snapshot. Adoption is refused if the draft fails the schema or the lint, which includes the consent gate. From v1 on, every change is a proposal.

Alternatives. Agents editing the file directly with git as the record: the history shows what changed but not why or on what evidence, and nothing stops an agent from editing consent. A shared chat between agents: no ownership and no structured record.

## ADR-019 — A deterministic showrunner with gates, budgets and autonomy per decision type

Status: Accepted 2026-11-25 (22:00).

Context. Something has to decide which agent works next, when to stop for Y and how much each agent may spend. An LLM supervisor would add another unrepeatable, quota-hungry judgement to the loop, and the order of film production is already known (the brief's Appendix C).

Decision. The showrunner is code, not an LLM. It's a phase machine in `pipeline/agents/showrunner.py` that keeps no state of its own: it reads the phase from the contract, decisions.jsonl and the files on disk, so a crash resumes cleanly. Phases and gates:
- P0 brief → G0: the brief and the intent are written by Y.
- P1 story → G1: the beat sheet; G2: storyboard v1 and a native check of the Amharic text; then the radio cut and user test 1 → G3: v2.
- P2 look → G4: the golden reference, always picked by Y.
- P3 shots and music → G5: the rough cut.
- P4 edit → user test 2 → G6: picture lock.

Inside a phase, agents work on their own within budget. At a gate, `film status` shows what waits for Y, and `film next` runs the current phase's agents up to the next gate.

The specialists are LLM calls with structured output: Gemini 3.8 Flash, or Flash-Lite for the per-shot workers. Each has a prompt file in `pipeline/agents/prompts/`, an output schema and its owned paths.
- **Story** is a prompt chain: logline → beat sheet → shot list → narration → translation. Each step is validated and kept in `docs/story/drafts/`.
- **Look-dev** and the **cinematographer** follow generate → judge → pin. The cinematographer runs one worker per shot over a shared bible: the style block and the character descriptions.
- **The critic** is a vision call. It ranks candidates against the golden reference with a fixed rubric: identity, style, hands and faces, stray text, and composition centred enough for both crops. Candidates are shuffled and the order is logged.

The producer is code too. It's the quota ledger from runs.jsonl plus the budgets in `config/agents.toml`:
- keyframes: 3 candidates a round and at most 3 rounds (the brief's three-attempts rule), then the shot is flagged for Y;
- references: 4 candidates;
- music: 3 candidates.

It also keeps a reserve of each daily allowance for re-renders after the user tests. The editor stays code: assembly measures, and Y tunes (E11, E12).

Autonomy is set per decision type in config:
- `propose`: the proposal waits for Y;
- `veto`: it's applied now and listed for Y to undo with `film revert`;
- `auto`: it's applied and logged.

Story structure, narration, the golden reference and the music pick stay `propose`. Keyframe pins start at `propose` and move to `veto` only if the critic agrees with Y's blind picks on at least 8 of the first 10 shots (E13). That measurement is the promotion rule.

After the rough cut, the same operations (status, plan, explore, critique, propose, approve, reject, render, assemble) are exposed as an MCP server, `film mcp`. Claude Code, OpenCode or Antigravity can then drive the studio, and the guardrails stay in the code underneath, so a different driver can't skip them.

Consequences. Orchestration is repeatable and resumable, and autonomy becomes a measured setting rather than a choice made once. The cost is about a day of building across units A1–A5 (01-plan §14), which moves the submission target from 21:00 to 22:00 on Thursday.

Alternatives. An LLM supervisor that chooses each next step: flexible, but unrepeatable, and it spends quota on routing a process whose order is fixed. Agents talking to each other in a shared chat: no ownership and no clean record. A coding agent as the only orchestrator, over MCP: no custom orchestration code, but the guardrails would live in prompts.
