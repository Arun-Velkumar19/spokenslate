"""Paper detection, homography, rectified snapshot.

The page is the largest bright, LOW-SATURATION quadrilateral in the frame. The saturation
filter keeps skin (hands) out of the mask; a convex hull + polygon fit then recovers the
page outline when a hand or a thick pen stroke cuts into its edge.

Coordinates:
- camera px: raw frame pixels
- page coords: normalized, (0, 0) = top-left of the page as the person reads it,
  (1, 1) = bottom-right. Same coordinates the ControlSpec regions use.

Rotation: if the camera faces the person (e.g. a webcam on the laptop looking down at the
paper in front of it), the page appears upside-down in the frame. Set rotation=180.
scripts/page_preview.py lets you cycle it live and tells you the value to put in .env.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

# (long side, short side) in mm
PAPER_MM: dict[str, tuple[float, float]] = {
    "letter": (279.4, 215.9),
    "a4": (297.0, 210.0),
}

_UNIT = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)


@dataclass
class DetectParams:
    max_saturation: int = 60     # paper is grey/white; skin and colored objects are not
    min_value: int = 110         # brightness floor for paper
    max_value_thresh: int = 180  # cap so Otsu can't split a lit page in two
    min_area_frac: float = 0.05  # page must cover >= 5% of the frame
    min_fill: float = 0.7        # contour area / fitted quad area (allows a hand-sized notch)
    close_frac: float = 0.01     # morph-close kernel, fraction of frame long side
    border_px: int = 3           # reject quads touching the frame edge (page cut off)
    work_long_side: int = 640    # detect on a downscaled copy (speed), then refine corners
    refine: bool = True          # fit lines to the 4 edges, intersect for corners


def order_corners(pts: np.ndarray) -> np.ndarray | None:
    """Return corners as TL, TR, BR, BL in camera space, or None if ambiguous."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = pts[:, 1] - pts[:, 0]
    idx = [int(s.argmin()), int(d.argmin()), int(s.argmax()), int(d.argmax())]
    if len(set(idx)) != 4:  # page rotated ~45 degrees in frame
        return None
    return pts[idx]


def white_balance(frame: np.ndarray, percentile: float = 95.0) -> np.ndarray:
    """White-patch balance: make the brightest pixels (the page) neutral.

    Under warm lamp light white paper reads as yellow (saturation ~70+). After balancing,
    paper is neutral again while skin stays saturated, so the hand is still excluded.
    """
    sample = frame[::4, ::4].reshape(-1, 3).astype(np.float32)
    lum = sample.sum(axis=1)
    bright = sample[lum >= np.percentile(lum, percentile)]
    if bright.size == 0:
        return frame
    means = np.maximum(bright.mean(axis=0), 1.0)
    gains = means.max() / means
    ramp = np.arange(256, dtype=np.float32)
    luts = [np.clip(ramp * g, 0, 255).astype(np.uint8) for g in gains]
    return cv2.merge([cv2.LUT(ch, lut) for ch, lut in zip(cv2.split(frame), luts)])


