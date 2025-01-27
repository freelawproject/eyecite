import re
from typing import List, Type, cast

from eyecite.helpers import (
    disambiguate_reporters,
    extract_pin_cite,
    filter_citations,
    joke_cite,
    match_on_tokens,
)
from eyecite.models import (
    CaseReferenceToken,
    CitationBase,
    CitationToken,
    FullCaseCitation,
    FullCitation,
    FullJournalCitation,
    FullLawCitation,
    IdCitation,
    IdToken,
    ReferenceCitation,
    ResourceCitation,
    SectionToken,
    ShortCaseCitation,
    SupraCitation,
    SupraToken,
    Tokens,
    UnknownCitation,
)
from eyecite.regexes import SHORT_CITE_ANTECEDENT_REGEX, SUPRA_ANTECEDENT_REGEX
from eyecite.tokenizers import Tokenizer, default_tokenizer


def get_citations(
    plain_text: str,
    remove_ambiguous: bool = False,
    tokenizer: Tokenizer = default_tokenizer,
) -> List[CitationBase]:
    """This is eyecite's main workhorse function. Given a string of text
    (e.g., a judicial opinion or other legal document), return a list of
    `eyecite.models.CitationBase` objects representing the citations found
    in the document.

    Args:
        plain_text: The text to parse. You may wish to use the
            `eyecite.clean.clean_text` function to pre-process your text
            before passing it here.
        remove_ambiguous: Whether to remove citations that might refer to more
            than one reporter and can't be narrowed down by date.
        tokenizer: An instance of a Tokenizer object. See `eyecite.tokenizers`
            for information about available tokenizers. Uses the
            `eyecite.tokenizers.AhocorasickTokenizer` by default.

    Returns:
        A list of `eyecite.models.CitationBase` objects
    """
    if plain_text == "eyecite":
        return joke_cite

    words, citation_tokens = tokenizer.tokenize(plain_text)
    citations: list[CitationBase] = []

    for i, token in citation_tokens:
        citation: CitationBase
        token_type = type(token)

        # CASE 1: Token is a CitationToken (i.e., a reporter, a law journal,
        # or a law).
        # In this case, first try extracting it as a standard, full citation,
        # and if that fails try extracting it as a short form citation.
        if token_type is CitationToken:
            citation_token = cast(CitationToken, token)
            if citation_token.short:
                citation = _extract_shortform_citation(words, i)
            else:
                citation = _extract_full_citation(words, i)
                if citations and isinstance(citation, FullCitation):
                    citation.is_parallel_citation(citations[-1])

                # Check for reference citations that follow a full citation
                # Using the plaintiff or defendant
                references = _extract_reference_citations(citation, plain_text)
                citations.extend(references)

        # CASE 2: Token is an "Id." or "Ibid." reference.
        # In this case, the citation should simply be to the item cited
        # immediately prior, but for safety we will leave that resolution up
        # to the user.
        elif token_type is IdToken:
            citation = _extract_id_citation(words, i)

        # CASE 3: Token is a "supra" reference.
        # In this case, we're not sure yet what the citation's antecedent is.
        # It could be any of the previous citations above. Thus, like an Id.
        # citation, for safety we won't resolve this reference yet.
        elif token_type is SupraToken:
            citation = _extract_supra_citation(words, i)

        # CASE 4: Token is a section marker.
        # In this case, it's likely that this is a reference to a citation,
        # but we're not sure what it is if it doesn't match any of the above.
        # So we record this marker in order to keep an accurate list of the
        # possible antecedents for id citations.
        elif token_type is SectionToken:
            citation = UnknownCitation(cast(SectionToken, token), i)

        # CASE 5: The token is not a citation.
        else:
            continue

        citations.append(citation)

    citations = filter_citations(citations)

    # Remove citations with multiple reporter candidates where we couldn't
    # guess correct reporter
    if remove_ambiguous:
        citations = disambiguate_reporters(citations)

    # Returns a list of citations ordered in the sequence that they appear in
    # the document. The ordering of this list is important for reconstructing
    # the references of the ShortCaseCitation, SupraCitation, and
    # IdCitation and ReferenceCitation objects.
    return citations


def _extract_reference_citations(
    citation: FullCitation, plain_text: str
) -> List[ReferenceCitation]:
    """Extract reference citations that follow a full citation

    :param citation: the full case citation found
    :param plain_text: the text
    :return: Pin cite reference citations
    """
    if len(plain_text) <= citation.span()[-1]:
        return []
    if not isinstance(citation, FullCaseCitation):
        return []

    def is_valid_name(name: str) -> bool:
        """Validate name isnt a regex issue

        Excludes strings like Co., numbers or lower case strs

        :param name: The name to check
        :return: True if usable, false if not
        """
        return (
            isinstance(name, str)
            and len(name) > 2
            and name[0].isupper()
            and not name.endswith(".")
            and not name.isdigit()
        )

    regexes = [
        rf"(?P<{key}>{re.escape(value)})"
        for key in ["plaintiff", "defendant"]
        if (value := getattr(citation.metadata, key, None))
        and is_valid_name(value)
    ]
    if not regexes:
        return []
    pin_cite_re = (
        rf"\b(?:{'|'.join(regexes)})\s+at\s+(?P<pin_cite>\d{{1,5}})\b"
    )
    reference_citations = []
    remaining_text = plain_text[citation.span()[-1] :]
    offset = citation.span()[-1]
    for match in re.compile(pin_cite_re).finditer(remaining_text):
        start, end = match.span()
        matched_text = match.group(0)
        reference = ReferenceCitation(
            token=CaseReferenceToken(
                data=matched_text, start=start + offset, end=end + offset
            ),
            span_start=start + offset,
            span_end=end + offset,
            full_span_start=start + offset,
            full_span_end=end + offset,
            index=0,
            metadata=match.groupdict(),
        )
        reference_citations.append(reference)
    return reference_citations


