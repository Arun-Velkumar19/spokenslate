# PaperOS: agent handoff

Read this before touching code. It applies to every coding agent (Codex, Claude Code, etc.).
Owner: Roon (solo). Meta Global AI Developer Hackathon, Indie track.
**Submission deadline: Nov 4, 2026, 7:00 PM Arizona (9:00 PM ET).**

## What this is

A paper game controller you can reprogram with a pen while using it.
1. Draw controls on paper ("JUMP", "RUN →", "JUMP → ATTACK x2").
2. A camera sees the page; Meta's Muse model reads the drawing once and compiles it into a
   typed, validated `ControlSpec`.
3. The camera tracks the fingertip; tapping a drawn control sends a key press to the game
   (bitrun, an open-source browser platformer).
4. Cross out ATTACK and draw SHIELD mid-game: Muse recompiles **only the diff**, the game
   keeps running, untouched controls (e.g. an active RUN toggle) keep working.

The paper is passive; the camera is the sensor. Novelty = the combination of (a) the
drawing stays the live control surface, (b) pen edits change behavior mid-session,
(c) the model interprets improvised notation. See `docs/PRIOR_ART.md`: never claim we
invented paper controllers.

## Invariants (do not break)

- **The model never runs per frame.** It compiles once and recompiles on stable edits.
- **The model never emits code.** Only `ControlSpec` / `SpecDiff` JSON (see `spec.py`).
  Everything executable is deterministic code in this repo.
- **Validator gates everything.** No spec reaches the engine without
  `validator.validate(spec, keymap).ok`. The model only names semantic actions
  ("jump"); `adapters/keyboard.py` owns the key mapping. Never let a model output pick a key.
- **Freeze primitives, not notation.** Primitives (tap/hold/release/delay/sequence/repeat;
  button/toggle/slider) are fixed after Oct 28. Do NOT add a fixed drawing grammar
  (e.g. "arrows must be drawn like X"). Notation stays open; the model maps it.
- **Recompile = diff.** Control ids are stable across recompiles; removed ids are never
  reused. `apply_diff` + `Engine.load` must keep state for unchanged controls.
- **Safety on transitions.** Recompile, page lost, pause, shutdown → release held keys for
  affected controls (`Engine.load` / `Engine.stop` / `release_all`).
- **Fallback, never pivot.** If touch sensing fails the Oct 29 gate, switch to the
  documented fallback (acoustic-fused → vision-only → dwell, labeled honestly).
- **No scope creep:** no browser automation, no generated-code execution, no extra app
  integrations, no projector, no hardware. Ask Roon before adding any dependency.

## Status (keep this section current)

| Module | State |
|---|---|
| `spec.py`, `validator.py`, `runtime/engine.py`, `adapters/keyboard.py` | done, tested |
| `calibration/page.py` + `scripts/page_preview.py` | done, tested on synthetic frames; **not yet verified on a real camera** (PR #1) |
| `compiler/client.py`, `compiler/prompts.py` | written; **untested against the live Meta API** (base URL, model ids, image format unconfirmed) |
| `sensing/hand.py` + `scripts/page_preview.py --hand` | implemented (Tasks VIDEO, landmark 8, hand presence); fake-result/synthetic preview tests; **not yet verified on a real camera** |
| `sensing/acoustic.py`, `sensing/press.py` | stubs |
| `runtime/edits.py`, `overlay.py`, `main.py` loop | stubs |

Schedule, gates and today's checklist: `docs/PLAN.md`. Demo shot list: `docs/DEMO.md`.

## Layout

```
src/paperos/
  spec.py              ControlSpec / SpecDiff contract + apply_diff
  validator.py         spec vs keymap whitelist, limits, overlaps
  adapters/keyboard.py semantic action -> key (bitrun keymap), dry_run mode
  runtime/engine.py    deterministic executor (press / slide / load / stop)
  runtime/edits.py     stable-edit detection -> trigger recompile        [stub]
  calibration/page.py  page detect, PageTracker, to_page/to_camera, rectify
  sensing/hand.py      MediaPipe fingertip + hand_present
  sensing/acoustic.py  mic tap onsets                                     [stub]
  sensing/press.py     fuse fingertip + onsets/dwell -> InputEvents       [stub]
  compiler/            Muse client + prompts (compile, diff recompile)
  overlay.py           on-screen overlay (regions, rationale, status)     [stub]
  main.py              wiring
scripts/               dev tools (page_preview.py)
tests/                 pytest, all runnable without camera/mic/API
eval/                  CSV logs for acceptance gates (commit results)
docs/                  PLAN, DEMO, PRIOR_ART
```

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                      # must pass before every commit
ruff check src tests scripts   # must be clean
python scripts/page_preview.py # needs a webcam
```

## Conventions

- **Branch per task, PR into `main`.** Never push to `main` directly. Branch names:
  `<agent>/<short-task>` (e.g. `codex/hand-tracker`, `claude/acoustic`).
- **One agent per module at a time.** Several agents may run in parallel. Before starting,
  check open PRs (`gh pr list`) and don't edit files another open PR touches. Shared
  contracts (`spec.py`, `validator.py`, `engine.py` public API) change only in their own
  small PR.
- **Tests with every change.** Hardware-dependent code gets a pure-function core tested
  on synthetic data (see `tests/test_page.py` for the pattern: generated frames, no camera).
  Inject time/sleep/IO so tests are instant.
- Python 3.11+, type hints, ruff line length 100. Keep modules small; no frameworks.
- Update the **Status** table above and the checklist in `docs/PLAN.md` in the same PR.
- Log real-world trials to `eval/*.csv` (columns already defined). Log failures too.
- Never commit `.env`, API keys, or raw captures (`data/captures/` is gitignored).

## Gotchas already found (don't rediscover them)

- **MediaPipe 1.x removed `mp.solutions.hands`.** Use the Tasks API:
  `mediapipe.tasks.python.vision.HandLandmarker` (VIDEO/LIVE_STREAM mode) with
  `models/hand_landmarker.task` (gitignored; download from MediaPipe docs). Index fingertip = landmark 8.
- **Pass `hand_present` into `PageTracker.update()`.** A hand over a page corner makes the
  detector return a wrong outline; without the flag the tracker would relock to it after ~1 s.
- Page gating uses **max** corner distance, not mean (one occluded corner hides in a mean).
- Warm light: detection white-balances first. Skin stays saturated, so hands are excluded.
- A webcam facing the user sees the page upside-down: `PAPEROS_PAGE_ROTATION=180`.
- Expect ~100–150 ms tap-to-keypress latency. The demo uses a forgiving bitrun section.
- The game window must have focus for emulated keys to land.
- bitrun movement keys are **held** keys: map RUN to a **toggle** (hold on / release off) or a
  direction slider. Never require a physical press-and-hold on paper.
- Narration triggers acoustic taps: voiceover is recorded separately; every acoustic onset
  must be fused with a fingertip-in-region check.
- Meta Model API: OpenAI-SDK compatible per reports; **verify** base URL, model ids
  (`muse-spark-1.1`, `muse-wonder-1.0`), image input, and structured-output support before
  building on them. Set a spending cap; never put retry loops around paid calls without a bound.

## When unsure

Prefer the smallest change that keeps the invariants. If a task would change a primitive,
the validator's rules, the demo scope, or add a dependency, stop and ask Roon.
