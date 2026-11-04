"""Render a LectureDoc as an accessible HTML page.

The page IS the product for a blind student, so structure matters more than looks:
- one <h2> per board step, in the order written, so screen-reader heading navigation
  steps through the derivation
- each step shows what was written (LaTeX, plus a plain-language reading) and the speech
  around it
- resolved references link to the step they mean; unresolved ones say so explicitly
- erased steps are kept and labeled
All model-produced text is escaped: it is untrusted.

Each step leads with the plain reading ("matrix: row one: boxed one, two, one"), read
first by screen readers. VoiceOver testing (Oct 30) showed why it must not be hidden:
VoiceOver reads MathML matrices as a navigable table but drops \\boxed, i.e. the pivots.
Math steps then carry MathML (converted from the model's LaTeX and sanitized in mathml.py)
for cell-by-cell exploration, and the LaTeX source in a collapsed <details>. Text steps
show their text once. Quotes in reference notes are turned into words (mathml.speakable),
so a screen reader says "zero, boxed two, minus two", not "ampersand backslash boxed".
"""

from __future__ import annotations

import re
from html import escape

from spokenslate.mathml import latex_to_mathml, speakable
from spokenslate.spec import (
    LectureDoc,
    PriorVersion,
    ReferencePhrase,
    Resolution,
    TimedElement,
    Word,
)

CSS = """
:root { color-scheme: light dark; --fg:#1b1b1b; --bg:#fdfdfb; --muted:#5d5d5d;
        --accent:#1d5fbf; --warn:#9a5b00; --line:#d9d9d4; }
@media (prefers-color-scheme: dark) { :root { --fg:#ececec; --bg:#141414; --muted:#a8a8a8;
        --accent:#7fb0ff; --warn:#f0b35c; --line:#333; } }
body { font: 18px/1.6 system-ui, sans-serif; color: var(--fg); background: var(--bg);
       max-width: 46rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
h1 { font-size: 1.6rem; } h2 { font-size: 1.15rem; margin-top: 2rem; }
.meta, time { color: var(--muted); font-size: .9rem; }
.board { border-left: 4px solid var(--accent); padding: .5rem .9rem; margin: .5rem 0;
         background: color-mix(in srgb, var(--accent) 7%, transparent); }
.board code { font-size: 1.05rem; white-space: pre-wrap; }
.board math { font-size: 1.35rem; }
menclose[notation~="box"] { border: 1px solid currentColor; padding: 0 .2em; }  /* Chrome lacks menclose */
.board details { font-size: .85rem; color: var(--muted); }
.spoken { display: block; margin: 0 0 .3rem; }
.written { display: block; }
.note { color: var(--muted); font-size: .9em; }
.erased { border-left-color: var(--warn); }
a.ref { color: var(--accent); font-weight: 600; }
.unresolved { text-decoration: underline dotted var(--warn); }
p.speech { margin: .4rem 0; }
"""


