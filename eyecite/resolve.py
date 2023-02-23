import re
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple, cast

from eyecite.models import (
    CitationBase,
    FullCaseCitation,
    FullCitation,
    IdCitation,
    Resource,
    ResourceType,
    ShortCaseCitation,
    SupraCitation,
)
from eyecite.utils import strip_punct

# type shorthand
ResolvedFullCite = Tuple[FullCitation, ResourceType]
ResolvedFullCites = List[ResolvedFullCite]
Resolutions = Dict[ResourceType, List[CitationBase]]


# Skip id. citations that imply a page length longer than this,
# such as "1 U.S. 1. Id. at 200.":
MAX_OPINION_PAGE_COUNT = 150


def resolve_full_citation(full_citation: FullCitation) -> Resource:
    """By default, resolve `eyecite.models.FullCaseCitation` objects to a
    generic (but reference-unique) `eyecite.models.Resource` object. This
    method is publicly documented because even if you override this method
    yourself with more sophisticated resolution logic, you may wish to still
    use this one as a fallback. For example, this could be one sensible
    pattern:

    >>> def my_resolve(full_cite):
    ...     # special handling for resolution of known cases in a database
    ...     resource = MyOpinion.objects.get(full_cite)
    ...     if resource:
    ...         return resource
    ...     # allow normal clustering of other citations
    ...     return resolve_full_citation(full_cite)
    >>>
    >>> resolve_citations(citations, resolve_full_citation=my_resolve)
    >>>
    >>> returns (pseudo):
    >>> {
    ...     <MyOpinion object>: [<full_cite>, <short_cite>, <id_cite>],
    ...     <Resource object>: [<full cite>, <short cite>],
    >>> }

    Args:
        full_citation: A `eyecite.models.FullCitation` to resolve.

    Returns:
        The `eyecite.models.Resource` that the citation references.
    """
    return Resource(full_citation)


def _filter_by_matching_antecedent(
    resolved_full_cites: ResolvedFullCites,
    antecedent_guess: str,
) -> Optional[ResourceType]:
    matches: List[ResourceType] = []
    ag: str = strip_punct(antecedent_guess)
    for full_citation, resource in resolved_full_cites:
        if not isinstance(full_citation, FullCaseCitation):
            continue
        if (
            full_citation.metadata.defendant
            and ag in full_citation.metadata.defendant
        ):
            matches.append(resource)
        elif (
            full_citation.metadata.plaintiff
            and ag in full_citation.metadata.plaintiff
        ):
            matches.append(resource)

    # Remove duplicates and only accept if one candidate remains
    matches = list(set(matches))
    return matches[0] if len(matches) == 1 else None


def _has_invalid_pin_cite(
    full_cite: FullCitation, id_cite: IdCitation
) -> bool:
    """Return True if id_cite has a pin cite that can't be correct for the
    given full_cite."""
    # if full cite has a known missing page, this pin cite can't be correct
    if (
        type(full_cite) is FullCaseCitation
        and full_cite.groups.get("page") is None
    ):
        return True

    # if no pin cite, we're fine
    if not id_cite.metadata.pin_cite:
        return False

    # if full cite has no page (such as a statute), we don't know what to
    # check, so assume we're fine
    if not full_cite.groups.get("page", "").isdigit():
        return False

    # parse full cite page
    page = int(full_cite.groups["page"])

    # parse short cite pin
    m = re.match(r"(?:at )?(\d+)", id_cite.metadata.pin_cite)
    if not m:
        # If pin cite doesn't start with a digit, assume it is invalid.
        # This is hopefully a conservative rule -- it will err for valid pin
        # cites like "Id. at *10", but successfully filter invalid pin cites
        # like "1 U.S. 1. ... Id. at ¶ 10".
        return True
    pin_cite = int(m[1])

    # check page range
    if pin_cite < page or pin_cite > page + MAX_OPINION_PAGE_COUNT:
        return True

    return False


def _resolve_shortcase_citation(
    short_citation: ShortCaseCitation,
    resolved_full_cites: ResolvedFullCites,
) -> Optional[ResourceType]:
    """
    Try to match shortcase citations by checking whether their reporter and
    volume number matches those of any of the previously resolved full
    citations. If there are multiple possible matches, try to refine by also
    checking whether their antecedent_guess appears in either the defendant
    or plaintiff field of any of the previously resolved full citations.
    """
    candidates: ResolvedFullCites = []
    for full_citation, resource in resolved_full_cites:
        if (
            isinstance(full_citation, FullCaseCitation)
            and short_citation.corrected_reporter()
            == full_citation.corrected_reporter()
            and short_citation.groups.get("volume")
            == full_citation.groups.get("volume")
        ):
            # Append both keys and values for further refinement below
            candidates.append((full_citation, resource))

    # Remove duplicates and only accept if one candidate remains
    if len(set(resource for full_citation, resource in candidates)) == 1:
        return candidates[0][1]

    # Otherwise, if there is an antecedent guess, try to refine further
    elif short_citation.metadata.antecedent_guess:
        return _filter_by_matching_antecedent(
            candidates, short_citation.metadata.antecedent_guess
        )

    # Otherwise, nothing left to try
    else:
        return None


