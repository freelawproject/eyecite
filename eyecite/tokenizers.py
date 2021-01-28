import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
)

import ahocorasick
from reporters_db import REPORTERS

from eyecite.models import (
    CitationToken,
    Edition,
    IdToken,
    Reporter,
    SectionToken,
    StopWordToken,
    SupraToken,
    TokenExtractor,
    Tokens,
)
from eyecite.utils import (
    PAGE_NUMBER_REGEX,
    space_boundaries_re,
    strip_punctuation_re,
)

# Prepare extractors

# An extractor is an object that applies a particular regex to a string
# and returns Tokens for each match. We need to build a list of all of
# our extractors. Also build a lookup of Editions by reporter string,
# though that isn't directly used outside of tests.

EXTRACTORS = []
EDITIONS_LOOKUP = defaultdict(list)


def _populate_reporter_extractors():
    """Populate EXTRACTORS and EDITIONS_LOOKUP."""

    # Extractors step one: add an extractor for each reporter string

    def _cite_regex(reporter: str, cite_format: Optional[str] = None):
        """Helper to generate cite-matching regexes from a
        reporter like "U.S" and a cite_format like
        "{volume} {reporter} {page}"
        """
        if cite_format is None:
            cite_format = "{volume} {reporter},? {page}"
        return (
            cite_format.replace(
                "{volume}", strip_punctuation_re(r"(?P<volume>\d+)")
            )
            .replace("{reporter}", rf"(?P<reporter>{re.escape(reporter)})")
            .replace("{page}", rf"(?P<page>{PAGE_NUMBER_REGEX})")
        )

    def _add_reporter_regex(
        editions_by_regex: Dict,
        kind: str,
        reporter: str,
        edition: Edition,
        cite_format: str,
    ):
        """Helper to generate citations for a reporter
        and insert into editions_by_regex."""
        EDITIONS_LOOKUP[reporter].append(edition)

        # insert long cite
        regex = _cite_regex(reporter, cite_format)
        editions_by_regex[regex][kind].append(edition)
        editions_by_regex[regex]["strings"].add(reporter)

        # insert short cite -- we can currently only do this if there's
        # no custom cite_format in reporters_db
        if cite_format is None:
            regex = _cite_regex(reporter, "{volume} {reporter},? at {page}")
            editions_by_regex[regex][kind].append(edition)
            editions_by_regex[regex]["strings"].add(reporter)
            editions_by_regex[regex]["short"] = True

    # Build a lookup of regex -> edition.
    # Keys in this dict will be regular expressions to handle a
    # particular reporter string, like (simplified)
    # r"(?P<volume>\d+) (?P<reporter>U\.S\.) (?P<page>\d+)"
    editions_by_regex = defaultdict(
        # Values in this dict will be:
        lambda: {
            # Exact matches. If the regex is "\d+ U.S. \d+",
            # this will be [Edition("U.S.")]
            "editions": [],
            # Variants. If the regex matches "\d+ U. S. \d+",
            # this will be [Edition("U.S.")]
            "variations": [],
            # Strings a text must contain for this regex to match.
            # If the regex is "\d+ S.E. 2d \d+",
            # this will be {"S.E. 2d"}
            "strings": set(),
            # Whether this regex results in a short cite:
            "short": False,
        }
    )

    # Use our helper functions to insert a regex into editions_by_regex
    # for each reporter string in reporters_db:
    for reporter_key, reporter_cluster in REPORTERS.items():
        for reporter in reporter_cluster:
            reporter_obj = Reporter(
                short_name=reporter_key,
                name=reporter["name"],
                cite_type=reporter["cite_type"],
            )
            editions = {}
            cite_format = reporter.get("cite_format")
            for edition_name, dates in reporter["editions"].items():
                editions[edition_name] = Edition(
                    short_name=edition_name,
                    reporter=reporter_obj,
                    start=dates["start"],
                    end=dates["end"],
                )
                _add_reporter_regex(
                    editions_by_regex,
                    "editions",
                    edition_name,
                    editions[edition_name],
                    cite_format,
                )
            for variation, edition_name in reporter["variations"].items():
                _add_reporter_regex(
                    editions_by_regex,
                    "variations",
                    variation,
                    editions[edition_name],
                    cite_format,
                )

    # Add each regex to EXTRACTORS:
    for regex, cluster in editions_by_regex.items():
        EXTRACTORS.append(
            TokenExtractor(
                regex,
                CitationToken.from_match,
                extra={
                    "exact_editions": cluster["editions"],
                    "variation_editions": cluster["variations"],
                    "short": cluster["short"],
                },
                strings=list(cluster["strings"]),
            )
        )

    # Extractors step two:
    # Add a few one-off extractors to handle special token types
    # other than citations:

    id_regex = space_boundaries_re(r"id\.,?|ibid\.")
    supra_regex = space_boundaries_re(strip_punctuation_re("supra"))
    stop_word_regex = space_boundaries_re(
        strip_punctuation_re(rf'({"|".join(StopWordToken.stop_tokens)})')
    )
    symbol_regex = r"\S*§\S*"

    EXTRACTORS.extend(
        [
            # Id.
            TokenExtractor(
                id_regex,
                IdToken.from_match,
                flags=re.I,
                strings=["id.", "ibid."],
            ),
            # supra
            TokenExtractor(
                supra_regex,
                SupraToken.from_match,
                flags=re.I,
                strings=["supra"],
            ),
            # case name stopwords
            TokenExtractor(
                stop_word_regex,
                StopWordToken.from_match,
                flags=re.I,
                strings=StopWordToken.stop_tokens,
            ),
            # tokens containing section symbols
            TokenExtractor(
                symbol_regex, SectionToken.from_match, strings=["§"]
            ),
        ]
    )


