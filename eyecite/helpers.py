import logging
from datetime import date
from typing import List, Optional, Tuple, cast

import regex as re
from courts_db import courts

from eyecite.models import (
    CaseCitation,
    CitationBase,
    CitationToken,
    FullCaseCitation,
    FullJournalCitation,
    FullLawCitation,
    ParagraphToken,
    ReferenceCitation,
    ResourceCitation,
    StopWordToken,
    Token,
    Tokens,
)
from eyecite.regexes import (
    POST_FULL_CITATION_REGEX,
    POST_JOURNAL_CITATION_REGEX,
    POST_LAW_CITATION_REGEX,
    POST_SHORT_CITATION_REGEX,
    PRE_FULL_CITATION_REGEX,
    YEAR_REGEX,
)

logger = logging.getLogger(__name__)

BACKWARD_SEEK = 28  # Median case name length in the CL db is 28 (2016-02-26)

# Maximum characters to scan using match_on_tokens.
# If this is higher we have to do a little more work for each match_on_tokens
# call to prepare the text to be matched.
MAX_MATCH_CHARS = 300


def get_court_by_paren(paren_string: str) -> Optional[str]:
    """Takes the citation string, usually something like "2d Cir", and maps
    that back to the court code.

    Does not work on SCOTUS, since that court lacks parentheticals, and
    needs to be handled after disambiguation has been completed.
    """

    # Remove whitespace and punctuation because citation strings sometimes lack
    # internal spaces, e.g. "Pa.Super." or "SC" (South Carolina)
    court_str = re.sub(r"[^\w]", "", paren_string).lower()

    court_code = None
    if court_str:
        for court in courts:
            s = re.sub(r"[^\w]", "", court["citation_string"]).lower()

            # Check for an exact match first
            if s == court_str:
                return str(court["id"])

            # If no exact match, try to record a startswith match for possible
            # eventual return
            if s.startswith(court_str):
                court_code = court["id"]

        return court_code

    return court_code


# Highest valid year is this year + 1 because courts in December sometimes
# cite a case to be published in January.
_highest_valid_year = date.today().year + 1


def get_year(word: str) -> Optional[int]:
    """Given a matched year string, look for a year within a reasonable
    range."""
    try:
        year = int(word)
    except ValueError:
        return None

    if year < 1600 or year > _highest_valid_year:
        return None
    return year


def cali_square_parens(citation, words):
    """Find california parentheticals

    They have a
    Args:
        citation ():
        words ():

    Returns:

    """
    remainder = words[citation.index - 1 :]
    offset = sum([len(str(word)) for word in words])
    text = "".join(
        ["CITE" if isinstance(w, CitationToken) else str(w) for w in remainder]
    )
    offset -= len(text)
    pattern = r"^\[CITE(?:, CITE)?\] [\[(](?P<parenthetical>[^\[\]]+)[\])].*"
    m = re.search(pattern, text[:300])
    if m:
        return m.groupdict().get("parenthetical"), m.end() + offset
    return None, None


def add_post_citation(citation: CaseCitation, words: Tokens) -> None:
    """Add to a citation object any additional information found after the base
    citation, including court, year, and possibly page range.

    See POST_CITATION_REGEX for examples.
    """
    m = match_on_tokens(
        words,
        citation.index + 1,
        POST_FULL_CITATION_REGEX,
    )

    if not m:

        parenthetical, span_end = cali_square_parens(citation, words)
        if parenthetical:
            citation.metadata.parenthetical = parenthetical
            citation.full_span_end = span_end
        return

    citation.full_span_end = citation.span()[1] + m.end()
    citation.metadata.pin_cite = clean_pin_cite(m["pin_cite"]) or None
    if m["pin_cite"]:
        citation.metadata.pin_cite_span_end = citation.span()[1] + len(
            m["pin_cite"]
        )

    citation.metadata.extra = (m["extra"] or "").strip() or None
    citation.metadata.parenthetical = process_parenthetical(m["parenthetical"])

    if (
        citation.full_span_end
        and m["parenthetical"] is not None
        and isinstance(citation.metadata.parenthetical, str)
    ):
        if len(m["parenthetical"]) > len(citation.metadata.parenthetical):
            offset = len(m["parenthetical"]) - len(
                citation.metadata.parenthetical
            )
            citation.full_span_end = citation.full_span_end - offset
    citation.metadata.year = m["year"]
    if m["year"]:
        citation.year = get_year(m["year"])
    if m["court"]:
        citation.metadata.court = get_court_by_paren(m["court"])


