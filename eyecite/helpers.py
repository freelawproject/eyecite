import logging
from bisect import bisect_right
from datetime import date
from string import whitespace
from typing import Any, Optional, cast

import regex as re
from courts_db import courts

from eyecite.models import (
    CaseCitation,
    CitationBase,
    CitationToken,
    Document,
    FullCaseCitation,
    FullJournalCitation,
    FullLawCitation,
    ParagraphToken,
    PlaceholderCitationToken,
    ReferenceCitation,
    ResourceCitation,
    ShortCaseCitation,
    StopWordToken,
    SupraCitation,
    SupraToken,
    Token,
    Tokens,
)
from eyecite.regexes import (
    POST_FULL_CITATION_REGEX,
    POST_JOURNAL_CITATION_REGEX,
    POST_LAW_CITATION_REGEX,
    POST_SHORT_CITATION_REGEX,
    PRE_FULL_CITATION_REGEX,
    STOP_WORD_REGEX,
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


def find_case_name(
    citation: CaseCitation, document: Document, short: bool = False
) -> None:
    """Find case title in plain text

    This function attempts to improve the ability to gather case names,
    specifically plaintiff full names by using a few heuristics.

    It stops at obvious words, chars or patterns, but also allows the pattern
    to continue when appropriate.

    Args:
        citation: Case citation
        document: Document object
        short: Is this a short case citation or not

    Returns: None - updates the citation object in place
    """
    # Initialize search variables
    search_state = _initialize_search_state(citation)

    # Phase 1: Scan backward to find case name boundaries
    search_state = _scan_for_case_boundaries(document, citation, search_state)

    # Phase 2: Process found case name if any
    if search_state["candidate_case_name"]:
        _process_case_name(citation, document, search_state, short)


def _initialize_search_state(citation: CaseCitation) -> dict[str, Any]:
    """Initialize the state dictionary for case name search."""
    return {
        "offset": 0,
        "v_token": None,
        "start_index": None,
        "candidate_case_name": None,
        "pre_cite_year": None,
        "title_starting_index": citation.index - 1,
        "case_name_length": 0,
        "plaintiff_length": 0,
    }


def _scan_for_case_boundaries(
    document: Document, citation: CaseCitation, state: dict[str, Any]
) -> dict[str, Any]:
    """Scan backward from citation to find case name boundaries.

    Args:
        document (): Document object
        citation (): Citation object
        state (): Associated search metadata

    Returns: search state to process the information
    """
    words = document.words
    back_seek = citation.index - BACKWARD_SEEK

    for index in range(citation.index - 1, max(back_seek, -1), -1):
        word = words[index]
        word_str = str(word)
        state["offset"] += len(word)

        # Skip commas
        if word == ",":
            continue

        state["case_name_length"] += 1

        # Track plaintiff name length if we've already found a "v" token
        if state["v_token"] is not None and word_str.strip() != "":
            state["plaintiff_length"] += 1

        # Handle citation tokens - just adjust the title boundary
        if isinstance(word, CitationToken):
            state["title_starting_index"] = index - 1
            continue

        # Break on terminal punctuation
        if (
            word_str.endswith(";")
            or word_str.endswith("”")
            or word_str.endswith('"')
        ):
            state["start_index"] = index + 2
            state["candidate_case_name"] = _extract_text(
                words, state["start_index"], state["title_starting_index"]
            )
            break

        # Handle year before citation
        if re.match(r"\(\d{4}\)", word_str):
            state["title_starting_index"] = index - 1
            state["pre_cite_year"] = word_str[1:5]
            continue

        # Break on opening parenthesis after first word
        if word_str.startswith("(") and state["case_name_length"] > 3:
            state["start_index"] = index
            if (
                word_str == "("
                or word_str[1].isalpha()
                and word_str[1].islower()
            ):
                state["start_index"] = index + 2

            state["candidate_case_name"] = _extract_text(
                words, state["start_index"], state["title_starting_index"]
            )
            break

        # Break on lowercase word after "v" token
        if _is_lowercase_after_v_token(word_str, state["v_token"]):
            state["start_index"] = index + 2
            state["candidate_case_name"] = _extract_text(
                words, state["start_index"], state["title_starting_index"]
            )
            state["candidate_case_name"] = re.sub(
                r"^(of|the|an|and)\s+", "", state["candidate_case_name"]
            )
            break

        # Skip placeholder citations
        if isinstance(word, (CitationToken, PlaceholderCitationToken)):
            state["title_starting_index"] = index - 1
            continue

        # Handle "v" token - store it but don't break yet
        if _is_v_token(word):
            state["v_token"] = word
            state["start_index"] = index - 2
            state["candidate_case_name"] = _extract_text(
                words, state["start_index"], state["title_starting_index"]
            )
            continue

        # Break on likely new sentence after "v" token
        elif _is_capitalized_abbreviation(
            word_str, state["v_token"], state["plaintiff_length"]
        ) or isinstance(word, StopWordToken):
            state["start_index"] = index + 2
            state["candidate_case_name"] = _extract_text(
                words, state["start_index"], state["title_starting_index"]
            )
            break

        # Break on lowercase word w/o "v" token - start with capitalized words
        if _is_lowercase_without_v_token(word_str, state["v_token"]):
            if word_str in ["ex", "rel."]:
                # ignore common lower cased
                continue
            if isinstance(word, SupraToken):
                # supra usually is preceded by a case name so do not
                # break on supra but also do not capture in title
                state["title_starting_index"] = index - 1
                continue
            state["start_index"] = index + 2
            state["candidate_case_name"] = _extract_text(
                words, state["start_index"], state["title_starting_index"]
            )

            # Extract just the capitalized word if possible
            match = re.search(
                r"\b([A-Z][a-zA-Z0-9]*)\b.*", state["candidate_case_name"]
            )
            if match:
                state["candidate_case_name"] = state["candidate_case_name"][
                    match.start() :
                ]
            else:
                state["candidate_case_name"] = None
            break

        # Handle reaching start of text
        if index == 0:
            state["candidate_case_name"] = _extract_text(
                words, index, state["title_starting_index"]
            )
            state["start_index"] = 0
            state["candidate_case_name"] = re.sub(
                r"^(of|the|an|and)\b",
                "",
                state["candidate_case_name"],
                flags=re.IGNORECASE,
            )

            # Drop if case name ends in numbers (likely a citation)
            if re.search(r"\b\d+\b$", state["candidate_case_name"]):
                state["candidate_case_name"] = None

    return state


def _process_case_name(
    citation: CaseCitation,
    document: Document,
    state: dict[str, Any],
    short: bool,
) -> None:
    """Process the found case name and update the citation object.

    Analyzes the candidate case name to extract plaintiff and defendant info,
    cleans the extracted names by removing stop words, and updates the citation
    metadata with the results. Also calculates the full span of the citation
    including the case name.

    Args:
        citation: Citation object to update with extracted case name components
        document: Document containing the text being analyzed
        state: Dictionary with search state including candidate_case_name and
               boundary indices
        short: Whether this is a short-form citation (affects how the names
               are stored in metadata)

    Returns:
        None
    """
    words = document.words
    candidate_case_name = state["candidate_case_name"]

    # Extract plaintiff and defendant if we have a "v" token
    if state["v_token"]:
        splits = re.split(r"\s+v\.?\s+", candidate_case_name, maxsplit=1)
        if len(splits) == 2:
            plaintiff, defendant = splits
        else:
            plaintiff, defendant = "", splits[0]
        plaintiff = plaintiff.strip(f"{whitespace},(")
        clean_plaintiff = re.sub(r"\b[a-z]\w*\b", "", plaintiff)
        plaintiff = strip_stop_words(clean_plaintiff)
        citation.metadata.plaintiff = plaintiff
    else:
        defendant = candidate_case_name

    # Clean up defendant name
    clean_def = strip_stop_words(defendant)

    if clean_def:
        # Store defendant or antecedent based on citation type
        if short is False:
            citation.metadata.defendant = clean_def
        else:
            antecedent_guess = strip_stop_words(defendant)
            citation.metadata.antecedent_guess = antecedent_guess

        # Calculate full span start
        offset = (
            len(
                "".join(
                    str(w)
                    for w in words[state["start_index"] : citation.index - 1]
                )
            )
            + 1
        )
        citation.full_span_start = citation.span()[0] - offset

    # Store year if found
    if state["pre_cite_year"]:
        citation.metadata.year = state["pre_cite_year"]
        citation.year = int(state["pre_cite_year"])


# Helper functions to improve readability


def _extract_text(words: list[Any], start: int, end: int) -> str:
    """Extract text from words list between start and end indices."""
    return "".join(str(w) for w in words[start:end])


def _is_v_token(word: Any) -> bool:
    """Check if word is the 'v' stop word token."""
    return isinstance(word, StopWordToken) and word.groups["stop_word"] == "v"


def _is_lowercase_after_v_token(word_str: str, v_token: Optional[Any]) -> bool:
    """Check if we should break at lowercase word after v token.

    Determines if the current word should cause a break in case name
    parsing because it's a lowercase word after the versus token.

    Args:
        word_str: String representation of the current word
        v_token: The versus token if one has been found

    Returns:
        True if should break, False otherwise
    """
    return (
        v_token is not None
        and not word_str[0].isupper()
        and bool(word_str.strip())
        and word_str not in ["of", "the", "an", "and"]
    )


def _is_capitalized_abbreviation(
    word_str: str, v_token: Optional[Any], plaintiff_length: int
) -> bool:
    """Check if we found a likely abbreviation after 'v' token.

    Determines if the current word is likely an abbreviation or end of
    sentence that should cause a break in parsing.

    Args:
        word_str: String representation of the current word
        v_token: The versus token if one has been found
        plaintiff_length: Number of plaintiff words found so far

    Returns:
        True if should break, False otherwise
    """
    return (
        v_token is not None
        and word_str[0].isupper()
        and len(word_str) > 4
        and word_str.endswith(".")
        and plaintiff_length > 1
    )


def _is_lowercase_without_v_token(
    word_str: str, v_token: Optional[Any]
) -> bool:
    """Check if we should break at lowercase word with no v token.

    Determines if the current word should cause a break in case name
    parsing because it's a lowercase word and no versus token has been found.

    Args:
        word_str: String representation of the current word
        v_token: The versus token if one has been found

    Returns:
        True if should break, False otherwise
    """

    return (
        v_token is None
        and not word_str[0].isupper()
        and bool(word_str.strip())
        and word_str[0].isalpha()
        and word_str not in ["of", "the", "an", "and"]
    )


def find_html_tags_at_position(
    document: Document, position: int
) -> list[tuple[str, int, int]]:
    """Find emphasis tags at particular positions in HTML document.

    Locates HTML emphasis tags that contain the specified position.

    Args:
        document: Document object containing HTML markup
        position: Character position to find tags at

    Returns:
        List of tuples containing (tag_name, start_pos, end_pos)
        Empty list if no matching tags found
    """
    markup_loc = document.plain_to_markup.update(  # type: ignore
        position,
        bisect_right,
    )
    tags = [r for r in document.emphasis_tags if r[1] <= markup_loc < r[2]]
    if len(tags) != 1:
        return []
    return tags


def find_case_name_in_html(
    citation: CaseCitation, document: Document, short: bool = False
) -> None:
    """Extract case name info from HTML document and update citation metadata.

    This function analyzes the document around a citation to find and extract
    plaintiff/defendant information or antecedent text from HTML elements.

    Args:
        citation: The citation object to update with case name information
        document: The HTML document containing the citation
        short: Whether this is a short-form citation

    Returns:
        None - updates citation object in place, or None if no case name found
    """
    words = document.words
    back_seek = max(citation.index - BACKWARD_SEEK, 0)

    # Handle short citations differently
    if short:
        _extract_short_citation_name(citation, words, document)
        return

    # For regular citations, search backward for the 'v' stop word
    for index in range(citation.index - 1, back_seek - 1, -1):
        word = words[index]

        if _is_whitespace_word(word):
            continue

        if _is_versus_token(word):
            _extract_plaintiff_defendant_from_versus(
                citation, document, words, index, word
            )
            return

        elif isinstance(word, StopWordToken):
            _extract_defendant_after_stopword(
                citation, document, words, index, word
            )
            return

    # If we get here, we couldn't find case name information
    return None


def _is_whitespace_word(word: Any) -> bool:
    """Check if a word is just whitespace.

    Determines if a word consists only of whitespace characters
    or commas.

    Args:
        word: Word token to check

    Returns:
        True if the word is empty after stripping, False otherwise
    """
    return str(word).strip(", ") == ""


def _is_versus_token(word: Any) -> bool:
    """Check if word is the 'v' or 'vs' stop word token.

    Args:
        word: Word token to check
    Returns:
        True if the word is a versus token, False otherwise
    """
    return (
        isinstance(word, StopWordToken) and word.groups.get("stop_word") == "v"
    )


def _extract_short_citation_name(
    citation: CaseCitation, words: list[Any], document: Document
) -> None:
    """Extract case name for short-form citation.

    Args:
        citation: Citation object to update
        words: List of words in the document
        document: Document containing the citation
    """
    # Find first non-whitespace word preceding citation
    for index in range(
        citation.index - 1, max(citation.index - BACKWARD_SEEK, 0) - 1, -1
    ):
        word = words[index]
        if _is_whitespace_word(word):
            continue

        # Calculate position for finding HTML tags
        offset = len("".join([str(w) for w in words[index : citation.index]]))
        loc = words[citation.index].start - offset

        # Find and process HTML tags
        results = find_html_tags_at_position(document, loc)
        if results:
            antecedent_guess, start, end = convert_html_to_plain_text_and_loc(
                document, results
            )

            # Check for overlapping bad html
            cite_start, _ = citation.span()
            if end > cite_start:
                antecedent_guess = antecedent_guess[: cite_start - end]

            # Update citation metadata
            citation.metadata.antecedent_guess = strip_stop_words(
                antecedent_guess
            )
            citation.full_span_start = start
        break


def _extract_plaintiff_defendant_from_versus(
    citation: CaseCitation,
    document: Document,
    words: list[Any],
    index: int,
    versus_token: Any,
) -> Optional[None]:
    """Extract plaintiff and defendant from text around 'v' token.

    Args:
        citation: Citation object to update
        document: Document containing the citation
        words: List of words in the document
        index: Index of the 'v' token
        versus_token: The 'v' token itself
    """
    # Find positions to check for HTML tags
    left_shift = len("".join([str(w) for w in words[index - 2 : index]]))
    plaintiff_pos = versus_token.start - left_shift

    right_shift = len("".join([str(w) for w in words[index : index + 2]]))
    defendant_pos = versus_token.start + right_shift

    # Get HTML tags at positions
    plaintiff_tags = find_html_tags_at_position(document, plaintiff_pos)
    defendant_tags = find_html_tags_at_position(document, defendant_pos)

    if len(plaintiff_tags) != 1 or len(defendant_tags) != 1:
        return None

    # Extract plaintiff and defendant based on HTML structure
    if plaintiff_tags == defendant_tags:
        _extract_from_single_html_element(citation, document, plaintiff_tags)
    else:
        _extract_from_separate_html_elements(
            citation, document, plaintiff_tags, defendant_tags
        )


def _extract_from_single_html_element(
    citation: CaseCitation,
    document: Document,
    tags: list[tuple[str, int, int]],
) -> None:
    """Extract plaintiff and defendant from a single HTML element.

    When plaintiff and defendant are in the same HTML element,
    this function splits the text to extract both names.

    Args:
        citation: Citation object to update
        document: Document containing the citation
        tags: HTML tags containing the case name

    Returns:
        None - updates citation object in place
    """
    case_name, start, end = convert_html_to_plain_text_and_loc(document, tags)

    # Split on 'v' or 'vs'
    pattern = r"\s+vs?\.?\s+"
    splits = re.split(pattern, case_name, maxsplit=1, flags=re.IGNORECASE)

    if len(splits) == 2:
        plaintiff, defendant = splits
    else:
        plaintiff, defendant = "", case_name

    # Clean and update citation
    clean_plaintiff = strip_stop_words(plaintiff)
    citation.metadata.plaintiff = clean_plaintiff.strip().strip(",").strip("(")
    citation.metadata.defendant = (
        strip_stop_words(defendant).strip().strip(",")
    )

    # Adjust span start if needed
    if len(clean_plaintiff) != len(plaintiff):
        shift = len(plaintiff) - len(clean_plaintiff)
        start += shift

    citation.full_span_start = start


def _extract_from_separate_html_elements(
    citation: CaseCitation,
    document: Document,
    plaintiff_tags: list[tuple[str, int, int]],
    defendant_tags: list[tuple[str, int, int]],
) -> None:
    """Extract plaintiff and defendant from separate HTML elements.

    When plaintiff and defendant are in different HTML elements,
    this function extracts both names from their respective elements.

    Args:
        citation: Citation object to update
        document: Document containing the citation
        plaintiff_tags: HTML tags containing the plaintiff name
        defendant_tags: HTML tags containing the defendant name

    Returns:
        None - updates citation object in place
    """
    plaintiff, start, end = convert_html_to_plain_text_and_loc(
        document, plaintiff_tags
    )
    defendant, _, _ = convert_html_to_plain_text_and_loc(
        document, defendant_tags
    )

    # Clean and update citation
    clean_plaintiff = strip_stop_words(plaintiff)
    citation.metadata.plaintiff = clean_plaintiff.strip().strip(",").strip("(")
    citation.metadata.defendant = (
        strip_stop_words(defendant).strip().strip(",")
    )

    # Adjust span start if needed
    if len(clean_plaintiff) != len(plaintiff):
        shift = len(plaintiff) - len(clean_plaintiff)
        start += shift

    citation.full_span_start = start


def _extract_defendant_after_stopword(
    citation: CaseCitation,
    document: Document,
    words: list[Any],
    index: int,
    word: Any,
) -> Optional[None]:
    """Extract defendant name after a stop word.

    For cases where a stop word (other than 'v') precedes the defendant name,
    extracts just the defendant name from HTML.

    Args:
        citation: Citation object to update
        document: Document containing the citation
        words: List of words in the document
        index: Index of the stop word
        word: The stop word token

    Returns:
        None - updates citation object in place, or None if extraction fails
    """
    shift = 3
    while words[index + shift] == " ":
        shift += 1

    right_offset = len("".join([str(w) for w in words[index : index + shift]]))
    loc = word.start + right_offset - 1

    # Find HTML tags at position
    filtered_tags = find_html_tags_at_position(document, loc)
    if len(filtered_tags) != 1:
        return None

    # Extract defendant name
    defendant, start, end = convert_html_to_plain_text_and_loc(
        document, filtered_tags
    )

    # Trim if needed
    cite_start, _ = citation.span()
    if end > cite_start:
        defendant = defendant[: cite_start - end]

    # Update citation
    citation.metadata.defendant = strip_stop_words(defendant).strip(", ")
    citation.full_span_start = start


def strip_stop_words(text: str) -> str:
    """Strip stop words from the text.

    Removes common legal stop words and phrases from the
    beginning of text to clean up case names.

    Args:
        text: The text to clean

    Returns:
        Cleaned text with stop words removed
    """
    cleaned = re.sub(STOP_WORD_REGEX, " ", text)
    text = re.sub(r"^(?i)In\s+", "", cleaned).strip()
    text = text.lstrip("(").rstrip(")")
    if ";" in text:
        text = text.split(";")[1]
    return (
        re.sub(  # type: ignore
            STOP_WORD_REGEX,
            "",
            text.strip(", "),
            flags=re.IGNORECASE,
        )
        .strip(", ")
        .strip()
    ) or ""


def convert_html_to_plain_text_and_loc(
    document: Document, results: list[tuple[str, int, int]]
) -> tuple:
    """A helper function to convert emphasis tags to plain text and location

    Args:
        document (): The document to process
        results (): The empahsis tags

    Returns: The text of the plain text and the location it starts
    """
    markup_location = results[0]

    start = document.markup_to_plain.update(  # type: ignore
        markup_location[1],
        bisect_right,
    )
    end = document.markup_to_plain.update(  # type: ignore
        markup_location[2],
        bisect_right,
    )
    case_name = document.plain_text[start:end]
    return (case_name, start, end)


def add_pre_citation(citation: FullCaseCitation, document: Document) -> None:
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
) -> tuple[Optional[str], Optional[int], Optional[str]]:
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
