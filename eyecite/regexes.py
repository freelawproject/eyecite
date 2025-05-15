# *** Helpers for building regexes: ***


def space_boundaries_re(regex):
    """Wrap regex with space or end of string."""
    return rf"(?:^|\s)({regex})(?:\s|$)"


def strip_punctuation_re(regex):
    """Wrap regex with punctuation pattern."""
    return rf"{PUNCTUATION_REGEX}{regex}{PUNCTUATION_REGEX}"


def nonalphanum_boundaries_re(regex):
    """Wrap regex to require non-alphanumeric characters on left and right."""
    return rf"(?:^|[^a-zA-Z0-9])({regex})(?:[^a-zA-Z0-9]|$)"


def short_cite_re(regex):
    """Convert a full citation regex into a short citation regex.
    Currently this just means we turn '(?P<reporter>...),? (?P<page>...'
    to r'(?P<reporter>...),? at\\s(p\\.)? (?P<page>...'"""
    return regex.replace(r"(?P<page>", r"at\s?(p(\.|age)?)? (?P<page>")


def reference_pin_cite_re(regexes):
    """Create a reference pin-cite regex pattern

    Args:
        regexes (): Regexes of reference citations to build

    Returns: A pin cite reference regex
    """
    pin_cite_re = rf"\b(?:{'|'.join(regexes)})\s+{PIN_CITE_REGEX}"
    return pin_cite_re


# *** Tokenizer regexes: ***
# Regexes used from tokenizers.py

# We need a regex that matches roman numerals but not the empty string,
# without using lookahead assertions that aren't supported by hyperscan.
# We *don't* want to match roman numerals 'v', 'l', or 'c', or numerals over
# 200, or uppercase, as these are usually false positives
# (see https://github.com/freelawproject/eyecite/issues/56 ).
# Match roman numerals 1 to 199 except for 5, 50, 100:
ROMAN_NUMERAL_REGEX = "|".join(
    [
        # 10-199, but not 50-59 or 100-109 or 150-159:
        r"c?(?:xc|xl|l?x{1,3})(?:ix|iv|v?i{0,3})",
        # 1-9, 51-59, 101-109, 151-159, but not 5, 55, 105, 155:
        r"(?:c?l?)(?:ix|iv|v?i{1,3})",
        # 55, 105, 150, 155:
        r"(?:lv|cv|cl|clv)",
    ]
)

# Page number regex to match one of the following:
# (ordered in descending order of likelihood)
# 1) A plain digit. E.g. "123"
# 2) A roman numeral.
# 3) A page placeholder. E.g. "Carpenter v. United States, 585 U.S. ___ (2018)"
PAGE_NUMBER_REGEX = rf"(?:\d+|{ROMAN_NUMERAL_REGEX}|_+)"

# Regex to match punctuation around volume numbers and stopwords.
# This could potentially be more precise.
PUNCTUATION_REGEX = r"[^\sa-zA-Z0-9]*"

# Regex for IdToken
ID_REGEX = space_boundaries_re(r"id\.,?|ibid\.")

# Regex for SupraToken
SUPRA_REGEX = space_boundaries_re(strip_punctuation_re("supra"))

# Regex for StopWordToken
STOP_WORDS = (
    "v",
    "in re",
    "re",
    "quoting",
    "e.g.",
    "parte",
    "denied",
    "citing",
    "aff'd",
    "affirmed",
    "remanded",
    "see also",
    "see",
    "granted",
    "dismissed",
    "Cf",
)
STOP_WORD_REGEX = space_boundaries_re(
    strip_punctuation_re(rf"(?P<stop_word>{'|'.join(STOP_WORDS)})")
)

# Regex for SectionToken
SECTION_REGEX = r"(\S*§\S*)"

# Regex for ParagraphToken
PARAGRAPH_REGEX = r"(\n)"

common_placeholder_reporters = [
    r"A\.?2d",
    r"A\.?3d",
    r"AD3d",
    r"Cal\.",
    r"F\.?3d",
    r"F\.Supp\.2d",
    r"Idaho",
    r"Iowa",
    r"L\.Ed\.",
    r"Mass\.",
    r"N\.?J\.?",
    r"N\.C\.\s?App\.",
    r"N\.E\.3d",
    r"N\.J\.\sSuper\.(\sat)?",
    r"N\.W\.2d",
    r"N\.W\.3d",
    r"N\.?Y\.?",
    r"Nev\.",
    r"NY3d",
    r"Ohio\sSt\.3d",
    r"P\.?3d",
    r"S\.?E\.?2d",
    r"S\.?E\.?3d",
    r"S\.?W\.?2d",
    r"S\.?W\.?3d",
    r"S\.C\.",
    r"S\.Ct\.",
    r"So\.?3d",
    r"U\.\s?S\.",
    r"W\.Va\.",
    r"Wis\.\s?2d",
]

