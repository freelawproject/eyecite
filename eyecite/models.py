import re
from collections import UserString
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Hashable, List, Optional, Sequence, Union

ResourceType = Hashable


@dataclass(eq=True, frozen=True)
class Reporter:
    """Class for top-level reporters in reporters_db, like "S.W." """

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
    """Class for individual editions in reporters_db,
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
    """Base class for objects returned by get_citations()."""

    token: "Token"  # token this citation came from
    index: int  # index of _token in the token list
    # span() overrides
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    groups: dict = field(default_factory=dict, compare=False)

    def __post_init__(self):
        """Set groups."""
        self.groups = self.token.groups

    def __repr__(self):
        """Simplified repr() to be more readable than full dataclass repr().
        Just shows 'FullCaseCitation("matched text", groups=...)'."""
        return (
            f"{self.__class__.__name__}("
            + f"{repr(self.matched_text())}"
            + (f", groups={repr(self.groups)}" if self.groups else "")
            + ")"
        )

    def formatted(self):
        """Return formatted version of extracted cite."""
        return self.matched_text()

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


@dataclass(eq=True, unsafe_hash=True, repr=False)
class ResourceCitation(CitationBase):
    """Base class for a case, law, or journal citation. Could be short or
    long."""

    # Value of the 'reporter' match group, for normalizing variations
    reporter_found: Optional[str] = None
    reporter: Optional[str] = None

    # Set during disambiguation.
    # For a citation to F.2d, the canonical reporter is F.
    canonical_reporter: Optional[str] = None

    # Editions that might match this reporter string
    exact_editions: Sequence[Edition] = field(default_factory=tuple)
    variation_editions: Sequence[Edition] = field(default_factory=tuple)
    all_editions: Sequence[Edition] = field(default_factory=tuple)
    edition_guess: Optional[Edition] = None

    parenthetical: Optional[str] = None
    pin_cite: Optional[str] = None
    year: Optional[int] = None

    def __post_init__(self):
        """Make iterables into tuples to make sure we're hashable."""
        self.exact_editions = tuple(self.exact_editions)
        self.variation_editions = tuple(self.variation_editions)
        self.all_editions = tuple(self.exact_editions) + tuple(
            self.variation_editions
        )
        super().__post_init__()

    def base_citation(self):
        """Return a simple version of the citation."""
        if self.edition_guess:
            # normalize reporter
            return self.matched_text().replace(
                self.reporter_found, self.edition_guess.short_name
            )
        return self.matched_text()

    def guess_edition(self):
        """Set canonical_reporter, edition_guess, and reporter."""
        # Use exact matches if possible, otherwise try variations
        editions = self.exact_editions or self.variation_editions
        if not editions:
            return

        # Attempt resolution by date
        if len(editions) > 1 and self.year:
            editions = [e for e in editions if e.includes_year(self.year)]

        if len(editions) == 1:
            self.edition_guess = editions[0]
            self.canonical_reporter = editions[0].reporter.short_name
            self.reporter = editions[0].short_name


@dataclass(eq=True, unsafe_hash=True, repr=False)
class FullCitation(ResourceCitation):
    """Abstract base class indicating cite fully identifies a resource."""


@dataclass(eq=True, unsafe_hash=True, repr=False)
class FullLawCitation(FullCitation):
    """Citation to a source from laws.json."""

    publisher: Optional[str] = None
    day: Optional[str] = None
    month: Optional[str] = None


@dataclass(eq=True, unsafe_hash=True, repr=False)
class FullJournalCitation(FullCitation):
    """Citation to a source from journals.json."""

    # Core data.
    page: Optional[str] = None
    volume: Optional[str] = None


@dataclass(eq=True, unsafe_hash=True, repr=False)
class CaseCitation(ResourceCitation):
    """Convenience class which represents a single citation found in a
    document.
    """

    # Core data.
    page: Optional[str] = None
    volume: Optional[str] = None

    # Supplementary data, if possible:
    #  <plaintiff> v. <defendant>,
    #  <matched_text> <pin_cite> <extra>
    #  (<court> <year>)
    #  (<parenthetical).
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    extra: Optional[str] = None
    court: Optional[str] = None

    def formatted(self):
        """Return formatted version of extracted cite."""
        parts = []
        if self.plaintiff:
            parts.append(f"{self.plaintiff} v. ")
        if self.defendant:
            parts.append(f"{self.defendant}, ")
        parts.append(self.base_citation())
        if self.pin_cite:
            parts.append(f", {self.pin_cite}")
        if self.extra:
            parts.append(self.extra)
        if self.court or self.year:
            parts.append(" (")
            parts.append(" ".join(i for i in (self.court, self.year) if i))
            parts.append(")")
        if self.parenthetical:
            parts.append(f" ({self.parenthetical})")
        return "".join(parts)

    def guess_court(self):
        """Set court based on reporter."""
        if not self.court and any(
            e.reporter.is_scotus for e in self.all_editions
        ):
            self.court = "scotus"


