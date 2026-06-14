from typing import cast

import regex as re

from eyecite.models import Token, Tokens
from eyecite.regexes import POST_SHORT_CITATION_REGEX
from eyecite.token_matching import match_on_tokens
from eyecite.citation_metadata import clean_pin_cite, process_parenthetical


def extract_pin_cite(
    words: Tokens, index: int, prefix: str = ""
) -> tuple[str | None, int | None, str | None]:
    """Test whether text following token at index is a valid pin cite.
    Return pin cite text and number of extra characters matched.
    If prefix is provided, use that as the start of text to match.
    """
    from_token = cast(Token, words[index])
    m = match_on_tokens(
        words,
        index + 1,
        POST_SHORT_CITATION_REGEX,
        prefix=prefix,
        strings_only=True,
    )
    if m:
        if m["pin_cite"]:
            pin_cite = clean_pin_cite(m["pin_cite"])
            extra_chars = len(m["pin_cite"].rstrip(", "))
        else:
            pin_cite = None
            extra_chars = 0
        parenthetical = process_parenthetical(m["parenthetical"])
        return (
            pin_cite,
            from_token.end + extra_chars - len(prefix),
            parenthetical,
        )
    return None, None, None
