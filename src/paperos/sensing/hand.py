"""Fingertip tracking (MediaPipe HandLandmarker, index fingertip = landmark 8).  [Oct 26-27]

NOTE: mediapipe 1.x removed the legacy `mp.solutions.hands` API that most tutorials
use. Use the Tasks API: mediapipe.tasks.python.vision.HandLandmarker with
running_mode=VIDEO (or LIVE_STREAM) and the hand_landmarker.task model file.
Verified Oct 25 on mediapipe 1.1.1.

Output per frame: fingertip in camera px + a hand-present flag. Also exposes
hand_present for edit detection (never compile while a hand is over the page) and for
PageTracker.update(frame, hand_present=...), which stops a hand covering a page corner
from being mistaken for the page moving.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Fingertip:
    x_px: float
    y_px: float
    t: float


class HandTracker:
    def update(self, frame, t: float) -> Fingertip | None:
        raise NotImplementedError

    @property
    def hand_present(self) -> bool:
        raise NotImplementedError
