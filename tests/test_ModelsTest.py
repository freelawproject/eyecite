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

    def test_missing_page_cite_conversion(self):
        """Do citations with missing page numbers get their groups['page']
        attribute set to None?"""

        citation1 = case_citation(2, volume="2", reporter="U.S.", page="__")
        citation2 = get_citations("2 U.S. __")[0]
        print("Testing missing page conversion...", end=" ")
        self.assertIsNone(citation1.groups["page"])
        self.assertIsNone(citation2.groups["page"])
        print("✓")

    def test_corrected_reporter_hash(self):
        """Does comparison_hash takes into account the CORRECTED reporter name"""
        print("Testing corrected reporter in comparison_hash...", end=" ")
        citation1 = case_citation(2, volume="2", reporter="U.S.", page="4")
        citation2 = case_citation(2, volume="2", reporter="U. S.", page="4")
        assert (
            citation1.comparison_hash() == citation2.comparison_hash()
        ), "Hashes should correct the name of the reporter"
        print("✓")

    def test_persistent_hash(self):
        print("Testing persistent citation hash...", end=" ")
        to_try = [
            (
                "410 U. S. 113",
                5904291041102972810493908667478218834778705903309186584557044276298549009917,
            ),
            (
                "Mass. Gen. Laws ch. 1, § 2",
                98891269647289523286825964672272849189828231198517528987112432466498422590834,
            ),
            (
                "1 Minn. L. Rev. 1.",
                69915006852161462854562160007484851653820242543399933830251998315868402860112,
            ),
            (
                "2006-Ohio-2095",
                110457034384732404262597239748797657065588592487529346764178536066702898199641,
            ),
        ]
        for citation, cit_hash in to_try:
            assert (
                get_citations(citation)[0].comparison_hash() == cit_hash
            ), "Hashes should be persistent"

        print("✓")
