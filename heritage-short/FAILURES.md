# FAILURES

What broke, what we tried and what fixed it, written when it happens, with the evidence that shows it.

## F1: vertical subtitles ran to three lines (2026-11-25, assemble)

Symptom. All 19 tests passed and every export measured correctly, yet a frame grab of the full-size vertical mock film showed a three-line subtitle. The chunker had produced two lines of up to 42 characters, and libass wrapped the first line again because it was wider than the 720-pixel frame. No test could see this, because the tests check text and numbers, not pixels.

What we tried. We measured the rendered character width from the frame (about 22 px per character at FontSize 11). The first fix shortened vertical lines to 28 characters, which exposed a second problem: a one-word card shown for 0.4 s.

What fixed it. Line length per orientation (28 vertical, 42 horizontal); a smaller vertical font with wider side margins, to stay clear of phone UI; and a balanced chunker that breaks after punctuation. Both rules now have tests (E17).

What it changed. Looking at a rendered frame is now part of checking any change to assembly, alongside the tests.

## F2: Homebrew's FFmpeg can't burn in subtitles (2026-11-25, Wed, setup)

Symptom. Moving from claude.ai's sandbox to Y's Mac, `brew install ffmpeg` installed FFmpeg 9.1, but `ffmpeg -filters` listed no `subtitles` filter (and no `drawtext`). Assembly burns every subtitle card in with `subtitles=…`, so every export would have failed at the last step, after all the model calls had been spent. Brew's own message gave the cause: the core formula is now slim, and libass lives in `ffmpeg-full`.

What we tried. Listing the filters the code actually uses (16, from `pipeline/*.py`) and checking each one against this build: 15 were present, and only `subtitles` was missing.

What fixed it. `brew install ffmpeg-full`. It is keg-only, which means it is installed but not put on PATH, because it conflicts with `ffmpeg`. So the first test run still found the slim build and skipped the media tests. `media._exe` now looks in Homebrew's keg directory first (or in `FFMPEG_BIN`), and `media.missing_filters()` checks all 16 filters. A machine with the wrong build now fails at the start with a clear message, instead of after quota has been spent. The README names the right formula. With the full build, all 72 tests pass, including both full mock builds. A frame grab from each orientation showed two-line subtitles inside the safe area, and the blurred fill behind the vertical clip in 16:9.

What it changed. Tools are checked for the features we use, not just for being on PATH.

## F3: Gemini was overloaded during the first live smoke test (2026-11-25, Wed, 23:57)

Symptom. The first `make smoke` with real keys took more than two minutes. runs.jsonl shows why: the text call to `gemini-3.8-flash` got `503 UNAVAILABLE` three times (attempts 1–3, at 20:57:32, :36 and :42 UTC), and attempt 4 succeeded after 131,011 ms, for an answer of 9 tokens. Speech (4.2 s) and the image (9.5 s) were fine.

What we tried. Nothing by hand. The engine's retry policy treated the 503s as transient, backed off with jitter, and logged every attempt. That is exactly what non-negotiable 5 is for.

What fixed it. The retries carried it. One gap showed up: the Gemini client had no timeout, so a hung call would have hung the run. It now has a 240 s timeout, and a timeout counts as a transient error, which is retried and logged.

What it changed. Agent steps can be slow when Gemini is under load, so the story chain is run when someone is watching, not right before a deadline. Steps already done stay cached if a later one fails.

## F4: Addis AI answered 201 with the audio inline, not what its docs describe (2026-11-26, Thu, 00:10)

Symptom. The first live `make smoke` with the Addis AI key failed on `speech_am` with "Addis AI 201 : {"data":{"id":"8069f0ab-…","voice_id":"am-hamen",…,"audio":"data:audio/wav;base64,UklGR…". The clip had been generated, and probably billed, but the adapter called it an error. Two assumptions from the docs were wrong: a new clip comes back as **201 Created**, not 200, and the WAV comes **inline** as a data URL in `data.audio`, not as a signed `audio_url` to download.

