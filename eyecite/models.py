import logging
import re
from collections import UserString
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import (
    Any,
    Optional,
    cast,
)

from eyecite import clean_text
from eyecite.annotate import SpanUpdater
from eyecite.utils import REPORTERS_THAT_NEED_PAGE_CORRECTION, hash_sha256

logger = logging.getLogger(__name__)

ResourceType = Hashable


@dataclass(eq=True, frozen=True)
class Reporter:
    """Class for top-level reporters in `reporters_db`, like "S.W." """

    short_name: str
    name: str
    cite_type: str
    source: str  # one of "reporters", "laws", "journals"
    is_scotus: bool = False

    def __post_init__(self):
        if (
            self.cite_type == "federal" and "supreme" in self.name.lower()
        ) or "scotus" in self.cite_type.lower():
            # use setattr because this class is frozen
            object.__setattr__(self, "is_scotus", True)


@dataclass(eq=True, frozen=True)
class Edition:
    """Class for individual editions in `reporters_db`,
    like "S.W." and "S.W.2d"."""

    reporter: Reporter
    short_name: str
    start: datetime | None
    end: datetime | None

    def includes_year(
        self,
        year: int,
    ) -> bool:
        """Return True if edition contains cases for the given year."""
        return (
            year <= datetime.now().year
            and (self.start is None or self.start.year <= year)
            and (self.end is None or self.end.year >= year)
        )


@dataclass(eq=False, unsafe_hash=False)
class CitationBase:
    """Base class for objects returned by `eyecite.find.get_citations`. We
    define several subclasses of this class below, representing the various
    types of citations that might exist."""

    token: "Token"  # token this citation came from
    index: int  # index of _token in the token list
    # span() overrides
    span_start: int | None = None
    span_end: int | None = None
    full_span_start: int | None = None
    full_span_end: int | None = None
    groups: dict = field(default_factory=dict)
    metadata: Any = None
    document: Optional["Document"] = None

    def __post_init__(self):
        """Set up groups and metadata."""
        # Allow groups to be used in comparisons:
        self.groups = self.token.groups
        # Make metadata a self.Metadata object:
        self.metadata = (
            self.Metadata(**self.metadata)
            if isinstance(self.metadata, dict)
            else self.Metadata()
        )
        # Set known missing page numbers to None
        if re.search("^_+$", self.groups.get("page", "") or ""):
            self.groups["page"] = None

    def __repr__(self):
        """Simplified repr() to be more readable than full dataclass repr().
        Just shows 'FullCaseCitation("matched text", groups=...)'."""
        return (
            f"{self.__class__.__name__}("
            + f"{repr(self.matched_text())}"
            + (f", groups={repr(self.groups)}" if self.groups else "")
            + f", metadata={repr(self.metadata)}"
            + ")"
        )

    def __hash__(self) -> int:
        """In general, citations are considered equivalent if they have the
        same group values (i.e., the same regex group content that is extracted
        from the matched text). Subclasses may override this method in order to
        specify equivalence behavior that is more appropriate for certain
        kinds of citations (e.g., see CaseCitation override).

        self.groups typically contains different keys for different objects:

        FullLawCitation (non-exhaustive and non-guaranteed):
        - chapter
        - reporter
        - law_section
        - issue
        - page
        - docket_number
        - pamphlet
        - title

        FullJournalCitation (non-exhaustive and non-guaranteed):
        - volume
        - reporter
        - page

        FullCaseCitation (see CaseCitation.__hash__() notes)
        """
        return hash(
            hash_sha256(
                {**dict(self.groups.items()), **{"class": type(self).__name__}}
            )
        )

    def __eq__(self, other):
        """This method is inherited by all subclasses and should not be
        overridden. It implements object equality in exactly the same way as
        defined in an object's __hash__() function, which should be overridden
        instead if desired.
        """
        return self.__hash__() == other.__hash__()

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata:
        """Define fields on self.metadata."""

        parenthetical: str | None = None
        pin_cite: str | None = None
        pin_cite_span_start: int | None = None
        pin_cite_span_end: int | None = None

    def corrected_citation(self):
        """Return citation with any variations normalized."""
        return self.matched_text()

    def corrected_citation_full(self):
        """Return citation with any variations normalized, including extracted
        metadata if any."""
        return self.matched_text()

    def dump(self) -> dict:
        """Return citation data for printing by dump_citations."""
        return {
            "groups": self.groups,
            "metadata": {
                k: v
                for k, v in self.metadata.__dict__.items()
                if v is not None
            },
        }

    def matched_text(self):
        """Text that identified this citation, such as '1 U.S. 1' or 'Id.'"""
        return str(self.token)

    def span(self):
        """Start and stop offsets in source text for matched_text()."""
        return (
            (
                self.span_start
                if self.span_start is not None
                else self.token.start
            ),
            self.span_end if self.span_end is not None else self.token.end,
        )

    def span_with_pincite(self) -> tuple[int, int]:
        """Start and stop offsets in source text for pin cites."""
        start = min(
            list(
                filter(
                    lambda v: v is not None,
                    [
                        self.metadata.pin_cite_span_start,
                        self.span_start,
                        self.token.start,
                    ],
                )
            ),
            default=self.token.start,
        )

        end = max(
            list(
                filter(
                    lambda v: v is not None,
                    [
                        self.metadata.pin_cite_span_end,
                        self.token.end,
                        self.span_end,
                    ],
                )
            ),
            default=self.token.end,
        )

        return (start, end)

    def full_span(self) -> tuple[int, int]:
        """Span indices that fully cover the citation

        Start and stop offsets in source text for full citation text (including
        plaintiff, defendant, post citation, ...)

        Relevant for FullCaseCitation, FullJournalCitation and FullLawCitation.

        :returns: Tuple of start and end indicies
        """
        start = self.full_span_start
        if start is None:
            start = self.span()[0]

        end = self.full_span_end
        if end is None:
            end = self.span()[1]

        return start, end


