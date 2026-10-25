# Prior art

PaperOS does not claim to invent paper interfaces. The field is over a decade old.

| Work | What it does | Difference from PaperOS |
|---|---|---|
| SketchSynth (2012) | Camera-tracked hand-drawn buttons, sliders, dials control software | Fixed widget types; no model interpreting behavior; no live reprogramming of behavior |
| PaperBand | Finger-operated, camera-tracked paper instruments | Instruments, fixed mappings |
| Paper DJ (2026) | Real-time paper sliders/dials for audio mixing | Fixed control semantics |
| [Paper Launchpad](https://devpost.com/software/paper-launchpad) | Drawn boxes become music buttons (contour detection) | Shapes → fixed sounds; no compound behavior |
| Paper Machine | Model compiles a photographed hand-drawn state diagram into a browser program | Photo → program; paper is not the live controller; continuous re-scan listed as future work |
| Post-it! (2026) | Photographed handwritten workflows → executable automations | Not a live physical controller |
| aiClicker (Sep 2026) | AI generates a custom controller from an app screenshot, on a phone | Controller on a phone screen, not editable paper |
| Dynamicland | Room-scale paper computing | Requires a purpose-built space |

**PaperOS's claim:** the combination of (1) the drawing stays the live physical control
surface, (2) behavior can be changed with a pen mid-session without restarting the target,
and (3) a multimodal model interprets improvised handwritten notation into validated
behavior without per-control configuration.

TODO before submission: verify each entry and add links.
