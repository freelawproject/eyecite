from unittest import TestCase

from eyecite import get_citations
from eyecite.models import Resource
from eyecite.test_factories import (
    case_citation,
    id_citation,
    journal_citation,
    law_citation,
    unknown_citation,
)


class ModelsTest(TestCase):
    def test_citation_comparison(self):
        """Are two citation objects equal when their attributes are
        the same?"""
        for factory in [case_citation, journal_citation, law_citation]:
            citations = [
                factory(),
                factory(),
            ]
            print(f"Testing {factory.__name__} comparison...", end=" ")
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

    def test_citation_comparison_with_missing_page_cites(self):
        """Are two citation objects different when one of them is missing
        a page, even if their other attributes are the same?"""
        citations = [
            case_citation(2, volume="2", reporter="U.S.", page="__"),
            case_citation(2, volume="2", reporter="U.S.", page="__"),
        ]
        print("Testing citation comparison with missing pages...", end=" ")
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

    def test_citation_comparison_with_different_source_text(self):
        """Are two citation objects equal when their attributes are
        the same, even if they have different source text?"""
        citations = [
            case_citation(
                source_text="foobar", volume="2", reporter="U.S.", page="4"
            ),
            case_citation(
                source_text="foo", volume="2", reporter="U.S.", page="4"
            ),
        ]
        print(
            "Testing citation comparison with different source text...",
            end=" ",
        )
        self.assertEqual(citations[0], citations[1])
        self.assertEqual(hash(citations[0]), hash(citations[1]))
        print("✓")

    def test_citation_comparison_with_nominative_reporter(self):
        """Are two citation objects equal when their attributes are
        the same, even if one of them has a nominative reporter?"""
        citations = [
            get_citations("5 U.S. 137")[0],
            get_citations("5 U.S. (1 Cranch) 137")[0],
        ]
        print(
            "Testing citation comparison with nominative reporter...", end=" "
        )
        self.assertEqual(citations[0], citations[1])
        self.assertEqual(hash(citations[0]), hash(citations[1]))
        print("✓")

    def test_citation_comparison_with_different_reporter(self):
        """Are two citation objects different when they have different
        reporters, even if their other attributes are the same?
        (sanity check)"""
        citations = [
            case_citation(2, volume="2", reporter="F. Supp.", page="4"),
            case_citation(2, volume="2", reporter="U. S.", page="4"),
        ]
        print(
            "Testing citation comparison with different reporters...", end=" "
        )
        self.assertNotEqual(citations[0], citations[1])
        self.assertNotEqual(hash(citations[0]), hash(citations[1]))
        print("✓")

    def test_id_citation_comparison(self):
        """Are two IdCitation objects always different?"""
        citations = [
            id_citation("Id.,", metadata={"pin_cite": "at 123"}),
            id_citation("Id.,", metadata={"pin_cite": "at 123"}),
        ]
        print("Testing id citation comparison...", end=" ")
        self.assertNotEqual(citations[0], citations[1])
        self.assertNotEqual(hash(citations[0]), hash(citations[1]))
        print("✓")

    def test_unknown_citation_comparison(self):
        """Are two UnknownCitation objects always different?"""
        citations = [
            unknown_citation("§99"),
            unknown_citation("§99"),
        ]
        print("Testing unknown citation comparison...", end=" ")
        self.assertNotEqual(citations[0], citations[1])
        self.assertNotEqual(hash(citations[0]), hash(citations[1]))
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

    def test_persistent_hash(self):
        """Are object hashes reproducible across runs?"""
        print("Testing persistent citation hash...", end=" ")
        objects = [
            (
                case_citation(),
                1009797070,
            ),
            (
                journal_citation(),
                -1332833206,
            ),
            (
                law_citation(),
                554454242,
            ),
            (
                Resource(case_citation()),
                -666984820,
            ),
        ]
        for citation, citation_hash in objects:
            self.assertEqual(hash(citation), citation_hash)
            print("✓")

    def test_hash_function_identity(self):
        """Do hash() and __hash__() output the same hash?"""
        citation = case_citation()
        resource = Resource(case_citation())
        print("Testing hash function identity...", end=" ")
        self.assertEqual(hash(citation), citation.__hash__())
        self.assertEqual(hash(resource), resource.__hash__())
        print("✓")