def add_defendant(citation: CaseCitation, words: Tokens) -> None:
    """Scan backwards from reporter until you find v., in re,
    etc. If no known stop-token is found, no defendant name is stored.  In the
    future, this could be improved.
    """
    # To turn word indexing into char indexing,
    # useful for span, account for shift
    offset = 0
    start_index = None
    back_seek = citation.index - BACKWARD_SEEK
    for index in range(citation.index - 1, max(back_seek, -1), -1):
        word = words[index]
        offset += len(word)
        if word == ",":
            # Skip it
            continue
        if isinstance(word, StopWordToken):
            if word.groups["stop_word"] == "v" and index > 0:
                citation.metadata.plaintiff = "".join(
                    str(w) for w in words[max(index - 2, 0) : index]
                ).strip("( ")
                offset += len(citation.metadata.plaintiff) + 1
            else:
                # We don't want to include stop words such as
                # 'citing' in the span
                offset -= len(word)

            start_index = index + 1
            break
        if word.endswith(";"):
            # String citation
            break
    if start_index:
        citation.full_span_start = citation.span()[0] - offset
        defendant = "".join(
            str(w) for w in words[start_index : citation.index]
        ).strip(", ()")
        if defendant.strip():
            citation.metadata.defendant = defendant


def add_pre_citation(citation: FullCaseCitation, words: Tokens) -> None:
    """Scan backwards to find a (PartyName - Pincite) component

    Do not try if plaintiff or defendant has already been found
    """
    if citation.metadata.plaintiff or citation.metadata.defendant:
        return

    m = match_on_tokens(
        words,
        citation.index - 1,
        PRE_FULL_CITATION_REGEX,
        forward=False,
        strings_only=True,
    )
    if not m:
        return

    if m["pin_cite"]:
        # if a pin cite occurs before the citation mark it down
        start, end = m.span()
        citation.metadata.pin_cite_span_start = citation.span()[0] - (
            end - start
        )

    citation.metadata.pin_cite = clean_pin_cite(m["pin_cite"]) or None
    citation.metadata.antecedent_guess = m["antecedent"]
    match_length = m.span()[1] - m.span()[0]
    citation.full_span_start = citation.span()[0] - match_length


def add_law_metadata(citation: FullLawCitation, words: Tokens) -> None:
    """Annotate FullLawCitation with pin_cite, publisher, etc."""
    m = match_on_tokens(
        words, citation.index + 1, POST_LAW_CITATION_REGEX, strings_only=True
    )
    if not m:
        return

    citation.full_span_end = citation.span()[1] + m.end()
    citation.metadata.pin_cite = clean_pin_cite(m["pin_cite"]) or None
    citation.metadata.publisher = m["publisher"]
    citation.metadata.day = m["day"]
    citation.metadata.month = m["month"]
    citation.metadata.parenthetical = process_parenthetical(m["parenthetical"])
    citation.metadata.year = m["year"]
    if m["year"]:
        citation.year = get_year(m["year"])


def add_journal_metadata(citation: FullJournalCitation, words: Tokens) -> None:
    """Annotate FullJournalCitation with pin_cite, year, etc."""
    m = match_on_tokens(
        words,
        citation.index + 1,
        POST_JOURNAL_CITATION_REGEX,
        strings_only=True,
    )
    if not m:
        return

    citation.full_span_end = citation.span()[1] + m.end()
    citation.metadata.pin_cite = clean_pin_cite(m["pin_cite"]) or None
    citation.metadata.parenthetical = process_parenthetical(m["parenthetical"])
    citation.metadata.year = m["year"]
    if m["year"]:
        citation.year = get_year(m["year"])


def clean_pin_cite(pin_cite: Optional[str]) -> Optional[str]:
    """Strip spaces and commas from pin_cite, if it is not None."""
    if pin_cite is None:
        return pin_cite
    return pin_cite.strip(", ")


