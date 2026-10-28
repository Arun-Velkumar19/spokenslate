"""Video input: frames at times, audio extraction, keyframe selection.

Keyframes are where the board changed. Selection runs on downscaled greyscale frames and
ignores pixels covered by the lecturer mask when one is available, so walking around
doesn't trigger a board read. A minimum gap bounds the number of paid model calls.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np


class FrameSource(Protocol):
    duration: float

    def frame_at(self, t: float) -> np.ndarray: ...


class VideoFile:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.cap = cv2.VideoCapture(str(self.path))
        if not self.cap.isOpened():
            raise FileNotFoundError(f"cannot open video {self.path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.duration = self.n_frames / self.fps if self.fps else 0.0

    def frame_at(self, t: float) -> np.ndarray:
        # The last frame starts at duration - 1/fps; asking for t == duration returns
        # nothing on real files, so clamp to the last frame index.
        idx = min(max(0, round(t * self.fps)), max(0, self.n_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self.cap.read()
        if not ok:
            raise ValueError(f"no frame at t={t:.2f}s")
        return frame


def iter_frames(path: Path, fps: float | None = None) -> Iterator[tuple[float, np.ndarray]]:
    """Yield (t, frame) reading the file once, front to back (no per-frame seeks).

    t is frame_index / native fps. With ``fps``, frames are subsampled to at most that
    rate; skipped frames are grabbed but not decoded into arrays.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open video {path}")
    native = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = 1.0 / fps if fps else 0.0
    next_t = 0.0
    idx = 0
    try:
        while cap.grab():
            t = idx / native
            idx += 1
            # Half a source frame of slack so 30 fps -> 10 fps keeps exactly every 3rd frame.
            if t + 0.5 / native < next_t:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                break
            next_t += step
            yield t, frame
    finally:
        cap.release()


def extract_audio(video: Path, out_wav: Path) -> Path:
    """16 kHz mono WAV via ffmpeg (system binary)."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found; install it (brew install ffmpeg)")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vn",
                    "-ac", "1", "-ar", "16000", str(out_wav)], check=True)
    return out_wav


def to_jpeg(frame: np.ndarray, long_side: int = 1280, quality: int = 88) -> bytes:
    h, w = frame.shape[:2]
    s = min(1.0, long_side / max(h, w))
    if s < 1.0:
        frame = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("jpeg encode failed")
    return buf.tobytes()


def thumbnail(frame: np.ndarray, width: int = 320) -> np.ndarray:
    """Small BGR copy for keyframe selection; keeps memory flat for long clips."""
    s = min(1.0, width / frame.shape[1])
    return cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else frame


def _small_gray(frame: np.ndarray, width: int = 160) -> np.ndarray:
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    s = width / g.shape[1]
    return cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA).astype(np.float32)


def select_keyframes(
    samples: list[tuple[float, np.ndarray]],
    masks: list[np.ndarray | None] | None = None,
    thresh: float = 3.0,
    min_gap_s: float = 4.0,
) -> list[float]:
    """Times where the (unmasked) board differs from the last keyframe by > thresh
    (mean abs grey level on a 160px-wide thumbnail). The first sample is always kept."""
    keep: list[float] = []
    last: np.ndarray | None = None
    last_t = -1e9
    for i, (t, frame) in enumerate(samples):
        g = _small_gray(frame)
        m = masks[i] if masks else None
        valid = np.ones_like(g, bool)
        if m is not None:
            valid = cv2.resize(m, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_NEAREST) == 0
        if last is None:
            keep.append(t)
            last, last_t = g, t
            continue
        if valid.sum() == 0 or t - last_t < min_gap_s:
            continue
        diff = float(np.abs(g - last)[valid].mean())
        if diff > thresh:
            keep.append(t)
            last, last_t = g, t
    return keep
