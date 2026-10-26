# PaperOS

**Draw it. Compile it. Control it.**

PaperOS makes a paper interface *live-programmable*. Draw controls on an ordinary sheet of paper, a Meta model compiles the drawing into a validated control spec, and the paper stays the physical controller. Edit it with a pen mid-session and the behavior updates without restarting the target app.

> Status (Oct 26): implemented and tested: `spec`, `validator`, `runtime/engine`, `adapters/keyboard`, `calibration/page`, `sensing/hand` (fake results; real camera unverified). `compiler` written but untested against the live API. Stubs: acoustic/press sensing, edits, overlay, main loop.

## How it works

```
camera snapshot ──► page calibration (homography, rectify)
                         │
                         ▼
             Muse (compile / diff-recompile)  ◄── optional: target app controls screenshot
                         │
                         ▼
             ControlSpec (typed, validated)  ── fixed primitives, open notation
                         │
live frames ──► fingertip tracking ─┐
mic ──────────► tap onsets ─────────┼──► press/toggle/slider events
                                    ▼
                    deterministic runtime engine
                                    │
                                    ▼
                    adapter (keyboard emulation) ──► target app (bitrun)
```

Key rules:
- The model never runs per frame. It compiles once and recompiles on stable edits, as a **diff** against the current spec.
- The model never emits executable code. It emits a `ControlSpec` built only from fixed primitives; the validator rejects anything outside the adapter's allowed actions.
- **Freeze primitives, not notation.** The person can improvise arrows, words, numbers; the model maps them onto the primitives.

## Layout

```
src/paperos/
  config.py            env + settings
  spec.py              ControlSpec contract (primitives)
  validator.py         spec ↔ adapter whitelist checks
  calibration/page.py  paper detection, homography, rectified snapshot
  sensing/hand.py      fingertip tracking
  sensing/acoustic.py  tap onset detection
  sensing/press.py     fusion → PressEvent / slider values
  compiler/            Muse client, prompts, diff recompile
  runtime/engine.py    deterministic executor
  runtime/edits.py     stable-edit detection (page still, no hand)
  adapters/keyboard.py keyboard emulation + bitrun keymap
  overlay.py           on-screen overlay
  main.py              entry point
scripts/page_preview.py  live check of paper detection + flattened page
eval/                  acceptance-gate trial logs
docs/                  PLAN, DEMO shot list, PRIOR_ART
```

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in API key, base URL, model IDs
pytest                 # spec, validator, engine: runs without camera or API
```

Hand tracking uses the MediaPipe **Tasks** API (`HandLandmarker`); the legacy
`mp.solutions.hands` API is gone in mediapipe 1.x. Download `hand_landmarker.task`
from the [MediaPipe models section](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models)
into `models/` (the file is gitignored).

Set a spending cap/alert in the Meta Model API console. Credits are applied before your card is charged.

## Day-1 camera check

```bash
python scripts/page_preview.py
```

Green outline = page locked. The **page** window must show your handwriting upright;
press `r` until it does and copy the printed `PAPEROS_PAGE_ROTATION` into `.env`
(180 is typical when the camera faces you). `s` saves a frame + flattened page to
`data/captures/` for testing the compiler.

To overlay the index fingertip, enable hand tracking:

```bash
python scripts/page_preview.py --hand
# Optional model location:
python scripts/page_preview.py --hand --hand-model /path/to/hand_landmarker.task
```

The camera view shows a cyan fingertip dot, camera pixels, and normalized page coordinates
via `PageTracker.to_page` (including the selected rotation). The flattened page shows the
same dot when it is on the page. Off-page fingertips and an unlocked page are labeled.
Hand presence is passed to the page tracker each frame to protect against corner
occlusion. Without `--hand`, preview needs no hand model and performs page tracking only.

## Run (once implemented)

```bash
python -m paperos --camera 0 --target bitrun
```

## Demo target

[bitrun](https://slashlab.itch.io/bitrun) by Phorb: open-source HTML5 platformer, assets CC BY-SA 4.0. Played in the browser, not redistributed. Credit in video and submission.

## Prior art

PaperOS builds on a decade of paper-interface work. See [docs/PRIOR_ART.md](docs/PRIOR_ART.md).

## Hackathon

Meta Global AI Developer Hackathon. Indie track, Oct 26 – Nov 4, 2026.
