"""smoke_api.py with a fake OpenAI client: one call, request logged without key or bytes."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from paperos.models.muse import MuseClient

spec = importlib.util.spec_from_file_location(
    "smoke_api", Path(__file__).parents[1] / "scripts" / "smoke_api.py"
)
smoke = importlib.util.module_from_spec(spec)
sys.modules["smoke_api"] = smoke   # dataclasses look the module up by name
spec.loader.exec_module(smoke)

KEY = "sk-test-not-a-real-key"
DIFF = {"added": [{"id": "a", "kind": "math", "content": "x^2", "region":
                   {"x0": 0.1, "y0": 0.1, "x1": 0.3, "y1": 0.2}}]}


class FakeOpenAI:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def client(*replies):
    muse = MuseClient(KEY, "http://localhost:9/v1", "muse-spark-1.3")
    fake = FakeOpenAI(*replies)
    muse.client = fake
    return muse, fake


def test_valid_board_diff_is_parsed_and_request_redacted():
    muse, fake = client("```json\n" + json.dumps(DIFF) + "\n```")
    r = smoke.run(muse, b"\xff\xd8fake-jpeg")
    assert r.parsed and r.diff["added"][0]["content"] == "x^2"
    assert len(fake.calls) == 1
    assert r.raw.startswith("```json")
    assert r.latency_s >= 0
    req = json.dumps(r.request)
    assert KEY not in req and "base64,<" in req and "elided>" in req
    assert r.request["model"] == "muse-spark-1.3"
    system, user = r.request["messages"]
    assert system["role"] == "system" and system["content"]
    assert [p["type"] for p in user["content"]] == ["image_url", "text"]
    assert user["content"][0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    # the real request (sent to the API) still carried the full image
    assert "elided" not in fake.calls[0]["messages"][1]["content"][0]["image_url"]["url"]


def test_invalid_reply_is_one_call_not_a_retry():
    muse, fake = client("I see some math on the board.")
    r = smoke.run(muse, b"jpeg")
    assert not r.parsed and r.raw == "I see some math on the board."
    assert "BoardDiff" in r.error
    assert len(fake.calls) == 1


def test_api_error_still_reports_request():
    muse = MuseClient(KEY, "http://localhost:9/v1", "m")

    def boom(**kwargs):
        raise ConnectionError("refused")

    muse.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=boom)))
    r = smoke.run(muse, b"jpeg")
    assert not r.parsed and r.error == "ConnectionError: refused"
    assert r.request["model"] == "m"


def test_missing_key_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "")
    monkeypatch.chdir(tmp_path)   # no .env here
    with pytest.raises(SystemExit) as e:
        smoke.main(["board.jpg"])
    assert "META_API_KEY is not set" in str(e.value)


def test_main_prints_and_logs(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("META_API_KEY", KEY)
    monkeypatch.chdir(tmp_path)
    img = tmp_path / "board.png"
    cv2.imwrite(str(img), np.full((90, 160, 3), 255, np.uint8))
    fake = FakeOpenAI(json.dumps(DIFF))
    monkeypatch.setattr(smoke, "MuseClient", lambda *a: _with(MuseClient(*a), fake))
    smoke.main([str(img), "--log", str(tmp_path / "smoke.json")])
    out = capsys.readouterr().out
    assert "parsed as BoardDiff: yes" in out and KEY not in out
    log = json.loads((tmp_path / "smoke.json").read_text())
    assert log["parsed_as_BoardDiff"] and KEY not in json.dumps(log)
    sent = fake.calls[0]["messages"][1]["content"][0]["image_url"]["url"]
    assert sent.startswith("data:image/jpeg;base64,/9j/")   # PNG input is sent as JPEG


def _with(muse, fake):
    muse.client = fake
    return muse
