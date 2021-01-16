from unittest import TestCase

from eyecite.utils import clean_text


class UtilsTest(TestCase):
    def test_clean_text(self):
        test_pairs = (
            (["whitespace"], "  word  \n  word  ", "word \n word"),
            (["underscores"], "__word__word_", "wordword_"),
            (["html"], " <style>ignore</style> <i> word </i> ", " word "),
            (
                ["html", "underscores", "whitespace"],
                " <style>ignore</style> __ <i> word  word </i>",
                "word word",
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
