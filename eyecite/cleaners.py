import re
from typing import Callable, Dict

import lxml.html


def html(html_content: str) -> str:
    """Given HTML markup, return only text that is visible
    Adopted from freelawproject/juriscraper/lib/html_utils.py#L163

    :param html_content: The HTML string
    :return: Text that is visible
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
    """Collapse multiple spaces or tabs into one space character."""
    return re.sub(r"[ \t]+", " ", text)


def all_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into one space character."""
    return re.sub(r"\s+", " ", text)


def underscores(text: str) -> str:
    """Remove strings of two or more underscores that are common
    in text extracted from PDFs."""
    return re.sub(r"__+", "", text)


cleaners_lookup: Dict[str, Callable[[str], str]] = {
    "html": html,
    "inline_whitespace": inline_whitespace,
    "all_whitespace": all_whitespace,
    "underscores": underscores,
}
