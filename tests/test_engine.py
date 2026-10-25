from paperos.adapters.keyboard import BITRUN, KeyboardAdapter
from paperos.runtime.engine import Engine
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
    SpecDiff,
    Tap,
    Toggle,
    apply_diff,
)


def ctrl(cid, behavior, x0=0.1):
    return Control(id=cid, label=cid, region=Region(x0=x0, y0=0.1, x1=x0 + 0.15, y1=0.25),
                   behavior=behavior)


def make():
    adapter = KeyboardAdapter(BITRUN, dry_run=True)
    slept = []
    eng = Engine(adapter, sleep=slept.append, threaded=False)
    return adapter, eng, slept


def test_compound_button_runs_in_order():
    adapter, eng, slept = make()
    eng.load(ControlSpec(version=0, controls=[ctrl("c", Button(on_press=Sequence(steps=[
        Tap(action="jump"), Delay(ms=250), Repeat(times=2, body=Tap(action="attack"))])))]))
    eng.press("c")
    assert adapter.log_events == [("tap", "jump"), ("tap", "attack"), ("tap", "attack")]
    assert slept == [0.25]


def test_toggle_holds_then_releases():
    adapter, eng, _ = make()
    eng.load(ControlSpec(version=0, controls=[
        ctrl("run", Toggle(on_enable=Hold(action="right"), on_disable=Release(action="right")))]))
    eng.press("run")
    eng.press("run")
    assert adapter.log_events == [("down", "right"), ("up", "right")]


def test_slider_switches_held_action():
    adapter, eng, _ = make()
    eng.load(ControlSpec(version=0, controls=[ctrl("dir", Slider(axis="horizontal", zones=[
        SliderZone(lo=0.0, hi=0.4, action="left"), SliderZone(lo=0.4, hi=0.6, action=None),
        SliderZone(lo=0.6, hi=1.0, action="right")]))]))
    for v in (0.1, 0.2, 0.5, 0.9, None):
        eng.slide("dir", v)
    assert adapter.log_events == [("down", "left"), ("up", "left"), ("down", "right"),
                                  ("up", "right")]


def test_recompile_keeps_unaffected_toggle_and_releases_removed():
    """The live-edit guarantee: crossing out ATTACK must not stop RUN."""
    adapter, eng, _ = make()
    run = ctrl("run", Toggle(on_enable=Hold(action="right"), on_disable=Release(action="right")))
    spec = ControlSpec(version=0, controls=[run, ctrl("atk", Button(on_press=Tap(action="attack")),
                                                      x0=0.5)])
    eng.load(spec)
    eng.press("run")
    new = apply_diff(spec, SpecDiff(removed=["atk"], added=[
        ctrl("shield", Button(on_press=Tap(action="shield")), x0=0.5)]))
    eng.load(new)
    assert "run" in eng.toggled                     # still running right
    assert adapter.log_events == [("down", "right")]  # no spurious release
    eng.press("shield")
    assert adapter.log_events[-1] == ("tap", "shield")


def test_removed_toggle_is_released():
    adapter, eng, _ = make()
    run = ctrl("run", Toggle(on_enable=Hold(action="right"), on_disable=Release(action="right")))
    spec = ControlSpec(version=0, controls=[run])
    eng.load(spec)
    eng.press("run")
    eng.load(apply_diff(spec, SpecDiff(removed=["run"])))
    assert adapter.log_events == [("down", "right"), ("up", "right")]