@dataclass(eq=False, unsafe_hash=False, repr=False)
class ResourceCitation(CitationBase):
    """Base class for a case, law, or journal citation. Could be short or
    long."""

    # Editions that might match this reporter string
    exact_editions: Sequence[Edition] = field(default_factory=tuple)
    variation_editions: Sequence[Edition] = field(default_factory=tuple)
    all_editions: Sequence[Edition] = field(default_factory=tuple)
    edition_guess: Edition | None = None

    # year extracted from metadata["year"] and converted to int,
    # if in a valid range
    year: int | None = None

    def __post_init__(self):
        """Make iterables into tuples to make sure we're hashable."""
        self.exact_editions = tuple(self.exact_editions)
        self.variation_editions = tuple(self.variation_editions)
        self.all_editions = tuple(self.exact_editions) + tuple(
            self.variation_editions
        )
        super().__post_init__()

    def __hash__(self) -> int:
        """ResourceCitation objects are hashed in the same way as their
        parent class (CitationBase) objects, except that we also take into
        consideration the all_editions field.
        """
        return hash(
            hash_sha256(
                {
                    **dict(self.groups.items()),
                    **{
                        "all_editions": sorted(
                            [asdict(e) for e in self.all_editions],
                            key=lambda d: d["short_name"],  # type: ignore
                        ),
                        "class": type(self).__name__,
                    },
                }
            )
        )

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CitationBase.Metadata):
        """Define fields on self.metadata."""

        year: str | None = None
        month: str | None = None
        day: str | None = None

    def add_metadata(self, document: "Document"):
        """Extract metadata from text before and after citation."""
        self.guess_edition()

    def dump(self) -> dict:
        """Return citation data for printing by dump_citations."""
        return {
            **super().dump(),
            "year": self.year,
        }

    def corrected_reporter(self):
        """Get official reporter string from edition_guess, if possible."""
        return (
            self.edition_guess.short_name
            if self.edition_guess
            else self.groups["reporter"]
        )

    def corrected_citation(self):
        """Return citation with corrected reporter and standardized page"""
        corrected = self.matched_text()
        if self.edition_guess:
            corrected = corrected.replace(
                self.groups.get("reporter"), self.edition_guess.short_name
            )

        corrected_page = self.corrected_page()
        if corrected_page and corrected_page != self.groups["page"]:
            corrected = corrected.replace(self.groups["page"], corrected_page)

        return corrected

    def corrected_page(self):
        """Can we standardize a page value?"""
        page = self.groups.get("page")
        if page is None:
            return

        standard_reporter = ""
        if reporter := self.groups.get("reporter"):
            if self.edition_guess:
                standard_reporter = self.edition_guess.short_name
            if {
                reporter,
                standard_reporter,
            } & REPORTERS_THAT_NEED_PAGE_CORRECTION:
                return page.replace("[U]", "(U)").replace("[A]", "(A)")

        return page

    def guess_edition(self):
        """Set edition_guess."""
        # Use exact matches if possible, otherwise try variations
        editions = self.exact_editions or self.variation_editions
        if not editions:
            return

        # Attempt resolution by date
        if len(editions) > 1 and self.year:
            editions = [e for e in editions if e.includes_year(self.year)]

        if len(editions) == 1:
            self.edition_guess = editions[0]


