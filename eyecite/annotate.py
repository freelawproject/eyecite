from bisect import bisect_left, bisect_right
from collections.abc import Callable, Iterable
from difflib import SequenceMatcher
from functools import partial
from logging import getLogger
from typing import TYPE_CHECKING, Any

import fast_diff_match_patch

from eyecite.utils import (
    is_balanced_html,
    maybe_balance_style_tags,
    wrap_html_tags,
)

if TYPE_CHECKING:
    from eyecite.models import Document

logger = getLogger(__name__)


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


def annotate_citations(
    document: "Document",
    annotations: Iterable[tuple[tuple[int, int], Any, Any]],
    unbalanced_tags: str = "unchecked",
    annotator: Callable[[Any, str, Any], str] | None = None,
) -> str:
    """Given a `eyecite.models.Document` and a list of citation positions,
    insert annotations into the text surrounding each citation. This could be
    useful for linking the citations to a URL, or otherwise indicating that
    they were successfully parsed or resolved.

    Example:
    >>> document = Document("foo 1 U.S. 1 bar")
    >>> citations = get_citations(document)
    >>> annotate_citations(document, [(citations[0].span(), "<a>", "</a>")])
    >>>
    >>> returns: "foo <a>1 U.S. 1</a> bar"

    Args:
        document: The `eyecite.models.Document` object from which the
            citations were parsed.
        annotations: A `Tuple` of (1) the start and end positions of the
            citation in the text, (2) the text to insert before the citation,
            and (3) the text to insert after the citation.
        unbalanced_tags: Optional instruction for how to handle the insertion
            of annotations into a `eyecite.models.Document` instantiated from
            markup. If `unbalanced_tags="unchecked"` (default), no handling
            is performed. If `unbalanced_tags="skip"`, annotations that would
            result in the creation of invalid markup are skipped. If
            `unbalanced_tags="wrap"`, annotations that would result in the
            creation of invalid markup are wrapped in additional tags to
            ensure balance.
        annotator: If provided, should be a function that takes three
            arguments (the text to insert before, the text of the citation,
            and the text to insert after) and returns the annotation. This is
            useful for customizing the annotation action: If you don't pass
            this function, eyecite will simply concatenate the before_text,
            citation_text, and after_text together for each annotation.
    Returns:
        The annotated text.
    """
    if unbalanced_tags not in ["unchecked", "skip", "wrap"]:
        raise ValueError(f"Unknown option '{unbalanced_tags}")

    # if no cleaning was applied to the document, then no need to calculate
    # any offsets
    if document.source_text == document.cleaned_text:
        offset_updater = None
    else:
        offset_updater = document.cleaned_to_source

    # append text for each annotation to out
    annotations = sorted(annotations)
    out = []
    last_end = 0
    for (start, end), before, after in annotations:
        # update offsets if necessary
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

        span_text = document.source_text[start:end]

        # handle HTML tags
        if unbalanced_tags == "unchecked":
            pass
        elif not is_balanced_html(span_text):
            if unbalanced_tags == "wrap":
                span_text = wrap_html_tags(span_text, after, before)
            else:  # "skip" case
                original_span_text = span_text
                start, end, span_text = maybe_balance_style_tags(
                    start, end, document.source_text
                )
                if not is_balanced_html(span_text):
                    logger.warning(
                        "Citation was not annotated due to unbalanced tags %s",
                        original_span_text,
                    )
                    continue

        if annotator is not None:
            annotated_span = annotator(before, span_text, after)
        else:
            annotated_span = before + span_text + after

        # append each span
        out.extend(
            [
                document.source_text[last_end:start],
                annotated_span,
            ]
        )
        last_end = end

    # append text after final citation
    if last_end < len(document.source_text):
        out.append(document.source_text[last_end:])

    return "".join(out)
