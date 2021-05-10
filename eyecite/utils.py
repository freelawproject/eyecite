import re
from typing import Callable, Iterable, Union

from lxml import etree

from eyecite.cleaners import cleaners_lookup

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
PAGE_NUMBER_REGEX = rf"(?:\d+|{ROMAN_NUMERAL_REGEX})"


# Regex to match punctuation around volume numbers and stopwords.
# This could potentially be more precise.
PUNCTUATION_REGEX = r"[^\sa-zA-Z0-9]*"


def strip_punct(text: str) -> str:
    """Strips punctuation from a given string
    Adapted from nltk Penn Treebank tokenizer

    :param str: The raw string
    :return: The stripped string
    """
    # starting quotes
    text = re.sub(r"^[\"\']", r"", text)
    text = re.sub(r"(``)", r"", text)
    text = re.sub(r'([ (\[{<])"', r"", text)

    # punctuation
    text = re.sub(r"\.\.\.", r"", text)
    text = re.sub(r"[,;:@#$%&]", r"", text)
    text = re.sub(r'([^\.])(\.)([\]\)}>"\']*)\s*$', r"\1", text)
    text = re.sub(r"[?!]", r"", text)

    text = re.sub(r"([^'])' ", r"", text)

    # parens, brackets, etc.
    text = re.sub(r"[\]\[\(\)\{\}\<\>]", r"", text)
    text = re.sub(r"--", r"", text)

    # ending quotes
    text = re.sub(r'"', "", text)
    text = re.sub(r"(\S)(\'\'?)", r"\1", text)

    return text.strip()


def clean_text(text, steps: Iterable[Union[str, Callable[[str], str]]]) -> str:
    """Applies each step in order to text, returning the result.
    Steps may be the names of functions in eyecite.cleaners, or callables.
    """
    for step in steps:
        if step in cleaners_lookup:
            step_func = cleaners_lookup[step]  # type: ignore
        elif callable(step):
            step_func = step
        else:
            raise ValueError(
                "clean_text steps must be callable "
                f"or one of {list(cleaners_lookup.keys())}"
            )
        text = step_func(text)

    return text  # type: ignore


def space_boundaries_re(regex):
    """Wrap regex with space or end of string."""
    return rf"(?:^|\s)({regex})(?:\s|$)"


def strip_punctuation_re(regex):
    """Wrap regex with punctuation pattern."""
    return rf"{PUNCTUATION_REGEX}{regex}{PUNCTUATION_REGEX}"


def nonalphanum_boundaries_re(regex):
    """Wrap regex to require non-alphanumeric characters on left and right."""
    return rf"(?:^|[^a-zA-Z0-9])({regex})(?:[^a-zA-Z0-9]|$)"


def is_balanced_html(text: str) -> bool:
    """Return False if text contains un-balanced HTML, otherwise True."""
    # fast check for strings without angle brackets
    if not ("<" in text or ">" in text):
        return True

    # lxml will throw an error while parsing if the string is unbalanced
    try:
        etree.fromstring(f"<div>{text}</div>")
        return True
    except etree.XMLSyntaxError:
        return False


def wrap_html_tags(text: str, before: str, after: str):
    """Wrap any html tags in text with before and after strings."""
    return re.sub(r"(<[^>]+>)", rf"{before}\1{after}", text)
