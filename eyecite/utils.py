import re

from lxml import etree


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


class HashableDict(dict):
    """Dict that works as an attribute of a hashable dataclass."""

    def __hash__(self):
        return hash(frozenset(self.items()))


def dump_citations(citations, text, context_chars=30):
    """Dump citations extracted from text, for debugging. Example:
    >>> text = "blah. Foo v. Bar, 1 U.S. 1, 2 (1999). blah"
    >>> dump_citations(get_citations(text), text)
    blah. Foo v. Bar, 1 U.S. 1, 2 (1999). blah
      * FullCaseCitation
      * reporter_found='U.S.'
      * pin_cite='2'
      * groups={'volume': '1', 'reporter': 'U.S.', 'page': '1'}
      * ...
    """
    out = []
    green_fmt = "\x1B[32m"
    blue_fmt = "\x1B[94m"
    bold_fmt = "\x1B[1m"
    end_fmt = "\x1B[0m"
    for citation in citations:
        start, end = citation.span()
        context_before = text[max(0, start - context_chars) : start]
        context_before = context_before.split("\n")[-1].lstrip()
        matched_text = text[start:end]
        context_after = text[end : end + context_chars]
        context_after = context_after.split("\n")[0].rstrip()
        out.append(
            f"{green_fmt}{citation.__class__.__name__}:{end_fmt} "
            f"{context_before}"
            f"{blue_fmt}{bold_fmt}{matched_text}{end_fmt}"
            f"{context_after}"
        )
        for key, value in citation.dump().items():
            if value:
                if isinstance(value, dict):
                    out.append(f"  * {key}")
                    for sub_key, sub_value in value.items():
                        out.append(f"    * {sub_key}={repr(sub_value)}")
                else:
                    out.append(f"  * {key}={repr(value)}")
    return "\n".join(out)
