# The Heritage Short

A small studio in code. `storyboard.json` goes in; a 60–90 second family film comes out, narrated in English and Amharic, with English subtitles, an original score ducked under the voice and an AI end card, in 9:16 and 16:9. Built for 10 Academy's B2W0 challenge.

**Status (Wed 25 Nov 2026):** the contract, the cache-and-logging engine, Ken Burns shots and the full assembly (ducking, subtitles, loudness, end card, both orientations, both languages) run end to end on mock providers, and the tests prove that one edit to the storyboard causes exactly one new model call. The real providers (Gemini, Cloudflare, the Kaggle/Colab GPU runner) are unit U3. After that comes the agent layer (ADR-017 to ADR-019): a team of agents that drafts the story and explores, judges and pins the pictures, with Y approving at gates. Our own story's storyboard is built through it. Progress is logged in `docs/build-log.md`.

## Rebuild the film

You need Python 3.11+, [uv](https://docs.astral.sh/uv/) and FFmpeg on your PATH.

    make setup     # install dependencies
    make film      # validate → render whatever changed → assemble every language and orientation

Every generated asset is committed in `outputs/` next to a sidecar holding its cache key. On a fresh clone, `make film` therefore makes **zero model calls** and needs no keys or GPU: it re-renders the Ken Burns clips and assembles the films with FFmpeg. To regenerate an asset, change it in `storyboard.json` and add keys to `.env` (see `.env.example`); `make plan` shows exactly what will be regenerated before anything is spent.

## Try it without keys

    make mock      # the whole pipeline on placeholder providers, written to build/mock/
    make test      # unit tests plus a full mock build, including the one-edit-one-call check

## Commands

| Command | What it does |
|---|---|
| `make validate` | Schema, lint and consent gate on `storyboard.json` |
| `make plan` | Dry run: what would be generated and how many model calls that costs |
| `make render` | Generate whatever changed, nothing else |
| `make radio` | The user-test prototype: narration over a temp drone on black, with English subtitles |
| `make film` | Render, then assemble everything |
| `make test` | Tests and a full mock build |

Each wraps `uv run film <command>`, so everything works without make too. Add `MOCK=1` to run any of them on the example storyboard with placeholder providers.

## Where to read more

ARCHITECTURE.md explains the stages, the contract, caching and failure handling. DESIGN.md holds the audience, the intent and the user tests. The plan, the decision log and the build log live in `docs/`. EXPERIMENTS.md, FAILURES.md, COSTS.md and ETHICS.md hold what the brief asks for.

## What it costs

COSTS.md is generated from the logs by `film costs` (unit U9, not built yet). Every model call is already logged in `runs.jsonl` with its latency, seed and cache key.
