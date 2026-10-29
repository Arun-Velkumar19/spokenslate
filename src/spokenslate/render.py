"""Render a LectureDoc as an accessible HTML page.

The page IS the product for a blind student, so structure matters more than looks:
- one <h2> per board step, in the order written, so screen-reader heading navigation
  steps through the derivation
- each step shows what was written (LaTeX, plus a plain-language reading) and the speech
  around it
- resolved references link to the step they mean; unresolved ones say so explicitly
- erased steps are kept and labeled
All model-produced text is escaped: it is untrusted.

Math format (MathML vs LaTeX vs plain language) is still an open question for SAILS;
for now each step carries LaTeX in <code> and the plain reading as the accessible label.
"""

from __future__ import annotations

from html import escape

from spokenslate.spec import LectureDoc, ReferencePhrase, Resolution, TimedElement, Word

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
.spoken { display: block; color: var(--muted); }
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
            out.append(escape(words[i].text))
            i += 1
            continue
        text = escape(p.text)
        r = res.get(p.id)
        if r and r.status == "resolved" and r.element_id in elements:
            el = elements[r.element_id]
            whole = el.spoken or el.content
            # say the exact part ("ln x") when the quote is narrower than the whole step
            part = r.quote if r.quote and len(r.quote) < len(el.content) * 0.6 else ""
            label = escape(f"{part}, in step {step_no[el.id]}: {whole}" if part
                           else f"step {step_no[el.id]}: {whole}")
            out.append(f'<a class="ref" href="#{_anchor(el.id)}">{text}</a>'
                       f' <span class="note">(means {label})</span>')
        elif r:
            hint = ""
            if r.suggested_element_id in elements:
                sug = elements[r.suggested_element_id]
                hint = (f"; possibly step {step_no[sug.id]}: "
                        f"{escape(sug.spoken or sug.content)}")
            out.append(f'<span class="unresolved">{text}</span>'
                       f' <span class="note">(unresolved{hint})</span>')
        else:
            out.append(text)
        i = p.word_end
    return " ".join(out)


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
        label = escape(el.spoken or el.content)
        speech = _speech_html(doc.words, lo, wi, doc.phrases, res, elements, step_no)
        sections.append(
            f'<section aria-labelledby="{_anchor(el.id)}">'
            f'<h2 id="{_anchor(el.id)}">Step {n + 1}, <time>{_ts(el.first_seen)}</time>{erased}</h2>'
            f'<div class="board{" erased" if el.erased_at is not None else ""}" role="math" '
            f'aria-label="{label}"><code>{escape(el.content)}</code>'
            f'<span class="spoken">{label}</span></div>'
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