@dataclass(eq=False, unsafe_hash=False, repr=False)
class FullCitation(ResourceCitation):
    """Abstract base class indicating that a citation fully identifies a
    resource."""


@dataclass(eq=False, unsafe_hash=False, repr=False)
class FullLawCitation(FullCitation):
    """Citation to a source from `reporters_db/laws.json`."""

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(FullCitation.Metadata):
        """Define fields on self.metadata."""

        publisher: str | None = None
        day: str | None = None
        month: str | None = None

    def add_metadata(self, document: "Document"):
        """Extract metadata from text before and after citation."""
        # pylint: disable=import-outside-toplevel
        from eyecite.helpers import add_law_metadata

        add_law_metadata(self, document.words)
        super().add_metadata(document)

    def corrected_citation_full(self):
        """Return citation with any variations normalized, including extracted
        metadata if any."""
        parts = [self.corrected_citation()]
        m = self.metadata
        if m.pin_cite:
            parts.append(f"{m.pin_cite}")
        publisher_date = " ".join(
            i for i in (m.publisher, m.month, m.day, m.year) if i
        )
        if publisher_date:
            parts.append(f" ({publisher_date})")
        if m.parenthetical:
            parts.append(f" ({m.parenthetical})")
        return "".join(parts)


@dataclass(eq=False, unsafe_hash=False, repr=False)
class FullJournalCitation(FullCitation):
    """Citation to a source from `reporters_db/journals.json`."""

    def add_metadata(self, document: "Document"):
        """Extract metadata from text before and after citation."""
        # pylint: disable=import-outside-toplevel
        from eyecite.helpers import add_journal_metadata

        add_journal_metadata(self, document.words)
        super().add_metadata(document)

    def corrected_citation_full(self):
        """Return citation with any variations normalized, including extracted
        metadata if any."""
        parts = [self.corrected_citation()]
        m = self.metadata
        if m.pin_cite:
            parts.append(f", {m.pin_cite}")
        if m.year:
            parts.append(f" ({m.year})")
        if m.parenthetical:
            parts.append(f" ({m.parenthetical})")
        return "".join(parts)


