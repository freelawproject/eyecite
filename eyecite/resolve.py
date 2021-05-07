from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple

from eyecite.models import (
    CitationBase,
    FullCaseCitation,
    IdCitation,
    NonopinionCitation,
    Resource,
    ResourceType,
    ShortCaseCitation,
    SupraCitation,
)
from eyecite.utils import strip_punct


def resolve_full_citation(full_citation: FullCaseCitation) -> Resource:
    """
    Resolve fullcase citations to resources directly.
    """
    return Resource(full_citation)


def _filter_by_matching_antecedent(
    resolved_full_cites: List[Tuple[FullCaseCitation, ResourceType]],
    antecedent_guess: str,
) -> Optional[ResourceType]:
    matches: List[ResourceType] = []
    ag: str = strip_punct(antecedent_guess)
    for full_citation, resource in resolved_full_cites:
        if full_citation.defendant and ag in full_citation.defendant:
            matches.append(resource)
        elif full_citation.plaintiff and ag in full_citation.plaintiff:
            matches.append(resource)

    # Remove duplicates and only accept if one candidate remains
    matches = list(set(matches))
    return matches[0] if len(matches) == 1 else None


def _resolve_shortcase_citation(
    short_citation: ShortCaseCitation,
    resolved_full_cites: Dict[FullCaseCitation, ResourceType],
) -> Optional[ResourceType]:
    """
    Try to match shortcase citations by checking whether their reporter and
    volume number matches those of any of the previously resolved full
    citations. If there are multiple possible matches, try to refine by also
    checking whether their antecedent_guess appears in either the defendant
    or plaintiff field of any of the previously resolved full citations.
    """
    candidates: List[Tuple[FullCaseCitation, ResourceType]] = []
    for full_citation, resource in resolved_full_cites.items():
        if (
            short_citation.reporter == full_citation.reporter
            and short_citation.volume == full_citation.volume
        ):
            # Append both keys and values for further refinement below
            candidates.append((full_citation, resource))

    # Remove duplicates and only accept if one candidate remains
    if (
        len(list(set([resource for full_citation, resource in candidates])))
        == 1
    ):
        return candidates[0][1]

    # Otherwise, if there is an antecedent guess, try to refine further
    elif short_citation.antecedent_guess:
        return _filter_by_matching_antecedent(
            candidates, short_citation.antecedent_guess
        )

    # Otherwise, nothing left to try
    else:
        return None


def _resolve_supra_citation(
    supra_citation: SupraCitation,
    resolved_full_cites: Dict[FullCaseCitation, ResourceType],
) -> Optional[ResourceType]:
    """
    Try to resolve supra citations by checking whether their antecedent_guess
    appears in either the defendant or plaintiff field of any of the
    previously resolved full citations.
    """
    if not supra_citation.antecedent_guess:  # If no guess, can't do anything
        return None

    return _filter_by_matching_antecedent(
        list(resolved_full_cites.items()), supra_citation.antecedent_guess
    )


def _resolve_id_citation(
    id_citation: IdCitation,
    last_resolution: ResourceType,
) -> Optional[ResourceType]:
    """
    Resolve id citations to the resource of the previously resolved
    citation.
    """
    return last_resolution


def resolve_citations(
    citations: List[CitationBase],
    resolve_fullcase_citation: Callable[
        [FullCaseCitation], ResourceType
    ] = resolve_full_citation,
    resolve_shortcase_citation: Callable[
        [ShortCaseCitation, Dict[FullCaseCitation, ResourceType]],
        Optional[ResourceType],
    ] = _resolve_shortcase_citation,
    resolve_supra_citation: Callable[
        [SupraCitation, Dict[FullCaseCitation, ResourceType]],
        Optional[ResourceType],
    ] = _resolve_supra_citation,
    resolve_id_citation: Callable[
        [IdCitation, ResourceType], Optional[ResourceType]
    ] = _resolve_id_citation,
) -> Dict[ResourceType, List[CitationBase]]:
    """Resolves a list of citations to their associated resources by matching
    each type of Citation object (FullCaseCitation, ShortCaseCitation,
    SupraCitation, and IdCitation) to a "resource" object. Assumes that the
    list of citations is ordered in the order that they were extracted from
    the text (i.e., assumes that supra citations and id citations can only
    refer to previous references). Returns a dict in the following format:
        keys = resources
        values = lists of citations

    The individual resolution steps can be supplanted with more complex logic
    by passing custom functions (e.g., if you have a thicker resource
    abstraction that you want to use); the default approach is to use simple
    heuristics to narrow down the set of possible resolutions. If a citation
    cannot be definitively resolved to a resource, it is dropped and not
    resolved.
    """
    # Dict of all citation resolutions
    resolutions: Dict[ResourceType, List[CitationBase]] = defaultdict(list)

    # Dict mapping full citations to their resolved resources
    resolved_full_cites: Dict[FullCaseCitation, ResourceType] = {}

    # The resource of the most recently resolved citation, if any
    last_resolution: Optional[ResourceType] = None

    # Iterate over each citation and attempt to resolve it to a resource
    for citation in citations:

        # If the citation is to a non-opinion document, ignore for now
        if isinstance(citation, NonopinionCitation):
            resolution = None

        # If the citation is a full case citation, try to resolve it
        elif isinstance(citation, FullCaseCitation):
            resolution = resolve_fullcase_citation(citation)
            resolved_full_cites[citation] = resolution

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
            resolution = resolve_id_citation(citation, last_resolution)

        if resolution:
            # Update the most recently resolved resource
            last_resolution = resolution

            # Record the citation in the appropriate list
            resolutions[resolution].append(citation)
        else:
            last_resolution = None

    return resolutions
