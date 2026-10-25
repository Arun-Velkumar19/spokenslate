"""On-screen overlay.  [Oct 30-31]

Shows: page outline, control regions with labels + rationale line, press flashes,
toggle state, slider position, recompile status ("edit detected -> compiling -> ready
in 2.1s"), clarification questions. This is what makes the model's reasoning visible
on video, so keep the rationale text readable.
"""

from __future__ import annotations


class Overlay:
    def draw(self, frame, spec, state) -> None:
        raise NotImplementedError
