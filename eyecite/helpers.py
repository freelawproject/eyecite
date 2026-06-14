"""Thin re-export module for eyecite.helpers.

This module re-exports all public names from the domain-focused modules
that were split out from this file. Existing code that imports from
``eyecite.helpers`` will continue to work unchanged.
"""

import logging

# -- court_matching --
from eyecite.court_matching import get_court_by_paren

# -- token_matching --
from eyecite.token_matching import match_on_tokens, MAX_MATCH_CHARS

# -- citation_metadata --
from eyecite.citation_metadata import (
    add_post_citation,
    add_pre_citation,
    add_law_metadata,
    add_journal_metadata,
    clean_pin_cite,
    process_parenthetical,
    get_year,
)

# -- case_name --
from eyecite.case_name import (
    BACKWARD_SEEK,
    find_case_name,
    find_case_name_in_html,
    find_html_tags_at_position,
    strip_stop_words,
    convert_html_to_plain_text_and_loc,
)

# -- pin_cite --
from eyecite.pin_cite import extract_pin_cite

# -- citation_filter --
from eyecite.citation_filter import (
    disambiguate_reporters,
    overlapping_citations,
    filter_citations,
    joke_cite,
)

# Preserve the module-level logger so that code patching
# ``eyecite.helpers.logger`` (e.g. tests) continues to work.
logger = logging.getLogger(__name__)

__all__ = [
    # court_matching
    "get_court_by_paren",
    # token_matching
    "match_on_tokens",
    "MAX_MATCH_CHARS",
    # citation_metadata
    "add_post_citation",
    "add_pre_citation",
    "add_law_metadata",
    "add_journal_metadata",
    "clean_pin_cite",
    "process_parenthetical",
    "get_year",
    # case_name
    "BACKWARD_SEEK",
    "find_case_name",
    "find_case_name_in_html",
    "find_html_tags_at_position",
    "strip_stop_words",
    "convert_html_to_plain_text_and_loc",
    # pin_cite
    "extract_pin_cite",
    # citation_filter
    "disambiguate_reporters",
    "overlapping_citations",
    "filter_citations",
    "joke_cite",
]
