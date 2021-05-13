from unittest import TestCase

import exrex
import roman

from eyecite.regexes import ROMAN_NUMERAL_REGEX


class RegexesTest(TestCase):
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
