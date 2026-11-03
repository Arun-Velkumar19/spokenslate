from fixtures import el, leonard_timeline

from spokenslate.mathml import latex_to_mathml, speakable
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
    assert "aria-hidden" not in html            # VoiceOver drops \\boxed: never hide the reading
    first = html.index('id="step-e1"')
    assert html.index('<p class="spoken">', first) < html.index("<math ", first)  # reading first
    assert "<details><summary>LaTeX</summary>" in html
    assert "<script>" not in html                          # hostile step fell back to escaped
    assert '<p class="spoken">x then a script</p>' in html and 'role="math"' not in html


def test_quotes_become_words_a_screen_reader_says_well():
    assert speakable(r"0 & \boxed{2} & -2") == "0, boxed 2, minus 2"
    assert speakable(r"(21) \rightarrow") == "(21) to"        # \right must not eat \rightarrow
    assert speakable(r"\begin{bmatrix}1 & 2 \\ 3 & 4\end{bmatrix}") == "1, 2; 3, 4"
    assert "\\" not in speakable(r"\weird{q} + \ln x")


def test_text_steps_once_and_notes_in_words():
    from fixtures import words

    from spokenslate.references import find_reference_phrases
    from spokenslate.spec import ResolveOutput
    from spokenslate.validator import validate_resolution

    tl = leonard_timeline()
    tl.apply(BoardDiff(added=[
        el("e4", "success", .0, .2, .1, .3, spoken="success", kind="text"),
        el("e5", r"\begin{bmatrix}1 & 2 & 1 \\ 0 & \boxed{2} & -2\end{bmatrix}", .5, .2, .9, .5,
           spoken="matrix: row one: one, two, one; row two: zero, boxed two, minus two"),
    ]), 130.0)
    ws = words("subtract this row now", start=131.0)
    (p,) = find_reference_phrases(ws)
    res = validate_resolution(
        ResolveOutput(element_id="e5", quote=r"0 & \boxed{2} & -2", confidence=0.9), p, tl)
    doc = LectureDoc(title="t", source="s", duration=140, words=ws, elements=tl.all(),
                     phrases=[p], resolutions=[res])
    html = render_html(doc)
    assert html.count(">success<") == 1                     # was shown twice
    assert "(means 0, boxed 2, minus 2, in step 5)" in html
    assert "&amp; \\boxed" not in html.split("<details>")[0]  # no raw LaTeX in the reading


def test_long_readings_are_cut_in_notes_and_dash_words_cleaned():
    from fixtures import words

    from spokenslate.render import _short, _word

    assert _short("short one") == "short one"
    long = "matrix: row one: boxed one, two, one; row two: zero, boxed two, minus two; row three"
    cut = _short(long)
    assert cut.endswith("…") and len(cut) <= 81 and long.startswith(cut[:-1])
    assert [_word(w.text) for w in words("One -two -one -2")] == ["One", "two", "one", "-2"]


def test_powers_read_naturally():
    assert speakable("x^2") == "x squared"
    assert speakable("x^{3} + y^n") == "x cubed plus y to the n"
