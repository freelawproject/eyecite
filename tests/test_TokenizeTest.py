from unittest import TestCase

from eyecite.reporter_tokenizer import tokenize


class TokenizerTest(TestCase):
    def test_reporter_tokenizer(self):
        """Do we tokenize correctly?"""
        self.assertEqual(
            tokenize("See Roe v. Wade, 410 U. S. 113 (1973)"),
            ["See", "Roe", "v.", "Wade,", "410", "U. S.", "113", "(1973)"],
        )
        self.assertEqual(
            tokenize("Foo bar eats grue, 232 Vet. App. (2003)"),
            ["Foo", "bar", "eats", "grue,", "232", "Vet. App.", "(2003)"],
        )
        # Tests that the tokenizer handles whitespace well. In the past, the
        # capital letter P in 5243-P matched the abbreviation for the Pacific
        # reporter ("P"), and the tokenizing would be wrong.
        self.assertEqual(
            tokenize("Failed to recognize 1993 Ct. Sup. 5243-P"),
            ["Failed", "to", "recognize", "1993", "Ct. Sup.", "5243-P"],
        )
        # Tests that the tokenizer handles commas after a reporter. In the
        # past, " U. S. " would match but not " U. S., "
        self.assertEqual(
            tokenize("See Roe v. Wade, 410 U. S., at 113"),
            ["See", "Roe", "v.", "Wade,", "410", "U. S.", ",", "at", "113"],
        )
