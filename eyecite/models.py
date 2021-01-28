import re
from collections import UserString
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, ClassVar, Dict, List, Optional, Sequence, Union


@dataclass
class Reporter:
    """Class for top-level reporters in reporters_db, like "S.W." """

    short_name: str
    name: str
    cite_type: str

    def __post_init__(self):
        self.is_scotus = (
            self.cite_type == "federal" and "supreme" in self.name.lower()
        ) or "scotus" in self.cite_type.lower()


@dataclass
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


class Citation:
    """Convenience class which represents a single citation found in a
    document.
    """

    def __init__(
        self,
        reporter,
        page,
        volume,
        canonical_reporter=None,
        extra=None,
        defendant=None,
        plaintiff=None,
        court=None,
        year=None,
        match_url=None,
        match_id=None,
        reporter_found=None,
        reporter_index=None,
        all_editions=None,
        exact_editions=None,
        variation_editions=None,
    ):

        # Core data.
        self.reporter = reporter
        self.volume = volume
        self.page = page

        # These values are set during disambiguation.
        # For a citation to F.2d, the canonical reporter is F.
        self.canonical_reporter = canonical_reporter

        # Supplementary data, if possible.
        self.extra = extra
        self.defendant = defendant
        self.plaintiff = plaintiff
        self.court = court
        self.year = year

        # The reporter found in the text is often different from the reporter
        # once it's normalized. We need to keep the original value so we can
        # linkify it with a regex.
        self.reporter_found = reporter_found

        # The location of the reporter is useful for tasks like finding
        # parallel citations, and finding supplementary info like defendants
        # and years.
        self.reporter_index = reporter_index

        # Attributes of the matching item, for URL generation.
        self.match_url = match_url
        self.match_id = match_id

        # List of reporter models that may match this reporter string
        self.all_editions = tuple(all_editions) if all_editions else tuple()
        self.exact_editions = (
            tuple(exact_editions) if all_editions else tuple()
        )
        self.variation_editions = (
            tuple(variation_editions) if all_editions else tuple()
        )
        self.edition_guess: Optional[Edition] = None

    def as_regex(self):
        pass

    def base_citation(self):
        return "%s %s %s" % (self.volume, self.reporter, self.page)

    def __repr__(self):
        print_string = self.base_citation()
        if self.defendant:
            print_string = " ".join([self.defendant, print_string])
            if self.plaintiff:
                print_string = " ".join([self.plaintiff, "v.", print_string])
        if self.extra:
            print_string = " ".join([print_string, self.extra])
        if self.court and self.year:
            paren = "(%s %d)" % (self.court, self.year)
        elif self.year:
            paren = "(%d)" % self.year
        elif self.court:
            paren = "(%s)" % self.court
        else:
            paren = ""
        print_string = " ".join([print_string, paren])
        return print_string

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(tuple(self.__dict__.values()))

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

    def guess_court(self):
        """Set court based on reporter."""
        if not self.court and any(
            e.reporter.is_scotus for e in self.all_editions
        ):
            self.court = "scotus"


class FullCitation(Citation):
    """Convenience class which represents a standard, fully named citation,
    i.e., the kind of citation that marks the first time a document is cited.

    Example: Adarand Constructors, Inc. v. Peña, 515 U.S. 200, 240
    """

    def __init__(self, *args, **kwargs):
        # Fully implements the standard Citation object.
        super().__init__(*args, **kwargs)

    def as_regex(self):
        return r"%d(\s+)%s(\s+)%s(\s?)" % (
            self.volume,
            re.escape(self.reporter_found),
            re.escape(self.page),
        )


class ShortformCitation(Citation):
    """Convenience class which represents a short form citation, i.e., the kind
    of citation made after a full citation has already appeared. This kind of
    citation lacks a full case name and usually has a different page number
    than the canonical citation.

    Example 1: Adarand, 515 U.S., at 241
    Example 2: Adarand, 515 U.S. at 241
    Example 3: 515 U.S., at 241
    """

    def __init__(self, reporter, page, volume, antecedent_guess, **kwargs):
        # Like a Citation object, but we have to guess who the antecedent is
        # and the page number is non-canonical
        super().__init__(reporter, page, volume, **kwargs)

        self.antecedent_guess = antecedent_guess

    def __repr__(self):
        print_string = "%s, %d %s, at %s" % (
            self.antecedent_guess,
            self.volume,
            self.reporter,
            self.page,
        )
        return print_string

    def as_regex(self):
        return r"%s(\s+)%d(\s+)%s(,?)(\s+)at(\s+)%s(\s?)" % (
            re.escape(self.antecedent_guess),
            self.volume,
            re.escape(self.reporter_found),
            re.escape(self.page),
        )


class SupraCitation(Citation):
    """Convenience class which represents a 'supra' citation, i.e., a citation
    to something that is above in the document. Like a short form citation,
    this kind of citation lacks a full case name and usually has a different
    page number than the canonical citation.

    Example 1: Adarand, supra, at 240
    Example 2: Adarand, 515 supra, at 240
    Example 3: Adarand, supra, somethingelse
    Example 4: Adarand, supra. somethingelse
    """

    def __init__(self, antecedent_guess, page=None, volume=None, **kwargs):
        # Like a Citation object, but without knowledge of the reporter or the
        # volume. Only has a guess at what the antecedent is.
        super().__init__(None, page, volume, **kwargs)

        self.antecedent_guess = antecedent_guess

    def __repr__(self):
        print_string = "%s supra, at %s" % (self.antecedent_guess, self.page)
        return print_string

    def as_regex(self):
        if self.volume:
            regex = r"%s(\s+)%d(\s+)supra" % (
                re.escape(self.antecedent_guess),
                self.volume,
            )
        else:
            regex = r"%s(\s+)supra" % re.escape(self.antecedent_guess)

        if self.page:
            regex += r",(\s+)at(\s+)%s" % re.escape(self.page)

        return regex + r"(\s?)"


