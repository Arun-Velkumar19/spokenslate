"""Score a processed lecture against the reference benchmark.

    python scripts/score.py --truth eval/references.csv --doc site/clip.json
    python scripts/score.py --truth eval/references.csv --doc site/clip.json \
        --lecture "Lecture 6.1" --offset -3060 -v

Matches each truth row to a detected phrase (time window +/- --tol seconds, phrase text),
then reports correct / unresolved / wrong / confident-wrong (wrong at confidence >= 0.7)
for Seed and for a plain-transcript baseline that resolves nothing. Use --offset when the
CSV times are in the full lecture and the doc is a clip (clip t = lecture t + offset).
See src/paperos/scoring.py for the rules.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from paperos.scoring import baseline, load_truth, score_doc
from paperos.spec import LectureDoc

COLS = ("system", "n", "correct", "unresolved", "wrong", "confident_wrong", "missed")


def table(rows: list[dict[str, int | str]]) -> str:
    widths = [max(len(c), *(len(str(r[c])) for r in rows)) for c in COLS]

    def line(vals: list) -> str:
        return "  ".join(str(v).ljust(w) for v, w in zip(vals, widths, strict=True))

    return "\n".join([line(list(COLS)), *(line([r[c] for c in COLS]) for r in rows)])


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--truth", required=True, help="ground-truth CSV (eval/references.csv)")
    ap.add_argument("--doc", required=True, help="LectureDoc JSON from `paperos process`")
    ap.add_argument("--lecture", default="", help="only rows whose lecture column contains this")
    ap.add_argument("--offset", type=float, default=0.0, help="seconds added to CSV times")
    ap.add_argument("--tol", type=float, default=5.0, help="time-window slack in seconds")
    ap.add_argument("-v", "--verbose", action="store_true", help="per-row outcomes")
    args = ap.parse_args(argv)

    rows = load_truth(Path(args.truth), args.lecture)
    for r in rows:
        r.t0 += args.offset
        r.t1 += args.offset
    doc = LectureDoc.model_validate_json(Path(args.doc).read_text())
    seed = score_doc(rows, doc, args.tol)
    print(table([seed.row(), baseline(rows).row()]))
    if args.verbose:
        for j in seed.judged:
            flag = "  CONFIDENT-WRONG" if j.confident_wrong else ""
            print(f"{j.row.t0:8.1f}s  {j.row.phrase!r:40} -> {j.outcome:10} "
                  f"phrase={j.phrase_id or '-'} element={j.element_id or '-'} "
                  f"conf={j.confidence:.2f}{flag}")
    if not rows:
        print("no truth rows (empty CSV or --lecture filter matched nothing)")


if __name__ == "__main__":
    main()