def process_parenthetical(
    matched_parenthetical: Optional[str],
) -> Optional[str]:
    """Exclude any additional paren matched as well as year parentheticals

    For example: 'something) (something else)' will be trimmed down
    to 'something' but 'something (clarifying something) or other' will be
    kept in full.
    """
    if matched_parenthetical is None:
        return matched_parenthetical
    paren_balance = 0
    for i, char in enumerate(matched_parenthetical):
        if char == "(":  # Nested parenthetical
            paren_balance += 1
        elif char == ")":
            paren_balance -= 1
        if paren_balance < 0:  # End parenthetical reached
            return matched_parenthetical[:i] or None
    if re.match(YEAR_REGEX, matched_parenthetical, flags=re.X):
        return None
    return matched_parenthetical or None


def extract_pin_cite(
    words: Tokens, index: int, prefix: str = ""
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """Test whether text following token at index is a valid pin cite.
    Return pin cite text and number of extra characters matched.
    If prefix is provided, use that as the start of text to match.
    """
    from_token = cast(Token, words[index])
    m = match_on_tokens(
        words,
        index + 1,
        POST_SHORT_CITATION_REGEX,
        prefix=prefix,
        strings_only=True,
    )
    if m:
        if m["pin_cite"]:
            pin_cite = clean_pin_cite(m["pin_cite"])
            extra_chars = len(m["pin_cite"].rstrip(", "))
        else:
            pin_cite = None
            extra_chars = 0
        parenthetical = process_parenthetical(m["parenthetical"])
        return (
            pin_cite,
            from_token.end + extra_chars - len(prefix),
            parenthetical,
        )
    return None, None, None


def match_on_tokens(
    words,
    start_index,
    regex,
    prefix="",
    strings_only=False,
    forward=True,
    flags=re.X,
):
    """Scan forward or backward starting from the given index, up to max_chars.
    Return result of matching regex against token text.
    If prefix is provided, start from that text and then add token text.
    If strings_only is True, stop matching at any non-string token; otherwise
    stop matching only at paragraph tokens.
    """
    # Build text to match against, starting from prefix
    text = prefix

    # Get range of token indexes to append to text. Use indexes instead of
    # slice for performance to avoid copying list.
    if forward:
        indexes = range(min(start_index, len(words)), len(words))
        # If scanning forward, regex must match at start
        regex = rf"^(?:{regex})"
    else:
        indexes = range(max(start_index, -1), -1, -1)
        # If scanning backward, regex must match at end
        regex = rf"(?:{regex})$"

    # Append text of each token until we reach max_chars or a stop token:
    for index in indexes:
        token = words[index]

        # check for stop token
        if strings_only and not isinstance(token, str):
            break
        if isinstance(token, ParagraphToken):
            break

        # append or prepend text
        if forward:
            text += str(token)
        else:
            text = str(token) + text

        # check for max length
        if len(text) >= MAX_MATCH_CHARS:
            if forward:
                text = text[:MAX_MATCH_CHARS]
            else:
                text = text[-MAX_MATCH_CHARS:]
            break

    m = re.search(regex, text, flags=flags)
    # Useful for debugging regex failures:
    # print(f"Regex: {regex}")
    # print(f"Text: {repr(text)}")
    # print(f"Match: {m.groupdict() if m else None}")
    return m


def disambiguate_reporters(
    citations: List[CitationBase],
) -> List[CitationBase]:
    """Filter out citations where there is more than one possible reporter."""
    return [
        c
        for c in citations
        if not isinstance(c, ResourceCitation) or c.edition_guess
    ]


def overlapping_citations(
    full_span_1: Tuple[int, int], full_span_2: Tuple[int, int]
) -> bool:
    """Check if citations overlap at all"""
    start_1, end_1 = full_span_1
    start_2, end_2 = full_span_2
    return max(start_1, start_2) < min(end_1, end_2)


def filter_citations(citations: List[CitationBase]) -> List[CitationBase]:
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
    filtered_citations: List[CitationBase] = [sorted_citations[0]]

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


joke_cite: List[CitationBase] = [
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
