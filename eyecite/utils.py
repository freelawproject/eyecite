import re
from typing import Callable, Iterable, Optional, Union

from eyecite.cleaners import cleaners_lookup


def is_roman(token: str) -> Optional[re.Match]:
    """Checks if a lowercase or uppercase string is a valid Roman numeral.
    Based on: http://www.diveintopython.net/regular_expressions/n_m_syntax.html

    :param token: A string
    :return: Boolean
    """
    return re.match(
        "^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$",
        token,
        re.IGNORECASE,
    )


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