placeholder_reporters = "|".join(common_placeholder_reporters)

# Regex for Placeholder Citations
PLACEHOLDER_CITATIONS = rf"([_—–-]+\s({placeholder_reporters})\s[_—–-]+)"


# *** Metadata regexes: ***
# Regexes used to scan forward or backward from a citation token. NOTE:
# * Regexes are written in verbose mode. Intentional spaces must be escaped.
# * In many regexes order matters: options separated by "|" are
#   tested left to right, so more specific (typically longer) have to come
#   before less specific.

# Parenthetical regex:
# Capture a parenthetical after a cite, like " (overruling Foo)"
PARENTHETICAL_REGEX = r"""
    (?:
        # optional space, opening paren
        \ ?\(
            # capture until last end paren, we'll trim off extra afterwards
            (?P<parenthetical>.*)
           \)
    )?
"""

MONTH_REGEX = r"""
    (?P<month>
        January|Jan\.|
        February|Feb\.|
        March|Mar\.|
        April|Apr\.|
        May|
        June|Jun\.|
        July|Jul\.|
        August|Aug\.|
        September|Sept?\.|
        October|Oct\.|
        November|Nov\.|
        December|Dec\.
    )
"""

YEAR_REGEX = r"""
    (?:
        (?P<year>
            \d{4}
        )
        # Year is occasionally a range, like "1993-94" or "2005-06".
        # For now we ignore the end of the range:
        (?:-\d{2})?
    )
"""

# Pin cite regex:
# A pin cite is the part of a citation used to specify a particular section of
# the referenced document. These may have prefixes, may include paragraph,
# page, or line references, and may have multiple ranges specified.
# For some examples see
# https://github.com/freelawproject/courtlistener/issues/1344#issuecomment-662994948
PIN_CITE_TOKEN_REGEX = r"""
    # optional label (longest to shortest):
    (?:
        (?:
            (?:&\ )?note|       # note, & note
            (?:&\ )?nn?\.?|     # n., nn., & nn.
            (?:&\ )?fn?\.?|     # fn., & fn.
            ¶{1,2}|             # ¶
            §{1,2}|             # §
            \*{1,4}|            # *
            pg\.?|              # pg.
            pp?\.?              # p., pp.
        )\ ?  # optional space after label
    )?
    (?:
        # page:paragraph cite, like 123:24-25 or 123:24-124:25:
        \d+:\d+(?:-\d+(?::\d+)?)?|
        # page range, like 12 or 12-13:
        [*]?\d+(?:-\d+)?
    )
"""

PIN_CITE_REGEX = rf"""
    (?P<pin_cite>
        # optional comma, space, "at" before pin cite
        ,?\ ?(?:at\ )?
        # first mandatory page number
        {PIN_CITE_TOKEN_REGEX}
        # optional additional page numbers
        (?:,\ ?{PIN_CITE_TOKEN_REGEX})*
        # pin cite must be followed by one of these so it doesn't capture
        # start of next citation
        (?=
            [,.;)\]\\]|  # ending punctuation
            \ ?[(\[]|    # space and start of parens
            $            # end of text
        )
    )
"""

# Law subsection regex:
# Capture a single subsection like "(a)", "(1)", or "(viii)":
LAW_SUBSECTION = r"""
    (?:
        \([0-9a-zA-Z]{1,4}\)
    )
"""

# Law pin cite regex:
# Capture pin cite immediately after a law section number.
# Examples:
#  ...(a)(2)
#  ...(a)(2) and (d)
#  ... et seq.
# We should also capture ranges like "123-124" here, but those are ambiguous
# and are already captured as section numbers the same as "12-34-5".
LAW_PIN_CITE_REGEX = rf"""
    (?P<pin_cite>
        # subsection like (a)(1)(xiii):
        {LAW_SUBSECTION}*
        (?:\ and\ {LAW_SUBSECTION}+)?
        (?:\ et\ seq\.)?
    )
"""

# Short cite antecedent regex:
# What case does a short cite refer to? For now, we just capture the previous
# word optionally followed by a comma. Example: Adarand, 515 U.S. at 241.
SHORT_CITE_ANTECEDENT_REGEX = r"""
    (?P<antecedent>[A-Za-z][\w\-.]+)\ ?,?
    \   # final space
"""


