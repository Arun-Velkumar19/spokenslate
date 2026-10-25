# PaperOS build plan

Oct 26 – Nov 4, 2026. Solo. Submission deadline Nov 4, 9:00 PM ET = **7:00 PM Arizona**
(re-check the official rules at kickoff). Target submitting by early afternoon.

## Before kickoff (Oct 25)
- [ ] Count real hours per day Oct 26 – Nov 4 (classes, work). Write them here:
  | Mon 26 | Tue 27 | Wed 28 | Thu 29 | Fri 30 | Sat 31 | Sun 1 | Mon 2 | Tue 3 | Wed 4 |
  |---|---|---|---|---|---|---|---|---|---|
  |   |   |   |   |   |   |   |   |   |   |
  If weekdays are ~4h, pull the Spark/Wonder benchmark and scope lock earlier.
- [ ] Meta Model API account + payment method + spending cap; note Team ID for the credit form.
- [ ] Check employer policy on accepting the $150 credits (optional to claim).
- [ ] Play bitrun once; confirm keys (shield hold vs tap) and pick a forgiving section.
- [ ] Camera mount working at ~35–50°.

## Calendar

| Date | Outcome | Gate |
|---|---|---|
| Oct 26 | Page calibration + rectified snapshot; first Muse compile; **acoustic tap experiment**; bitrun keymap verified | — |
| Oct 27 | Spark vs Wonder: parse quality + latency on 10 drawings; pick one. Fingertip → page coords | compile latency measured |
| Oct 28 | **Scope lock.** Freeze primitives and action vocab (NOT notation). Pick movement method (toggle vs slider) | — |
| Oct 29 | **Kill test**: press vs hover | 27/30 presses, ≤3/30 false hovers → else fallback, no pivot |
| Oct 30 | Engine + adapter end-to-end on bitrun; overlay with rationale text | — |
| Oct 31 | Compound instructions working live in bitrun; compile gate trials | 8/10 compound compiles, ≥5 drawn by others |
| Nov 1 | Live edit: stable-edit detection, diff recompile, **cross-out = delete** | edit without restart |
| Nov 2 | Blind-layout reliability runs; fix weak spots only. **Write README + submission text tonight** | — |
| Nov 3 | Record demo (one continuous take for the key beat); final reliability numbers | — |
| Nov 4 | Final regression, upload, submit early | deadline 7 PM AZ |

## Acceptance gates (log to eval/)
1. **Physical interaction**: 27/30 presses, ≤3/30 false hover activations, with the chosen method.
2. **Semantic compilation**: ≥8/10 unseen compound instructions compile to correct behavior.
   At least half drawn by people told only *what* it should do, not *how* to draw it.
   A clarifying question followed by a correct compile counts as a pass.
3. **Live modification**: add / cross out a control mid-session; target app keeps running,
   unaffected controls (e.g. an active RUN toggle) keep working.
4. **Latency**: edit-to-ready time measured and shown on screen. Don't promise a number
   until it's measured.

## Rules
- Freeze primitives, not notation.
- Model never per-frame; never emits code; diffs only on recompile.
- No browser automation, no generated code execution, no extra app integrations.
- Fallback, never pivot.
