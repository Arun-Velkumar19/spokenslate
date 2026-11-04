# Submission text (copy into the form)

Every number here traces to a file in `eval/results/`.

---

## Name

SpokenSlate

## Tagline (one line)

Transcripts tell you what the professor said. SpokenSlate tells you what they meant.

## Inspiration

A whiteboard lecture is two streams: what's said and what's written. Captions keep only the
first. For a blind or low-vision student, a recorded lecture is full of dead ends: *"this term
cancels with that one"*, *"subtract twice this from the second row"*. Accessibility guides
ask instructors to "say what you write and avoid *this* and *here*". In practice nobody does,
and the student is left with a transcript that points at nothing.

## What it does

SpokenSlate takes a recorded lecture and produces an accessible web page:

- **Every board step, in order, at the moment it was written.** Each step leads with a plain
  reading ("matrix: row one: boxed one, boxed two; row two: three, four"), then MathML a
  screen reader can explore cell by cell, then the LaTeX.
- **Spoken references linked to what they mean.** "Subtracting twice *this*" becomes a link to
  the exact board step, with what it means read aloud.
- **It says when it isn't sure.** Ambiguous references are marked *unresolved*. A confident
  wrong answer would mislead a student who can't check the board, so every check fails toward
  "unresolved".
- **Erased steps are kept** and labelled, so nothing that was on the board is lost.

Live: https://arun-velkumar19.github.io/spokenslate/

## How we built it (Meta models)

- **Muse Spark (`muse-spark-1.3`)** does the two hard jobs. It reads each board keyframe into
  structured steps (LaTeX, plain reading, region, erased or not), and it resolves each spoken
  reference: given three frames around the phrase, the words being said in each, the board
  elements alive at that moment and where the lecturer's fingertip is, it picks an element
  with a quote and a confidence.
- **SAM 3.1 (`sam-3.1`)** masks the lecturer on every candidate keyframe, decoded with Meta's
  `meta-sam-parser`. Board reads see the board instead of a person, and when only the
  lecturer moved (masked board unchanged), the Muse read is skipped.
- **Muse Wonder (`muse-wonder-1.0`)** is an optional second opinion when Spark abstains, still
  behind the same validator.
- Supporting pieces: local faster-whisper for word timestamps (pointing has to line up with
  the word being said, and Muse Voice Transcribe is realtime-only), MediaPipe for fingertip
  tracking, `latex2mathml` behind an allowlist for safe MathML.

The model never sets times or ids and never emits code. It returns JSON that a validator
checks: unknown element, element not on the board yet, quote not in the element, or
confidence below 0.7 → "unresolved". Calls run at temperature 0 so results repeat.

## Results

Every spoken reference was labelled by hand, before scoring except on the erase clip.
"Confident-wrong" = wrong link at confidence ≥ 0.7. A plain transcript links none of these references.

| Clip | References | Correct | Confident-wrong | Unresolved |
|---|---|---|---|---|
| Own whiteboard recording (fixed camera) | 16 | 11 | 0 | 5 |
| Own recording with an erase (portrait phone video) | 5 | 3 | 0 | 2 |
| MIT OCW 18.06 excerpt (camera-operated, 480p chalk) | 14 | 7 | 2* | 5 |

\*Both are "the pivots are there" linked to the matrix holding the pivots, counted wrong under
a strict label written before matrices became one element. On the whiteboard clip, all 5
unresolved happened while the lecturer's shoulder hid the board. On the erase clip the wiped
line is kept, but the board reader misread its text (small handwriting in a portrait video).

Small numbers (35 references), labels by the author, not yet tested with blind users:
evidence the method works, not a study.

## Challenges

- **Word timing.** A point lines up with the word being said at that instant, not the whole
  sentence. "The problem I just gave you" and "this problem" sat in one caption line and meant
  opposite things, so captions-per-frame weren't enough; we moved to word timestamps.
- **The lecturer is always in the way.** Hidden is not erased. The board prompt and timeline
  only erase on an explicit erase, and SAM masking keeps the person out of the read.
- **Phone auto-exposure.** Our first SAM gate skipped nothing on an iPhone clip because the
  whole frame's brightness swung; gain normalization fixed it.
- **Screen readers drop things.** VoiceOver reads MathML matrices as tables but silently drops
  `\boxed` (the pivots), so every step leads with a plain reading that is never hidden.
- **Camera-operated lectures.** Cuts and zooms re-read the same writing as new. We test and
  demo on fixed cameras, which is what lecture-capture rooms use, and say so.

## Accomplishments

- 0 confident-wrong links on our own fixed-camera recording, with most correct links citing
  the fingertip ("pointing candidate, distance 0.00").
- A validator that makes "I'm not sure" the default, not an afterthought.
- Output that was checked with VoiceOver, not just with a validator.

## What we learned

Reading the board is the easy part. Knowing what "this" means needs the words, the frames
and the hand together, at the same instant, and an honest way to say "I don't know".

## What's next

- Test with blind and low-vision students through a university disability resource office.
- Camera-motion handling for camera-operated recordings.
- Tablet-ink-over-slides lectures, common in online courses (same said-vs-written problem,
  untested so far).

## Built with

Muse Spark, SAM 3.1, Muse Wonder, meta-sam-parser, Python, faster-whisper, MediaPipe,
OpenCV, latex2mathml, MathML, GitHub Pages