def page_mask(frame: np.ndarray, p: DetectParams) -> np.ndarray | None:
    hsv = cv2.cvtColor(white_balance(frame), cv2.COLOR_BGR2HSV)
    sat, val = hsv[..., 1], hsv[..., 2]
    low_sat = sat <= p.max_saturation
    vals = val[low_sat]
    if vals.size < 100:
        return None
    otsu, _ = cv2.threshold(
        vals.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    thr = float(np.clip(otsu, p.min_value, p.max_value_thresh))
    mask = (low_sat & (val > thr)).astype(np.uint8) * 255
    k = max(3, int(max(frame.shape[:2]) * p.close_frac)) | 1
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    return mask


def _fit_quad(contour: np.ndarray) -> np.ndarray | None:
    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    for eps in np.linspace(0.01, 0.08, 15):
        approx = cv2.approxPolyDP(hull, float(eps) * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx.reshape(4, 2).astype(np.float32)
        if len(approx) < 4:
            break
    return None


def _refine_by_lines(pts: np.ndarray, quad: np.ndarray, band: float) -> np.ndarray:
    """Fit a line to each page edge and intersect neighbours.

    The polygon fit snaps to contour vertices, which can sit a few px along an edge from
    the true corner. Edge points are taken from the middle 80% of each side and within
    `band` px of it, so rounded corners and a hand-shaped notch don't bias the fit.
    """
    lines = []
    for i in range(4):
        a, b = quad[i], quad[(i + 1) % 4]
        d = b - a
        length = float(np.linalg.norm(d))
        if length < 1:
            return quad
        n = np.array([-d[1], d[0]]) / length
        t = (pts - a) @ d / (length * length)
        dist = np.abs((pts - a) @ n)
        sel = pts[(t > 0.1) & (t < 0.9) & (dist < band)]
        if len(sel) < 5:
            return quad
        vx, vy, x0, y0 = cv2.fitLine(sel.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        lines.append((np.array([x0, y0]), np.array([vx, vy])))
    out = []
    for i in range(4):  # corner i joins edge i-1 and edge i
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        A = np.array([d1, -d2]).T
        if abs(np.linalg.det(A)) < 1e-6:
            return quad
        k = np.linalg.solve(A, p2 - p1)
        out.append(p1 + k[0] * d1)
    refined = np.array(out, np.float32)
    if np.linalg.norm(refined - quad, axis=1).max() > 4 * band:
        return quad
    return refined


def detect_quad(frame: np.ndarray, p: DetectParams | None = None) -> np.ndarray | None:
    """Single-frame page detection. Returns TL, TR, BR, BL camera px, or None.

    Runs on a downscaled copy (~3 ms at 1280x720) and maps corners back to full res.
    """
    p = p or DetectParams()
    fh, fw = frame.shape[:2]
    scale = min(1.0, p.work_long_side / max(fh, fw))
    small = (cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
             if scale < 1.0 else frame)
    quad = _detect_small(small, p)
    if quad is None:
        return None
    return ((quad + 0.5) / scale - 0.5).astype(np.float32)


def _detect_small(frame: np.ndarray, p: DetectParams) -> np.ndarray | None:
    mask = page_mask(frame, p)
    if mask is None:
        return None
    h, w = frame.shape[:2]
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
        area = cv2.contourArea(c)
        if area < p.min_area_frac * w * h:
            break
        quad = _fit_quad(c)
        if quad is None:
            continue
        qa = cv2.contourArea(quad)
        if qa <= 0 or area / qa < p.min_fill:
            continue
        b = p.border_px
        if (quad[:, 0].min() < b or quad[:, 1].min() < b
                or quad[:, 0].max() > w - 1 - b or quad[:, 1].max() > h - 1 - b):
            continue
        quad = order_corners(quad)
        if quad is None:
            continue
        if p.refine:
            quad = _refine_by_lines(c.reshape(-1, 2).astype(np.float32), quad, band=3.0)
        return quad
    return None


def _max_corner_dist(a: np.ndarray, b: np.ndarray) -> float:
    """Largest single-corner displacement. Not the mean: one occluded corner moving 100px
    averages to 25px and would slip under the tolerance."""
    return float(np.linalg.norm(a - b, axis=1).max())


class PageTracker:
    """Stable page pose across frames.

    - Locks after `lock_frames` consistent detections.
    - While locked: small changes are smoothed in (EMA); a big jump is ignored unless it
      persists for `move_frames` with NO hand in view. A hand covering a corner produces a
      wrong outline that looks like a move (area only ~9% different), so callers should
      pass hand_present from the hand tracker. Moving the page with no hand relocks.
    - Missed detections keep the last pose (the page is assumed static during play).
    """

    def __init__(
        self,
        paper: str = "letter",
        orientation: Literal["landscape", "portrait"] = "landscape",
        rotation: int = 0,
        params: DetectParams | None = None,
        lock_frames: int = 3,
        move_frames: int = 30,
        tol_frac: float = 0.02,
        alpha: float = 0.3,
        detect_every: int = 3,
    ) -> None:
        if paper not in PAPER_MM:
            raise ValueError(f"paper must be one of {sorted(PAPER_MM)}")
        if rotation % 90:
            raise ValueError("rotation must be a multiple of 90")
        self.paper = paper
        self.orientation = orientation
        self.rotation = rotation % 360
        self.params = params or DetectParams()
        self.lock_frames = lock_frames
        self.move_frames = move_frames
        self.tol_frac = tol_frac
        self.alpha = alpha
        self.detect_every = max(1, detect_every)
        self._frame_i = 0
        self.quad: np.ndarray | None = None  # camera px, TL TR BR BL (camera order)
        self.missed = 0
        self._cand: np.ndarray | None = None
        self._cand_n = 0
        self._H: np.ndarray | None = None
        self._Hinv: np.ndarray | None = None

    # ------------------------------------------------------------------ state
    @property
    def locked(self) -> bool:
        return self.quad is not None

    def reset(self) -> None:
        self.quad = self._cand = self._H = self._Hinv = None
        self._cand_n = self.missed = 0

    def set_rotation(self, rotation: int) -> None:
        if rotation % 90:
            raise ValueError("rotation must be a multiple of 90")
        self.rotation = rotation % 360
        if self.quad is not None:
            self._set(self.quad)

    def page_corners(self) -> np.ndarray | None:
        """Camera px of the page's own TL, TR, BR, BL (rotation applied)."""
        if self.quad is None:
            return None
        return np.roll(self.quad, -(self.rotation // 90), axis=0)

    def _set(self, quad: np.ndarray) -> None:
        self.quad = quad.astype(np.float32)
        corners = self.page_corners()
        self._H = cv2.getPerspectiveTransform(corners, _UNIT)
        self._Hinv = cv2.getPerspectiveTransform(_UNIT, corners)

    def _track_candidate(self, det: np.ndarray, tol: float, needed: int) -> bool:
        if self._cand is not None and _max_corner_dist(det, self._cand) < tol:
            self._cand_n += 1
            self._cand = det
        else:
            self._cand, self._cand_n = det, 1
        return self._cand_n >= needed

    # ------------------------------------------------------------------ update
    def update(self, frame: np.ndarray, hand_present: bool = False) -> np.ndarray | None:
        """Call every frame. Once locked, re-detects only every `detect_every` frames
        (the page is static during play) unless a possible move is being confirmed."""
        self._frame_i += 1
        if (self.quad is not None and self._cand is None
                and self._frame_i % self.detect_every):
            return self.quad
        det = detect_quad(frame, self.params)
        if det is None:
            self.missed += 1
            return self.quad
        self.missed = 0
        tol = self.tol_frac * float(np.hypot(*frame.shape[:2]))

        if hand_present and self.quad is not None:
            # Only accept small refinements while a hand may be occluding the page.
            if _max_corner_dist(det, self.quad) < tol:
                self._set(self.alpha * det + (1 - self.alpha) * self.quad)
            self._cand, self._cand_n = None, 0
            return self.quad

        if self.quad is None:
            if self._track_candidate(det, tol, self.lock_frames):
                self._set(det)
                self._cand, self._cand_n = None, 0
            return self.quad

        if _max_corner_dist(det, self.quad) < tol:
            self._set(self.alpha * det + (1 - self.alpha) * self.quad)
            self._cand, self._cand_n = None, 0
        elif self._track_candidate(det, tol, self.move_frames):
            self._set(det)  # page really moved
            self._cand, self._cand_n = None, 0
        return self.quad

    # ------------------------------------------------------------------ mapping
    def to_page(self, x_px: float, y_px: float, margin: float = 0.0) -> tuple[float, float] | None:
        """Camera px -> normalized page coords; None if off the page (beyond margin)."""
        if self._H is None:
            return None
        u, v = cv2.perspectiveTransform(np.array([[[x_px, y_px]]], np.float32), self._H)[0, 0]
        if -margin <= u <= 1 + margin and -margin <= v <= 1 + margin:
            return float(u), float(v)
        return None

    def to_camera(self, u: float, v: float) -> tuple[float, float] | None:
        """Normalized page coords -> camera px (for drawing the overlay)."""
        if self._Hinv is None:
            return None
        x, y = cv2.perspectiveTransform(np.array([[[u, v]]], np.float32), self._Hinv)[0, 0]
        return float(x), float(y)

    # ------------------------------------------------------------------ snapshot
    def page_size_px(self, long_side_px: int) -> tuple[int, int]:
        long_mm, short_mm = PAPER_MM[self.paper]
        short_px = round(long_side_px * short_mm / long_mm)
        if self.orientation == "landscape":
            return long_side_px, short_px
        return short_px, long_side_px

    def rectify(self, frame: np.ndarray, long_side_px: int = 1280) -> np.ndarray | None:
        """Flat, upright image of the page, or None if no page is locked."""
        corners = self.page_corners()
        if corners is None:
            return None
        w, h = self.page_size_px(long_side_px)
        dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float32)
        M = cv2.getPerspectiveTransform(corners, dst)
        return cv2.warpPerspective(frame, M, (w, h), flags=cv2.INTER_CUBIC)

    def rectified_snapshot(
        self, frame: np.ndarray, long_side_px: int = 1280, quality: int = 90
    ) -> bytes | None:
        """Rectified page as JPEG bytes, ready for the compiler."""
        img = self.rectify(frame, long_side_px)
        if img is None:
            return None
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else None
