import re
from typing import Callable, Iterable, List, Optional, Union

from eyecite.helpers import (
    REPORTER_STRINGS,
    add_defendant,
    add_post_citation,
    disambiguate_reporters,
    is_neutral_tc_reporter,
    is_scotus_reporter,
    parse_page,
    remove_address_citations,
)
from eyecite.models import (
    Citation,
    FullCitation,
    IdCitation,
    NonopinionCitation,
    ShortformCitation,
    SupraCitation,
)
from eyecite.reporter_tokenizer import tokenize
from eyecite.utils import clean_text, strip_punct


def get_citations(
    text: str,
    do_post_citation: bool = True,
    do_defendant: bool = True,
    disambiguate: bool = True,
    clean: Iterable[Union[str, Callable[[str], str]]] = ("whitespace",),
) -> List[Union[NonopinionCitation, Citation]]:
    """Main function"""
    if clean:
        text = clean_text(text, clean)

    words = tokenize(text)
    citations: List[Union[Citation, NonopinionCitation]] = []

    for i in range(0, len(words) - 1):
        citation_token = words[i]
        citation: Union[Citation, NonopinionCitation, None] = None

        # CASE 1: Citation token is a reporter (e.g., "U. S.").
        # In this case, first try extracting it as a standard, full citation,
        # and if that fails try extracting it as a short form citation.
        if citation_token in REPORTER_STRINGS:
            citation = extract_full_citation(words, i)
            if citation:
                # CASE 1A: Standard citation found, try to add additional data
                if do_post_citation:
                    add_post_citation(citation, words)
                if do_defendant:
                    add_defendant(citation, words)
            else:
                # CASE 1B: Standard citation not found, so see if this
                # reference to a reporter is a short form citation instead
                citation = extract_shortform_citation(words, i)

                if not citation:
                    # Neither a full nor short form citation
                    continue

        # CASE 2: Citation token is an "Id." or "Ibid." reference.
        # In this case, the citation should simply be to the item cited
        # immediately prior, but for safety we will leave that resolution up
        # to the user.
        elif citation_token.lower() in {"id.", "id.,", "ibid."}:
            citation = extract_id_citation(words, i)

        # CASE 3: Citation token is a "supra" reference.
        # In this case, we're not sure yet what the citation's antecedent is.
        # It could be any of the previous citations above. Thus, like an Id.
        # citation, for safety we won't resolve this reference yet.
        elif re.match(r"[^a-z0-9]*supra[^a-z0-9]*$", citation_token.lower()):
            citation = extract_supra_citation(words, i)

        # CASE 4: Citation token is a section marker.
        # In this case, it's likely that this is a reference to a non-
        # opinion document. So we record this marker in order to keep
        # an accurate list of the possible antecedents for id citations.
        elif "§" in citation_token:
            citation = NonopinionCitation(match_token=citation_token)

        # CASE 5: The token is not a citation.
        else:
            continue

        if citation is not None:
            citations.append(citation)

    # Disambiguate each citation's reporter
    if disambiguate:
        citations = disambiguate_reporters(citations)

    citations = remove_address_citations(citations)

    # Set each citation's court property to "scotus" by default
    for citation in citations:
        if (
            isinstance(citation, Citation)
            and not citation.court
            and is_scotus_reporter(citation)
        ):
            citation.court = "scotus"

    # Returns a list of citations ordered in the sequence that they appear in
    # the document. The ordering of this list is important for reconstructing
    # the references of the ShortformCitation, SupraCitation, and
    # IdCitation objects.
    return citations


def extract_full_citation(
    words: List[str],
    reporter_index: int,
) -> Optional[FullCitation]:
    """Given a list of words and the index of a federal reporter, look before
    and after for volume and page. If found, construct and return a
    FullCitation object.

    Example: Adarand Constructors, Inc. v. Peña, 515 U.S. 200, 240

    If we are given neutral, tax court opinions we treat them differently.
    The formats often follow {REPORTER} {YEAR}-{ITERATIVE_NUMBER}
    ex. T.C. Memo. 2019-13
    """
    # Get reporter
    reporter = words[reporter_index]

    # Variables to extact
    volume: Union[int, str, None]
    page: Union[int, str, None]

    # Handle tax citations
    is_tax_citation = is_neutral_tc_reporter(reporter)
    if is_tax_citation:
        volume, page = words[reporter_index + 1].replace("–", "-").split("-")

    # Handle "normal" citations, e.g., XX F.2d YY
    else:
        # Don't check if we are at the beginning of a string
        if reporter_index == 0:
            return None
        volume = strip_punct(words[reporter_index - 1])
        page = strip_punct(words[reporter_index + 1])

    # Get volume
    if volume.isdigit():
        volume = int(volume)
    else:
        # No volume, therefore not a valid citation
        return None

    # Get page
    page = parse_page(page)
    if not page:
        return None

    # Return FullCitation
    return FullCitation(
        reporter,
        page,
        volume,
        reporter_found=reporter,
        reporter_index=reporter_index,
    )


