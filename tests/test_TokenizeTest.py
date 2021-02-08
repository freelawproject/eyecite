from unittest import TestCase

from eyecite.models import CitationToken, StopWordToken
from eyecite.tokenizers import (
    EDITIONS_LOOKUP,
    AhocorasickTokenizer,
    default_tokenizer,
)


class TokenizerTest(TestCase):
    def test_reporter_tokenizer(self):
        """Do we tokenize correctly?"""
        tokenize = default_tokenizer.tokenize
        us_reporter = EDITIONS_LOOKUP["U.S."][0]
        us_citation = CitationToken(
            "410 U. S. 113", 17, 30, "410", "U. S.", "113", [], [us_reporter]
        )
        see_token = StopWordToken("See", 0, 3, "see")
        v_token = StopWordToken("v.", 8, 10, "v")
        self.assertEqual(
            list(tokenize("See Roe v. Wade, 410 U. S. 113 (1973)")),
            [see_token, "Roe", v_token, "Wade,", us_citation, "(1973)"],
        )
        self.assertEqual(
            list(tokenize("Foo bar eats grue, 232 U.S. (2003)")),
            ["Foo", "bar", "eats", "grue,", "232", "U.S.", "(2003)"],
        )

    def test_extractor_filter(self):
        """Does AhocorasickTokenizer only run the needed extractors?"""
        text = "See foo, 123 U.S. 456. Id."
        # text should only require four extractors --
        # stop token, US long cite, US short cite, id.
        expected_strings = {
            tuple(StopWordToken.stop_tokens),
            ("U.S.",),
            ("U.S.",),
            ("id.", "ibid."),
        }
        extractors = AhocorasickTokenizer().get_extractors(text)
        extractor_strings = set(tuple(e.strings) for e in extractors)
        self.assertEqual(expected_strings, extractor_strings)
