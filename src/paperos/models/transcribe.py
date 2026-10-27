"""Speech -> timestamped words.

Seed needs WORD-level timestamps: a point lines up with the words spoken at that instant,
not the whole sentence (see the Oct 27 "the problem I just gave you" case).

UNVERIFIED: whether Muse Voice Transcribe returns word timestamps, and its request shape.
Check in the playground's Audio tab first. Until then, `load_words` reads a JSON file
([{"text","start","end"}, ...]) so the rest of the pipeline can be built and tested.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from paperos.spec import Word


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> list[Word]: ...


def load_words(path: Path) -> list[Word]:
    return [Word.model_validate(w) for w in json.loads(Path(path).read_text())]


def save_words(words: list[Word], path: Path) -> None:
    Path(path).write_text(json.dumps([w.model_dump() for w in words], indent=1))


class MuseTranscriber:
    """OpenAI-style audio transcription with word granularity. Verify before use."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def transcribe(self, audio_path: Path) -> list[Word]:
        with open(audio_path, "rb") as f:
            resp = self.client.audio.transcriptions.create(
                model=self.model, file=f, response_format="verbose_json",
                timestamp_granularities=["word"],
            )
        words = getattr(resp, "words", None)
        if not words:
            raise RuntimeError(
                "transcription returned no word timestamps; check the Audio tab / API docs")
        return [Word(text=w.word, start=w.start, end=w.end) for w in words]
