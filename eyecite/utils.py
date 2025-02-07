import hashlib
import json
import re

from lxml import etree

# Names not allowed to be reference citations
# this is partially taken from juriscraper
DISALLOWED_NAMES = [
    # Common options
    "state",
    "united states",
    "people",
    "commonwealth",
    "mass",
    "commissioner"
    # AGs
    "Akerman",
    "Ashcroft",
    "Barr",
    "Bates",
    "Bell",
    "Berrien",
    "Biddle",
    "Black",
    "Bonaparte",
    "Bork",
    "Bondi",
    "Bradford",
    "Breckinridge",
    "Brewster",
    "Brownell",
    "Butler",
    "Civiletti",
    "Clark",
    "Clement",
    "Clifford",
    "Crittenden",
    "Cummings",
    "Cushing",
    "Daugherty",
    "Devens",
    "Evarts",
    "Filip",
    "Garland",
    "Gerson",
    "Gilpin",
    "Gonzales",
    "Gregory",
    "Griggs",
    "Grundy",
    "Harmon",
    "Hoar",
    "Holder",
    "Jackson",
    "Johnson",
    "Katzenbach",
    "Keisler",
    "Kennedy",
    "Kleindienst",
    "Knox",
    "Lee",
    "Legaré",
    "Levi",
    "Lincoln",
    "Lynch",
    "MacVeagh",
    "Mason",
    "McGranery",
    "McGrath",
    "McKenna",
    "McReynolds",
    "Meese",
    "Miller",
    "Mitchell",
    "Moody",
    "Mukasey",
    "Murphy",
    "Nelson",
    "Olney",
    "Palmer",
    "Pierrepont",
    "Pinkney",
    "Randolph",
    "Reno",
    "Richardson",
    "Rodney",
    "Rogers",
    "Rush",
    "Sargent",
    "Saxbe",
    "Sessions",
    "Smith",
    "Speed",
    "Stanbery",
    "Stanton",
    "Stone",
    "Taft",
    "Taney",
    "Thornburgh",
    "Toucey",
    "Whitacker",
    "Wickersham",
    "Williams",
    "Wirt",
]


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


def hash_sha256(dictionary: dict) -> int:
    """Hash dictionaries in a deterministic way.

    :param dictionary: The dictionary to hash
    :return: An integer hash
    """

    # Convert the dictionary to a JSON string
    # default needed because of dates
    json_str: str = json.dumps(dictionary, sort_keys=True, default=str)

    # Convert the JSON string to bytes
    json_bytes: bytes = json_str.encode("utf-8")

    # Calculate the hash of the bytes, convert to an int, and return
    return int.from_bytes(hashlib.sha256(json_bytes).digest(), byteorder="big")


def maybe_balance_style_tags(
    start: int, end: int, plain_text: str
) -> tuple[int, int, str]:
    """Try to include style tags at the edge of the span marked as invalid

    In some HTML sources the citations are styled with tags like <i> or <em>
    When the citation is found in a stripped-of-tags text, the span may
    leave out the opening or closing tag. When this happens and we try to
    annotate the HTML, it will render invalid HTML. This happens mostly with
    IdCitation, ReferenceCitation, etc.

    This function will try to find opening or closing tags inmediately
    preceding or following the citation span. If it finds them, it will
    return the new start, end and span. If not, it will return the old ones

    :param start: the original start of the span
    :param end: the origina end of the span
    :param plain_text: the text to annotate
    :return: a tuple (new start, new end, new span text)
    """
    span_text = plain_text[start:end]
    style_tags = ["i", "em", "b"]
    tolerance = 5  # tolerate at most this amount of whitespace

    for tag in style_tags:
        opening_tag = f"<{tag}>"
        closing_tag = f"</{tag}>"
        has_opening = opening_tag in span_text
        has_closing = closing_tag in span_text
        if has_opening and not has_closing:
            # look for closing tag after the end
            extended_end = max(
                end + len(closing_tag) + tolerance, len(plain_text)
            )
            if end_match := re.search(
                rf"{span_text}\s*{closing_tag}",
                plain_text[start:extended_end],
                flags=re.MULTILINE,
            ):
                end = start + end_match.end()

        if not has_opening and has_closing:
            # look for opening tag before the start
            extended_start = min(start - len(opening_tag) - tolerance, 0)
            if start_match := re.search(
                rf"{opening_tag}\s*{span_text}",
                plain_text[extended_start:end],
                flags=re.MULTILINE,
            ):
                start = extended_start + start_match.start()

    return start, end, plain_text[start:end]
