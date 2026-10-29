"""Lecture video/audio -> words.json with word-level timestamps (faster-whisper, local).

    python scripts/transcribe.py data/clip.mp4 --out data/clip.words.json
    python scripts/transcribe.py data/clip.mp4 --out data/clip.words.json --model medium.en

Writes [{"text","start","end"}, ...] for `python -m spokenslate process --words`. The first
run downloads the model (small.en is ~0.5 GB) into the Hugging Face cache.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from spokenslate.config import load_settings
from spokenslate.models.transcribe import Transcriber, WhisperTranscriber, save_words


def run(media: Path, out: Path, transcriber: Transcriber) -> int:
    words = transcriber.transcribe(media)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_words(words, out)
    print(f"{len(words)} words, {words[0].start:.2f}s-{words[-1].end:.2f}s -> {out}")
    print("first:", " ".join(f"{w.text}@{w.start:.2f}" for w in words[:8]))
    return len(words)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("media", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default=load_settings().whisper_model,
                    help="faster-whisper model (tiny.en, base.en, small.en, medium.en)")
    args = ap.parse_args(argv)
    run(args.media, args.out, WhisperTranscriber(args.model))


if __name__ == "__main__":
    main()
