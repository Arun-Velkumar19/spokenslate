# Seed (working name)

**A lecture is two streams: what's said and what's written. Transcripts keep only one.**

Seed turns a recorded whiteboard lecture into an accessible page: every board step as math,
at the moment it was written, with spoken references like *"this term cancels"* linked to
the exact thing on the board. When it isn't sure, it says so. Erased steps are kept.

Built first for blind and low-vision students, for whom "this term" is a dead end.

> Status (Oct 27, 2026): core pipeline built and tested on fake models and real video files.
> Live Meta API wiring is next. Playground evidence: `muse-spark-1.3` resolved 10/10 spoken
> references on a real calculus lecture (`eval/results/`).

## How it works

| Step | Meta model | Job |
|---|---|---|
| Lecturer masking | SAM 3.1 | so the board is read even when the professor stands in front of it |
| Board reading | Muse Spark | each written line → LaTeX + plain-language reading, tracked over time |
| Speech | Muse Voice Transcribe | words with timestamps |
| Reference resolution | Muse Spark (Wonder as fallback) | "this term" → the specific board element, with evidence + confidence |

Deterministic code assigns ids and times, finds reference phrases, ranks pointing candidates
from fingertip tracking, and **validates every answer**: an invented element, a quote that
doesn't match the board, or low confidence all become "unresolved", never a guess.

## Use

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # add META_API_KEY
pytest -q

python -m paperos process lecture.mp4 --words words.json --out site/ \
  --title "Calculus 2, 6.1" --source "credit line"
```

Output: `site/lecture.html` (the accessible page) and `site/lecture.json` (everything,
including evidence for each resolved reference).

## Pointing (hand tracking)

Fingertip tracking (MediaPipe Tasks) gives the resolver ranked candidates for what the
lecturer is pointing at. Download `hand_landmarker.task` from the
[MediaPipe models page](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models)
into `models/` (gitignored). Live check with a webcam:

```bash
python scripts/page_preview.py --hand
```

## Docs

- [`AGENTS.md`](AGENTS.md): handoff for coding agents (invariants, status, gotchas)
- [`docs/PLAN.md`](docs/PLAN.md): calendar and gates
- [`docs/DEMO.md`](docs/DEMO.md): video shot list
- [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md): what exists and what's different

## Hackathon

Meta Global AI Developer Hackathon, Indie track, Oct 26 – Nov 4, 2026.
