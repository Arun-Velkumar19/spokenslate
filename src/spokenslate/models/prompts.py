"""Prompts for Muse. Built from the Oct 27 playground test, where muse-spark-1.3 resolved
10/10 references with these ingredients: frames in time order, the words spoken during
each frame, an explicit "unresolved" option, and a request for evidence.

Change these only alongside a re-run of the reference benchmark (eval/), so prompt edits
can't silently overfit one lecture.
"""

from __future__ import annotations

import json

from spokenslate.spec import BoardDiff, ResolveOutput, TimedElement


def _schema(model) -> str:
    return json.dumps(model.model_json_schema(), separators=(",", ":"))


def _board_listing(elements: list[TimedElement]) -> str:
    if not elements:
        return "(the board is empty so far)"
    return "\n".join(
        f'- id={e.id} kind={e.kind} region=({e.region.x0:.2f},{e.region.y0:.2f})-'
        f'({e.region.x1:.2f},{e.region.y1:.2f}) content="{e.content}"'
        for e in elements
    )


BOARD_RULES = """\
You transcribe a lecture whiteboard into structured elements for blind students.

The image is one moment of the lecture. The lecturer may be blocking part of the board
(possibly masked out). Report ONLY what changed compared to the current board below:
- added: new elements. Use ids "new1", "new2", ... (the system assigns permanent ids).
- updated: an existing element that got more writing or a correction. Keep its id.
- erased: ids of existing elements that are now wiped off the board.
Rules:
- One element per written line or per distinct expression/diagram. Do not merge lines.
- content: exactly as written. Math in LaTeX. Do not fix the lecturer's math.
- spoken: how a screen reader should say it, in plain words ("x squared plus one, cubed").
- region: tight normalized box (0..1) around the element in this image.
- If something is hidden by the lecturer, do NOT mark it erased. Hidden is not erased.
- If nothing changed, return empty lists.
Return JSON only, matching the schema."""


def board_prompt(current: list[TimedElement]) -> str:
    return (f"{BOARD_RULES}\n\nCurrent board:\n{_board_listing(current)}\n\n"
            f"Schema:\n{_schema(BoardDiff)}")


RESOLVE_RULES = """\
You resolve what a lecturer's spoken words refer to on the board, for a blind student who
cannot see the pointing. A wrong answer is worse than no answer.

You get: frames in time order, the words spoken during each frame, the phrase to resolve,
and the board elements that existed around that moment (with ids). If geometry found the
lecturer's fingertip near some elements, they are listed as pointing candidates.

Answer with:
- element_id: one id from the board list, or null if you cannot tell.
- quote: the specific part of that element the phrase means, as written (may be a
  sub-expression, e.g. "\\ln x" inside "(\\ln x)^{1/3}").
- confidence: 0..1. Use < 0.7 whenever more than one element is plausible.
- evidence: short reasons (pointing, hand position, order of writing, what was said
  before/after, math structure, earlier/later frames).
Something hidden under the lecturer's hand can still be the answer if an earlier frame
shows it. Return JSON only, matching the schema."""


def resolve_prompt(
    phrase_text: str,
    sentence: str,
    frame_words: list[tuple[float, str]],
    elements: list[TimedElement],
    candidates: list[tuple[str, float]],
) -> str:
    frames = "\n".join(f"Frame {i + 1} (t={t:.1f}s): \"{w}\"" for i, (t, w) in enumerate(frame_words))
    cands = (", ".join(f"{eid} (distance {d:.2f})" for eid, d in candidates)
             if candidates else "none (no fingertip detected near the board)")
    return (
        f"{RESOLVE_RULES}\n\nWords spoken during each frame:\n{frames}\n\n"
        f'Full sentence: "{sentence}"\nPhrase to resolve: "{phrase_text}"\n\n'
        f"Board elements around this moment:\n{_board_listing(elements)}\n\n"
        f"Pointing candidates: {cands}\n\nSchema:\n{_schema(ResolveOutput)}"
    )