@dataclass(eq=False, unsafe_hash=False, repr=False)
class CaseCitation(ResourceCitation):
    """Convenience class which represents a single citation found in a
    document.
    """

    def __hash__(self) -> int:
        """CaseCitation objects that have the same volume, reporter, and page
        are considered equivalent, unless the citation is missing a page, in
        which case the object's hash will be unique for safety.

        self.groups for CaseCitation objects usually contains these keys:
        - page (guaranteed here: https://github.com/freelawproject/reporters-db/blob/main/tests.py#L129)  # noqa: E501
        - reporter (guaranteed here: https://github.com/freelawproject/reporters-db/blob/main/tests.py#L129)  # noqa: E501
        - volume (almost always present, but some tax court citations don't have volumes)  # noqa: E501
        - reporter_nominative (sometimes)
        - volumes_nominative (sometimes)
        """
        if self.groups["page"] is None:
            return id(self)
        else:
            return hash(
                hash_sha256(
                    {
                        **{
                            k: self.groups[k]
                            for k in ["volume", "page"]
                            if k in self.groups
                        },
                        **{
                            "reporter": self.corrected_reporter(),
                            "class": type(self).__name__,
                        },
                    }
                )
            )

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(FullCitation.Metadata):
        """Define fields on self.metadata."""

        # court is included for ShortCaseCitation as well. It won't appear in
        # the cite itself but can also be guessed from the reporter
        court: str | None = None

    def guess_court(self):
        """Set court based on reporter."""
        if not self.metadata.court and any(
            e.reporter.is_scotus for e in self.all_editions
        ):
            self.metadata.court = "scotus"


@dataclass(eq=False, unsafe_hash=False, repr=False)
class FullCaseCitation(CaseCitation, FullCitation):
    """Convenience class which represents a standard, fully named citation,
    i.e., the kind of citation that marks the first time a document is cited.

    Example:
    ```
    Adarand Constructors, Inc. v. Peña, 515 U.S. 200, 240
    Peña at 222, 515 U.S. 200
    ```
    """

    def is_parallel_citation(self, preceding: CaseCitation):
        """Check if preceding citation is parallel

        Args:
            preceding (): The previous citation found

        Returns: None
        """
        if self.full_span_start == preceding.full_span_start:
            # if parallel get plaintiff/defendant data from
            # the earlier citation, since it won't be on the
            # parallel one.
            self.metadata.defendant = preceding.metadata.defendant
            self.metadata.plaintiff = preceding.metadata.plaintiff
            # California style may have a year prior to citation; merge as well
            self.metadata.year = preceding.metadata.year
            self.year = preceding.year

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CaseCitation.Metadata):
        """Define fields on self.metadata."""

        plaintiff: str | None = None
        defendant: str | None = None
        extra: str | None = None
        antecedent_guess: str | None = None
        # May be populated after citation resolution
        resolved_case_name_short: str | None = None
        resolved_case_name: str | None = None

    def add_metadata(self, document: "Document"):
        """Extract metadata from text before and after citation."""
        # pylint: disable=import-outside-toplevel
        from eyecite.helpers import (
            add_post_citation,
            add_pre_citation,
            find_case_name,
            find_case_name_in_html,
        )

        add_post_citation(self, document.words)

        if document.markup_text:
            find_case_name_in_html(self, document)
            if self.metadata.defendant is None:
                find_case_name(self, document)

        else:
            find_case_name(self, document)

        add_pre_citation(self, document)
        self.guess_court()
        super().add_metadata(document)

    def corrected_citation_full(self):
        """Return formatted version of extracted cite."""
        parts = []
        m = self.metadata
        if m.plaintiff:
            parts.append(f"{m.plaintiff} v. ")
        if m.defendant:
            parts.append(f"{m.defendant}, ")
        parts.append(self.corrected_citation())
        if m.pin_cite:
            parts.append(f", {m.pin_cite}")
        if m.extra:
            parts.append(m.extra)
        publisher_date = " ".join(i for i in (m.court, m.year) if i)
        if publisher_date:
            parts.append(f" ({publisher_date})")
        if m.parenthetical:
            parts.append(f" ({m.parenthetical})")
        return "".join(parts)


