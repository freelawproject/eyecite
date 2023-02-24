import re
from collections import UserString
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Hashable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from eyecite.utils import HashableDict

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
    start: Optional[datetime]
    end: Optional[datetime]

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


@dataclass(eq=True, unsafe_hash=True)
class CitationBase:
    """Base class for objects returned by `eyecite.find.get_citations`. We
    define several subclasses of this class below, representing the various
    types of citations that might exist."""

    token: "Token"  # token this citation came from
    index: int  # index of _token in the token list
    # span() overrides
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    full_span_start: Optional[int] = None
    full_span_end: Optional[int] = None
    groups: dict = field(default_factory=dict)
    metadata: Any = None

    def __post_init__(self):
        """Set up groups and metadata."""
        # Allow groups to be used in comparisons:
        self.groups = HashableDict(self.token.groups)
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

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata:
        """Define fields on self.metadata."""

        parenthetical: Optional[str] = None

    def comparison_hash(self) -> int:
        """Return hash that will be the same if two cites are semantically
        equivalent, unless the citation is a CaseCitation missing a page.
        """
        if isinstance(self, CaseCitation) and self.groups["page"] is None:
            return id(self)
        else:
            return hash((type(self), tuple(self.groups.items())))

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
            self.span_start
            if self.span_start is not None
            else self.token.start,
            self.span_end if self.span_end is not None else self.token.end,
        )

    def full_span(self) -> Tuple[int, int]:
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


@dataclass(eq=True, unsafe_hash=True, repr=False)
class ResourceCitation(CitationBase):
    """Base class for a case, law, or journal citation. Could be short or
    long."""

    # Editions that might match this reporter string
    exact_editions: Sequence[Edition] = field(default_factory=tuple)
    variation_editions: Sequence[Edition] = field(default_factory=tuple)
    all_editions: Sequence[Edition] = field(default_factory=tuple)
    edition_guess: Optional[Edition] = None

    # year extracted from metadata["year"] and converted to int,
    # if in a valid range
    year: Optional[int] = None

    def __post_init__(self):
        """Make iterables into tuples to make sure we're hashable."""
        self.exact_editions = tuple(self.exact_editions)
        self.variation_editions = tuple(self.variation_editions)
        self.all_editions = tuple(self.exact_editions) + tuple(
            self.variation_editions
        )
        super().__post_init__()

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CitationBase.Metadata):
        """Define fields on self.metadata."""

        pin_cite: Optional[str] = None
        year: Optional[str] = None

    def comparison_hash(self) -> int:
        """Return hash that will be the same if two cites are semantically
        equivalent."""
        return hash((super().comparison_hash(), self.all_editions))

    def add_metadata(self, words: "Tokens"):
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
        """Return citation with corrected reporter."""
        if self.edition_guess:
            return self.matched_text().replace(
                self.groups["reporter"], self.edition_guess.short_name
            )
        return self.matched_text()

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


@dataclass(eq=True, unsafe_hash=True, repr=False)
class FullCitation(ResourceCitation):
    """Abstract base class indicating that a citation fully identifies a
    resource."""


@dataclass(eq=True, unsafe_hash=True, repr=False)
class FullLawCitation(FullCitation):
    """Citation to a source from `reporters_db/laws.json`."""

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(FullCitation.Metadata):
        """Define fields on self.metadata."""

        publisher: Optional[str] = None
        day: Optional[str] = None
        month: Optional[str] = None

    def add_metadata(self, words: "Tokens"):
        """Extract metadata from text before and after citation."""
        # pylint: disable=import-outside-toplevel
        from eyecite.helpers import add_law_metadata

        add_law_metadata(self, words)
        super().add_metadata(words)

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


@dataclass(eq=True, unsafe_hash=True, repr=False)
class FullJournalCitation(FullCitation):
    """Citation to a source from `reporters_db/journals.json`."""

    def add_metadata(self, words: "Tokens"):
        """Extract metadata from text before and after citation."""
        # pylint: disable=import-outside-toplevel
        from eyecite.helpers import add_journal_metadata

        add_journal_metadata(self, words)
        super().add_metadata(words)

    def corrected_citation_full(self):
        """Return citation with any variations normalized, including extracted
        metadata if any."""
        parts = [self.corrected_citation()]
        m = self.metadata
        if m.pin_cite:
            parts.append(f", {m.pin_cite}")
        if m.year:
            parts.append(f" ({m.year}")
        if m.parenthetical:
            parts.append(f" ({m.parenthetical})")
        return "".join(parts)


