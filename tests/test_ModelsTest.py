from unittest import TestCase

from eyecite.models import Citation


class ModelsTest(TestCase):
    def test_comparison(self):
        """Are two citation objects equal when their attributes are
        the same?"""
        citations = [
            Citation(reporter=2, volume="U.S.", page="2", reporter_index=2),
            Citation(reporter=2, volume="U.S.", page="2", reporter_index=2),
        ]
        print("Testing citation comparison...", end=" ")
        self.assertEqual(citations[0], citations[1])
        self.assertEqual(hash(citations[0]), hash(citations[1]))
        print("✓")
