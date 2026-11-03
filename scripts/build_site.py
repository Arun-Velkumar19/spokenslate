"""Build the public demo site: one accessible page per processed lecture + a landing page.

    python scripts/build_site.py --out public/ \
        site/board.json:product-rule site/sam/strang.json:mit-18-06-elimination

Each argument is LECTURE_JSON:SLUG. Pages are rendered with the same renderer as
`spokenslate render`; the landing page lists them with their step / reference counts.
The output folder is what gets published (e.g. to a gh-pages branch).
"""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

from spokenslate.render import CSS, render_html
from spokenslate.spec import LectureDoc

REPO = "https://github.com/Arun-Velkumar19/spokenslate"


def lecture_item(doc: LectureDoc, slug: str) -> str:
    linked = sum(r.status == "resolved" for r in doc.resolutions)
    return (f'<li><a href="{escape(slug)}.html">{escape(doc.title)}</a>'
            f'<span class="meta">{len(doc.elements)} board steps · {len(doc.phrases)} spoken '
            f"references, {linked} linked · {escape(doc.source)}</span></li>")


def index_html(items: list[str]) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>SpokenSlate: the board, for everyone in the room</title>"
        f"<style>{CSS} li {{ margin: .6rem 0; }} .meta {{ display: block; }}</style>"
        "</head><body><main>"
        "<h1>SpokenSlate</h1>"
        "<p><strong>Transcripts tell you what the professor said. SpokenSlate tells you what "
        "they meant.</strong></p>"
        "<p>A recorded whiteboard lecture, turned into a page a screen reader can follow: every "
        "board step in order, and spoken references like <em>“this term cancels”</em> linked to "
        "the exact thing on the board. When it isn’t sure, it says <em>unresolved</em> instead "
        "of guessing.</p>"
        "<h2>Lectures</h2><ul>" + "".join(items) + "</ul>"
        "<h2>Reading a page with a screen reader</h2><ul>"
        "<li>Each board step is a heading. Jump between steps with your screen reader’s "
        "heading key (VoiceOver: Control-Option-Command-H; NVDA and JAWS: H).</li>"
        "<li>Each step starts with a plain-language reading, then the math itself, which you "
        "can explore cell by cell, then the LaTeX source behind a “LaTeX” toggle.</li>"
        "<li>In the speech, a linked reference says what it means, for example "
        "<em>“this (means minus 2, in step 3)”</em>. Follow the link to jump to that step.</li>"
        "<li>“Unresolved” means the system wasn’t confident. It may add “possibly step N”, "
        "which is a hint, not a claim.</li>"
        "<li>Steps that were erased on the board are kept and labelled.</li></ul>"
        "<h2>How it works</h2><p>Meta’s <strong>SAM 3.1</strong> masks the lecturer out of "
        "each board image; <strong>Muse Spark</strong> reads the board into steps and "
        "decides what each spoken reference points at, using the words at that instant, the "
        "lecturer’s fingertip, and frames before and after. Every answer passes a validator; "
        "anything uncertain becomes “unresolved”.</p>"
        f'<p><a href="{REPO}">Source code, method and evaluation on GitHub</a></p>'
        "<h2>Credits</h2><p>The MIT 18.06 page is derived from Gilbert Strang’s Linear Algebra "
        "Lecture 2, MIT OpenCourseWare, licensed "
        '<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC BY-NC-SA 4.0</a>; '
        "that page is shared under the same license. The product-rule lecture is recorded by "
        "Arun Velkumar.</p>"
        "</main></body></html>"
    )


def build(pairs: list[tuple[Path, str]], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    items, written = [], []
    for src, slug in pairs:
        doc = LectureDoc.model_validate_json(Path(src).read_text())
        page = out / f"{slug}.html"
        page.write_text(render_html(doc))
        items.append(lecture_item(doc, slug))
        written.append(page)
    (out / "index.html").write_text(index_html(items))
    (out / ".nojekyll").write_text("")  # serve files as-is on GitHub Pages
    return [*written, out / "index.html"]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("lectures", nargs="+", help="LECTURE_JSON:SLUG")
    args = ap.parse_args(argv)
    pairs = [(Path(a.rsplit(":", 1)[0]), a.rsplit(":", 1)[1]) for a in args.lectures]
    for p in build(pairs, args.out):
        print("wrote", p)


if __name__ == "__main__":
    main()
