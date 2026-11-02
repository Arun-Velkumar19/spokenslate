"""Find spoken phrases that refer to something on the board.

Deterministic and deliberately high-recall: a missed phrase can never be resolved, while
a false positive only costs one model call and comes back "unresolved". Two kinds:

- deictic: "this", "this term", "that one", "these", "here", "over here", "right there"
- role:    "the first", "the second", "the inside", "the numerator", ...
- anaphora: "the problem I just gave you", "the equation from before"
"""

from __future__ import annotations

import re

from spokenslate.spec import ReferencePhrase, Word

NOUNS = {
    "term", "terms", "one", "ones", "problem", "equation", "line", "part", "piece", "guy",
    "guys", "thing", "things", "step", "expression", "function", "value", "number", "side",
    "power", "exponent", "fraction", "derivative", "integral", "graph", "curve", "point",
    "box", "factor", "answer", "example", "formula", "bracket", "parenthesis", "quantity",
    "angle", "vector", "matrix", "row", "column", "entry", "arrow", "limit", "sum",
}
DEMONSTRATIVES = {"this", "that", "these", "those"}
PLACES = {"here", "there"}
ROLES = {
    "first", "second", "inside", "outside", "numerator", "denominator", "exponent",
    "base", "top", "bottom", "coefficient",
}
# "that" as a conjunction: "notice that it", "so that", "know that we"
THAT_CONJ_BEFORE = {
    "so", "know", "think", "see", "say", "said", "mean", "notice", "remember", "is", "was",
    "now", "such", "realize", "means", "show", "shows", "prove", "given", "assume",
}
THAT_OBJECT_VERBS = {
    "cover", "take", "put", "circle", "use", "plug", "move", "multiply", "divide", "add",
    "subtract", "factor", "cancel", "erase", "copy", "write", "call", "simplify", "times",
}
THAT_END = {"", "right", "over", "with", "up", "down", "there", "here"}
# "there" as existential: "there's", "there is", "there are"
EXISTENTIAL_AFTER = {"is", "are", "was", "were", "will", "might"}
# "is there a ...?", "are there any ...": existential question, not a place
EXISTENTIAL_Q_BEFORE = {"is", "are", "was", "were", "isnt", "arent"}
EXISTENTIAL_Q_AFTER = {"a", "an", "any", "some", "no", "anything", "something"}
# words that can't modify a noun, so "this <w> <noun>" is not one phrase ("this is the step")
NOT_MODIFIER = {
    "is", "was", "are", "were", "has", "had", "the", "a", "an", "and", "or", "but", "to", "of",
    "in", "on", "with", "for", "it", "i", "we", "you", "he", "she", "they", "be", "gets", "get",
    "goes", "will", "can", "would", "should", "times", "minus", "plus", "equals",
}
ROLE_SKIP_AFTER = {"time", "times", "place", "day", "week", "thing"}
# "the <noun>" followed by one of these points back at something specific
ANAPHORA_AFTER = {
    "i", "we", "you", "that", "from", "on", "up", "above", "below", "before", "earlier",
    "over", "at", "in", "which", "where",
}

_PUNCT = re.compile(r"[^\w']+")


def _norm(w: str) -> str:
    return _PUNCT.sub("", w.lower())


def find_reference_phrases(words: list[Word]) -> list[ReferencePhrase]:
    toks = [_norm(w.text) for w in words]
    out: list[ReferencePhrase] = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        prev = toks[i - 1] if i > 0 else ""
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        span: tuple[int, int, str] | None = None

        if tok in DEMONSTRATIVES:
            after = toks[i + 2] if i + 2 < len(toks) else ""
            if nxt in NOUNS:
                span = (i, i + 2, "deictic")  # "this term", "that one"
            elif (after in NOUNS and nxt and nxt not in NOT_MODIFIER and nxt not in NOUNS
                  and nxt not in DEMONSTRATIVES):
                span = (i, i + 3, "deictic")  # "this elimination step", "that upper row"
            elif tok != "that":
                span = (i, i + 1, "deictic")  # bare "this"/"these"/"those"
            elif prev not in THAT_CONJ_BEFORE and (prev in THAT_OBJECT_VERBS or nxt in THAT_END):
                span = (i, i + 1, "deictic")  # "cover that", "that right there"
            # else: bare "that" is usually a conjunction ("so that", "notice that it")
        elif tok in PLACES or tok in {"heres", "theres"}:
            if tok in {"there", "theres"} and (tok == "theres" or nxt in EXISTENTIAL_AFTER):
                span = None
            elif tok == "there" and prev in EXISTENTIAL_Q_BEFORE and nxt in EXISTENTIAL_Q_AFTER:
                span = None  # "is there a ...?"
            elif prev in {"over", "right", "up", "down"}:
                span = (i - 1, i + 1, "deictic")
            else:
                span = (i, i + 1, "deictic")
        elif tok == "the" and nxt in NOUNS and nxt not in {"one", "ones"} and (
            (toks[i + 2] if i + 2 < len(toks) else "") in ANAPHORA_AFTER
        ):
            span = (i, i + 2, "anaphora")
        elif tok == "the" and nxt in ROLES:
            after = toks[i + 2] if i + 2 < len(toks) else ""
            if after not in ROLE_SKIP_AFTER or (nxt in {"first", "second"} and after == "times"):
                # "the first times the second" (product rule) is a role reference
                span = (i, i + 2, "role")

        if span is not None:
            s, e, kind = span
            if out and out[-1].word_end > s:  # overlapping ("over" already consumed)
                s = out[-1].word_end
            if s < e:
                out.append(
                    ReferencePhrase(
                        id=f"r{len(out) + 1}",
                        text=" ".join(w.text for w in words[s:e]),
                        kind=kind,  # type: ignore[arg-type]
                        start=words[s].start,
                        end=words[e - 1].end,
                        word_start=s,
                        word_end=e,
                    )
                )
                i = e
                continue
        i += 1
    return out
