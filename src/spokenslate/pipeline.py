"""SpokenSlate pipeline: recorded lecture -> LectureDoc.

1. Board: sample frames, pick keyframes where the board changed, ask the board reader
   for a BoardDiff at each, apply to the Timeline (ids assigned here, never by the model).
2. Speech: timestamped words (from a transcriber or a words file).
3. References: find phrases ("this term", "the first", "the problem I just gave you").
4. Resolve: for each phrase, 3 frames around it + words per frame + board elements alive
   then + pointing candidates -> resolver -> validator. If the first model abstains or is
   unsure, escalate once to a stronger model (offline, so latency is fine).
Every model call goes through a Protocol, so tests run on fakes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from spokenslate.models.muse import FrameShot, ResolveRequest
from spokenslate.models.segment import NullSegmenter, Segmenter, apply_mask
from spokenslate.pointing import Sample, candidates, pointing_at
from spokenslate.references import find_reference_phrases
from spokenslate.spec import (
    BoardDiff,
    LectureDoc,
    ReferencePhrase,
    Resolution,
    ResolveOutput,
    TimedElement,
    Word,
)
from spokenslate.timeline import DiffError, Timeline
from spokenslate.validator import (
    CONFIDENCE_THRESHOLD,
    LOOKAHEAD_S,
    LOOKBACK_S,
    validate_resolution,
)
from spokenslate.video import (
    FrameSource,
    masked_board_diff,
    select_keyframes,
    thumbnail,
    to_jpeg,
)

log = logging.getLogger(__name__)


class BoardReader(Protocol):
    def read_board(self, jpeg: bytes, current: list[TimedElement]) -> BoardDiff: ...


class Resolver(Protocol):
    def resolve(self, req: ResolveRequest) -> ResolveOutput: ...


@dataclass
class Clients:
    board: BoardReader
    resolver: Resolver
    escalate: Resolver | None = None
    segmenter: Segmenter = field(default_factory=NullSegmenter)


@dataclass
class Stats:
    keyframes: int = 0
    board_calls: int = 0
    rejected_diffs: int = 0
    resolve_calls: int = 0
    escalations: int = 0
    skipped_reads: int = 0  # candidate keyframes where only the lecturer moved (SAM gate)


def assign_ids(diff: BoardDiff, next_n: int) -> tuple[BoardDiff, int]:
    """Replace model-proposed ids of added elements with permanent e<N> ids."""
    added = []
    for e in diff.added:
        added.append(e.model_copy(update={"id": f"e{next_n}"}))
        next_n += 1
    return diff.model_copy(update={"added": added}), next_n


def words_between(words: list[Word], t0: float, t1: float) -> str:
    return " ".join(w.text for w in words if w.end >= t0 and w.start <= t1)


def build_board(
    source: FrameSource, clients: Clients, stats: Stats,
    sample_every_s: float = 1.0, min_gap_s: float = 4.0, gate_thresh: float = 1.5,
) -> Timeline:
    # Pass 1: cheap thumbnails only (a 3-min 1080p clip at full res would be ~1 GB).
    # No segmentation here: SAM per sample would be ~1 paid call per second of video.
    times = [i * sample_every_s for i in range(int(source.duration / sample_every_s) + 1)]
    thumbs = [(t, thumbnail(source.frame_at(t))) for t in times]
    keys = select_keyframes(thumbs, min_gap_s=min_gap_s)
    # Pass 2: full-res frames at candidate keyframes only. Mask the lecturer; if the board
    # itself (lecturer removed) hasn't changed since the last read, skip the paid read.
    tl, next_n = Timeline(), 1
    last: tuple[np.ndarray, np.ndarray | None] | None = None
    log.info("board: %d keyframes from %d samples", len(keys), len(thumbs))
    for k, t in enumerate(keys, 1):
        frame = source.frame_at(t)
        mask = clients.segmenter.person_mask(frame)
        stats.keyframes += 1
        if last is not None:
            d = masked_board_diff(last[0], last[1], frame, mask)
            if d is not None and d < gate_thresh:
                stats.skipped_reads += 1
                log.info("board %d/%d at %.1fs: skipped (only the lecturer moved, %.2f)",
                         k, len(keys), t, d)
                continue
        last = (frame, mask)
        stats.board_calls += 1
        diff = clients.board.read_board(to_jpeg(apply_mask(frame, mask)), tl.alive_at(t))
        diff, next_n = assign_ids(diff, next_n)
        try:
            tl.apply(diff, t)
            log.info("board %d/%d at %.1fs: +%d updated %d erased %d", k, len(keys), t,
                     len(diff.added), len(diff.updated), len(diff.erased))
        except DiffError as e:  # model contradicted itself; keep the last good board
            stats.rejected_diffs += 1
            log.warning("rejected board diff at %.1fs: %s", t, e)
    return tl


def resolve_phrase(
    p: ReferencePhrase, words: list[Word], source: FrameSource, tl: Timeline,
    clients: Clients, stats: Stats, fingertips: list[Sample], threshold: float,
) -> Resolution:
    mid = (p.start + p.end) / 2
    shots = []
    for t in (max(0.0, p.start - 1.5), mid, min(source.duration, p.end + 1.5)):
        shots.append(FrameShot(t=t, jpeg=to_jpeg(source.frame_at(t)),
                               words=words_between(words, t - 0.75, t + 0.75)))
    # same window the validator accepts, so the model is never offered an answer
    # that would be rejected (e.g. something erased before the phrase)
    elements = tl.alive_during(p.start - LOOKBACK_S, p.end + LOOKAHEAD_S)
    req = ResolveRequest(
        phrase=p,
        sentence=words_between(words, p.start - 4.0, p.end + 3.0),
        frames=shots,
        elements=elements,
        candidates=candidates(elements, pointing_at(fingertips, p.start, p.end)),
    )
    stats.resolve_calls += 1
    res = validate_resolution(clients.resolver.resolve(req), p, tl, threshold)
    if res.status == "unresolved" and clients.escalate is not None:
        stats.escalations += 1
        res2 = validate_resolution(clients.escalate.resolve(req), p, tl, threshold)
        if res2.status == "resolved":
            return res2.model_copy(update={"evidence": [*res2.evidence, "escalated model"]})
    return res


def process(
    source: FrameSource,
    words: list[Word],
    clients: Clients,
    title: str,
    source_name: str,
    fingertips: list[Sample] | None = None,
    threshold: float = CONFIDENCE_THRESHOLD,
    models: dict[str, str] | None = None,
) -> tuple[LectureDoc, Stats]:
    stats = Stats()
    tl = build_board(source, clients, stats)
    phrases = find_reference_phrases(words)
    resolutions = []
    for k, p in enumerate(phrases, 1):
        r = resolve_phrase(p, words, source, tl, clients, stats, fingertips or [], threshold)
        log.info("resolve %d/%d %r at %.1fs -> %s %s (%.2f)", k, len(phrases), p.text, p.start,
                 r.status, r.element_id or "-", r.confidence)
        resolutions.append(r)
    doc = LectureDoc(title=title, source=source_name, duration=source.duration, words=words,
                     elements=tl.all(), phrases=phrases, resolutions=resolutions,
                     models=models or {})
    return doc, stats