def _extract_full_citation(
    words: Tokens,
    index: int,
) -> FullCitation:
    """Given a list of words and the index of a citation, return
    a FullCitation object."""

    # Our cite was matched by one or more regexes, which could have come from
    # one or more of the sources in reporters_db (e.g. reporters, laws,
    # journals). Get the set of all sources that matched, preferring exact
    # matches to variations:
    token = cast(CitationToken, words[index])
    cite_sources = set(
        e.reporter.source
        for e in (token.exact_editions or token.variation_editions)
    )

    # get citation_class based on cite_sources
    citation_class: Type[ResourceCitation]
    if "reporters" in cite_sources:
        citation_class = FullCaseCitation
    elif "laws" in cite_sources:
        citation_class = FullLawCitation
    elif "journals" in cite_sources:
        citation_class = FullJournalCitation
    else:
        raise ValueError(f"Unknown cite_sources value {cite_sources}")

    # make citation
    citation = citation_class(
        token,
        index,
        exact_editions=token.exact_editions,
        variation_editions=token.variation_editions,
    )
    citation.add_metadata(words)

    return citation


def _extract_shortform_citation(
    words: Tokens,
    index: int,
) -> ShortCaseCitation:
    """Given a list of words and the index of a citation, construct and return
    a ShortCaseCitation object.

    Shortform 1: Adarand, 515 U.S., at 241
    Shortform 2: 515 U.S., at 241
    """
    # get antecedent word
    antecedent_guess = None
    m = match_on_tokens(
        words,
        index - 1,
        SHORT_CITE_ANTECEDENT_REGEX,
        strings_only=True,
        forward=False,
    )
    if m:
        antecedent_guess = m["antecedent"].strip()

    # Get pin_cite
    cite_token = cast(CitationToken, words[index])
    pin_cite, span_end, full_span_end, parenthetical = extract_pin_cite(
        words, index, prefix=cite_token.groups["page"]
    )

    # make ShortCaseCitation
    citation = ShortCaseCitation(
        cite_token,
        index,
        exact_editions=cite_token.exact_editions,
        variation_editions=cite_token.variation_editions,
        span_end=span_end,
        full_span_start=(
            index
            if not antecedent_guess
            else index - 1 + m.start()
        ),
        full_span_end=full_span_end,
        metadata={
            "antecedent_guess": antecedent_guess,
            "pin_cite": pin_cite,
            "parenthetical": parenthetical,
        },
    )

    # add metadata
    citation.guess_edition()
    citation.guess_court()
    return citation


def _extract_supra_citation(
    words: Tokens,
    index: int,
) -> SupraCitation:
    """Given a list of words and the index of a supra token, look before
    and after to see if this is a supra citation. If found, construct
    and return a SupraCitation object.

    Supra 1: Adarand, supra, at 240
    Supra 2: Adarand, 515 supra, at 240
    Supra 3: Adarand, supra, somethingelse
    Supra 4: Adrand, supra. somethingelse
    """
    pin_cite, span_end, full_span_end, parenthetical = extract_pin_cite(words, index)
    antecedent_guess = None
    volume = None
    m = match_on_tokens(
        words,
        index - 1,
        SUPRA_ANTECEDENT_REGEX,
        strings_only=True,
        forward=False,
    )
    if m:
        antecedent_guess = m["antecedent"]
        volume = m["volume"]

    # Return SupraCitation
    return SupraCitation(
        cast(SupraToken, words[index]),
        index,
        span_end=span_end,
        full_span_start=(
            index
            if not antecedent_guess
            else index - 1 + m.start()
        ),
        full_span_end=full_span_end,
        metadata={
            "antecedent_guess": antecedent_guess,
            "pin_cite": pin_cite,
            "parenthetical": parenthetical,
            "volume": volume,
        },
    )


def _extract_id_citation(
    words: Tokens,
    index: int,
) -> IdCitation:
    """Given a list of words and the index of an id token, gather the
    immediately succeeding tokens to construct and return an IdCitation
    object.
    """
    pin_cite, span_end, full_span_end, parenthetical = extract_pin_cite(words, index)
    return IdCitation(
        cast(IdToken, words[index]),
        index,
        span_end=span_end,
        full_span_end=full_span_end,
        metadata={
            "pin_cite": pin_cite,
            "parenthetical": parenthetical,
        },
    )
