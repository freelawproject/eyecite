import logging
from bisect import bisect_right
from datetime import date
from typing import List, Optional, Tuple, cast

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


def find_case_name(citation: CaseCitation, document: Document, short=False):
    """Find case title in plain text

    This function attempts to improve the ability to gather case names,
    specifically plaintiff full names by using a few heuristics

    Stop at obvious words, characters or patterns. But also allow the pattern
    to continue when smart.
    Args:
        citation: Case citation
        document: Document object
        short: Is this a short case citation or not

    Returns: None
    """
    words = document.words
    back_seek = citation.index - BACKWARD_SEEK
    offset = 0
    v_token = None
    start_index = None
    candidate_case_name = None
    pre_cite_year = None
    title_starting_index = citation.index - 1
    case_name_length = 0
    plaintiff_length = 0
    for index in range(citation.index - 1, max(back_seek, -1), -1):
        word = words[index]
        word_str = str(word)
        offset += len(word)

        if word == ",":
            # Skip it
            continue
        case_name_length += 1
        if v_token is not None:
            if word_str.strip() != "":
                # Count the size of the plaintiff case name
                # this allows us to better establish when we are ending vs
                # going into a new sentence
                plaintiff_length += 1
        if isinstance(word, CitationToken):
            title_starting_index = index - 1
            continue
        if (
            word_str.endswith(";")
            or word_str.endswith("”")
            or word_str.endswith('"')
        ):
            start_index = index + 2
            candidate_case_name = "".join(
                str(w) for w in words[start_index:title_starting_index]
            )
            # Always break if a word ends with a semicolon, or quotes
            break
        if re.match(r"\(\d{4}\)", word_str):
            # Identify year before citation but after title
            title_starting_index = index - 1
            pre_cite_year = word_str[1:5]
            continue

        if word_str.startswith("(") and case_name_length > 2:
            start_index = index
            candidate_case_name = "".join(
                str(w) for w in words[start_index:title_starting_index]
            )
            # Break case name search if a word (not year) begins with a
            # parenthesis after the first word think (SHS) judge abbreviation
            break
        if (
            v_token is not None
            and not word_str[0].isupper()
            and word_str.strip()
            and word_str not in ["of", "the", "an", "and"]
        ):
            start_index = index + 2
            candidate_case_name = "".join(
                str(w) for w in words[start_index:title_starting_index]
            )
            candidate_case_name = re.sub(
                r"^(of|the|an|and)\s+",
                "",
                candidate_case_name,
            )

            break
        if isinstance(word, CitationToken) or isinstance(
            word, PlaceholderCitationToken
        ):
            title_starting_index = index - 1
            continue

        if isinstance(word, StopWordToken) and word.groups["stop_word"] == "v":
            v_token = word
            start_index = index - 2
            candidate_case_name = "".join(
                str(w) for w in words[start_index:title_starting_index]
            )
            # if we come across the v-token stop store the case name using
            # the word before the v to the end of the title
            # We will use this if we dont find a stop word later
            continue
        elif (
            v_token is not None
            and word_str[0].isupper()
            and len(word_str) > 4
            and word_str.endswith(".")
            and plaintiff_length > 1
        ):
            # I dont have a good solution here but it the sentence before the
            # citation ends in a capitalized word,
            # we should just bail if its longer than three characters
            # And its not the first word after the v.
            start_index = index + 2
            candidate_case_name = "".join(
                [str(w) for w in words[start_index:title_starting_index]]
            )
            break
        elif isinstance(word, StopWordToken):
            start_index = index + 2
            candidate_case_name = "".join(
                [str(w) for w in words[start_index:title_starting_index]]
            )
            # If we come across a stop word before or after a v token break
            break
        if (
            v_token is None
            and not word_str[0].isupper()
            and word_str.strip()
            and word_str[0].isalpha()
            and word_str not in ["of", "the", "an", "and"]
            and len(word_str) > 2
        ):
            start_index = index + 2
            candidate_case_name = "".join(
                str(w) for w in words[start_index:title_starting_index]
            )
            # If no v token has been found and a lower case word is found
            # break and use all upper case words found previously
            # ie. as `seen in Miranda, 1 U.S. 1 (1990)`
            break
        if index == 0:
            # If we finish running thru the list without breaking
            # we would still be identifying capitalized words without any
            # reason to break.  Use entire string for case title
            # But - lets be cautious and throw it away if it has numbers.
            # This is trying to balance between, someone parsing just a
            # single citation vs extracting from entire texts.
            # if we get to the end - ensure the last word is not lowercased
            candidate_case_name = "".join(
                [str(w) for w in words[index:title_starting_index]]
            )
            start_index = 0
            candidate_case_name = re.sub(
                r"^(of|the|an|and)",
                "",
                candidate_case_name,
                flags=re.IGNORECASE,
            )
            # if case name ends in numbers drop it.
            # possibly a citation
            if re.search(r"\b\d+\b$", candidate_case_name):
                candidate_case_name = None

    if candidate_case_name:
        if v_token:
            splits = re.split(r"\s+v\.?\s+", candidate_case_name, maxsplit=1)
            if len(splits) == 2:
                plaintiff, defendant = splits
            else:
                plaintiff, defendant = "", splits[0]
            citation.metadata.plaintiff = (
                plaintiff.strip(", ").strip().strip("(")
            )
        else:
            defendant = candidate_case_name

        defendant = strip_stop_words(defendant)

        clean_def = defendant.strip(", ").strip()
        if clean_def:
            if short is False and clean_def:
                citation.metadata.defendant = clean_def
            else:
                citation.metadata.antecedent_guess = (
                    defendant.strip(" ").strip(",").strip("(")
                )

            offset = (
                len(
                    "".join(
                        str(w) for w in words[start_index : citation.index - 1]
                    )
                )
                + 1
            )
            citation.full_span_start = citation.span()[0] - offset

        if pre_cite_year:
            # found pre citation year, store it
            citation.metadata.year = pre_cite_year
            citation.year = int(pre_cite_year)


