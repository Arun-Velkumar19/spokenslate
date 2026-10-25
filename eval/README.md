# Evaluation logs

One CSV per gate. Append a row per trial; commit results to `results/`.
Raw images/audio stay in `data/captures/` (gitignored); reference them by filename.

| File | Gate | Pass bar |
|---|---|---|
| `press_trials.csv` | physical interaction | ≥27/30 presses, ≤3/30 false hovers |
| `compile_trials.csv` | semantic compilation | ≥8/10, ≥half drawn by others |
| `edit_trials.csv` | live modification | edit applied, target never restarted, untouched controls unaffected |
| `latency.csv` | compile / edit-to-ready | measured, reported as median + worst |

Log failures too. The final numbers go on screen in the demo.
