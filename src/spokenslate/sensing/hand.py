"""Index fingertip in camera pixels; hand presence also gates page/edit tracking.

The default backend uses MediaPipe Tasks in VIDEO mode. Inject a HandDetector to
exercise tracking without MediaPipe, a model file, or a camera.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Self

import cv2
import numpy as np

DEFAULT_MODEL_PATH = Path("models/hand_landmarker.task")


class Landmark(Protocol):
    x: float
    y: float


class HandResult(Protocol):
    hand_landmarks: Sequence[Sequence[Landmark]]


class HandDetector(Protocol):
    def detect_for_video(self, frame: np.ndarray, timestamp_ms: int) -> HandResult: ...

    def close(self) -> None: ...


class MediaPipeHandDetector:
    """Thin BGR-frame adapter around the MediaPipe Tasks API."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH) -> None:
        if not Path(model_path).is_file():
            raise FileNotFoundError(
                f"Hand model not found: {model_path}. Download hand_landmarker.task "
                "from the MediaPipe docs (see README.md), or use --hand-model PATH."
            )
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)

    def detect_for_video(self, frame: np.ndarray, timestamp_ms: int) -> HandResult:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        return self._landmarker.detect_for_video(image, timestamp_ms)

    def close(self) -> None:
        self._landmarker.close()


@dataclass
class Fingertip:
    x_px: float
    y_px: float
    t: float


class HandTracker:
    """Track landmark 8 of the first returned hand (no cross-frame hand identity).

    ``t`` is nonnegative monotonic time in seconds, retained in Fingertip.t.
    MediaPipe receives strictly increasing integer milliseconds, including when
    successive frames fall in the same millisecond. Off-frame/invalid fingertips
    yield None without clearing hand_present: a hand may still occlude the page.
    Close the tracker when done, or use it as a context manager.
    """

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        *,
        detector: HandDetector | None = None,
    ) -> None:
        self._detector = detector if detector is not None else MediaPipeHandDetector(model_path)
        self._hand_present = False
        self._last_t = 0.0
        self._timestamp_ms = -1
        self._closed = False

    def update(self, frame: np.ndarray, t: float) -> Fingertip | None:
        if self._closed:
            raise RuntimeError("HandTracker is closed")
        if not math.isfinite(t) or t < self._last_t:
            raise ValueError("t must be finite, nonnegative, and monotonic (seconds)")
        timestamp_ms = max(int(t * 1000), self._timestamp_ms + 1)
        result = self._detector.detect_for_video(frame, timestamp_ms)
        self._last_t, self._timestamp_ms = t, timestamp_ms
        self._hand_present = bool(result.hand_landmarks)
        if not self._hand_present or len(result.hand_landmarks[0]) <= 8:
            return None
        tip = result.hand_landmarks[0][8]
        if not (
            math.isfinite(tip.x) and math.isfinite(tip.y) and 0 <= tip.x <= 1 and 0 <= tip.y <= 1
        ):
            return None
        h, w = frame.shape[:2]
        return Fingertip(tip.x * w, tip.y * h, t)

    @property
    def hand_present(self) -> bool:
        return self._hand_present

    def close(self) -> None:
        if not self._closed:
            self._detector.close()
            self._closed = True
            self._hand_present = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
