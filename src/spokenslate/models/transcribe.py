"""Speech -> timestamped words.

SpokenSlate needs WORD-level timestamps: a point lines up with the words spoken at that instant,
not the whole sentence (see the Oct 27 "the problem I just gave you" case).

Muse Voice Transcribe can't supply them (checked Oct 29): it is realtime WebSocket only
(`wss://api.meta.ai/v1/asr/realtime`), `/v1/audio/transcriptions` returns 404, and the
playground gives turn-level times (~20 s turns, whole seconds). So words come from
faster-whisper, run locally with word timestamps. It reads video files directly (PyAV).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from spokenslate.spec import Word

DEFAULT_WHISPER_MODEL = "small.en"


class Transcriber(Protocol):
    def transcribe(self, media_path: Path) -> list[Word]: ...


def load_words(path: Path) -> list[Word]:
    return [Word.model_validate(w) for w in json.loads(Path(path).read_text())]


def save_words(words: list[Word], path: Path) -> None:
    Path(path).write_text(json.dumps([w.model_dump() for w in words], indent=1))


def words_from_segments(segments: Iterable[Any]) -> list[Word]:
    """faster-whisper segments (each with .words: word/start/end) -> clean, ordered Words.

    Whisper words carry a leading space and occasionally a zero-length or slightly
    overlapping span; strip text, drop empties, and keep times non-decreasing so the
    Word contract (end >= start) and phrase windows stay valid.
    """
    out: list[Word] = []
    last_end = 0.0
    for seg in segments:
        for w in getattr(seg, "words", None) or []:
            text = (w.word or "").strip()
            if not text:
                continue
            start = max(float(w.start), last_end)
            end = max(float(w.end), start)
            out.append(Word(text=text, start=round(start, 3), end=round(end, 3)))
            last_end = end
    return out


class WhisperTranscriber:
    """Local faster-whisper with word timestamps. CPU int8 is fine for lecture clips."""

    def __init__(self, model: str = DEFAULT_WHISPER_MODEL, device: str = "cpu",
                 compute_type: str = "int8") -> None:
        from faster_whisper import WhisperModel  # heavy import; only when transcribing

        self.model_name = model
        self.model = WhisperModel(model, device=device, compute_type=compute_type)

    def transcribe(self, media_path: Path) -> list[Word]:
        segments, _info = self.model.transcribe(
            str(media_path), language="en", word_timestamps=True, vad_filter=True,
            condition_on_previous_text=False,  # limits runaway repetition on long clips
        )
        words = words_from_segments(segments)
        if not words:
            raise RuntimeError(f"no speech found in {media_path}")
        return words
