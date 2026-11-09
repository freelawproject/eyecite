import re
from textwrap import dedent
from unittest import TestCase

from eyecite import clean_text, get_citations
from eyecite.utils import dump_citations


class UtilsTest(TestCase):
    def test_clean_text(self):
        test_pairs = (
            (["inline_whitespace"], "  word \t \n  word  ", " word \n word "),
            (["all_whitespace"], "  word \t \n  word  ", " word word "),
            (["underscores"], "__word__word_", "wordword_"),
            (["html"], " <style>ignore</style> <i> word </i> ", " word "),
            (
                ["html", "underscores", "inline_whitespace"],
                " <style>ignore</style> __ <i> word  word </i>",
                " word word ",
            ),
            # text that continues after an inline element is not split
            # (#364)
            (
                ["html"],
                '<p><a class="citation">410 U.S. 113</a>, 115 (1973)</p>',
                "410 U.S. 113, 115 (1973)",
            ),
            (
                ["html"],
                "<a>Conn. Gen. Stat. § 10</a>-236b(f)",
                "Conn. Gen. Stat. § 10-236b(f)",
            ),
            (["html"], "<em>Id</em>. at 263", "Id. at 263"),
            (
                ["html", "inline_whitespace"],
                "104 <i>L.Ed.</i>2d 487",
                "104 L.Ed.2d 487",
            ),
            (["html"], "<i><b>Id</b></i>.", "Id."),
            (["html"], "can<page-number>*642</page-number>not", "cannot"),
            # block elements, opening elements, footnote marks and
            # whitespace still separate text
            (["html"], "<p>word</p><p>word</p>", "word word"),
            (["html"], "<div>word<br>word</div>", "word word"),
            (["html"], "<p>word</p>.", "word ."),
            (
                ["html"],
                "<p>word</p>\n<p><page-number>*2</page-number>word</p>",
                "word word",
            ),
            (["html"], "<td>word</td><td>word</td>", "word word"),
            (["html"], "<li><i>word</i></li><li>word</li>", "word word"),
            (["html"], "<em>word</em><em>word</em>", "word word"),
            (["html"], "word<sup>1</sup>word", "word 1 word"),
            (["html"], "<i><b>word</b> </i>word", "word word"),
        )
        for steps, text, expected in test_pairs:
            print("Testing clean_text for " + text.replace("\n", " "), end=" ")
            result = clean_text(text, steps)
            self.assertEqual(
                result,
                expected,
            )
            print("✓")

    def test_clean_text_invalid(self):
        with self.assertRaises(ValueError):
            clean_text("foo", ["invalid"])

    def test_dump_citations(self):
        text = "blah. Foo v. Bar, 1 U.S. 2, 3-4 (1999). blah"
        cites = get_citations(text)
        dumped_text = dump_citations(cites, text)
        dumped_text = re.sub(r"\x1B.*?m", "", dumped_text)  # strip colors
        expected = dedent(
            """
        FullCaseCitation: blah. Foo v. Bar, 1 U.S. 2, 3-4 (1999). blah
          * groups
            * volume='1'
            * reporter='U.S.'
            * page='2'
          * metadata
            * pin_cite='3-4'
            * pin_cite_span_end=31
            * year='1999'
            * court='scotus'
            * plaintiff='Foo'
            * defendant='Bar'
          * year=1999
        """
        )
        self.assertEqual(dumped_text.strip(), expected.strip())
