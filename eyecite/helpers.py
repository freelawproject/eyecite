import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Union

from courts_db import courts
from reporters_db import EDITIONS, REPORTERS, VARIATIONS_ONLY

from eyecite.models import (
    Citation,
    FullCitation,
    NonopinionCitation,
    ShortformCitation,
)
from eyecite.utils import is_roman, strip_punct

FORWARD_SEEK = 20
BACKWARD_SEEK = 28  # Median case name length in the CL db is 28 (2016-02-26)
STOP_TOKENS = [
    "v",
    "re",
    "parte",
    "denied",
    "citing",
    "aff'd",
    "affirmed",
    "remanded",
    "see",
    "granted",
    "dismissed",
]
REPORTER_STRINGS: Set[str] = set(
    list(EDITIONS.keys()) + list(VARIATIONS_ONLY.keys())
)


def is_scotus_reporter(citation: Citation) -> bool:
    """Check if the citation is for a SCOTUS reporter."""
    try:
        reporter = REPORTERS[citation.canonical_reporter][
            citation.lookup_index
        ]
    except (TypeError, KeyError):
        # Occurs when citation.lookup_index is None
        return False

    if reporter:
        truisms = [
            (
                reporter["cite_type"] == "federal"
                and "supreme" in reporter["name"].lower()
            ),
            "scotus" in reporter["cite_type"].lower(),
        ]
        return any(truisms)
    return False


def is_neutral_tc_reporter(reporter: str) -> bool:
    """Test whether the reporter is a neutral Tax Court reporter.

    These take the format of T.C. Memo YEAR-SERIAL

    :param reporter: A string of the reporter, e.g. "F.2d" or "T.C. Memo"
    :return True if a T.C. neutral citation, else False
    """
    if re.match(r"T\. ?C\. (Summary|Memo)", reporter):
        return True
    return False


def get_court_by_paren(paren_string: str, citation: Citation) -> Optional[str]:
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


def get_year(token: str) -> Optional[int]:
    """Given a string token, look for a valid 4-digit number at the start and
    return its value.
    """
    token = strip_punct(token)
    if not token.isdigit():
        # Sometimes funny stuff happens?
        token = re.sub(r"(\d{4}).*", r"\1", token)
        if not token.isdigit():
            return None
    if len(token) != 4:
        return None
    year = int(token)
    if year < 1754:  # Earliest case in the database
        return None
    return year


def add_post_citation(citation: Citation, words: List[str]) -> None:
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
    fwd_sk = citation.reporter_index + FORWARD_SEEK
    for start in range(citation.reporter_index + 2, min(fwd_sk, len(words))):
        if words[start].startswith("("):
            # Get the year by looking for a token that ends in a paren.
            for end in range(start, start + FORWARD_SEEK):
                try:
                    has_ending_paren = words[end].find(")") > -1
                except IndexError:
                    # Happens with words like "(1982"
                    break
                if has_ending_paren:
                    # Sometimes the paren gets split from the preceding content
                    if words[end].startswith(")"):
                        citation.year = get_year(words[end - 1])
                    else:
                        citation.year = get_year(words[end])
                    citation.court = get_court_by_paren(
                        " ".join(words[start : end + 1]), citation
                    )
                    break

            if start > citation.reporter_index + 2:
                # Then there's content between page and (), starting with a
                # comma, which we skip
                citation.extra = " ".join(
                    words[citation.reporter_index + 2 : start]
                )
            break


