# GPU work on Kaggle (or Colab)

Moving shots (Wan 2.2 TI2V-5B) and the score (ACE-Step 1.5) need a GPU. They're units with cache keys like everything else, but they're rendered off this machine (ADR-006):

```
uv run film bundle shots        # packs every uncached Wan clip:   build/bundles/shots-<run>.zip
uv run film bundle music        # packs every uncached score take: build/bundles/music-<run>.zip
```

1. On kaggle.com: **Datasets → New Dataset**, upload the zip(s). Kaggle unpacks them.
2. **Code → New Notebook → File → Import Notebook** → `gpu/kaggle_runner.ipynb`.
3. Settings: **Accelerator → GPU T4 x2** (never P100), **Internet → on** (needs a phone-verified account). **Add Input** → your dataset.
4. Set `LIMIT` in the first cell: `1` for a spike (one job per bundle, to measure time and memory), `0` for everything.
5. **Save Version → Save & Run All**. It keeps running after you close the tab; Kaggle allows 12 hours a session and about 30 GPU hours a week.
6. Download `heritage-gpu-out.zip` from the version's Output tab, then:

```
uv run film ingest ~/Downloads/heritage-gpu-out.zip
```

`ingest` accepts a result only if its cache key still matches the storyboard, so a clip for a shot you edited after bundling is reported stale and left out. Every result, failures included, becomes a line in `runs.jsonl` with its GPU seconds, model-load time and peak memory. Until a clip arrives, its shot uses the Ken Burns fallback.

## How the models run on a T4 (checked 2026-11-26)

| | Wan 2.2 TI2V-5B (`runner_wan.py`) | ACE-Step 1.5 (`runner_acestep.py`) |
|---|---|---|
| Code path | diffusers `WanImageToVideoPipeline` (Kaggle's image has diffusers 0.42). The official repo needs FlashAttention 2, which Turing GPUs lack | Its own repo in a Python 3.12 `uv` environment, run as a subprocess (Kaggle is on Python 3.13; ACE-Step needs <3.13) |
| Precision | fp16 transformer (a T4 emulates bf16, about 11x slower), fp32 VAE | fp16, chosen by ACE-Step on pre-Ampere GPUs |
| Memory | Model CPU offload (the text encoder alone is 11 GB), tiled VAE decode | DiT only (turbo, 8 steps); the LM planner needs FlashAttention |
| Download | About 34 GB per session, into `/tmp/hf` | About 10 GB of checkpoints |
| Reported speed | About 8 s per step at 832×480 for a 2 s clip, peak 13 GB (a community run); 121 frames at 50 steps is untested, estimated 17+ minutes a clip | No T4 figure published |
| Licence | Apache-2.0 | MIT; outputs usable commercially |

Spike S1 (Wan) and S2 (ACE-Step) are the first real runs. Their measured times go into COSTS.md and EXPERIMENTS.md (E7), and decide how many shots get real motion.
