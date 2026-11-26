# COSTS

Generated from `runs.jsonl` and `stages.jsonl` by `film costs` (unit U9, not built yet). It will hold:
- calls, median and p95 latency, and GPU minutes per stage;
- the free-tier limits we actually hit, read from the providers' error bodies;
- a list-price equivalent, with each price's source and date.

We have no frontier-model access (compute is Kaggle T4s and Colab), so there will be no frontier comparison; the brief asks for one only where we had access.

Measured so far, on mock providers only (this says nothing about model costs):

| Run | What ran | Wall time |
|---|---|---|
| Full-size mock build, 25 Nov | 31 placeholder "model" units, 16 Ken Burns renders at 720p, four 67 s exports | 87 s on the build sandbox; 36 s on Y's Mac |

First real calls (`make smoke`, Wed 25 Nov, 23:57 EAT; runs.jsonl):

| Provider and model | What | Latency | Notes |
|---|---|---|---|
| Gemini `gemini-3.8-flash` | 9-token structured answer | 131,011 ms on attempt 4 | Attempts 1–3 got 503 UNAVAILABLE (1.7–3.4 s each); retried and logged (FAILURES.md F3) |
| Gemini `gemini-3.8-flash-tts`, voice Kore | "Testing the narrator." | 4,207 ms | WAV with header, 24 kHz mono 16-bit, 1.71 s long. Three words in 1.7 s suggests the style text ("calm and warm") was not spoken; to confirm by ear (E1) |
| Cloudflare `flux-2-klein-4b` | 256×256 image | 9,490 ms | PNG; neurons used still to read on the Cloudflare dashboard |

Storyboard v1, first production calls (Thu 26 Nov, 00:58–01:04 EAT):

| Stage | Calls | Latency | Notes |
|---|---|---|---|
| Story agent, `gemini-3.8-flash` (5 steps) | 5 ok, 6 failed attempts (one 504 after 239 s, five 503s) | 66–152 s per answer; 13 min 54 s in all | Gemini was overloaded both times; every attempt is logged |
| Narration, English, `gemini-3.8-flash-tts` | 9 ok, 2 per-minute 429s, 1 daily cap | 3.9–5.9 s per line | Lines measured 4.1–6.8 s, 1.9–2.7 words a second; 45 s of speech for nine lines. The daily cap is about 10 calls (FAILURES.md F5) |
| Keyframes s02 and s09 (no people), `flux-2-klein-4b`, 1080×1920 | 2 ok | 10.9 and 14.1 s | For spike S1 |
| Narration s10.en after the 11:00 reset | 1 ok | 4.6 s | The English narration is complete: 10 lines |
| Wan 2.2 TI2V-5B on Kaggle T4 (s02.i2v, 480×832, 121 frames, 50 steps) | 1 ok after two failed runs | 1,737 GPU s (about 34.7 s a step); load 357 s; peak 5.75 GB | Group offload, fp16 with fp32 VAE (E7, F7–F9). About 29 GPU minutes per 5 s clip |
| ACE-Step 1.5 turbo, DiT only, Kaggle T4 (GPU 1), three 86 s takes | 3 ok (after the failures in F7–F9) | 99.7 s for the first (each job starts its own subprocess, so it includes model start-up), then 27.3 and 25.8 s; environment build `load_s` 62 s | About 26 GPU s per 86 s of music, roughly 3× real time; 48 kHz stereo WAV |
| Wan 2.2 on Kaggle T4, s06/s08/s10 (same settings) | 3 ok | 2,060, 2,065 and 2,067 GPU s (about 34 min each; one session 16:48–18:51 including the queue) | 1 kept (s06); s08 and s10 rejected on review (EXPERIMENTS, Wan on people). The four Wan clips cost 8,930 GPU s, about 2.5 GPU hours, for two usable shots |
| References, `flux-2-klein-4b`, 1024×1024 | 12 ok | 9.4–33.4 s each, median about 13 s | About 1,250 neurons by the docs' tile price; to confirm on the dashboard |

## Free-tier allowances, from the providers' docs (checked 2026-11-25)

These are the documented numbers. The measured ones will replace them as the logs fill up.

