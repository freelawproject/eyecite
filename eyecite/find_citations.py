from typing import Iterable, List, Optional, cast

from eyecite.helpers import (
    add_defendant,
    add_post_citation,
    disambiguate_reporters,
    joke_cite,
    parse_page,
    remove_address_citations,
)
from eyecite.models import (
    CitationBase,
    CitationToken,
    FullCaseCitation,
    IdCitation,
    IdToken,
    NonopinionCitation,
    SectionToken,
    ShortCaseCitation,
    SupraCitation,
    SupraToken,
    Token,
    Tokens,
)
from eyecite.tokenizers import Tokenizer, default_tokenizer


def get_citations(
    plain_text: str,
    do_post_citation: bool = True,
    do_defendant: bool = True,
    remove_ambiguous: bool = False,
    tokenizer: Tokenizer = default_tokenizer,
) -> Iterable[CitationBase]:
    """Main function"""
    if plain_text == "this":
        return joke_cite

    words = cast(Tokens, list(tokenizer.tokenize(plain_text)))
    citations: List[CitationBase] = []

    for i, token in enumerate(words):
        citation: Optional[CitationBase]
        token_type = type(token)

        # CASE 1: Citation token is a reporter (e.g., "U. S.").
        # In this case, first try extracting it as a standard, full citation,
        # and if that fails try extracting it as a short form citation.
        if token_type is CitationToken:
            citation_token = cast(CitationToken, token)
            if citation_token.short:
                citation = extract_shortform_citation(words, i)
            else:
                citation = extract_full_citation(words, i)
                if do_post_citation:
                    add_post_citation(citation, words)
                if do_defendant:
                    add_defendant(citation, words)
            citation.guess_edition()
            citation.guess_court()

        # CASE 2: Citation token is an "Id." or "Ibid." reference.
        # In this case, the citation should simply be to the item cited
        # immediately prior, but for safety we will leave that resolution up
        # to the user.
        elif token_type is IdToken:
            citation = extract_id_citation(words, i)

        # CASE 3: Citation token is a "supra" reference.
        # In this case, we're not sure yet what the citation's antecedent is.
        # It could be any of the previous citations above. Thus, like an Id.
        # citation, for safety we won't resolve this reference yet.
        elif token_type is SupraToken:
            citation = extract_supra_citation(cast(SupraToken, words), i)

        # CASE 4: Citation token is a section marker.
        # In this case, it's likely that this is a reference to a non-
        # opinion document. So we record this marker in order to keep
        # an accurate list of the possible antecedents for id citations.
        elif token_type is SectionToken:
            citation = NonopinionCitation(cast(SectionToken, token), i)

        # CASE 5: The token is not a citation.
        else:
            continue

        if citation is not None:
            citations.append(citation)

    # Remove citations with multiple reporter candidates where we couldn't
    # guess correct reporter
    if remove_ambiguous:
        citations = disambiguate_reporters(citations)

    citations = remove_address_citations(citations)

    # Returns a list of citations ordered in the sequence that they appear in
    # the document. The ordering of this list is important for reconstructing
    # the references of the ShortCaseCitation, SupraCitation, and
    # IdCitation objects.
    return citations


def extract_full_citation(
    words: Tokens,
    index: int,
) -> FullCaseCitation:
    """Given a list of words and the index of a citation, return
    a FullCaseCitation object."""
    cite_token = cast(CitationToken, words[index])

    # Return FullCaseCitation
    return FullCaseCitation(
        cite_token,
        index,
        reporter=cite_token.reporter,
        page=cite_token.page,
        volume=cite_token.volume,
        reporter_found=cite_token.reporter,
        exact_editions=cite_token.exact_editions,
        variation_editions=cite_token.variation_editions,
    )


def extract_shortform_citation(
    words: Tokens,
    index: int,
) -> ShortCaseCitation:
    """Given a list of words and the index of a citation, construct and return
    a ShortCaseCitation object.

    Shortform 1: Adarand, 515 U.S., at 241
    Shortform 2: 515 U.S., at 241
    """
    # Variables to extact
    antecedent_guess: str

    # Get antecedent
    antecedent_guess = str(words[index - 1])
    if antecedent_guess == ",":
        antecedent_guess = str(words[index - 2]) + ","

    # Get citation
    cite_token = cast(CitationToken, words[index])

    # Return ShortCaseCitation
    return ShortCaseCitation(
        cite_token,
        index,
        reporter=cite_token.reporter,
        page=cite_token.page,
        volume=cite_token.volume,
        antecedent_guess=antecedent_guess,
        reporter_found=cite_token.reporter,
        exact_editions=cite_token.exact_editions,
        variation_editions=cite_token.variation_editions,
    )


def extract_supra_citation(
    words: Tokens,
    index: int,
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
    if index <= 1:
        return None

    # Get volume
    volume = None

    # Get page
    try:
        page = parse_page(str(words[index + 2]))
    except IndexError:
        page = None

    # Get antecedent
    antecedent_guess = str(words[index - 1])
    if antecedent_guess.isdigit():
        volume = antecedent_guess
        antecedent_guess = str(words[index - 2])
    elif antecedent_guess == ",":
        antecedent_guess = str(words[index - 2]) + ","

    # Return SupraCitation
    return SupraCitation(
        cast(SupraToken, words[index]),
        index,
        antecedent_guess,
        page=page,
        volume=volume,
    )


def extract_id_citation(
    words: Tokens,
    index: int,
) -> Optional[IdCitation]:
    """Given a list of words and the index of an id token, gather the
    immediately succeeding tokens to construct and return an IdCitation
    object.
    """
    # List of literals that could come after an id token
    id_reference_token_literals = {
        "at",
        "p.",
        "p",
        "pp.",
        "p",
        "@",
        "pg",
        "pg.",
        "¶",
        "¶¶",
    }

    # Helper function to see whether a token qualifies as a page candidate
    def is_page_candidate(token):
        return token in id_reference_token_literals or (
            not isinstance(token, Token) and parse_page(token)
        )

    # Check if the post-id token is indeed a page candidate
    scan_index = index
    has_page = False
    while scan_index + 1 < len(words) and is_page_candidate(
        words[scan_index + 1]
    ):
        scan_index += 1
        has_page = True

    # If it is not, simply set a naive anchor for the end of the scan_index
    if scan_index == index:
        has_page = False
        scan_index = index + 3

    # Only linkify the after tokens if a page is found
    return IdCitation(
        cast(IdToken, words[index]),
        index,
        after_tokens=words[index + 1 : scan_index + 1],
        has_page=has_page,
    )
