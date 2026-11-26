# ETHICS

Consent, labelling and licences. The pipeline reads the consent table below. A character marked `real_person: true` can't be generated until its consent id appears here with every cell filled in (ADR-014).

## Consent record

One row per real person shown or voiced, filled in before anything of them is generated. The evidence itself (a voice note, a message) stays in `private/`, never in the repo.

| ID | Person (role in the film) | Who gave consent | Scope: likeness, voice, words | Date | How it was recorded |
|---|---|---|---|---|---|
| — | No consent rows are needed: nobody real is shown or voiced (see the next table). Tesfaye and the guest are fictional, the great emperor is an unnamed fictional ruler, and the narrator is a prebuilt voice | — | — | — | — |

Our narrator is a prebuilt Gemini TTS voice, not a clone of anyone's voice. Where the narration speaks about a real person, they (or close family) approved the script; the Scope cell says so.

## Real people the story touches (decided 2026-11-26 with Y)

| Person | In the film as | Shown or voiced? | Consent needed? | Why |
|---|---|---|---|---|
| Emperor Haile Selassie (1892–1975), whose palace the family story is set in | Not portrayed. The film has "the great emperor": unnamed and fictional, a short elderly man with an upright posture (Y's decision, 2026-11-26, 00:40) | The fictional emperor is shown, at a distance, from behind or in profile, never in close-up and never voiced | Not for a fictional character. **Residual risk:** a viewer or grader may still read him as Haile Selassie, and the brief's gate zeroes the film if a real person appears without consent | Y chose to show an emperor rather than only imply one. We keep him unnamed, generic in dress, unvoiced and off close-ups, and Y checks every keyframe of him so that none becomes a portrait of Haile Selassie |
| Tesfaye, the honey wine server | A fictional character inspired by the family story | Shown, never voiced (the narrator retells) | No: `real_person: false` | Y chose to treat him as inspired-by, not a portrait; his look is described, not taken from photos |
| Y's grandmother | Mentioned by the narrator as the one who tells the story | Never | No | Not shown or voiced. Y to confirm she's happy for her story to be told |

The scenes are imagined: the end card says the film is inspired by a family story and that some scenes are imagined, so it doesn't pass invention off as history.

## What we send to which endpoint (ADR-013)

| Endpoint | What we send | What we never send |
|---|---|---|
| Gemini API, free tier | The public story brief, narration text, director prompts | Full names beyond first names, addresses, anything in `private/` |
| Cloudflare Workers AI | Image prompts, reference sheets we generated | Family photos, unless a consent row covers that use |
| Kaggle and Colab | Keyframes and motion prompts | Keys or secrets |
| Addis AI (Addis Voices 2), chosen by Y for Amharic (P-0005) | The ten Amharic narration lines, which the film publishes anyway | Anything else. Its Terms (§6, 2026-07-13) let Addis AI use what we send to train models, whatever its FAQ says; a no-training promise needs an enterprise agreement |

## Licences

| Component | Used for | Licence or terms | Checked |
|---|---|---|---|
| Gemini 3.8 Flash and Gemini 3.8 TTS | Script, translation, narration | Gemini API terms; free-tier inputs may be used to improve Google's products | to check |
| FLUX.2 klein 4B on Workers AI | References, keyframes | Apache-2.0 per the brief, and the 4B (not the non-commercial 9B) is the one we used; Cloudflare's service terms apply to the API | 4B licence per the brief; Cloudflare terms not read in full |
| FLUX.1 schnell | Fallback images, never used | Apache-2.0 | not needed: no schnell image is in the film |
| Wan 2.2 TI2V-5B | Moving shots | Apache-2.0 (model card, Hugging Face) | yes, 2026-11-26 |
| ACE-Step 1.5 | Score | MIT for code and weights; its model card says generated music may be used commercially, and its README asks users to check outputs for similarity to existing works | yes, 2026-11-26 |
| FFmpeg (Homebrew `ffmpeg-full` 9.1) | Assembly | A GPL build, because it includes GPL libraries such as libx264. We run it as a tool and don't distribute it; its licence doesn't extend to the videos it encodes | yes, 2026-11-26 |
| Addis Voices 2 (Addis AI), voice am-loza | Amharic narration (P-0005) | Addis AI Terms 2026-07-13: paid API customers may use outputs in their own products (§4); Addis AI assigns us its rights in the output, but not in its voices or models, with no exclusivity (§5); we must disclose AI audio where leaving it out could mislead (§8), which the end card and the platform label do | to check: whether signup credit alone counts as a paid customer |
| DejaVu fonts (`assets/fonts`) | Subtitles, end card | DejaVu / Bitstream Vera licence, free to redistribute (`assets/fonts/LICENSE-DejaVu.txt`) | yes |
| Claude (claude.ai) and Claude Code | Planning; writing the code | Anthropic's terms; named here because the brief asks which coding agent we used | to check |

## Labelling plan

The film ends on a 2–3 s card saying it was made with AI and naming the models. When we post, we switch on the platform's AI-content label. We don't strip watermarks or provenance metadata, such as SynthID in Gemini audio or C2PA where present.
