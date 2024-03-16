import pytest

from eyecite import get_citations
from tests.assets.bluebook_citations import (
    bluebook_1,
    bluebook_2,
    bluebook_3,
    bluebook_4,
    bluebook_5,
)


@pytest.mark.parametrize(
    ["input_text", "count"],
    [
        (bluebook_1, 3),
        # (bluebook_2, 1),
        # (bluebook_3, 2),
        # (bluebook_4, 3),
        # (bluebook_5, 4),
    ],
)
def test_bluebook_count(input_text: str, count: int):
    cits = get_citations(input_text)
    assert len(cits) == count
