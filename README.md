# AI Content Generation: The Heritage Short

The 10 Academy B2W0 challenge. The project lives in [`heritage-short/`](heritage-short/): a pipeline that turns one `storyboard.json` into a 60–90 second film, with a team of agents that drafts the story and proposes every change, and a person who approves at gates.

```
cd heritage-short
make setup      # Python 3.12 + dependencies via uv; FFmpeg with libass (macOS: brew install uv ffmpeg-full)
make film       # rebuilds all four films from the committed cache: zero model calls, no keys, no GPU
```

Start with [`heritage-short/README.md`](heritage-short/README.md), then `ARCHITECTURE.md`, `DESIGN.md`, `EXPERIMENTS.md`, `FAILURES.md`, `COSTS.md` and `ETHICS.md` in the same folder.
