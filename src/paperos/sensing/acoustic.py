"""Tap onset detection from the mic.  [Oct 26: run the experiment day 1]

Questions to answer on day 1, logged in eval/:
- Does a fingertip tap on paper over a desk produce a clean onset? (try both
  bare desk and a mousepad under the page)
- False onsets from narration, typing, desk bumps? (record voiceover separately)
Every onset must be fused with a fingertip-in-region check (sensing/press.py).
"""

from __future__ import annotations


class TapDetector:
    def poll(self) -> list[float]:
        """Return onset timestamps since last poll (monotonic seconds)."""
        raise NotImplementedError
