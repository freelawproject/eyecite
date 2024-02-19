from collections import defaultdict
from typing import List, Optional, Tuple
from unittest import TestCase

from eyecite import get_citations
from eyecite.models import FullCitation, Resource
from eyecite.resolve import resolve_citations


def format_resolution(resolution):
    """For debugging, convert resolution dict from resolve_citations() to
    just the matched_text() of each cite, like
        {'1 U.S. 1': ['1 U.S. 1', '1 U.S., at 2']}.
    """
    return {
        k.citation.matched_text(): [i.matched_text() for i in v]
        for k, v in resolution.items()
    }


class ResolveTest(TestCase):
    """Tests whether different types of citations (i.e., full, short form,
    supra, id) are resolved properly."""

    maxDiff = None

    def assertResolution(self, citations, expected_resolution_dict):
        actual_resolution_dict = resolve_citations(citations)
        self.assertEqual(
            format_resolution(actual_resolution_dict),
            format_resolution(expected_resolution_dict),
        )

    def checkResolution(
        self, *expected_resolutions: Tuple[Optional[int], str]
    ):
        """Helper function to check how a list of citation strings is
        resolved by resolve_citations().

        For example, suppose we want to check
        resolutions for "1 U.S. 1. 1 U.S., at 2. 1 F.2d 1. 2 U.S., at 2.".

        We can call this:
            >>> self.checkResolution(
            ...     (0, "1 U.S. 1."),
            ...     (0, "1 U.S., at 2."),
            ...     (1, "1 F.2d 1."),
            ...     (None, "2 U.S., at 2."),
            ... )
        Meaning "1 U.S. 1." and "1 U.S., at 2." should resolve into the first
        Resource, "1 F.2d 1." should resolve into the second Resource, and
        "2 U.S., at 2." shouldn't be included in any Resource.

        checkResolutionList converts the above input to expected_resolution_dict:
            {
                Resource(citation=<1 U.S. 1>): [<1 U.S. 1>, <1 U.S., at 2>],
                Resource(citation=<1 F.2d 1>): [<1 F.2d 1>],
            }

        And then calls:
            self.assertResolution(
                [<1 U.S. 1>, <1 U.S., at 2>, <1 F.2d 1>, <2 U.S., at 2>],
                expected_resolution_dict
            )
        """
        # input we're building for self.assertResolution
        expected_resolution_dict = defaultdict(list)
        citations = []

        # resources we've found so far
        resources: List[Resource] = []

        for i, cite_text in expected_resolutions:
            # extract cite and make sure there's only one:
            cites = get_citations(cite_text)
            self.assertEqual(
                len(cites),
                1,
                f"Failed to find exactly one cite in {repr(cite_text)}",
            )
            cite = cites[0]
            citations.append(cite)

            # skip clustering for cites marked "None":
            if i is None:
                continue

            # make sure resources are numbered consecutively
            if i > len(resources):
                self.fail(
                    f"Invalid row {repr((i, cite_text))}: target index {i} is too high."
                )

            # add each resource when first encountered
            if i == len(resources):
                if not isinstance(cite, FullCitation):
                    self.fail(
                        f"Invalid row {repr((i, cite_text))}: first instance of {i} must be a full cite."
                    )
                resources.append(Resource(citation=cite))

            # add current cite to resource
            expected_resolution_dict[resources[i]].append(cites[0])

        self.assertResolution(citations, expected_resolution_dict)

    def test_issue_167(self):
        self.checkResolution((0,'25 Texas L.Rev. 199'))
        
    def test_full_resolution(self):
        # Test resolving a single, full citation
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
        )
        # Test resolving two full citations to the same document
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (0, "Foo v. Bar, 1 U.S. 1."),
        )
        # Test resolving two full citations with missing page numbers but
        # otherwise identical. These should not resolve to the same document.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. ____."),
            (1, "Foo v. Bar, 1 U.S. ____."),
        )
        # Test resolving multiple full citations to different documents
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (1, "Smith v. Jones, 1 F.2d 1."),
        )
        # Supra and short cites should resolve if there are redundant full
        # cites -- redundant cites don't create ambiguity
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (0, "Foo v. Bar, 1 U.S. 1."),
            (0, "Foo, 1 U.S., at 2."),
            (0, "Foo, supra at 2."),
        )

    def test_supra_resolution(self):
        # Test resolving a supra citation
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (0, "Foo, supra, at 2."),
        )
        # Test resolving a supra citation when its antecedent guess matches
        # two possible candidates. We expect the supra citation to not
        # be resolved.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (1, "Foo v. Bar, 1 U.S. 2."),
            (None, "Foo, supra, at 2."),
        )

    def test_short_resolution(self):
        # Test resolving a short form citation
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (0, "1 U.S., at 2."),
        )
        # Test resolving a short form citation with an antecedent
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (0, "Foo, 1 U.S., at 2."),
        )
        # Test resolving a short form citation when its reporter and
        # volume match two possible candidates. We expect its antecedent
        # guess to provide the correct tiebreaker.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (1, "Wrong v. Wrong, 1 U.S. 2."),
            (0, "Foo, 1 U.S., at 2."),
        )
        # Test resolving a short form citation when its reporter and
        # volume match two possible candidates, and when it lacks a
        # meaningful antecedent. We expect the short form citation to not
        # be resolved.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (1, "Boo v. Far, 1 U.S. 2."),
            (None, "1 U.S., at 2."),
        )
        # Test resolving a short form citation when its reporter and
        # volume match two possible candidates, and when its antecedent
        # guess also matches multiple possibilities. We expect the short
        # form citation to not be resolved.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (1, "Foo v. Bar, 1 U.S. 2."),
            (None, "Foo, 1 U.S., at 2."),
        )
        # Test resolving a short form citation when its reporter and
        # volume are erroneous. We expect the short form citation to not
        # be resolved.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (None, "2 F.2d, at 2."),
        )

    def test_ambigous_short_cite(self):
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (1, "See Foo, 1 U.S. 2."),
            (None, "Foo, 1 U.S., at 2."),
        )

    def test_id_resolution(self):
        # Test resolving an Id. citation
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (0, "Id."),
            (0, "Id. at 2."),
        )
        # Test resolving an Id. citation when the previous citation
        # resolution failed. We expect the Id. citation to also not be
        # resolved.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (None, "2 F.2d, at 2."),
            (None, "Id. at 2."),
        )
        # Test resolving an Id. citation when the previous citation is to an
        # unknown document. Since we can't resolve those documents,
        # we expect the Id. citation to also not be matched.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (None, "Blah § 2."),
            (None, "Id. at 2."),
        )
        # Test resolving an Id. citation when it is the first citation
        # found. Since there is nothing before it, we expect no matches to
        # be returned.
        self.checkResolution(
            (None, "Id. at 2."),
        )
        # Id. cites will not match if their pin cite is
        # invalid relative to the target full cite.
        self.checkResolution(
            # too high:
            (0, "Foo v. Bar, 1 U.S. 100."),
            (None, "Id. at 500."),
            # too low:
            (0, "Foo v. Bar, 1 U.S. 100."),  # reset
            (None, "Id. at 50."),
            # edge case -- pin cites with non-digits at beginning are
            # assumed not to match cites with a "page" value:
            (0, "Foo v. Bar, 1 U.S. 100."),  # reset
            (None, "Id. at ¶ 100."),
            # edge case -- cites without a "page" group are assumed to match:
            (1, "Ala. Code § 92"),
            (1, "Id. at 2000"),
        )
        # Test resolving an Id. citation with a pin cite when the previous
        # citation only has a placeholder page. We expect this to fail.
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. ___"),
            (None, "Id. at 100."),
        )

    def test_non_case_resolution(self):
        """Test law and journal resolution."""
        self.checkResolution(
            (0, "Foo v. Bar, 1 U.S. 1."),
            (0, "Id. at 2."),
            (1, "Mass. Gen. Laws ch. 1, § 2"),
            (1, "Id."),
            (0, "Foo, supra, at 2."),
            (2, "1 Minn. L. Rev. 1."),
            (2, "Id. at 2."),
            (0, "Foo, 1 U.S., at 2."),
        )

    def test_complex_resolution(self):
        """
        Tests whether resolution works with a more complex string.
        Inspired by: https://github.com/freelawproject/courtlistener/blob/d65d4c1e11328fd9f24dabd2aa9a792b4e725832/cl/citations/tests.py#L546
        """
        self.checkResolution(
            (0, "Blah blah Foo v. Bar 1 U.S. 1, 77 blah blah."),
            (1, "Asdf asdf Qwerty v. Uiop 2 F.3d 500, 555."),
            (0, "Also check out Foo, 1 U.S. at 99."),
            (1, "Then let's cite Qwerty, supra, at 567."),
            (0, "See also Foo, supra, at 101 as well."),
            (2, "Another full citation is Lorem v. Ipsum 1 U. S. 50."),
            (1, "Quoting Qwerty, “something something”, 2 F.3d 500, at 559."),
            (None, "This case is similar to Fake, supra,"),
            (1, "and Qwerty supra, as well."),
            (1, "This should resolve to the foregoing. Ibid."),
            (1, "This should also convert appropriately, see Id. at 567."),
            (
                None,
                "But this fails because the pin cite is too low, see Id. at 400.",
            ),
            (
                None,
                "This should fail to resolve because the reporter and citation is ambiguous, 1 U. S., at 51.",
            ),
            (2, "However, this should succeed, Lorem, 1 U.S., at 52."),
        )
