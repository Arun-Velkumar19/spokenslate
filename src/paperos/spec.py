"""Seed data contracts.

A lecture is two streams: what was SAID (timestamped words) and what was WRITTEN (board
elements that appear, change, and get erased). Seed joins them, and resolves spoken
references ("this term", "the first", "over here") to specific board elements.

Rules the contracts enforce:
- The model never sets times. It reports what is on the board (BoardDiff) and what a
  phrase refers to (ResolveOutput). The pipeline stamps times and the validator decides.
- Element ids are stable for the whole lecture and never reused, even after erasing.
- Erased elements are kept (with erased_at), never deleted.

Coordinates are normalized to the board image: (0, 0) top-left, (1, 1) bottom-right.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- speech


class Word(_Strict):
    text: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Word:
        if self.end < self.start:
            raise ValueError("word end before start")
        return self


# --------------------------------------------------------------------------- board


class Region(_Strict):
    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> Region:
        if not (self.x0 < self.x1 and self.y0 < self.y1):
            raise ValueError("region must have x0 < x1 and y0 < y1")
        return self

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def distance(self, x: float, y: float) -> float:
        """0 inside the box, else Euclidean distance to its edge."""
        dx = max(self.x0 - x, 0.0, x - self.x1)
        dy = max(self.y0 - y, 0.0, y - self.y1)
        return (dx * dx + dy * dy) ** 0.5


ElementKind = Literal["math", "text", "diagram", "annotation"]


class BoardElement(_Strict):
    """One thing on the board, as the model reads it. Usually one written line."""

    id: str = Field(min_length=1)
    kind: ElementKind
    content: str = Field(description="As written. LaTeX for math.")
    spoken: str = Field(default="", description="Plain-language reading for screen readers.")
    region: Region


class BoardDiff(_Strict):
    """Model output for one keyframe: only what changed since the current board."""

    added: list[BoardElement] = Field(default_factory=list)
    updated: list[BoardElement] = Field(default_factory=list)  # same id, more written / fixed
    erased: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.updated or self.erased)


class TimedElement(BoardElement):
    """A board element with pipeline-owned timing. Never produced by the model."""

    first_seen: float = Field(ge=0)
    last_updated: float = Field(ge=0)
    erased_at: float | None = None

    def alive_at(self, t: float) -> bool:
        return self.first_seen <= t and (self.erased_at is None or t < self.erased_at)


# --------------------------------------------------------------------------- references

RefKind = Literal["deictic", "role", "anaphora"]


class ReferencePhrase(_Strict):
    """A spoken phrase that points at something.

    deictic: "this term", "over here"; role: "the first", "the inside";
    anaphora: "the problem I just gave you", "the equation from before".
    """

    id: str
    text: str
    kind: RefKind
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    word_start: int = Field(ge=0)  # index into the word list, inclusive
    word_end: int = Field(ge=0)    # exclusive


class ResolveOutput(_Strict):
    """Model output for one phrase. element_id=None means the model abstained."""

    element_id: str | None
    quote: str = Field(default="", description="The referent as written on the board.")
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class Resolution(_Strict):
    """Validator output: what the user actually sees."""

    phrase_id: str
    status: Literal["resolved", "unresolved"]
    element_id: str | None = None
    quote: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    note: str = ""                      # why unresolved
    suggested_element_id: str | None = None  # low-confidence guess, shown as "possibly"


# --------------------------------------------------------------------------- document


class LectureDoc(_Strict):
    title: str
    source: str
    duration: float = Field(ge=0)
    words: list[Word]
    elements: list[TimedElement]
    phrases: list[ReferencePhrase]
    resolutions: list[Resolution]
    models: dict[str, str] = Field(default_factory=dict)
