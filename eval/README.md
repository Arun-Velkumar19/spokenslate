# Evaluation

The number that matters: **confident-wrong = 0.** A wrong link misleads a blind student;
"unresolved" is honest. Report correct / unresolved / wrong, and wrong-with-confidence ≥ 0.7.

| File | What | Gate (Oct 29) |
|---|---|---|
| `references.csv` | one row per spoken reference, ground truth written BEFORE asking the model | ≥15 refs, 2 lecturers, ≥80% correct, 0 confident-wrong, abstains on ambiguous |
| `latency.csv` | model call timings and attempts | report median + worst |
| `results/` | committed result snapshots (playground runs, pipeline runs) | — |

Rules: write the truth column first. Include genuinely ambiguous moments (truth =
`unresolved`). Note any help the prompt gave (e.g. manually aligned words per frame).
Raw video stays in `data/` (gitignored); reference lectures by title + timestamp.

## Runs so far (hand-judged)

| File | Clip | Refs | Correct | Confident-wrong | Unresolved | Notes |
|---|---|---|---|---|---|---|
| `results/2026-10-27-playground.csv` | Leonard, Calc 2 (playground, frames chosen by hand) | 10 | 10 | 0 | 0 | not the pipeline |
| `results/2026-10-29-strang-first-run.csv` | MIT OCW 18.06 excerpt | 14 (+1 false positive) | 4 | 1 | 9 (2 correct abstentions) | camera-operated, rows split |
| `results/2026-10-29-strang-matrix-prompt.csv` | same | 14 | 6 | 1 | 7 (2 correct abstentions) | matrix = one element |
| `results/2026-10-30-strang-sam.csv` | same | 14 | 7 | 2 | 5 (1 correct abstention) | + SAM; both confident-wrongs are "the pivots are there" → the matrix holding them (strict label) |
| `results/2026-11-01-whiteboard.csv` | own whiteboard recording | 16 | 11 | 0 | 5 | temperature 0, SAM, fingertips |

A plain transcript links none of these references. The truth column in the Oct 29–Nov 1
files is a description judged by hand (not an element-content string), so `scripts/score.py`
is not used on them yet. Runs before Nov 1 used the API's default temperature (1), so each is
a single random sample.
