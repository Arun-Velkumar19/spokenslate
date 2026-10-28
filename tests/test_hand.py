"""Camera/model-free tracker tests with MediaPipe-shaped landmark results."""

from types import SimpleNamespace

import numpy as np
import pytest

from spokenslate.sensing.hand import Fingertip, HandTracker, MediaPipeHandDetector


def hand_result(x=0.25, y=0.75):
    landmarks = [SimpleNamespace(x=0.9, y=0.1) for _ in range(21)]
    landmarks[8] = SimpleNamespace(x=x, y=y)
    return SimpleNamespace(hand_landmarks=[landmarks])


class FakeDetector:
    def __init__(self, *results):
        self.results = iter(results)
        self.calls = []
        self.closed = 0

    def detect_for_video(self, frame, timestamp_ms):
        self.calls.append((frame, timestamp_ms))
        return next(self.results)

    def close(self):
        self.closed += 1


def test_landmark_8_uses_camera_dimensions_and_preserves_time():
    frame = np.zeros((480, 640, 3), np.uint8)
    detector = FakeDetector(hand_result())
    with HandTracker(detector=detector) as tracker:
        assert not tracker.hand_present
        assert tracker.update(frame, 1.234) == Fingertip(160, 360, 1.234)
        assert tracker.hand_present
        assert detector.calls[0][0] is frame
        assert detector.calls[0][1] == 1234
    assert detector.closed == 1


def test_presence_resets_on_hand_loss_and_recovers_without_stale_tip():
    frame = np.zeros((100, 200, 3), np.uint8)
    detector = FakeDetector(
        hand_result(), SimpleNamespace(hand_landmarks=[]), hand_result(0.5, 0.2)
    )
    with HandTracker(detector=detector) as tracker:
        assert tracker.update(frame, 0) is not None
        assert tracker.hand_present
        assert tracker.update(frame, 0.1) is None
        assert not tracker.hand_present
        assert tracker.update(frame, 0.2) == Fingertip(100, 20, 0.2)
        assert tracker.hand_present


def test_multiple_hands_use_first_result():
    result = hand_result()
    result.hand_landmarks += hand_result(0.5, 0.5).hand_landmarks
    with HandTracker(detector=FakeDetector(result)) as tracker:
        assert tracker.update(np.zeros((100, 200, 3), np.uint8), 0) == Fingertip(50, 75, 0)
        assert tracker.hand_present


@pytest.mark.parametrize("x,y", [(-0.1, 0.5), (0.5, 1.1), (float("nan"), 0.5), (0.5, float("inf"))])
def test_unusable_tip_does_not_clear_hand_presence(x, y):
    with HandTracker(detector=FakeDetector(hand_result(x, y))) as tracker:
        assert tracker.update(np.zeros((100, 200, 3), np.uint8), 0) is None
        assert tracker.hand_present


def test_partial_landmarks_still_gate_page_updates():
    result = SimpleNamespace(hand_landmarks=[[SimpleNamespace(x=0.5, y=0.5)]])
    with HandTracker(detector=FakeDetector(result)) as tracker:
        assert tracker.update(np.zeros((100, 200, 3), np.uint8), 0) is None
        assert tracker.hand_present


def test_video_timestamps_are_strictly_increasing_at_submillisecond_intervals():
    detector = FakeDetector(*(hand_result() for _ in range(4)))
    with HandTracker(detector=detector) as tracker:
        for t in (0, 0, 0.0001, 0.1):
            tip = tracker.update(np.zeros((10, 20, 3), np.uint8), t)
            assert tip.t == t
    assert [ms for _, ms in detector.calls] == [0, 1, 2, 100]


@pytest.mark.parametrize("t", [-1, float("nan"), float("inf"), 0.9])
def test_invalid_or_backwards_time_is_rejected_before_detection(t):
    detector = FakeDetector(hand_result())
    with HandTracker(detector=detector) as tracker:
        frame = np.zeros((10, 20, 3), np.uint8)
        tracker.update(frame, 1)
        with pytest.raises(ValueError, match="monotonic"):
            tracker.update(frame, t)
    assert len(detector.calls) == 1


def test_context_closes_on_exception_and_close_is_idempotent():
    detector = FakeDetector(hand_result())
    tracker = HandTracker(detector=detector)
    with pytest.raises(RuntimeError, match="example"), tracker:
        tracker.update(np.zeros((10, 20, 3), np.uint8), 0)
        raise RuntimeError("example")
    tracker.close()
    assert detector.closed == 1
    assert not tracker.hand_present
    with pytest.raises(RuntimeError, match="closed"):
        tracker.update(np.zeros((10, 20, 3), np.uint8), 1)


def test_missing_model_has_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="hand_landmarker.task"):
        MediaPipeHandDetector(tmp_path / "missing.task")


def test_mediapipe_adapter_uses_video_rgb_and_two_hands(monkeypatch, tmp_path):
    """Exercise the thin API boundary with a fake Tasks module; no model or native runtime."""
    import sys

    calls = {}
    result = hand_result()
    native = SimpleNamespace(
        detect_for_video=lambda image, ms: calls.update(image=image, ms=ms) or result,
        close=lambda: calls.update(closed=True),
    )
    vision = SimpleNamespace(
        RunningMode=SimpleNamespace(VIDEO="VIDEO"),
        HandLandmarkerOptions=lambda **kw: SimpleNamespace(**kw),
        HandLandmarker=SimpleNamespace(
            create_from_options=lambda options: calls.update(options=options) or native
        ),
    )
    python = SimpleNamespace(BaseOptions=lambda **kw: SimpleNamespace(**kw), vision=vision)
    mp = SimpleNamespace(
        Image=lambda **kw: SimpleNamespace(**kw), ImageFormat=SimpleNamespace(SRGB="SRGB")
    )
    monkeypatch.setitem(sys.modules, "mediapipe", mp)
    monkeypatch.setitem(sys.modules, "mediapipe.tasks", SimpleNamespace(python=python))
    monkeypatch.setitem(sys.modules, "mediapipe.tasks.python", python)
    model = tmp_path / "hand_landmarker.task"
    model.touch()
    detector = MediaPipeHandDetector(model)
    bgr = np.array([[[10, 20, 30]]], np.uint8)
    assert detector.detect_for_video(bgr, 123) is result
    assert calls["options"].running_mode == "VIDEO"
    assert calls["options"].num_hands == 2
    assert calls["options"].base_options.model_asset_path == str(model)
    assert calls["image"].image_format == "SRGB"
    np.testing.assert_array_equal(calls["image"].data, [[[30, 20, 10]]])
    np.testing.assert_array_equal(bgr, [[[10, 20, 30]]])
    assert calls["ms"] == 123
    detector.close()
    assert calls["closed"]
