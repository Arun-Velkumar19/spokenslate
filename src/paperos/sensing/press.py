"""Fusion: fingertip + (tap onsets | shadow/height cues | dwell) -> events.  [Oct 27-29]

Chosen method is decided by the Oct 29 kill test (27/30 presses, <=3/30 false hovers).
Fallback order: acoustic-fused tap -> vision-only press -> dwell (labeled honestly).
Movement in bitrun uses toggles or a direction slider, never true press-and-hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class InputEvent:
    kind: Literal["press", "slide", "slide_end"]
    control_id: str
    value: float | None = None  # slider position 0..1
    t: float = 0.0


class PressDetector:
    method: Literal["acoustic", "vision", "dwell"] = "acoustic"

    def update(self, fingertip_page_xy, onsets: list[float], spec, t: float) -> list[InputEvent]:
        raise NotImplementedError
