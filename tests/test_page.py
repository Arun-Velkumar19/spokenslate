"""Page detection on synthetic perspective frames (no camera needed)."""

import cv2
import numpy as np
import pytest

from paperos.calibration.page import PageTracker, detect_quad

H, W = 720, 1280
# A landscape letter page seen at an angle: far edge (top of frame) narrower.
TRUTH = np.array([[420, 170], [880, 175], [1030, 600], [260, 590]], np.float32)  # TL TR BR BL


def make_frame(quad=TRUTH, hand=False, seed=0):
    rng = np.random.default_rng(seed)
    f = np.full((H, W, 3), 55, np.uint8)
    f = cv2.add(f, rng.integers(0, 20, f.shape, dtype=np.uint8))  # textured desk
    cv2.fillConvexPoly(f, quad.astype(np.int32), (235, 238, 240))
    # ink: a few drawn "buttons" and a pen line inside the page
    M = cv2.getPerspectiveTransform(
        np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32), quad.astype(np.float32))
    for (u0, v0, u1, v1) in [(0.1, 0.2, 0.3, 0.4), (0.4, 0.2, 0.6, 0.4), (0.7, 0.6, 0.9, 0.8)]:
        pts = cv2.perspectiveTransform(
            np.array([[[u0, v0], [u1, v0], [u1, v1], [u0, v1]]], np.float32), M)
        cv2.polylines(f, [pts.astype(np.int32)], True, (20, 20, 20), 4)
    if hand:  # skin-colored blob covering part of the bottom edge
        cv2.ellipse(f, (650, 600), (90, 140), 0, 0, 360, (120, 150, 210), -1)
    return f


def corner_err(a, b):
    return float(np.linalg.norm(a - b, axis=1).max())


def test_detects_page_corners():
    q = detect_quad(make_frame())
    assert q is not None
    assert corner_err(q, TRUTH) < 1.5


def test_hand_over_edge_still_detected():
    q = detect_quad(make_frame(hand=True))
    assert q is not None
    assert corner_err(q, TRUTH) < 1.5


def test_warm_lamp_light():
    f = make_frame()
    page = f[..., 0] > 200
    f[page] = (170, 215, 235)  # white paper under a warm bulb reads yellow (S ~ 70)
    q = detect_quad(f)
    assert q is not None and corner_err(q, TRUTH) < 1.5


def test_warm_light_hand_still_excluded():
    f = make_frame(hand=True)
    page = (f[..., 0] > 200)
    f[page] = (170, 215, 235)
    f[(f[..., 2] == 210) & (f[..., 0] == 120)] = (90, 140, 220)  # warm-lit skin
    q = detect_quad(f)
    assert q is not None and corner_err(q, TRUTH) < 1.5


def test_light_grey_desk():
    f = make_frame()
    desk = (f[..., 0] > 40) & (f[..., 0] < 100)
    f[desk] = 170
    q = detect_quad(f)
    assert q is not None and corner_err(q, TRUTH) < 1.5


def test_empty_desk_returns_none():
    f = np.full((H, W, 3), 55, np.uint8)
    assert detect_quad(f) is None


def test_page_cut_off_by_frame_is_rejected():
    quad = TRUTH + np.array([0, 150], np.float32)  # bottom edge off-frame
    assert detect_quad(make_frame(quad)) is None


def locked_tracker(rotation=0, frames=4, detect_every=1):
    t = PageTracker(rotation=rotation, detect_every=detect_every)
    for i in range(frames):
        t.update(make_frame(seed=i))
    return t


def test_tracker_locks_and_maps_coordinates():
    t = locked_tracker()
    assert t.locked
    for (x, y), (u, v) in zip(TRUTH, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        pu, pv = t.to_page(x, y, margin=0.01)
        assert abs(pu - u) < 0.01 and abs(pv - v) < 0.01
    assert t.to_page(10, 10) is None  # desk, not page
    # round trip page -> camera -> page
    x, y = t.to_camera(0.3, 0.7)
    u, v = t.to_page(x, y)
    assert abs(u - 0.3) < 1e-3 and abs(v - 0.7) < 1e-3


def test_rotation_180_flips_page_origin():
    t = locked_tracker(rotation=180)
    u, v = t.to_page(*TRUTH[2], margin=0.01)  # camera bottom-right
    assert u < 0.01 and v < 0.01               # is the page's top-left


def test_does_not_lock_on_one_frame():
    t = PageTracker()
    t.update(make_frame())
    assert not t.locked


def test_holds_pose_through_misses_and_one_off_jumps():
    t = locked_tracker()
    before = t.quad.copy()
    t.update(np.full((H, W, 3), 55, np.uint8))           # page not found
    t.update(make_frame(TRUTH + np.array([120, 0], np.float32)))  # single glitch
    assert t.missed == 0
    assert corner_err(t.quad, before) < 1


def test_hand_resting_on_corner_does_not_move_page():
    t = locked_tracker()
    before = t.quad.copy()
    covered = make_frame()
    cv2.circle(covered, (1030, 600), 110, (120, 150, 210), -1)  # hand over BR corner
    assert corner_err(detect_quad(covered), TRUTH) > 50           # detector alone is fooled
    for _ in range(t.move_frames * 3):
        t.update(covered, hand_present=True)
    assert corner_err(t.quad, before) < 1


def test_relocks_when_page_really_moves():
    t = locked_tracker()
    moved = TRUTH + np.array([120, -40], np.float32)
    for i in range(t.move_frames):
        t.update(make_frame(moved, seed=i))
    assert corner_err(t.quad, moved) < 5


@pytest.mark.parametrize("orientation,shape", [("landscape", (989, 1280)),
                                                ("portrait", (1280, 989))])
def test_rectified_snapshot(orientation, shape):
    t = PageTracker(orientation=orientation)
    for i in range(4):
        t.update(make_frame(seed=i))
    jpg = t.rectified_snapshot(make_frame(), long_side_px=1280)
    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[:2] == shape


def test_rectified_page_is_flat():
    """Drawn boxes should land where they were drawn in page coords."""
    t = locked_tracker()
    img = t.rectify(make_frame(), long_side_px=1000)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # top edge of the first box: v=0.2 between u=0.1..0.3 should be dark ink
    row = gray[int(0.2 * h), int(0.12 * w):int(0.28 * w)]
    assert row.mean() < 120
    # inside the box should be paper
    assert gray[int(0.3 * h), int(0.2 * w)] > 200


def test_skips_redetection_while_locked(monkeypatch):
    from paperos.calibration import page
    t = locked_tracker(detect_every=3)
    calls = []
    real = page.detect_quad
    monkeypatch.setattr(page, "detect_quad", lambda f, p=None: calls.append(1) or real(f, p))
    for _ in range(9):
        t.update(make_frame())
    assert len(calls) == 3