def find_html_tags_at_position(
    document: Document, position: int
) -> List[Tuple[str, int, int]]:
    """Find emphasis tags at particular positions

    Args:
        position: the position to find in html
        document: the document object

    Returns: HTML tags if any
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
):
    """Add case name from HTML

    Args:
        citation ():
        document ():
        short ():

    Returns:

    """
    words = document.words
    back_seek = citation.index - BACKWARD_SEEK
    for index in range(citation.index - 1, max(back_seek, -1), -1):
        word = words[index]
        if short is True:
            # Identify the html tags immediately preceding a short citation
            if str(word).strip(", ") == "":
                continue

            offset = len(
                "".join([str(w) for w in words[index : citation.index]])
            )
            loc = words[citation.index].start - offset  # type: ignore

            results = find_html_tags_at_position(document, loc)
            if results:
                antecedent_guess, start = convert_html_to_plain_text_and_loc(
                    document, results
                )
                citation.metadata.antecedent_guess = strip_stop_words(
                    antecedent_guess
                )
                citation.full_span_start = start
            break

        if isinstance(word, StopWordToken) and word.groups["stop_word"] == "v":
            # Identify tags on either side of the v stop word token
            # and parse out plaintiff and defendant if separate or same tags
            left_shift = len(
                "".join([str(w) for w in words[index - 2 : index]])
            )
            loc = word.start - left_shift

            plaintiff_tags = find_html_tags_at_position(document, loc)
            right_shift = len(
                "".join([str(w) for w in words[index : index + 2]])
            )
            r_loc = word.start + right_shift
            defendant_tags = find_html_tags_at_position(document, r_loc)

            if len(plaintiff_tags) != 1 or len(defendant_tags) != 1:
                return None

            if plaintiff_tags == defendant_tags:
                case_name, start = convert_html_to_plain_text_and_loc(
                    document, plaintiff_tags
                )
                pattern = r"\s+vs?\.?\s+"
                splits = re.split(
                    pattern, case_name, maxsplit=1, flags=re.IGNORECASE
                )
                if len(splits) == 2:
                    plaintiff, defendant = splits
                else:
                    plaintiff, defendant = "", case_name

            else:
                plaintiff, start = convert_html_to_plain_text_and_loc(
                    document, plaintiff_tags
                )
                defendant, _ = convert_html_to_plain_text_and_loc(
                    document, defendant_tags
                )
            clean_plaintiff = strip_stop_words(plaintiff)

            citation.metadata.plaintiff = clean_plaintiff.strip().strip(",")
            citation.metadata.defendant = (
                strip_stop_words(defendant).strip().strip(",")
            )

            # Update full span start accordingly
            if len(clean_plaintiff) != len(plaintiff):
                shift = len(plaintiff) - len(clean_plaintiff)
                start += shift

            citation.full_span_start = start
            return

        elif isinstance(word, StopWordToken):
            # stopped at a stop word, work forward to possible title
            # this should be at least two words (including whitespace)
            # but with html could be more.
            # shift = index + 2
            shift = 3
            while True:
                if words[index + shift] == " ":
                    shift += 1
                else:
                    break
            right_offset = len(
                "".join([str(w) for w in words[index : index + shift]])
            )
            loc = word.start + right_offset - 1
            # find a character in the word
            filtered_tags = find_html_tags_at_position(document, loc)
            if len(filtered_tags) != 1:
                return None

            defendant, start = convert_html_to_plain_text_and_loc(
                document, filtered_tags
            )

            citation.metadata.defendant = strip_stop_words(defendant).strip(
                ", "
            )
            citation.full_span_start = start
            return


def strip_stop_words(text: str) -> str:
    """Strip stop words from the text

    Args:
        text (): the text to strip

    Returns: clean text

    """
    return re.sub(  # type: ignore
        STOP_WORD_REGEX,
        "",
        text.strip(", "),
        flags=re.IGNORECASE,
    )


def convert_html_to_plain_text_and_loc(
    document: Document, results: List[Tuple[str, int, int]]
) -> Tuple:
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
    return (case_name, start)


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
