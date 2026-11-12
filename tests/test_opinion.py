"""Test cases for Attorney General opinion citation parsing."""

import unittest
from pathlib import Path

from eyecite.models_extended import AttorneyGeneralCitation
from eyecite.tokenizers_extended import AttorneyGeneralOpinionsTokenizer


class TestAttorneyGeneralOpinions(unittest.TestCase):
    """Test Attorney General opinion citation detection."""

    def setUp(self):
        """Set up tokenizer and asset paths."""
        self.tokenizer = AttorneyGeneralOpinionsTokenizer()
        assets_dir = Path(__file__).parent / "assets"
        self.opinion_al_path = assets_dir / "opinion_AL.txt"

    def test_alabama_ag_opinion(self):
        """Test extraction of AG opinions from Alabama opinion text."""
        text = self.opinion_al_path.read_text(encoding="utf-8")
        citations = list(self.tokenizer.find_all_citations(text))
        self.assertGreater(len(citations), 0)
        for cite in citations:
            self.assertIsInstance(cite, AttorneyGeneralCitation)


if __name__ == "__main__":
    unittest.main()
