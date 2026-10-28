"""Benchmark scoring on synthetic docs and CSVs (no API, no video)."""

import importlib.util
from pathlib import Path

import pytest

from paperos.scoring import (
    TruthRow,
    baseline,
    load_truth,
    parse_window,
    phrase_matches,
    score_doc,
)
from paperos.spec import LectureDoc, ReferencePhrase, Region, Resolution, TimedElement

spec = importlib.util.spec_from_file_location(
    "score", Path(__file__).parents[1] / "scripts" / "score.py"
)
score_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_script)

R = Region(x0=0.1, y0=0.1, x1=0.4, y1=0.2)
HEADER = "date,lecture,lecturer,t,phrase,kind,truth,model,answer,confidence,outcome,notes\n"


def el(id, content):
    return TimedElement(id=id, kind="math", content=content, region=R, first_seen=0,
                        last_updated=0)


def ph(id, text, start):
    return ReferencePhrase(id=id, text=text, kind="deictic", start=start, end=start + 0.6,
                           word_start=0, word_end=1)


def resolved(pid, eid, conf, quote=""):
    return Resolution(phrase_id=pid, status="resolved", element_id=eid, confidence=conf,
                      quote=quote)


def unresolved(pid, suggested=None):
    return Resolution(phrase_id=pid, status="unresolved", note="low confidence",
                      suggested_element_id=suggested)


def doc(phrases, resolutions):
    return LectureDoc(
        title="t", source="s", duration=600, words=[],
        elements=[el("e1", r"\frac{d}{dx}[(x^2+1)^3]"), el("e2", "x^3"), el("e3", r"\ln 5x")],
        phrases=phrases, resolutions=resolutions,
    )


@pytest.mark.parametrize("s, window", [
    ("51:10", (3070, 3070)), ("~59:05", (3545, 3545)), ("1:10:35+", (4235, 4235)),
    ("1:10:25-35", (4225, 4235)), ("59:15-1:00:02", (3555, 3602)), ("12.5", (12.5, 12.5)),
])
def test_parse_window(s, window):
    assert parse_window(s) == window


def test_phrase_text_matching():
    assert phrase_matches("the first / the second", "the second")
    assert phrase_matches("here (what we had here)", "here")
    assert phrase_matches('"this problem"', "This problem,")
    assert phrase_matches("the problem I just gave you", "the problem i just gave you")
    assert not phrase_matches("(problem being worked)", "problem")   # description, not speech
    assert not phrase_matches("the first", "the second")
    assert not phrase_matches("this term", "that equation")


def test_all_four_outcomes_and_baseline():
    rows = [
        TruthRow(10, 10, "this term", "e1"),                         # correct by id
        TruthRow(20, 20, "the first", "x^3"),                         # correct by text
        TruthRow(30, 30, "the second", "e3"),                         # confident wrong
        TruthRow(40, 40, "over here", "ln 5x"),                       # low-confidence wrong
        TruthRow(50, 50, "this one", "e1"),                           # unresolved (suggested)
        TruthRow(60, 60, "that", "unresolved"),                       # correct abstention
        TruthRow(70, 70, "it", "unresolved"),                         # wrong: resolved anyway
        TruthRow(80, 80, "the inside", "e2"),                         # missed: no phrase
    ]
    d = doc(
        [ph("p1", "this term", 10.2), ph("p2", "the first", 19.5), ph("p3", "the second", 30),
         ph("p4", "over here", 40), ph("p5", "this one", 50), ph("p6", "that", 60),
         ph("p7", "it", 70), ph("p8", "the inside", 200)],
        [resolved("p1", "e1", 0.9), resolved("p2", "e2", 0.8), resolved("p3", "e2", 0.85),
         resolved("p4", "e2", 0.5), unresolved("p5", suggested="e1"), unresolved("p6"),
         resolved("p7", "e3", 0.95), resolved("p8", "e2", 0.9)],
    )
    s = score_doc(rows, d)
    assert [j.outcome for j in s.judged] == [
        "correct", "correct", "wrong", "wrong", "unresolved", "correct", "wrong", "unresolved"]
    assert s.row() == {"system": "seed", "n": 8, "correct": 3, "unresolved": 2, "wrong": 3,
                       "confident_wrong": 2, "missed": 1}
    assert [j.confident_wrong for j in s.judged][2:7] == [True, False, False, False, True]

    b = baseline(rows).row()
    assert (b["correct"], b["unresolved"], b["wrong"], b["confident_wrong"]) == (2, 6, 0, 0)


