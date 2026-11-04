from fixtures import words

from spokenslate.references import find_reference_phrases


def texts(s):
    return [(p.text, p.kind) for p in find_reference_phrases(words(s))]


def test_leonard_sentences():
    assert texts("the similarity between the problem I just gave you and this problem right") \
        == [("the problem", "anaphora"), ("this problem", "deictic")]
    assert texts("No, I know there's an ln over here, but what we had here, we had something") \
        == [("over here,", "deictic"), ("here,", "deictic")]
    assert texts("if I cover this with my hand do I have something to some power") \
        == [("this", "deictic")]


def test_roles_product_rule():
    got = texts("derivative of the first times the second plus the first times the derivative of the second")
    assert got == [("the first", "role"), ("the second", "role"),
                   ("the first", "role"), ("the second", "role")]


def test_inside():
    assert texts("multiply by the derivative of whatever the inside is") == [("the inside", "role")]


def test_conjunction_that_and_existential_there_skipped():
    assert texts("notice that it cancels") == []
    assert texts("so that we can integrate") == []
    assert texts("there is a constant and there are two roots") == []
    assert texts("the first time I saw this") == [("this", "deictic")]


def test_object_that_kept():
    assert texts("now cancel that and we're done") == [("that", "deictic")]
    assert texts("that term goes away") == [("that term", "deictic")]


def test_timestamps_and_spans():
    ws = words("cover this term now", start=10.0, step=0.5)
    (p,) = find_reference_phrases(ws)
    assert (p.word_start, p.word_end) == (1, 3)
    assert p.start == ws[1].start and p.end == ws[2].end


def test_anaphora_needs_a_pointer_back():
    assert texts("plug it into the equation from before") == [("the equation", "anaphora")]
    assert texts("the equation is linear") == []          # generic, not pointing back
    assert texts("the derivative of the inside") == [("the inside", "role")]


def test_first_live_run_cases():
    """From the Oct 29 Strang run: existential 'is there a', modifier + noun phrases."""
    assert texts("box all three pivots. Is there a, I think that's") == []
    assert texts("the three pivots are there. I know") == [("there.", "deictic")]
    assert texts("This elimination step from A") == [("This elimination step", "deictic")]
    assert texts("so this is the step") == [("this", "deictic")]           # 'is' isn't a modifier
    assert texts("cover this with my hand") == [("this", "deictic")]


def test_demonstrative_is_never_a_modifier():
    """Nov 1 whiteboard run: "we can see that this function" came out as one phrase."""
    assert texts("so we can see that this function is a product") == [("this function", "deictic")]
    assert texts("similar to this first function") == [("this first function", "deictic")]


def test_sentence_initial_that_is_a_reference():
    # Nov 3 mini clip: the lecturer points at a wrong line and says "That is wrong."
    assert texts("Let's differentiate this function. That is wrong.") \
        == [("this function.", "deictic"), ("That", "deictic")]
    assert texts("That is wrong.") == [("That", "deictic")]
    # mid-sentence "that is" stays a conjunction / relative clause
    assert texts("notice that is not zero") == []
