from collections import deque

import pytest

from eyecite import get_citations
from eyecite.helpers import process_case_name_candidate


@pytest.mark.parametrize(
    ["test_candidate", "expected"],
    [
        (deque(["hi", "there", "how", "are", "you", "?"]), "hi there how are you?"),
        (deque(["you", "there"]), "you there"),
        (deque([".", "Thus", ",", "in", "Aarhaus", ","]), ". Thus, in Aarhaus,"),
        (deque(["cool", ".", "edge", "case", ",", "bro"]), "cool. edge case, bro"),
    ],
)
def test_process_case_name_candidate(test_candidate, expected):
    processed = process_case_name_candidate(test_candidate)
    res = " ".join(processed)

    assert res == expected


@pytest.mark.parametrize(
    ["test_text", "expected"],
    [
        (
            "This left rescissory damages as the principal alternative, but rescissory damages are the exception; not the rule. Strassbourg, 675 F.3d at 579.",
            "the rule. Strassbourg,",
        ),
        ("cool.stuff. Loki, 123 F.3d at 870; but hi", "cool. stuff. Loki,"),
        (
            "YOROR (S.D.N.Y. 1987); Cool v. Stuff, 123 F.3d 870, 876 (E.D. Cal. 1996). but I digress",
            "Cool v. Stuff,",
        ),
    ],
)
def test_case_name_candidate(test_text, expected):
    citations = get_citations(test_text)
    citation = citations[0]

    assert citation.name_candidate == expected
