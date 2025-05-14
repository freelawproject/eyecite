from unittest import TestCase

from eyecite.models import CitationToken, IdToken, StopWordToken
from eyecite.regexes import STOP_WORDS
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
            "410 U. S. 113",
            17,
            30,
            groups={"volume": "410", "reporter": "U. S.", "page": "113"},
            variation_editions=(us_reporter,),
        )
        see_token = StopWordToken("See", 0, 3, "see")
        v_token = StopWordToken("v.", 8, 10, "v")
        self.assertEqual(
            tokenize("See Roe v. Wade, 410 U. S. 113 (1973)"),
            (
                [
                    see_token,
                    " ",
                    "Roe",
                    " ",
                    v_token,
                    " ",
                    "Wade,",
                    " ",
                    us_citation,
                    " ",
                    "(1973)",
                ],
                [(0, see_token), (4, v_token), (8, us_citation)],
            ),
        )
        self.assertEqual(
            tokenize("Foo bar eats grue, 232 U.S. (2003)"),
            (
                [
                    "Foo",
                    " ",
                    "bar",
                    " ",
                    "eats",
                    " ",
                    "grue,",
                    " ",
                    "232",
                    " ",
                    "U.S.",
                    " ",
                    "(2003)",
                ],
                [],
            ),
        )

    def test_overlapping_regexes(self):
        # Make sure we find both "see" and "id." tokens even though their
        # full regexes overlap
        stop_token = StopWordToken(
            data="see", start=0, end=3, groups={"stop_word": "see"}
        )
        id_token = IdToken(data="id.", start=4, end=7)
        self.assertEqual(
            default_tokenizer.tokenize("see id. at 577."),
            (
                [
                    stop_token,
                    " ",
                    id_token,
                    " ",
                    "at",
                    " ",
                    "577.",
                ],
                [(0, stop_token), (2, id_token)],
            ),
        )

    def test_extractor_filter(self):
        """Does AhocorasickTokenizer only run the needed extractors?"""
        text = "See foo, 123 U.S. 456. Id."
        # text should only require four extractors --
        # stop token, US long cite, US short cite, id.
        expected_strings = {
            STOP_WORDS,
            ("U.S.",),
            ("U.S.",),
            ("id.", "ibid."),
        }
        extractors = AhocorasickTokenizer().get_extractors(text)
        extractor_strings = {tuple(e.strings) for e in extractors if e.strings}
        self.assertEqual(expected_strings, extractor_strings)
