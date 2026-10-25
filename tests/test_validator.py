from paperos.adapters.keyboard import BITRUN
from paperos.spec import (
    Button,
    Control,
    ControlSpec,
    Delay,
    Hold,
    Region,
    Release,
    Repeat,
    Sequence,
    Slider,
    SliderZone,
    Tap,
    Toggle,
)
from paperos.validator import validate


def ctrl(cid, behavior, x0=0.1):
    return Control(id=cid, label=cid, region=Region(x0=x0, y0=0.1, x1=x0 + 0.15, y1=0.25),
                   behavior=behavior)


def test_valid_demo_layout_passes():
    spec = ControlSpec(version=0, controls=[
        ctrl("run", Toggle(on_enable=Hold(action="right"), on_disable=Release(action="right"))),
        ctrl("jump", Button(on_press=Tap(action="jump")), x0=0.3),
        ctrl("combo", Button(on_press=Sequence(steps=[
            Tap(action="jump"), Delay(ms=150), Tap(action="attack")])), x0=0.5),
        ctrl("dir", Slider(axis="horizontal", zones=[
            SliderZone(lo=0.0, hi=0.4, action="left"),
            SliderZone(lo=0.4, hi=0.6, action=None),
            SliderZone(lo=0.6, hi=1.0, action="right")]), x0=0.7),
    ])
    r = validate(spec, BITRUN)
    assert r.ok, r.errors


def test_unknown_and_unholdable_actions_blocked():
    spec = ControlSpec(version=0, controls=[
        ctrl("x", Button(on_press=Tap(action="rm -rf"))),
        ctrl("y", Toggle(on_enable=Hold(action="jump"), on_disable=Release(action="jump")), x0=0.5),
    ])
    r = validate(spec, BITRUN)
    assert any("unknown action" in e for e in r.errors)
    assert any("cannot be held" in e for e in r.errors)


def test_limits_and_overlaps():
    spec = ControlSpec(version=0, controls=[
        ctrl("spam", Button(on_press=Repeat(times=50, body=Tap(action="attack")))),
        ctrl("wait", Button(on_press=Delay(ms=60_000)), x0=0.2),  # overlaps "spam"
    ])
    r = validate(spec, BITRUN)
    assert any("repeat" in e for e in r.errors)
    assert any("total delay" in e for e in r.errors)
    assert any("overlap" in e for e in r.errors)


def test_overlapping_slider_zones_blocked():
    spec = ControlSpec(version=0, controls=[ctrl("s", Slider(axis="horizontal", zones=[
        SliderZone(lo=0.0, hi=0.6, action="left"), SliderZone(lo=0.5, hi=1.0, action="right")]))])
    assert any("zones overlap" in e for e in validate(spec, BITRUN).errors)
