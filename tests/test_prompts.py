"""The prompts' worked examples must agree with the code that checks the answers."""

import re

from spokenslate.models.prompts import board_prompt, resolve_prompt
from spokenslate.validator import quote_matches

BOARD = board_prompt([])
RESOLVE = resolve_prompt("this row", "s", [(1.0, "this row")], [], [])
MATRIX = re.search(r"content (\\begin\{bmatrix\}.*?\\end\{bmatrix\})", BOARD, re.DOTALL).group(1)
ROW_QUOTE = re.search(r'\(e\.g\. "(0 & .*?)"\)', RESOLVE).group(1)


def test_matrix_example_is_one_element():
    assert "is ONE element" in BOARD
    assert MATRIX.count("\\\\") == 1 and MATRIX.count("&") == 4   # 2 rows x 3 entries


def test_row_quote_example_passes_the_validator():
    assert quote_matches(ROW_QUOTE, MATRIX)
    assert not quote_matches("0 0 5", MATRIX)       # a row that isn't there still fails


def test_safety_rules_still_present():
    assert "Hidden is not erased" in BOARD
    assert "NOT new: match it by content and keep its id" in BOARD
    assert "A wrong answer is worse than no answer" in RESOLVE
