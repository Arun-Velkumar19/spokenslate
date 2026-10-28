# Seed: agent handoff

Read this before touching code. It applies to every coding agent (Codex, Claude Code, etc.).
Owner: Roon (solo). Meta Global AI Developer Hackathon, Indie track.
**Submission deadline: Nov 4, 2026, 7:00 PM Arizona (9:00 PM ET).** Target: submitted by early afternoon.

"Seed" is a working name; the Python package is still `paperos` (the project pivoted from
PaperOS on Oct 27). A rename is one PR once the name is picked. Don't rename on your own.

## What this is

A board-aware lecture transcript. A whiteboard lecture is two streams: what's **said** and
what's **written**. Transcripts keep only the first. Seed takes a recorded lecture clip and
produces an accessible web page where:
1. each line written on the board appears, as math, at the moment it was written
2. spoken references ("this term cancels", "the first", "the problem I just gave you")
   link to the exact thing on the board, or say "unresolved" when unsure
3. erased steps are kept

Primary user: blind and low-vision students (the board is a dead end for them). Operator:
a university accessibility office, or anyone with the recording. The student only reads
the output page with a screen reader.

Evidence it works (Oct 27, playground): `muse-spark-1.3` resolved 10/10 references on
Professor Leonard's Calc 2 lecture, incl. one hidden under his hand. See `eval/results/`.

## Pipeline

```
video ──► thumbnails ──► keyframes (board changed) ──► SAM 3.1 masks lecturer ──► Muse: BoardDiff
                                                                                       │
audio ──► Voice Transcribe ──► words w/ timestamps ──► reference phrases       Timeline (ids, times,
                                       │                                         erased kept)
fingertip track (hand.py) ──► pointing candidates ──┐          │                      │
                                                    ▼          ▼                      ▼
                                   Muse: ResolveOutput (3 frames + words per frame + board elements)
                                                    │
                                     validator (fails toward "unresolved")  ──► LectureDoc ──► HTML
```

## Invariants (do not break)

- **A confident wrong answer is the worst outcome.** Every check fails toward
  "unresolved". Never loosen the validator to raise the resolved count.
- **The model never sets times or permanent ids, and never emits code.** It returns
  `BoardDiff` / `ResolveOutput` JSON. The pipeline assigns ids (`e1, e2, ...`) and times.
- **Validator gates every resolution** (`validator.validate_resolution`): unknown id,
  element not on the board then, quote mismatch, low confidence → unresolved.
- **Erased content is kept** (`TimedElement.erased_at`), never deleted. Ids never reused.
- **Offline only.** Recorded clips in, static pages out. No live classroom mode.
- **Bounded spend.** No per-frame model calls; keyframes have a min gap; ≤2 attempts per
  call; escalation to Wonder at most once per phrase. Log calls.
- **Footage rights.** Only commit your own recordings or openly licensed lectures (e.g.
  MIT OCW, CC BY-NC-SA, with credit). Never commit YouTube downloads. `data/` is gitignored.
- **No scope creep:** no slides, no live mode, no dictation/two-way, no translation, no
  hosted upload backend (stretch only, after Nov 1). Ask Roon before adding a dependency.

## Status (keep this section current)

| Module | State |
|---|---|
| `spec.py`, `timeline.py`, `references.py`, `pointing.py`, `validator.py`, `render.py` | done, tested |
| `pipeline.py`, `video.py`, `main.py` CLI | done, tested with fake models + a real mp4 |
| `models/muse.py`, `models/prompts.py` | board read verified live Oct 28 (chat.completions, JPEG `image_url` data URL, `muse-spark-1.3` at `https://api.meta.ai/v1` → valid `BoardDiff`, 9.2s); `scripts/smoke_api.py IMAGE` packages that one call (logs the request minus key/bytes, raw reply, latency, parse); `resolve` **not yet run against the live API** |
| `scoring.py` + `scripts/score.py` | scores a LectureDoc against `eval/references.csv` (time window + phrase text; truth = element id or written referent) → correct / unresolved / wrong / confident-wrong, plus a plain-transcript baseline; tested on synthetic data; **not yet run on a real pipeline output** (CSV still empty) |
| `models/transcribe.py` | `load_words` works; Muse transcription **unverified** (word timestamps?) |
| `models/segment.py` | `NullSegmenter` only; SAM 3.1 API shape **unverified** |
| `sensing/hand.py` + `scripts/page_preview.py --hand` + `scripts/fingertips.py` | MediaPipe Tasks fingertip (landmark 8) + hand presence; `scripts/fingertips.py VIDEO --out fingertips.json [--fps 10]` writes the frame-normalized `[[t, u, v], ...]` track for `process --fingertips` (reads frames sequentially via `video.iter_frames`); tested with a fake detector + synthetic mp4 through the process CLI and pointing; **not yet run on a real lecture clip or camera** |
| `calibration/page.py` | from PaperOS; page detection for camera setups (lecture video uses frame coords, see gotchas) |

