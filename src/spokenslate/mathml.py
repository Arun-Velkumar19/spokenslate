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


_CMD_WORDS = {
    "cdot": "times", "times": "times", "div": "divided by", "pm": "plus or minus",
    "to": "to", "rightarrow": "to", "leftarrow": "from", "infty": "infinity",
    "le": "less than or equal to", "leq": "less than or equal to", "ge": "at least",
    "geq": "at least", "ne": "not equal to", "neq": "not equal to", "approx": "about",
    "pi": "pi", "theta": "theta", "alpha": "alpha", "beta": "beta", "lambda": "lambda",
    "ln": "ln", "log": "log", "sin": "sine", "cos": "cosine", "tan": "tangent",
}


def speakable(latex: str) -> str:
    """Short LaTeX fragment (a quoted row or sub-expression) -> words a screen reader says
    well: "0 & \\boxed{2} & -2" -> "0, boxed 2, minus 2". Deliberately small; anything it
    doesn't know loses its backslash instead of being read as "backslash ..."."""
    import re

    s = latex
    s = re.sub(r"\\begin\{[a-z]*matrix\}|\\end\{[a-z]*matrix\}", " ", s)
    s = re.sub(r"\\boxed\{([^{}]*)\}", r" boxed \1 ", s)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r" \1 over \2 ", s)
    s = re.sub(r"\\sqrt\[([^\]]*)\]\{([^{}]*)\}", r" root \1 of \2 ", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r" square root of \1 ", s)
    s = re.sub(r"\^\{([^{}]*)\}|\^(\w)", lambda m: f" to the {m.group(1) or m.group(2)} ", s)
    s = re.sub(r"_\{([^{}]*)\}|_(\w)", lambda m: f" sub {m.group(1) or m.group(2)} ", s)
    s = re.sub(r"\\(?:left|right)(?![A-Za-z])", " ", s)
    s = re.sub(r"\\\\", " ; ", s)
    s = s.replace("&", " , ")
    s = re.sub(r"\\([A-Za-z]+)", lambda m: f" {_CMD_WORDS.get(m.group(1), m.group(1))} ", s)
    s = re.sub(r"(^|[\s(,;=])-(?=\s*[\w(])", r"\1 minus ", s)
    s = s.replace("+", " plus ").replace("=", " equals ").replace("{", " ").replace("}", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"([(\[])\s+", r"\1", s)
    s = re.sub(r"\s+([)\]])", r"\1", s)
    s = re.sub(r"\s+([,;])", r"\1", s)
    return re.sub(r"([,;])(?:[,;\s]+)", r"\1 ", s).strip(" ,;")
