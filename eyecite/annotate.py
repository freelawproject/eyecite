from bisect import bisect_left, bisect_right
from difflib import SequenceMatcher
from functools import partial
from typing import Any, Callable, Iterable, Optional, Tuple

import diff_match_patch

from eyecite.utils import is_balanced_html, wrap_html_tags


def annotate(
    plain_text: str,
    annotations: Iterable[Tuple[Tuple[int, int], Any, Any]],
    source_text: Optional[str] = None,
    unbalanced_tags: str = "unchecked",
    use_dmp: bool = True,
    annotator: Optional[Callable[[Any, str, Any], str]] = None,
):
    """Insert annotations into text around each citation.
    Each annotation is a tuple of an extracted citation, before text, and
    after text.

    Example:
    >>> plain_text = "foo 1 U.S. 1 bar"
    >>> citations = get_citations(plain_text)
    >>> annotate("foo 1 U.S. 1 bar",
    ...     [(citations[0].span(), "<a>", "</a>")])
    "foo <a>1 U.S. 1</a> bar"

    If source_text is provided, apply annotations to that text
    instead using diffing.

    If source_text is provided, unbalanced_tags="skip" will skip inserting
    annotations that result in invalid HTML. unbalanced_tags="wrap" will
    ensure valid HTML by wrapping annotations around any unbalanced tags.

    If use_dmp=True (default), use the fast diff_match_patch_python library
    for diffing. Use False for the slower builtin difflib, which may be
    useful for debugging.

    If annotator is provided, it should be a function that takes
    (before, span_text, after) and returns the annotation.
    By default before + span_text + after will be inserted.
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
            return diff_match_patch.diff(
                a, b, timelimit=0, checklines=False, cleanup_semantic=False
            )
        except AttributeError as e:
            raise AttributeError(
                "This may be caused by having the diff_match_patch package "
                "installed, which is incompatible with "
                "diff_match_patch_python."
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