def _ts(t: float) -> str:
    m, s = divmod(int(t), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _anchor(eid: str) -> str:
    return "step-" + "".join(c if c.isalnum() else "-" for c in eid)


NOTE_MAX = 80  # characters of a step's reading repeated inside a reference note


def _short(reading: str, limit: int = NOTE_MAX) -> str:
    """A step's reading for a reference note: whole if short, else cut at a word + "…".
    The link itself jumps to the step, so the note only has to identify it."""
    reading = " ".join(reading.split())
    if len(reading) <= limit:
        return reading
    return reading[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _word(text: str) -> str:
    # Whisper writes "One-two-one" as "One -two -one"; a screen reader says "dash two"
    return re.sub(r"^-(?=[A-Za-z])", "", text)


def _speech_html(
    words: list[Word],
    lo: int,
    hi: int,
    phrases: list[ReferencePhrase],
    res: dict[str, Resolution],
    elements: dict[str, TimedElement],
    step_no: dict[str, int],
) -> str:
    starts = {p.word_start: p for p in phrases if lo <= p.word_start < hi}
    out: list[str] = []
    i = lo
    while i < hi:
        p = starts.get(i)
        if p is None:
            out.append(escape(_word(words[i].text)))
            i += 1
            continue
        text = escape(p.text)
        r = res.get(p.id)
        if r and r.status == "resolved" and r.element_id in elements:
            el = elements[r.element_id]
            # say the exact part ("ln x") when the quote is narrower than the whole step;
            # then naming the step is enough (the link goes there)
            part = speakable(r.quote) if r.quote and len(r.quote) < len(el.content) * 0.6 else ""
            label = escape(f"{part}, in step {step_no[el.id]}" if part
                           else f"step {step_no[el.id]}: {_short(el.spoken or el.content)}")
            out.append(f'<a class="ref" href="#{_anchor(el.id)}">{text}</a>'
                       f' <span class="note">(means {label})</span>')
        elif r:
            hint = ""
            if r.suggested_element_id in elements:
                sug = elements[r.suggested_element_id]
                hint = (f"; possibly step {step_no[sug.id]}: "
                        f"{escape(_short(sug.spoken or sug.content))}")
            out.append(f'<span class="unresolved">{text}</span>'
                       f' <span class="note">(unresolved{hint})</span>')
        else:
            out.append(text)
        i = p.word_end
    return " ".join(out)


def _same_text(a: str, b: str) -> bool:
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def _board_html(el: TimedElement) -> str:
    cls = "board erased" if el.erased_at is not None else "board"
    return _reading_html(el.kind, el.content, el.spoken, cls) + _earlier_html(el)


def _reading_html(kind: str, content: str, spoken: str, cls: str) -> str:
    spoken = spoken.strip()
    lead = f'<p class="spoken">{escape(spoken)}</p>' if spoken else ""
    mathml = latex_to_mathml(content, alttext=spoken) if kind == "math" else None
    if mathml is not None:
        return (f'<div class="{cls}">{lead}{mathml}'
                f"<details><summary>LaTeX</summary><code>{escape(content)}</code></details>"
                "</div>")
    if kind == "math":  # LaTeX that didn't convert safely: reading first, source after
        return (f'<div class="{cls}">{lead}'
                f"<details><summary>LaTeX</summary><code>{escape(content)}</code></details>"
                "</div>")
    if not spoken or _same_text(spoken, content):  # text written on the board: once
        return f'<div class="{cls}"><p class="written">{escape(content)}</p></div>'
    # annotation / diagram: reading first, then what was literally written
    return (f'<div class="{cls}">{lead}<p class="written"><code>{escape(content)}</code>'
            "</p></div>")


_LATEX_NOISE = re.compile(r"\\[,;:! ]|\\left|\\right|[{}\s]")


def _continues(earlier: str, later: str) -> bool:
    """True if `later` still contains all of `earlier` (ignoring LaTeX spacing): more was
    written, or the first read missed a part the hand covered ("(x) =" -> "f(x) = x^3")."""
    return _LATEX_NOISE.sub("", earlier) in _LATEX_NOISE.sub("", later)


def replaced_versions(el: TimedElement) -> list[PriorVersion]:
    """Earlier readings that were replaced, not just continued: a line wiped and rewritten,
    or a misreading the model corrected. Partial reads of a line still being written are
    left out (they are kept in the JSON)."""
    out = []
    for i, v in enumerate(el.versions):
        nxt = el.versions[i + 1].content if i + 1 < len(el.versions) else el.content
        if not _continues(v.content, nxt):
            out.append(v)
    return out


def _earlier_html(el: TimedElement) -> str:
    parts = []
    for v in replaced_versions(el):
        parts.append(f'<p class="meta">Earlier reading of this step, changed at '
                     f'<time>{_ts(v.replaced_at)}</time>:</p>'
                     + _reading_html(v.kind, v.content, v.spoken, "board erased"))
    return "".join(parts)


def _id_num(eid: str) -> int:
    digits = "".join(c for c in eid if c.isdigit())
    return int(digits) if digits else 0


def render_html(doc: LectureDoc) -> str:
    elements = {e.id: e for e in doc.elements}
    res = {r.phrase_id: r for r in doc.resolutions}
    # ids are e1, e2, ... ; sort numerically so e10 doesn't land between e1 and e2
    steps = sorted(doc.elements, key=lambda e: (e.first_seen, _id_num(e.id), e.id))
    step_no = {e.id: n + 1 for n, e in enumerate(steps)}

    # speech before each step's first appearance belongs to the previous step's section
    bounds = [e.first_seen for e in steps] + [float("inf")]
    sections: list[str] = []
    wi = 0
    lead = []
    while wi < len(doc.words) and doc.words[wi].start < bounds[0]:
        wi += 1
    if wi:
        lead.append(f'<p class="speech">{_speech_html(doc.words, 0, wi, doc.phrases, res, elements, step_no)}</p>')

    for n, el in enumerate(steps):
        lo = wi
        while wi < len(doc.words) and doc.words[wi].start < bounds[n + 1]:
            wi += 1
        erased = (f' <span class="meta">(erased at <time>{_ts(el.erased_at)}</time>;'
                  f" kept here)</span>" if el.erased_at is not None else "")
        if replaced_versions(el):
            erased += ' <span class="meta">(changed; earlier reading kept)</span>'
        speech = _speech_html(doc.words, lo, wi, doc.phrases, res, elements, step_no)
        sections.append(
            f'<section aria-labelledby="{_anchor(el.id)}">'
            f'<h2 id="{_anchor(el.id)}">Step {n + 1}, <time>{_ts(el.first_seen)}</time>{erased}</h2>'
            + _board_html(el)
            + (f'<p class="speech">{speech}</p>' if speech else "")
            + "</section>"
        )

    resolved = sum(r.status == "resolved" for r in doc.resolutions)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(doc.title)}</title><style>{CSS}</style></head><body><main>"
        f"<h1>{escape(doc.title)}</h1>"
        f'<p class="meta">{len(steps)} board steps · {len(doc.phrases)} spoken references, '
        f"{resolved} resolved · source: {escape(doc.source)}</p>"
        + "".join(lead) + "".join(sections)
        + "</main></body></html>"
    )
