from fixtures import el, leonard_timeline

from spokenslate.mathml import latex_to_mathml
from spokenslate.render import render_html
from spokenslate.spec import BoardDiff, LectureDoc


def test_board_latex_becomes_navigable_mathml():
    m = latex_to_mathml(r"0 \boxed{2} -2", alttext="zero, boxed two, minus two")
    assert m.startswith('<math xmlns="http://www.w3.org/1998/Math/MathML"')
    assert '<menclose notation="box">' in m and 'alttext="zero, boxed two, minus two"' in m
    assert "<mtable>" in latex_to_mathml(r"\begin{bmatrix}1&2\\3&4\end{bmatrix}")


def test_untrusted_latex_never_becomes_markup():
    assert latex_to_mathml(r"x \text{<script>alert(1)</script>}") is None   # raw element
    assert latex_to_mathml(r"\unknowncmd{x}") is None                       # leaked command
    assert latex_to_mathml(r"\frac{1}{") is None                            # malformed
    assert latex_to_mathml("a & b") is None                                 # not well-formed
    assert latex_to_mathml("   ") is None
    m = latex_to_mathml("x", alttext='"><img src=x onerror=alert(1)>')
    assert "<img" not in m and "&quot;&gt;&lt;img" in m                    # alttext escaped


def test_render_uses_mathml_and_falls_back_safely():
    tl = leonard_timeline()
    tl.apply(BoardDiff(added=[el("e4", r"x \text{<script>alert(1)</script>}", .1, .8, .2, .9,
                                 spoken="x then a script")]), 130.0)
    doc = LectureDoc(title="t", source="s", duration=140, words=[], elements=tl.all(),
                     phrases=[], resolutions=[])
    html = render_html(doc)
    assert html.count("<math ") == 3                       # the three Leonard math steps
    assert '<span class="spoken" aria-hidden="true">' in html  # not read twice
    assert "<details><summary>LaTeX</summary>" in html
    assert "<script>" not in html                          # hostile step fell back to escaped
    assert 'role="math" aria-label="x then a script"' in html
