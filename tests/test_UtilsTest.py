from unittest import TestCase

import exrex
import roman

from eyecite.utils import ROMAN_NUMERAL_REGEX, clean_text


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
            print(
                "Testing clean_text for %s" % text.replace("\n", " "), end=" "
            )
            result = clean_text(text, steps)
            self.assertEqual(
                result,
                expected,
            )
            print("✓")

    def test_clean_text_invalid(self):
        with self.assertRaises(ValueError):
            clean_text("foo", ["invalid"])

    def test_roman_numeral_regex(self):
        """Make sure ROMAN_NUMERAL_REGEX matches all numbers between 1-199
        except 5, 50, 100."""
        expected = (
            list(range(1, 5))
            + list(range(6, 50))
            + list(range(51, 100))
            + list(range(101, 200))
        )
        actual = sorted(
            roman.fromRoman(n.upper())
            for n in exrex.generate(ROMAN_NUMERAL_REGEX)
        )
        self.assertEqual(actual, expected)
