"""Day-1 check: does the camera find the paper, and does the flattened page look right?

    python scripts/page_preview.py            # camera from .env (PAPEROS_CAMERA_INDEX)
    python scripts/page_preview.py --camera 1

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

import cv2

from paperos.calibration.page import PageTracker, detect_quad
from paperos.config import load_settings

GREEN, YELLOW, WHITE = (60, 200, 60), (0, 210, 255), (255, 255, 255)


def main() -> None:
    s = load_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=s.camera_index)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera)
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
        quad = tracker.update(frame)
        ms = (time.perf_counter() - t0) * 1000

        vis = frame.copy()
        if quad is not None:
            corners = tracker.page_corners()
            cv2.polylines(vis, [corners.astype(int)], True, GREEN, 2)
            tl = tuple(int(v) for v in corners[0])
            cv2.circle(vis, tl, 8, GREEN, -1)
            cv2.putText(vis, "TL", (tl[0] + 10, tl[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, GREEN, 2)
            status, color = f"LOCKED  missed={tracker.missed}", GREEN
        else:
            raw = detect_quad(frame)
            if raw is not None:
                cv2.polylines(vis, [raw.astype(int)], True, YELLOW, 2)
            status, color = "SEARCHING (hold still)", YELLOW
        cv2.putText(vis, f"{status}  {ms:.1f} ms  rot={tracker.rotation}", (16, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(vis, "r rotate | s save | q quit", (16, vis.shape[0] - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 1)
        cv2.imshow("camera", vis)

        page = tracker.rectify(frame, long_side_px=900)
        if page is not None:
            cv2.imshow("page", page)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("r"):
            tracker.set_rotation(tracker.rotation + 90)
            print(f"rotation={tracker.rotation}  ->  put PAPEROS_PAGE_ROTATION={tracker.rotation} in .env")
        if key == ord("s"):
            stamp = time.strftime("%Y%m%d-%H%M%S")
            cv2.imwrite(str(out / f"{stamp}-frame.png"), frame)
            jpg = tracker.rectified_snapshot(frame)
            if jpg:
                (out / f"{stamp}-page.jpg").write_bytes(jpg)
            print(f"saved {out}/{stamp}-*")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
