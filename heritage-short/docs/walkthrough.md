# Walkthrough script (at most 5 minutes)

The brief asks for three things: the architecture, one hard decision, and one shot regenerated live. Rehearse once; the live part costs one Gemini TTS call. The free cap is about 10 a day and resets at 11:00 EAT (FAILURES.md F5), so check `make plan` before recording.

## 0:00–0:40 · The film and who it's for

Play the first 15 seconds of `outputs/final/film_en_9x16.mp4`.
- *The Last Pour*: a palace server who poured honey wine for an emperor, unnoticed for years, is called by his name for one night. It's inspired by a story my grandmother tells, for Ethiopians on social media, and it should leave them with the dignity of the people history doesn't name.
- English and Amharic, vertical and horizontal.

## 0:40–2:00 · The architecture

Open `ARCHITECTURE.md`, or the diagram in `README.md`.
- **One contract.** `storyboard.json` is the only thing the stages share, validated by a schema, a lint and a consent gate before anything runs.
- **A cache keyed by inputs.** Every image, line, clip and take sits next to a sidecar holding a hash of everything that made it. `make film` regenerates only what changed. From a clean clone it makes zero model calls.
- **Agents propose, the pipeline renders.** Show `decisions.jsonl` and one file in `proposals/`, for example P-0007. Agents never write the storyboard or call a model inside `make film`. They file JSON Patches, checked for ownership, schema and consent, and approved by me. Eight decisions shaped this film; I rejected one (P-0004).
- **GPU off the laptop.** `film kaggle push` runs the Wan and ACE-Step jobs on a free Kaggle T4, and `film kaggle pull` brings them back into the same cache.

## 2:00–3:00 · One hard decision (pick one)

- **The emperor.** The brief scores the film zero if a real person appears without recorded consent, and a man who died in 1975 can't give it. He became "the great emperor": unnamed, fictional, never voiced, never in close-up. A consent check at the shot step refuses any frame that puts an unconsented real person on screen (ETHICS.md, FAILURES.md F10 context).
- **Wan on a free T4.** Three runs each failed on a different limit: GPU memory, then host RAM (the OS killed the process), then our own glue code. The fourth worked: about 29 GPU minutes per 5 s clip, peak 5.75 GB (FAILURES.md F7–F9). Then two of four clips were rejected on review (EXPERIMENTS.md, "Wan on people").
- **The score in two languages.** I picked a take because it goes quiet under the grandmother line. Amharic runs 6% longer, which moved the silence, so the score is anchored to the shot per language (E15, P-0006).

## 3:00–4:30 · Regenerate one shot live

Shot s08's line reads awkwardly ("Hearing Tesfaye, he raised a toast…"), so the live edit also improves the film.

1. In `storyboard.json`, change `shots[s08].narration.en` to:
   `He answered, "Tesfaye." The emperor raised a toast, and the whole hall lifted their glasses.`
   That's 15 words, inside the 16-word budget for an 8-second shot.
2. `make plan`: it names exactly one unit, `narration s08.en`, one model call. Point out that the Amharic line, the pictures and the music all stay cached.
3. `uv run film render --stage narration --lang en`, then `tail -n 1 runs.jsonl`: one new line, with its model, latency and cache key. Pause the recording while it runs if you like.
4. `uv run film assemble --lang en --orient vertical`, then play s08 (about 49–57 s) to hear and read the new line.

## 4:30–5:00 · What I learned

Choose one: orchestration with judgement is the work, more than any single model call. Or: look at the output, because 82 passing tests couldn't see triplets in a keyframe or heads cut off in the 16:9 cut.
