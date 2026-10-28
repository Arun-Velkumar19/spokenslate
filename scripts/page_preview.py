"""Day-1 check: does the camera find the paper, and does the flattened page look right?

    python scripts/page_preview.py            # camera from .env (PAPEROS_CAMERA_INDEX)
    python scripts/page_preview.py --camera 1
    python scripts/page_preview.py --hand     # needs models/hand_landmarker.task

Windows:
  camera : live feed, page outline (green = locked, yellow = searching), page's own
           top-left corner marked "TL", detection time.
  page   : the flattened page. Handwriting must read upright here. If it's upside down
           or sideways, press r until it's right and copy the printed value into .env.

Keys:  r = rotate 90   s = save snapshot   q / Esc = quit

Setup tips: dark, matte desk or mat under the paper; whole page in frame with a margin;
even light, no glare. Camera at ~35-50 degrees.
"""

from __future__ import annotations

import argparse
import pathlib
import time
from contextlib import ExitStack

import cv2
import numpy as np

from paperos.calibration.page import PageTracker, detect_quad
from paperos.config import load_settings
from paperos.sensing.hand import DEFAULT_MODEL_PATH, Fingertip, HandTracker

CYAN = (255, 220, 0)
GREEN, YELLOW, WHITE = (60, 200, 60), (0, 210, 255), (255, 255, 255)


def draw_fingertip(
    vis: np.ndarray, tip: Fingertip, tracker: PageTracker
) -> tuple[float, float] | None:
    """Mark the camera fingertip and report normalized, rotation-aware page coords."""
    point = (round(tip.x_px), round(tip.y_px))
    cv2.circle(vis, point, 8, CYAN, -1)
    uv = tracker.to_page(tip.x_px, tip.y_px)
    if uv is not None:
        label = f"page=({uv[0]:.3f}, {uv[1]:.3f})"
    else:
        label = "off page" if tracker.locked else "page not locked"
    cv2.putText(
        vis,
        f"tip=({tip.x_px:.1f}, {tip.y_px:.1f}) px  {label}",
        (16, 64),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        CYAN,
        2,
    )
    return uv


def main() -> None:
    s = load_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=s.camera_index)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--hand", action="store_true", help="draw index fingertip and page coords")
    ap.add_argument(
        "--hand-model",
        type=pathlib.Path,
        default=DEFAULT_MODEL_PATH,
        help="MediaPipe hand_landmarker.task path (used with --hand)",
    )
    args = ap.parse_args()

    with ExitStack() as stack:
        hands = stack.enter_context(HandTracker(args.hand_model)) if args.hand else None
        cap = cv2.VideoCapture(args.camera)
        stack.callback(cap.release)
        stack.callback(cv2.destroyAllWindows)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        if not cap.isOpened():
            raise SystemExit(f"could not open camera {args.camera}; try --camera 1")

        tracker = PageTracker(paper=s.paper, orientation=s.orientation, rotation=s.page_rotation)
        out = pathlib.Path("data/captures")
        out.mkdir(parents=True, exist_ok=True)
        print(f"paper={s.paper} orientation={s.orientation} rotation={tracker.rotation}")

        while True:
            ok, frame = cap.read()
            if not ok:
                print("camera read failed")
                break
            t0 = time.perf_counter()
            tip = hands.update(frame, time.monotonic()) if hands is not None else None
            quad = tracker.update(
                frame, hand_present=hands.hand_present if hands is not None else False
            )
            ms = (time.perf_counter() - t0) * 1000

            vis = frame.copy()
            if quad is not None:
                corners = tracker.page_corners()
                cv2.polylines(vis, [corners.astype(int)], True, GREEN, 2)
                tl = tuple(int(v) for v in corners[0])
                cv2.circle(vis, tl, 8, GREEN, -1)
                cv2.putText(
                    vis, "TL", (tl[0] + 10, tl[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, GREEN, 2
                )
                status, color = f"LOCKED  missed={tracker.missed}", GREEN
            else:
                raw = detect_quad(frame)
                if raw is not None:
                    cv2.polylines(vis, [raw.astype(int)], True, YELLOW, 2)
                status, color = "SEARCHING (hold still)", YELLOW
            cv2.putText(
                vis,
                f"{status}  {ms:.1f} ms  rot={tracker.rotation}",
                (16, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )
            cv2.putText(
                vis,
                "r rotate | s save | q quit",
                (16, vis.shape[0] - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                WHITE,
                1,
            )
            uv = draw_fingertip(vis, tip, tracker) if tip is not None else None
            if hands is not None and tip is None:
                label = "hand present; fingertip unavailable" if hands.hand_present else "no hand"
                cv2.putText(vis, label, (16, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.6, CYAN, 2)
            cv2.imshow("camera", vis)

            page = tracker.rectify(frame, long_side_px=900)
            if page is not None:
                if uv is not None:
                    h, w = page.shape[:2]
                    point = (round(uv[0] * (w - 1)), round(uv[1] * (h - 1)))
                    cv2.circle(page, point, 8, CYAN, -1)
                cv2.imshow("page", page)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                tracker.set_rotation(tracker.rotation + 90)
                print(
                    f"rotation={tracker.rotation}  ->  put PAPEROS_PAGE_ROTATION={tracker.rotation} in .env"
                )
            if key == ord("s"):
                stamp = time.strftime("%Y%m%d-%H%M%S")
                cv2.imwrite(str(out / f"{stamp}-frame.png"), frame)
                jpg = tracker.rectified_snapshot(frame)
                if jpg:
                    (out / f"{stamp}-page.jpg").write_bytes(jpg)
                print(f"saved {out}/{stamp}-*")


if __name__ == "__main__":
    main()
