# Import extended functionality
from . import models_extended, tokenizers_extended
from .annotate import annotate_citations
from .clean import clean_text
from .find import get_citations
from .models_extended import (
    AttorneyGeneralCitation,
    BaseCitation,
    ConstitutionCitation,
    CourtRuleCitation,
    JournalArticleCitation,
    LegislativeBillCitation,
    RegulationCitation,
    ScientificIdentifierCitation,
    SessionLawCitation,
)
from .resolve import resolve_citations
from .tokenizers_extended import (
    AttorneyGeneralOpinionsTokenizer,
    ExtendedCitationTokenizer,
    FederalLegislationTokenizer,
    JournalArticleTokenizer,
    ScientificIdentifierTokenizer,
    StateConstitutionTokenizer,
    default_extended_tokenizer,
)

__all__ = [
    "annotate_citations",
    "get_citations",
    "clean_text",
    "resolve_citations",
    # Extended functionality
    "models_extended",
    "tokenizers_extended",
    "BaseCitation",
    "ConstitutionCitation",
    "RegulationCitation",
    "CourtRuleCitation",
    "LegislativeBillCitation",
    "SessionLawCitation",
    "JournalArticleCitation",
    "ScientificIdentifierCitation",
    "AttorneyGeneralCitation",
    "StateConstitutionTokenizer",
    "JournalArticleTokenizer",
    "FederalLegislationTokenizer",
    "ScientificIdentifierTokenizer",
    "ExtendedCitationTokenizer",
    "default_extended_tokenizer",
    "AttorneyGeneralOpinionsTokenizer",
]

# No need to create API documentation for these internal helper functions
__pdoc__ = {
    "annotate.SpanUpdater": False,
    "helpers": False,
    "regexes": False,
    "test_factories": False,
    "utils": False,
}
