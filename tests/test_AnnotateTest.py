from unittest import TestCase

from eyecite import annotate, clean_text, get_citations


class AnnotateTest(TestCase):
    def test_annotate(self):
        test_pairs = (
            # single cite
            ("1 U.S. 1", "<0>1 U.S. 1</0>", [], True),
            # cite with extra text
            ("foo 1 U.S. 1 bar", "foo <0>1 U.S. 1</0> bar", [], True),
            # cite with punctuation
            ("foo '1 U.S. 1' bar", "foo '<0>1 U.S. 1</0>' bar", [], True),
            # whitespace and html tags stripped
            (
                "<body>foo  <i>1   <b>U.S.</b>   1</i> bar</body>",
                "<body>foo  <i><0>1 </0>  <b><0>U.S.</0></b>  <0> 1</0></i> bar</body>",
                ["html", "whitespace"],
                True,
            ),
            # whitespace and html tags stripped -- wrap_elisions=False
            (
                "<body>foo  <i>1   <b>U.S.</b>   1</i> bar</body>",
                "<body>foo  <i><0>1   <b>U.S.</b>   1</0></i> bar</body>",
                ["html", "whitespace"],
                False,
            ),
            # multiple Id. tags
            (
                "1 U.S. 1. Id. 2 U.S. 2. Id.",
                "<0>1 U.S. 1</0>. <1>Id.</1> <2>2 U.S. 2</2>. <3>Id.</3>",
                [],
                True,
            ),
        )
        for orig_text, expected, clean_steps, wrap_elisions in test_pairs:
            with self.subTest(
                orig_text, clean_steps=clean_steps, wrap_elisions=wrap_elisions
            ):
                text = clean_text(orig_text, clean_steps)
                cites = get_citations(text, clean=[])
                annotations = [
                    (c.span(), f"<{i}>", f"</{i}>")
                    for i, c in enumerate(cites)
                ]
                annotated = annotate(
                    text,
                    annotations,
                    target_text=orig_text,
                    wrap_elisions=wrap_elisions,
                )
                self.assertEqual(annotated, expected)
