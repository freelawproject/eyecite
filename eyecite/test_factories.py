from eyecite.helpers import get_year
from eyecite.models import (
    CaseReferenceToken,
    CitationToken,
    FullCaseCitation,
    FullJournalCitation,
    FullLawCitation,
    IdCitation,
    IdToken,
    ReferenceCitation,
    SectionToken,
    ShortCaseCitation,
    SupraCitation,
    SupraToken,
    UnknownCitation,
)
from eyecite.tokenizers import EDITIONS_LOOKUP


def resource_citation(
    cls, source_text, reporter, short=False, year=None, index=0, **kwargs
):
    """Create a mock ResourceCitation."""
    metadata = kwargs.pop("metadata", {})
    groups = kwargs.pop("groups", {})
    groups.setdefault("reporter", kwargs.pop("reporter_found", reporter))
    edition = EDITIONS_LOOKUP[reporter][0]
    kwargs.setdefault("exact_editions", [edition])
    kwargs.setdefault("edition_guess", edition)
    if year:
        metadata["year"] = str(year)
    elif "year" in metadata:
        year = get_year(metadata["year"])
    # Avoid https://github.com/PyCQA/pylint/issues/3201
    # pylint: disable=unexpected-keyword-arg
    token = CitationToken(
        source_text,
        0,  # fake start offset
        99,  # fake end offset
        groups=groups,
        exact_editions=[edition],
        variation_editions=[],
        short=short,
    )
    return cls(token, index, metadata=metadata, year=year, **kwargs)


def case_citation(
    source_text=None,
    page="1",
    reporter="U.S.",
    volume="1",
    short=False,
    **kwargs,
):
    """Convenience function for creating mock CaseCitation objects."""
    metadata = kwargs.setdefault("metadata", {})
    groups = kwargs.setdefault("groups", {})
    if reporter == "U.S.":
        metadata.setdefault("court", "scotus")
    if not source_text:
        source_text = f"{volume} {reporter} {page}"
    if short:
        metadata.setdefault("pin_cite", page)
    groups.setdefault("volume", volume)
    groups.setdefault("page", page)
    cls = ShortCaseCitation if short else FullCaseCitation
    return resource_citation(cls, source_text, reporter, short, **kwargs)


def law_citation(
    source_text=None,
    reporter="Mass. Gen. Laws",
    **kwargs,
):
    """Convenience function for creating mock FullLawCitation objects."""
    return resource_citation(FullLawCitation, source_text, reporter, **kwargs)


def journal_citation(
    source_text=None,
    page="1",
    reporter="Minn. L. Rev.",
    volume="1",
    **kwargs,
):
    """Convenience function for creating mock CaseCitation objects."""
    groups = kwargs.setdefault("groups", {})
    if not source_text:
        source_text = f"{volume} {reporter} {page}"
    groups.setdefault("volume", volume)
    groups.setdefault("page", page)
    return resource_citation(
        FullJournalCitation, source_text, reporter, **kwargs
    )


def id_citation(source_text=None, index=0, **kwargs):
    """Convenience function for creating mock IdCitation objects."""
    return IdCitation(IdToken(source_text, 0, 99), index, **kwargs)


def reference_citation(source_text=None, index=0, **kwargs):
    """Convenience function for creating mock ReferenceCitation objects."""
    return ReferenceCitation(
        CaseReferenceToken(source_text, 0, 99), index, **kwargs
    )


def unknown_citation(source_text=None, index=0, **kwargs):
    """Convenience function for creating mock UnknownCitation objects."""
    return UnknownCitation(SectionToken(source_text, 0, 99), index, **kwargs)


def supra_citation(source_text=None, index=0, **kwargs):
    """Convenience function for creating mock SupraCitation objects."""
    return SupraCitation(SupraToken(source_text, 0, 99), index, **kwargs)