def test_free_text_truth_must_be_in_linked_element():
    rows = [TruthRow(10, 10, "the inside", "x^2+1")]
    d = doc([ph("p1", "the inside", 10)], [resolved("p1", "e1", 0.9, quote="(x^2 + 1)")])
    assert score_doc(rows, d).judged[0].outcome == "correct"


def test_model_quote_cannot_rescue_a_wrong_link():
    """Regression: wrong element + short quote contained in the truth was scored correct."""
    rows = [TruthRow(10, 10, "this", "(x^2+1)^3")]
    d = doc([ph("p1", "this", 10)], [resolved("p1", "e2", 0.9, quote="x")])  # e2 = x^3
    j = score_doc(rows, d).judged[0]
    assert j.outcome == "wrong" and j.confident_wrong


def test_one_phrase_per_row_nearest_in_time():
    rows = [TruthRow(10, 10, "this", "e1"), TruthRow(13, 13, "this", "e2")]
    d = doc([ph("p1", "this", 12.8), ph("p2", "this", 10.1)],
            [resolved("p1", "e2", 0.9), resolved("p2", "e1", 0.9)])
    s = score_doc(rows, d)
    assert [j.phrase_id for j in s.judged] == ["p2", "p1"]
    assert s.count("correct") == 2


def test_outside_time_window_is_missed():
    rows = [TruthRow(10, 10, "this term", "e1")]
    d = doc([ph("p1", "this term", 30)], [resolved("p1", "e1", 0.9)])
    assert score_doc(rows, d, tol=5).judged[0].missed
    assert score_doc(rows, d, tol=25).judged[0].outcome == "correct"


def test_load_truth_and_lecture_filter(tmp_path):
    csv = tmp_path / "refs.csv"
    csv.write_text(HEADER
                   + '2026-10-27,Calc 2 Lecture 6.1,Leonard,~0:10,"this term",deictic,e1,,,,,\n'
                   + "2026-10-28,MIT 18.01,Jerison,1:00-05,the first,role,unresolved,,,,,\n")
    rows = load_truth(csv)
    assert [(r.t0, r.t1, r.truth) for r in rows] == [(10, 10, "e1"), (60, 65, "unresolved")]
    assert [r.lecture for r in load_truth(csv, "6.1")] == ["Calc 2 Lecture 6.1"]


def test_cli_prints_seed_and_baseline_rows(tmp_path, capsys):
    csv = tmp_path / "refs.csv"
    csv.write_text(HEADER + '2026-10-28,clip,x,1:00,"this term",deictic,e1,,,,,\n')
    path = tmp_path / "clip.json"
    path.write_text(doc([ph("p1", "this term", 30)], [resolved("p1", "e1", 0.9)])
                    .model_dump_json())
    score_script.main(["--truth", str(csv), "--doc", str(path), "--offset", "-30", "-v"])
    out = capsys.readouterr().out.splitlines()
    assert out[0].split() == ["system", "n", "correct", "unresolved", "wrong",
                              "confident_wrong", "missed"]
    assert out[1].split() == ["seed", "1", "1", "0", "0", "0", "0"]
    assert out[2].split() == ["transcript", "(baseline)", "1", "0", "1", "0", "0", "1"]
    assert "correct" in out[3] and "phrase=p1" in out[3]