# Supra cite antecedent regex:
# What case does a short cite refer to? For now, we just capture the previous
# word optionally followed by a comma. Example: Adarand, supra.
# If the previous word is a digit, we capture both that (to store as a volume)
# and the word before it (to store as antecedent).
SUPRA_ANTECEDENT_REGEX = r"""
    (?:
        (?P<antecedent>[\w\-.]+)\ ?,?\ (?P<volume>\d+)|
        (?P<volume>\d+)|
        (?P<antecedent>[\w\-.]+)\ ?,?
    )
    \   # final space
"""


# Post full citation regex:
# Capture metadata after a full cite. For example given the citation "1 U.S. 1"
# with the following text:
#   1 U.S. 1, 4-5, 2 S. Ct. 2, 6-7 (4th Cir. Jan. 1, 2012) (overruling foo)
# we want to capture:
#   pin_cite = 4-5
#   extra = 2 S. Ct. 2, 6-7
#   court = 4th Cir.
#   month = Jan.
#   day = 1
#   year = 2012
#   parenthetical = overruling foo
POST_FULL_CITATION_REGEX = rf"""
    (?: # handle a full cite with a valid court+date paren:
        # content before court+date paren:
        (?:
            # pin cite with comma and extra:
            {PIN_CITE_REGEX}?
            ,?\ ?
            (?P<extra>[^(;]*)
        )
        # content within court+date paren:
        [\(\[] # opening paren or bracket
        (?:
            (?:
                (?P<court>.*?) # treat anything before date as court
                (?= # lookahead to stop when we see a month or year
                    \s+{MONTH_REGEX} |
                    \s+{YEAR_REGEX}
                )
            )?
            \ ?
            (?P<month>{MONTH_REGEX})?\ ?   # optional month
            (?P<day>\d{{1,2}})?\,?\ ?      # optional day and comma
            (?P<year>{YEAR_REGEX})         # year is required
        )
        [\)\]] # closing paren or bracket
        # optional parenthetical comment:
        {PARENTHETICAL_REGEX}
    |  # handle a pin cite with no valid court+date paren:
        {PIN_CITE_REGEX}
    )
"""

# These full case citations usually appear after the same full case citation
# has appeared at least once.
# Example with pincite: "Nobelman at 332, 113 S.Ct. 2106"
# Example without pincite: "Johnson, 515 U. S. 304"
PRE_FULL_CITATION_REGEX = rf"""
    # single word antecedent
    (?P<antecedent>[A-Z][a-z\-.]+)\ ?,?
    # optional pincite
    {PIN_CITE_REGEX}?
    # `PIN_CITE_REGEX` uses a positive lookahead for end characters, but we
    # must also capture them to calculate spans
    ,?\ ?
"""


# Post short-form citation regex:
# Capture pin cite and parenthetical after a short, id, or supra citation.
# For example, given the citation 'asdf, 1 U.S., at 3 (overruling xyz)',
# this will capture:
#   pin_cite = 3
#   parenthetical = overruling xyz
POST_SHORT_CITATION_REGEX = rf"""
    # optional pin cite
    {PIN_CITE_REGEX}?
    \ ?
    # optional parenthetical comment:
    {PARENTHETICAL_REGEX}
"""


# Post law citation regex:
# statutory and regulatory cites may have publishers and dates after them, like
#  (West), (West 1999), (Lexis Jun. 2018), (1999), or (May 2, 1999),
# and then may be followed by a parenthetical:
POST_LAW_CITATION_REGEX = rf"""
    {LAW_PIN_CITE_REGEX}?
    \ ?
    (?:\(
        # Consol., McKinney, Deering, West, LexisNexis, etc.
        (?P<publisher>
            [A-Z][a-z]+\.?
            (?:\ Supp\.)?
        )?
        \ ?
        # month
        (?:{MONTH_REGEX}\ )?
        # day
        (?P<day>\d{{1,2}})?,?\ ?
        # four-digit year
        {YEAR_REGEX}?
    \))?
    \ ?
    # parenthetical
    {PARENTHETICAL_REGEX}
"""

# Post journal cite regex:
# Journal cites may have a pin cite, then year, then parenthetical.
POST_JOURNAL_CITATION_REGEX = rf"""
    {PIN_CITE_REGEX}?
    \ ?
    (?:\({YEAR_REGEX}\))?
    \ ?
    {PARENTHETICAL_REGEX}
"""

# A simple regex to check if year precedes citation
DEFENDANT_YEAR_REGEX = r"(?P<defendant>.*)\s\((?P<year>\d{4})\)$"
