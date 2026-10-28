# Prior art

SpokenSlate does not claim to invent lecture capture, AI note-taking, or multimodal grounding.

| Work | What it does | Difference |
|---|---|---|
| [HoverNotes](https://hovernotes.io/) | captures equations, code and visuals from lecture videos | notes for sighted review; no resolution of spoken references; not built for screen readers |
| [LensNote](https://lensnote.app/) | slides + timestamps + transcripts | slide-based; no board-step timeline or reference resolution |
| [AirSketch](https://devpost.com/software/airsketch) | syncs drawings, audio and notes | drawing capture; not reference grounding |
| [Lecturer removal from whiteboard video (2024)](https://www.sciencedirect.com/science/article/pii/S096599782400139X) | removes the lecturer to show the board | one ingredient (SAM masking) of SpokenSlate |
| [VeasyGuide](https://veasyguide.github.io/app/) | detects and highlights writing/pointing moments in lecture video | highlighting for viewers; no grounded transcript |
| [CrossA11y](https://research.adobe.com/publication/crossa11y-identifying-video-accessibility-issues-via-cross-modal-grounding/) | finds missing accessibility information across audio/video | identifies gaps; SpokenSlate fills one specific gap |
| EgoPoint-Ground (ECCV 2026), Speech-to-Spatial (IEEE VR 2026) | research on grounding pointing + speech to objects | the underlying capability is active research; SpokenSlate applies it to an accessibility workflow with abstention |
| University instructor guidance | "say what you write; avoid 'this' and 'here'" | the problem is recognized; SpokenSlate does it automatically for recordings |

**SpokenSlate's claim:** the combination of (1) a timeline of board steps including erased ones,
(2) spoken references resolved to specific board elements using speech timing, pointing,
and earlier/later frames, (3) explicit abstention, and (4) output designed for screen readers.

TODO before submission: verify each link and claim; add the instructor-guidance sources.