@dataclass(eq=False, unsafe_hash=False, repr=False)
class ShortCaseCitation(CaseCitation):
    """Convenience class which represents a short form citation, i.e., the kind
    of citation made after a full citation has already appeared. This kind of
    citation lacks a full case name and usually has a different page number
    than the canonical citation.

    Examples:
    ```
    Adarand, 515 U.S., at 241
    Adarand, 515 U.S. at 241
    515 U.S., at 241
    ```
    """

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CaseCitation.Metadata):
        """Define fields on self.metadata."""

        antecedent_guess: str | None = None

    def corrected_citation_full(self):
        """Return formatted version of extracted cite."""
        parts = []
        if self.metadata.antecedent_guess:
            parts.append(f"{self.metadata.antecedent_guess}, ")
        parts.append(self.corrected_citation())
        return "".join(parts)


@dataclass(eq=False, unsafe_hash=False, repr=False)
class SupraCitation(CitationBase):
    """Convenience class which represents a 'supra' citation, i.e., a citation
    to something that is above in the document. Like a short form citation,
    this kind of citation lacks a full case name and usually has a different
    page number than the canonical citation.


    Examples:
    ```
    Adarand, supra, at 240
    Adarand, 515 supra, at 240
    Adarand, supra, somethingelse
    Adarand, supra. somethingelse
    ```
    """

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CitationBase.Metadata):
        """Define fields on self.metadata."""

        antecedent_guess: str | None = None
        volume: str | None = None

    def formatted(self):
        """Return formatted version of extracted cite."""
        parts = []
        m = self.metadata
        if m.antecedent_guess:
            parts.append(f"{m.antecedent_guess}, ")
        if m.volume:
            parts.append(f"{m.volume} ")
        parts.append("supra")
        if m.pin_cite:
            parts.append(f", {m.pin_cite}")
        return "".join(parts)


@dataclass(eq=False, unsafe_hash=False, repr=False)
class IdCitation(CitationBase):
    """Convenience class which represents an 'id' or 'ibid' citation, i.e., a
    citation to the document referenced immediately prior. An 'id' citation is
    unlike a regular citation object since it has no knowledge of its reporter,
    volume, or page. Instead, the only helpful information that this reference
    possesses is a record of the pin cite after the 'id' token.

    Example: "... foo bar," id., at 240
    """

    def __hash__(self) -> int:
        """IdCitation objects are always considered unique for safety."""
        return id(self)

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CitationBase.Metadata):
        """Define fields on self.metadata."""

        pass

    def formatted(self):
        """Return formatted version of extracted cite."""
        parts = ["id."]
        if self.metadata.pin_cite:
            parts.append(f", {self.metadata.pin_cite}")
        return "".join(parts)


@dataclass(eq=False, unsafe_hash=False, repr=False)
class ReferenceCitation(CitationBase):
    """A reference citation is a citation that refers to
    a full case citation by name and pincite alone.

    Future versions hopefully with drop the pincite requirement

    Examples:
    Roe at 240
    """

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CitationBase.Metadata):
        """Define fields on self.metadata."""

        plaintiff: str | None = None
        defendant: str | None = None
        resolved_case_name_short: str | None = None
        resolved_case_name: str | None = None

    name_fields = [
        "plaintiff",
        "defendant",
        "resolved_case_name_short",
        "resolved_case_name",
    ]


@dataclass(eq=False, unsafe_hash=False, repr=False)
class UnknownCitation(CitationBase):
    """Convenience class which represents an unknown citation. A recognized
    citation should theoretically be parsed as a CaseCitation, FullLawCitation,
    or a FullJournalCitation. If it's something else, this class serves as
    a naive catch-all.
    """

    def __hash__(self) -> int:
        """UnknownCitation objects are always considered unique for safety."""
        return id(self)


