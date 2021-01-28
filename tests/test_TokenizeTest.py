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
            "410 U. S. 113", "410", "U. S.", "113", [], [us_reporter]
        )
        see_token = StopWordToken("See", "see")
        v_token = StopWordToken("v.", "v")
        self.assertEqual(
            list(tokenize("See Roe v. Wade, 410 U. S. 113 (1973)")),
            [see_token, "Roe", v_token, "Wade,", us_citation, "(1973)"],
        )
        self.assertEqual(
            list(tokenize("Foo bar eats grue, 232 U.S. (2003)")),
            ["Foo", "bar", "eats", "grue,", "232", "U.S.", "(2003)"],
        )
        # Tests that the tokenizer handles whitespace well. In the past, the
        # capital letter P in 5243-P matched the abbreviation for the Pacific
        # reporter ("P"), and the tokenizing would be wrong.
        ct_sup_reporter = EDITIONS_LOOKUP["Ct. Sup."][0]
        ct_sup_citation = CitationToken(
            "1993 Ct. Sup. 5243-P",
            "1993",
            "Ct. Sup.",
            "5243-P",
            [],
            [ct_sup_reporter],
        )
        self.assertEqual(
            list(tokenize("Failed to recognize 1993 Ct. Sup. 5243-P")),
            ["Failed", "to", "recognize", ct_sup_citation],
        )
        # Tests that the tokenizer handles commas after a reporter. In the
        # past, " U. S. " would match but not " U. S., "
        us_citation = CitationToken(
            "410 U. S., at 113",
            "410",
            "U. S.",
            "113",
            [],
            [us_reporter],
            short=True,
        )
        self.assertEqual(
            list(tokenize("See Roe v. Wade, 410 U. S., at 113")),
            [see_token, "Roe", v_token, "Wade,", us_citation],
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
