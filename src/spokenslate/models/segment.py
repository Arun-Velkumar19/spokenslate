"""Lecturer masking with SAM 3.1, so the board is read without the person in the way.

Verified Oct 30 (playground + one API call): SAM 3.1 is called through the Responses API.
Upload the frame (`POST /v1/files`, purpose `user_data`), then `POST /v1/responses` with
model `sam-3.1`, an `input_text` noun phrase ("person") and the `input_image` file id,
`metadata={"mask_encoding": "lossless", "include_confidence": "true"}`. The answer is
special-token text, one box then one mask per object:

    <|box;x1=178;y1=100;x2=365;y2=351;w=480;h=352;c=0.9766|>
    <|mask;x=0;y=0;c=0.9766;data=252,188,~<base85 payload>|>

`w`/`h` are the uploaded image's size; the mask is H x W pixels placed at the box's
top-left plus (x, y). The payload is decoded with Meta's `meta-sam-parser` (lossless
masks use an arithmetic coder; there is no sensible way to decode them by hand).

Every failure returns None: the pipeline then reads the unmasked frame, exactly as with
NullSegmenter. A missing mask must never stop a lecture from being processed.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

import cv2
import numpy as np

log = logging.getLogger(__name__)

PROMPT = "person"
MIN_CONFIDENCE = 0.5
_TOKEN = re.compile(r"<\|(box|mask);([^|]*)\|>")


class Segmenter(Protocol):
    def person_mask(self, frame: np.ndarray) -> np.ndarray | None:
        """uint8 mask, 255 where the lecturer is, same HxW as frame; None if unknown."""
        ...


class NullSegmenter:
    def person_mask(self, frame: np.ndarray) -> np.ndarray | None:
        return None


def _fields(body: str) -> dict[str, str]:
    out = {}
    for part in body.split(";"):
        k, sep, v = part.partition("=")
        if sep:
            out[k.strip()] = v
    return out


def parse_sam_text(text: str, frame_h: int, frame_w: int,
                   min_confidence: float = MIN_CONFIDENCE) -> np.ndarray | None:
    """Union of all confident object masks in SAM's text output, as a frame-sized uint8
    mask (255 = object). None if there is no usable mask or anything fails to parse."""
    from meta_sam_parser import SegmentationMask, decode_mask_to_raster

    full: np.ndarray | None = None
    box: dict[str, str] | None = None
    try:
        for kind, body in _TOKEN.findall(text):
            f = _fields(body)
            if kind == "box":
                box = f
                continue
            if box is None:
                return None  # a mask always follows its box
            conf = float(f.get("c", box.get("c", "1")))
            h_str, w_str, payload = f["data"].split(",", 2)
            mh, mw = int(h_str), int(w_str)
            enc = {"~": "lossless", "!": "one_bit"}[payload[:1]]
            raster = decode_mask_to_raster(SegmentationMask(
                encoding=enc, payload=payload, width=mw, height=mh))
            iw, ih = int(box["w"]), int(box["h"])  # the uploaded image's size
            if full is None:
                full = np.zeros((ih, iw), np.uint8)
            if conf < min_confidence:
                box = None
                continue
            ox = int(float(box["x1"])) + int(f.get("x", "0"))
            oy = int(float(box["y1"])) + int(f.get("y", "0"))
            m = np.frombuffer(raster, np.uint8).reshape(mh, mw)
            hh, ww = max(0, min(mh, ih - oy)), max(0, min(mw, iw - ox))
            full[oy:oy + hh, ox:ox + ww] |= m[:hh, :ww] * 255
            box = None
    except Exception as e:  # noqa: BLE001  malformed output -> no mask, never a crash
        log.warning("could not parse SAM output: %s", e)
        return None
    if full is None or not full.any():
        return None
    if full.shape != (frame_h, frame_w):
        full = cv2.resize(full, (frame_w, frame_h), interpolation=cv2.INTER_NEAREST)
    return full


class MetaSAM:
    """SAM 3.1 on the Meta Model API: 2 calls per frame (upload + segment), 1 attempt."""

    def __init__(self, api_key: str, base_url: str, model: str = "sam-3.1",
                 client=None) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=base_url)
        self.client, self.model = client, model
        self.calls = 0

    def person_mask(self, frame: np.ndarray) -> np.ndarray | None:
        from spokenslate.video import to_jpeg

        file_id = None
        try:
            up = self.client.files.create(file=("frame.jpg", to_jpeg(frame), "image/jpeg"),
                                          purpose="user_data")
            file_id = up.id
            self.calls += 1
            resp = self.client.responses.create(
                model=self.model, stream=False,
                input=[{"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": PROMPT},
                    {"type": "input_image", "file_id": file_id}]}],
                metadata={"mask_encoding": "lossless", "include_confidence": "true"},
            )
            self.calls += 1
            text = "".join(c.text for o in resp.output for c in (getattr(o, "content", None)
                                                                  or []) if hasattr(c, "text"))
        except Exception as e:  # noqa: BLE001  API trouble -> unmasked frame, never a crash
            log.warning("SAM call failed: %s", e)
            return None
        finally:
            if file_id is not None:
                try:
                    self.client.files.delete(file_id)  # don't leave lecture frames stored
                except Exception as e:  # noqa: BLE001  cleanup only; the mask is still good
                    log.warning("could not delete uploaded frame %s: %s", file_id, e)
        return parse_sam_text(text, frame.shape[0], frame.shape[1])


def apply_mask(frame: np.ndarray, mask: np.ndarray | None, fill: int = 128) -> np.ndarray:
    """Grey out the lecturer so the board reader isn't distracted by them."""
    if mask is None:
        return frame
    out = frame.copy()
    out[mask > 0] = fill
    return out
