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


class WalkingLecturer(FakeVideo):
    """The FakeVideo board, plus a dark 'lecturer' that walks across it every 4 s."""

    def frame_at(self, t):
        f = super().frame_at(t)
        x = int(40 + (t * 37) % 500)
        f[150:350, x:x + 60] = 60
        return f


class BoxSegmenter:
    """Perfect lecturer mask for WalkingLecturer."""

    def __init__(self, video):
        self.video, self.calls = video, 0

    def person_mask(self, frame):
        self.calls += 1
        m = np.zeros(frame.shape[:2], np.uint8)
        m[(frame[:, :, 0] == 60)] = 255
        return m


def test_sam_gate_skips_reads_when_only_the_lecturer_moved():
    from spokenslate.pipeline import Stats, build_board

    video = WalkingLecturer()
    no_gate, gated = Stats(), Stats()
    build_board(video, Clients(board=FakeBoard(), resolver=None), no_gate)
    board = FakeBoard()
    tl = build_board(video, Clients(board=board, resolver=None,
                                    segmenter=BoxSegmenter(video)), gated)
    assert no_gate.board_calls == no_gate.keyframes > 3    # walking triggers every candidate
    assert gated.keyframes == no_gate.keyframes
    assert gated.board_calls + gated.skipped_reads == gated.keyframes
    assert gated.board_calls < no_gate.board_calls          # paid reads saved
    assert gated.board_calls >= 3                            # 0 s, 10 s and 40 s writing still read
    assert len(tl.all()) == 2                                # both lines still on the board



class ExposingLecturer(WalkingLecturer):
    """WalkingLecturer filmed by a phone that re-exposes as the lecturer moves (Nov 1 clip:
    the bare wall swung between grey 165 and 232)."""

    def frame_at(self, t):
        f = super().frame_at(t).astype(np.float32)
        gain = 0.8 + 0.2 * ((int(t) // 4) % 3) / 2            # 0.8, 0.9, 1.0, ...
        out = np.clip(f * gain, 0, 255).astype(np.uint8)
        out[f[:, :, 0] == 60] = 60                               # keep the 'lecturer' detectable
        return out


def test_sam_gate_ignores_auto_exposure():
    from spokenslate.pipeline import Stats, build_board

    video, stats = ExposingLecturer(), Stats()
    tl = build_board(video, Clients(board=FakeBoard(), resolver=None,
                                    segmenter=BoxSegmenter(video)), stats)
    assert stats.skipped_reads > stats.keyframes // 2     # brightness swings are not writing
    assert stats.board_calls >= 3 and len(tl.all()) == 2  # real writing still read
