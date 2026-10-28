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
