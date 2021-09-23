from .annotate import annotate_citations
from .clean import clean_text
from .find import get_citations
from .resolve import resolve_citations

__all__ = [
    "annotate_citations",
    "get_citations",
    "clean_text",
    "resolve_citations",
]

# No need to create API documentation for these internal helper functions
__pdoc__ = {
    "annotate.SpanUpdater": False,
    "helpers": False,
    "regexes": False,
    "test_factories": False,
    "utils": False,
}