_populate_reporter_extractors()

# Tokenizers


@dataclass
class BaseTokenizer:
    """A tokenizer takes a list of extractors, and provides a tokenize()
    method to tokenize text using those extractors."""

    extractors: List[TokenExtractor] = field(
        default_factory=lambda: list(EXTRACTORS)
    )

    def tokenize(self, text: str) -> Generator[Tokens, None, None]:
        """Main interface for callers."""
        raise NotImplementedError

    def get_extractors(self, text: str):
        """Subclasses can override this to filter extractors based on text."""
        return self.extractors


@dataclass
class Tokenizer(BaseTokenizer):
    """The simplest working tokenizer: find all matches for all
    extractors and return all non-overlapping tokens."""

    def tokenize(self, text: str) -> Generator[Tokens, None, None]:
        """Tokenize text and yield tokens."""
        # Get all matches. This may include overlaps.
        # Entries in matches are
        # ((start_offset, end_offset), Match, TokenExtractor)
        extractors = self.get_extractors(text)
        matches = [
            (m.span(), m, e) for e in extractors for m in e.get_matches(text)
        ]

        # Sort all matches by start offset ascending, then end offset
        # descending. Remove overlaps by iteratively returning only matches
        # where the current start offset is greater than the previously
        # returned end offset:
        matches.sort(key=lambda m: (m[0][0], -m[0][1]))
        offset = 0
        for (start, end), m, extractor in matches:
            # skip overlaps
            if offset > start:
                continue
            # yield plain text tokens before current token
            if offset < start:
                yield from text[offset:start].strip().split()
            # yield current token
            yield extractor.get_token(m)
            offset = end
        # yield plain text tokens after final token
        if offset < len(text):
            yield from text[offset:].strip().split()


@dataclass
class AhocorasickTokenizer(Tokenizer):
    """A performance-optimized Tokenizer using the
    pyahocorasick library. Only runs extractors where
    the target text contains one of the strings from
    TokenExtractor.strings."""

    def get_extractors(self, text: str) -> Set[TokenExtractor]:
        """Override get_extractors() to filter out extractors
        that can't possibly match."""
        unique_extractors = set()
        for _, extractors in self.case_sensitive_filter.iter(text):
            unique_extractors.update(extractors)
        for _, extractors in self.case_insensitive_filter.iter(text.lower()):
            unique_extractors.update(extractors)
        return unique_extractors

    @property
    def case_sensitive_filter(self):
        """Build a pyahocorasick filter for all case-sensitive extractors."""
        if not hasattr(self, "_case_sensitive_filter"):
            self._case_sensitive_filter = self.make_ahocorasick_filter(
                (s, e)
                for e in EXTRACTORS
                if not e.flags & re.I
                for s in e.strings
            )
            self._case_insensitive_filter = self.make_ahocorasick_filter(
                (s.lower(), e)
                for e in EXTRACTORS
                if e.flags & re.I
                for s in e.strings
            )
        return self._case_sensitive_filter

    @property
    def case_insensitive_filter(self):
        """Build a pyahocorasick filter for all case-insensitive extractors."""
        if not hasattr(self, "_case_insensitive_filter"):
            _ = self._case_sensitive_filter
        return self._case_insensitive_filter

    @staticmethod
    def make_ahocorasick_filter(
        items: Iterable[Sequence[Any]],
    ) -> ahocorasick.Automaton:
        """Given a list of items like
            [['see', stop_word_extractor],
             ['see', another_extractor],
             ['nope', some_extractor]],
        return a pyahocorasick filter such that
            text_filter.iter('...see...')
        yields
            [[stop_word_extractor, another_extractor]].
        """
        grouped = defaultdict(list)
        for string, extractor in items:
            grouped[string].append(extractor)

        text_filter = ahocorasick.Automaton()
        for string, extractors in grouped.items():
            text_filter.add_word(string, extractors)
        text_filter.make_automaton()
        return text_filter


