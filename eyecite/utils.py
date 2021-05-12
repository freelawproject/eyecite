import re
from typing import Callable, Iterable, Union

from lxml import etree

from eyecite.cleaners import cleaners_lookup


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


def hyperscan_match(regexes, text):
    """Run regexes on text using hyperscan, for debugging."""
    # import here so the dependency is optional
    import hyperscan  # pylint: disable=import-outside-toplevel

    flags = [hyperscan.HS_FLAG_SOM_LEFTMOST] * len(regexes)
    regexes = [regex.encode("utf8") for regex in regexes]
    hyperscan_db = hyperscan.Database()
    hyperscan_db.compile(expressions=regexes, flags=flags)
    matches = []

    def on_match(index, start, end, flags, context):
        matches.append((index, start, end, flags, context))

    hyperscan_db.scan(text.encode("utf8"), on_match)

    return matches
