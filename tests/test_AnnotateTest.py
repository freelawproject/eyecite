from unittest import TestCase

from eyecite import annotate, clean_text, get_citations


class AnnotateTest(TestCase):
    def test_annotate(self):
        def straighten_quotes(text):
            return text.replace("’", "'")

        test_pairs = (
            # single cite
            ("1 U.S. 1", "<0>1 U.S. 1</0>", []),
            # cite with extra text
            ("foo 1 U.S. 1 bar", "foo <0>1 U.S. 1</0> bar", []),
            # cite with punctuation
            ("foo '1 U.S. 1' bar", "foo '<0>1 U.S. 1</0>' bar", []),
            # Id. cite
            (
                "1 U.S. 1. Foo. Id. Bar. Id. at 2.",
                "<0>1 U.S. 1</0>. Foo. <1>Id.</1> Bar. <2>Id. at 2.</2>",
                [],
            ),
            # Supra cite
            (
                "1 U.S. 1. Foo v. Bar, supra at 2.",
                "<0>1 U.S. 1</0>. Foo v. Bar, <1>supra</1> at 2.",
                [],
            ),
            # whitespace and html -- no unbalanced tag check
            (
                "<body>foo  <i>1   <b>U.S.</b></i>   1 bar</body>",
                "<body>foo  <i><0>1   <b>U.S.</b></i>   1</0> bar</body>",
                ["html", "spaces_and_tabs"],
            ),
            # whitespace and html -- skip unbalanced tags
            (
                "foo  <i>1 U.S.</i> 1; 2 <i>U.S.</i> 2",
                "foo  <i>1 U.S.</i> 1; <1>2 <i>U.S.</i> 2</1>",
                ["html", "spaces_and_tabs"],
                {"unbalanced_tags": "skip"},
            ),
            # whitespace and html -- wrap unbalanced tags
            (
                "<i>1 U.S.</i> 1; 2 <i>U.S.</i> 2",
                "<i><0>1 U.S.</0></i><0> 1</0>; <1>2 <i>U.S.</i> 2</1>",
                ["html", "spaces_and_tabs"],
                {"unbalanced_tags": "wrap"},
            ),
            # whitespace containing linebreaks
            ("1\nU.S. 1", "<0>1\nU.S. 1</0>", ["all_whitespace"]),
            # multiple Id. tags
            (
                "1 U.S. 1. Id. 2 U.S. 2. Id.",
                "<0>1 U.S. 1</0>. <1>Id.</1> <2>2 U.S. 2</2>. <3>Id.</3>",
                [],
            ),
            # replacement in cleaners
            (
                "1 Abbott’s Pr.Rep. 1",
                "<0>1 Abbott’s Pr.Rep. 1</0>",
                [straighten_quotes],
            ),
        )
        for source_text, expected, clean_steps, *annotate_kwargs in test_pairs:
            annotate_kwargs = annotate_kwargs[0] if annotate_kwargs else {}
            with self.subTest(
                source_text,
                clean_steps=clean_steps,
                annotate_args=annotate_kwargs,
            ):
                plain_text = clean_text(source_text, clean_steps)
                cites = get_citations(plain_text)
                annotations = [
                    (c.span(), f"<{i}>", f"</{i}>")
                    for i, c in enumerate(cites)
                ]
                annotated = annotate(
                    plain_text,
                    annotations,
                    source_text=source_text,
                    **annotate_kwargs,
                )
                self.assertEqual(annotated, expected)
