from eyecite.models import (
    CitationToken,
    FullCaseCitation,
    IdCitation,
    IdToken,
    NonopinionCitation,
    SectionToken,
    ShortCaseCitation,
    SupraCitation,
    SupraToken,
)
from eyecite.tokenizers import EDITIONS_LOOKUP


def case_citation(
    index,
    source_text=None,
    page="1",
    reporter="U.S.",
    volume="1",
    short=False,
    **kwargs,
):
    kwargs.setdefault("canonical_reporter", reporter)
    kwargs.setdefault("reporter_found", reporter)
    if reporter == "U.S.":
        kwargs.setdefault("court", "scotus")
    if not source_text:
        source_text = f"{volume} {reporter} {page}"
    edition = EDITIONS_LOOKUP[reporter][0]
    token = CitationToken(
        source_text,
        volume,
        reporter,
        page,
        exact_editions=[edition],
        variation_editions=[],
        short=short,
    )
    cls = ShortCaseCitation if short else FullCaseCitation
    return cls(
        token, index, volume=volume, reporter=reporter, page=page, **kwargs
    )


def id_citation(index, source_text, **kwargs):
    return IdCitation(IdToken(source_text), index, **kwargs)


def nonopinion_citation(index, source_text):
    return NonopinionCitation(SectionToken(source_text), index)


def supra_citation(index, source_text, **kwargs):
    return SupraCitation(SupraToken(source_text), index, **kwargs)
