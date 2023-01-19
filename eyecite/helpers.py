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
    YEAR_REGEX,
)
from eyecite.utils import strip_punct

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
    court_str = strip_punct(paren_string)

    court_code = None
    if court_str:
        # Map the string to a court, if possible.
        for court in courts:
            # Use startswith because citations are often missing final period,
            # e.g. "2d Cir"
            if court["citation_string"].startswith(court_str):
                court_code = court["id"]
                break

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
        return

    citation.full_span_end = citation.span()[1] + m.end()
    citation.metadata.pin_cite = clean_pin_cite(m["pin_cite"]) or None
    citation.metadata.extra = (m["extra"] or "").strip() or None
    citation.metadata.parenthetical = process_parenthetical(m["parenthetical"])
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
                ).strip()
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
        citation.metadata.defendant = "".join(
            str(w) for w in words[start_index : citation.index]
        ).strip(", ")


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
            text = text[:MAX_MATCH_CHARS]
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
