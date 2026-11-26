# EXPERIMENTS

Hypothesis, one change, result, and the run ids or measurements that prove it. The backlog (E1–E16) is in `docs/01-plan.md` §16; entries move here as they run.

## Index

| ID | Question | Status |
|---|---|---|
| E1 | Does 3.8 TTS speak style words typed into the text? | planned |
| E2 | Does a style instruction beat switching voices? | planned |
| E3 | Is Flash-Lite TTS good enough for the English version? | planned |
| E4 | Does conditioning on the golden reference keep the character recognisable? | planned |
| E5 | Is klein 9B worth its non-commercial licence over 4B? | planned |
| E6 | Does a fixed style block drift less than per-shot style wording? | planned |
| E7 | How much GPU time does 480p save over 720p, and at what cost? | half done: 480p measured in S1 (1,737 s a clip); 720p not run |
| E8 | Do motion-only prompts beat re-describing the subject? | planned |
| E9 | Can a square master serve both orientations? | planned (spike S1) |
| E10 | Which score candidate works under the voice, and why? | done 2026-11-26: m1.13, the quietest, picked by ear (decision P-0001) |
| E11 | Do the brief's ducking defaults suit our voice? | planned |
| E12 | Does normalising each stem first make mixing easier? | planned |
| E13 | Does the critic agree with Y's blind picks often enough to delegate keyframe pins? | planned (A3); its result sets the autonomy |
| E14 | Do viewers prefer real motion for people but not for places? | planned (test 2) |
| E15 | Does the same meaning run longer in Amharic than in English? | done 2026-11-26: yes, 6% longer overall and up to 29% per line; it moved the score's silence |
| E16 | Does respelling a name fix an Amharic mispronunciation? | planned |
| E17 | How many characters per subtitle line fit each orientation? | done, 2026-11-25 |
| E18 | Does a staged story chain need fewer corrections than drafting in one call? | planned (A2) |
| E19 | Does the critic's ranking change with the order candidates are shown in? | planned (A3) |
| E20 | Does feeding the critic's reasons back raise the next round's acceptance? | planned (A3) |
| E21 | For Amharic narration, does a model built for Amharic (Addis Voices 2) beat a general one (Gemini 3.8 TTS)? | planned (Thursday, after the radio cut) |
| E22 | Does FLUX.2 klein drift away from Ethiopian features unless the description names them explicitly? | done 2026-11-26: yes; explicit features fixed 2 of 3 characters fully and the guest partly |

## E17: subtitle line length per orientation (2026-11-25)

Hypothesis. The brief's guide of about 40 characters per line works in both orientations.

Change. The same subtitles were burned into the vertical (720×1280) and horizontal (1280×720) mock exports, first at 42 characters per line, then at 28 for vertical only. Seed fixed; mock workspace.

Evidence. On a frame grab of the vertical film at 10.5 s, libass re-wrapped the 38-character first line, so the card showed three lines. That breaks the two-line rule. Measured on the same frame, DejaVu Sans at FontSize 11 is about 22 px per character (0.45 em). That leaves room for about 30 characters inside the vertical margins. At FontSize 9, with 40-unit side margins, 28 characters fit on two lines, clear of the bottom fifth and the right edge where phone apps draw buttons. Horizontal frames fit 42 characters on two lines at FontSize 15.

Result. Rejected for vertical. Line length is now per orientation (`config/pipeline.toml`: 28 vertical, 42 horizontal), with one SRT per orientation. A test checks that no line exceeds its limit and no card holds more than two lines.

Follow-up. The first fix left a one-word card ("evening.") on screen for 0.4 s. The chunker now picks the fewest cards with the most even lengths and prefers breaking after commas. A test checks that no card is shorter than eight characters.

## S1 → E7, first half: Wan 2.2 TI2V-5B on a Kaggle T4 (2026-11-26)

Hypothesis. A free T4 can animate a keyframe with Wan 2.2 5B at 480p, slowly but within budget.