What we tried. Read the logged error body, which already held the answer, and checked the audio header in it (`UklGR` is base64 for `RIFF`, so it's a WAV).

What fixed it. The adapter now accepts any 2xx, and takes audio from `data.audio`, `audio_url`, `audio_data_url` or `playback.url`. A test reproduces the production answer. Re-running the smoke test sent the same `client_request_id` and came back with the same clip id, `8069f0ab-…`, so the retry wasn't a second generation. The result is 2.58 s of 44.1 kHz mono 16-bit WAV, in 2.7 s. Failed attempts made through the speech router are now logged against the provider that failed (`addis`), not the router.

What it changed. Docs written by the provider are a starting point, and the first logged answer is the ground truth. Logging the full error body is what made this a five-minute fix.

## F5: Gemini's daily TTS cap ran out on the last line of the narration (2026-11-26, Thu, 01:01)

Symptom. `film render --stage narration --lang en` voiced s01–s09, then s10.en failed: "Gemini daily quota used up: GenerateRequestsPerDayPerProjectPerModel-FreeTier". Two per-minute 429s (s05, s09) came first and were retried. Counting runs.jsonl, `gemini-3.8-flash-tts` had answered 11 times since the Pacific day began (two smoke tests and nine lines), so the free cap for this model is about 10 a day. It resets at midnight Pacific, 11:00 EAT. The error body didn't state the cap, and the adapter didn't log one even when it was present, so the message now carries "cap N a day" when Google gives it.

What we tried. The engine did what ADR-008 says: it stopped calling that provider for the rest of the run, marked s10 deferred, and exited resumable. Nine lines are cached and won't be paid for again. The radio cut refuses to build with a line missing, by design.

What fixed it, or works around it.
- s10.en is voiced after 11:00 EAT with one call, then the radio cut is built. Nothing else needs to rerun.
- About 10 Gemini TTS calls a day is the real budget for the whole film: 10 English lines, 10 Amharic lines and every retake after the user tests. Addis AI has no daily cap (it bills per minute), so moving Amharic to it (E21) would leave Gemini's 10 a day for English. That's Y's decision.

What it changed. TTS, not the GPU, is the scarcest resource, as the plan predicted (risk table, ADR-008). Smoke tests now cost real quota, so they belong at the start of a day, not between runs.

## F6: The Kaggle CLI no longer accepts the username and key (2026-11-26, Thu, 01:25)

Symptom. With `KAGGLE_USERNAME` and `KAGGLE_KEY` set from `.env`, `kaggle kernels list --mine` (Kaggle CLI 2.2.5) answered "Authentication required to call the Kaggle API". It offered two routes: an OAuth login (`kaggle auth login`), or a new-style API token from kaggle.com/settings/api, supplied as `KAGGLE_API_TOKEN` or in `~/.kaggle/access_token`. Before that, `import kaggle` failed with "No module named 'six'", a dependency the package uses but doesn't declare.

What we tried. A read-only listing call, to check the credentials before anything touched Y's account.

What fixed it. `six` is now a dependency in pyproject. `.env.example` now asks for `KAGGLE_API_TOKEN` instead of the old pair. The token itself has to come from Y: it's generated in Y's Kaggle settings, and only Y can do that.

What it changed. This is the brief's warning in action: tools move, so check each tool against today's version before relying on it. Until the token is in `.env`, the GPU round trip is launched by hand through the notebook (gpu/README.md).

## F7: The first Kaggle run failed all four jobs, for two reasons that were both ours (2026-11-26, Thu, 12:37)

Symptom. `film kaggle push` launched at 12:09. The run queued until about 12:30, ran about 7 minutes, and finished "complete" with every job failed. `film kaggle pull` logged all four failures in runs.jsonl.
- **s02.i2v (Wan):** the weights loaded (`load_s` 361, including the 34 GB download), then 15.5 s later `torch.OutOfMemoryError ... GPU 0 has a total capacity of 14.56 GiB of which 98.81 MiB is free ... 14.28 GiB is allocated by PyTorch`. This happened inside a `.to(device)`, before any denoising step.
- **m1.11–m1.13 (ACE-Step):** its own environment built in 61 s, then every job failed at once with `RuntimeError: Invalid device argument : did you call init?`.

What we tried. Read the tracebacks in the run's logs, which `pull` downloads with the results.
- **Wan:** diffusers' model CPU offload moves whole components and evicts one only when the next in its fixed order starts. The TI2V pipeline encodes the first frame with the VAE after the text encoder and before the transformer. So the 11 GB umT5 encoder was still on the GPU when the 2.8 GB fp32 VAE was moved there, and the two together don't fit in 15 GB.
- **ACE-Step:** the runner reset GPU 1's peak-memory counters from a process that had never touched GPU 1. ACE-Step itself runs in a subprocess, and this was the runner's bookkeeping.

What fixed it.
- **Wan now uses group offloading** (`runner_wan.py`). Each model's weights stay in CPU memory and stream to the GPU two blocks at a time, with the transformer's transfers overlapped on a CUDA stream. Sequential offload is the fallback. The notebook also sets `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
- **Peak-memory measurement is best effort.** It runs only if CUDA was initialised in that process, and it can never fail a job.

Rebundled and relaunched at 12:40. The job specs didn't change, so the cache keys are the same.

What it changed. The cheapest useful run is the one that fails in the first minutes and logs why. This one cost about 7 GPU minutes, and both causes are visible in text. Measuring on the real hardware (spike S1) is what the plan asked for, and the docs' recommended offload setting was wrong for this pipeline on a 15 GB card.

## F8: Run 2: Wan killed by the OS (host RAM), ACE-Step stopped by a matplotlib setting (2026-11-26, Thu, 13:11)

Symptom. Run 2 queued from 12:40 to about 13:03 and finished at 13:10, again with no output.
- **s02.i2v (Wan):** the run log ends just after "Loading checkpoint shards 5/5" and diffusers' note "Using streams is only supported for num_blocks_per_group=1… Setting it to 1". There was no traceback and no result line, and the notebook reported the process "finished with exit code -9". That's a SIGKILL from Linux's out-of-memory killer, so it was host RAM this time, not the GPU. The 11 GB text encoder, the 10 GB fp16 transformer, a pinned copy of the transformer made for streaming, and ACE-Step running alongside together went past the box's 29 GB.
- **m1.11–m1.13 (ACE-Step):** the environment built (`load_s` 106 s), then each job failed with `ValueError: Key backend: 'module://matplotlib_inline…'`. Kaggle's notebook sets `MPLBACKEND` to its inline backend, the subprocess inherited it, and ACE-Step's own environment can't import it.

What we tried. Read the notebook's own log, downloaded by `film kaggle pull`. It holds the exit codes the runner can't report once it has been killed.

What fixed it.
- **Wan's memory plan was rewritten** (`runner_wan.py`):
  - encode every prompt once with the text encoder alone on the GPU, then drop it from GPU and host memory;
  - keep the fp32 VAE resident on the GPU;
  - stream the transformer one block at a time, with pinning on the fly where diffusers supports it;
  - pin the pipeline's execution device to the GPU.
- **ACE-Step's subprocess gets `MPLBACKEND=Agg`.**
- **The notebook now runs the bundles one after another,** music first, because host RAM, not the two GPUs, is the binding limit.
- **The runner writes a "started" line before each job.** If the OS kills it mid-job, `film ingest` logs that job as a failure ("the runner died during this job…") instead of it vanishing. A test covers it.

Launched as run 3 at 13:15.

What it changed. One layer at a time: run 1 found the GPU limit, run 2 the host-RAM limit, each in under 10 GPU minutes. A process killed by the OS leaves no traceback, so the "started" line is the only way the logs can show it happened.

## F9: Run 3: Wan worked; ACE-Step crashed on a missing key signature (2026-11-26, Thu, 13:54)

Symptom. Run 3 (launched 13:15) was the first to produce a clip. s02.i2v came back "ok" after 1,737 s, and its frames look right. The three music jobs failed inside ACE-Step's own code: `metadata_utils.py, line 72, in _build_metadata_dict: metadata_dict["keyscale"] = key_scale if key_scale.strip() else "N/A" … AttributeError: 'NoneType' object has no attribute 'strip'`. The notebook itself ended in ERROR: `KeyError: 'seconds'` in its summary cell, which tripped on the new "started" lines (F8), so the zip was never written. `film kaggle pull` fell back to the raw output folder, and ingest still worked.

What we tried. The traceback says it outright. Our music cue has no `key` (the story agent's draft gives a caption only), our job script turned that into `None`, and ACE-Step expects a string. It's a good sign in itself: ACE-Step's model loaded and got as far as building its metadata on the T4, in fp16, from its own Python 3.12 environment.

What fixed it. A missing key is now `""`, so ACE-Step picks one itself. The notebook zips the output first and then prints the summary, skipping "started" lines, so a printing problem can't cost the results again. The music bundle was relaunched alone at 13:55.

What it changed. After a model ran on the target hardware, the remaining failures were in our glue code, each found and fixed from the logged traceback within minutes.

## F10: Triplets in the keyframes, and headless shots in the 16:9 cut (2026-11-26, Thu, 16:45)

Symptom. The first eight keyframes with people (16:40) put Tesfaye in the frame two or three times in s01, s06 and s10, side by side like a character sheet. s07 showed the great emperor from the front, raising his glass, against Y's framing rule and the narration. Then the first 16:9 rough cut cut the heads off Tesfaye, the guest and the emperor in five of six sampled frames.

What we tried. Looked at every keyframe, and at sampled frames of both exports, before going further. The tests passed throughout; only the pictures showed the problems, as F1 warned.
- **The triplets.** Keyframes were conditioned on the whole selected reference image: a sheet with three views of the same man. FLUX.2 klein reproduced the layout as well as the identity.
- **The headless shots.** The Ken Burns shots were cropped to 16:9 from the centre of 9:16 keyframes, which keeps only the middle third.

What fixed it.
- **Keyframes now condition on the front view only:** the left third of the sheet (`images.reference_view = "front"`, part of each conditioned keyframe's key). On the re-render (eight calls, about 1 minute), every frame had one Tesfaye, recognisably the same man in all five of his shots, and s07 came out from behind. Shots with no people (s02, s09) kept their keys, so s02's finished Wan clip wasn't thrown away; the first version of the fix would have re-keyed them, and `film plan` caught it.
- **The 16:9 film now uses the vertical master on a blurred fill for every shot** (ADR-011, accepted). The s07 prompt fix is proposal P-0004, waiting for Y.

What it changed. Reference images are inputs with a layout, not just an identity. Looking at outputs, the keyframes and frames of both exports, is part of every render step, as F1 said.

## F11: Larger subtitles brought back the three-line wrap (2026-11-26, Thu, 20:00)

Symptom. Test 2 asked for larger subtitles (T1, T3). At FontSize 11 with 24-unit margins, a frame grab at 13.7 s showed the 28-character line "And he knew how to disappear" wrapped onto a third line, which is F1 again.

What we tried. libass scales the ASS units from its default 384×288 script size to the 720×1280 frame. So FontSize 11 is about 49 px, and 28 characters is about 680 px, wider than the 630 px left between the margins. We checked frames rather than trusting the arithmetic.

What fixed it. FontSize 10 with 20-unit margins: about 11% larger than before, and 28 characters fit on one line. Checked on frames at 13.7 s (the longest line), 26.0 s and 62.0 s, all two lines. Larger text would mean fewer characters per line, so more cards, and cards that change faster, which T2 already found quick. That's a trade-off for the next round, not tonight.