@dataclass(eq=True, unsafe_hash=True, repr=False)
class CaseCitation(ResourceCitation):
    """Convenience class which represents a single citation found in a
    document.
    """

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(FullCitation.Metadata):
        """Define fields on self.metadata."""

        # court is included for ShortCaseCitation as well. It won't appear in
        # the cite itself but can also be guessed from the reporter
        court: Optional[str] = None

    def guess_court(self):
        """Set court based on reporter."""
        if not self.metadata.court and any(
            e.reporter.is_scotus for e in self.all_editions
        ):
            self.metadata.court = "scotus"


@dataclass(eq=True, unsafe_hash=True, repr=False)
class FullCaseCitation(CaseCitation, FullCitation):
    """Convenience class which represents a standard, fully named citation,
    i.e., the kind of citation that marks the first time a document is cited.

    Example:
    ```
    Adarand Constructors, Inc. v. Peña, 515 U.S. 200, 240
    ```
    """

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CaseCitation.Metadata):
        """Define fields on self.metadata."""

        plaintiff: Optional[str] = None
        defendant: Optional[str] = None
        extra: Optional[str] = None

    def add_metadata(self, words: "Tokens"):
        """Extract metadata from text before and after citation."""
        # pylint: disable=import-outside-toplevel
        from eyecite.helpers import add_defendant, add_post_citation

        add_post_citation(self, words)
        add_defendant(self, words)
        self.guess_court()
        super().add_metadata(words)

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
            parts.append(f" ({publisher_date}")
        if m.parenthetical:
            parts.append(f" ({m.parenthetical})")
        return "".join(parts)


@dataclass(eq=True, unsafe_hash=True, repr=False)
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

        antecedent_guess: Optional[str] = None

    def corrected_citation_full(self):
        """Return formatted version of extracted cite."""
        parts = []
        if self.metadata.antecedent_guess:
            parts.append(f"{self.metadata.antecedent_guess}, ")
        parts.append(self.corrected_citation())
        return "".join(parts)


@dataclass(eq=True, unsafe_hash=True, repr=False)
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

        antecedent_guess: Optional[str] = None
        pin_cite: Optional[str] = None
        volume: Optional[str] = None

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


@dataclass(eq=True, unsafe_hash=True, repr=False)
class IdCitation(CitationBase):
    """Convenience class which represents an 'id' or 'ibid' citation, i.e., a
    citation to the document referenced immediately prior. An 'id' citation is
    unlike a regular citation object since it has no knowledge of its reporter,
    volume, or page. Instead, the only helpful information that this reference
    possesses is a record of the pin cite after the 'id' token.

    Example: "... foo bar," id., at 240
    """

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CitationBase.Metadata):
        """Define fields on self.metadata."""

        pin_cite: Optional[str] = None

    def formatted(self):
        """Return formatted version of extracted cite."""
        parts = ["id."]
        if self.metadata.pin_cite:
            parts.append(f", {self.metadata.pin_cite}")
        return "".join(parts)


@dataclass(eq=True, unsafe_hash=True, repr=False)
class UnknownCitation(CitationBase):
    """Convenience class which represents an unknown citation. A recognized
    citation should theoretically be parsed as a CaseCitation, FullLawCitation,
    or a FullJournalCitation. If it's something else, this class serves as
    a naive catch-all.
    """


def NonopinionCitation(*args, **kwargs):
    from warnings import warn

    warn(
        """NonopinionCitation will be deprecated in eyecite 2.5.0.
        Please use UnknownCitation instead.""",
        DeprecationWarning,
    )
    return UnknownCitation(*args, **kwargs)


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
TokenOrStr = Union[Token, str]
Tokens = List[TokenOrStr]


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


@dataclass
class TokenExtractor:
    """Class for extracting all matches from a given string for the given
    regex, and then for returning Token objects for all matches."""

    regex: str
    # constructor should be Callable[[re.Match, dict, int], Token]
    # but this issue makes it inconvenient to specify the input types:
    # https://github.com/python/mypy/issues/5485
    constructor: Callable[..., Token]
    extra: Dict = field(default_factory=dict)
    flags: int = 0
    strings: List = field(default_factory=list)

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
        equivalent.

        Note: Resources composed of citations with missing page numbers are
        NOT considered the same, even if their other attributes are identical.
        This is to avoid potential false positives.
        """
        return self.citation.comparison_hash()

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()
