import re
from typing import Callable, Dict, Iterable, Union

import lxml.html


def clean_text(text, steps: Iterable[Union[str, Callable[[str], str]]]) -> str:
    """Given a list of "cleaning" functions, apply each in sequence to a
    given text string and return the result. Steps may be the names of
    functions in `eyecite.clean`, or other custom callables. You may wish to
    use this tool to pre-process your text before feeding it into
    `eyecite.find.get_citations`, especially if the text was
    OCR'd from a PDF.

    Args:
        text: The text to clean.
        steps: Any `Iterable` (e.g., a list) of cleaning functions to apply.

    Returns:
        The cleaned text.
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


def html(html_content: str) -> str:
    """Given HTML markup, return only text that would be rendered visibly.
    Adopted from freelawproject/juriscraper/lib/html_utils.py#L163.

    Args:
        html_content: The HTML string.

    Returns:
        Text that is visible.
    """
    html_tree = lxml.html.fromstring(html_content)
    text = html_tree.xpath(
        """//text()[normalize-space() and not(
            parent::style |
            parent::link |
            parent::head |
            parent::script)]"""
    )
    return " ".join(text)


def inline_whitespace(text: str) -> str:
    """Collapse multiple spaces or tabs within a string into one space
    character.

    Args:
        text: The input string.

    Returns:
        Text with collapsed spaces and tabs.
    """
    return re.sub(r"[ \t]+", " ", text)


def all_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters within a string into one space
    character.

    Args:
        text: The input string.

    Returns:
        Text with collapsed whitespace characters.
    """
    return re.sub(r"\s+", " ", text)


def underscores(text: str) -> str:
    """Remove strings of two or more underscores that are common
    in text extracted from PDFs.

    Args:
        text: The input string.

    Returns:
        Text without underscores.
    """
    return re.sub(r"__+", "", text)


cleaners_lookup: Dict[str, Callable[[str], str]] = {
    "html": html,
    "inline_whitespace": inline_whitespace,
    "all_whitespace": all_whitespace,
    "underscores": underscores,
}
