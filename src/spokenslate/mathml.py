"""LaTeX (model output) -> MathML that screen readers can read and navigate as math.

latex2mathml does the conversion but passes text through unescaped (\\text{<script>} comes
out as a live <script> element), and unknown commands come out as <mi>\\cmd</mi>. Board
content is untrusted model output, so the result is re-parsed as XML, checked against a
MathML element/attribute allowlist, and re-serialized (which escapes all text). Anything
that fails any check returns None and the caller shows the escaped LaTeX instead.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
ET.register_namespace("", MATHML_NS)

ELEMENTS = {
    "math", "mrow", "mi", "mn", "mo", "ms", "mtext", "mspace", "msup", "msub", "msubsup",
    "mfrac", "msqrt", "mroot", "mfenced", "menclose", "mover", "munder", "munderover",
    "mtable", "mtr", "mtd", "mstyle", "mpadded", "mphantom",
}
ATTRS = {
    "display", "notation", "stretchy", "fence", "form", "separator", "lspace", "rspace",
    "mathvariant", "columnalign", "rowalign", "rowspacing", "columnspacing", "columnlines",
    "rowlines", "frame", "accent", "accentunder", "linethickness", "displaystyle",
    "scriptlevel", "width", "height", "depth", "minsize", "maxsize", "symmetric",
    "movablelimits", "largeop", "open", "close", "separators", "alttext",
}


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def latex_to_mathml(latex: str, alttext: str = "") -> str | None:
    """Sanitized inline MathML for `latex`, or None if it can't be converted safely."""
    if not latex.strip():
        return None
    try:
        from latex2mathml.converter import convert

        root = ET.fromstring(convert(latex))
    except Exception:  # noqa: BLE001  latex2mathml raises many types; any failure -> fallback
        return None
    for node in root.iter():
        if _local(node.tag) not in ELEMENTS:
            return None
        if any(_local(a) not in ATTRS and a != "xmlns" for a in node.attrib):
            return None
        if "\\" in (node.text or ""):  # unknown command leaked through as text
            return None
    if _local(root.tag) != "math":
        return None
    if alttext:
        root.set("alttext", alttext)
    return ET.tostring(root, encoding="unicode")
