import regex as re

from eyecite.models import ParagraphToken

# Maximum characters to scan using match_on_tokens.
# If this is higher we have to do a little more work for each match_on_tokens
# call to prepare the text to be matched.
MAX_MATCH_CHARS = 300


def match_on_tokens(
    words,
    start_index,
    regex,
    prefix="",
    strings_only=False,
    forward=True,
    flags=re.X,
):
    """Scan forward or backward starting from the given index, up to max_chars.
    Return result of matching regex against token text.
    If prefix is provided, start from that text and then add token text.
    If strings_only is True, stop matching at any non-string token; otherwise
    stop matching only at paragraph tokens.
    """
    # Build text to match against, starting from prefix
    text = prefix

    # Get range of token indexes to append to text. Use indexes instead of
    # slice for performance to avoid copying list.
    if forward:
        indexes = range(min(start_index, len(words)), len(words))
        # If scanning forward, regex must match at start
        regex = rf"^(?:{regex})"
    else:
        indexes = range(max(start_index, -1), -1, -1)
        # If scanning backward, regex must match at end
        regex = rf"(?:{regex})$"

    # Append text of each token until we reach max_chars or a stop token:
    for index in indexes:
        token = words[index]

        # check for stop token
        if strings_only and not isinstance(token, str):
            break
        if isinstance(token, ParagraphToken):
            break

        # append or prepend text
        if forward:
            text += str(token)
        else:
            text = str(token) + text

        # check for max length
        if len(text) >= MAX_MATCH_CHARS:
            if forward:
                text = text[:MAX_MATCH_CHARS]
            else:
                text = text[-MAX_MATCH_CHARS:]
            break

    m = re.search(regex, text, flags=flags)
    # Useful for debugging regex failures:
    # print(f"Regex: {regex}")
    # print(f"Text: {repr(text)}")
    # print(f"Match: {m.groupdict() if m else None}")
    return m
