from unittest import TestCase

from eyecite import get_citations
from eyecite.models import FullLawCitation


def law_section(text):
    """Return the section value of the first FullLawCitation found, or None."""
    law_cites = [
        c for c in get_citations(text) if isinstance(c, FullLawCitation)
    ]
    return law_cites[0].groups.get("section") if law_cites else None


class CitationParserTest(TestCase):
    def test_law_section_letter_suffix(self):
        """Section numbers with an uppercase letter suffix are recognized."""
        positive_samples = {
            "18 U.S.C. § 1028A": "1028A",  # the reported bug (#146)
            "18 U.S.C. § 1028": "1028",  # plain section, unaffected
        }
        for text, expected_section in positive_samples.items():
            self.assertEqual(law_section(text), expected_section)

    def test_law_section_does_not_fabricate(self):
        """No section number is fabricated from adjacent lowercase prose,
        and unsupported lowercase compound sections stay safely unmatched
        rather than returning wrong data."""
        negative_samples = [
            "42 U.S.C. §1983and the equal protection clause",
            "18 U.S.C. §1030is a computer fraud statute",
            "18 U.S.C. §1983or the due process clause",
            "42 U.S.C. § 300gg-91",  # lowercase compound -- known limitation
            "12 U.S.C. § 1749bbb-10c",  # lowercase compound -- known limitation
            "42 U.S.C. § 1396a",  # lowercase single letter -- known limitation
        ]
        for text in negative_samples:
            self.assertIsNone(
                law_section(text),
                f"Expected no section fabricated/matched from {text!r}",
            )
