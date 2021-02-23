import re
from typing import Callable, Iterable, Union

from lxml import etree

from eyecite.cleaners import cleaners_lookup

# We need a regex that matches roman numerals but not the empty string,
# without using lookahead assertions that aren't supported by hyperscan.
# Since people don't always follow the correct format for these anyway,
# we can use a simple regex that allows any order:
ROMAN_NUMERAL_REGEX = r"[IVXLCDM]+\b"
# Alternatively this regex claims to match roman numerals but not the empty
# string without lookaheads:
# https://stackoverflow.com/a/60469651/307769
# roman_numeral_regex = "|".join(
#     r"(I[VX]|VI{0,3}|I{1,3})"
#     r"((X[LC]|LX{0,3}|X{1,3})(I[VX]|V?I{0,3}))"
#     r"((C[DM]|DC{0,3}|C{1,3})(X[LC]|L?X{0,3})(I[VX]|V?I{0,3}))"
#     r"(M+(C[DM]|D?C{0,3})(X[LC]|L?X{0,3})(I[VX]|V?I{0,3}))"
# )


# Page number regex to match one of the following:
# (ordered in descending order of likelihood)
# 1) A numerical page range. E.g., "123-124"
# 2) A roman numeral. E.g., "250 Neb. xxiv (1996)"
# 3) A special Connecticut or Illinois number. E.g., "13301-M"
# 4) A page with a weird suffix. E.g., "559 N.W.2d 826|N.D."
# 5) A page with a ¶ symbol, star, and/or colon. E.g., "¶ 119:12-14"
PAGE_NUMBER_REGEX = r"(?:%s)" % "|".join(
    [
        r"\d{1,6}[-]?[a-zA-Z]{1,6}",  # CT/IL page
        r"\d{1,6}-\d{1,6}",  # page range
        r"\d+",  # simple digit
        ROMAN_NUMERAL_REGEX,
        ROMAN_NUMERAL_REGEX.lower(),
        r"[*¶]*[\d:\-]+",  # ¶, star, colon
    ]
)


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
