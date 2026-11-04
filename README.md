# SpokenSlate

**Transcripts tell you what the professor said. SpokenSlate tells you what they meant.**

A whiteboard lecture is two streams: what's said and what's written. Captions keep only the
first, so for a blind or low-vision student a recorded lecture is full of dead ends:
*"this term cancels with that one"*, *"plug it into the equation from before"*. Universities
ask instructors to "say what you write and avoid *this* and *here*". In practice, nobody does.

SpokenSlate takes a recorded lecture and produces an accessible web page:

- **Every board step, in order, at the moment it was written**: a plain-language reading
  first ("matrix: row one: boxed one, two, one…"), then real math (MathML) a screen reader can
  explore cell by cell, then the LaTeX source.
- **Spoken references linked to what they mean**: *"subtracting twice **this**"* →
  *(means minus 2, in step 6)*, a link to that step.
- **It says when it isn't sure.** Ambiguous references are marked *unresolved*, with a
  "possibly step N" hint. A confident wrong answer is the worst outcome, so the system is
  built to abstain rather than guess.
- **Erased steps are kept** and labelled ("erased at 1:36, kept here").

**Try it:** [arun-velkumar19.github.io/spokenslate](https://arun-velkumar19.github.io/spokenslate/), with two processed lectures and a guide to reading them with a screen reader.

## How it works

```
video ─► candidate keyframes ─► SAM 3.1: mask the lecturer ─► board changed? ─► Muse Spark: read board
                                                                                   (diff → timeline)
audio ─► word timestamps ─► reference phrases ("this term", "the first", "the problem I just gave you")
fingertip track ─► pointing candidates ─┐
                                        ▼
            Muse Spark: which board element does this phrase mean? (3 frames + words + board)
                                        ▼
            validator: unknown element, element not on the board yet, quote not in it,
            or confidence < 0.7  →  "unresolved"           ─►  accessible HTML page
```

| Meta model / tool | Job in SpokenSlate |
|---|---|
| **Muse Spark** (`muse-spark-1.3`) | reads the board into structured steps (LaTeX + plain reading + region), and resolves each spoken reference to a board element with evidence and confidence |
| **SAM 3.1** (`sam-3.1`) + Meta's **`meta-sam-parser`** | masks the lecturer ("person") on each candidate keyframe. Board reads see the board, not the person, and a read is skipped when only the lecturer moved |
| **Muse Wonder** (`muse-wonder-1.0`) | optional second opinion (`--escalate`) when Spark abstains, still behind the validator |
| MediaPipe hand landmarker | fingertip track → ranked "pointing candidates" given to the resolver |
| faster-whisper (local) | word-level timestamps. Muse Voice Transcribe is realtime-only and returns ~20 s turns, while pointing needs per-word timing |

**The model never sets times, ids or code.** It returns JSON (`BoardDiff`, `ResolveOutput`) that is
validated. The pipeline assigns ids, keeps erased elements, and runs every model call at
temperature 0 so results are repeatable.

## Results

Every spoken reference was labelled by hand, before scoring except on the erase clip.
"Confident-wrong" means a wrong link at confidence ≥ 0.7, the failure that misleads a student. A plain transcript links none of
these references.

| Clip | References | Correct links | Confident-wrong | Unresolved |
|---|---|---|---|---|
| Whiteboard, own recording (fixed camera, temperature 0) | 16 | **11** | **0** | 5 |
| Own recording with an erase (portrait phone video; labels written after the run) | 5 | 3 | **0** | 2 |
| MIT OCW 18.06 excerpt (camera-operated, chalk, 480p; single run at default temperature) | 14 | 7 | 2* | 5 (1 a correct abstention) |
| *Plain transcript (any clip)* | *35* | *0* | *0* | *35* |

\*Both are "the pivots are there" linked to the matrix that holds the boxed pivots. We count
them as wrong because the label, set before matrices became single elements, said "no single
element". On the whiteboard clip, all 5 unresolved references happened while the lecturer's
shoulder hid the board and he wasn't pointing. The system's own evidence says so.

Fingertip tracking matters: most correct links on the whiteboard clip cite *"pointing
candidate, distance 0.00"*. Per-run CSVs and notes: [`eval/`](eval/README.md).

Honest scope: three short clips, labels written by the author, and **not yet tested with
blind users**. Treat these numbers as evidence the method works, not a study.

## Accessibility decisions (from VoiceOver testing)

- VoiceOver reads MathML matrices as a navigable table but **drops `\boxed`** (the pivots). So
  every step leads with the plain-language reading, which is never `aria-hidden`.
- Reference notes speak quotes in words ("0, boxed 2, minus 2"), not raw LaTeX, and name the
  step instead of repeating a whole matrix.
- One heading per board step, so a student can skim the derivation with heading navigation.

## Limitations

- **Fixed camera.** Camera-operated recordings (pans, zooms, cuts) re-read the same writing
  as new and can fake erasures. Tested on MIT OCW 18.06, where it still worked but with
  duplicates.
- Board reading depends on legible writing and resolution. Chalk at 480p is hard. On the
  erase clip (phone held upright, board half the frame), the erased line was misread as a
  copy of the line above it: the step is kept, but its text is wrong.
- A matrix written one row at a time can come out as separate rows.
- English only; offline (recorded lectures in, static pages out).

## Use

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env            # add META_API_KEY
pytest -q

python -m spokenslate process lecture.mp4 --out site/ \
  --title "Calculus 2, 6.1" --source "credit line"
```
Without `--words`, speech is transcribed locally and saved to `site/lecture.words.json`.
SAM masking is on by default (`--no-sam` to skip); `--escalate` adds Muse Wonder.

Output: `site/lecture.html` (the accessible page) and `site/lecture.json` (everything,
including evidence for each resolved reference).

## Pointing (hand tracking)

Fingertip tracking (MediaPipe Tasks) gives the resolver ranked candidates for what the
lecturer is pointing at. Download `hand_landmarker.task` from the
[MediaPipe models page](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models)
into `models/` (gitignored). Extract a track from a recorded lecture, then pass it to
the processor:

```bash
python scripts/fingertips.py lecture.mp4 --out fingertips.json --fps 10
python -m spokenslate process lecture.mp4 --words words.json --fingertips fingertips.json \
  --out site/ --title "Calculus 2, 6.1" --source "credit line"
```

The exporter defaults to 10 samples/second and decodes frames sequentially. It writes
`[[t, u, v], ...]`: clip-relative seconds, `x / frame_width`, and `y / frame_height`.
Sampling uses the nearest source frame at each interval, retaining that frame's actual
time; rates above the source FPS use each frame once. Missing/invalid fingertips are
omitted. Lecture coordinates use the full frame with no page rectification.
Use `--hand-model PATH` for a model stored elsewhere.

The existing camera/page preview is also available:

```bash
python scripts/page_preview.py --hand
```

## Docs

- [`AGENTS.md`](AGENTS.md): handoff for coding agents (invariants, status, gotchas)
- [`docs/PLAN.md`](docs/PLAN.md): calendar and gates
- [`docs/DEMO.md`](docs/DEMO.md): video shot list
- [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md): what exists and what's different

## Credits

- MIT OCW 18.06 Linear Algebra, Lecture 2, Gilbert Strang (CC BY-NC-SA 4.0), used as a
  test lecture with credit; the excerpt page carries the license.
- `meta-sam-parser` by Meta Platforms (SAM License).

## Hackathon

Meta Global AI Developer Hackathon, Indie track, Oct 26 – Nov 4, 2026. Solo: Arun Velkumar.
