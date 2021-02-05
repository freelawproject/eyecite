import re
from typing import List, Optional, Union

from courts_db import courts

from eyecite.models import (
    CaseCitation,
    CitationBase,
    FullCaseCitation,
    StopWordToken,
    Token,
    TokenOrStr,
    Tokens,
)
from eyecite.utils import PAGE_NUMBER_REGEX, strip_punct

FORWARD_SEEK = 20
BACKWARD_SEEK = 28  # Median case name length in the CL db is 28 (2016-02-26)


def get_court_by_paren(
    paren_string: str, citation: CaseCitation
) -> Optional[str]:
    """Takes the citation string, usually something like "2d Cir", and maps
    that back to the court code.

    Does not work on SCOTUS, since that court lacks parentheticals, and
    needs to be handled after disambiguation has been completed.
    """
    if citation.year is None:
        court_str = strip_punct(paren_string)
    else:
        year_index = paren_string.find(str(citation.year))
        court_str = strip_punct(paren_string[:year_index])

    court_code = None
    if court_str == "":
        court_code = None
    else:
        # Map the string to a court, if possible.
        for court in courts:
            # Use startswith because citations are often missing final period,
            # e.g. "2d Cir"
            if court["citation_string"].startswith(court_str):
                court_code = court["id"]
                break

    return court_code


def get_year(token: TokenOrStr) -> Optional[int]:
    """Given a string token, look for a valid 4-digit number at the start and
    return its value.
    """
    word = strip_punct(str(token))
    if not word.isdigit():
        # Sometimes funny stuff happens?
        word = re.sub(r"(\d{4}).*", r"\1", word)
        if not word.isdigit():
            return None
    if len(word) != 4:
        return None
    year = int(word)
    if year < 1754:  # Earliest case in the database
        return None
    return year


def add_post_citation(citation: CaseCitation, words: Tokens) -> None:
    """Add to a citation object any additional information found after the base
    citation, including court, year, and possibly page range.

    Examples:
        Full citation: 123 U.S. 345 (1894)
        Post-citation info: year=1894

        Full citation: 123 F.2d 345, 347-348 (4th Cir. 1990)
        Post-citation info: year=1990, court="4th Cir.",
        extra (page range)="347-348"
    """
    # Start looking 2 tokens after the reporter (1 after page), and go to
    # either the end of the words list or to FORWARD_SEEK tokens from where you
    # started.
    fwd_sk = citation.index + FORWARD_SEEK
    for start in range(citation.index + 1, min(fwd_sk, len(words))):
        if words[start].startswith("("):
            # Get the year by looking for a token that ends in a paren.
            for end in range(start, start + FORWARD_SEEK):
                if ")" in words[end]:
                    # Sometimes the paren gets split from the preceding content
                    if words[end].startswith(")"):
                        citation.year = get_year(words[end - 1])
                    else:
                        citation.year = get_year(words[end])
                    citation.court = get_court_by_paren(
                        " ".join(str(w) for w in words[start : end + 1]),
                        citation,
                    )
                    break

            if start > citation.index + 1:
                # Then there's content between page and (), starting with a
                # comma, which we skip
                citation.extra = " ".join(
                    str(w) for w in words[citation.index + 2 : start]
                )
            break


def add_defendant(citation: CaseCitation, words: Tokens) -> None:
    """Scan backwards from reporter until you find v., in re,
    etc. If no known stop-token is found, no defendant name is stored.  In the
    future, this could be improved.
    """
    start_index = None
    back_seek = citation.index - BACKWARD_SEEK
    for index in range(citation.index - 1, max(back_seek, -1), -1):
        word = words[index]
        if word == ",":
            # Skip it
            continue
        if isinstance(word, StopWordToken):
            if word.stop_word == "v":
                citation.plaintiff = str(words[index - 1])
            start_index = index + 1
            break
        if word.endswith(";"):
            # String citation
            break
    if start_index:
        citation.defendant = " ".join(
            str(w) for w in words[start_index : citation.index]
        )


def parse_page(page: Union[str, int]) -> Optional[str]:
    """Test whether something is a valid page number."""
    page = strip_punct(str(page))

    if page.isdigit():
        # First, check whether the page is a simple digit. Most will be.
        return page

    # Otherwise, check whether the "page" is really one of the following:
    # (ordered in descending order of likelihood)
    # 1) A numerical page range. E.g., "123-124"
    # 2) A roman numeral. E.g., "250 Neb. xxiv (1996)"
    # 3) A special Connecticut or Illinois number. E.g., "13301-M"
    # 4) A page with a weird suffix. E.g., "559 N.W.2d 826|N.D."
    # 5) A page with a ¶ symbol, star, and/or colon. E.g., "¶ 119:12-14"
    match = re.match(PAGE_NUMBER_REGEX, page)
    if match:
        return str(match.group(0))
    return None


def disambiguate_reporters(
    citations: List[CitationBase],
) -> List[CitationBase]:
    """Filter out citations where there is more than one possible reporter."""
    return [
        c
        for c in citations
        if not isinstance(c, CaseCitation) or c.edition_guess
    ]


def remove_address_citations(
    citations: List[CitationBase],
) -> List[CitationBase]:
    """Some addresses look like citations, but they're not. Remove them.

    An example might be 111 S.W. 23st St.

    :param citations: A list of citations. These should generally be
    disambiguated, but it's not essential.
    :returns A list of citations with addresses removed.
    """
    coordinate_reporters = ("N.E.", "S.E.", "S.W.", "N.W.")
    good_citations = []
    for citation in citations:
        if not isinstance(citation, FullCaseCitation):
            good_citations.append(citation)
            continue

        if not isinstance(citation.page, str):
            good_citations.append(citation)
            continue

        page = citation.page.lower()
        is_ordinal_page = (
            page.endswith("st")
            or page.endswith("nd")
            or page.endswith("rd")
            or page.endswith("th")
        )
        is_coordinate_reporter = (
            # Assuming disambiguation was used, check the canonical_reporter
            citation.canonical_reporter in coordinate_reporters
            # If disambiguation wasn't used, check the reporter attr
            or citation.reporter in coordinate_reporters
        )
        if is_ordinal_page and is_coordinate_reporter:
            # It's an address. Skip it.
            continue

        good_citations.append(citation)
    return good_citations


joke_cite: List[CaseCitation] = [
    CaseCitation(
        Token("1 FLP 1", 0, 7),
        0,
        volume="1",
        reporter="FLP",
        page="1",
        year=2021,
        extra="Eyecite is a collaborative community effort.",
    )
]
