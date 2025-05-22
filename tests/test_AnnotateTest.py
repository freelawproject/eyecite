import re
from pathlib import Path
from unittest import TestCase

from eyecite import annotate_citations, clean_text, get_citations
from eyecite.models import Document
from eyecite.utils import maybe_balance_style_tags


class AnnotateTest(TestCase):
    def test_annotate(self):
        def straighten_quotes(text):
            return text.replace("’", "'")

        def lower_annotator(before, text, after):
            return before + text.lower() + after

        self.maxDiff = None
        test_pairs = (
            # single cite
            ("1 U.S. 1", "<0>1 U.S. 1</0>", []),
            # cite with extra text
            ("foo 1 U.S. 1 bar", "foo <0>1 U.S. 1</0> bar", []),
            # cite with punctuation
            ("foo '1 U.S. 1' bar", "foo '<0>1 U.S. 1</0>' bar", []),
            # cite with missing page number (original underscores should be
            # rendered in annotated text even though the missing page number
            # has been normalized to None within the citation object)
            ("foo 1 U.S. ____ bar", "foo <0>1 U.S. ____</0> bar", []),
            # law cite
            (
                "foo. Mass. Gen. Laws ch. 1, § 2. bar",
                "foo. <0>Mass. Gen. Laws ch. 1, § 2</0>. bar",
                [],
            ),
            # journal cite
            (
                "foo. 1 Minn. L. Rev. 2. bar",
                "foo. <0>1 Minn. L. Rev. 2</0>. bar",
                [],
            ),
            # Id. cite
            (
                "1 U.S. 1. Foo. Id. Bar. Id. at 2.",
                "<0>1 U.S. 1</0>. Foo. <1>Id.</1> Bar. <2>Id. at 2</2>.",
                [],
            ),
            # Supra cite
            (
                "1 U.S. 1. Foo v. Bar, supra at 2.",
                "<0>1 U.S. 1</0>. Foo v. Bar, <1>supra at 2</1>.",
                [],
            ),
            # Reference cite
            (
                "Foo v. Bar 1 U.S. 1. In Foo at 2.",
                "Foo v. Bar <0>1 U.S. 1</0>. In <1>Foo at 2</1>.",
                [],
            ),
            # whitespace and html -- no unbalanced tag check
            (
                "<body>foo  <i>1   <b>U.S.</b></i>   1 bar</body>",
                "<body>foo  <i><0>1   <b>U.S.</b></i>   1</0> bar</body>",
                ["html", "inline_whitespace"],
            ),
            # whitespace and html -- unbalanced tags are repaired
            (
                "foo  <i>1 U.S.</i> 1; 2 <i>U.S.</i> 2",
                "foo  <0><i>1 U.S.</i> 1</0>; <1>2 <i>U.S.</i> 2</1>",
                ["html", "inline_whitespace"],
                {"unbalanced_tags": "skip"},
            ),
            # whitespace and html -- wrap unbalanced tags
            (
                "<i>1 U.S.</i> 1; 2 <i>U.S.</i> 2",
                "<i><0>1 U.S.</0></i><0> 1</0>; <1>2 <i>U.S.</i> 2</1>",
                ["html", "inline_whitespace"],
                {"unbalanced_tags": "wrap"},
            ),
            # tighly-wrapped html -- skip unbalanced tags (issue #54)
            (
                "foo <i>Ibid.</i> bar",
                "foo <i><0>Ibid.</0></i> bar",
                ["html", "inline_whitespace"],
                {"unbalanced_tags": "skip"},
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
            # custom annotator
            (
                "1 U.S. 1",
                "<0>1 u.s. 1</0>",
                [],
                {"annotator": lower_annotator},
            ),
            # solvable unbalanced <em> tag. Need the FullCaseCitation first
            # so the ReferenceCitation can be found
            # from https://www.courtlistener.com/api/rest/v4/opinions/8496639/
            # source: Opinion.xml_harvard
            (
                " partially secured by a debtor’s principal residence was not "
                "con-firmable. <em>Nobelman v. Am. Sav. Bank, </em>"
                "508 U.S. 324, 113 S.Ct. 2106, 124 L.Ed.2d 228 (1993). That "
                "plan proposed to bifurcate the claim and... pay the unsecured"
                "... only by a lien on the debtor’s principal residence.” "
                "<em>Nobelman </em>at 332, 113 S.Ct. 2106. Section 1123(b)(5) "
                "codifies the <em>Nobelman </em>decision in individual debtor "
                "chapter 11 cases.",
                " partially secured by a debtor’s principal residence was not con-firmable. <em>Nobelman v. Am. Sav. Bank, </em><a href='something'>508 U.S. 324</a>, <a href='something'>113 S.Ct. 2106</a>, <a href='something'>124 L.Ed.2d 228</a> (1993). That plan proposed to bifurcate the claim and... pay the unsecured... only by a lien on the debtor’s principal residence.” <em>Nobelman </em>at 332, <a href='something'>113 S.Ct. 2106</a>. Section 1123(b)(5) codifies the <em><a href='something'>Nobelman</a> </em>decision in individual debtor chapter 11 cases.",
                ["html", "all_whitespace"],
                {
                    "annotate_anchors": True,
                    "unbalanced_tags": "skip",
                    "use_markup": True,
                },
            ),
            # solvable unbalanced <i> tag
            # from https://www.courtlistener.com/api/rest/v4/opinions/2841253/
            # source: Opinion.html
            (
                "he has not agreed so to submit.’”  <i>Howsam v. Dean"
                " Witter Reynolds, Inc.</i>, 537 U.S. 79, 83, 123 S. Ct."
                " 588, 591 (2002) (combined mandamus and"
                " interlocutory appeal) (citing <i>Howsam</i> at 84, 123"
                " S. Ct. at 592)",
                "he has not agreed so to submit.’”  <i>Howsam v. Dean"
                " Witter Reynolds, Inc.</i>, <a href='something'>537 U.S."
                " 79</a>, 83, <a href='something'>123 S. Ct. 588</a>, 591"
                " (2002) (combined mandamus and interlocutory appeal)"
                " (citing <a href='something'><i>Howsam</i> at 84</a>, <a"
                " href='something'>123 S. Ct. at 592</a>)",
                ["html", "all_whitespace"],
                {
                    "annotate_anchors": True,
                    "unbalanced_tags": "skip",
                    "use_markup": True,
                },
            ),
            # The next 2 examples could be resolved if we increased the
            # character tolerance or admitted the full case name instead of
            # just one of the parties
            (
                # https://www.courtlistener.com/api/rest/v4/opinions/1535649/
                # source: xml_harvard
                "See also Styler v. Tall Oaks, Inc. (In re Hatch),"
                " 93 B.R. 263, 267 (Bankr.D. Utah 1988),"
                " <em> rev'd </em> 114 B.R. 747 (D.Utah 1989)."
                "</p>...   The court makes no"
                " determination as to whe Fifth Amendment to the"
                " constitution of the United States.” <em> Styler v."
                " Tall Oaks, Inc. (In re Hatch), </em> at 748."
                "</p>",
                "See also Styler v. Tall Oaks, Inc. (In re Hatch),"
                " <a href='something'>93 B.R. 263</a>, 267"
                " (Bankr.D. Utah 1988), <em> rev'd </em> <a"
                " href='something'>114 B.R. 747</a> (D.Utah 1989)."
                "</p>...   The court makes no"
                " determination as to whe Fifth Amendment to the"
                " constitution of the United States.” <em> Styler v."
                " Tall Oaks, Inc. (In re Hatch), </em> at 748."
                "</p>",
                ["html", "all_whitespace"],
                {
                    "annotate_anchors": True,
                    "unbalanced_tags": "skip",
                    "use_markup": True,
                },
            ),
            (
                # https://www.courtlistener.com/api/rest/v4/opinions/1985850/
                # source: html_lawbox
                "to act rationally. <i>See, e.g., </i><i>State v."
                " Wingler,</i> 25 <i>N.J.</i> 161, 175, 135 <i>A.</i>2d"
                " 468 (1957); <i>citing, ...  have been applied.'"
                " [<i>State v. Wingler</i> at 175, 135 <i>A.</i>2d"
                " 468, <i>citing, </i><i>Minnesota ex rel.</i>",
                "to act rationally. <i>See, e.g., </i><i>State v."
                " Wingler,</i> <a href='something'>25 <i>N.J.</i>"
                " 161</a>, 175, <a href='something'>135 <i>A.</i>2d"
                " 468</a> (1957); <i>citing, ...  have been applied.'"
                " [<i>State v. Wingler</i> at 175, <a"
                " href='something'>135 <i>A.</i>2d 468</a>, <i>citing,"
                " </i><i>Minnesota ex rel.</i>",
                ["html", "all_whitespace"],
                {
                    "annotate_anchors": True,
                    "unbalanced_tags": "skip",
                    "use_markup": True,
                },
            ),
            (
                """<p index="143">2016 WL 4217254</p>.<p index="144">id.</p>""",
                """<p index="143"><0>2016 WL 4217254</0></p>.<p index="144"><1>id.</1></p>""",
                ["html", "all_whitespace"],
                {
                    "annotate_anchors": False,
                    "unbalanced_tags": "skip",
                    "use_markup": True,
                },
            ),
            # Ensure < does not affect annotations
            (
                """contending it <12123 is < the most “apt.” “ ‘[A] vast enterprise usu. <p index="143">2016 WL 4217254</p>""",
                """contending it <12123 is < the most “apt.” “ ‘[A] vast enterprise usu. <p index="143"><0>2016 WL 4217254</0></p>""",
                ["html", "all_whitespace"],
                {
                    "annotate_anchors": False,
                    "unbalanced_tags": "skip",
                    "use_markup": True,
                },
            ),
        )
        for source_text, expected, clean_steps, *annotate_kwargs in test_pairs:
            annotate_kwargs = annotate_kwargs[0] if annotate_kwargs else {}
            with self.subTest(
                source_text,
                clean_steps=clean_steps,
                annotate_args=annotate_kwargs,
            ):
                if annotate_kwargs.pop("use_markup", False):
                    get_citations_args = {"markup_text": source_text}
                else:
                    get_citations_args = {"plain_text": source_text}

                document = Document(
                    **get_citations_args, clean_steps=clean_steps
                )

                cites = get_citations(
                    **get_citations_args, clean_steps=clean_steps
                )
                annotations = [
                    (c.span(), f"<{i}>", f"</{i}>")
                    for i, c in enumerate(cites)
                ]

                if annotate_kwargs.pop("annotate_anchors", False):
                    annotations = [
                        (c.span(), "<a href='something'>", "</a>")
                        for c in cites
                    ]

                annotated = annotate_citations(
                    document.plain_text,
                    annotations,
                    source_text=source_text,
                    **annotate_kwargs,
                )
                self.assertEqual(annotated, expected)

    def test_tag_balancing(self):
        """Test trickier tag balancing cases"""
        pairs = [
            (
                "Something; In <em>Nobelman </em> at 332, 113 S.Ct. 2106 (2010); Something else",
                "Nobelman </em> at 332, 113 S.Ct. 2106 (2010)",
            ),
            (
                "it established in  <i>State v. Wingler</i> something",
                "Wingler</i>",
            ),
            ("something <em>See id.</em> at 642", "id.</em> at 642"),
            ("something <i>AT&T, supra</i> something", "supra</i>"),
        ]
        for full_string, span_text in pairs:
            start, end = re.search(re.escape(span_text), full_string).span()
            _, _, balanced = maybe_balance_style_tags(start, end, full_string)
            self.assertTrue(
                re.search("^<(i|em)>", balanced),
                f"{balanced} is not the expected output",
            )

        # test that we don't get style tags beyond the inmediate neighboring
        # one
        counter_examples = [
            ("<em>see</em><em>id</em>", "id</em>", "<em>id</em>"),
            ("<em>id.</em>.<em>See</em>", "<em>id.", "<em>id.</em>"),
        ]
        for full_string, span, expected_balanced in counter_examples:
            start, end = re.search(re.escape(span), full_string).span()
            _, _, balanced = maybe_balance_style_tags(start, end, full_string)
            self.assertEqual(balanced, expected_balanced)

    def test_long_diff(self):
        """Does diffing work across a long text with many changes?"""
        opinion_text = (
            Path(__file__).parent / "assets" / "opinion.txt"
        ).read_text()
        cleaned_text = clean_text(opinion_text, ["all_whitespace"])
        annotated_text = annotate_citations(
            cleaned_text, [((902, 915), "~FOO~", "~BAR~")], opinion_text
        )
        self.assertIn("~FOO~539\n  U. S. 306~BAR~", annotated_text)

    def test_span_with_pincite(self):
        test_pairs = [
            # full case citaiton pin cite
            (
                "foo, Foo v. Bar, 550 U. S. 500, at 554-555, and so on ",
                ["550 U. S. 500, at 554-555"],
            ),
            # short case citaiton pin cite
            (
                "foo, Twombly, 550 U. S., at 554-555. ",
                ["550 U. S., at 554-555"],
            ),
            # id pin cite span
            (
                "Twombly, 550 U. S., at 554-555. ... etitive entry,’ ” id., at 551, beca",
                ["550 U. S., at 554-555", "id., at 551"],
            ),
            # reference citation pin cite span
            (
                "compelling Amick v. Liberty Mut. Ins. Co., 455 A.2d 793 (R.I. 1983). In that case ... Stats, do. See Amick at 795",
                ["455 A.2d 793", "Amick at 795"],
            ),
            # capture supra pin cite span in html
            (
                "Bell Atlantic Corp. </em>v. <em>Twombly, </em>550 U. S. 544 (2007), which discussed... apellate court’s core competency <em>Twombly, </em>550 U. S., at 557. Evaluating... In <em>Twombly</em>, supra, at 553-554, the ",
                ["550 U. S. 544", "550 U. S., at 557", "supra, at 553-554"],
            ),
        ]
        for source_text, expected in test_pairs:
            plain_text = clean_text(source_text, ["all_whitespace", "html"])
            citations = get_citations(plain_text)
            for citation in citations:
                start, end = citation.span_with_pincite()
                pin_cite_span = plain_text[start:end]
                self.assertEqual(
                    pin_cite_span,
                    expected.pop(0),
                    msg="Failed to extract pin cite span",
                )
