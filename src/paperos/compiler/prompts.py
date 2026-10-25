"""Compiler prompts. The model maps improvised notation onto fixed primitives.

Iterate on these Oct 26-27 against real drawings. Log every change in eval/ with the
compile-gate results, so prompt edits can't silently overfit to your own handwriting.
"""

from __future__ import annotations

import json

from paperos.spec import ControlSpec, SpecDiff

PRINCIPLES = """\
You compile a hand-drawn paper interface into a ControlSpec (JSON).

The image is a top-down, rectified photo of one sheet of paper. Coordinates are
normalized to the page: (0,0) top-left, (1,1) bottom-right.

Rules:
1. Every drawn control becomes one Control with a tight region around the drawn shape
   (box, circle, line). Labels outside a shape belong to the nearest shape.
2. There is NO fixed notation. Infer meaning from what the person drew: arrows, "then",
   "->", numbered steps, "x2", "3 sec", "hold", brackets. Map it onto the primitives
   only: tap, hold, release, delay, sequence, repeat; controls are button, toggle,
   slider.
3. Use only action names from the allowed list. If a drawn label has no sensible action,
   do not invent one: add a Question instead.
4. Held keys ("RUN", "walk right", "keep shield up") become a toggle: on_enable holds,
   on_disable releases.
5. A drawn line or bar with a label is a slider. Zones map positions to held actions;
   use action=null for idle zones.
6. Crossed-out or scribbled-over controls do not exist.
7. If the drawing is ambiguous, still emit your best spec AND a Question with 2-3
   options. Never guess silently.
8. rationale: one short line per control explaining how you read the notation.
Output JSON only, matching the schema."""


def compile_prompt(action_vocab: str) -> str:
    schema = json.dumps(ControlSpec.model_json_schema(), separators=(",", ":"))
    return f"{PRINCIPLES}\n\n{action_vocab}\n\nSchema:\n{schema}\n\nSet version to 0."


def recompile_prompt(action_vocab: str, current: ControlSpec) -> str:
    schema = json.dumps(SpecDiff.model_json_schema(), separators=(",", ":"))
    return (
        f"{PRINCIPLES}\n\n{action_vocab}\n\n"
        "The person edited the page while using it. Here is the current spec:\n"
        f"{current.model_dump_json()}\n\n"
        "Return ONLY what changed, as a SpecDiff:\n"
        "- removed: ids of controls that were crossed out or erased\n"
        "- updated: existing controls whose label, region, or behavior changed (keep id)\n"
        "- added: new controls, with new ids never used before\n"
        "Controls you did not change must not appear. If nothing changed, return an "
        f"empty diff.\n\nSchema:\n{schema}"
    )
