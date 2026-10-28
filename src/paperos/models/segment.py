"""Lecturer masking with SAM 3.1, so the board is read without the person in the way.

UNVERIFIED: SAM 3.1 request/response shape on the Meta Model API. Reports say it returns
segmentation as special-token text (box + RLE mask per object), parsed by Meta's
`meta-sam-parser` package. Verify in the playground's Segment tab (prompt "person"),
then implement MetaSAM.person_mask. Adding meta-sam-parser is a new dependency: ask first.

Until then NullSegmenter keeps the pipeline working: the board reader is told the
lecturer may block parts of the board, and hidden != erased (see prompts.BOARD_RULES).
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class Segmenter(Protocol):
    def person_mask(self, frame: np.ndarray) -> np.ndarray | None:
        """uint8 mask, 255 where the lecturer is, same HxW as frame; None if unknown."""
        ...


class NullSegmenter:
    def person_mask(self, frame: np.ndarray) -> np.ndarray | None:
        return None


class MetaSAM:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key, self.base_url, self.model = api_key, base_url, model

    def person_mask(self, frame: np.ndarray) -> np.ndarray | None:
        raise NotImplementedError("verify SAM 3.1 API shape in the Segment tab first")


def apply_mask(frame: np.ndarray, mask: np.ndarray | None, fill: int = 128) -> np.ndarray:
    """Grey out the lecturer so the board reader isn't distracted by them."""
    if mask is None:
        return frame
    out = frame.copy()
    out[mask > 0] = fill
    return out