@dataclass
class HyperscanTokenizer(BaseTokenizer):
    """A performance-optimized Tokenizer using the
    hyperscan library. Precompiles a database of all
    extractors and runs them in a single pass through
    the target text."""

    # Precompiling the database takes several seconds.
    # To avoid that, provide a cache directory writeable
    # only by this user where the precompiled database
    # can be stored.
    cache_dir: Optional[str] = None

    def tokenize(self, text: str) -> Generator[Tokens, None, None]:
        """Tokenize text and yield tokens."""
        # Convert input text to bytes for hyperscan, with a
        # helper to convert back from a given range.
        text_bytes = text.encode("utf8")

        def get_text(start, end):
            return text_bytes[start:end].decode("utf8")

        # Get all matches. This may include overlaps.
        # Entries in matches are
        # ((start_offset, end_offset), Match, TokenExtractor)
        matches = []

        def on_match(index, start, end, flags, context):
            matches.append(((start, end), None, self.extractors[index]))

        self.hyperscan_db.scan(text_bytes, match_event_handler=on_match)

        # Sort all matches by start offset ascending, then end offset
        # descending. Remove overlaps by iteratively returning only matches
        # where the current start offset is greater than the previously
        # returned end offset:
        matches.sort(key=lambda m: (m[0][0], -m[0][1]))
        offset = 0
        for (start, end), m, extractor in matches:
            if offset > start:
                continue
            if offset < start:
                yield from get_text(offset, start).strip().split()
            # To get match groups, re-run the regex using the
            # builtin regex library.
            m = extractor.compiled_regex.match(get_text(start, end))
            yield extractor.get_token(m)
            offset = end
        if offset < len(text_bytes):
            yield from get_text(offset, None).strip().split()

    @property
    def hyperscan_db(self):
        """Compile extractors into a hyperscan DB. Use a cache file
        if we've compiled this set before."""
        if not hasattr(self, "_db"):
            # import here so the dependency is optional
            import hyperscan  # pylint: disable=import-outside-toplevel

            hyperscan_db = None
            cache = None

            flag_conversion = {re.I: hyperscan.HS_FLAG_CASELESS}

            def convert_flags(re_flags):
                hyperscan_flags = 0
                for re_flag, hyperscan_flag in flag_conversion.items():
                    if re_flags & re_flag:
                        hyperscan_flags |= hyperscan_flag
                return hyperscan_flags

            expressions = [e.regex.encode("utf8") for e in self.extractors]
            # HS_FLAG_SOM_LEFTMOST so hyperscan includes the start offset
            flags = [
                convert_flags(e.flags) | hyperscan.HS_FLAG_SOM_LEFTMOST
                for e in self.extractors
            ]

            if self.cache_dir is not None:
                # Attempt to use cache.
                # Cache key is a hash of all regexes and flags, so we
                # automatically recompile if anything changes.
                fingerprint = hashlib.md5(
                    str(expressions).encode("utf8") + str(flags).encode("utf8")
                ).hexdigest()
                cache_dir = Path(self.cache_dir)
                cache_dir.mkdir(exist_ok=True)
                cache = cache_dir / fingerprint
                if cache.exists():
                    hyperscan_db = hyperscan.loadb(cache.read_bytes())

            if not hyperscan_db:
                # No cache, so compile database.
                hyperscan_db = hyperscan.Database()
                hyperscan_db.compile(expressions=expressions, flags=flags)
                if cache:
                    cache.write_bytes(hyperscan.dumpb(hyperscan_db))

            self._db = hyperscan_db

        return self._db


default_tokenizer = AhocorasickTokenizer()
