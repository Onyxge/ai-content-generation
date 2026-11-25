# ETHICS

Consent, labelling and licences. The pipeline reads the consent table below. A character marked `real_person: true` can't be generated until its consent id appears here with every cell filled in (ADR-014).

## Consent record

One row per real person shown or voiced, filled in before anything of them is generated. The evidence itself (a voice note, a message) stays in `private/`, never in the repo.

| ID | Person (role in the film) | Who gave consent | Scope: likeness, voice, words | Date | How it was recorded |
|---|---|---|---|---|---|
| C1 | … | … | … | … | … |

Our narrator is a prebuilt Gemini TTS voice, not a clone of anyone's voice. Where the narration speaks about a real person, they (or close family) approved the script; the Scope cell says so.

## What we send to which endpoint (ADR-013)

| Endpoint | What we send | What we never send |
|---|---|---|
| Gemini API, free tier | The public story brief, narration text, director prompts | Full names beyond first names, addresses, anything in `private/` |
| Cloudflare Workers AI | Image prompts, reference sheets we generated | Family photos, unless a consent row covers that use |
| Kaggle and Colab | Keyframes and motion prompts | Keys or secrets |

## Licences

| Component | Used for | Licence or terms | Checked |
|---|---|---|---|
| Gemini 3.8 Flash and Gemini 3.8 TTS | Script, translation, narration | Gemini API terms; free-tier inputs may be used to improve Google's products | to check |
| FLUX.2 klein 4B on Workers AI | References, keyframes | Apache-2.0 per the brief; Cloudflare's terms | to check |
| FLUX.1 schnell | Fallback images | Apache-2.0 | to check |
| Wan 2.2 TI2V-5B | Moving shots | Apache-2.0 | to check |
| ACE-Step 1.5 | Score | MIT; outputs usable commercially | to check |
| FFmpeg | Assembly | LGPL or GPL, depending on the build | to check |
| DejaVu fonts (`assets/fonts`) | Subtitles, end card | DejaVu / Bitstream Vera licence, free to redistribute (`assets/fonts/LICENSE-DejaVu.txt`) | yes |
| Claude (claude.ai) and Claude Code | Planning; writing the code | Anthropic's terms; named here because the brief asks which coding agent we used | to check |

## Labelling plan

The film ends on a 2–3 s card saying it was made with AI and naming the models. When we post, we switch on the platform's AI-content label. We don't strip watermarks or provenance metadata, such as SynthID in Gemini audio or C2PA where present.
