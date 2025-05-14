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
