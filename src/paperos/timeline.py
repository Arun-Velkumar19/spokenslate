"""Board timeline: apply per-keyframe BoardDiffs, answer "what was on the board at t".

Erased elements stay in the timeline with erased_at set, which is how Seed keeps steps
the lecturer wiped off. Diffs are applied atomically: an inconsistent diff (unknown id,
reused id, erasing something already gone) raises DiffError and changes nothing.
"""

from __future__ import annotations

from paperos.spec import BoardDiff, TimedElement


class DiffError(ValueError):
    pass


class Timeline:
    def __init__(self) -> None:
        self._elements: dict[str, TimedElement] = {}

    def __contains__(self, element_id: str) -> bool:
        return element_id in self._elements

    def get(self, element_id: str) -> TimedElement | None:
        return self._elements.get(element_id)

    def apply(self, diff: BoardDiff, t: float) -> None:
        # validate everything first, then mutate
        alive = {eid for eid, e in self._elements.items() if e.erased_at is None}
        seen_in_diff: set[str] = set()
        for eid in diff.erased:
            if eid not in alive:
                raise DiffError(f"erased unknown or already-erased element {eid!r}")
            seen_in_diff.add(eid)
        for e in diff.updated:
            if e.id not in alive:
                raise DiffError(f"updated unknown or erased element {e.id!r}")
            if e.id in seen_in_diff:
                raise DiffError(f"element {e.id!r} appears twice in one diff")
            seen_in_diff.add(e.id)
        for e in diff.added:
            if e.id in self._elements or e.id in seen_in_diff:
                raise DiffError(f"added element reuses id {e.id!r}")
            seen_in_diff.add(e.id)
        if self._elements and t < max(e.last_updated for e in self._elements.values()):
            raise DiffError("diffs must be applied in time order")

        for eid in diff.erased:
            self._elements[eid] = self._elements[eid].model_copy(update={"erased_at": t})
        for e in diff.updated:
            old = self._elements[e.id]
            self._elements[e.id] = TimedElement(
                **e.model_dump(), first_seen=old.first_seen, last_updated=t
            )
        for e in diff.added:
            self._elements[e.id] = TimedElement(**e.model_dump(), first_seen=t, last_updated=t)

    def alive_at(self, t: float) -> list[TimedElement]:
        return [e for e in self.all() if e.alive_at(t)]

    def alive_during(self, t0: float, t1: float) -> list[TimedElement]:
        """Elements on the board at any moment in [t0, t1]."""
        return [
            e for e in self.all()
            if e.first_seen <= t1 and (e.erased_at is None or e.erased_at > t0)
        ]

    def all(self) -> list[TimedElement]:
        return sorted(self._elements.values(), key=lambda e: (e.first_seen, e.id))