Plan, gates, calendar: `docs/PLAN.md`. Demo: `docs/DEMO.md`. Prior art: `docs/PRIOR_ART.md`.

## Layout

```
src/paperos/
  spec.py          Word, BoardElement/Diff, TimedElement, ReferencePhrase, ResolveOutput,
                   Resolution, LectureDoc
  timeline.py      apply BoardDiffs atomically; alive_at / alive_during; erased kept
  references.py    find "this term" / "the first" / "the problem I just gave you" (high recall)
  pointing.py      fingertip samples -> ranked candidate elements
  validator.py     ResolveOutput -> Resolution; the hallucination guard
  scoring.py       LectureDoc vs eval/references.csv: correct / unresolved / wrong / conf-wrong
  render.py        accessible HTML (headings per step, links, unresolved marked, escaped)
  pipeline.py      orchestration behind Protocols (BoardReader, Resolver, Segmenter)
  video.py         VideoFile, iter_frames, extract_audio (ffmpeg), keyframe selection, jpeg
  models/          muse.py (board + resolve), prompts.py, transcribe.py, segment.py
  calibration/     page/board detection (PaperOS); sensing/hand.py fingertip tracking
  main.py          CLI: process / render
tests/             pytest, no API/camera needed (fixtures.py = Leonard test data)
eval/              reference benchmark CSVs + results
docs/              PLAN, DEMO, PRIOR_ART
```

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q && ruff check src tests scripts          # both must pass before every commit
python -m paperos process clip.mp4 --words words.json --out site/ --title "..." --source "credit"
python -m paperos render site/clip.json --out site/clip.html
```
`ffmpeg` must be installed for audio extraction (`brew install ffmpeg`).

## Conventions

- **Branch per task, PR into `main`.** Never push to `main`. Branch `<agent>/<task>`.
- **One agent per module.** Check `gh pr list` first; don't edit files another open PR
  touches. Contract changes (`spec.py`, `validator.py`, Protocols in `pipeline.py`) go in
  their own small PR.
- **Tests with every change**, runnable without API/camera. Model calls go through the
  Protocols so tests use fakes (see `tests/test_pipeline.py`).
- **Prompt changes** (`models/prompts.py`) must be re-scored on the reference benchmark
  (`eval/references.csv`) in the same PR, with the before/after numbers in the PR text.
- Python 3.11+, type hints, ruff line length 100. Small modules, no frameworks.
- Update the Status table and `docs/PLAN.md` checklist in the same PR.
- Never commit `.env`, keys, raw video/audio, or downloaded lectures.

## Gotchas already found (don't rediscover them)

- **Word timestamps are essential.** A point lines up with the words being said at that
  instant, not the whole sentence ("the problem I just gave you" vs "this problem" in one
  caption line meant opposite things). Captions-per-frame aren't enough.
- **Offline is an advantage:** later frames can resolve earlier references (the model used
  frame 3 to resolve frame 1). Keep the lookahead.
- **Hidden ≠ erased.** The lecturer's body covers the board constantly. The board prompt
  says so; the timeline only erases on explicit model `erased`.
- **Real video files:** the last frame is at `duration - 1/fps`; `VideoFile.frame_at` clamps.
- **Lecture video ≠ paper page:** the board usually fills/exceeds the frame, and
  `calibration.page.detect_quad` rejects quads touching the frame edge. For lecture clips
  use frame-normalized coords as board coords (fixed camera). Rectification is optional.
- **Playground:** "referenced response not found or expired" = stale chat; click New chat.
  Crop screenshots to the video (full-browser screenshots shrink the handwriting).
- **Avoid `-contributor` model variants** until we know what they do with data. Free
  credits: Meta notes content may be used for product improvement.
- **MediaPipe 1.x removed `mp.solutions.hands`.** Use Tasks API `HandLandmarker`. The model
  file `models/hand_landmarker.task` is gitignored; download it from the
  [MediaPipe hand landmarker models](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models).
- Meta Model API base URL `https://api.meta.ai/v1` (per LiteLLM docs). Confirm with the
  playground's "Get code", incl. image message format and JSON mode.

## When unsure

Prefer the smallest change that keeps the invariants. If a task would change the contracts,
loosen the validator, widen scope, or add a dependency, stop and ask Roon.
