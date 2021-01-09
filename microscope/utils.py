#!/usr/bin/env python
# encoding: utf-8
import re

from lxml import html


def get_visible_text(html_content: str) -> str:
    """Given HTML markup, return only text that is visible
    Adopted from https://github.com/freelawproject/juriscraper/blob/master/juriscraper/lib/html_utils.py#L163

    :param html_content: The HTML string
    :return: Text that is visible
    """
    html_tree = html.fromstring(html_content)
    text = html_tree.xpath(
        """//text()[normalize-space() and not(
            parent::style |
            parent::link |
            parent::head |
            parent::script)]"""
    )
    return " ".join(text)


def isroman(s: str) -> bool:
    """Checks if a lowercase or uppercase string is a valid Roman numeral.
    Based on: http://www.diveintopython.net/regular_expressions/n_m_syntax.html

    :param s: A string
    :return: Boolean
    """
    return re.match(
        "^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$",
        s,
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
