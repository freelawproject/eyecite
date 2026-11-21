import re
from textwrap import dedent
from unittest import TestCase

from eyecite import clean_text, get_citations
from eyecite.models import ReferenceCitation
from eyecite.utils import dump_citations, is_valid_name


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

    def test_is_valid_name_disallowed(self):
        """Are disallowed names rejected in any case? See #351."""
        for name in ["Commissioner", "Akerman", "Ashcroft", "Barr"]:
            self.assertFalse(is_valid_name(name), name)
        self.assertTrue(is_valid_name("Foo"))
        text = (
            "Foo v. Ashcroft, 1 U.S. 12 (2001). "
            "See Ashcroft at 62. And Foo at 63."
        )
        references = [
            c.matched_text()
            for c in get_citations(text)
            if isinstance(c, ReferenceCitation)
        ]
        self.assertEqual(references, ["Foo at 63"])
