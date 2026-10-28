"""Pointing: turn fingertip positions on the board into candidate referents.

This is the PaperOS fingertip-on-a-surface idea applied to a whiteboard. Geometry gives
a short, ranked candidate list; the model only confirms or picks among them, which is
far more reliable than asking it to find the referent from scratch.

Fingertip samples are (t, u, v) in normalized board coordinates. For fixed-camera
lecture video, scripts/fingertips.py uses sensing/hand.py and normalizes by the
full frame dimensions, without page calibration.
"""

from __future__ import annotations

from statistics import median

from paperos.spec import TimedElement

Sample = tuple[float, float, float]  # (t, u, v)


def pointing_at(samples: list[Sample], t0: float, t1: float, pad: float = 0.5) -> tuple[float, float] | None:
    """Median fingertip position while the phrase is spoken (± pad seconds)."""
    pts = [(u, v) for t, u, v in samples if t0 - pad <= t <= t1 + pad]
    if not pts:
        return None
    return median(u for u, _ in pts), median(v for _, v in pts)


def candidates(
    elements: list[TimedElement],
    point: tuple[float, float] | None,
    k: int = 3,
    max_dist: float = 0.15,
) -> list[tuple[str, float]]:
    """Up to k (element_id, distance) nearest the point, within max_dist. Inside = 0."""
    if point is None:
        return []
    u, v = point
    scored = sorted(
        ((e.id, e.region.distance(u, v)) for e in elements),
        key=lambda x: (x[1], x[0]),
    )
    return [(eid, d) for eid, d in scored if d <= max_dist][:k]
