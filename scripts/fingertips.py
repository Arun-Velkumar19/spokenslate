"""Extract a fingertip track from a recorded lecture video for `process --fingertips`.

    python scripts/fingertips.py clip.mp4 --out fingertips.json            # 10 fps
    python scripts/fingertips.py clip.mp4 --out fingertips.json --fps 5
    python -m paperos process clip.mp4 --words words.json --fingertips fingertips.json ...

Writes [[t, u, v], ...]: t in seconds, u = x/width, v = y/height of MediaPipe landmark 8.
Coords are frame-normalized; for a fixed lecture camera they serve as board coords (no
page rectification, see AGENTS.md gotchas). Frames with no fingertip are skipped.
Needs models/hand_landmarker.task (or --hand-model PATH).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

import numpy as np

from paperos.sensing.hand import DEFAULT_MODEL_PATH, HandTracker
from paperos.video import iter_frames


def track(frames: Iterable[tuple[float, np.ndarray]], tracker: HandTracker) -> list[list[float]]:
    """[[t, u, v], ...] for frames where the tracker found a fingertip."""
    out: list[list[float]] = []
    for t, frame in frames:
        tip = tracker.update(frame, t)
        if tip is None:
            continue
        h, w = frame.shape[:2]
        out.append([round(t, 3), round(tip.x_px / w, 4), round(tip.y_px / h, 4)])
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--out", required=True, help="output JSON [[t, u, v], ...]")
    ap.add_argument("--fps", type=float, default=10.0, help="sample rate (default 10)")
    ap.add_argument("--hand-model", default=str(DEFAULT_MODEL_PATH))
    args = ap.parse_args(argv)
    if args.fps <= 0:
        ap.error("--fps must be positive")

    with HandTracker(args.hand_model) as tracker:
        samples = track(iter_frames(Path(args.video), args.fps), tracker)
    Path(args.out).write_text(json.dumps(samples))
    print(f"{len(samples)} fingertip samples -> {args.out}")


if __name__ == "__main__":
    main()
