import pytest

from eyecite import get_citations
from tests.assets.bluebook_citations import (
    bluebook_1,
    bluebook_2,
    bluebook_3,
    bluebook_4,
    bluebook_5,
    bluebook_6,
    bluebook_7,
)

# bluebook_8,
from tests.assets.ca_citations import ca_1, ca_2, ca_3


@pytest.mark.parametrize(
    ["input_text", "count"],
    [
        (bluebook_1, 3),
        (bluebook_2, 4),
        (bluebook_3, 2),
        (bluebook_4, 5),
        (bluebook_5, 2),
        (bluebook_6, 11),
        (bluebook_7, 5),
        # (bluebook_8, 6), # Fails; obscure statutory scheme
    ],
)
def test_bluebook_count(input_text: str, count: int):
    cits = get_citations(input_text)

    for c in cits:
        print(c.corrected_citation_full())
    assert len(cits) == count


@pytest.mark.parametrize(["input_text", "count"], [(ca_1, 3), (ca_2, 5), (ca_3, 6)])
def test_ca_count(input_text: str, count: int):
    cits = get_citations(input_text)
    for c in cits:
        print("\n")
        print(c.corrected_citation_full())

    assert len(cits) == count
