"""ControlSpec: the contract between the compiler (Muse) and everything deterministic.

Freeze primitives, not notation. People draw whatever notation they like (arrows,
"then", numbered steps, "x2"); the model's only job is to map it onto these types.
The model never emits code. Anything it emits must parse as a ControlSpec or SpecDiff,
then pass the validator against the active adapter's action whitelist.

Coordinates are normalized to the rectified page: (0, 0) top-left, (1, 1) bottom-right.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------- actions


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Tap(_Strict):
    """Press and release an adapter action once (e.g. jump)."""

    op: Literal["tap"] = "tap"
    action: str


class Hold(_Strict):
    """Start holding an adapter action until a matching Release (e.g. run right)."""

    op: Literal["hold"] = "hold"
    action: str


class Release(_Strict):
    op: Literal["release"] = "release"
    action: str


class Delay(_Strict):
    op: Literal["delay"] = "delay"
    ms: int = Field(ge=0)


class Sequence(_Strict):
    """Run steps in order. This is how drawn arrows / 'then' compile."""

    op: Literal["sequence"] = "sequence"
    steps: list[Action] = Field(min_length=1)


class Repeat(_Strict):
    """Run `body` n times. This is how 'x2' compiles."""

    op: Literal["repeat"] = "repeat"
    times: int = Field(ge=1)
    body: Action


Action = Annotated[
    Tap | Hold | Release | Delay | Sequence | Repeat,
    Field(discriminator="op"),
]

Sequence.model_rebuild()
Repeat.model_rebuild()

# --------------------------------------------------------------------------- controls


class Region(_Strict):
    """Axis-aligned box on the rectified page, normalized 0..1."""

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

    def overlaps(self, other: Region) -> bool:
        return not (
            self.x1 <= other.x0 or other.x1 <= self.x0 or self.y1 <= other.y0 or other.y1 <= self.y0
        )


class Button(_Strict):
    kind: Literal["button"] = "button"
    on_press: Action


class Toggle(_Strict):
    """Tap once for on, tap again for off. Primary way to express held keys (RUN →)."""

    kind: Literal["toggle"] = "toggle"
    on_enable: Action
    on_disable: Action


class SliderZone(_Strict):
    """While the slider value is in [lo, hi), `action` is held. action=None means idle."""

    lo: float = Field(ge=0, le=1)
    hi: float = Field(ge=0, le=1)
    action: str | None = None


class Slider(_Strict):
    """Fingertip position along the drawn line → value 0..1 → held action for its zone."""

    kind: Literal["slider"] = "slider"
    axis: Literal["horizontal", "vertical"]
    zones: list[SliderZone] = Field(min_length=1)


Behavior = Annotated[Button | Toggle | Slider, Field(discriminator="kind")]


class Control(_Strict):
    id: str = Field(min_length=1, description="Stable across recompiles. Never reuse a removed id.")
    label: str = Field(description="What the person wrote, verbatim as best read.")
    region: Region
    behavior: Behavior
    rationale: str = Field(
        default="",
        description="One line: how the drawn notation was interpreted. Shown in the overlay.",
    )


class Question(_Strict):
    """Asked instead of guessing when the drawing is ambiguous."""

    control_id: str | None = None
    text: str
    options: list[str] = Field(default_factory=list)


class ControlSpec(_Strict):
    version: int = Field(ge=0)
    controls: list[Control] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)

    def by_id(self) -> dict[str, Control]:
        return {c.id: c for c in self.controls}


class SpecDiff(_Strict):
    """Recompile output: only what changed. Unchanged controls keep their ids and state."""

    added: list[Control] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    updated: list[Control] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.updated)


class DiffError(ValueError):
    pass


def apply_diff(spec: ControlSpec, diff: SpecDiff) -> ControlSpec:
    """Deterministically apply a SpecDiff. Raises DiffError on inconsistent diffs."""
    current = spec.by_id()
    for cid in diff.removed:
        if cid not in current:
            raise DiffError(f"removed unknown control {cid!r}")
        del current[cid]
    for c in diff.updated:
        if c.id not in current:
            raise DiffError(f"updated unknown control {c.id!r}")
        current[c.id] = c
    for c in diff.added:
        if c.id in current or c.id in diff.removed or c.id in spec.by_id():
            raise DiffError(f"added control reuses id {c.id!r}")
        current[c.id] = c
    ordered = [current[c.id] for c in spec.controls if c.id in current]
    ordered += [c for c in diff.added]
    return ControlSpec(version=spec.version + 1, controls=ordered, questions=diff.questions)


def iter_action_names(action: Action):
    """Yield every adapter action name referenced inside an Action tree."""
    if isinstance(action, (Tap, Hold, Release)):
        yield action.action
    elif isinstance(action, Sequence):
        for s in action.steps:
            yield from iter_action_names(s)
    elif isinstance(action, Repeat):
        yield from iter_action_names(action.body)
