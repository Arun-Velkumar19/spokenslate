# SpokenSlate: agent handoff

Read this before touching code. It applies to every coding agent (Codex, Claude Code, etc.).
Owner: Roon (solo). Meta Global AI Developer Hackathon, Indie track.
**Submission deadline: Nov 4, 2026, 7:00 PM Arizona (9:00 PM ET).** Target: submitted by early afternoon.

Product name **SpokenSlate**; repo, package, and CLI `spokenslate`. The project pivoted from
PaperOS on Oct 27 (briefly called "Seed"). Env vars are `SPOKENSLATE_*`; the old `SEED_*` /
`PAPEROS_*` names are still read as fallbacks so existing `.env` files keep working.

## What this is

A board-aware lecture transcript. A whiteboard lecture is two streams: what's **said** and
what's **written**. Transcripts keep only the first. SpokenSlate takes a recorded lecture clip and
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
audio ──► faster-whisper ───► words w/ timestamps ──► reference phrases       Timeline (ids, times,
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
  Updates keep the text they replace (`TimedElement.versions`); the page shows a version
  only when it was replaced, not merely continued.
- **Offline only.** Recorded clips in, static pages out. No live classroom mode.
- **Bounded spend.** No per-frame model calls; keyframes have a min gap; ≤2 attempts per
  call; escalation to Wonder at most once per phrase; SAM only on candidate keyframes
  (upload + segment, 1 attempt, failure = unmasked frame). Log calls.
- **Footage rights.** Only commit your own recordings or openly licensed lectures (e.g.
  MIT OCW, CC BY-NC-SA, with credit). Never commit YouTube downloads. `data/` is gitignored.
- **No scope creep:** no slides, no live mode, no dictation/two-way, no translation, no
  hosted upload backend (stretch only, after Nov 1). Ask Roon before adding a dependency.

## Status (keep this section current)

| Module | State |
|---|---|
| `spec.py`, `timeline.py`, `references.py`, `pointing.py`, `validator.py`, `render.py` | done, tested |
| `mathml.py` (used by `render.py`) | math steps render as MathML (`latex2mathml`, re-parsed against a MathML allowlist; unsafe or unknown LaTeX falls back to escaped code); `alttext` = plain reading; VoiceOver (Safari, Oct 30): MathML matrices read as a navigable table **but `\boxed` is dropped**, so each step leads with the plain reading (never `aria-hidden`), then MathML, then LaTeX in `<details>`; text steps shown once; reference-note quotes spoken via `mathml.speakable` ("0, boxed 2, minus 2") and step readings cut to 80 chars |
| `pipeline.py`, `video.py`, `main.py` CLI | done, tested with fake models + a real mp4 |
| `models/muse.py`, `models/prompts.py` | board read verified live Oct 28 (chat.completions, JPEG `image_url` data URL, `muse-spark-1.3` at `https://api.meta.ai/v1` → valid `BoardDiff`, 9.2s); `scripts/smoke_api.py IMAGE` packages that one call (logs the request minus key/bytes, raw reply, latency, parse); first full live run Oct 29 on an OCW 18.06 clip: 28 board + 15 resolve calls, 0 invalid JSON (see `eval/results/2026-10-29-strang-first-run.csv`) |
| `scoring.py` + `scripts/score.py` | scores a LectureDoc against `eval/references.csv` (time window + phrase text; truth = element id or written referent) → correct / unresolved / wrong / confident-wrong, plus a plain-transcript baseline; tested on synthetic data; **not yet run on a real pipeline output** (CSV still empty) |
| `models/transcribe.py` + `scripts/transcribe.py` | words from local **faster-whisper** (`word_timestamps=True`, VAD, `small.en`); `scripts/transcribe.py VIDEO --out words.json`; `process` without `--words` transcribes and saves `<out>/<stem>.words.json`; verified on real speech Oct 29 (45 s clip → 115 words, first word at 0.98 s; `av<19` required) |
| `models/segment.py` | **SAM 3.1 verified Oct 30** (playground + 1 API call): upload frame (`/v1/files`) → `/v1/responses` with `sam-3.1`, "person" + file id → `<|box…|><|mask…|>` text, decoded with Meta's `meta-sam-parser`; real response kept as `tests/data/sam_person_480x352.txt`. `MetaSAM` on by default (`--no-sam` to skip; 2 calls per candidate keyframe; uploaded frame deleted after). Pipeline gate: candidate keyframe whose board (lecturer masked out, brightness-matched) didn't change since the last read → Muse read skipped (synthetic walking lecturer: 18 → 3 reads). Live Nov 1 on Roon's iPhone clip: 0 skipped of 52, because auto-exposure swung the whole frame (wall grey 165–232) → gain normalization added; **real savings not yet measured** |
| `sensing/hand.py` + `scripts/page_preview.py --hand` + `scripts/fingertips.py` | MediaPipe Tasks fingertip (landmark 8) + hand presence; `scripts/fingertips.py VIDEO --out fingertips.json [--fps 10]` writes the frame-normalized `[[t, u, v], ...]` track for `process --fingertips` (reads frames sequentially via `video.iter_frames`); tested with a fake detector + synthetic mp4 through the process CLI and pointing; **not yet run on a real lecture clip or camera** |
| `calibration/page.py` | from PaperOS; page detection for camera setups (lecture video uses frame coords, see gotchas) |

Plan, gates, calendar: `docs/PLAN.md`. Demo: `docs/DEMO.md`. Prior art: `docs/PRIOR_ART.md`.

## Layout

```
src/spokenslate/
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
python -m pip install -e ".[dev]"
chflags nohidden .venv/lib/python3*/site-packages/*.pth   # macOS only, see gotchas
pytest -q && ruff check src tests scripts          # both must pass before every commit
python -m spokenslate process clip.mp4 --words words.json --out site/ --title "..." --source "credit"
python -m spokenslate render site/clip.json --out site/clip.html
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

- **Muse Voice Transcribe can't give word times (checked Oct 29).** It is realtime WebSocket
  only (`wss://api.meta.ai/v1/asr/realtime`); `POST /v1/audio/transcriptions` returns 404;
  the playground's Diarization/Endpointing modes give ~20 s turns at whole-second times.
  Words come from local faster-whisper instead. Don't retry the batch endpoint.
- **Camera-operated lectures break the fixed-view assumption** (OCW 18.06: 98 cuts in 47 min,
  slow zooms between cuts). Each zoom re-reads the same rows as new elements (duplicates →
  the resolver rightly abstains) and can mark rows "erased". Test and demo on fixed-camera
  footage; camera-motion handling is out of scope unless Roon decides otherwise.
- **Matrices are one element** (board prompt, Oct 29; rows are quoted with their `&`).
  Scored on the Strang clip: correct links 4 → 6, confident-wrong 1 → 1 (a different,
  debatable case), duplicates gone. Still open: a matrix written row by row (U) comes out as
  separate row elements, and camera zooms still cause false "erased".
- `objc: Class AVFFrameReceiver is implemented in both ...cv2... and ...av...` on macOS is a
  warning (OpenCV and PyAV both bundle FFmpeg). Runs completed fine; note it if a crash appears.
- **Muse calls run at temperature 0** (Nov 1). The playground default is 1, so earlier runs
  (Oct 29–30) were single random samples: a ±1 change between them may be noise. Benchmark
  numbers come from temperature-0 runs.
- **Word timestamps are essential.** A point lines up with the words being said at that
  instant, not the whole sentence ("the problem I just gave you" vs "this problem" in one
  caption line meant opposite things). Captions-per-frame aren't enough.
- **Offline is an advantage:** later frames can resolve earlier references (the model used
  frame 3 to resolve frame 1). Keep the lookahead.
- **A wiped-and-rewritten line can come back as an update instead of an erase** (Nov 3
  mini clip, two runs at temperature 0: run 1 replaced the wrong f′(x) in place, run 2
  reported the erase). Temperature 0 is not fully deterministic. Updates keep `versions`,
  so either way the wiped attempt survives; the page shows a version only if the new text
  no longer contains it (a hand-covered partial read like "(x) =" is not a change).
- **Small handwriting gets misread.** Portrait phone video, board ~half the frame width:
  the wrong attempt `f'(x) = x^3 ln x · 1/x` was read as `f(x)=x^3 \ln x` (a copy of line 1).
  Frames go to Muse at 1280 px on the long side; film landscape with the board filling it.
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
- **macOS hides the editable-install `.pth` file** (seen on Python 3.12 and 3.14 venvs), so
  `No module named spokenslate` right after a successful `pip install -e`. Fix after every
  install: `chflags nohidden .venv/lib/python3*/site-packages/*.pth`. Use `python -m pip`.
- **MediaPipe 1.x removed `mp.solutions.hands`.** Use Tasks API `HandLandmarker`. The model
  file `models/hand_landmarker.task` is gitignored; download it from the
  [MediaPipe hand landmarker models](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models).
- Meta Model API base URL `https://api.meta.ai/v1` (per LiteLLM docs). Confirm with the
  playground's "Get code", incl. image message format and JSON mode.

## When unsure

Prefer the smallest change that keeps the invariants. If a task would change the contracts,
loosen the validator, widen scope, or add a dependency, stop and ask Roon.
