"""Muse client (Meta Model API, OpenAI-compatible chat completions with image input).

UNVERIFIED against the live API: base URL, image content format, and JSON mode. Click
"Get code" in the playground and make this match before relying on it. Paid calls are
bounded: at most `max_attempts` per request, no unbounded retry loops.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from paperos.models.prompts import board_prompt, resolve_prompt
from paperos.spec import BoardDiff, ReferencePhrase, ResolveOutput, TimedElement

T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class MuseError(RuntimeError):
    pass


def parse_json_as(model: type[T], text: str) -> T:
    cleaned = _FENCE.sub("", text.strip())
    try:
        return model.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(str(e)) from e


def _image(jpeg: bytes) -> dict:
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    return {"type": "image_url", "image_url": {"url": url}}


@dataclass
class FrameShot:
    t: float
    jpeg: bytes
    words: str  # words spoken around this frame


@dataclass
class ResolveRequest:
    phrase: ReferencePhrase
    sentence: str
    frames: list[FrameShot]
    elements: list[TimedElement]
    candidates: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class CallLog:
    model: str
    kind: str
    latency_s: float
    attempts: int


class MuseClient:
    def __init__(self, api_key: str, base_url: str, model: str, max_attempts: int = 2) -> None:
        from openai import OpenAI

        if not api_key:
            raise MuseError("META_API_KEY not set (see .env.example)")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_attempts = max_attempts
        self.log: list[CallLog] = []

    def _call(self, kind: str, prompt: str, images: list[bytes], target: type[T]) -> T:
        messages: list[dict] = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": [*map(_image, images), {"type": "text", "text": "Answer."}]},
        ]
        t0, err = time.perf_counter(), ""
        for attempt in range(1, self.max_attempts + 1):
            resp = self.client.chat.completions.create(model=self.model, messages=messages)
            raw = resp.choices[0].message.content or ""
            try:
                out = parse_json_as(target, raw)
                self.log.append(CallLog(self.model, kind, time.perf_counter() - t0, attempt))
                return out
            except ValueError as e:
                err = str(e)
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content": f"Invalid: {err}\nReturn valid JSON only."}]
        raise MuseError(f"{kind}: no valid {target.__name__} after {self.max_attempts} attempts: {err}")

    # BoardReader
    def read_board(self, jpeg: bytes, current: list[TimedElement]) -> BoardDiff:
        return self._call("board", board_prompt(current), [jpeg], BoardDiff)

    # Resolver
    def resolve(self, req: ResolveRequest) -> ResolveOutput:
        prompt = resolve_prompt(req.phrase.text, req.sentence,
                                [(f.t, f.words) for f in req.frames], req.elements, req.candidates)
        return self._call("resolve", prompt, [f.jpeg for f in req.frames], ResolveOutput)