@dataclass(eq=True, unsafe_hash=True, repr=False)
class FullCaseCitation(CaseCitation, FullCitation):
    """Convenience class which represents a standard, fully named citation,
    i.e., the kind of citation that marks the first time a document is cited.

    Example: Adarand Constructors, Inc. v. Peña, 515 U.S. 200, 240
    """


@dataclass(eq=True, unsafe_hash=True, repr=False)
class ShortCaseCitation(CaseCitation):
    """Convenience class which represents a short form citation, i.e., the kind
    of citation made after a full citation has already appeared. This kind of
    citation lacks a full case name and usually has a different page number
    than the canonical citation.

    Example 1: Adarand, 515 U.S., at 241
    Example 2: Adarand, 515 U.S. at 241
    Example 3: 515 U.S., at 241
    """

    # Like a Citation object, but we have to guess who the antecedent is
    # and the page number is non-canonical
    antecedent_guess: Optional[str] = None

    def formatted(self):
        """Return formatted version of extracted cite."""
        parts = []
        if self.antecedent_guess:
            parts.append(f"{self.antecedent_guess}, ")
        parts.append(self.base_citation())
        return "".join(parts)


@dataclass(eq=True, unsafe_hash=True, repr=False)
class SupraCitation(CitationBase):
    """Convenience class which represents a 'supra' citation, i.e., a citation
    to something that is above in the document. Like a short form citation,
    this kind of citation lacks a full case name and usually has a different
    page number than the canonical citation.

    Example 1: Adarand, supra, at 240
    Example 2: Adarand, 515 supra, at 240
    Example 3: Adarand, supra, somethingelse
    Example 4: Adarand, supra. somethingelse
    """

    # Like a Citation object, but without knowledge of the reporter or the
    # volume. Only has a guess at what the antecedent is.
    antecedent_guess: Optional[str] = None
    pin_cite: Optional[str] = None
    volume: Optional[str] = None

    def formatted(self):
        """Return formatted version of extracted cite."""
        parts = []
        if self.antecedent_guess:
            parts.append(f"{self.antecedent_guess}, ")
        if self.volume:
            parts.append(f"{self.volume} ")
        parts.append("supra")
        if self.pin_cite:
            parts.append(f", {self.pin_cite}")
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

    pin_cite: Optional[str] = None

    def formatted(self):
        """Return formatted version of extracted cite."""
        parts = ["id."]
        if self.pin_cite:
            parts.append(f", {self.pin_cite}")
        return "".join(parts)


@dataclass(eq=True, unsafe_hash=True, repr=False)
class NonopinionCitation(CitationBase):
    """Convenience class which represents a citation to something that we know
    is not an opinion. This could be a citation to a statute, to the U.S. code,
    the U.S. Constitution, etc.

    Example 1: 18 U.S.C. §922(g)(1)
    Example 2: U. S. Const., Art. I, §8
    """


@dataclass(eq=True, frozen=True)
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


# For performance, lists of tokens can include either Token subclasses
# or bare strings (the typical case of words that aren't
# related to citations)
TokenOrStr = Union[Token, str]
Tokens = List[TokenOrStr]


@dataclass(eq=True, frozen=True)
class CitationToken(Token):
    """String matching a citation regex from reporters.json."""

    exact_editions: Sequence[Edition] = field(default_factory=tuple)
    variation_editions: Sequence[Edition] = field(default_factory=tuple)
    short: bool = False

    def __post_init__(self):
        """Make iterables into tuples to make sure we're hashable."""
        # use setattr because this class is frozen
        object.__setattr__(self, "exact_editions", tuple(self.exact_editions))
        object.__setattr__(
            self, "variation_editions", tuple(self.variation_editions)
        )


@dataclass(eq=True, frozen=True)
class SectionToken(Token):
    """Word containing a section symbol."""


@dataclass(eq=True, frozen=True)
class SupraToken(Token):
    """Word matching "supra" with or without punctuation."""


@dataclass(eq=True, frozen=True)
class IdToken(Token):
    """Word matching "id" or "ibid"."""


@dataclass(eq=True, frozen=True)
class ParagraphToken(Token):
    """Word matching a break between paragraphs."""


@dataclass(eq=True, frozen=True)
class StopWordToken(Token):
    """Word matching one of the STOP_TOKENS."""


@dataclass
class TokenExtractor:
    """Object to extract all matches from a given string for the given regex,
    and then to return Token objects for all matches."""

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
    resolved."""

    citation: FullCitation

    def __hash__(self):
        """
        Full citations are constructively equal if the groups matched by their
        regexes are equal.
        """
        return hash((type(self.citation), tuple(self.citation.groups.items())))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()
