"""End-to-end pipeline on a synthetic 'lecture' with fake models (no API, no video file)."""

import numpy as np
from fixtures import CHAIN, CUBE_ROOT, words

from spokenslate.models.muse import ResolveRequest
from spokenslate.pipeline import Clients, assign_ids, process
from spokenslate.render import render_html
from spokenslate.spec import BoardDiff, ResolveOutput
from spokenslate.video import select_keyframes


class FakeVideo:
    """Board is blank until 10s, gains a line at 10s and another at 40s."""

    duration = 70.0

    def frame_at(self, t):
        f = np.full((360, 640, 3), 230, np.uint8)
        if t >= 10:
            f[100:130, 50:300] = 30
        if t >= 40:
            f[100:130, 350:600] = 30
        return f


class FakeBoard:
    def __init__(self):
        self.calls = []

    def read_board(self, jpeg, current):
        self.calls.append([e.id for e in current])
        n = len(self.calls)
        if n == 2:
            return BoardDiff(added=[CHAIN.model_copy(update={"id": "new1"})])
        if n == 3:
            return BoardDiff(added=[CUBE_ROOT.model_copy(update={"id": "new1"})])
        return BoardDiff()


class FakeResolver:
    def __init__(self, answer):
        self.answer, self.requests = answer, []

    def resolve(self, req: ResolveRequest):
        self.requests.append(req)
        return self.answer(req)


def test_keyframes_follow_board_changes():
    v = FakeVideo()
    samples = [(float(t), v.frame_at(t)) for t in range(70)]
    assert select_keyframes(samples) == [0.0, 10.0, 40.0]


def test_assign_ids_replaces_model_ids():
    d, n = assign_ids(BoardDiff(added=[CHAIN.model_copy(update={"id": "new1"}),
                                       CUBE_ROOT.model_copy(update={"id": "new2"})]), 5)
    assert [e.id for e in d.added] == ["e5", "e6"] and n == 7


def test_end_to_end_with_escalation():
    ws = words("so if I cover this with my hand do I have something to some power", start=59.0)
    # Spark abstains on "this"; Wonder answers with the hidden ln x
    spark = FakeResolver(lambda r: ResolveOutput(element_id=None, confidence=0.0))
    wonder = FakeResolver(lambda r: ResolveOutput(element_id="e2", quote="ln x", confidence=0.85,
                                                  evidence=["hand covers (ln x)"]))
    board = FakeBoard()
    doc, stats = process(FakeVideo(), ws, Clients(board=board, resolver=spark, escalate=wonder),
                         title="t", source_name="synthetic")
    assert stats.keyframes == 3 and stats.rejected_diffs == 0
    assert board.calls == [[], [], ["e1"]]                 # reader sees the current board
    assert [e.id for e in doc.elements] == ["e1", "e2"]
    (res,) = doc.resolutions
    assert res.status == "resolved" and res.element_id == "e2"
    assert "escalated model" in res.evidence and stats.escalations == 1
    req = spark.requests[0]
    assert len(req.frames) == 3 and "this" in req.frames[1].words
    assert {e.id for e in req.elements} == {"e1", "e2"}
    assert "means ln x, in step 2" in render_html(doc)


def test_invented_answer_stays_unresolved():
    ws = words("cover this now", start=59.0)
    liar = FakeResolver(lambda r: ResolveOutput(element_id="e7", quote="sin x", confidence=0.99))
    doc, _ = process(FakeVideo(), ws, Clients(board=FakeBoard(), resolver=liar),
                     title="t", source_name="synthetic")
    assert doc.resolutions[0].status == "unresolved"


def test_pointing_candidates_reach_the_resolver():
    ws = words("cover this now", start=59.0)
    seen = FakeResolver(lambda r: ResolveOutput(element_id=None, confidence=0.0))
    tips = [(59.0, 0.7, 0.45), (59.2, 0.71, 0.45)]
    process(FakeVideo(), ws, Clients(board=FakeBoard(), resolver=seen),
            title="t", source_name="s", fingertips=tips)
    assert seen.requests[0].candidates[0][0] == "e2"


def test_real_video_file_last_frame(tmp_path):
    """Regression: on real files, t == duration has no frame; frame_at must clamp."""
    import cv2

    from spokenslate.video import VideoFile

    path = tmp_path / "clip.mp4"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (640, 360))
    fv = FakeVideo()
    for i in range(120):
        w.write(fv.frame_at(i / 10))
    w.release()
    v = VideoFile(path)
    assert abs(v.duration - 12.0) < 0.2
    assert v.frame_at(v.duration).shape == (360, 640, 3)
    assert v.frame_at(11.0)[115, 100].mean() < 80   # the line written at 10s is there


def test_progress_is_logged(caplog):
    import logging

    ws = words("cover this now", start=59.0)
    spark = FakeResolver(lambda r: ResolveOutput(element_id="e2", quote="ln x", confidence=0.9))
    with caplog.at_level(logging.INFO, logger="spokenslate.pipeline"):
        process(FakeVideo(), ws, Clients(board=FakeBoard(), resolver=spark),
                title="t", source_name="s")
    msgs = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("board 1/") for m in msgs)
    assert any(m.startswith("resolve 1/1 'this'") and "resolved e2" in m for m in msgs)
