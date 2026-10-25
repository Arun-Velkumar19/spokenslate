"""Muse client: rectified page image → ControlSpec / SpecDiff.

Assumes the Meta Model API's OpenAI-compatible endpoint. Verify at kickoff:
base URL, model IDs, image input format, and whether structured-output /
response_format is supported (use it if so; the JSON-parse path below is the fallback).
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from paperos.compiler.prompts import compile_prompt, recompile_prompt
from paperos.config import Settings
from paperos.spec import ControlSpec, SpecDiff

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass
class CompileResult:
    value: BaseModel
    latency_s: float
    model: str
    raw: str
    attempts: int


class CompileError(RuntimeError):
    pass


def _data_url(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()


def parse_json_as(model: type[T], text: str) -> T:
    """Strip code fences, parse, validate. Raises ValueError with a readable reason."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return model.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(str(e)) from e


class MuseCompiler:
    def __init__(self, settings: Settings, model: str | None = None) -> None:
        from openai import OpenAI

        if not settings.api_key or not settings.base_url:
            raise CompileError("META_API_KEY / META_API_BASE_URL not set (see .env.example)")
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        self.model = model or settings.compile_model

    def _call(self, system: str, page_jpeg: bytes, target: type[T], max_attempts: int = 2):
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _data_url(page_jpeg)}},
                    {"type": "text", "text": "Compile this page."},
                ],
            },
        ]
        t0 = time.perf_counter()
        last_err = ""
        for attempt in range(1, max_attempts + 1):
            resp = self.client.chat.completions.create(model=self.model, messages=messages)
            raw = resp.choices[0].message.content or ""
            try:
                value = parse_json_as(target, raw)
                return CompileResult(value, time.perf_counter() - t0, self.model, raw, attempt)
            except ValueError as e:
                last_err = str(e)
                messages += [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"Invalid output: {last_err}\nReturn valid JSON only."},
                ]
        raise CompileError(f"no valid {target.__name__} after {max_attempts} attempts: {last_err}")

    def compile(self, page_jpeg: bytes, action_vocab: str) -> CompileResult:
        return self._call(compile_prompt(action_vocab), page_jpeg, ControlSpec)

    def recompile(self, page_jpeg: bytes, action_vocab: str, current: ControlSpec) -> CompileResult:
        return self._call(recompile_prompt(action_vocab, current), page_jpeg, SpecDiff)