def _resolve_supra_citation(
    supra_citation: SupraCitation,
    resolved_full_cites: ResolvedFullCites,
) -> Optional[ResourceType]:
    """
    Try to resolve supra citations by checking whether their antecedent_guess
    appears in either the defendant or plaintiff field of any of the
    previously resolved full citations.
    """
    # If no guess, can't do anything
    if not supra_citation.metadata.antecedent_guess:
        return None

    return _filter_by_matching_antecedent(
        resolved_full_cites, supra_citation.metadata.antecedent_guess
    )


def _resolve_id_citation(
    id_citation: IdCitation,
    last_resolution: ResourceType,
    resolutions: Resolutions,
) -> Optional[ResourceType]:
    """
    Resolve id citations to the resource of the previously resolved
    citation.
    """
    # if last resolution failed, id. cite should also fail
    if not last_resolution:
        return None

    # filter out citations based on pin cite
    full_cite = cast(FullCitation, resolutions[last_resolution][0])
    if _has_invalid_pin_cite(full_cite, id_citation):
        return None

    return last_resolution


def resolve_citations(
    citations: List[CitationBase],
    resolve_full_citation: Callable[
        [FullCitation], ResourceType
    ] = resolve_full_citation,
    resolve_shortcase_citation: Callable[
        [ShortCaseCitation, ResolvedFullCites],
        Optional[ResourceType],
    ] = _resolve_shortcase_citation,
    resolve_supra_citation: Callable[
        [SupraCitation, ResolvedFullCites],
        Optional[ResourceType],
    ] = _resolve_supra_citation,
    resolve_id_citation: Callable[
        [IdCitation, ResourceType, Resolutions], Optional[ResourceType]
    ] = _resolve_id_citation,
) -> Resolutions:
    """Resolve a list of citations to their associated resources by matching
    each type of Citation object (FullCaseCitation, ShortCaseCitation,
    SupraCitation, and IdCitation) to a "resource" object. A "resource" could
    be a document, a URL, a database entry, etc. -- anything that conforms to
    the (non-prescriptive) requirements of the `eyecite.models.ResourceType`
    type. By default, eyecite uses an extremely thin "resource" object that
    simply serves as a conceptual way to group citations with the same
    references together.

    This function assumes that the given list of citations is ordered in the
    order that they were extracted from the text (i.e., assumes that supra
    citations and id citations can only refer to previous references).

    It returns a dict in the following format:
    ```
        keys = resources
        values = lists of citations
    ```

    The individual resolution steps can be supplanted with more complex logic
    by passing custom functions (e.g., if you have a thicker resource
    abstraction that you want to use); the default approach is to use simple
    heuristics to narrow down the set of possible resolutions. If a citation
    cannot be definitively resolved to a resource, it is dropped and not
    resolved.

    Args:
        citations: A list of `eyecite.models.CitationBase` objects, returned
            from calling `eyecite.find.get_citations`.
        resolve_full_citation: A function that resolves
            `eyecite.models.FullCitation` objects to resources.
        resolve_shortcase_citation: A function that resolves
            `eyecite.models.ShortCaseCitation` objects to resources.
        resolve_supra_citation: A function that resolves
            `eyecite.models.SupraCitation` objects to resources.
        resolve_id_citation: A function that resolves
            `eyecite.models.IdCitation` objects to resources.

    Returns:
        A dictionary mapping `eyecite.models.ResourceType` objects (the keys)
            to lists of `eyecite.models.CitationBase` objects (the values).
    """
    # Dict of all citation resolutions
    resolutions: Resolutions = defaultdict(list)

    # Dict mapping full citations to their resolved resources
    resolved_full_cites: ResolvedFullCites = []

    # The resource of the most recently resolved citation, if any
    last_resolution: Optional[ResourceType] = None

    # Iterate over each citation and attempt to resolve it to a resource
    for citation in citations:
        # If the citation is a full citation, try to resolve it
        if isinstance(citation, FullCitation):
            resolution = resolve_full_citation(citation)
            resolved_full_cites.append((citation, resolution))

        # If the citation is a short case citation, try to resolve it
        elif isinstance(citation, ShortCaseCitation):
            resolution = resolve_shortcase_citation(
                citation, resolved_full_cites
            )

        # If the citation is a supra citation, try to resolve it
        elif isinstance(citation, SupraCitation):
            resolution = resolve_supra_citation(citation, resolved_full_cites)

        # If the citation is an id citation, try to resolve it
        elif isinstance(citation, IdCitation):
            resolution = resolve_id_citation(
                citation, last_resolution, resolutions
            )

        # If the citation is to an unknown document, ignore for now
        else:
            resolution = None

        last_resolution = resolution
        if resolution:
            # Record the citation in the appropriate list
            resolutions[resolution].append(citation)

    return resolutions
