from bisect import bisect_right
from string import whitespace
from typing import Any

import regex as re

from eyecite.models import (
    CaseCitation,
    CitationToken,
    Document,
    PlaceholderCitationToken,
    StopWordToken,
    SupraToken,
)
from eyecite.regexes import STOP_WORD_REGEX

BACKWARD_SEEK = 28  # Median case name length in the CL db is 28 (2016-02-26)


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
            or word_str.endswith("\u201d")
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
        if isinstance(word, CitationToken | PlaceholderCitationToken):
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


def _is_lowercase_after_v_token(word_str: str, v_token: Any | None) -> bool:
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
    word_str: str, v_token: Any | None, plaintiff_length: int
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


def _is_lowercase_without_v_token(word_str: str, v_token: Any | None) -> bool:
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
) -> None:
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
) -> None:
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
    while index + shift < len(words) and words[index + shift] == " ":
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
