from bisect import bisect_left, bisect_right
from difflib import SequenceMatcher
from functools import partial
from typing import Any, Callable, Iterable, Optional, Tuple

import fast_diff_match_patch

from eyecite.utils import is_balanced_html, wrap_html_tags


def annotate_citations(
    plain_text: str,
    annotations: Iterable[Tuple[Tuple[int, int], Any, Any]],
    source_text: Optional[str] = None,
    unbalanced_tags: str = "unchecked",
    use_dmp: bool = True,
    annotator: Optional[Callable[[Any, str, Any], str]] = None,
) -> str:
    """Given a list of citations and the text from which they were parsed,
    insert annotations into the text surrounding each citation. This could be
    useful for linking the citations to a URL, or otherwise indicating that
    they were successfully parsed or resolved.

    If you pre-processed your text before extracting the citations, this
    function will intelligently reconcile the differences between the original
    source text and the cleaned text using a diffing algorithm, ensuring that
    each annotation is inserted in the correct location.

    Example:
    >>> plain_text = "foo 1 U.S. 1 bar"
    >>> citations = get_citations(plain_text)
    >>> annotate_citations("foo 1 U.S. 1 bar",
    ...     [(citations[0].span(), "<a>", "</a>")])
    >>>
    >>> returns: "foo <a>1 U.S. 1</a> bar"

    Args:
        plain_text: The text containing the citations. If this text was
            cleaned, you should also pass the `source_text` below.
        annotations: A `Tuple` of (1) the start and end positions of the
            citation in the text, (2) the text to insert before the citation,
            and (3) the text to insert after the citation.
        source_text: If provided, apply annotations to this text instead using
            a diffing algorithm.
        unbalanced_tags: If provided, unbalanced_tags="skip" will skip
            inserting annotations that result in invalid HTML.
            unbalanced_tags="wrap" will ensure valid HTML by wrapping
            annotations around any unbalanced tags.
        use_dmp: If `True` (default), use the fast_diff_match_patch_python
            library for diffing. If `False`, use the slower built-in difflib,
            which may be useful for debugging.
        annotator: If provided, should be a function that takes three
            arguments (the text to insert before, the text of the citation,
            and the text to insert after) and returns the annotation. This is
            useful for customizing the annotation action: If you don't pass
            this function, eyecite will simply concatenate the before_text,
            citation_text, and after_text together for each annotation.

    Returns:
        The annotated text.
    """
    # set up offset_updater if we have to move annotations to source_text
    offset_updater = None
    if source_text and source_text != plain_text:
        offset_updater = SpanUpdater(plain_text, source_text, use_dmp=use_dmp)
        plain_text = source_text

    # append text for each annotation to out
    annotations = sorted(annotations)
    out = []
    last_end = 0
    for (start, end), before, after in annotations:
        # if we're applying to source_text, update offsets
        if offset_updater:
            start = offset_updater.update(start, bisect_right)
            end = offset_updater.update(end, bisect_left)

        # handle overlaps
        if start < last_end:
            # include partial annotation if possible
            start = last_end
            if start >= end:
                # if annotation is entirely covered, skip
                continue

        span_text = plain_text[start:end]

        # handle HTML tags
        if unbalanced_tags == "unchecked":
            pass
        elif unbalanced_tags in ("skip", "wrap"):
            if not is_balanced_html(span_text):
                if unbalanced_tags == "skip":
                    continue
                span_text = wrap_html_tags(span_text, after, before)
        else:
            raise ValueError(f"Unknown option '{unbalanced_tags}")

        if annotator is not None:
            annotated_span = annotator(before, span_text, after)
        else:
            annotated_span = before + span_text + after

        # append each span
        out.extend(
            [
                plain_text[last_end:start],
                annotated_span,
            ]
        )
        last_end = end

    # append text after final citation
    if last_end < len(plain_text):
        out.append(plain_text[last_end:])

    return "".join(out)


class SpanUpdater:
    """Helper object to shift offsets from text_before to text_after.

    For example:
    >>> text_before = "foo bar"
    >>> text_after = "foo baz bar"
    >>> updater = SpanUpdater(text_before, text_after)

    Offset 1 is still at offset 1:
    >>> updater.update(1)

    Offset 8 has moved to offset 10:
    >>> updater.update(8)
    10
    """

    def __init__(self, text_before, text_after, use_dmp=True):
        """To set up, we need to populate self.offsets and self.updaters:
            >>> SpanUpdater(text_before, text_after).offsets
            [0, 4]
            >>> SpanUpdater(text_before, text_after).updaters
            [partial(shift_offset, delta=0), partial(shift_offset, delta=4)]
        This indicates that offsets 0 to 4 need to be shifted by 0,
        and offsets 4 and up need to be shifted by 4.
        """

        # helpers for the two kinds of updates we need to apply to offsets:
        def shift_offset(offset, delta):
            return offset + delta

        def replace_offset(offset, new_offset):
            return new_offset

        # diff the two strings and set self.offsets and self.updaters:
        offset = 0
        delta = 0
        self.offsets = offsets = []
        self.updaters = updaters = []
        get_diff_steps = (
            self.get_diff_steps if use_dmp else self.get_diff_steps_builtin
        )
        for operation, amount in get_diff_steps(text_before, text_after):
            if operation == "=":
                # start a new range with a relative delta,
                # and push the offset forward
                offsets.append(offset)
                updaters.append(partial(shift_offset, delta=delta))
                offset += amount
            elif operation == "+":
                # push the delta forward
                delta += amount
            else:  # operation == '-'
                # Start a new range with an absolute delta.
                # Push the offset forward and delta backward.
                offsets.append(offset)
                updaters.append(
                    partial(replace_offset, new_offset=offset + delta)
                )
                offset += amount
                delta -= amount

    @staticmethod
    def get_diff_steps(a: str, b: str):
        """Yield steps to turn a into b. Example:
            >>> list(SpanUpdater.get_diff_steps("12 34 56", "12 78 34"))
            [('=', 3), ('+', 3), ('=', 2), ('-', 3)]
        Meaning: to turn a into b, keep the first 3 characters the same,
        insert three new characters (we don't care what), keep the next
        two characters, delete three characters.
        """
        try:
            return fast_diff_match_patch.diff(
                a, b, timelimit=0, checklines=False, cleanup="No"
            )
        except AttributeError as e:
            raise AttributeError(
                "This may be caused by having the diff_match_patch package "
                "installed, which is incompatible with "
                "fast_diff_match_patch_python."
            ) from e

    @staticmethod
    def get_diff_steps_builtin(a: str, b: str):
        """Same as get_diff_steps but using the builtin difflib.
        Much slower but potentially useful for debugging."""
        diffs = SequenceMatcher(a=a, b=b, autojunk=False)
        for operation, a1, a2, b1, b2 in diffs.get_opcodes():
            if operation == "insert":
                yield "+", b2 - b1
            elif operation == "replace":
                yield "-", a2 - a1
                yield "+", b2 - b1
            elif operation == "delete":
                yield "-", a2 - a1
            elif operation == "equal":
                yield "=", a2 - a1

    def update(self, offset, bisect):
        """Shift an offset left or right."""
        index = bisect(self.offsets, offset) - 1
        updater = self.updaters[index]
        return updater(offset)