def extract_shortform_citation(
    words: List[str],
    reporter_index: int,
) -> Optional[ShortformCitation]:
    """Given a list of words and the index of a federal reporter, look before
    and after to see if this is a short form citation. If found, construct
    and return a ShortformCitation object.

    Shortform 1: Adarand, 515 U.S., at 241
    Shortform 2: 515 U.S., at 241
    """
    # Don't check if we are at the beginning of a string
    if reporter_index <= 2:
        return None

    # Variables to extact
    volume: Union[int, str, None]
    page: Union[int, str, None]
    antecedent_guess: str

    # Get volume
    volume = strip_punct(words[reporter_index - 1])
    if volume.isdigit():
        volume = int(volume)
    else:
        # No volume, therefore not a valid citation
        return None

    # Get page
    try:
        page = parse_page(words[reporter_index + 2])
        if not page:
            # There might be a comma in the way, so try one more index
            page = parse_page(words[reporter_index + 3])
            if not page:
                # No page, therefore not a valid citation
                return None
    except IndexError:
        return None

    # Get antecedent
    antecedent_guess = words[reporter_index - 2]
    if antecedent_guess == ",":
        antecedent_guess = words[reporter_index - 3] + ","

    # Get reporter
    reporter = words[reporter_index]

    # Return ShortformCitation
    return ShortformCitation(
        reporter,
        page,
        volume,
        antecedent_guess,
        reporter_found=reporter,
        reporter_index=reporter_index,
    )


def extract_supra_citation(
    words: List[str],
    supra_index: int,
) -> Optional[SupraCitation]:
    """Given a list of words and the index of a supra token, look before
    and after to see if this is a supra citation. If found, construct
    and return a SupraCitation object.

    Supra 1: Adarand, supra, at 240
    Supra 2: Adarand, 515 supra, at 240
    Supra 3: Adarand, supra, somethingelse
    Supra 4: Adrand, supra. somethingelse
    """
    # Don't check if we are at the beginning of a string
    if supra_index <= 1:
        return None

    # Get volume
    volume = None

    # Get page
    try:
        page = parse_page(words[supra_index + 2])
    except IndexError:
        page = None

    # Get antecedent
    antecedent_guess = words[supra_index - 1]
    if antecedent_guess.isdigit():
        volume = int(antecedent_guess)
        antecedent_guess = words[supra_index - 2]
    elif antecedent_guess == ",":
        antecedent_guess = words[supra_index - 2] + ","

    # Return SupraCitation
    return SupraCitation(antecedent_guess, page=page, volume=volume)


def extract_id_citation(
    words: List[str],
    id_index: int,
) -> Optional[IdCitation]:
    """Given a list of words and the index of an id token, gather the
    immediately succeeding tokens to construct and return an IdCitation
    object.
    """
    # Keep track of whether a page is detected or not
    has_page = False

    # List of literals that could come after an id token
    id_reference_token_literals = set(
        ["at", "p.", "p", "pp.", "p", "@", "pg", "pg.", "¶", "¶¶"]
    )

    # Helper function to see whether a token qualifies as a page candidate
    def is_page_candidate(token):
        return token in id_reference_token_literals or parse_page(token)

    # Check if the post-id token is indeed a page candidate
    if is_page_candidate(words[id_index + 1]):
        # If it is, set the scan_index appropriately
        scan_index = id_index + 2
        has_page = True

        # Also, keep trying to scan for more pages
        while is_page_candidate(words[scan_index]):
            scan_index += 1

    # If it is not, simply set a naive anchor for the end of the scan_index
    else:
        has_page = False
        scan_index = id_index + 4

    # Only linkify the after tokens if a page is found
    return IdCitation(
        id_token=words[id_index],
        after_tokens=words[id_index + 1 : scan_index],
        has_page=has_page,
    )