@dataclass(eq=True, unsafe_hash=True)
class Token(UserString):
    """Base class for special tokens. For performance, this isn't used
    for generic words."""

    data: str
    start: int
    end: int
    groups: dict = field(default_factory=dict, compare=False)

    @classmethod
    def from_match(cls, m, extra, offset=0) -> "Token":
        """Return a token object based on a regular expression match.
        This gets called by TokenExtractor. By default, just use the
        entire matched string."""
        start, end = m.span(1)
        # ignore "too many arguments" type error -- this is called
        # by subclasses with additional attributes
        return cls(  # type: ignore[call-arg]
            m[1], start + offset, end + offset, groups=m.groupdict(), **extra
        )

    def merge(self, other: "Token") -> Optional["Token"]:
        """Merge two tokens, by returning self if other is identical to
        self."""
        if (
            self.start == other.start
            and self.end == other.end
            and type(self) is type(other)
            and self.groups == other.groups
        ):
            return self
        return None


# For performance, lists of tokens can include either Token subclasses
# or bare strings (the typical case of words that aren't
# related to citations)
TokenOrStr = Token | str
Tokens = list[TokenOrStr]


@dataclass(eq=True, unsafe_hash=True)
class CitationToken(Token):
    """String matching a citation regex from `reporters_db/reporters.json`."""

    exact_editions: Sequence[Edition] = field(default_factory=tuple)
    variation_editions: Sequence[Edition] = field(default_factory=tuple)
    short: bool = False

    def __post_init__(self):
        """Make iterables into tuples to make sure we're hashable."""
        self.exact_editions = tuple(self.exact_editions)
        self.variation_editions = tuple(self.variation_editions)

    def merge(self, other: "Token") -> Optional["Token"]:
        """To merge citation tokens, also make sure `short` matches,
        and combine their editions."""
        merged = super().merge(other)
        if merged:
            other = cast(CitationToken, other)
            if self.short == other.short:
                self.exact_editions = cast(tuple, self.exact_editions) + cast(
                    tuple, other.exact_editions
                )
                self.variation_editions = cast(
                    tuple, self.variation_editions
                ) + cast(tuple, other.variation_editions)
                # Remove duplicate editions after merge
                self.exact_editions = tuple(set(self.exact_editions))
                self.variation_editions = tuple(set(self.variation_editions))
                return self
        return None


@dataclass(eq=True, unsafe_hash=True)
class SectionToken(Token):
    """Word containing a section symbol."""


@dataclass(eq=True, unsafe_hash=True)
class SupraToken(Token):
    """Word matching "supra" with or without punctuation."""


@dataclass(eq=True, unsafe_hash=True)
class IdToken(Token):
    """Word matching "id" or "ibid"."""


@dataclass(eq=True, unsafe_hash=True)
class ParagraphToken(Token):
    """Word matching a break between paragraphs."""


@dataclass(eq=True, unsafe_hash=True)
class StopWordToken(Token):
    """Word matching one of the STOP_TOKENS."""


@dataclass(eq=True, unsafe_hash=True)
class PlaceholderCitationToken(Token):
    """Placeholder Citation Tokens."""


@dataclass(eq=True, unsafe_hash=True)
class CaseReferenceToken(Token):
    """Word matching plaintiff or defendant in a full case citation"""


@dataclass
class TokenExtractor:
    """Class for extracting all matches from a given string for the given
    regex, and then for returning Token objects for all matches."""

    regex: str
    # constructor should be Callable[[re.Match, dict, int], Token]
    # but this issue makes it inconvenient to specify the input types:
    # https://github.com/python/mypy/issues/5485
    constructor: Callable[..., Token]
    extra: dict = field(default_factory=dict)
    flags: int = 0
    strings: list = field(default_factory=list)

    def get_matches(self, text):
        """Return match objects for all matches in text."""
        return self.compiled_regex.finditer(text)

    def get_token(self, m, offset=0) -> Token:
        """For a given match object, return a Token."""
        return self.constructor(m, self.extra, offset)

    def __hash__(self):
        """This needs to be hashable so we can remove redundant
        extractors returned by the pyahocorasick filter."""
        return hash(repr(self))

    @property
    def compiled_regex(self):
        """Cache compiled regex as a property."""
        if not hasattr(self, "_compiled_regex"):
            self._compiled_regex = re.compile(self.regex, flags=self.flags)
        return self._compiled_regex


