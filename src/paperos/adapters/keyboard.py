"""Keyboard-emulation adapter.

The model only ever references *semantic* action names (jump, attack, ...). This module
owns the mapping to real keys, so a bad compile can never press an arbitrary key.

pynput is imported lazily so tests and dry runs work without an input backend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionDef:
    key: str          # pynput key name ("up", "space") or a single character ("f")
    holdable: bool    # may be used with Hold/Release and slider zones
    description: str


@dataclass(frozen=True)
class Keymap:
    target: str
    actions: dict[str, ActionDef]

    def describe(self) -> str:
        """Action vocabulary as given to the compiler prompt."""
        lines = [f"Target app: {self.target}. Allowed actions:"]
        for name, a in self.actions.items():
            hold = "tap or hold" if a.holdable else "tap only"
            lines.append(f"- {name}: {a.description} ({hold})")
        return "\n".join(lines)


# bitrun (https://slashlab.itch.io/bitrun) controls, from its itch.io page:
# walk Left/Right, jump Up, attack Space, interact F, shield Down, pause P.
# Verify in-game on Oct 26 (shield hold vs tap, attack hold behavior).
BITRUN = Keymap(
    target="bitrun",
    actions={
        "left": ActionDef("left", True, "walk left (hold to keep walking)"),
        "right": ActionDef("right", True, "walk right (hold to keep walking)"),
        "jump": ActionDef("up", False, "jump"),
        "attack": ActionDef("space", False, "attack"),
        "shield": ActionDef("down", True, "raise shield (hold to keep it up)"),
        "interact": ActionDef("f", False, "interact / dismiss dialog"),
        "pause": ActionDef("p", False, "pause"),
    },
)

KEYMAPS: dict[str, Keymap] = {"bitrun": BITRUN}


@dataclass
class KeyboardAdapter:
    keymap: Keymap
    dry_run: bool = False
    _held: set[str] = field(default_factory=set)
    _ctrl: object | None = None
    log_events: list[tuple[str, str]] = field(default_factory=list)

    def _controller(self):
        if self._ctrl is None:
            from pynput.keyboard import Controller

            self._ctrl = Controller()
        return self._ctrl

    def _resolve(self, key: str):
        from pynput.keyboard import Key

        return getattr(Key, key) if len(key) > 1 else key

    def _send(self, kind: str, action: str) -> None:
        if action not in self.keymap.actions:
            raise KeyError(f"action {action!r} not in {self.keymap.target} keymap")
        self.log_events.append((kind, action))
        if self.dry_run:
            log.info("%s %s", kind, action)
            return
        key = self._resolve(self.keymap.actions[action].key)
        ctrl = self._controller()
        if kind in ("down", "tap"):
            ctrl.press(key)
        if kind in ("up", "tap"):
            ctrl.release(key)

    def tap(self, action: str) -> None:
        self._send("tap", action)

    def hold(self, action: str) -> None:
        if action in self._held:
            return
        self._held.add(action)
        self._send("down", action)

    def release(self, action: str) -> None:
        if action not in self._held:
            return
        self._held.discard(action)
        self._send("up", action)

    def release_all(self) -> None:
        """Safety: called on recompile, pause, page lost, and shutdown."""
        for a in list(self._held):
            self.release(a)
