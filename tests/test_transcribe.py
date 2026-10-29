import importlib.util
import json
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from spokenslate.models.transcribe import load_words, words_from_segments
from spokenslate.references import find_reference_phrases
from spokenslate.spec import Word

_spec = importlib.util.spec_from_file_location(
    "transcribe_script", Path(__file__).resolve().parents[1] / "scripts" / "transcribe.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def seg(*words):
    return NS(words=[NS(word=w, start=a, end=b) for w, a, b in words])


def test_whisper_words_are_cleaned_and_ordered():
    segs = [
        seg((" So", 0.0, 0.2), (" cover", 0.2, 0.5), (" this", 0.5, 0.7)),
        seg(("  ", 0.7, 0.7), (" term", 0.65, 0.9), (" now.", 0.9, 0.88)),  # overlap, end<start
        NS(words=None),                                                    # VAD-only segment
    ]
    ws = words_from_segments(segs)
    assert [w.text for w in ws] == ["So", "cover", "this", "term", "now."]
    assert ws[3].start == 0.7                       # pulled forward past the previous end
    assert ws[4].end == ws[4].start == 0.9          # never end < start
    assert all(a.end <= b.start for a, b in pairwise(ws))


def test_word_times_reach_reference_phrases():
    ws = words_from_segments([seg((" cover", 59.0, 59.3), (" this", 59.3, 59.5),
                                  (" with", 59.5, 59.7), (" my", 59.7, 59.8))])
    (p,) = find_reference_phrases(ws)
    assert p.text == "this" and (p.start, p.end) == (59.3, 59.5)


class FakeTranscriber:
    def transcribe(self, media_path):
        assert media_path.name == "clip.mp4"
        return [Word(text="this", start=1.0, end=1.2), Word(text="term", start=1.2, end=1.5)]


def test_script_writes_words_json_that_process_reads(tmp_path, capsys):
    out = tmp_path / "w" / "clip.words.json"
    assert script.run(tmp_path / "clip.mp4", out, FakeTranscriber()) == 2
    assert json.loads(out.read_text())[1] == {"text": "term", "start": 1.2, "end": 1.5}
    assert [w.text for w in load_words(out)] == ["this", "term"]
    assert "this@1.00" in capsys.readouterr().out


def test_empty_transcript_is_an_error(monkeypatch):
    from spokenslate.models import transcribe as t

    class Model:
        def transcribe(self, *a, **k):
            return iter([]), None

    w = t.WhisperTranscriber.__new__(t.WhisperTranscriber)
    w.model = Model()
    with pytest.raises(RuntimeError, match="no speech"):
        w.transcribe(Path("silent.mp4"))


def test_audio_decoding_works_with_installed_pyav(tmp_path):
    """Regression: faster-whisper 1.2.1 + PyAV 19 fails in decode_audio (metadata_errors)."""
    import wave

    import numpy as np
    from faster_whisper.audio import decode_audio

    p = tmp_path / "silence.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(np.zeros(8000, np.int16).tobytes())
    assert decode_audio(str(p)).shape == (8000,)
