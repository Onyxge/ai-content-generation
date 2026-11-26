# The Heritage Short: "The Last Pour"

A small studio in code. `storyboard.json` goes in; a 60–90 second film comes out, narrated in English and Amharic, with English subtitles, an original score ducked under the voice and an AI end card, in 9:16 and 16:9. A team of agents drafts the story and proposes every change, and a person approves at gates. Built for 10 Academy's B2W0 challenge.

**The film.** *The Last Pour* (Amharic, the main version, 76.7 s; English 73.8 s) is inspired by a story the author's grandmother tells. A server who poured honey wine at an emperor's palace for years, unnoticed, is called by his name for one night. The scenes are imagined, and the end card says so.

**Status (Thu 26 Nov 2026).** All four exports are built from the cache: English and Amharic, each in 9:16 and 16:9.
- Shots: ten. Two have Wan 2.2 motion (s02, s06); eight use Ken Burns.
- Score: ACE-Step 1.5, take m1.13, anchored per language.
- Narration: Gemini 3.8 TTS in English, Addis Voices 2 in Amharic.
- Tests: 82 pass.
- The full record: what was decided (`decisions.jsonl`, `proposals/`), what was called (`runs.jsonl`), what broke (`FAILURES.md`) and what was measured (`EXPERIMENTS.md`, `COSTS.md`).

## How it works, in one picture

```
docs/story/brief.md + DESIGN.md intent
   │  story agent (Gemini): outline → beats ─ gate G1 (Y) ─ shots → narration → Amharic
   ▼
storyboard.json  ◄── every later change is a proposal (JSON Patch by id), checked for ownership,
   │                 schema, lint and consent, and approved by Y or by its autonomy setting
   │                 (decisions.jsonl)
   │  make film: a pure function of storyboard.json + the cache; agents never run here
   ├─ references, keyframes ─── Cloudflare FLUX.2 klein
   ├─ narration ─────────────── Gemini 3.8 TTS (en), Addis Voices 2 (am)
   ├─ music, Wan clips ──────── film bundle → Kaggle T4 (gpu/runner.py) → film ingest
   └─ assemble (FFmpeg) ─────── timing fitted to the voice, ducking, subtitles, loudness, end card, 4 exports
every model call → runs.jsonl · every stage → stages.jsonl · every decision → decisions.jsonl
```

ARCHITECTURE.md explains it properly. The reasoning behind each choice is in `docs/decisions.md` (ADR-001 to ADR-019).

## Rebuild the film

You need Python 3.11+, [uv](https://docs.astral.sh/uv/) and an FFmpeg build with libass on your PATH. On macOS that's `brew install uv ffmpeg-full`: Homebrew's slim `ffmpeg` formula can't burn in subtitles (FAILURES.md F2). `ffmpeg-full` installs off PATH (keg-only), and the pipeline finds it there. `make film` checks for every filter it needs before it starts.

    make setup     # install dependencies
    make film      # validate → render whatever changed → assemble every language and orientation

Every generated asset is committed in `outputs/` next to a sidecar holding its cache key. On a fresh clone, `make film` therefore makes **zero model calls** and needs no keys or GPU: it re-renders the Ken Burns clips and assembles the films with FFmpeg. This was checked on 2026-11-26: the committable files only, no `.env`, keys unset; four films; runs.jsonl unchanged (re-checked after the final cut at 20:05: 108 lines before and after). To regenerate an asset, change it in `storyboard.json` and add keys to `.env` (see `.env.example`); `make plan` shows exactly what will be regenerated before anything is spent.

## Make the film again, or change it

```
make plan                      # what would be generated, and how many model calls; spends nothing
uv run film render             # generate whatever changed (needs keys in .env for the hosted models)
make film                      # render, then assemble all four exports into outputs/final/
```

Change one narration line or one image prompt in `storyboard.json`, and `make plan` names exactly the units it affects. The walkthrough demo is that single change (`docs/walkthrough.md`). GPU work (Wan clips and score takes) goes through Kaggle:

```
uv run film bundle shots       # packs the uncached GPU jobs
uv run film kaggle push        # private dataset + private notebook on GPU T4 x2 (needs KAGGLE_API_TOKEN)
uv run film kaggle status
uv run film kaggle pull        # downloads the results and ingests them into the cache
```

`gpu/README.md` has the manual route through the Kaggle UI. Making a new film from your own story is `make storyboard` (the story agent) followed by the same commands; see "The story agent" below.

## Try it without keys

    make mock      # the whole pipeline on placeholder providers, written to build/mock/
    make test      # unit tests plus a full mock build, including the one-edit-one-call check

## Commands

| Command | What it does |
|---|---|
| `make smoke` | One tiny logged call to each provider (Gemini text, Gemini TTS, Cloudflare FLUX) plus an FFmpeg filter check; once a day, then cached |
| `make storyboard` | The story agent: `docs/story/brief.md` and DESIGN.md's intent → outline and beats (stop for Y, gate G1) → shots, narration, Amharic → a draft storyboard Y adopts as v1 (`--adopt`, gate G2) |
| `make validate` | Schema, lint and consent gate on `storyboard.json` |
| `make plan` | Dry run: what would be generated and how many model calls that costs |
| `make render` | Generate whatever changed, nothing else |
| `make radio` | The user-test prototype: narration over a temp drone on black, with English subtitles |
| `make film` | Render, then assemble everything |
| `make test` | Tests and a full mock build |
| `uv run film kaggle push` / `status` / `pull` | Run the GPU bundles on a private Kaggle notebook (GPU T4 x2), check on it, then download and ingest its results. Needs `KAGGLE_USERNAME` and `KAGGLE_API_TOKEN` in `.env`; see `gpu/README.md` |
| `make proposals` | What the agents have proposed that waits for Y (ADR-018) |
| `uv run film approve P-0007` / `reject` / `revert` | Decide on a proposal; every decision goes to `decisions.jsonl` |

Each wraps `uv run film <command>`, so everything works without make too. Add `MOCK=1` to run any of them on the example storyboard with placeholder providers.

## Where to read more

ARCHITECTURE.md explains the stages, the contract, caching and failure handling. DESIGN.md holds the audience, the intent and the user tests. The plan, the decision log and the build log live in `docs/`. EXPERIMENTS.md, FAILURES.md, COSTS.md and ETHICS.md hold what the brief asks for.

## The story agent

`make storyboard` reads `docs/story/brief.md` (from `docs/story/brief.template.md`) and DESIGN.md's audience and intent. It drafts an outline and beats, then stops for you at gate G1. `film storyboard --approve-beats` continues to shots, narration and the Amharic translation. `film storyboard --adopt` makes the assembled draft `storyboard.json` (gate G2). Every step is cached and logged, your edits to any draft are kept, and the steps after an edit rerun. After v1, changes are proposals: `film proposals`, `film approve P-0007`, `film reject`, `film revert`.

## What it costs

`make costs` regenerates COSTS.md's tables from the logs. For this film:
- **Model calls:** 106 attempts, 81 of them successful, every failure logged and explained in FAILURES.md.
- **GPU:** about 142 Kaggle T4 minutes. Wan took about 29–34 min per 5 s clip; the score took about 26 s per 86 s take.
- **Money:** $0 actually paid (free tiers, plus a few birr of Addis AI credit). Images priced at Cloudflare's list rate come to about $0.15; the other providers are left unpriced where no price was checked.
