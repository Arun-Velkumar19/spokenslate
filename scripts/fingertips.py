"""Extract a fingertip track from a recorded lecture video for `process --fingertips`.

    python scripts/fingertips.py clip.mp4 --out fingertips.json            # 10 fps
    python scripts/fingertips.py clip.mp4 --out fingertips.json --fps 5
    python -m spokenslate process clip.mp4 --words words.json --fingertips fingertips.json ...

Writes [[t, u, v], ...]: t in seconds, u = x/width, v = y/height of MediaPipe landmark 8.
Coords are frame-normalized; for a fixed lecture camera they serve as board coords (no
page rectification, see AGENTS.md gotchas). Frames with no fingertip are skipped.
Needs models/hand_landmarker.task (or --hand-model PATH).
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

import numpy as np

from spokenslate.sensing.hand import DEFAULT_MODEL_PATH, HandDetector, HandTracker
from spokenslate.video import iter_frames


def track(frames: Iterable[tuple[float, np.ndarray]], tracker: HandTracker) -> list[list[float]]:
    """[[t, u, v], ...] for frames where the tracker found a fingertip."""
    out: list[list[float]] = []
    for t, frame in frames:
        tip = tracker.update(frame, t)
        if tip is None:
            continue
        h, w = frame.shape[:2]
        out.append([tip.t, tip.x_px / w, tip.y_px / h])
    return out


def extract_fingertips(
    video: Path,
    fps: float = 10.0,
    *,
    model_path: Path = DEFAULT_MODEL_PATH,
    detector: HandDetector | None = None,
) -> list[list[float]]:
    """Track a clip, closing the detector and frame iterator even on failure."""
    tracker = HandTracker(model_path) if detector is None else HandTracker(model_path, detector=detector)
    with tracker, closing(iter_frames(video, fps)) as frames:
        return track(frames, tracker)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--out", required=True, help="output JSON [[t, u, v], ...]")
    ap.add_argument("--fps", type=float, default=10.0, help="sample rate (default 10)")
    ap.add_argument("--hand-model", default=str(DEFAULT_MODEL_PATH))
    args = ap.parse_args(argv)
    if not math.isfinite(args.fps) or args.fps <= 0:
        ap.error("--fps must be finite and greater than zero")

    samples = extract_fingertips(Path(args.video), args.fps, model_path=Path(args.hand_model))
    Path(args.out).write_text(json.dumps(samples, allow_nan=False) + "\n")
    print(f"{len(samples)} fingertip samples -> {args.out}")


if __name__ == "__main__":
    main()
