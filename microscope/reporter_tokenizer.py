#!/usr/bin/env python
# encoding: utf-8

# Loosely adapted from the Natural Language Toolkit: Tokenizers
# URL: <http://nltk.sourceforge.net>

import re

from reporters_db import EDITIONS, VARIATIONS_ONLY

# We need to build a REGEX that has all the variations and the reporters in
# order from longest to shortest.
REGEX_LIST = list(EDITIONS.keys()) + list(VARIATIONS_ONLY.keys())
REGEX_LIST.sort(key=len, reverse=True)
REGEX_STR = "|".join(map(re.escape, REGEX_LIST))
REPORTER_RE = re.compile(r"(^|\s)(%s)(\s|,)" % REGEX_STR)


def tokenize(text: str) -> str:
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
        return text.split("-")
    # otherwise, we just split on spaces to find words
    strings = REPORTER_RE.split(text)
    words = []
    for string in strings:
        if string in list(EDITIONS.keys()) + list(VARIATIONS_ONLY.keys()):
            words.append(string)
        else:
            # Normalize spaces
            words.extend(_tokenize(string))
    return words


def _tokenize(text: str) -> str:
    # add extra space to make things easier
    text = " " + text + " "

    # get rid of all the annoying underscores in text from pdfs
    text = re.sub(r"__+", "", text)

    # reduce excess whitespace
    text = re.sub(" +", " ", text)
    text = text.strip()

    return text.split()