def add_defendant(citation: Citation, words: List[str]) -> None:
    """Scan backwards from 2 tokens before reporter until you find v., in re,
    etc. If no known stop-token is found, no defendant name is stored.  In the
    future, this could be improved.
    """
    start_index = None
    back_seek = citation.reporter_index - BACKWARD_SEEK
    for index in range(citation.reporter_index - 1, max(back_seek, 0), -1):
        word = words[index]
        if word == ",":
            # Skip it
            continue
        if strip_punct(word).lower() in STOP_TOKENS:
            if word == "v.":
                citation.plaintiff = words[index - 1]
            start_index = index + 1
            break
        if word.endswith(";"):
            # String citation
            break
    if start_index:
        citation.defendant = " ".join(
            words[start_index : citation.reporter_index - 1]
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
    match = (
        re.match(r"\d{1,6}-\d{1,6}", page)  # Simple page range
        or is_roman(page)  # Roman numeral
        or re.match(r"\d{1,6}[-]?[a-zA-Z]{1,6}", page)  # CT/IL page
        or re.match(r"\d{1,6}", page)  # Weird suffix
        or re.match(r"[*\u00b6\ ]*[0-9:\-]+", page)  # ¶, star, colon
    )
    if match:
        return str(match.group(0))
    return None


def is_date_in_reporter(
    editions: Dict[str, Dict[str, Optional[datetime]]],
    year: int,
) -> bool:
    """Checks whether a year falls within the range of 1 to n editions of a
    reporter

    Editions will look something like:
        'editions': {'S.E.': {'start': datetime.datetime(1887, 1, 1),
                              'end': datetime.datetime(1939, 12, 31)},
                     'S.E.2d': {'start': datetime.datetime(1939, 1, 1),
                                'end': None}},
    """
    for date_dict in editions.values():
        if date_dict["end"] is None:
            date_dict["end"] = datetime.now()

        # At this point, both "start" and "end" should be datetime objects
        assert isinstance(date_dict["start"], datetime)
        assert isinstance(date_dict["end"], datetime)

        if date_dict["start"].year <= year <= date_dict["end"].year:
            return True
    return False


def disambiguate_reporters(
    citations: List[Union[Citation, NonopinionCitation]]
) -> List[Union[Citation, NonopinionCitation]]:
    """Convert a list of citations to a list of unambiguous ones.

    Goal is to figure out:
     - citation.canonical_reporter
     - citation.lookup_index

    And there are a few things that can be ambiguous:
     - More than one variation.
     - More than one reporter for the key.
     - Could be an edition (or not)
     - All combinations of the above:
        - More than one variation.
        - More than one variation, with more than one reporter for the key.
        - More than one variation, with more than one reporter for the key,
          which is an edition.
        - More than one variation, which is an edition
        - ...

    For variants, we just need to sort out the canonical_reporter.

    If it's not possible to disambiguate the reporter, we simply have to drop
    it.
    """
    unambiguous_citations = []
    for citation in citations:
        # Only disambiguate citations with a reporter
        if not isinstance(citation, (FullCitation, ShortformCitation)):
            unambiguous_citations.append(citation)
            continue

        # Non-variant items (P.R.R., A.2d, Wash., etc.)
        if REPORTERS.get(EDITIONS.get(citation.reporter)) is not None:
            citation.canonical_reporter = EDITIONS[citation.reporter]
            if len(REPORTERS[EDITIONS[citation.reporter]]) == 1:
                # Single reporter, easy-peasy.
                citation.lookup_index = 0
                unambiguous_citations.append(citation)
                continue

            # Multiple books under this key, but which is correct?
            if citation.year:
                # attempt resolution by date
                possible_citations = []
                rep_len = len(REPORTERS[EDITIONS[citation.reporter]])
                for i in range(0, rep_len):
                    if is_date_in_reporter(
                        REPORTERS[EDITIONS[citation.reporter]][i]["editions"],
                        citation.year,
                    ):
                        possible_citations.append((citation.reporter, i))
                if len(possible_citations) == 1:
                    # We were able to identify only one hit
                    # after filtering by year.
                    citation.reporter = possible_citations[0][0]
                    citation.lookup_index = possible_citations[0][1]
                    unambiguous_citations.append(citation)
                    continue

        # Try doing a variation of an edition.
        elif VARIATIONS_ONLY.get(citation.reporter) is not None:
            if len(VARIATIONS_ONLY[citation.reporter]) == 1:
                # Only one variation -- great, use it.
                citation.canonical_reporter = EDITIONS[
                    VARIATIONS_ONLY[citation.reporter][0]
                ]
                cached_variation = citation.reporter
                citation.reporter = VARIATIONS_ONLY[citation.reporter][0]
                if len(REPORTERS[citation.canonical_reporter]) == 1:
                    # It's a single reporter under a misspelled key.
                    citation.lookup_index = 0
                    unambiguous_citations.append(citation)
                    continue

                # Multiple reporters under a single misspelled key
                # (e.g. Wn.2d --> Wash --> Va Reports, Wash or
                #                          Washington Reports).
                if citation.year:
                    # attempt resolution by date
                    possible_citations = []
                    rep_can = len(REPORTERS[citation.canonical_reporter])
                    for i in range(0, rep_can):
                        if is_date_in_reporter(
                            REPORTERS[citation.canonical_reporter][i][
                                "editions"
                            ],
                            citation.year,
                        ):
                            possible_citations.append((citation.reporter, i))
                    if len(possible_citations) == 1:
                        # We were able to identify only one hit after
                        # filtering by year.
                        citation.lookup_index = possible_citations[0][1]
                        unambiguous_citations.append(citation)
                        continue
                # Attempt resolution by unique variation
                # (e.g. Cr. can only be Cranch[0])
                possible_citations = []
                reps = REPORTERS[citation.canonical_reporter]
                for i in range(0, len(reps)):
                    for variation in REPORTERS[citation.canonical_reporter][i][
                        "variations"
                    ].items():
                        if variation[0] == cached_variation:
                            possible_citations.append((variation[1], i))
                if len(possible_citations) == 1:
                    # We were able to find a single match after filtering
                    # by variation.
                    citation.lookup_index = possible_citations[0][1]
                    unambiguous_citations.append(citation)
                    continue
            else:
                # Multiple variations, deal with them.
                possible_citations = []
                for reporter_key in VARIATIONS_ONLY[citation.reporter]:
                    for i in range(0, len(REPORTERS[EDITIONS[reporter_key]])):
                        # This inner loop works regardless of the number of
                        # reporters under the key.
                        key = REPORTERS[EDITIONS[reporter_key]]
                        if citation.year:
                            cite_year = citation.year
                            if is_date_in_reporter(
                                key[i]["editions"], cite_year
                            ):
                                possible_citations.append((reporter_key, i))
                if len(possible_citations) == 1:
                    # We were able to identify only one hit after filtering by
                    # year.
                    citation.canonical_reporter = EDITIONS[
                        possible_citations[0][0]
                    ]
                    citation.reporter = possible_citations[0][0]
                    citation.lookup_index = possible_citations[0][1]
                    unambiguous_citations.append(citation)
                    continue

    return unambiguous_citations


def remove_address_citations(
    citations: List[Union[Citation, NonopinionCitation]]
) -> List[Union[Citation, NonopinionCitation]]:
    """Some addresses look like citations, but they're not. Remove them.

    An example might be 111 S.W. 23st St.

    :param citations: A list of citations. These should generally be
    disambiguated, but it's not essential.
    :returns A list of citations with addresses removed.
    """
    coordinate_reporters = ("N.E.", "S.E.", "S.W.", "N.W.")
    good_citations = []
    for citation in citations:
        if not isinstance(citation, FullCitation):
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


joke_cite: List[Citation] = [
    Citation(
        volume=1,
        reporter="FLP",
        page=1,
        year=2021,
        extra="Eyecite is a collaborative community effort.",
    )
]
