import pytest
from fixtures import CHAIN, CUBE_ROOT, el, leonard_timeline

from spokenslate.spec import BoardDiff
from spokenslate.timeline import DiffError, Timeline


def test_alive_and_erased_kept():
    tl = leonard_timeline()
    assert [e.id for e in tl.alive_at(50)] == ["e1", "e2"]
    assert [e.id for e in tl.alive_at(130)] == ["e2", "e3"]
    gone = tl.get("e1")
    assert gone.erased_at == 120.0 and gone.first_seen == 10.0  # erased, not deleted
    assert [e.id for e in tl.all()] == ["e1", "e2", "e3"]


def test_alive_during_window():
    tl = leonard_timeline()
    assert {e.id for e in tl.alive_during(115, 125)} == {"e1", "e2", "e3"}
    assert {e.id for e in tl.alive_during(0, 5)} == set()


def test_update_keeps_first_seen():
    tl = Timeline()
    tl.apply(BoardDiff(added=[el("a", "x^2", .1, .1, .2, .2)]), 5.0)
    tl.apply(BoardDiff(updated=[el("a", "x^2 + 1", .1, .1, .3, .2)]), 8.0)
    a = tl.get("a")
    assert (a.first_seen, a.last_updated, a.content) == (5.0, 8.0, "x^2 + 1")


@pytest.mark.parametrize("diff", [
    BoardDiff(erased=["nope"]),
    BoardDiff(updated=[el("nope", "y", .1, .1, .2, .2)]),
    BoardDiff(added=[CHAIN]),                       # id reuse
    BoardDiff(erased=["e1"], updated=[CHAIN]),      # same id twice
])
def test_bad_diffs_rejected_atomically(diff):
    tl = Timeline()
    tl.apply(BoardDiff(added=[CHAIN, CUBE_ROOT]), 10.0)
    before = [e.model_dump() for e in tl.all()]
    with pytest.raises(DiffError):
        tl.apply(diff, 20.0)
    assert [e.model_dump() for e in tl.all()] == before


def test_erased_id_never_reused():
    tl = leonard_timeline()
    with pytest.raises(DiffError):
        tl.apply(BoardDiff(added=[CHAIN]), 200.0)


def test_out_of_order_rejected():
    tl = leonard_timeline()
    with pytest.raises(DiffError):
        tl.apply(BoardDiff(added=[el("z", "z", .1, .8, .2, .9)]), 50.0)
