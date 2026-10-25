"""Paper detection, homography, rectified snapshot.  [Oct 26]

- Find the page quad each frame (largest bright quadrilateral; dark desk helps).
- H: camera px -> normalized page coords (0..1). Used by sensing to map fingertips.
- rectified_snapshot(): full-resolution, rectified JPEG of the page for compiling.
  Take compile snapshots at a steeper angle than the interaction view if parse
  quality drops at 35-50 degrees (handwriting at the far edge gets small/skewed).
"""

from __future__ import annotations


class PageTracker:
    def update(self, frame):
        """Return the page quad (4x2 px) or None if the page isn't found."""
        raise NotImplementedError

    def to_page(self, x_px: float, y_px: float) -> tuple[float, float] | None:
        """Camera pixel -> normalized page coords, or None if outside the page."""
        raise NotImplementedError

    def rectified_snapshot(self, frame, long_side_px: int = 1600) -> bytes:
        """Rectified page as JPEG bytes for the compiler."""
        raise NotImplementedError
