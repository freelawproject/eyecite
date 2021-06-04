import hashlib
import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import (
    Any,
    Generator,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)

import ahocorasick
from reporters_db import JOURNALS, LAWS, RAW_REGEX_VARIABLES, REPORTERS
from reporters_db.utils import process_variables, recursive_substitute

from eyecite.models import (
    CitationToken,
    Edition,
    IdToken,
    ParagraphToken,
    Reporter,
    SectionToken,
    StopWordToken,
    SupraToken,
    Token,
    TokenExtractor,
    Tokens,
)
from eyecite.regexes import (
    ID_REGEX,
    PAGE_NUMBER_REGEX,
    PARAGRAPH_REGEX,
    SECTION_REGEX,
    STOP_WORD_REGEX,
    STOP_WORDS,
    SUPRA_REGEX,
    nonalphanum_boundaries_re,
    short_cite_re,
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

    # Set up regex replacement variables from reporters-db
    raw_regex_variables = deepcopy(RAW_REGEX_VARIABLES)
    raw_regex_variables["full_cite"][""] = "$volume $reporter,? $page"
    raw_regex_variables["page"][""] = rf"(?P<page>{PAGE_NUMBER_REGEX})"
    regex_variables = process_variables(raw_regex_variables)

    def _substitute_edition(template, *edition_names):
        """Helper to replace $edition in template with edition_names."""
        edition = "|".join(re.escape(e) for e in edition_names)
        return Template(template).safe_substitute(edition=edition)

    # Extractors step one: add an extractor for each reporter string

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

    def _add_regex(
        kind: str,
        reporters: List[str],
        edition: Edition,
        regex: str,
    ):
        """Helper to generate citations for a reporter
        and insert into editions_by_regex."""
        for reporter in reporters:
            EDITIONS_LOOKUP[reporter].append(edition)
        editions_by_regex[regex][kind].append(edition)

        # add strings
        have_strings = re.escape(reporters[0]) in regex
        if have_strings:
            editions_by_regex[regex]["strings"].update(reporters)

        # add short cite
        short_cite_regex = short_cite_re(regex)
        if short_cite_regex != regex:
            editions_by_regex[short_cite_regex][kind].append(edition)
            editions_by_regex[short_cite_regex]["short"] = True
            if have_strings:
                editions_by_regex[short_cite_regex]["strings"].update(
                    reporters
                )

    def _add_regexes(
        regex_templates: List[str],
        edition_name: str,
        edition: Edition,
        variations: List[str],
    ):
        """Expand regex_templates and add to editions_by_regex."""
        for regex_template in regex_templates:
            regex_template = recursive_substitute(
                regex_template, regex_variables
            )
            regex = _substitute_edition(regex_template, edition_name)
            _add_regex("editions", [edition_name], edition, regex)
            if variations:
                regex = _substitute_edition(regex_template, *variations)
                _add_regex(
                    "variations",
                    variations,
                    edition,
                    regex,
                )

    # add reporters.json:
    for source_key, source_cluster in REPORTERS.items():
        for source in source_cluster:
            reporter_obj = Reporter(
                short_name=source_key,
                name=source["name"],
                cite_type=source["cite_type"],
                source="reporters",
            )
            variations = source["variations"]
            for edition_name, edition_data in source["editions"].items():
                edition = Edition(
                    short_name=edition_name,
                    reporter=reporter_obj,
                    start=edition_data["start"],
                    end=edition_data["end"],
                )
                regex_templates = edition_data.get("regexes") or ["$full_cite"]
                edition_variations = [
                    k for k, v in variations.items() if v == edition_name
                ]
                _add_regexes(
                    regex_templates, edition_name, edition, edition_variations
                )

    # add laws.json
    for source_key, source_cluster in LAWS.items():
        for source in source_cluster:
            reporter_obj = Reporter(
                short_name=source_key,
                name=source["name"],
                cite_type=source["cite_type"],
                source="laws",
            )
            edition = Edition(
                short_name=source_key,
                reporter=reporter_obj,
                start=source["start"],
                end=source["end"],
            )
            regex_templates = source.get("regexes") or ["$full_cite"]
            # handle citation to multiple sections, like
            # "Mass. Gen. Laws ch. 1, §§ 2-3":
            regex_templates = [
                r.replace(r"§ ", r"§§? ?") for r in regex_templates
            ]
            _add_regexes(
                regex_templates,
                source_key,
                edition,
                source.get("variations", []),
            )

    # add journals.json
    for source_key, source_cluster in JOURNALS.items():
        for source in source_cluster:
            reporter_obj = Reporter(
                short_name=source_key,
                name=source["name"],
                cite_type=source["cite_type"],
                source="journals",
            )
            edition = Edition(
                short_name=source_key,
                reporter=reporter_obj,
                start=source["start"],
                end=source["end"],
            )
            regex_templates = source.get("regexes") or ["$full_cite"]
            _add_regexes(
                regex_templates,
                source_key,
                edition,
                source.get("variations", []),
            )

    # Add each regex to EXTRACTORS:
    for regex, cluster in editions_by_regex.items():
        EXTRACTORS.append(
            TokenExtractor(
                nonalphanum_boundaries_re(regex),
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

    EXTRACTORS.extend(
        [
            # Id.
            TokenExtractor(
                ID_REGEX,
                IdToken.from_match,
                flags=re.I,
                strings=["id.", "ibid."],
            ),
            # supra
            TokenExtractor(
                SUPRA_REGEX,
                SupraToken.from_match,
                flags=re.I,
                strings=["supra"],
            ),
            # paragraph
            TokenExtractor(
                PARAGRAPH_REGEX,
                ParagraphToken.from_match,
            ),
            # case name stopwords
            TokenExtractor(
                STOP_WORD_REGEX,
                StopWordToken.from_match,
                flags=re.I,
                strings=STOP_WORDS,
            ),
            # tokens containing section symbols
            TokenExtractor(
                SECTION_REGEX, SectionToken.from_match, strings=["§"]
            ),
        ]
    )


_populate_reporter_extractors()

# Tokenizers


@dataclass
class Tokenizer:
    """A tokenizer takes a list of extractors, and provides a tokenize()
    method to tokenize text using those extractors.
    This base class should be overridden by tokenizers that use a
    more efficient strategy for running all the extractors."""

    extractors: List[TokenExtractor] = field(
        default_factory=lambda: list(EXTRACTORS)
    )

    def tokenize(self, text: str) -> Tuple[Tokens, List[Tuple[int, Token]]]:
        """Tokenize text and return list of all tokens, followed by list of
        just non-string tokens along with their positions in the first list."""
        # Sort all matches by start offset ascending, then end offset
        # descending. Remove overlaps by returning only matches
        # where the current start offset is greater than the previously
        # returned end offset. Also return text between matches.
        citation_tokens = []
        all_tokens: Tokens = []
        tokens = sorted(
            self.extract_tokens(text), key=lambda m: (m.start, -m.end)
        )
        last_token = None
        offset = 0
        for token in tokens:
            if last_token:
                # Sometimes the exact same cite is matched by two different
                # regexes. Attempt to merge rather than discarding one or the
                # other:
                merged = last_token.merge(token)
                if merged:
                    continue
            if offset > token.start:
                # skip overlaps
                continue
            if offset < token.start:
                # capture plain text before each match
                self.append_text(all_tokens, text[offset : token.start])
            # capture match
            citation_tokens.append((len(all_tokens), token))
            all_tokens.append(token)
            offset = token.end
            last_token = token
        # capture plain text after final match
        if offset < len(text):
            self.append_text(all_tokens, text[offset:])
        return all_tokens, citation_tokens

    def get_extractors(self, text: str):
        """Subclasses can override this to filter extractors based on text."""
        return self.extractors

    def extract_tokens(self, text) -> Generator[Token, None, None]:
        """Get all instances where an extractor matches the given text."""
        for extractor in self.get_extractors(text):
            for match in extractor.get_matches(text):
                yield extractor.get_token(match)

    @staticmethod
    def append_text(tokens, text):
        """Split text into words, treating whitespace as a word, and append
        to tokens. NOTE this is a significant portion of total runtime of
        get_citations(), so benchmark if changing.
        """
        for part in text.split(" "):
            if part:
                tokens.extend((part, " "))
            else:
                tokens.append(" ")
        tokens.pop()  # remove final extra space


@dataclass
class AhocorasickTokenizer(Tokenizer):
    """A performance-optimized Tokenizer using the
    pyahocorasick library. Only runs extractors where
    the target text contains one of the strings from
    TokenExtractor.strings."""

    def __post_init__(self):
        """Set up helpers to narrow down possible extractors."""
        # Build a set of all extractors that don't list required strings
        self.unfiltered_extractors = set(
            e for e in EXTRACTORS if not e.strings
        )
        # Build a pyahocorasick filter for all case-sensitive extractors
        self.case_sensitive_filter = self.make_ahocorasick_filter(
            (s, e)
            for e in EXTRACTORS
            if e.strings and not e.flags & re.I
            for s in e.strings
        )
        # Build a pyahocorasick filter for all case-insensitive extractors
        self.case_insensitive_filter = self.make_ahocorasick_filter(
            (s.lower(), e)
            for e in EXTRACTORS
            if e.strings and e.flags & re.I
            for s in e.strings
        )

    def get_extractors(self, text: str) -> Set[TokenExtractor]:
        """Override get_extractors() to filter out extractors
        that can't possibly match."""
        unique_extractors = set(self.unfiltered_extractors)
        for _, extractors in self.case_sensitive_filter.iter(text):
            unique_extractors.update(extractors)
        for _, extractors in self.case_insensitive_filter.iter(text.lower()):
            unique_extractors.update(extractors)
        return unique_extractors

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
class HyperscanTokenizer(Tokenizer):
    """A performance-optimized Tokenizer using the
    hyperscan library. Precompiles a database of all
    extractors and runs them in a single pass through
    the target text."""

    # Precompiling the database takes several seconds.
    # To avoid that, provide a cache directory writeable
    # only by this user where the precompiled database
    # can be stored.
    cache_dir: Optional[str] = None

    def extract_tokens(self, text) -> Generator[Token, None, None]:
        """Extract tokens via hyperscan."""
        # Get all matches, with byte offsets because hyperscan uses
        # bytes instead of unicode:
        text_bytes = text.encode("utf8")
        matches = []

        def on_match(index, start, end, flags, context):
            matches.append((self.extractors[index], (start, end)))

        self.hyperscan_db.scan(text_bytes, match_event_handler=on_match)

        # Build a lookup table of byte offset -> str offset for all of the
        # matches we found. Stepping through offsets in sorted order avoids
        # having to decode each part of the string more than once:
        byte_to_str_offset = {}
        last_byte_offset = 0
        str_offset = 0
        byte_offsets = sorted(set(i for m in matches for i in m[1]))
        for byte_offset in byte_offsets:
            try:
                str_offset += len(
                    text_bytes[last_byte_offset:byte_offset].decode("utf8")
                )
            except UnicodeDecodeError:
                # offsets will fail to decode for invalid regex matches
                # that don't align with a unicode character
                continue
            byte_to_str_offset[byte_offset] = str_offset
            last_byte_offset = byte_offset

        # Narrow down our matches to only those that successfully decoded,
        # re-run regex against just the matching strings to get match groups
        # (which aren't provided by hyperscan), and tokenize:
        for extractor, (start, end) in matches:
            if start in byte_to_str_offset and end in byte_to_str_offset:
                start = byte_to_str_offset[start]
                end = byte_to_str_offset[end]
                m = extractor.compiled_regex.match(text[start:end])
                yield extractor.get_token(m, offset=start)

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

            def convert_regex(regex):
                # hyperscan doesn't understand repetition flags like {,3},
                # so replace with {0,3}:
                regex = re.sub(r"\{,(\d+)\}", r"{0,\1}", regex)
                # Characters like "§" convert to more than one byte in utf8,
                # so "§?" won't work as expected. Convert "§?" to "(?:§)?":
                long_chars = [c for c in regex if len(c.encode("utf8")) > 1]
                if long_chars:
                    regex = re.sub(
                        rf'([{"".join(set(long_chars))}])\?', r"(?:\1)?", regex
                    )
                # encode as bytes:
                return regex.encode("utf8")

            expressions = [convert_regex(e.regex) for e in self.extractors]
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
