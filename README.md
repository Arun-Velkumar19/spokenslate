# SpokenSlate

**A lecture is two streams: what's said and what's written. Transcripts keep only one.**

SpokenSlate turns a recorded whiteboard lecture into an accessible page: every board step as math,
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
| Speech | (local faster-whisper) | words with word-level timestamps; Muse Voice Transcribe is realtime-only and has no word times |
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

python -m spokenslate process lecture.mp4 --words words.json --out site/ \
  --title "Calculus 2, 6.1" --source "credit line"
```

Output: `site/lecture.html` (the accessible page) and `site/lecture.json` (everything,
including evidence for each resolved reference).

## Pointing (hand tracking)

Fingertip tracking (MediaPipe Tasks) gives the resolver ranked candidates for what the
lecturer is pointing at. Download `hand_landmarker.task` from the
[MediaPipe models page](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models)
into `models/` (gitignored). Extract a track from a recorded lecture, then pass it to
the processor:

```bash
python scripts/fingertips.py lecture.mp4 --out fingertips.json --fps 10
python -m spokenslate process lecture.mp4 --words words.json --fingertips fingertips.json \
  --out site/ --title "Calculus 2, 6.1" --source "credit line"
```

The exporter defaults to 10 samples/second and decodes frames sequentially. It writes
`[[t, u, v], ...]`: clip-relative seconds, `x / frame_width`, and `y / frame_height`.
Sampling uses the nearest source frame at each interval, retaining that frame's actual
time; rates above the source FPS use each frame once. Missing/invalid fingertips are
omitted. Lecture coordinates use the full frame with no page rectification.
Use `--hand-model PATH` for a model stored elsewhere.

The existing camera/page preview is also available:

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
