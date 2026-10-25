"""Stable-edit detection: when to snapshot for a recompile.  [Nov 1]

Trigger a recompile only when ALL hold:
- no hand over the page for >= STABLE_S
- page pixels changed vs the last compiled snapshot (ink diff above threshold)
- page itself hasn't moved (homography stable)
While recompiling: engine.stop() is NOT called; unaffected controls keep working.
On a diff: validate -> apply_diff -> engine.load(new_spec).
"""

from __future__ import annotations

STABLE_S = 1.0


class EditWatcher:
    def update(self, rectified_gray, hand_present: bool, t: float) -> bool:
        """Return True when a stable edit is ready to recompile."""
        raise NotImplementedError
