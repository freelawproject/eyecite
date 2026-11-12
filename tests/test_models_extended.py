import unittest

from eyecite.models import Token
from eyecite.models_extended import (
    ConstitutionCitation,
    JournalArticleCitation,
    LegislativeBillCitation,
    ScientificIdentifierCitation,
    SessionLawCitation,
)


class TestExtendedModels(unittest.TestCase):
    """Test cases for extended citation models."""

    def test_constitution_citation_creation(self):
        """Test creating a ConstitutionCitation."""
        token = Token("U.S. CONST. art. I, § 9", 0, 18, {})
        citation = ConstitutionCitation(
            token=token,
            index=0,
            jurisdiction="United States",
            article="I",
            section="9",
        )
        self.assertEqual(citation.jurisdiction, "United States")
        self.assertEqual(citation.article, "I")
        self.assertEqual(citation.section, "9")

    def test_journal_article_creation(self):
        """Test creating a JournalArticleCitation."""
        token = Token("125 Yale L.J. 250", 0, 18, {})
        citation = JournalArticleCitation(
            token=token,
            index=0,
            volume="125",
            reporter="Yale L.J.",
            page="250",
            year="2015",
        )
        self.assertEqual(citation.volume, "125")
        self.assertEqual(citation.reporter, "Yale L.J.")
        self.assertEqual(citation.page, "250")
        self.assertEqual(citation.year, "2015")

    def test_scientific_identifier_creation(self):
        """Test creating a ScientificIdentifierCitation."""
        token = Token("DOI: 10.1038/171737a0", 0, 21, {})
        citation = ScientificIdentifierCitation(
            token=token, index=0, id_type="DOI", id_value="10.1038/171737a0"
        )
        self.assertEqual(citation.id_type, "DOI")
        self.assertEqual(citation.id_value, "10.1038/171737a0")

        # Test corrected citation
        self.assertEqual(
            citation.corrected_citation_full(), "DOI: 10.1038/171737a0"
        )

    def test_legislative_bill_creation(self):
        """Test creating a LegislativeBillCitation."""
        token = Token("H.R. 25, 118th Cong.", 0, 20, {})
        citation = LegislativeBillCitation(
            token=token,
            index=0,
            jurisdiction="United States",
            chamber="House",
            bill_num="25",
            congress_num="118",
        )
        self.assertEqual(citation.chamber, "House")
        self.assertEqual(citation.bill_num, "25")
        self.assertEqual(citation.congress_num, "118")

    def test_session_law_creation(self):
        """Test creating a SessionLawCitation."""
        token = Token("Pub. L. No. 94-579, 90 Stat. 2743", 0, 32, {})
        citation = SessionLawCitation(
            token=token,
            index=0,
            jurisdiction="United States",
            volume="90",
            page="2743",
            law_num="94-579",
        )
        self.assertEqual(citation.volume, "90")
        self.assertEqual(citation.page, "2743")
        self.assertEqual(citation.law_num, "94-579")


if __name__ == "__main__":
    unittest.main()
