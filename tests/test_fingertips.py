"""Fingertip track from a synthetic mp4 with a fake detector (no camera, no model file)."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from paperos.pointing import pointing_at
from paperos.sensing.hand import HandTracker
from paperos.video import iter_frames

spec = importlib.util.spec_from_file_location(
    "fingertips", Path(__file__).parents[1] / "scripts" / "fingertips.py"
)
fingertips = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fingertips)

W, H, FPS, N = 320, 180, 30, 60


def dot_at(i):
    """Pixel position of the 'fingertip' dot in frame i, or None (no hand) every 4th frame."""
    return None if i % 4 == 3 else (20 + 4 * i, 40 + i)


def write_clip(path):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(N):
        frame = np.zeros((H, W, 3), np.uint8)
        if (p := dot_at(i)) is not None:
            cv2.circle(frame, p, 5, (255, 255, 255), -1)
        w.write(frame)
    w.release()
    return path


class DotDetector:
    """Reports landmark 8 at the bright dot's centroid; no landmarks when there is no dot."""

    def __init__(self):
        self.timestamps = []
        self.closed = False

    def detect_for_video(self, frame, timestamp_ms):
        self.timestamps.append(timestamp_ms)
        ys, xs = np.nonzero(frame[..., 0] > 128)
        if len(xs) == 0:
            return SimpleNamespace(hand_landmarks=[])
        lm = [SimpleNamespace(x=0.0, y=0.0) for _ in range(21)]
        lm[8] = SimpleNamespace(x=xs.mean() / frame.shape[1], y=ys.mean() / frame.shape[0])
        return SimpleNamespace(hand_landmarks=[lm])

    def close(self):
        self.closed = True


@pytest.fixture
def clip(tmp_path):
    return write_clip(tmp_path / "clip.mp4")


def test_iter_frames_sequential_and_subsampled(clip):
    all_frames = list(iter_frames(clip))
    assert len(all_frames) == N
    assert [t for t, _ in all_frames[:3]] == pytest.approx([0, 1 / 30, 2 / 30])
    ten = [t for t, _ in iter_frames(clip, fps=10)]
    assert ten == pytest.approx([i / 10 for i in range(20)])   # every 3rd source frame
    assert len(list(iter_frames(clip, fps=1000))) == N        # never upsamples


def test_iter_frames_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        next(iter_frames(tmp_path / "nope.mp4"))


def test_track_frame_normalized_and_skips_empty_frames(clip):
    with HandTracker(detector=DotDetector()) as tracker:
        samples = fingertips.track(iter_frames(clip), tracker)
    expected = [i for i in range(N) if dot_at(i) is not None]
    assert [s[0] for s in samples] == pytest.approx([i / FPS for i in expected], abs=1e-3)
    for (_, u, v), i in zip(samples, expected, strict=True):
        x, y = dot_at(i)
        assert u == pytest.approx(x / W, abs=0.01)
        assert v == pytest.approx(y / H, abs=0.01)
    assert all(len(s) == 3 for s in samples)   # no hand-presence field


def test_cli_writes_json_the_process_command_reads(clip, tmp_path, monkeypatch):
    detector = DotDetector()
    monkeypatch.setattr(fingertips, "HandTracker", lambda _model: HandTracker(detector=detector))
    out = tmp_path / "fingertips.json"
    fingertips.main([str(clip), "--out", str(out), "--fps", "10"])
    assert detector.closed
    # Same parsing as paperos.main._process
    tips = [tuple(x) for x in json.loads(out.read_text())]
    assert [t for t, _, _ in tips] == pytest.approx([i / 10 for i in range(20) if (3 * i) % 4 != 3])
    point = pointing_at(tips, 1.0, 1.0, pad=0)   # source frame 30
    assert point == pytest.approx(((20 + 4 * 30) / W, (40 + 30) / H), abs=0.01)


def test_cli_rejects_nonpositive_fps(clip, tmp_path):
    with pytest.raises(SystemExit):
        fingertips.main([str(clip), "--out", str(tmp_path / "f.json"), "--fps", "0"])