@dataclass(frozen=True)
class Resource(ResourceType):
    """Thin resource class representing an object to which a citation can be
    resolved. See `eyecite.resolve` for more details."""

    citation: FullCitation

    def __hash__(self):
        """Resources are the same if their citations are semantically
        equivalent, as defined by their hash function.

        Note: Resources composed of citations with missing page numbers are
        NOT considered the same, even if their other attributes are identical.
        This is to avoid potential false positives.
        """
        return hash(
            hash_sha256(
                {
                    "citation": hash(self.citation),
                    "class": type(self).__name__,
                }
            )
        )

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()


@dataclass(eq=False, unsafe_hash=False)
class Document:
    """A class to encapsulate the source text and the pre-processing applied to
    it before citation parsing

    If the source text comes from `markup_text`, SpanUpdater objects are
    created to help on citation parsing
    """

    plain_text: str = ""
    markup_text: str | None = ""
    citation_tokens: list[tuple[int, Token]] = field(default_factory=list)
    words: Tokens = field(default_factory=list)
    plain_to_markup: SpanUpdater | None = field(default=None, init=False)
    markup_to_plain: SpanUpdater | None = field(default=None, init=False)
    clean_steps: Iterable[str | Callable[[str], str]] | None = field(
        default_factory=list
    )
    emphasis_tags: list[tuple[str, int, int]] = field(default_factory=list)
    source_text: str = ""  # will be useful for the annotation step

    def __post_init__(self):
        from eyecite.utils import placeholder_markup

        if self.plain_text and not self.markup_text:
            self.source_text = self.plain_text
            if self.clean_steps:
                self.plain_text = clean_text(self.plain_text, self.clean_steps)

        elif self.markup_text and not self.plain_text:
            self.source_text = self.markup_text

            if "html" not in self.clean_steps:
                self.clean_steps.insert("html", 0)
                logger.warning(
                    "`html` has been added to `markup_text` clean_steps list"
                )

            self.plain_text = clean_text(self.markup_text, self.clean_steps)

            # Replace original tags (including their attributes) with same‐length placeholders
            # so that SpanUpdater’s offset calculations remain correct and aren’t skewed by
            # attribute characters (e.g., in id or index). ex. <span> <XXXX>
            placeholder_markup = placeholder_markup(self.markup_text)

            self.plain_to_markup = SpanUpdater(
                self.plain_text, placeholder_markup
            )
            self.markup_to_plain = SpanUpdater(
                self.markup_text, self.plain_text
            )

            self.identify_emphasis_tags()

        elif not self.markup_text and not self.plain_text:
            raise ValueError("Both `markup_text` and `plain_text` are empty")

        elif self.plain_text and self.markup_text:
            # both arguments were passed, we assume that `plain_text` is the
            # cleaned version of `markup_text`
            if self.clean_steps:
                raise ValueError(
                    "Both `markup_text` and `plain_text` were passed. "
                    "Not clear which to apply `clean_steps` to"
                )

            self.source_text = self.markup_text

    def identify_emphasis_tags(self):
        pattern = re.compile(
            r"<(em|i)[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL
        )
        self.emphasis_tags = [
            (m.group(2).strip(), m.start(), m.end())
            for m in pattern.finditer(self.markup_text)
        ]

    def tokenize(self, tokenizer):
        """Tokenize the document and store the results in the document
        object"""
        self.words, self.citation_tokens = tokenizer.tokenize(self.plain_text)
