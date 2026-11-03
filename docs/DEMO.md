# Demo video (≤ 2 min, recorded Nov 3)

Pitch line: **"Transcripts tell you what the professor said. SpokenSlate tells you what they meant."**

Everything on screen is real output from `site/board.json` (Nov 1 whiteboard run) or the
OCW 18.06 run. No mocked screens, no narrated "what a screen reader would say".

## Shot list

| Time | Shot | Audio |
|---|---|---|
| 0:00–0:12 | **Black screen**, white text appears line by line: *"So this row is the pivot row."* → *"Which row?"* | Plain TTS / VoiceOver reading just the transcript line |
| 0:12–0:20 | Whiteboard clip, you pointing at the matrix (≈ 2:44 in `board.mov`, "this row") | Your real lecture audio |
| 0:20–0:55 | **One continuous screen take** of `product-rule.html` in Safari with VoiceOver: Ctrl-Opt-Cmd-H to *Step 5* → it reads *"matrix: row one: boxed one, boxed two; row two: three, four"* → Ctrl-Opt-→ into the speech → *"this row, link, (means boxed 1, boxed 2, in step 5)"* | Real VoiceOver audio |
| 0:55–1:15 | **How it works**, 3 quick cards: (1) SAM 3.1 mask overlay (`sam_box.png`, real SAM output on an OCW frame) "SAM 3.1 removes the lecturer"; (2) the board as steps "Muse Spark reads the board"; (3) evidence line *"pointing candidate e5, distance 0.00"* "…and decides what *this* means, using the words at that instant, the fingertip, and frames before and after" | Your voice-over |
| 1:15–1:30 | **Honesty beat**: the g(x) recital on the page: *"the first (unresolved) … the second (unresolved)"* + evidence *"no pointing and view occluded by shoulder"* | VO: "When it can't tell, it says so. A wrong answer is worse than none." |
| 1:30–1:45 | **Results card**: whiteboard 16 references → 11 linked, **0 wrong**; plain transcript → 0. OCW 18.06 excerpt: 7 of 14 on a real camera-operated chalk lecture. | VO reads the two numbers |
| 1:45–2:00 | Landing page with the link · Meta models used · credits (MIT OCW CC BY-NC-SA) | VO: "SpokenSlate. The board, for everyone in the room." |

If the mini clip (hand-cover + deliberately vague references) gets recorded and run, swap the
honesty beat for: hand over `x³` → *"this (means x cubed …)"*, then *"this one" (unresolved)*.

## Recording notes
- **System audio:** QuickTime can't record VoiceOver. Use OBS (macOS Screen Capture source
  with audio) or Cmd-Shift-5 on a macOS version that offers system audio; test 5 seconds first.
- Safari, zoom 125%, window ~1280×800, dark-mode off (higher contrast on video).
- VoiceOver speaking rate: slow it a notch (VoiceOver Utility → Speech) so judges can follow.
- Record each row as its own clip; assemble in iMovie / CapCut. Captions on (VoiceOver is fast).
- Every number on screen comes from `eval/results/` or the README results table.
