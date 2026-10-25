"""Deterministic executor: input events in, adapter calls out. No model calls here.

Actions run on a worker thread so a Delay never blocks sensing. Sleep is injectable
so tests run instantly.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Protocol

from paperos.spec import (
    Action,
    Button,
    ControlSpec,
    Delay,
    Hold,
    Release,
    Repeat,
    Sequence,
    Slider,
    Tap,
    Toggle,
)


class Adapter(Protocol):
    def tap(self, action: str) -> None: ...
    def hold(self, action: str) -> None: ...
    def release(self, action: str) -> None: ...
    def release_all(self) -> None: ...


class Engine:
    def __init__(
        self,
        adapter: Adapter,
        sleep: Callable[[float], None] = time.sleep,
        threaded: bool = True,
    ) -> None:
        self.adapter = adapter
        self.sleep = sleep
        self.threaded = threaded
        self.spec: ControlSpec | None = None
        self.toggled: set[str] = set()
        self.slider_action: dict[str, str | None] = {}
        self._cancel = threading.Event()

    # ------------------------------------------------------------------ spec swap
    def load(self, spec: ControlSpec) -> None:
        """Swap in a new spec. Keep toggle/slider state for controls that still exist."""
        self._cancel.set()
        self._cancel = threading.Event()
        old = self.spec.by_id() if self.spec else {}
        new = spec.by_id()
        for cid in list(self.toggled):
            if cid not in new or new[cid] != old.get(cid):
                self._disable_toggle(cid, old.get(cid))
        for cid in list(self.slider_action):
            if cid not in new or new[cid] != old.get(cid):
                held = self.slider_action.pop(cid)
                if held:
                    self.adapter.release(held)
        self.spec = spec

    def stop(self) -> None:
        self._cancel.set()
        self.toggled.clear()
        self.slider_action.clear()
        self.adapter.release_all()

    # ------------------------------------------------------------------ events
    def press(self, control_id: str) -> None:
        c = self._control(control_id)
        b = c.behavior
        if isinstance(b, Button):
            self._run(b.on_press)
        elif isinstance(b, Toggle):
            if control_id in self.toggled:
                self.toggled.discard(control_id)
                self._run(b.on_disable)
            else:
                self.toggled.add(control_id)
                self._run(b.on_enable)

    def slide(self, control_id: str, value: float | None) -> None:
        """value=None means finger left the slider: release whatever it held."""
        c = self._control(control_id)
        if not isinstance(c.behavior, Slider):
            raise TypeError(f"{control_id} is not a slider")
        want = None
        if value is not None:
            for z in c.behavior.zones:
                if z.lo <= value < z.hi or (value == 1.0 and z.hi == 1.0):
                    want = z.action
                    break
        have = self.slider_action.get(control_id)
        if want == have:
            return
        if have:
            self.adapter.release(have)
        if want:
            self.adapter.hold(want)
        self.slider_action[control_id] = want

    # ------------------------------------------------------------------ internals
    def _control(self, control_id: str):
        if self.spec is None:
            raise RuntimeError("no spec loaded")
        return self.spec.by_id()[control_id]

    def _disable_toggle(self, cid: str, control) -> None:
        self.toggled.discard(cid)
        if control is not None and isinstance(control.behavior, Toggle):
            self._exec(control.behavior.on_disable, threading.Event())

    def _run(self, action: Action) -> None:
        cancel = self._cancel
        if self.threaded:
            threading.Thread(target=self._exec, args=(action, cancel), daemon=True).start()
        else:
            self._exec(action, cancel)

    def _exec(self, a: Action, cancel: threading.Event) -> None:
        if cancel.is_set():
            return
        if isinstance(a, Tap):
            self.adapter.tap(a.action)
        elif isinstance(a, Hold):
            self.adapter.hold(a.action)
        elif isinstance(a, Release):
            self.adapter.release(a.action)
        elif isinstance(a, Delay):
            self.sleep(a.ms / 1000)
        elif isinstance(a, Sequence):
            for s in a.steps:
                self._exec(s, cancel)
        elif isinstance(a, Repeat):
            for _ in range(a.times):
                self._exec(a.body, cancel)
