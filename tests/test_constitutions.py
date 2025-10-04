"""Test cases for constitution citation parsing."""

import unittest

from eyecite.models_extended import ConstitutionCitation
from eyecite.tokenizers_extended import StateConstitutionTokenizer


class TestConstitutionTokenizers(unittest.TestCase):
    """Test constitution citation tokenizers."""

    def setUp(self):
        """Set up tokenizer for tests."""
        self.tokenizer = StateConstitutionTokenizer()

    def test_federal_constitution_main_art(self):
        """Test federal constitution article citation."""
        text = "This is governed by U.S. CONST. art. I, § 9, cl. 2."
        citations = list(self.tokenizer.find_all_citations(text))

        # Should find one citation
        self.assertEqual(len(citations), 1)
        citation = citations[0]
        self.assertIsInstance(citation, ConstitutionCitation)
        self.assertEqual(citation.jurisdiction, "United States")
        self.assertEqual(citation.article, "I")
        self.assertEqual(citation.section, "9")
        self.assertEqual(citation.clause, "2")

    def test_federal_constitution_amendment(self):
        """Test federal constitution amendment citation."""
        text = "Protected by U.S. CONST. amend. XIV, § 1."
        citations = list(self.tokenizer.find_all_citations(text))

        self.assertEqual(len(citations), 1)
        citation = citations[0]
        self.assertEqual(citation.jurisdiction, "United States")
        self.assertEqual(citation.amendment, "XIV")
        self.assertEqual(citation.section, "1")

    def test_georgia_constitution(self):
        """Test Georgia constitution citation."""
        text = "Ga. CONST. art. I, § 1, para. I."
        citations = list(self.tokenizer.find_all_citations(text))

        self.assertEqual(len(citations), 1)
        citation = citations[0]
        self.assertEqual(citation.jurisdiction, "Georgia")
        self.assertEqual(citation.article, "I")
        self.assertEqual(citation.section, "1")
        self.assertEqual(citation.paragraph, "I")

    def test_maine_constitution(self):
        """Test Maine constitution citation."""
        text = "Me. CONST. art. IV, pt. 3, § 1"
        citations = list(self.tokenizer.find_all_citations(text))

        self.assertEqual(len(citations), 1)
        citation = citations[0]
        self.assertEqual(citation.jurisdiction, "Maine")
        self.assertEqual(citation.article, "IV")
        self.assertEqual(citation.part, "3")
        self.assertEqual(citation.section, "1")

    def test_standard_state_constitution(self):
        """Test standard state constitution format."""
        text = "Va. CONST. art. IV, § 14"
        citations = list(self.tokenizer.find_all_citations(text))

        self.assertEqual(len(citations), 1)
        citation = citations[0]
        self.assertEqual(citation.jurisdiction, "Va.")
        self.assertEqual(citation.article, "IV")
        self.assertEqual(citation.section, "14")

    def test_multiple_constitutions(self):
        """Test multiple constitution citations in one text."""
        text = (
            "Both U.S. CONST. art. I, § 9 and Texas CONST. art. I, § 2 apply."
        )
        citations = list(self.tokenizer.find_all_citations(text))

        self.assertEqual(len(citations), 2)

        # First should be federal
        fed_cite = citations[0]
        self.assertEqual(fed_cite.jurisdiction, "United States")
        self.assertEqual(fed_cite.article, "I")
        self.assertEqual(fed_cite.section, "9")

        # Second should be state
        state_cite = citations[1]
        self.assertEqual(state_cite.jurisdiction, "Texas")
        self.assertEqual(state_cite.article, "I")
        self.assertEqual(state_cite.section, "2")


if __name__ == "__main__":
    unittest.main()
