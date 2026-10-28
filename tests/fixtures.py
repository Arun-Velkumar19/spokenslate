"""Shared fixtures modeled on the Oct 27 playground test (Professor Leonard, Calc 2 Lecture 6.1)."""

from spokenslate.spec import BoardDiff, BoardElement, Region, Word
from spokenslate.timeline import Timeline


def el(eid, content, x0, y0, x1, y1, spoken="", kind="math"):
    return BoardElement(id=eid, kind=kind, content=content, spoken=spoken,
                        region=Region(x0=x0, y0=y0, x1=x1, y1=y1))


CHAIN = el("e1", r"\frac{d}{dx}[(x^2+1)^3] = 3(x^2+1)^2 \cdot \frac{d}{dx}[x^2+1]",
           0.08, 0.40, 0.48, 0.50, "d by dx of x squared plus one, cubed")
CUBE_ROOT = el("e2", r"\frac{d}{dx}[\sqrt[3]{\ln x}] \to \frac{d}{dx}[(\ln x)^{1/3}]",
               0.55, 0.40, 0.92, 0.50, "d by dx of the cube root of ln x")
PRODUCT = el("e3", r"\frac{d}{dx}[x^3 \ln 5x]", 0.05, 0.62, 0.30, 0.70,
             "d by dx of x cubed times ln of 5x")


def words(text: str, start: float = 0.0, step: float = 0.3) -> list[Word]:
    out, t = [], start
    for w in text.split():
        out.append(Word(text=w, start=round(t, 2), end=round(t + step * 0.8, 2)))
        t += step
    return out


def leonard_timeline() -> Timeline:
    tl = Timeline()
    tl.apply(BoardDiff(added=[CHAIN]), 10.0)
    tl.apply(BoardDiff(added=[CUBE_ROOT]), 40.0)
    tl.apply(BoardDiff(erased=["e1"], added=[PRODUCT]), 120.0)
    return tl
