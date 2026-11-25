# 00 — Requirements

The Heritage Short, 10 Academy B2W0. This is our reading of what must exist by Thursday and how each grading point will be proven. We come back to it at every checkpoint and update the Status columns as we go.

Source of truth: the project holds two versions of the brief, a plain-text copy and a PDF printed from tenx on 24 Nov 2026 at 15:13. The PDF is newer and stricter in five places, so where they differ we follow the PDF.

## 1. Where the two versions differ

| Topic | Text copy | PDF (we follow this) | What it changes for us |
|---|---|---|---|
| Deadline | Not stated | Both assignments due Thu 26 Nov, 23:59 EAT | We aim to submit by 21:00 EAT on Thursday; the build starts on Wednesday 25 Nov, so we have about a day and a half |
| First user test | Radio cut played to "a few people" | At least three people from the audience | Recruit testers today |
| Second user test | "Show your audience again" | Near-final cut to at least three people, named as the second test | A second round early on Thursday afternoon |
| Walkthrough | One shot regenerated live | Change one keyframe prompt or one narration line, rerun, and show that only that shot regenerates. Wan need not run on camera, pausing is fine, and logs showing a single new model call count as evidence | `film plan` and runs.jsonl must make "exactly one new call" obvious |
| Assignment 2 format | Three links | Vertical MP4 is the main submission; horizontal MP4, walkthrough and post go in as attachments on tenx | Four public links, each opening without login |

## 2. Deliverables

### Film and release (Assignment 2, graded by hand)

| Requirement | How we check it | Status |
|---|---|---|
| 60–90 s, exported 9:16 and 16:9 as MP4 (H.264 + AAC) | ffprobe runtime and frame size written to stages.jsonl | ☐ |
| English narration, plus an Amharic version from the same storyboard; the testers' response decides which is the main submission (ADR-015) | One native-speaker listen per language, noted in DESIGN.md | ☐ |
| Accurate English subtitles, burned in, inside the vertical safe area | Translation checked by a native speaker; at most two lines of about 40 characters | ☐ |
| Original score ducked under the voice | Music level under the voice vs in the pauses, measured and logged | ☐ |
| Final loudness about −14 LUFS, true peak at most −1 dB | Two-pass loudnorm report logged | ☐ |
| Visible AI end card, 2–3 s | Present in timeline.json, visible in the walkthrough | ☐ |
| Consistent character and style | Golden reference, critic verdicts, a human check of every keyframe | ☐ |
| A story that lands for our audience | Second user test notes | ☐ |
| Walkthrough of at most 5 min: architecture, one hard decision, one live regeneration | `film plan` shows one miss; runs.jsonl gains one line | ☐ |
| Public post written by Y: the story, why it matters, one lesson; platform AI label on | Screenshot kept | ☐ |
| Every link opens without login | Checked in a private browser window | ☐ |

### Repository and report (Assignment 1, read as text)