Change. None yet: this is the baseline. s02 (honey wine pouring into a berele), 480×832, 121 frames (5.04 s at 24 fps), 50 steps, guidance 5.0, seed 2002. Diffusers in fp16 with the VAE in fp32. The transformer streams one block at a time (group offload, CUDA stream, on-the-fly pinning), and the text encoder is freed after the prompts are encoded. It took three runs to get here (FAILURES.md F7–F9).

Evidence. `runs.jsonl`, s02.i2v, provider "gpu-runner (kaggle)":
- `gpu_s` 1737.44, so about 34.7 s a step, including the tiled VAE decode and the export;
- `load_s` 357 (download about 34 GB and load);
- peak GPU memory 5.75 GB.

The clip is 121 frames at 24 fps. On four frames from 0.1 s to 4.9 s, the pour is continuous, the flask fills and foams, and the candles and table stay put, with no flicker or morphing visible at that sampling.

Result. Confirmed. The cost is about 29 GPU minutes per 5 s clip. The four Wan shots planned (s02, s06, s08, s10) come to about two GPU hours, or about 6% of the weekly 30, in one session that runs them one after another. 50 steps stays. The 720p half of E7 isn't worth the quota this week.

## E10, setup: three ACE-Step takes under the narration (2026-11-26)

Hypothesis (from the plan). The quietest of three candidates works best under the voice.

Change. One caption ("Gentle, understated acoustic strings with soft traditional krar notes, warm and meditative under spoken narration"), instrumental, 86 s, turbo, 8 steps. Seeds 11, 12 and 13 are the only difference.

Measurements (`ffmpeg ebur128`, `silencedetect` at −45 dB for 2 s, and a spectrogram in `build/review/score_takes_spectrum.png`):

| Take | Integrated | LRA | Gaps over 2 s | What the spectrogram shows |
|---|---|---|---|---|
| m1.11 | −14.3 LUFS | 7.4 LU | 1 (the end) | Continuous to about 78 s, then a low hum |
| m1.12 | −14.9 LUFS | 7.6 LU | 0 | Continuous to about 82 s, then a fade |
| m1.13 | −16.3 LUFS (quietest) | 7.8 LU | 3 | Drops out around 55–62 s and 66–68 s, which would fall under s08–s09 |

All three are rhythmically dense, with plucked-sounding strokes across the whole range, so they're busier than the caption asked for. Three radio cuts, one per take, are in `build/review/radio_en_take_m1.*.mp4` for Y to hear at low volume on a phone, as the brief suggests.

Early read, before listening. The hypothesis looked in trouble: the quietest take (m1.13) is quiet partly because it drops out in the middle of the film.

Result (16:20). Y picked **m1.13** by ear, and a colleague, listening separately, preferred it too. That supports the hypothesis, though for a reason the numbers missed. Mapped onto the English timeline, its two quiet stretches fall at 54.8–60.1 s, under s09 ("My grandmother said he spent his life serving the emperor", shot 54.8–60.8 s), and at 65.7–68.5 s, under the last words of s10, whose narration ends at 67.7 s. The score steps back exactly where the story turns to family memory, then returns for the end card. "Gaps" counted as a defect in the measurements were the take's strength under this voice. The lesson: measure, but choose by listening against the picture and the voice. The pick is decision P-0001 in decisions.jsonl, with the reason in `music.cues[0].why`. The rebuilt radio cut measures −14.8 LUFS and −1.0 dB true peak.

## E22: naming Ethiopian features in the character descriptions (2026-11-26)

Hypothesis. FLUX.2 klein falls back on its default faces unless the description names the features. Saying "Ethiopian" once isn't enough.

Change. Only the three character descriptions (decision P-0002, actor Y). Each now names "Ethiopian Habesha", skin tone, hair texture, face shape and period dress: a tunic with a woven tibeb border for Tesfaye, a black wool kaba cape for the guest, a clean-shaven face for the great emperor. The reference prompt, style block, seeds (101–104, 201–204, 301–304), size and model are unchanged. The "before" images are kept in `build/review/refs_before/`.

Evidence. `build/review/ref_*_before_after.png`, 12 renders each way, all logged in runs.jsonl. This is Claude Code's reading of the sheets, for Y to confirm:

| Character | Read as Habesha, before | After |
|---|---|---|
| Tesfaye | 1 of 4 (seed 103) | 4 of 4: dark-brown skin, tightly curled hair, slender faces, consistent across the three views |
| The great emperor | about 1 of 4, ambiguous | 4 of 4: elderly, white-haired, clean-shaven, upright. None resembles Haile Selassie (no beard, different face) |
| The guest | 0 of 4 (Mediterranean in all) | 2 of 4 (202, 204); 201 and 203 still read Mediterranean. The moustache and kaba came through in all four |

Result. Confirmed for two characters, partly for the third. Naming the features moved FLUX away from its defaults. An older man in a cape still pulls toward a Mediterranean face, so the guest gets a reference pick that reads right rather than another description rewrite. Cost: 12 images, about 2 minutes.

## E15: the same meaning in Amharic and English (2026-11-26)

Hypothesis. The same meaning runs longer in Amharic than in English.

Change. The same ten shots: English by Gemini 3.8 TTS (Kore), Amharic by Addis Voices 2 (am-loza, decision P-0005), measured from the WAVs.

Evidence:
- **Overall,** speech totals 51.6 s in English and 54.8 s in Amharic, a ratio of 1.06.
- **Per line,** the ratio runs from 0.74 (s06, s07) to 1.29 (s09).
- **Five Amharic lines don't fit their shots** with the 0.4 s lead-in and 0.6 s tail: s01 +0.1, s04 +1.6, s08 +0.8, s09 +1.1 and s10 +0.2 s. Assembly lengthened those shots, as designed, so the Amharic film is 74.8 s against 71.8 s in English, both inside 60–90.
- **Speaking rate:** English 1.9–2.7 words a second; Amharic 5.4–8.4 Ge'ez characters a second.

Result. Confirmed, with a side effect nobody planned for. The score's first quiet stretch (54.8–60.1 s), chosen because it falls under s09 in English, started under the end of the toast line (s08) in Amharic, and the music came back halfway through s09. A score laid from t = 0 doesn't survive a language change. Fix: an optional `anchor` on the cue (`{"shot": "s09", "at_s": 54.8}`), with the score shifted per language: −0.008 s in English, +1.75 s in Amharic. Y approved it as P-0006 at 17:32. The rebuilt radio cuts log `music_offset_s` −0.008 (English) and +1.742 (Amharic). ADR-010 already said music cues reference shots, not seconds; this makes that true at a point inside the cue.

## Wan on people: what image-to-video kept and what it broke (2026-11-26)

Observation, not a planned A/B. It feeds E8 (motion-only prompts) and E14 (real motion versus Ken Burns, for people and for things).

Four Wan 2.2 clips, all at the same settings (480×832, 121 frames, 50 steps, fp16). Frames sampled at 0.1, 1.7, 3.3 and 4.9 s (`build/review/wan_s06_s08_s10.png`):

| Shot | Motion prompt | What came back | Verdict |
|---|---|---|---|
| s02 | "Static camera as honey wine pours smoothly into the glass flask with rising micro-bubbles" | A continuous pour, the flask fills, the scene stays stable | Kept |
| s06 | "Static camera as the server gently lowers his gaze and holds his breath in composure" | He lowers his gaze and raises a hand to his chin; the identity holds | Kept |
| s08 | "Subtle handheld tremor as the subject takes a slow, shaky breath with glistening eyes" | A second person's hand appears, pushing a white object to his mouth | Rejected |
| s10 | "Gentle forward camera drift as the subject slowly brings the glass to his lips looking out" | The push-in turns into a close-up of a different-looking face, which grows a moustache; no drink | Rejected |

Reading. The two clips that worked asked for one gentle movement with a static camera. The two that failed asked for a camera move ("handheld tremor", "forward drift") on a face, plus an emotional or object action. That matches the brief's tips: short, slow, one movement, and say "static camera". Identity is safe while the face stays at the keyframe's scale; a push-in makes Wan invent the face it zooms into. A retry would say: static camera, one small action, no objects that aren't already in the frame. Cost: two rejected clips are about 69 GPU minutes. The decision to fall back is P-0007.
