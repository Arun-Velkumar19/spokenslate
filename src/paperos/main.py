"""Entry point. Wiring only; logic lives in the modules."""

from __future__ import annotations

import argparse
import logging

from paperos.adapters.keyboard import KEYMAPS
from paperos.config import load_settings


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="paperos")
    p.add_argument("--camera", type=int, default=None)
    p.add_argument("--target", default=None, choices=sorted(KEYMAPS))
    p.add_argument("--dry-run", action="store_true", help="log key events instead of sending")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    s = load_settings()
    target = args.target or s.target
    keymap = KEYMAPS[target]
    print(keymap.describe())
    # Loop (to implement): frame -> PageTracker -> HandTracker -> PressDetector
    #   -> Engine.press/slide ; EditWatcher -> MuseCompiler.recompile -> validate
    #   -> apply_diff -> Engine.load ; Overlay.draw
    raise SystemExit("main loop not implemented yet (starts Oct 26)")


if __name__ == "__main__":
    main()
