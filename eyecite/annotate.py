from bisect import bisect_right
from difflib import SequenceMatcher
from functools import partial
from typing import Iterable, Optional, Tuple

from eyecite.utils import is_balanced_html, wrap_html_tags


def annotate(
    plain_text: str,
    annotations: Iterable[Tuple[Tuple[int, int], str, str]],
    source_text: Optional[str] = None,
    unbalanced_tags: str = "unchecked",
    use_dmp: bool = False,
):
    """Insert annotations into text around each citation.
        Each annotation is a tuple of an extracted citation, before text, and
        after text.

        Example:
        >>> plain_text = "foo 1 U.S. 1 bar"
        >>> citations = get_citations(plain_text)
        >>> annotate("foo 1 U.S. 1 bar",[citations[0].span(), "<a>", "</a>")
    ])
        "foo <a>1 U.S. 1</a> bar"

        If source_text is provided, apply annotations to that text
        instead using diff_match_patch.

        If source_text is provided, unbalanced_tags="skip" will skip inserting
        annotations that result in invalid HTML. unbalanced_tags="wrap" will
        ensure valid HTML by wrapping annotations around any unbalanced tags.

        If use_dmp=True, use the optional diff-match-patch library, which
        guarantees minimal diffs, instead of the built in Python diff library.
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
            start = offset_updater.update(start)
            end = offset_updater.update(end)

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
        elif unbalanced_tags == "skip" or unbalanced_tags == "wrap":
            if not is_balanced_html(span_text):
                if unbalanced_tags == "skip":
                    continue
                else:
                    span_text = wrap_html_tags(span_text, after, before)
        else:
            raise ValueError(f"Unknown option '{unbalanced_tags}")

        # append each span
        out.extend(
            [
                plain_text[last_end:start],
                before,
                span_text,
                after,
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

    def __init__(self, text_before, text_after, use_dmp=False):
        """To set up, we need to populate self.offsets and self.updaters:
            >>> SpanUpdater(text_before, text_after).offsets
            [0, 4]
            >>> SpanUpdater(text_before, text_after).updaters
            [partial(shift_offset, delta=0), partial(shift_offset, delta=4)]
        This indicates that offsets 0 to 4 need to be shifted by 0,
        and offsets 4 and up need to be shifted by 4.

        use_dmp=True will use the optional diff-match-patch library, which
        guarantees minimal diffs, instead of the built in Python diff library.
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
            self.get_dmp_diff_steps if use_dmp else self.get_diff_steps
        )
        for operation, amount in get_diff_steps(text_before, text_after):
            if operation == "equal":
                # start a new range with a relative delta,
                # and push the offset forward
                offsets.append(offset)
                updaters.append(partial(shift_offset, delta=delta))
                offset += amount
            elif operation == "insert":
                # push the delta forward
                delta += amount
            else:  # operation == 'delete'
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
            [('equal', 3), ('insert', 3), ('equal', 2), ('delete', 3)]
        Meaning: to turn a into b, keep the first 3 characters the same,
        insert three new characters (we don't care what), keep the next
        two characters, delete three characters.
        """
        diffs = SequenceMatcher(a=a, b=b, autojunk=False)
        for operation, a1, a2, b1, b2 in diffs.get_opcodes():
            if operation == "insert":
                yield operation, b2 - b1
            elif operation == "replace":
                yield "delete", a2 - a1
                yield "insert", b2 - b1
            else:  # 'delete', 'equal'
                yield operation, a2 - a1

    @staticmethod
    def get_dmp_diff_steps(a: str, b: str):
        """Same as get_diff_steps but using the diff-match-patch library, which
        may work better with some inputs because it offers minimal edit
        sequences."""
        # pylint: disable=import-outside-toplevel
        # import here so the dependency is optional
        from diff_match_patch import diff_match_patch

        dmp = diff_match_patch()
        diffs = dmp.diff_main(a, b)
        for operation, text in diffs:
            if operation == diff_match_patch.DIFF_EQUAL:
                yield "equal", len(text)
            elif operation == diff_match_patch.DIFF_INSERT:
                yield "insert", len(text)
            else:  # operation == diff_match_patch.DIFF_DELETE
                yield "delete", len(text)

    def update(self, offset):
        """Shift an offset left or right."""
        index = bisect_right(self.offsets, offset) - 1
        updater = self.updaters[index]
        return updater(offset)
