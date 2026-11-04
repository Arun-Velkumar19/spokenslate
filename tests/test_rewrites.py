"""A line wiped and rewritten in place comes back from the model as an update of the same id.
The earlier reading must be kept (in the data, and on the page when it was replaced)."""

from fixtures import el

from spokenslate.render import render_html, replaced_versions
from spokenslate.spec import BoardDiff, LectureDoc, TimedElement
from spokenslate.timeline import Timeline


def _rewritten_line() -> TimedElement:
    tl = Timeline()
    tl.apply(BoardDiff(added=[el("e2", "f'(x) =", .1, .3, .3, .35)]), 12.0)
    tl.apply(BoardDiff(updated=[el("e2", r"f'(x) = x^3 \cdot \frac{1}{x}", .1, .3, .5, .35,
                                   spoken="f prime of x equals x cubed times one over x")]),
             20.0)
    tl.apply(BoardDiff(updated=[el("e2", r"f'(x) = x^3 \cdot \frac{1}{x}", .1, .3, .5, .35,
                                   spoken="f prime of x equals x cubed times one over x")]),
             24.0)  # same text read again: not a new version
    tl.apply(BoardDiff(updated=[el("e2", "f'(x) = 3x^2", .1, .3, .3, .35)]), 36.0)
    tl.apply(BoardDiff(updated=[el("e2", r"f'(x) = 3x^2 \ln x + x^2", .1, .3, .5, .35,
                                   spoken="f prime of x equals 3 x squared ln x plus x squared")]),
             48.0)
    return tl.get("e2")


def test_update_keeps_every_earlier_reading():
    e = _rewritten_line()
    assert e.content == r"f'(x) = 3x^2 \ln x + x^2"
    assert e.erased_at is None  # replaced is not erased: only the model says "erased"
    assert [(v.content, v.replaced_at) for v in e.versions] == [
        ("f'(x) =", 20.0),
        (r"f'(x) = x^3 \cdot \frac{1}{x}", 36.0),
        ("f'(x) = 3x^2", 48.0),
    ]


def test_only_replaced_readings_count_not_partial_writing():
    e = _rewritten_line()
    assert [v.content for v in replaced_versions(e)] == [r"f'(x) = x^3 \cdot \frac{1}{x}"]


def test_page_shows_the_earlier_reading():
    e = _rewritten_line()
    html = render_html(LectureDoc(title="t", source="s", duration=60, elements=[e], words=[],
                                  phrases=[], resolutions=[]))
    assert "changed; earlier reading kept" in html
    assert "Earlier reading of this step, changed at <time>0:36</time>" in html
    assert "x cubed times one over x" in html  # the wiped attempt is still readable
    assert html.count('class="board erased"') == 1


def test_old_json_without_versions_still_loads():
    data = {"id": "e1", "kind": "math", "content": "x", "spoken": "",
            "region": {"x0": 0, "y0": 0, "x1": 1, "y1": 1},
            "first_seen": 0, "last_updated": 0, "erased_at": None}
    e = TimedElement.model_validate(data)
    assert e.versions == [] and replaced_versions(e) == []


def test_partial_read_missing_its_start_is_not_a_replacement():
    # Nov 3 mini clip: the hand covered the "f", so the first read was "(x) ="
    tl = Timeline()
    tl.apply(BoardDiff(added=[el("e1", "(x) =", .3, .3, .4, .35)]), 4.0)
    tl.apply(BoardDiff(updated=[el("e1", r"f(x)=x^3 \ln x", .3, .3, .5, .35)]), 8.0)
    e = tl.get("e1")
    assert [v.content for v in e.versions] == ["(x) ="]  # kept in the data
    assert replaced_versions(e) == []                    # but not shown as a change
