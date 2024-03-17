import pytest

from eyecite import get_citations

# from eyecite.helpers import get_case_name_candidate


def test_case_name_candidate():
    test_text = """ This left rescissory damages as the
principal alternative, but rescissory damages are the exception; not the rule. Strassbourg, 675 F.3d at 579."""

    citations = get_citations(test_text)
    citation = citations[0]

    assert citation.name_candidate == " not the rule. Strassbourg"
