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


def whitespace(text: str) -> str:
    """Collapse multiple spaces into one, and strip whitespace."""
    text = re.sub(" +", " ", text)

    return text.strip()


def underscores(text: str) -> str:
    """Remove strings of two or more underscores that are common
    in text extracted from PDFs."""
    return re.sub(r"__+", "", text)


cleaners_lookup: Dict[str, Callable[[str], str]] = {
    "html": html,
    "whitespace": whitespace,
    "underscores": underscores,
}
