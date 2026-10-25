import pytest
from pydantic import ValidationError

from paperos.spec import (
    Button,
    Control,
    ControlSpec,
    DiffError,
    Region,
    SpecDiff,
    Tap,
    apply_diff,
    iter_action_names,
)


def btn(cid, action, x0=0.1, y0=0.1):
    return Control(
        id=cid,
        label=cid.upper(),
        region=Region(x0=x0, y0=y0, x1=x0 + 0.1, y1=y0 + 0.1),
        behavior=Button(on_press=Tap(action=action)),
    )


def test_parses_compound_instruction_from_json():
    # What the model should emit for: [JUMP] -> [ATTACK]  ("x2" on attack)
    raw = {
        "version": 0,
        "controls": [
            {
                "id": "c1",
                "label": "JUMP -> ATTACK x2",
                "region": {"x0": 0.1, "y0": 0.1, "x1": 0.3, "y1": 0.2},
                "behavior": {
                    "kind": "button",
                    "on_press": {
                        "op": "sequence",
                        "steps": [
                            {"op": "tap", "action": "jump"},
                            {"op": "delay", "ms": 150},
                            {"op": "repeat", "times": 2, "body": {"op": "tap", "action": "attack"}},
                        ],
                    },
                },
            }
        ],
    }
    spec = ControlSpec.model_validate(raw)
    names = list(iter_action_names(spec.controls[0].behavior.on_press))
    assert names == ["jump", "attack"]


def test_rejects_unknown_fields_and_bad_regions():
    with pytest.raises(ValidationError):
        Region(x0=0.5, y0=0.1, x1=0.4, y1=0.2)
    with pytest.raises(ValidationError):
        ControlSpec.model_validate({"version": 0, "controls": [], "code": "import os"})


def test_apply_diff_preserves_ids_and_order():
    spec = ControlSpec(version=3, controls=[btn("jump", "jump"), btn("atk", "attack", x0=0.5)])
    diff = SpecDiff(removed=["atk"], added=[btn("shield", "shield", x0=0.5)])
    new = apply_diff(spec, diff)
    assert new.version == 4
    assert [c.id for c in new.controls] == ["jump", "shield"]
    assert new.by_id()["jump"] == spec.by_id()["jump"]


def test_apply_diff_rejects_id_reuse_and_unknown_ids():
    spec = ControlSpec(version=0, controls=[btn("a", "jump")])
    with pytest.raises(DiffError):
        apply_diff(spec, SpecDiff(added=[btn("a", "attack", x0=0.5)]))
    with pytest.raises(DiffError):
        apply_diff(spec, SpecDiff(removed=["nope"]))
    with pytest.raises(DiffError):
        apply_diff(spec, SpecDiff(removed=["a"], added=[btn("a", "attack")]))
