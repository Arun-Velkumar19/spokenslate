# SpokenSlate build plan

Pivoted from PaperOS on Oct 27 after the playground test passed (10/10 references, 0
confident wrong). Deadline **Nov 4, 7:00 PM Arizona**. Target: submitted by early afternoon.
Part-time solo: count real hours per day and pull work earlier if weekdays are thin.

## Judging (weights) and how SpokenSlate scores
- **Impact 30%**: blind/low-vision students lose everything on the board. Evidence: SAILS
  conversation (emailed Oct 27), published "describe what you write" instructor guidance,
  benchmark numbers. Be honest: not yet tested with blind users.
- **Meta tooling 25%**: SAM 3.1 + Muse Spark (+ Wonder escalation), each essential. Speech
  timing is local faster-whisper (Muse Voice has no word times; stretch: Muse WebSocket
  transcript + Meta MMS forced alignment). Unexpected capability: resolving a reference to something hidden under the hand.
- **Technical 20%**: validated JSON contracts, timeline with erased content, hallucination
  guard, benchmark with abstention.
- **Demo 25%**: hosted pages judges can open with a screen reader; VoiceOver in the video.

## Open verifications (do first, Oct 27)
- [ ] Playground **Get code**: chat request shape with images, JSON mode → match `models/muse.py`
- [x] **Audio** (Oct 29): Muse Voice Transcribe has no word timestamps (realtime WebSocket only,
      ~20 s turns). Decision: local faster-whisper for words (`scripts/transcribe.py`).
- [ ] **Segment**: SAM 3.1 "person" mask on a lecture frame; note request/response shape
- [ ] **Abstention test**: 2–3 genuinely ambiguous moments; model must say unresolved
- [ ] **Second lecturer** (MIT OCW 18.06 Strang, chalkboard): repeat 5 references

## Calendar

| Date | Outcome | Gate |
|---|---|---|
| Tue Oct 27 | Verifications above. Record your own 2–3 min whiteboard clip (rights-clean, controllable) | API shapes known |
| Wed Oct 28 | First live end-to-end run on one clip (`process` → page). **Scope lock.** | page renders from real model output |
| Thu Oct 29 | **Reference benchmark**: ≥15 references, 2 lecturers | ≥80% correct, **0 confident-wrong**, abstains on ambiguous |
| Fri Oct 30 | Fingertip track from lecture video (`sensing/hand.py`, merged) → board coords → pointing candidates in real runs | candidates help on ≥1 case |
| Sat Oct 31 | Math rendering per SAILS answer (MathML/KaTeX); VoiceOver pass on the page | navigable by headings with VoiceOver |
| Sun Nov 1 | Baseline-vs-SpokenSlate table; host 2–3 lectures on GitHub Pages | public link works |
| Mon Nov 2 | Fix weak spots only. **Write README + submission text tonight** | — |
| Tue Nov 3 | Record demo video (VoiceOver beat in one take) | — |
| Wed Nov 4 | Final check, upload, submit early | 7 PM AZ |

If the Oct 29 gate fails: ship with "possibly" suggestions and candidates highlighted
rather than auto-resolution. Fallback, never pivot.

## Validation track (parallel, not blocking)
- [x] Offline fingertip exporter → frame-normalized `--fingertips` JSON; sequential video
      decoding and pointing handoff tested with a fake detector + synthetic mp4.
- [ ] Validate MediaPipe tracking on a real lecture; candidates help on ≥1 case.
- [x] `scripts/smoke_api.py`: one logged `read_board` call (format verified Oct 28, valid
      `BoardDiff` in 9.2s); `scripts/score.py` + `scoring.py`: benchmark scorer with baseline row.
- [ ] Fill `eval/references.csv` (≥15 refs, 2 lecturers) and score a real `process` output.
- SAILS email sent Oct 27. Nudge Thu Oct 29; walk in (Wilson Hall) if silent.
- Backup: Dr. Troy McDaniel (CUbiC), Arizona Association of Blind Students, AppleVis forum
  (once there's a page to show). Lock whatever evidence exists by Sat Oct 31.

## Cut list (do not build)
Live classroom mode · slides · dictation / two-way math input (future work line only) ·
translation · hosted upload backend (stretch after Nov 1 only) · multi-camera.