| Path | What it must hold | Status |
|---|---|---|
| README.md | One command to rebuild the film, what it does, what it costs; followable by a stranger | ☐ |
| storyboard.json | 8–12 shots: durations, image and motion prompts, references, narration, music cues, and a reason for every shot | ☐ |
| schema/ | JSON Schema for the storyboard, validated before every run | ☐ |
| pipeline/ | One script per stage: script, keyframes, shots, music, narration, assemble (we add references) | ☐ |
| runs.jsonl | One line per model call: model, parameters, seed, latency, cost | ☐ |
| outputs/ | Generated images, audio and video kept for inspection (graders don't open them) | ☐ |
| DESIGN.md | Audience and intent written before any generation; both user tests; what changed; why each shot exists | ☐ |
| ARCHITECTURE.md | Stages, contracts, caching, failure handling | ☐ |
| EXPERIMENTS.md | At least ten hypothesis → change → result entries backed by run ids | ☐ |
| FAILURES.md | Real blockers, what we tried, what got us past them | ☐ |
| COSTS.md | Measured latency and GPU minutes per stage, free-tier limits actually hit, list-price equivalent | ☐ |
| ETHICS.md | Consent record, licence of every model and output, labelling plan | ☐ |
| Report (PDF, Word or link) | Who it was for, what the audience taught us, the hardest problem, a suggested practice that helped and one that didn't, ceiling work, what next | ☐ |

## 3. Where the points come from

Assignment 1 is read as code, text and logs, then followed by an AI interview that checks we understand our own work.

| Criterion | Points | How we'll prove it |
|---|---|---|
| Software engineering and reproducibility | 20 | Schema and lint before every run; per-unit cache with sidecars; retry policy in code; gitleaks in pre-commit and CI; complete runs.jsonl; a CI job that clones fresh and runs `make film` |
| Documentation | 10 | README tried on someone who hasn't seen the repo; ARCHITECTURE.md built from these docs |
| Design thinking and audience | 10 | DESIGN.md committed before the first generative call (git history shows the order); two test tables of at least three people; storyboard snapshots v1, v2, v3 with each change traced to what a tester said; `reason` required for every shot |
| Experimentation and iteration | 10 | EXPERIMENTS.md entries citing run ids; one change per experiment, seed fixed |
| Troubleshooting and persistence | 10 | FAILURES.md written when things break, with the log line that shows it |
| Measurement | 5 | `film costs` builds COSTS.md from the logs; list prices with source and date; no frontier comparison, because we have no frontier access, stated plainly |
| Consent, labelling and licences | 5 | Consent table filled before anything of a real person is generated; licence table; labelling plan |
| Report: reflection and audience | 10 | Tester quotes and changes from DESIGN.md; the hardest problem from FAILURES.md |
| Report: practices tested honestly | 10 | Practice ledger in build-log.md, with our instinct written down before testing |
| Report: curiosity beyond the floor | 10 | One ceiling direction, measured and written up |

Assignment 2 is graded by hand: the film 50, the walkthrough 30, the post 20.

## 4. The gate

If a real person appears or is voiced without a consent record in ETHICS.md, the film scores zero however good it is. We read "appears" broadly: an AI-generated character meant to be a real family member counts, even if no photo was used. Consent comes from the person, or from close family if they have passed away. It covers how they are shown and the words said about them or in their voice, and it is recorded before we generate anything of them. A family photo is used as a reference only if the person agrees to that specific use, since free endpoints may keep what we send. The lint step enforces the gate in code (ADR-014).

## 5. Constraints found in research (25 Nov 2026)

The brief warns that parts of it will be out of date, so we checked each tool before designing around it.

| Resource | What we found | What it means for the design | Source |
|---|---|---|---|
| Gemini 3.8 Flash TTS | Model `gemini-3.8-flash-tts` (130 languages) and `gemini-3.8-flash-lite-tts` (101). Input text is read verbatim, so style hints typed into it may be spoken aloud. Default output is WAV with a RIFF header. | Narration text holds only spoken words; voice and style are separate fields; language support for our language is confirmed per model in the smoke test | [model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts) |
| TTS quota | Limits apply per project and per model; daily limits reset at midnight Pacific, which is 11:00 EAT. Developers report 100 requests/day enforced on 3.8 Flash TTS even on paid Tier 1, and 10/day on the free tier of the previous TTS model. Our own free-tier cap is unknown until we hit it. | TTS, not GPU, is our scarcest resource: cache per line, dry-run before spending, keep Flash-Lite TTS as a fallback with its own quota, read the cap from the 429 body | [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [report 1](https://discuss.ai.google.dev/t/gemini-3-8-flash-tts-api-enforces-100-rpd-despite-ai-studio-showing-10k-rpd/187223), [report 2](https://discuss.ai.google.dev/t/will-tier-2-increase-the-effective-daily-quota-for-gemini-3-8-tts/187071), [report 3](https://discuss.ai.google.dev/t/gemini-lies-about-free-tier-quota-limits-sudden-resource-exhausted-blockers-on-tts-models/177531) |
| FLUX.2 klein on Workers AI | `@cf/black-forest-labs/flux-2-klein-4b` (also `-9b`). Steps fixed at 4, `seed` supported, up to four reference images sent as multipart form data, each under 512×512; multipart is required even for text-only calls. The brief lists 4B as Apache-2.0 and 9B as non-commercial. | Reference sheet designed as at most four small images, downscaled before upload; 4B by default, 9B only if an experiment justifies it | [4B changelog](https://developers.cloudflare.com/changelog/post/2026-01-15-flux-2-klein-4b-workers-ai/), [9B changelog](https://developers.cloudflare.com/changelog/post/2026-01-28-flux-2-klein-9b-workers-ai/) |
| Image allowance | The brief says roughly 50–170 free images a day | References on day 1, keyframes on day 2, exploration capped | Brief |
| Wan 2.2 TI2V-5B | 720p means 1280×704 or 704×1280 at 24 fps; frame counts are 4n+1 (121 frames ≈ 5 s); the official single-GPU 720p run needs at least 24 GB of VRAM; in image-to-video the output's aspect ratio follows the input image | A Kaggle T4 (about 15 GB usable) can't run the official 720p path as-is | [model card](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B), [frame counts](https://www.runpod.io/articles/guides/comfyui-wan-2-2) |
| Wan on a free T4 | One community project reports most checkpoints don't fit a free T4 and recommends the distilled 5B "FastWan" build at 480p, at about 8 minutes per 5-second clip; GGUF quantisations for ComfyUI also target the T4 | Spike S1 tonight decides how many shots get real motion; Ken Burns covers the rest | [Wan2GP-on-Colab](https://github.com/Square-Zero-Labs/Wan2GP-on-Colab), [guide](https://dev.to/haroonch_rashid_72f1d7e31/wan22-free-open-source-ai-video-generation-720p-cinematic-clips-with-no-subscription-i0n) |
| Kaggle CLI | `kaggle kernels push` uploads and runs a kernel, `kaggle kernels output` downloads its results; the accelerator must be named, because the default GPU is a P100 too old for current PyTorch; secrets set in the Kaggle UI are reported to be stripped on CLI pushes. About 30 GPU hours a week; phone verification required | A CLI job runner keeps "one command"; nothing secret travels to Kaggle | [CLI docs](https://raw.githubusercontent.com/Kaggle/kaggle-api/main/docs/kernels.md), [P100 issue](https://github.com/nvandessel/hippofloop/pull/18) |
| ACE-Step 1.5 | Python 3.11–3.12; CUDA recommended, CPU and MPS work but slower; Python and REST APIs; the 2B model's weights need about 4.7 GB of VRAM (XL about 9 GB); MIT licence | Fits a T4 comfortably; three candidates in one session | [repo](https://github.com/ACE-Step/ACE-Step-1.5), [GPU guide](https://raw.githubusercontent.com/ace-step/ACE-Step-1.5/HEAD/docs/en/GPU_COMPATIBILITY.md) |
| Google Colab | Free GPUs aren't guaranteed and idle sessions time out, so outputs should be saved to Drive as they're made | Colab is our second GPU lane (music, overflow), never the only one; the runner saves each output as it finishes | [guide](https://dev.to/haroonch_rashid_72f1d7e31/wan22-free-open-source-ai-video-generation-720p-cinematic-clips-with-no-subscription-i0n) |
| Our own setup | Claude in claude.ai can't reach Gemini, Cloudflare or Kaggle from its sandbox; Y already hands work to Claude Code through CLAUDE.md; Y's laptop has no GPU and we have no frontier key | We plan in claude.ai; Claude Code writes and runs the code on Y's laptop; GPU work goes to Kaggle and Colab. Offline parts (mock providers, FFmpeg) can be tested anywhere | — |

## 6. How we read the ambiguous parts

| Question the brief leaves open | Our reading | Why |
|---|---|---|
| What does "rebuild from a clean clone" require? | `make film` on a fresh clone rebuilds the film from committed artifacts through the cache, so only FFmpeg runs and no keys or GPU are needed. `make film FORCE=1` with keys regenerates everything | Graders can actually run it, and we stay honest that full regeneration needs quota |
| Is the script stage part of `make film`? | No. `make storyboard` drafts and we review; `make film` starts from the committed storyboard | Re-running the writer on every build would overwrite our edits and make the film unrepeatable |
| What goes in runs.jsonl? | Every model-call attempt, failures and retries included, and remote GPU jobs with their GPU seconds. Cache hits go to stages.jsonl | Keeps the "single new model call" proof readable |
| Does an AI character based on a real person "appear"? | Yes | The gate zeroes the film, so we read it conservatively |
| Burned-in or sidecar subtitles? | Both: burned into each export, plus an .srt | Phase 3 says burn in; the .srt costs nothing |
| Who counts as "from your audience"? | People like the intended viewers. Slack colleagues are extra voices, not substitutes | The rubric asks for three people from the audience, each time |
| Delivery resolution? | 720p (720×1280 vertical, 1280×720 horizontal), unless the spike shows 720p Wan is affordable | The brief sets none; upscaling 480p clips to 1080p adds file size, not detail |
| Can we add a stage? | Yes: `references` runs before `keyframes` | The brief invites improvements, and a separate stage makes the reference sheet's effect visible in the cache and the logs |
| Which language is the main submission? | Whichever version the testers respond to best, English by default; the other is linked from the post and the report (ADR-015) | English must be available; the brief accepts any language; Amharic is the version most likely to need fixes |
