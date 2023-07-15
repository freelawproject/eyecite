from unittest import TestCase

from eyecite import get_citations
from eyecite.models import Resource
from eyecite.test_factories import case_citation


class ModelsTest(TestCase):
    def test_citation_comparison(self):
        """Are two citation objects equal when their attributes are
        the same?"""
        citations = [
            case_citation(2, volume="2", reporter="U.S.", page="2"),
            case_citation(2, volume="2", reporter="U.S.", page="2"),
        ]
        print("Testing citation comparison...", end=" ")
        self.assertEqual(citations[0], citations[1])
        self.assertEqual(hash(citations[0]), hash(citations[1]))
        print("✓")

    def test_resource_comparison(self):
        """Are two Resource objects equal when their citations' attributes are
        the same?"""
        resources = [
            Resource(case_citation(2, volume="2", reporter="U.S.", page="2")),
            Resource(case_citation(2, volume="2", reporter="U.S.", page="2")),
        ]
        print("Testing resource comparison...", end=" ")
        self.assertEqual(resources[0], resources[1])
        self.assertEqual(hash(resources[0]), hash(resources[1]))
        print("✓")

    def test_resource_comparison_with_missing_page_cites(self):
        """Are two Resource objects different when their citations are missing
        pages, even if their other attributes are the same?"""
        citations = [
            Resource(case_citation(2, volume="2", reporter="U.S.", page="__")),
            Resource(case_citation(2, volume="2", reporter="U.S.", page="__")),
        ]
        print("Testing resource comparison with missing pages...", end=" ")
        self.assertNotEqual(citations[0], citations[1])
        self.assertNotEqual(hash(citations[0]), hash(citations[1]))
        print("✓")

    def test_citation_comparison_with_corrected_reporter(self):
        """Are two citation objects equal when their attributes are
        the same, even if the reporter has been normalized?"""
        citations = [
            case_citation(2, volume="2", reporter="U.S.", page="4"),
            case_citation(2, volume="2", reporter="U. S.", page="4"),
        ]
        print(
            "Testing citation comparison with corrected reporter...", end=" "
        )
        self.assertEqual(citations[0], citations[1])
        self.assertEqual(hash(citations[0]), hash(citations[1]))
        print("✓")

    def test_missing_page_cite_conversion(self):
        """Do citations with missing page numbers get their groups['page']
        attribute set to None?"""

        citation1 = case_citation(2, volume="2", reporter="U.S.", page="__")
        citation2 = get_citations("2 U.S. __")[0]
        print("Testing missing page conversion...", end=" ")
        self.assertIsNone(citation1.groups["page"])
        self.assertIsNone(citation2.groups["page"])
        print("✓")
