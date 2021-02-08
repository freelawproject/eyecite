from bisect import bisect_right
from difflib import SequenceMatcher
from functools import partial
from typing import Iterable, Optional, Tuple


def annotate(
    text: str,
    annotations: Iterable[Tuple[Tuple[int, int], str, str]],
    target_text: Optional[str] = None,
    wrap_elisions: bool = True,
):
    """Insert annotations into text around each citation.
    Each annotation is a tuple of an extracted citation, before text, and
    after text.

    Example:
    >>> text = "foo 1 U.S. 1 bar"
    >>> citations = get_citations(text)
    >>> annotate("foo 1 U.S. 1 bar", [citations[0].span(), "<a>", "</a>")])
    "foo <a>1 U.S. 1</a> bar"

    If target_text is provided, apply annotations to that text
    instead using diff_match_patch.

    If target_text is provided and wrap_elisions is False, don't wrap
    internal elisions from target_text.
    """
    # set up offset_updater if we have to move annotations to target_text
    offset_updater = None
    if target_text and target_text != text:
        offset_updater = SpanUpdater(text, target_text)
        text = target_text

    # append text for each annotation to out
    annotations = sorted(annotations)
    out = []
    last_end = 0
    for span, before, after in annotations:
        # if we're applying to target_text, get target spans
        if offset_updater:
            spans = sorted(offset_updater.get_spans(*span))
            if not wrap_elisions:
                spans = [[spans[0][0], spans[-1][1]]]
        else:
            spans = [span]

        # append each span
        for start, end in spans:
            out.extend(
                [
                    text[last_end:start],
                    before,
                    text[start:end],
                    after,
                ]
            )
            last_end = end

    # append text after final citation
    if last_end < len(text):
        out.append(text[last_end:])

    return "".join(out)


class SpanUpdater:
    """Helper object to shift offsets from text_before to text_after
    using the diff-match-patch algorithm.

    For example:
    >>> text_before = "foo bar"
    >>> text_after = "foo baz bar"
    >>> SpanUpdater(text_before, text_after).get_spans(1, 6)
    [(1, 4), (8, 10)]

    This result indicates that text_before[1:6] ("oo ba") moved
    to text_after[1:4] ("oo ") + text_after[8:10] ("ba").
    """

    def __init__(self, text_before, text_after):
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
        for operation, amount in self.get_diff_steps(text_before, text_after):
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
            else:  # 'delete', 'equal'
                yield operation, a2 - a1

    # same as above using the diff-match-patch library, which may
    # work better with some inputs because it offers minimal edit sequences:
    # @staticmethod
    # def get_dmp_diff_steps(self, a: str, b: str):
    #     from diff_match_patch import diff_match_patch
    #     dmp = diff_match_patch()
    #     diffs = dmp.diff_main(a, b)
    #     for operation, text in diffs:
    #         if operation == diff_match_patch.DIFF_EQUAL:
    #             yield 'equal', len(text)
    #         elif operation == diff_match_patch.DIFF_INSERT:
    #             yield 'insert', len(text)
    #         else: # operation == diff_match_patch.DIFF_DELETE
    #             yield 'delete', len(text)

    def get_spans(self, start, end):
        """Given an input span, return one or more output spans."""
        # Get offset ranges that are covered by the start and
        # end of the input span:
        index_start = bisect_right(self.offsets, start)
        index_end = bisect_right(self.offsets, end)
        offsets = [start] + self.offsets[index_start:index_end] + [end]
        # Get updater for each offset range:
        updaters = self.updaters[index_start - 1 : index_end]
        # Return each output range:
        for updater, (span_start, span_end) in zip(
            updaters, zip(offsets, offsets[1:])
        ):
            span_start = updater(span_start)
            span_end = updater(span_end)
            # skip empty ranges
            if span_start != span_end:
                yield span_start, span_end
