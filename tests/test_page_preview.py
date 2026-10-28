"""Preview wiring with synthetic frames, fake hand results, and no camera/windows."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from paperos.calibration import page
from paperos.sensing.hand import HandTracker

spec = importlib.util.spec_from_file_location(
    "page_preview", Path(__file__).parents[1] / "scripts" / "page_preview.py"
)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


@pytest.mark.parametrize("enabled", [False, True])
def test_preview_updates_hands_before_page_and_draws_page_coords(monkeypatch, tmp_path, enabled):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["page_preview.py", "--hand"] if enabled else ["page_preview.py"]
    )
    monkeypatch.setattr(
        preview,
        "load_settings",
        lambda: SimpleNamespace(
            camera_index=0, paper="letter", orientation="landscape", page_rotation=180
        ),
    )
    frame = np.zeros((300, 400, 3), np.uint8)
    quad = np.array([[100, 100], [300, 100], [300, 200], [100, 200]], np.float32)
    monkeypatch.setattr(page, "detect_quad", lambda *_: quad)
    events, texts, circles, shown = [], [], [], []

    class Detector:
        closed = False

        def detect_for_video(self, image, timestamp_ms):
            events.append("hand")
            # First frame: fingertip on page. Second: hand gone. Third: tip on desk.
            x = 0.375 if events.count("hand") == 1 else 0.05
            landmarks = [SimpleNamespace(x=x, y=125 / 300) for _ in range(21)]
            return SimpleNamespace(hand_landmarks=[] if events.count("hand") == 2 else [landmarks])

        def close(self):
            self.closed = True

    detector = Detector()

    def make_hand_tracker(model_path):
        assert enabled, "default preview must not initialize MediaPipe"
        return HandTracker(detector=detector)

    monkeypatch.setattr(preview, "HandTracker", make_hand_tracker)
    flags = []

    class Tracker(page.PageTracker):
        def update(self, image, hand_present=False):
            events.append("page")
            flags.append(hand_present)
            return super().update(image, hand_present=hand_present)

    monkeypatch.setattr(preview, "PageTracker", lambda **kw: Tracker(lock_frames=1, **kw))

    class Camera:
        closed = False

        def set(self, *_):
            pass

        def isOpened(self):
            return True

        def read(self):
            return True, frame.copy()

        def release(self):
            self.closed = True

    camera = Camera()
    monkeypatch.setattr(preview.cv2, "VideoCapture", lambda _: camera)
    keys = iter([0, 0, ord("q")])
    monkeypatch.setattr(preview.cv2, "waitKey", lambda _: next(keys))
    monkeypatch.setattr(preview.cv2, "putText", lambda img, text, *args: texts.append(text))
    monkeypatch.setattr(preview.cv2, "circle", lambda img, xy, *args: circles.append(xy))
    monkeypatch.setattr(preview.cv2, "imshow", lambda name, img: shown.append(name))
    monkeypatch.setattr(preview.cv2, "destroyAllWindows", lambda: events.append("destroy"))
    preview.main()
    assert camera.closed
    assert events[-1] == "destroy"
    assert shown == ["camera", "page"] * 3
    if enabled:
        assert events[:-1] == ["hand", "page"] * 3
        assert flags == [True, False, True]
        # Camera point (150,125) becomes (0.75,0.75) after the page's 180-degree rotation.
        assert "tip=(150.0, 125.0) px  page=(0.750, 0.750)" in texts
        assert (150, 125) in circles
        assert (round(0.75 * 899), round(0.75 * (round(900 * 215.9 / 279.4) - 1))) in circles
        assert "no hand" in texts
        assert any("off page" in text for text in texts)
        assert detector.closed
    else:
        assert flags == [False] * 3
        assert events[:-1] == ["page"] * 3
        assert not any("tip=" in text for text in texts)


def test_fingertip_without_page_lock_is_labeled(monkeypatch):
    from paperos.sensing.hand import Fingertip

    texts = []
    monkeypatch.setattr(preview.cv2, "putText", lambda img, text, *args: texts.append(text))
    tracker = page.PageTracker()
    assert (
        preview.draw_fingertip(np.zeros((100, 200, 3), np.uint8), Fingertip(50, 25, 0), tracker)
        is None
    )
    assert "page not locked" in texts[0]
