import logging

from eyecite.models import (
    CitationBase,
    CitationToken,
    FullCaseCitation,
    ReferenceCitation,
    ResourceCitation,
    ShortCaseCitation,
    SupraCitation,
)

logger = logging.getLogger(__name__)


def disambiguate_reporters(
    citations: list[CitationBase],
) -> list[CitationBase]:
    """Filter out citations where there is more than one possible reporter."""
    return [
        c
        for c in citations
        if not isinstance(c, ResourceCitation) or c.edition_guess
    ]


def overlapping_citations(
    full_span_1: tuple[int, int], full_span_2: tuple[int, int]
) -> bool:
    """Check if citations overlap at all"""
    start_1, end_1 = full_span_1
    start_2, end_2 = full_span_2
    return max(start_1, start_2) < min(end_1, end_2)


def filter_citations(citations: list[CitationBase]) -> list[CitationBase]:
    """Filter and order citations, ensuring reference citations are in sequence

    This function resolves rare but possible overlaps between ref. citations
    and short citations. It also orders all citations by their `citation.span`,
    as reference citations may be extracted out of order. The final result is a
    properly sorted list of citations as they appear in the text

    :param citations: List of citations
    :return: Sorted and filtered citations
    """
    if not citations:
        return citations

    citations = list(
        {citation.span(): citation for citation in citations}.values()
    )
    sorted_citations = sorted(
        citations, key=lambda citation: citation.full_span()
    )
    filtered_citations: list[CitationBase] = [sorted_citations[0]]

    for citation in sorted_citations[1:]:
        last_citation = filtered_citations[-1]
        is_overlapping = overlapping_citations(
            citation.full_span(), last_citation.full_span()
        )
        if is_overlapping:
            # In cases overlap, prefer anything to a reference citation
            if isinstance(last_citation, ReferenceCitation):
                filtered_citations.pop(-1)
                filtered_citations.append(citation)
                continue
            if isinstance(citation, ReferenceCitation):
                continue

            if isinstance(citation, SupraCitation) and isinstance(
                last_citation, ShortCaseCitation
            ):
                continue

            # A citation in a paren would also overlap and should be kept.
            paren = last_citation.metadata.parenthetical
            if paren and citation.matched_text() in paren:
                filtered_citations.append(citation)
                continue

            # Known overlap case are parallel full citations
            if not (
                isinstance(citation, FullCaseCitation)
                and isinstance(last_citation, FullCaseCitation)
            ):
                logger.warning(
                    "Unknown overlap case. Last cite: %s. Current: %s",
                    last_citation,
                    citation,
                )

        filtered_citations.append(citation)

    return filtered_citations


joke_cite: list[CitationBase] = [
    FullCaseCitation(
        CitationToken(
            "1 FLP 1",
            0,
            99,
            {
                "volume": "1",
                "reporter": "FLP",
                "page": "1",
            },
        ),
        0,
        metadata={
            "year": "2021",
            "extra": "Eyecite is a collaborative community effort.",
        },
    )
]
