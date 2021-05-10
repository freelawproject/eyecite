from datetime import date
from typing import List, Optional, Tuple, cast

import regex as re
from courts_db import courts

from eyecite.models import (
    CaseCitation,
    CitationBase,
    ParagraphToken,
    StopWordToken,
    Token,
    Tokens,
)
from eyecite.utils import strip_punct

# *** Metadata regexes: ***
# Regexes used to scan forward or backward from a citation token. NOTE:
# * Regexes are written in verbose mode. Intentional spaces must be escaped.
# * In many regexes order matters: options separated by "|" are
#   tested left to right, so more specific (typically longer) have to come
#   before less specific.

# Pin cite regex:
# A pin cite is the part of a citation used to specify a particular section of
# the referenced document. These may have prefixes, may include paragraph,
# page, or line references, and may have multiple ranges specified.
# For some examples see
# https://github.com/freelawproject/courtlistener/issues/1344#issuecomment-662994948
PIN_CITE_TOKEN_REGEX = r"""
    # optional label (longest to shortest):
    (?:
        (?:
            (?:&\ )?note|       # note, & note
            (?:&\ )?nn?\.?|     # n., nn., & nn.
            (?:&\ )?fn?\.?|     # fn., & fn.
            ¶{1,2}|             # ¶
            §{1,2}|             # §
            \*{1,4}|            # *
            pg\.?|              # pg.
            pp?\.?              # p., pp.
        )\ ?  # optional space after label
    )?
    (?:
        # page:paragraph cite, like 123:24-25 or 123:24-124:25:
        \d+:\d+(?:-\d+(?::\d+)?)?|
        # page range, like 12 or 12-13:
        \d+(?:-\d+)?
    )
"""
PIN_CITE_REGEX = rf"""
    \ ?(?P<pin_cite>
        (?:at\ )?
        {PIN_CITE_TOKEN_REGEX},?
        (?:\ {PIN_CITE_TOKEN_REGEX},?)*
    )
"""


# Short cite antecedent regex:
# What case does a short cite refer to? For now, we just capture the previous
# word optionally followed by a comma. Example: Adarand, 515 U.S. at 241.
SHORT_CITE_ANTECEDENT_REGEX = r"""
    (?P<antecedent>[\w\-.]+),?
    \   # final space
"""


# Supra cite antecedent regex:
# What case does a short cite refer to? For now, we just capture the previous
# word optionally followed by a comma. Example: Adarand, supra.
# If the previous word is a digit, we capture both that (to store as a volume)
# and the word before it (to store as antecedent).
SUPRA_ANTECEDENT_REGEX = r"""
    (?:
        (?P<antecedent>[\w\-.]+),?\ (?P<volume>\d+)|
        (?P<volume>\d+)|
        (?P<antecedent>[\w\-.]+),?
    )
    \   # final space
"""


# Post citation regex:
# Capture metadata after a full cite. For example given the citation "1 U.S. 1"
# with the following text:
#   1 U.S. 1, 4-5, 2 S. Ct. 2, 6-7 (4th Cir. 2012) (overruling foo)
# we want to capture:
#   pin_cite = 4-5
#   extra = 2 S. Ct. 2, 6-7
#   court = 4th Cir.
#   year = 2012
#   parenthetical = overruling foo
POST_CITATION_REGEX = rf"""
    (?:  # handle a full cite with a valid year paren:
        # content before year paren:
        (?:
            # pin cite with comma and extra:
            ,{PIN_CITE_REGEX},\ (?P<extra>[^(]+)|
            # just pin cite:
            ,{PIN_CITE_REGEX}\ |
            # just extra
            (?P<extra>[^(]*)
        )
        # content within year paren:
        \((?:
            # court and year:
            (?P<court>[^)]+)\ (?P<year>\d{{4}})|
            # just year:
            (?P<year>\d{{4}})
        )\)
        # optional parenthetical comment:
        (?:\ \((?P<parenthetical>[^)]+)\))?
    |  # handle a pin cite with no valid year paren:
        ,{PIN_CITE_REGEX}(?:,|\.|\ \()
    )
"""

BACKWARD_SEEK = 28  # Median case name length in the CL db is 28 (2016-02-26)


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
        words, citation.index + 1, POST_CITATION_REGEX, max_chars=150
    )
    if not m:
        return

    citation.pin_cite = m["pin_cite"]
    citation.extra = (m["extra"] or "").strip() or None
    citation.parenthetical = m["parenthetical"]
    if m["year"]:
        citation.year = get_year(m["year"])
    if m["court"]:
        citation.court = get_court_by_paren(m["court"])


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
            if word.stop_word == "v" and index > 0:
                citation.plaintiff = "".join(
                    str(w) for w in words[max(index - 2, 0) : index]
                ).strip()
            start_index = index + 1
            break
        if word.endswith(";"):
            # String citation
            break
    if start_index:
        citation.defendant = "".join(
            str(w) for w in words[start_index : citation.index]
        ).strip()


def extract_pin_cite(
    words: Tokens, index: int, prefix: str = ""
) -> Tuple[Optional[str], Optional[int]]:
    """Test whether text following token at index is a valid pin cite.
    Return pin cite text and number of extra characters matched.
    If prefix is provided, use that as the start of text to match.
    """
    from_token = cast(Token, words[index])
    m = match_on_tokens(
        words, index + 1, PIN_CITE_REGEX, prefix=prefix, strings_only=True
    )
    if m:
        pin_cite = m["pin_cite"]
        extra_chars = m.span(1)[1]
        return pin_cite, from_token.end + extra_chars - len(prefix)
    return None, None


def match_on_tokens(
    words,
    start_index,
    regex,
    prefix="",
    max_chars=100,
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
        if len(text) >= max_chars:
            text = text[:max_chars]
            break

    m = re.search(regex, text, flags=flags)
    # Useful for debugging regex failures:
    # print(
    #     f"Regex: {regex}\nText: {text}\nMatch: {m.groups() if m else None}"
    # )
    return m


def disambiguate_reporters(
    citations: List[CitationBase],
) -> List[CitationBase]:
    """Filter out citations where there is more than one possible reporter."""
    return [
        c
        for c in citations
        if not isinstance(c, CaseCitation) or c.edition_guess
    ]


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