| Provider | Allowance | Resets | What one unit costs | Source |
|---|---|---|---|---|
| Cloudflare Workers AI | 10,000 neurons a day | 00:00 UTC (03:00 EAT) | FLUX.2 klein: about 26 neurons per 512×512 output tile and about 5.4 per reference tile, so about 104 for 1024×1024 and about 200–310 for a 1080×1920 keyframe (how part-tiles are rounded isn't documented). FLUX.1 schnell: about 58 at 4 steps | developers.cloudflare.com/workers-ai/platform/pricing |
| Addis AI | No daily cap; a prepaid wallet in ETB. Signup credit is 500 ETB per the FAQ, or "$3.17" per the pricing page | — | Addis Voices 2: 5 ETB a generated minute, so a full Amharic narration (about 70 s) is about 6 ETB. A 402 means the credit ran out | docs.addisassistant.com/docs/platform/pricing |
| Gemini API, free tier | Per model and per project; the numbers are no longer in the docs, only on the signed-in AI Studio rate-limit page | Midnight Pacific (11:00 EAT) | Free for `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts` | aistudio.google.com/docs/rate-limits |

The image allowance is the tighter one for agents. One round of three candidates for ten shots at 1080×1920 is 6,000–9,300 neurons, most of a day. The producer (A3) therefore has to budget in neurons, not in images.

## Measured, from the logs (`film costs`)

<!-- film costs: generated from runs.jsonl and stages.jsonl; edits between these markers are overwritten -->

### Every model call, by stage and model

| Stage | Provider | Model | Attempts | OK | Failed (by kind) | Median s | p95 s | GPU min | List-price equivalent |
|---|---|---|---|---|---|---|---|---|---|
| keyframes | cloudflare | @cf/black-forest-labs/flux-2-klein-4b | 18 | 18 | — | 7.9 | 14.1 | — | $0.061 |
| music | gpu-runner (kaggle) | ACE-Step-1.5 | 9 | 0 | error 9 | — | — | 6.9 | no checked price |
| music | gpu-runner (kaggle) | ACE-Step-1.5 (acestep-v15-turbo, DiT only) | 3 | 3 | — | 27.3 | 157.7 | 2.5 | no checked price |
| narration | addis | addis-voices-2 | 11 | 11 | — | 4.3 | 7.8 | — | no checked price |
| narration | gemini | gemini-3.8-flash-tts | 11 | 11 | — | 4.9 | 7.3 | — | no checked price |
| narration | gemini | per-voice | 3 | 0 | quota 1, transient 2 | — | — | — | no checked price |
| references | cloudflare | @cf/black-forest-labs/flux-2-klein-4b | 24 | 24 | — | 11.1 | 29.8 | — | $0.082 |
| shots | gpu-runner (kaggle) | Wan2.2-TI2V-5B | 1 | 0 | error 1 | — | — | 0.3 | no checked price |
| shots | gpu-runner (kaggle) | Wan2.2-TI2V-5B (diffusers, Wan2.2-TI2V-5B-Diffusers) | 4 | 4 | — | 2062.6 | 2068.9 | 132.2 | no checked price |
| smoke | addis | addis-voices-2 | 1 | 1 | — | 2.7 | 2.7 | — | no checked price |
| smoke | cloudflare | @cf/black-forest-labs/flux-2-klein-4b | 2 | 2 | — | 9.2 | 9.9 | — | $0.007 |
| smoke | gemini | gemini-3.8-flash | 6 | 2 | transient 4 | 83.3 | 212.1 | — | no checked price |
| smoke | gemini | gemini-3.8-flash-tts | 2 | 2 | — | 3.8 | 4.9 | — | no checked price |
| smoke | speech | per-voice | 2 | 0 | bad_request 1, error 1 | — | — | — | no checked price |
| story | gemini | gemini-3.8-flash | 11 | 5 | transient 6 | 120.3 | 166.8 | — | no checked price |

Totals: 108 attempts, 83 succeeded; GPU 141.9 min; priced items $0.15 at list price (unpriced rows excluded).

### Exports, as measured at the last assembly

| Export | Duration s | Integrated LUFS | True peak dB | Pictures | Music |
|---|---|---|---|---|---|
| am.horizontal | 76.708 | -13.9 | -1.4 | kenburns 8, i2v 2 | m1.13 |
| am.vertical | 76.708 | -13.9 | -1.4 | kenburns 8, i2v 2 | m1.13 |
| en.horizontal | 73.833 | -14.0 | -1.2 | kenburns 8, i2v 2 | m1.13 |
| en.vertical | 73.833 | -14.0 | -1.2 | kenburns 8, i2v 2 | m1.13 |
| radio.am | 76.667 | -13.9 | -1.4 | — | m1.13 |
| radio.en | 73.792 | -14.0 | -1.2 | — | m1.13 |

<!-- end of generated tables -->