class IdCitation(Citation):
    """Convenience class which represents an 'id' or 'ibid' citation, i.e., a
    citation to the document referenced immediately prior. An 'id' citation is
    unlike a regular citation object since it has no knowledge of its reporter,
    volume, or page. Instead, the only helpful information that this reference
    possesses is a record of the tokens after the 'id' token. Those tokens
    enable us to build a regex to match this citation later.

    Example: "... foo bar," id., at 240
    """

    def __init__(self, id_token=None, after_tokens=None, has_page=False):
        super().__init__(None, None, None)

        self.id_token = id_token
        self.after_tokens = after_tokens

        # Whether the "after tokens" comprise a page number
        self.has_page = has_page

    def __repr__(self):
        print_string = "%s %s" % (self.id_token, self.after_tokens)
        return print_string

    def as_regex(self):
        # This works by matching only the Id. token that precedes the "after
        # tokens" we collected earlier.

        # Whitespace regex explanation:
        #  \s matches any whitespace character
        #  </?\w+> matches any HTML tag
        #  , matches a comma
        #  The whole thing matches greedily, saved into a single group
        whitespace_regex = r"((?:\s|</?\w+>|,)*)"

        # Start with a matching group for any whitespace
        template = whitespace_regex

        # Add the id_token
        template += re.escape(self.id_token)

        # Add a matching group for any whitespace
        template += whitespace_regex

        # Add all the "after tokens", with whitespace groups in between
        template += whitespace_regex.join(
            [re.escape(t) for t in self.after_tokens]
        )

        # Add a final matching group for any non-HTML whitespace at the end
        template += r"(\s?)"

        return template


class NonopinionCitation:
    """Convenience class which represents a citation to something that we know
    is not an opinion. This could be a citation to a statute, to the U.S. code,
    the U.S. Constitution, etc.

    Example 1: 18 U.S.C. §922(g)(1)
    Example 2: U. S. Const., Art. I, §8
    """

    def __init__(self, match_token):
        # TODO: Make this more versatile.
        self.match_token = match_token

    def __repr__(self):
        return "NonopinionCitation"

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


@dataclass
class Token(UserString):
    """Base class for special tokens. For performance, this isn't used
    for generic words."""

    data: str

    @classmethod
    def from_match(cls, m, extra):
        """Return a token object based on a regular expression match.
        This gets called by TokenExtractor. By default, just use the
        entire matched string."""
        return cls(m[0])


# For performance, lists of tokens can include either Token subclasses
# or bare strings (the typical case of words that aren't
# related to citations)
TokenOrStr = Union[Token, str]
Tokens = Sequence[TokenOrStr]


@dataclass
class CitationToken(Token):
    """ String matching a citation regex. """

    volume: str
    reporter: str
    page: str
    exact_editions: List[Edition]
    variation_editions: List[Edition]
    short: bool = False

    @classmethod
    def from_match(cls, m, extra):
        """Citation regex matches have volume, reporter, and page match groups
        in their regular expressions, and "exact_editions" and
        "variation_editions" in their extra config. Pass all of that through
        to the constructor."""
        return cls(
            m[0],
            **m.groupdict(),
            **extra,
        )


@dataclass
class SectionToken(Token):
    """ Word containing a section symbol. """

    pass


@dataclass
class SupraToken(Token):
    """ Word matching "supra" with or without punctuation. """

    @classmethod
    def from_match(cls, m, extra):
        """Only use the captured part of the match to omit whitespace."""
        return cls(m[1])


@dataclass
class IdToken(Token):
    """ Word matching "id" or "ibid". """

    @classmethod
    def from_match(cls, m, extra):
        """Only use the captured part of the match to omit whitespace."""
        return cls(m[1])


@dataclass
class StopWordToken(Token):
    """ Word matching one of the STOP_TOKENS. """

    stop_word: str
    stop_tokens: ClassVar[List[str]] = [
        "v",
        "re",
        "parte",
        "denied",
        "citing",
        "aff'd",
        "affirmed",
        "remanded",
        "see",
        "granted",
        "dismissed",
    ]

    @classmethod
    def from_match(cls, m, extra):
        """m[1] is the captured part of the match, including punctuation.
        m[2] is just the underlying stopword like 'v', useful for comparison.
        """
        return cls(m[1], m[2].lower())


@dataclass
class TokenExtractor:
    """Object to extract all matches from a given string for the given regex,
    and then to return Token objects for all matches."""

    regex: str
    constructor: Callable
    extra: Dict = field(default_factory=dict)
    flags: int = 0
    strings: List = field(default_factory=list)

    def get_matches(self, text):
        """Return match objects for all matches in text."""
        return self.compiled_regex.finditer(text)

    def get_token(self, m):
        """For a given match object, return a Token."""
        return self.constructor(m, self.extra)

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
