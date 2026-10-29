from fixtures import el, leonard_timeline, words

from spokenslate.pointing import candidates, pointing_at
from spokenslate.references import find_reference_phrases
from spokenslate.render import render_html
from spokenslate.spec import BoardDiff, LectureDoc, ResolveOutput
from spokenslate.validator import validate_resolution


def test_pointing_candidates_rank_by_distance():
    tl = leonard_timeline()
    elements = tl.alive_at(59)
    samples = [(58.9, 0.70, 0.45), (59.0, 0.71, 0.46), (59.1, 0.72, 0.44), (70.0, 0.1, 0.1)]
    pt = pointing_at(samples, 59.0, 59.3)
    assert pt is not None and abs(pt[0] - 0.71) < 1e-9
    ranked = candidates(elements, pt)
    assert ranked[0] == ("e2", 0.0)            # finger is on the cube-root problem
    assert candidates(elements, (0.5, 0.95)) == []  # pointing at empty board
    assert candidates(elements, None) == []


def make_doc():
    tl = leonard_timeline()
    tl.apply(BoardDiff(added=[el("e4", "<script>alert(1)</script>", .1, .8, .2, .9,
                                 kind="text")]), 130.0)
    ws = words("so if I cover this with my hand", start=59.0)
    phrases = find_reference_phrases(ws)
    res = [validate_resolution(ResolveOutput(element_id="e2", quote="ln x", confidence=0.85),
                               phrases[0], tl)]
    return LectureDoc(title="Calc 2: chain rule", source="test", duration=140, words=ws,
                      elements=tl.all(), phrases=phrases, resolutions=res)


def test_render_structure_and_escaping():
    html = render_html(make_doc())
    assert html.startswith("<!doctype html>") and '<html lang="en">' in html
    assert html.count("<h2") == 4                       # one heading per board step
    assert 'href="#step-e2"' in html                    # "this" links to the step it means
    assert "(means ln x, in step 2: d by dx of the cube root of ln x)" in html
    assert "erased at <time>2:00</time>" in html        # erased step kept and labeled
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_render_unresolved_says_so():
    doc = make_doc()
    doc.resolutions[0] = doc.resolutions[0].model_copy(
        update={"status": "unresolved", "element_id": None, "suggested_element_id": "e2"})
    html = render_html(doc)
    assert 'class="unresolved"' in html and "possibly step 2: d by dx of the cube root" in html


def test_steps_seen_together_keep_numeric_order():
    """Regression (Oct 29 run): string sort put e10 before e9 when seen at the same time."""
    tl = leonard_timeline()
    extra = [el(f"e{n}", f"x_{n}", .1, .1 * (n - 8), .2, .1 * (n - 8) + .05) for n in (9, 10)]
    tl.apply(BoardDiff(added=extra), 200.0)
    doc = LectureDoc(title="t", source="s", duration=210, words=[], elements=tl.all(),
                     phrases=[], resolutions=[])
    html = render_html(doc)
    assert html.index('id="step-e9"') < html.index('id="step-e10"')
