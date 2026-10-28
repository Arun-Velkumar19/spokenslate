from fixtures import leonard_timeline

from spokenslate.spec import ReferencePhrase, ResolveOutput
from spokenslate.validator import quote_matches, validate_resolution


def phrase(start, end=None, text="this"):
    return ReferencePhrase(id="r1", text=text, kind="deictic", start=start,
                           end=end if end is not None else start + 0.3,
                           word_start=0, word_end=1)


def out(eid, quote="", conf=0.9):
    return ResolveOutput(element_id=eid, quote=quote, confidence=conf, evidence=["pointing"])


def test_resolves_hidden_ln_x():
    # "if I cover this" -> the ln x inside (ln x)^(1/3)  (playground test 2E)
    r = validate_resolution(out("e2", "ln x", 0.85), phrase(59.0), leonard_timeline())
    assert r.status == "resolved" and r.element_id == "e2"


def test_abstain_is_unresolved():
    r = validate_resolution(ResolveOutput(element_id=None, confidence=0.0), phrase(59), leonard_timeline())
    assert r.status == "unresolved" and r.note == "model abstained"


def test_invented_id_rejected():
    r = validate_resolution(out("e99"), phrase(59), leonard_timeline())
    assert r.status == "unresolved" and "unknown element" in r.note


def test_not_on_board_yet_or_already_erased():
    tl = leonard_timeline()
    assert validate_resolution(out("e3", "x^3 ln 5x"), phrase(20), tl).status == "unresolved"
    assert validate_resolution(out("e1", "(x^2+1)^3"), phrase(130), tl).status == "unresolved"
    # written a few seconds after being named ("this problem" while writing it) is fine
    assert validate_resolution(out("e3", "x^3 ln 5x"), phrase(115), tl).status == "resolved"


def test_quote_mismatch_rejected():
    r = validate_resolution(out("e2", "sin(theta)"), phrase(59), leonard_timeline())
    assert r.status == "unresolved" and "quote" in r.note


def test_low_confidence_becomes_suggestion():
    r = validate_resolution(out("e2", "ln x", 0.5), phrase(59), leonard_timeline())
    assert r.status == "unresolved" and r.suggested_element_id == "e2"


def test_quote_matching_tolerates_latex_and_spacing():
    assert quote_matches("(x^2+1)^3", r"\frac{d}{dx}[(x^2+1)^3] = 3(x^2+1)^2")
    assert quote_matches("ln x", r"(\ln x)^{1/3}")
    assert quote_matches("", "anything")
    assert not quote_matches("sin theta", r"(\ln x)^{1/3}")
