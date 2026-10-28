"""Score a LectureDoc against the reference benchmark (eval/references.csv).

Each truth row is matched to one detected phrase by time window and phrase text, then
judged against the doc's Resolution for it:

- correct          resolved to the truth referent, or unresolved where truth is `unresolved`
- unresolved       not resolved (includes `missed`: no detected phrase matched the row)
- wrong            resolved to something else (or resolved where truth is `unresolved`)
- confident_wrong  wrong with confidence >= 0.7 (a subset of wrong; the number that must be 0)

Truth is either an element id (`e3`, exact; best for pipeline runs) or the referent as
written (free text, which must appear in the linked element's content or spoken reading;
the model's quote is never trusted for scoring). A "possibly" suggestion is not a link, so it
counts as unresolved. The baseline is a plain transcript: it resolves nothing.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from spokenslate.spec import LectureDoc, ReferencePhrase, Resolution

CONFIDENT = 0.7
OUTCOMES = ("correct", "unresolved", "wrong")
_ID = re.compile(r"^e\d+$")


@dataclass
class TruthRow:
    t0: float
    t1: float
    phrase: str
    truth: str
    lecture: str = ""

    @property
    def abstain(self) -> bool:
        return self.truth.strip().lower() == "unresolved"


@dataclass
class Judged:
    row: TruthRow
    outcome: str  # one of OUTCOMES
    phrase_id: str | None = None
    element_id: str | None = None
    confidence: float = 0.0

    @property
    def missed(self) -> bool:
        return self.phrase_id is None

    @property
    def confident_wrong(self) -> bool:
        return self.outcome == "wrong" and self.confidence >= CONFIDENT


@dataclass
class Score:
    name: str
    judged: list[Judged] = field(default_factory=list)

    def count(self, outcome: str) -> int:
        return sum(j.outcome == outcome for j in self.judged)

    @property
    def confident_wrong(self) -> int:
        return sum(j.confident_wrong for j in self.judged)

    @property
    def missed(self) -> int:
        return sum(j.missed for j in self.judged)

    def row(self) -> dict[str, int | str]:
        return {"system": self.name, "n": len(self.judged),
                **{o: self.count(o) for o in OUTCOMES},
                "confident_wrong": self.confident_wrong, "missed": self.missed}


# --------------------------------------------------------------------------- parsing


def parse_clock(s: str) -> float:
    """'51:10' / '1:10:25' / '7.5' -> seconds."""
    parts = [float(p) for p in s.strip().split(":")]
    secs = 0.0
    for p in parts:
        secs = secs * 60 + p
    return secs


def parse_window(s: str) -> tuple[float, float]:
    """'51:10', '~59:05', '1:10:35+', '1:10:25-35' (end inherits the start's prefix)."""
    s = s.strip().lstrip("~").rstrip("+").strip()
    start, _, end = s.partition("-")
    t0 = parse_clock(start)
    if not end:
        return t0, t0
    head = start.split(":")[: -len(end.split(":"))]
    return t0, parse_clock(":".join([*head, end]))


def load_truth(path: Path, lecture: str = "") -> list[TruthRow]:
    rows = []
    with Path(path).open(newline="") as f:
        for r in csv.DictReader(f):
            if lecture and lecture.lower() not in r.get("lecture", "").lower():
                continue
            t0, t1 = parse_window(r["t"])
            rows.append(TruthRow(t0, t1, r["phrase"], r["truth"], r.get("lecture", "")))
    return rows


# --------------------------------------------------------------------------- matching


def _words(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", s.lower()))


def _norm_math(s: str) -> str:
    return re.sub(r"[\s{}\\$]", "", s.lower())


def phrase_alternatives(phrase: str) -> list[str]:
    """'the first / the second' -> both; 'here (what we had here)' -> 'here'.
    A fully parenthesized phrase ('(problem being worked)') is a description, not speech."""
    out = []
    for alt in phrase.split("/"):
        alt = re.sub(r"\([^)]*\)", "", alt).strip().strip('"')
        if w := _words(alt):
            out.append(w)
    return out


def phrase_matches(truth_phrase: str, spoken: str) -> bool:
    said = _words(spoken)
    return any(a == said or f" {a} " in f" {said} " or f" {said} " in f" {a} "
               for a in phrase_alternatives(truth_phrase))


def match_rows(rows: list[TruthRow], phrases: list[ReferencePhrase],
               tol: float = 5.0) -> dict[int, ReferencePhrase]:
    """Row index -> phrase, one-to-one, nearest in time first."""
    pairs = []
    for i, r in enumerate(rows):
        for p in phrases:
            if p.end < r.t0 - tol or p.start > r.t1 + tol:
                continue
            if phrase_matches(r.phrase, p.text):
                gap = max(r.t0 - p.end, 0.0, p.start - r.t1)
                pairs.append((gap, i, p.id, p))
    out: dict[int, ReferencePhrase] = {}
    used: set[str] = set()
    for _gap, i, pid, p in sorted(pairs, key=lambda x: (x[0], x[1], x[2])):
        if i not in out and pid not in used:
            out[i] = p
            used.add(pid)
    return out


# --------------------------------------------------------------------------- judging


def is_truth_referent(truth: str, res: Resolution, doc: LectureDoc) -> bool:
    """Strict on purpose: fuzziness must count against the system, never for it.

    The truth must appear in the LINKED ELEMENT itself (content or spoken reading). The
    model's own quote is never used: a short quote like "x" is contained in almost any
    truth and would turn a confidently wrong link into a "correct" one.
    """
    if _ID.match(truth.strip()):
        return res.element_id == truth.strip()
    want = _norm_math(truth)
    el = next((e for e in doc.elements if e.id == res.element_id), None)
    if not want or el is None:
        return False
    return any(want in _norm_math(t) for t in (el.content, el.spoken) if t)


def judge(row: TruthRow, phrase: ReferencePhrase | None, doc: LectureDoc) -> Judged:
    res = next((r for r in doc.resolutions if phrase and r.phrase_id == phrase.id), None)
    pid = phrase.id if phrase else None
    if res is None or res.status != "resolved":
        return Judged(row, "correct" if row.abstain else "unresolved", pid)
    ok = not row.abstain and is_truth_referent(row.truth, res, doc)
    return Judged(row, "correct" if ok else "wrong", pid, res.element_id, res.confidence)


def score_doc(rows: list[TruthRow], doc: LectureDoc, tol: float = 5.0) -> Score:
    matched = match_rows(rows, doc.phrases, tol)
    return Score("spokenslate", [judge(r, matched.get(i), doc) for i, r in enumerate(rows)])


def baseline(rows: list[TruthRow]) -> Score:
    """A plain transcript links nothing: right only where the truth is `unresolved`."""
    return Score("transcript (baseline)",
                 [Judged(r, "correct" if r.abstain else "unresolved") for r in rows])
