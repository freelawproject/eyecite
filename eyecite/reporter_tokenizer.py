# Loosely adapted from the Natural Language Toolkit: Tokenizers
# URL: <http://nltk.sourceforge.net>

import re
from collections import UserString, defaultdict
from typing import List, Set

from reporters_db import EDITIONS, REPORTERS, VARIATIONS_ONLY

from eyecite.models import Edition, Reporter

# Build lookups that match reporter strings like "U.S."
# or "U. S." to Edition objects:
EDITIONS_LOOKUP = defaultdict(list)
VARIATIONS_LOOKUP = defaultdict(list)
for reporter_key, reporter_cluster in REPORTERS.items():
    for reporter in reporter_cluster:
        reporter_obj = Reporter(
            short_name=reporter_key,
            name=reporter["name"],
            cite_type=reporter["cite_type"],
        )
        editions = {}
        for k, v in reporter["editions"].items():
            editions[k] = Edition(
                short_name=k,
                reporter=reporter_obj,
                start=v["start"],
                end=v["end"],
            )
            EDITIONS_LOOKUP[k].append(editions[k])
        for k, v in reporter["variations"].items():
            VARIATIONS_LOOKUP[k].append(editions[v])


# We need to build a REGEX that has all the variations and the reporters in
# order from longest to shortest.

REPORTER_STRINGS: Set[str] = set(
    list(EDITIONS.keys()) + list(VARIATIONS_ONLY.keys())
)
REGEX_LIST = sorted(REPORTER_STRINGS, key=len, reverse=True)
REGEX_STR = "|".join(map(re.escape, REGEX_LIST))
REPORTER_RE = re.compile(r"(^|\s)(%s)(\s|,)" % REGEX_STR)

STOP_TOKENS = {
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
}


class Token(UserString):
    """ Any word in the tokenized case, not otherwise identified. """

    def __repr__(self):
        return f"{type(self).__name__}({repr(self.data)})"


class ReporterToken(Token):
    """ Words in the case that refer to a reporter string, such as "U. S." """

    def __init__(self, s, editions, variations):
        # Track editions where we have an exact string match, like "U.S.",
        # separately from editions that match a variation, like "U. S."
        self.exact_editions = editions
        self.variation_editions = variations
        self.all_editions = editions + variations
        super().__init__(s)


class SectionToken(Token):
    """ Word containing a section symbol. """

    pass


class SupraToken(Token):
    """ Word matching "supra" with or without punctuation. """

    pass


class IdToken(Token):
    """ Word matching "id" or "ibid". """

    pass


class StopWordToken(Token):
    """ Word matching one of the STOP_TOKENS. """

    pass


def tokenize(text: str) -> List[Token]:
    """Tokenize text using regular expressions in the following steps:
     - Split the text by the occurrences of patterns which match a federal
       reporter, including the reporter strings as part of the resulting
       list.
     - Perform simple tokenization (whitespace split) on each of the
       non-reporter strings in the list.

    Example:
    >>>tokenize('See Roe v. Wade, 410 U. S. 113 (1973)')
    ['See', 'Roe', 'v.', 'Wade,', '410', 'U. S.', '113', '(1973)']
    """
    # if the text looks likes the corner-case 'digit-REPORTER-digit', splitting
    # by spaces doesn't work
    if re.match(r"\d+\-[A-Za-z]+\-\d+", text):
        parts = text.split("-")
        reporter = ReporterToken(
            parts[1],
            editions=EDITIONS_LOOKUP.get(parts[1], []),
            variations=VARIATIONS_LOOKUP.get(parts[1], []),
        )
        return [Token(parts[0]), reporter] + [
            Token(part) for part in parts[2:]
        ]
    # otherwise, we just split on spaces to find words
    strings = REPORTER_RE.split(text)
    tokens: List[Token] = []
    for string in strings:
        if string in REPORTER_STRINGS:
            tokens.append(
                ReporterToken(
                    string,
                    editions=EDITIONS_LOOKUP.get(string, []),
                    variations=VARIATIONS_LOOKUP.get(string, []),
                )
            )
        else:
            for word in string.strip().split():
                token: Token
                stripped_word = re.sub(
                    r"^[^a-z0-9]*|[^a-z0-9]*$", "", word.lower()
                )
                if word.lower() in {"id.", "id.,", "ibid."}:
                    token = IdToken(word)
                elif stripped_word == "supra":
                    token = SupraToken(word)
                elif stripped_word in STOP_TOKENS:
                    token = StopWordToken(word)
                elif "§" in word:
                    token = SectionToken(word)
                else:
                    token = Token(word)
                tokens.append(token)
    return tokens
