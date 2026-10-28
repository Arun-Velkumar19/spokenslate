"""One real Meta Model API call: read_board on a single image (paid, bounded to 1 call).

    python scripts/smoke_api.py board.jpg
    python scripts/smoke_api.py board.png --model muse-spark-1.3 --log smoke.json

Sends exactly what the pipeline sends: models/muse.py's MuseClient.read_board, i.e.
chat.completions with the board prompt as the system message and the frame as a JPEG
image_url data URL (format verified Oct 28 against https://api.meta.ai/v1, muse-spark-1.3).
Prints the request structure (no key, image bytes elided), the raw response, latency,
and whether it parsed as a BoardDiff. Needs META_API_KEY in the environment or .env.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from paperos.config import load_settings
from paperos.models.muse import MuseClient, MuseError
from paperos.video import to_jpeg


def redact(kwargs: dict[str, Any]) -> dict[str, Any]:
    """The request as sent, with image data URLs replaced by their size."""
    out = copy.deepcopy(kwargs)
    for msg in out.get("messages", []):
        if not isinstance(msg.get("content"), list):
            continue
        for part in msg["content"]:
            if part.get("type") == "image_url":
                url = part["image_url"]["url"]
                head, _, data = url.partition(",")
                part["image_url"]["url"] = f"{head},<{len(data)} base64 chars elided>"
    return out


class _Recorder:
    """Stands in for the OpenAI client: records each create() call and its raw reply."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.requests: list[dict[str, Any]] = []
        self.raw: list[str] = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs: Any) -> Any:
        self.requests.append(redact(kwargs))
        resp = self._client.chat.completions.create(**kwargs)
        self.raw.append(resp.choices[0].message.content or "")
        return resp


@dataclass
class SmokeResult:
    request: dict[str, Any]
    raw: str
    latency_s: float
    parsed: bool
    error: str = ""
    diff: dict[str, Any] | None = None


def run(muse: MuseClient, jpeg: bytes) -> SmokeResult:
    muse.max_attempts = 1  # exactly one paid call, no repair retry
    rec = _Recorder(muse.client)
    muse.client = rec
    t0 = time.perf_counter()
    try:
        diff = muse.read_board(jpeg, [])
        parsed, error, dump = True, "", diff.model_dump()
    except MuseError as e:  # reply came back but was not a valid BoardDiff
        parsed, error, dump = False, str(e), None
    except Exception as e:  # noqa: BLE001 -- network/auth/HTTP error: still report the request
        parsed, error, dump = False, f"{type(e).__name__}: {e}", None
    latency = time.perf_counter() - t0
    return SmokeResult(rec.requests[0] if rec.requests else {}, rec.raw[0] if rec.raw else "",
                       latency, parsed, error, dump)


def main(argv: list[str] | None = None) -> None:
    s = load_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image", help="board image (any format OpenCV reads; sent as JPEG)")
    ap.add_argument("--model", default=s.board_model)
    ap.add_argument("--log", help="also write request/response/latency JSON here")
    args = ap.parse_args(argv)

    if not s.api_key:
        sys.exit("META_API_KEY is not set. Put it in .env (see .env.example) or the environment.")
    frame = cv2.imread(args.image)
    if frame is None:
        sys.exit(f"cannot read image {args.image}")

    muse = MuseClient(s.api_key, s.base_url, args.model)
    r = run(muse, to_jpeg(frame))
    record = {"base_url": s.base_url, "request": r.request, "raw_response": r.raw,
              "latency_s": round(r.latency_s, 3), "parsed_as_BoardDiff": r.parsed,
              "error": r.error, "board_diff": r.diff}
    print("== request (key omitted, image bytes elided)")
    print(json.dumps({"base_url": s.base_url, **r.request}, indent=1))
    print("== raw response")
    print(r.raw)
    print(f"== latency {r.latency_s:.2f}s | parsed as BoardDiff: {'yes' if r.parsed else 'NO'}")
    if r.error:
        print(f"   {r.error}")
    if args.log:
        Path(args.log).write_text(json.dumps(record, indent=1))
        print(f"wrote {args.log}")


if __name__ == "__main__":
    main()
