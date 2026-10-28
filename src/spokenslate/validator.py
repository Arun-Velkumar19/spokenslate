"""Turn a model's ResolveOutput into what the user sees. The hallucination guard.

A confident wrong answer is worse than no answer for a blind student, so every rule here
fails toward "unresolved":
- model abstained                       -> unresolved
- element id doesn't exist              -> unresolved (model invented it)
- element not on the board at that time -> unresolved
- quote doesn't match the element       -> unresolved (model misread or confused)
- confidence below threshold            -> unresolved, kept as a "possibly" suggestion
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from spokenslate.spec import ReferencePhrase, Resolution, ResolveOutput
from spokenslate.timeline import Timeline

CONFIDENCE_THRESHOLD = 0.7
LOOKBACK_S = 0.0   # referent must still be on the board when the phrase starts...
LOOKAHEAD_S = 8.0  # ...or appear shortly after ("this problem" written as it's named)
QUOTE_MIN_RATIO = 0.6

_DROP = re.compile(r"[\s\\{}()\[\]$·*.,;:]|\bcdot\b|\bleft\b|\bright\b")


def normalize_math(s: str) -> str:
    s = s.lower().replace("×", "x").replace("−", "-").replace("^", "")
    return _DROP.sub("", s)


def quote_matches(quote: str, content: str) -> bool:
    """True if the quote is (fuzzily) part of the element's content, or vice versa."""
    q, c = normalize_math(quote), normalize_math(content)
    if not q:
        return True  # nothing to check
    if q in c or c in q:
        return True
    return SequenceMatcher(None, q, c).ratio() >= QUOTE_MIN_RATIO


def validate_resolution(
    raw: ResolveOutput,
    phrase: ReferencePhrase,
    timeline: Timeline,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> Resolution:
    base = {"phrase_id": phrase.id, "confidence": raw.confidence, "evidence": raw.evidence}

    def unresolved(note: str, suggest: str | None = None) -> Resolution:
        return Resolution(**base, status="unresolved", note=note, suggested_element_id=suggest,
                          quote=raw.quote)

    if raw.element_id is None:
        return unresolved("model abstained")
    el = timeline.get(raw.element_id)
    if el is None:
        return unresolved(f"unknown element {raw.element_id!r}")
    window = timeline.alive_during(phrase.start - LOOKBACK_S, phrase.end + LOOKAHEAD_S)
    if el.id not in {e.id for e in window}:
        return unresolved("element was not on the board at that time")
    if not quote_matches(raw.quote, el.content):
        return unresolved("quote does not match the board")
    if raw.confidence < threshold:
        return unresolved(f"low confidence ({raw.confidence:.2f})", suggest=el.id)
    return Resolution(**base, status="resolved", element_id=el.id, quote=raw.quote)
