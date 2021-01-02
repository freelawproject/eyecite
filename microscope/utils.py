#!/usr/bin/env python
# encoding: utf-8
import re

from lxml import html


def get_visible_text(html_content):
    """Given HTML markup, only text that is visible
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


def isroman(s):
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
