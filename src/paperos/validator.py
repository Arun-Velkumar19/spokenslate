"""Validate a ControlSpec against an adapter keymap before anything executes.

Errors block the spec. Warnings are shown in the overlay but don't block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

from paperos.adapters.keyboard import Keymap
from paperos.spec import (
    Action,
    Button,
    Control,
    ControlSpec,
    Delay,
    Hold,
    Release,
    Repeat,
    Sequence,
    Slider,
    Toggle,
    iter_action_names,
)

MAX_DELAY_MS = 10_000
MAX_REPEAT = 10
MAX_DEPTH = 4
MAX_STEPS = 20
MIN_REGION_SIDE = 0.03  # ~6mm on A4/letter; smaller than a fingertip is unusable


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _count_steps(a: Action) -> int:
    if isinstance(a, Sequence):
        return sum(_count_steps(s) for s in a.steps)
    if isinstance(a, Repeat):
        return a.times * _count_steps(a.body)
    return 1


def _depth(a: Action) -> int:
    if isinstance(a, Sequence):
        return 1 + max(_depth(s) for s in a.steps)
    if isinstance(a, Repeat):
        return 1 + _depth(a.body)
    return 0


def _total_delay(a: Action) -> int:
    if isinstance(a, Delay):
        return a.ms
    if isinstance(a, Sequence):
        return sum(_total_delay(s) for s in a.steps)
    if isinstance(a, Repeat):
        return a.times * _total_delay(a.body)
    return 0


def _walk(a: Action):
    yield a
    if isinstance(a, Sequence):
        for s in a.steps:
            yield from _walk(s)
    elif isinstance(a, Repeat):
        yield from _walk(a.body)


def _check_action(where: str, a: Action, keymap: Keymap, r: Report) -> None:
    for name in iter_action_names(a):
        if name not in keymap.actions:
            r.errors.append(f"{where}: unknown action {name!r}")
    for node in _walk(a):
        if (
            isinstance(node, (Hold, Release))
            and node.action in keymap.actions
            and not keymap.actions[node.action].holdable
        ):
            r.errors.append(f"{where}: action {node.action!r} cannot be held")
        if isinstance(node, Repeat) and node.times > MAX_REPEAT:
            r.errors.append(f"{where}: repeat {node.times} > {MAX_REPEAT}")
    if _total_delay(a) > MAX_DELAY_MS:
        r.errors.append(f"{where}: total delay {_total_delay(a)}ms > {MAX_DELAY_MS}ms")
    if _depth(a) > MAX_DEPTH:
        r.errors.append(f"{where}: nesting depth {_depth(a)} > {MAX_DEPTH}")
    if _count_steps(a) > MAX_STEPS:
        r.errors.append(f"{where}: {_count_steps(a)} steps > {MAX_STEPS}")
    holds = {n.action for n in _walk(a) if isinstance(n, Hold)}
    releases = {n.action for n in _walk(a) if isinstance(n, Release)}
    if holds - releases:
        r.warnings.append(f"{where}: holds {sorted(holds - releases)} with no release in same action")


def _check_control(c: Control, keymap: Keymap, r: Report) -> None:
    reg = c.region
    if (reg.x1 - reg.x0) < MIN_REGION_SIDE or (reg.y1 - reg.y0) < MIN_REGION_SIDE:
        r.errors.append(f"{c.id}: region too small to press reliably")
    b = c.behavior
    if isinstance(b, Button):
        _check_action(f"{c.id}.on_press", b.on_press, keymap, r)
    elif isinstance(b, Toggle):
        _check_action(f"{c.id}.on_enable", b.on_enable, keymap, r)
        _check_action(f"{c.id}.on_disable", b.on_disable, keymap, r)
    elif isinstance(b, Slider):
        zones = sorted(b.zones, key=lambda z: z.lo)
        for z in zones:
            if z.lo >= z.hi:
                r.errors.append(f"{c.id}: zone [{z.lo}, {z.hi}) is empty")
            if z.action is not None:
                if z.action not in keymap.actions:
                    r.errors.append(f"{c.id}: unknown action {z.action!r}")
                elif not keymap.actions[z.action].holdable:
                    r.errors.append(f"{c.id}: slider action {z.action!r} cannot be held")
        for a, b2 in pairwise(zones):
            if a.hi > b2.lo:
                r.errors.append(f"{c.id}: zones overlap at {b2.lo}")
            elif a.hi < b2.lo:
                r.warnings.append(f"{c.id}: gap in zones between {a.hi} and {b2.lo}")


def validate(spec: ControlSpec, keymap: Keymap) -> Report:
    r = Report()
    seen: set[str] = set()
    for c in spec.controls:
        if c.id in seen:
            r.errors.append(f"duplicate control id {c.id!r}")
        seen.add(c.id)
        _check_control(c, keymap, r)
    cs = spec.controls
    for i, a in enumerate(cs):
        for b in cs[i + 1 :]:
            if a.region.overlaps(b.region):
                r.errors.append(f"regions overlap: {a.id} / {b.id}")
    return r
