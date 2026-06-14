from datetime import date

import regex as re

from eyecite.models import (
    CaseCitation,
    FullCaseCitation,
    FullJournalCitation,
    FullLawCitation,
)
from eyecite.regexes import (
    POST_FULL_CITATION_REGEX,
    POST_JOURNAL_CITATION_REGEX,
    POST_LAW_CITATION_REGEX,
    PRE_FULL_CITATION_REGEX,
    YEAR_REGEX,
)
from eyecite.court_matching import get_court_by_paren
from eyecite.token_matching import match_on_tokens


# Highest valid year is this year + 1 because courts in December sometimes
# cite a case to be published in January.
_highest_valid_year = date.today().year + 1


def get_year(word: str) -> int | None:
    """Given a matched year string, look for a year within a reasonable
    range."""
    try:
        year = int(word)
    except ValueError:
        return None

    if year < 1600 or year > _highest_valid_year:
        return None
    return year


def add_post_citation(citation: CaseCitation, words) -> None:
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
    ) and len(m["parenthetical"]) > len(citation.metadata.parenthetical):
        offset = len(m["parenthetical"]) - len(citation.metadata.parenthetical)
        citation.full_span_end = citation.full_span_end - offset
    citation.metadata.year = m["year"]
    citation.metadata.month = m["month"]
    citation.metadata.day = m["day"]
    if m["year"]:
        citation.year = get_year(m["year"])
    if m["court"]:
        citation.metadata.court = get_court_by_paren(m["court"])


def add_pre_citation(citation: FullCaseCitation, document) -> None:
    """Scan backwards to find a (PartyName - Pincite) component

    Do not try if plaintiff or defendant has already been found
    """
    if citation.metadata.plaintiff or citation.metadata.defendant:
        return

    m = match_on_tokens(
        document.words,
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


def add_law_metadata(citation: FullLawCitation, words) -> None:
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


def add_journal_metadata(citation: FullJournalCitation, words) -> None:
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


def clean_pin_cite(pin_cite: str | None) -> str | None:
    """Strip spaces and commas from pin_cite, if it is not None."""
    if pin_cite is None:
        return pin_cite
    return pin_cite.strip(", ")


def process_parenthetical(
    matched_parenthetical: str | None,
) -> str | None:
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
