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
| E7 | How much GPU time does 480p save over 720p, and at what cost? | planned (spike S1) |
| E8 | Do motion-only prompts beat re-describing the subject? | planned |
| E9 | Can a square master serve both orientations? | planned (spike S1) |
| E10 | Which score candidate works under the voice, and why? | planned |
| E11 | Do the brief's ducking defaults suit our voice? | planned |
| E12 | Does normalising each stem first make mixing easier? | planned |
| E13 | Does the critic agree with Y's blind picks often enough to delegate keyframe pins? | planned (A3); its result sets the autonomy |
| E14 | Do viewers prefer real motion for people but not for places? | planned (test 2) |
| E15 | Does the same meaning run longer in Amharic than in English? | planned |
| E16 | Does respelling a name fix an Amharic mispronunciation? | planned |
| E17 | How many characters per subtitle line fit each orientation? | done, 2026-11-25 |
| E18 | Does a staged story chain need fewer corrections than drafting in one call? | planned (A2) |
| E19 | Does the critic's ranking change with the order candidates are shown in? | planned (A3) |
| E20 | Does feeding the critic's reasons back raise the next round's acceptance? | planned (A3) |

## E17: subtitle line length per orientation (2026-11-25)

Hypothesis. The brief's guide of about 40 characters per line works in both orientations.

Change. The same subtitles were burned into the vertical (720×1280) and horizontal (1280×720) mock exports, first at 42 characters per line, then at 28 for vertical only. Seed fixed; mock workspace.

Evidence. On a frame grab of the vertical film at 10.5 s, libass re-wrapped the 38-character first line, so the card showed three lines. That breaks the two-line rule. Measured on the same frame, DejaVu Sans at FontSize 11 is about 22 px per character (0.45 em). That leaves room for about 30 characters inside the vertical margins. At FontSize 9, with 40-unit side margins, 28 characters fit on two lines, clear of the bottom fifth and the right edge where phone apps draw buttons. Horizontal frames fit 42 characters on two lines at FontSize 15.

Result. Rejected for vertical. Line length is now per orientation (`config/pipeline.toml`: 28 vertical, 42 horizontal), with one SRT per orientation. A test checks that no line exceeds its limit and no card holds more than two lines.

Follow-up. The first fix left a one-word card ("evening.") on screen for 0.4 s. The chunker now picks the fewest cards with the most even lengths and prefers breaking after commas. A test checks that no card is shorter than eight characters.
