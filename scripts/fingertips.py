"""Extract a lecture fingertip track for `python -m paperos process --fingertips`.

    python scripts/fingertips.py lecture.mp4 --out fingertips.json --fps 10

Coordinates use the full video frame, without paper/page detection or rectification.
Only usable fingertips are saved; hand presence is not part of the JSON contract.
"""

from __future__ import annotations

import argparse
import json
import math
from contextlib import closing
from pathlib import Path

from paperos.pointing import Sample
from paperos.sensing.hand import DEFAULT_MODEL_PATH, HandDetector, HandTracker
from paperos.video import iter_frames


def extract_fingertips(
    video: Path,
    fps: float = 10.0,
    *,
    model_path: Path = DEFAULT_MODEL_PATH,
    detector: HandDetector | None = None,
) -> list[Sample]:
    """Return (seconds, x/width, y/height), closing the tracker and video on errors."""
    samples: list[Sample] = []
    with closing(iter_frames(video, fps)) as frames, HandTracker(
        model_path, detector=detector
    ) as tracker:
        for t, frame in frames:
            tip = tracker.update(frame, t)
            if tip is not None:
                h, w = frame.shape[:2]
                samples.append((tip.t, tip.x_px / w, tip.y_px / h))
    return samples


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="output JSON [[t,u,v], ...]")
    parser.add_argument("--fps", type=float, default=10.0, help="sample rate (default: 10)")
    parser.add_argument("--hand-model", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args(argv)
    if not math.isfinite(args.fps) or args.fps <= 0:
        parser.error("--fps must be finite and greater than zero")
    samples = extract_fingertips(args.video, args.fps, model_path=args.hand_model)
    args.out.write_text(json.dumps(samples, allow_nan=False) + "\n")
    print(f"wrote {len(samples)} fingertip samples to {args.out}")


if __name__ == "__main__":
    main()
