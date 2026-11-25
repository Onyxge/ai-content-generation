# CLAUDE.md — The Heritage Short

Context for Claude Code. The full reasoning lives in `docs/00-requirements.md`, `docs/01-plan.md` and `docs/decisions.md`; read them before starting a unit. This file is the short version, and nothing here may be violated.

## What we're building

A pipeline that renders a 60–90 s heritage film from one contract file, `storyboard.json`, for the 10 Academy B2W0 challenge: narration in English and, if it passes a native-speaker check, Amharic; English subtitles; an original score; an AI end card; exports in 9:16 and 16:9 for each language. Graders read code, text and logs, never the media. Deadline: Thu 26 Nov 2026, 23:59 EAT; we submit by 21:00. Y's laptop has no GPU, so GPU work runs on Kaggle (GPU T4 x2) and Colab.

A team of agents makes the film's decisions (ADR-017 to ADR-019). The story, look-dev, cinematographer, critic and composer agents draft the story and explore, judge and pin the pictures. A showrunner written in code runs them phase by phase, and Y approves at gates. This studio is also the reference TRP2 trainees will learn agent orchestration from, so keep it legible.

## Non-negotiables

1. `storyboard.json` is the only contract between stages. Each stage reads it, plus upstream artifacts on disk, and writes to `outputs/<stage>/`.
2. Validate (schema, lint, consent gate) before every run, and fail before any model call.
3. Cache every generative unit by the sha256 of canonical JSON: stage, stage_version, provider, model, params, seed, resolved prompt, upstream artifact hashes. No key may depend on whole-film values (total runtime, measured narration lengths).
4. Language is a dimension, not a fork. Narration, timelines, subtitles and assembly run per language; pictures and music are shared. An edit in one language must never invalidate the other.
5. Write one line to `runs.jsonl` per model-call attempt, failures and retries included, and remote GPU jobs with their GPU seconds. Each line names its `actor`: `pipeline`, or the agent that asked. Cache hits never go there; they go to `stages.jsonl`.
6. Agents never write an artifact and never run inside `make film`. They may call generation models only through `film explore`, within the producer's budget, and a candidate reaches the film only through a pin in `storyboard.json` (ADR-017).
7. No secrets in git. Keys live in `.env` (gitignored) and `.env.example` lists the names only. Nothing under `private/` is committed or sent to a model endpoint.
8. Before any run that spends quota or GPU time, print `film plan` and wait for Y's go-ahead.
9. Never generate references, keyframes or narration for a character with `real_person: true` unless its `consent_id` exists in ETHICS.md. The lint enforces this.
10. GPU work goes `film bundle` → `gpu/runner.py` on Kaggle or Colab → `film ingest`. Until a clip is ingested, assembly uses the Ken Burns fallback, so `make film` always produces a complete film.
11. Agents change `storyboard.json` only through proposals. A proposal is a JSON Patch inside the paths the agent owns (`config/agents.toml`), checked by the schema, the lint, the consent gate and `film plan`, and recorded in `decisions.jsonl`. Only Y changes `real_person`, `consent_id`, `voices`, `meta.languages`, `meta.primary` and `meta.runtime_s` (ADR-018).
12. The showrunner and the producer are code, not LLM calls. Autonomy changes only in config, and keyframe pins leave `propose` only after E13 shows the critic agreeing with Y's blind picks on 8 of 10 shots (ADR-019).

## Provider gotchas we already know

- Gemini 3.8 TTS reads its text verbatim. Only spoken words go in the text; voice and style go in their own request fields. It returns WAV with a header by default, so don't wrap it again.
- TTS quotas are per project and per model, small, and reset at 11:00 EAT (midnight Pacific). Treat every call as precious, and when a 429 arrives, log the cap from its body. If the cap is tight, English can move to `gemini-3.8-flash-lite-tts` so Flash's quota goes to Amharic retakes.
- Cloudflare FLUX.2 klein needs multipart form data even for text-only calls, takes at most four reference images, each under 512×512, has steps fixed at 4, and accepts `seed`.
- Kaggle: choose GPU T4 x2, never the P100, which current PyTorch can't use (the CLI defaults to it unless told otherwise). Run the runner as a saved version ("Save & Run All") so it keeps going after the browser closes. Secrets set in the Kaggle UI are stripped on CLI pushes, and the runner needs none.
- Colab: free GPUs aren't guaranteed and idle sessions time out, so the runner saves every output to Drive the moment it's done.

## How we work

Y designs and reviews; you write the code, one unit at a time from `docs/01-plan.md` §14, smallest working slice first, Musts before Coulds. `make test` must stay green: it includes a full mock build and the one-edit-one-call checks. Any change to assembly also gets a look at a rendered frame, because tests can't see pixels (FAILURES.md F1). After each unit, run `make test`, then append an entry to `docs/build-log.md` covering what changed, what we learned and what's next. If you made a design choice, add or update an ADR in `docs/decisions.md`; supersede old entries, never delete them. Write to `FAILURES.md` when something breaks, at the moment it breaks, with the log line. Record experiments in `EXPERIMENTS.md` as hypothesis, one change, result, citing `run_id`s. Every dated entry states the day and the date; check both against the system clock.

## Commands (target interface)

`make setup` · `make check` · `make test` · `make smoke` · `make validate` · `make plan` · `make storyboard` · `make radio` · `make bundle` · `make ingest` · `make film` · `make costs` · `make status` · `make next`

Each wraps `uv run film <subcommand>`, so everything also works without make. Built so far: `validate`, `plan`, `render`, `assemble`, `radio`, `build` and `make mock`. Still to build: `smoke`, `storyboard`, `bundle`, `ingest`, `costs`. Agent commands, also still to build (A1–A5): `status`, `next`, `explore`, `critique`, `proposals`, `approve`, `reject`, `revert`, `pick --blind`, `mcp`.
