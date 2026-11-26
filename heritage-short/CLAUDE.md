# CLAUDE.md — The Heritage Short

Context for Claude Code. The full reasoning lives in `docs/00-requirements.md`, `docs/01-plan.md` and `docs/decisions.md`; read them before starting a unit. This file is the short version, and nothing here may be violated.

## What we're building

A pipeline that renders a 60–90 s heritage film from one contract file, `storyboard.json`, for the 10 Academy B2W0 challenge: narration in English and, if it passes a native-speaker check, Amharic; English subtitles; an original score; an AI end card; exports in 9:16 and 16:9 for each language. Graders read code, text and logs, never the media. Deadline: Thu 26 Nov 2026, 23:59 EAT; we submit by 22:00. Y's laptop has no GPU, so GPU work runs on Kaggle (GPU T4 x2) and Colab.

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

- Gemini's docs moved to aistudio.google.com/docs (old ai.google.dev links redirect). `generate_content` is now called legacy but fully supported; we use it. Checked 2026-11-25.
- Model ids: `gemini-3.8-flash` (text and vision), `gemini-3.5-flash-lite` (there is no 3.8 Flash-Lite text model), `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts`. The TTS models need the `v1beta` API version. Sampling settings such as temperature are silently ignored on 3.6 and newer.
- Gemini 3.8 TTS reads its text verbatim. Only spoken words go in the text. The style goes on the part as `speech_metadata.style`, and the voice as `speech_config.voice_config.voice`. Never set `language_code`: Amharic isn't an allowed value, and the model detects the language. A one-shot call returns a complete WAV (24 kHz, mono, 16-bit), so don't wrap it again; `write_wav` wraps only headerless PCM.
- Structured output: `response_json_schema`. Gemini silently drops `pattern`, `minLength`, `maxLength`, `uniqueItems` and similar, so every answer is validated with jsonschema before use. The SDK's own retries are switched off, so that the engine retries and logs every attempt.
- TTS quotas are per project and per model, small, and reset at 11:00 EAT (midnight Pacific). Treat every call as precious, and when a 429 arrives, log the cap from its body. If the cap is tight, English can move to `gemini-3.8-flash-lite-tts` so Flash's quota goes to Amharic retakes.
- Cloudflare FLUX.2 klein (`@cf/black-forest-labs/flux-2-klein-4b`) needs multipart form data even for text-only calls. It takes width and height from 256 to 1920, a `seed`, and at most four reference images (`input_image_0..3`), each under 512×512; steps are fixed at 4. FLUX.1 schnell takes JSON with only `prompt` and `steps`: no seed and no size, so it can't reproduce an image exactly.
- Cloudflare's free allowance is 10,000 neurons a day, reset at 00:00 UTC (03:00 EAT). klein costs about 26 neurons per 512×512 output tile, so a 1024×1024 image is about 104 neurons and a 1080×1920 keyframe about 200–310, which allows only 30–50 keyframes a day. Error 3036 means the daily allowance is used up; 3040 (out of capacity) is retried.
- Homebrew's slim `ffmpeg` has no libass, so it has no `subtitles` filter: install `ffmpeg-full` (FAILURES.md F2). It is keg-only, so it isn't on PATH; `media._exe` finds it in Homebrew's keg directory, or in `FFMPEG_BIN`.
- Addis AI (Addis Voices 2, for Amharic): `POST https://api.addisassistant.com/api/v1/voice/generations` with the header `x-api-key`. The answer's `data.audio_url` is a signed URL, fetched without the key. Send `client_request_id`, the same on every retry, so a retried line isn't billed twice. A 402 means the ETB credit ran out (treated as a quota); 429 and 409 are retried. It doesn't speak English. A voice whose `model` is `addis-voices-2` is routed to it (`SpeechRouter`). Its Terms let it train on inputs, so it gets narration lines only.
- Kaggle: choose GPU T4 x2. The P100 has been retired, and current PyTorch can't use it anyway. The image is Python 3.13 with torch 2.11 (cu130), transformers 5.x and diffusers 0.42 (checked 2026-11-26). A T4 emulates bf16 at about 11x the cost, so use fp16 there. Run the runner as a saved version ("Save & Run All") so it keeps going after the browser closes. Secrets set in the Kaggle UI are stripped on CLI pushes, and the runner needs none.
- Wan 2.2 on a T4: use diffusers `WanImageToVideoPipeline`, fp16 transformer, fp32 VAE, model CPU offload, tiled decode (`gpu/runner_wan.py`). The official repo needs FlashAttention 2 and rejects 480p. Weights are about 34 GB, so set `HF_HOME` to `/tmp`, not `/kaggle/working` (20 GB, saved).
- ACE-Step 1.5: not the PyPI `ace-step` package, which is v1. It needs Python <3.13, so it runs in its own `uv sync --python 3.12` environment as a subprocess, DiT only, and picks fp16 itself on pre-Ampere GPUs (`gpu/runner_acestep.py`).
- Colab: free GPUs aren't guaranteed and idle sessions time out, so the runner saves every output to Drive the moment it's done.

## How we work

Y designs and reviews; you write the code, one unit at a time from `docs/01-plan.md` §14, smallest working slice first, Musts before Coulds. `make test` must stay green: it includes a full mock build and the one-edit-one-call checks. Any change to assembly also gets a look at a rendered frame, because tests can't see pixels (FAILURES.md F1). After each unit, run `make test`, then append an entry to `docs/build-log.md` covering what changed, what we learned and what's next. If you made a design choice, add or update an ADR in `docs/decisions.md`; supersede old entries, never delete them. Write to `FAILURES.md` when something breaks, at the moment it breaks, with the log line. Record experiments in `EXPERIMENTS.md` as hypothesis, one change, result, citing `run_id`s. Every dated entry states the day and the date; check both against the system clock.

## Commands (target interface)

`make setup` · `make check` · `make test` · `make smoke` · `make validate` · `make plan` · `make storyboard` · `make radio` · `make bundle` · `make ingest` · `make film` · `make costs` · `make status` · `make next`

Each wraps `uv run film <subcommand>`, so everything also works without make. Built so far: `validate`, `plan`, `render`, `assemble`, `radio`, `build`, `smoke`, `make mock`, the decision commands from A1 (`propose`, `proposals`, `approve`, `reject`, `revert`), and A2's `storyboard` (with `--approve-beats` for G1 and `--adopt` for G2). Built since: `bundle`, `ingest`, and `kaggle push|status|pull` (U11; KAGGLE_API_TOKEN in .env). Still to build: the runner's Wan and ACE-Step backends, `costs`, and the agent commands `status`, `next`, `explore`, `critique`, `pick --blind`, `mcp`.
