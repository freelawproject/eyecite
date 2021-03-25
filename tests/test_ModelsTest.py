from unittest import TestCase

from eyecite.test_factories import case_citation


class ModelsTest(TestCase):
    def test_comparison(self):
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
