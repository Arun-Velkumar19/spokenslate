"""Recorded-video export and process CLI handoff, without a camera/model/API."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fixtures import CHAIN, words

from paperos import main, video
from paperos.config import Settings
from paperos.models import muse
from paperos.sensing import hand
from paperos.spec import BoardDiff, ResolveOutput

spec = importlib.util.spec_from_file_location(
    "fingertips", Path(__file__).parents[1] / "scripts" / "fingertips.py"
)
fingertips = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fingertips)


def write_clip(tmp_path, fps=10, n_frames=8):
    path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (80, 40))
    assert writer.isOpened()
    try:
        for i in range(n_frames):
            writer.write(np.full((40, 80, 3), i * 8, np.uint8))
    finally:
        writer.release()
    return path


class FakeDetector:
    def __init__(self, position=lambda ms: (0.25, 0.45)):
        self.position = position
        self.calls = []
        self.closed = False

    def detect_for_video(self, frame, timestamp_ms):
        self.calls.append((frame, timestamp_ms))
        xy = self.position(timestamp_ms)
        landmarks = [] if xy is None else [SimpleNamespace(x=xy[0], y=xy[1])] * 21
        return SimpleNamespace(hand_landmarks=[landmarks] if landmarks else [])

    def close(self):
        self.closed = True


def capture_spy(monkeypatch):
    """Wrap the real MP4 decoder; any seek (including one before reading) fails."""
    open_capture = cv2.VideoCapture
    captures = []

    class Capture:
        def __init__(self, path):
            self.cap = open_capture(path)
            self.grabs = 0
            self.closed = False
            captures.append(self)

        def isOpened(self):
            return self.cap.isOpened()

        def get(self, prop):
            return self.cap.get(prop)

        def set(self, *_):
            pytest.fail("sequential extraction must never seek")

        def grab(self):
            self.grabs += 1
            return self.cap.grab()

        def retrieve(self):
            return self.cap.retrieve()

        def release(self):
            self.closed = True
            self.cap.release()

    monkeypatch.setattr(video.cv2, "VideoCapture", Capture)
    return captures


def test_export_cli_normalizes_full_frame_and_skips_missing_or_invalid_tip(tmp_path, monkeypatch):
    clip = write_clip(tmp_path)
    captures = capture_spy(monkeypatch)
    positions = {0: (0.25, 0.75), 200: None, 400: (1.1, 0.5), 600: (1.0, 0.0)}
    detector = FakeDetector(positions.__getitem__)
    monkeypatch.setattr(hand, "MediaPipeHandDetector", lambda path: detector)
    out = tmp_path / "fingertips.json"
    fingertips.main([str(clip), "--out", str(out), "--fps", "5"])
    assert json.loads(out.read_text()) == [[0.0, 0.25, 0.75], [0.6, 1.0, 0.0]]
    assert [ms for _, ms in detector.calls] == [0, 200, 400, 600]
    # Every source frame is grabbed, but only sampled frames are retrieved/detected.
    assert [round(float(f.mean()) / 8) for f, _ in detector.calls] == [0, 2, 4, 6]
    assert captures[0].grabs == 9 and captures[0].closed
    assert detector.closed


@pytest.mark.parametrize(
    "source_fps,n_frames,fps,indices",
    [(25, 26, 10, [0, 2, 5, 7, 10, 12, 15, 17, 20, 22, 25]),
     (10, 4, 30, [0, 1, 2, 3]), (10, 4, 10, [0, 1, 2, 3]), (10, 4, 0.5, [0])],
)
def test_sequential_sampling_uses_source_times_without_duplicate_frames(
    tmp_path, monkeypatch, source_fps, n_frames, fps, indices
):
    clip = write_clip(tmp_path, source_fps, n_frames)
    captures = capture_spy(monkeypatch)
    samples = list(video.iter_frames(clip, fps))
    assert [t for t, _ in samples] == pytest.approx([i / source_fps for i in indices])
    assert [round(float(f.mean()) / 8) for _, f in samples] == indices
    assert captures[0].grabs == n_frames + 1 and captures[0].closed


@pytest.mark.parametrize("fps", [0, -1, float("nan"), float("inf")])
def test_invalid_sample_rate_rejected_without_model_or_video(tmp_path, fps):
    with pytest.raises(ValueError, match="fps must be finite"):
        list(video.iter_frames(tmp_path / "missing.mp4", fps))
    with pytest.raises(SystemExit) as exc:
        fingertips.main(["missing.mp4", "--out", str(tmp_path / "tips.json"), f"--fps={fps}"])
    assert exc.value.code == 2
    assert not (tmp_path / "tips.json").exists()


def test_no_detections_writes_empty_track(tmp_path, monkeypatch):
    clip = write_clip(tmp_path, n_frames=3)
    detector = FakeDetector(lambda ms: None)
    monkeypatch.setattr(hand, "MediaPipeHandDetector", lambda path: detector)
    out = tmp_path / "tips.json"
    fingertips.main([str(clip), "--out", str(out)])
    assert json.loads(out.read_text()) == []
    assert [ms for _, ms in detector.calls] == [0, 100, 200]  # default 10 FPS
    assert detector.closed


@pytest.mark.parametrize("source_fps", [0, float("nan"), float("inf")])
def test_unknown_source_rate_fails_without_fabricating_times(tmp_path, monkeypatch, source_fps):
    released = []
    cap = SimpleNamespace(
        isOpened=lambda: True,
        get=lambda prop: source_fps,
        release=lambda: released.append(True),
    )
    monkeypatch.setattr(video.cv2, "VideoCapture", lambda path: cap)
    with pytest.raises(ValueError, match="invalid source FPS"):
        list(video.iter_frames(tmp_path / "clip.mp4"))
    assert released == [True]


def test_detector_failure_closes_tracker_and_video(tmp_path, monkeypatch):
    clip = write_clip(tmp_path)
    captures = capture_spy(monkeypatch)

    def fail(ms):
        raise RuntimeError("detector failed")

    detector = FakeDetector(fail)
    with pytest.raises(RuntimeError, match="detector failed"):
        fingertips.extract_fingertips(clip, detector=detector)
    assert detector.closed and captures[0].closed


def test_missing_video_releases_capture_and_tracker(tmp_path, monkeypatch):
    captures = capture_spy(monkeypatch)
    detector = FakeDetector()
    with pytest.raises(FileNotFoundError, match="cannot open video"):
        fingertips.extract_fingertips(tmp_path / "missing.mp4", detector=detector)
    assert detector.closed and captures[0].closed


def test_exported_json_feeds_process_cli_pointing_candidates(tmp_path, monkeypatch):
    clip = write_clip(tmp_path, n_frames=10)
    detector = FakeDetector()
    monkeypatch.setattr(hand, "MediaPipeHandDetector", lambda path: detector)
    track = tmp_path / "fingertips.json"
    fingertips.main([str(clip), "--out", str(track)])
    word_file = tmp_path / "words.json"
    word_file.write_text(json.dumps([w.model_dump() for w in words("cover this now", start=0.1,
                                                                 step=0.1)]))
    requests = []

    class FakeMuse:
        def read_board(self, jpeg, current):
            return BoardDiff(added=[CHAIN])

        def resolve(self, req):
            requests.append(req)
            return ResolveOutput(element_id=None, confidence=0.0)

    monkeypatch.setattr(muse, "MuseClient", lambda *args: FakeMuse())
    monkeypatch.setattr(main, "load_settings", Settings)
    out = tmp_path / "site"
    main.main(["process", str(clip), "--words", str(word_file), "--fingertips", str(track),
               "--out", str(out)])
    assert len(json.loads(track.read_text())) == 10
    assert len(requests) == 1 and requests[0].candidates == [("e1", 0.0)]
    assert (out / "clip.html").is_file()
    assert json.loads((out / "clip.json").read_text())["resolutions"][0]["status"] == "unresolved"
