# -*- coding: utf-8 -*-

from datetime import datetime
from unittest import TestCase

from reporters_db import REPORTERS

from microscope.find_citations import get_citations
from microscope.helpers import is_date_in_reporter
from microscope.models import (
    FullCitation,
    IdCitation,
    NonopinionCitation,
    ShortformCitation,
    SupraCitation,
)


class FindTest(TestCase):
    def test_find_citations(self):
        """Can we find and make citation objects from strings?"""
        # fmt: off
        test_pairs = (
            # Basic test
            ('1 U.S. 1',
             [FullCitation(volume=1, reporter='U.S.', page='1',
                           canonical_reporter='U.S.', lookup_index=0,
                           court='scotus', reporter_index=1,
                           reporter_found='U.S.')]),
            # Basic test of non-case name before citation (should not be found)
            ('lissner test 1 U.S. 1',
             [FullCitation(volume=1, reporter='U.S.', page='1',
                           canonical_reporter='U.S.', lookup_index=0,
                           court='scotus', reporter_index=3,
                           reporter_found='U.S.')]),
            # Test with plaintiff and defendant
            ('lissner v. test 1 U.S. 1',
             [FullCitation(plaintiff='lissner', defendant='test', volume=1,
                           reporter='U.S.', page='1',
                           canonical_reporter='U.S.', lookup_index=0,
                           court='scotus', reporter_index=4,
                           reporter_found='U.S.')]),
            # Test with plaintiff, defendant and year
            ('lissner v. test 1 U.S. 1 (1982)',
             [FullCitation(plaintiff='lissner', defendant='test', volume=1,
                           reporter='U.S.', page='1', year=1982,
                           canonical_reporter='U.S.', lookup_index=0,
                           court='scotus', reporter_index=4,
                           reporter_found='U.S.')]),
            # Test with different reporter than all of above.
            ('bob lissner v. test 1 F.2d 1 (1982)',
             [FullCitation(plaintiff='lissner', defendant='test', volume=1,
                           reporter='F.2d', page='1', year=1982,
                           canonical_reporter='F.', lookup_index=0,
                           reporter_index=5, reporter_found='F.2d')]),
            # Test with court and extra information
            ('bob lissner v. test 1 U.S. 12, 347-348 (4th Cir. 1982)',
             [FullCitation(plaintiff='lissner', defendant='test', volume=1,
                           reporter='U.S.', page='12', year=1982,
                           extra='347-348', court='ca4',
                           canonical_reporter='U.S.', lookup_index=0,
                           reporter_index=5, reporter_found='U.S.')]),
            # Test with text before and after and a variant reporter
            ('asfd 22 U. S. 332 (1975) asdf',
             [FullCitation(volume=22, reporter='U.S.', page='332', year=1975,
                           canonical_reporter='U.S.', lookup_index=0,
                           court='scotus', reporter_index=2,
                           reporter_found='U. S.')]),
            # Test with finding reporter when it's a second edition
            ('asdf 22 A.2d 332 asdf',
             [FullCitation(volume=22, reporter='A.2d', page='332',
                           canonical_reporter='A.', lookup_index=0,
                           reporter_index=2, reporter_found='A.2d')]),
            # Test if reporter in string will find proper citation string
            ('A.2d 332 11 A.2d 333',
             [FullCitation(volume=11, reporter='A.2d', page='333',
                           canonical_reporter='A.', lookup_index=0,
                           reporter_index=3, reporter_found='A.2d')]),
            # Test finding a variant second edition reporter
            ('asdf 22 A. 2d 332 asdf',
             [FullCitation(volume=22, reporter='A.2d', page='332',
                           canonical_reporter='A.', lookup_index=0,
                           reporter_index=2, reporter_found='A. 2d')]),
            # Test finding a variant of an edition resolvable by variant alone.
            ('171 Wn.2d 1016',
             [FullCitation(volume=171, reporter='Wash. 2d', page='1016',
                           canonical_reporter='Wash.', lookup_index=1,
                           reporter_index=1, reporter_found='Wn.2d')]),
            # Test finding two citations where one of them has abutting
            # punctuation.
            ('2 U.S. 3, 4-5 (3 Atl. 33)',
             [FullCitation(volume=2, reporter="U.S.", page='3', extra='4-5',
                           canonical_reporter="U.S.", lookup_index=0,
                           reporter_index=1, reporter_found="U.S.",
                           court='scotus'),
              FullCitation(volume=3, reporter="A.", page='33',
                           canonical_reporter="A.", lookup_index=0,
                           reporter_index=5, reporter_found="Atl.")]),
            # Test with the page number as a Roman numeral
            ('12 Neb. App. lxiv (2004)',
             [FullCitation(volume=12, reporter='Neb. Ct. App.', page='lxiv',
                           year=2004, canonical_reporter='Neb. Ct. App.',
                           lookup_index=0, reporter_index=1,
                           reporter_found='Neb. App.')]),
            # Test with page range with a weird suffix
            ('559 N.W.2d 826|N.D.',
             [FullCitation(volume=559, reporter='N.W.2d', page='826',
                           canonical_reporter='N.W.', lookup_index=0,
                           reporter_index=1, reporter_found='N.W.2d')]),
            # Test with malformed/missing page number
            ('1 U.S. f24601', []),
            # Test with the 'digit-REPORTER-digit' corner-case formatting
            ('2007-NMCERT-008',
             [FullCitation(volume=2007, reporter='NMCERT', page='008',
                           canonical_reporter='NMCERT', lookup_index=0,
                           reporter_index=1, reporter_found='NMCERT')]),
            ('2006-Ohio-2095',
             [FullCitation(volume=2006, reporter='Ohio', page='2095',
                           canonical_reporter='Ohio', lookup_index=0,
                           reporter_index=1, reporter_found='Ohio')]),
            ('2017 IL App (4th) 160407WC',
             [FullCitation(volume=2017, reporter='IL App (4th)',
                           page='160407WC', canonical_reporter='IL App (4th)',
                           lookup_index=0, reporter_index=1,
                           reporter_found='IL App (4th)')]),
            ('2017 IL App (1st) 143684-B',
             [FullCitation(volume=2017, reporter='IL App (1st)',
                           page='143684-B', canonical_reporter='IL App (1st)',
                           lookup_index=0, reporter_index=1,
                           reporter_found='IL App (1st)')]),
            # Test first kind of short form citation (meaningless antecedent)
            ('before asdf 1 U. S., at 2',
             [ShortformCitation(reporter='U.S.', page='2', volume=1,
                                antecedent_guess='asdf', court='scotus',
                                canonical_reporter='U.S.', lookup_index=0,
                                reporter_found='U. S.', reporter_index=3)]),
            # Test second kind of short form citation (meaningful antecedent)
            ('before asdf, 1 U. S., at 2',
             [ShortformCitation(reporter='U.S.', page='2', volume=1,
                                antecedent_guess='asdf,', court='scotus',
                                canonical_reporter='U.S.', lookup_index=0,
                                reporter_found='U. S.', reporter_index=3)]),
            # Test short form citation with preceding ASCII quotation
            ('before asdf,” 1 U. S., at 2',
             [ShortformCitation(reporter='U.S.', page='2', volume=1,
                                antecedent_guess='asdf,”', court='scotus',
                                canonical_reporter='U.S.', lookup_index=0,
                                reporter_found='U. S.', reporter_index=3)]),
            # Test short form citation when case name looks like a reporter
            ('before Johnson, 1 U. S., at 2',
             [ShortformCitation(reporter='U.S.', page='2', volume=1,
                                antecedent_guess='Johnson,', court='scotus',
                                canonical_reporter='U.S.', lookup_index=0,
                                reporter_found='U. S.', reporter_index=4)]),
            # Test short form citation with no comma after reporter
            ('before asdf, 1 U. S. at 2',
             [ShortformCitation(reporter='U.S.', page='2', volume=1,
                                antecedent_guess='asdf,', court='scotus',
                                canonical_reporter='U.S.', lookup_index=0,
                                reporter_found='U. S.', reporter_index=3)]),
            # Test short form citation at end of document (issue #1171)
            ('before asdf, 1 U. S. end', []),
            # Test short form citation with a page range
            ('before asdf, 1 U. S., at 20-25',
             [ShortformCitation(reporter='U.S.', page='20-25', volume=1,
                                antecedent_guess='asdf,', court='scotus',
                                canonical_reporter='U.S.', lookup_index=0,
                                reporter_found='U. S.', reporter_index=3)]),
            # Test short form citation with a page range with weird suffix
            ('before asdf, 1 U. S., at 20-25\\& n. 4',
             [ShortformCitation(reporter='U.S.', page='20-25', volume=1,
                                antecedent_guess='asdf,', court='scotus',
                                canonical_reporter='U.S.', lookup_index=0,
                                reporter_found='U. S.', reporter_index=3)]),
            # Test first kind of supra citation (standard kind)
            ('before asdf, supra, at 2',
             [SupraCitation(antecedent_guess='asdf,', page='2', volume=None)]),
            # Test second kind of supra citation (with volume)
            ('before asdf, 123 supra, at 2',
             [SupraCitation(antecedent_guess='asdf,', page='2', volume=123)]),
            # Test third kind of supra citation (sans page)
            ('before asdf, supra, foo bar',
             [SupraCitation(antecedent_guess='asdf,', page=None, volume=None)]),
            # Test third kind of supra citation (with period)
            ('before asdf, supra. foo bar',
             [SupraCitation(antecedent_guess='asdf,', page=None, volume=None)]),
            # Test supra citation at end of document (issue #1171)
            ('before asdf, supra end',
             [SupraCitation(antecedent_guess='asdf,', page=None, volume=None)]),
            # Test Ibid. citation
            ('foo v. bar 1 U.S. 12. asdf. Ibid. foo bar lorem ipsum.',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='Ibid.',
                         after_tokens=['foo', 'bar', 'lorem'])]),
            # Test italicized Ibid. citation
            ('<p>before asdf. <i>Ibid.</i></p> <p>foo bar lorem</p>',
             [IdCitation(id_token='Ibid.',
                         after_tokens=['foo', 'bar', 'lorem'])]),
            # Test Id. citation
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id., at 123. foo bar',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='Id.,',
                         after_tokens=['at', '123.'],
                         has_page=True)]),
            # Test italicized Id. citation
            ('<p>before asdf. <i>Id.,</i> at 123.</p> <p>foo bar</p>',
             [IdCitation(id_token='Id.,',
                         after_tokens=['at', '123.'],
                         has_page=True)]),
            # Test italicized Id. citation with another HTML tag in the way
            ('<p>before asdf. <i>Id.,</i> at <b>123.</b></p> <p>foo bar</p>',
             [IdCitation(id_token='Id.,',
                         after_tokens=['at', '123.'],
                         has_page=True)]),
            # Test weirder Id. citations (#1344)
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. ¶ 34. foo bar',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='Id.',
                         after_tokens=['¶', '34.'],
                         has_page=True)]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. at 62-63, 67-68. f b',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='Id.',
                         after_tokens=['at', '62-63,', '67-68.'],
                         has_page=True)]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id., at *10. foo bar',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='Id.,',
                         after_tokens=['at', '*10.'],
                         has_page=True)]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. at 7-9, ¶¶ 38-53. f b',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='Id.',
                         after_tokens=['at', '7-9,', '¶¶', '38-53.'],
                         has_page=True)]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. at pp. 45, 64. foo bar',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='Id.',
                         after_tokens=['at', 'pp.', '45,', '64.'],
                         has_page=True)]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. id. 119:12-14. foo bar',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='id.',
                         after_tokens=['119:12-14.'],
                         has_page=True)]),
            # Test Id. citation without page number
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. No page number.',
             [FullCitation(plaintiff='foo', defendant='bar', volume=1,
                           reporter='U.S.', page='12', lookup_index=0,
                           canonical_reporter='U.S.', reporter_index=4,
                           reporter_found='U.S.', court='scotus'),
              IdCitation(id_token='Id.',
                         after_tokens=['No', 'page', 'number.'],
                         has_page=False)]),
            # Test non-opinion citation
            ('lorem ipsum see §99 of the U.S. code.',
             [NonopinionCitation(match_token='§99')]),
            # Test address that's not a citation (#1338)
            ('lorem 111 S.W. 12th St.',
             [],),
            ('lorem 111 N. W. 12th St.',
             [],),
        )
        # fmt: on
        for q, a in test_pairs:
            print("Testing citation extraction for %s..." % q, end=" ")
            cites_found = get_citations(q)
            self.assertEqual(
                cites_found,
                a,
                msg="%s\n%s\n\n    !=\n\n%s"
                % (
                    q,
                    ",\n".join([str(cite.__dict__) for cite in cites_found]),
                    ",\n".join([str(cite.__dict__) for cite in a]),
                ),
            )
            print("✓")

    def test_find_tc_citations(self):
        """Can we parse tax court citations properly?"""
        # fmt: off
        test_pairs = (
            # Test with atypical formatting for Tax Court Memos
            ('the 1 T.C. No. 233',
             [FullCitation(volume=1, reporter='T.C. No.', page='233',
                           canonical_reporter='T.C. No.', lookup_index=0,
                           reporter_index=2, reporter_found='T.C. No.')]),
            ('word T.C. Memo. 2019-233',
             [FullCitation(volume=2019, reporter='T.C. Memo.', page='233',
                           canonical_reporter='T.C. Memo.', lookup_index=0,
                           reporter_index=1, reporter_found='T.C. Memo.')]),
            ('something T.C. Summary Opinion 2019-233',
             [FullCitation(volume=2019, reporter='T.C. Summary Opinion', page='233',
                           canonical_reporter='T.C. Summary Opinion',
                           lookup_index=0,
                           reporter_index=1,
                           reporter_found='T.C. Summary Opinion')]),
            ('T.C. Summary Opinion 2018-133',
             [FullCitation(volume=2018, reporter='T.C. Summary Opinion', page='133',
                           canonical_reporter='T.C. Summary Opinion',
                           lookup_index=0,
                           reporter_index=0,
                           reporter_found='T.C. Summary Opinion')]),
            ('1     UNITED STATES TAX COURT REPORT   (2018)',
             [FullCitation(volume=1, reporter='T.C.', page='2018',
                           canonical_reporter='T.C.',
                           lookup_index=0,
                           reporter_index=1,
                           reporter_found='UNITED STATES TAX COURT REPORT')]),
            ('U.S. of A. 1     UNITED STATES TAX COURT REPORT   (2018)',
             [FullCitation(volume=1, reporter='T.C.', page='2018',
                           canonical_reporter='T.C.',
                           lookup_index=0,
                           reporter_index=4,
                           reporter_found='UNITED STATES TAX COURT REPORT')]),
            # Added this after failing in production
            ('     202                 140 UNITED STATES TAX COURT REPORTS                                   (200)',
             [FullCitation(volume=140, reporter='T.C.', page='200',
                           canonical_reporter='T.C.',
                           lookup_index=0,
                           reporter_index=2,
                           reporter_found='UNITED STATES TAX COURT REPORTS')]),
            ('U.S. 1234 1 U.S. 1',
             [FullCitation(volume=1, reporter='U.S.', page='1',
                           canonical_reporter='U.S.',
                           lookup_index=0,
                           reporter_index=3,
                           court='scotus',
                           reporter_found='U.S.')]),
        )
        # fmt: on
        for q, a in test_pairs:
            print("Testing citation extraction for %s..." % q, end=" ")
            cites_found = get_citations(q)
            self.assertEqual(
                cites_found,
                a,
                msg="%s\n%s\n\n    !=\n\n%s"
                % (
                    q,
                    ",\n".join([str(cite.__dict__) for cite in cites_found]),
                    ",\n".join([str(cite.__dict__) for cite in a]),
                ),
            )
            print("✓")

    def test_date_in_editions(self):
        test_pairs = [
            ("S.E.", 1886, False),
            ("S.E.", 1887, True),
            ("S.E.", 1939, True),
            ("S.E.", 2012, True),
            ("T.C.M.", 1950, True),
            ("T.C.M.", 1940, False),
            ("T.C.M.", datetime.now().year + 1, False),
        ]
        for pair in test_pairs:
            date_in_reporter = is_date_in_reporter(
                REPORTERS[pair[0]][0]["editions"], pair[1]
            )
            self.assertEqual(
                date_in_reporter,
                pair[2],
                msg='is_date_in_reporter(REPORTERS[%s][0]["editions"], %s) != '
                "%s\nIt's equal to: %s"
                % (pair[0], pair[1], pair[2], date_in_reporter),
            )

    def test_disambiguate_citations(self):
        # fmt: off
        test_pairs = [
            # 1. P.R.R --> Correct abbreviation for a reporter.
            ('1 P.R.R. 1',
             [FullCitation(volume=1, reporter='P.R.R.', page='1',
                           canonical_reporter='P.R.R.', lookup_index=0,
                           reporter_index=1, reporter_found='P.R.R.')]),
            # 2. U. S. --> A simple variant to resolve.
            ('1 U. S. 1',
             [FullCitation(volume=1, reporter='U.S.', page='1',
                           canonical_reporter='U.S.', lookup_index=0,
                           court='scotus', reporter_index=1,
                           reporter_found='U. S.')]),
            # 3. A.2d --> Not a variant, but needs to be looked up in the
            #    EDITIONS variable.
            ('1 A.2d 1',
             [FullCitation(volume=1, reporter='A.2d', page='1',
                           canonical_reporter='A.', lookup_index=0,
                           reporter_index=1, reporter_found='A.2d')]),
            # 4. A. 2d --> An unambiguous variant of an edition
            ('1 A. 2d 1',
             [FullCitation(volume=1, reporter='A.2d', page='1',
                           canonical_reporter='A.', lookup_index=0,
                           reporter_index=1, reporter_found='A. 2d')]),
            # 5. P.R. --> A variant of 'Pen. & W.', 'P.R.R.', or 'P.' that's
            #    resolvable by year
            ('1 P.R. 1 (1831)',
             # Of the three, only Pen & W. was being published this year.
             [FullCitation(volume=1, reporter='Pen. & W.', page='1',
                           canonical_reporter='Pen. & W.', lookup_index=0,
                           year=1831, reporter_index=1, reporter_found='P.R.')]),
            # 5.1: W.2d --> A variant of an edition that either resolves to
            #      'Wis. 2d' or 'Wash. 2d' and is resolvable by year.
            ('1 W.2d 1 (1854)',
             # Of the two, only Wis. 2d was being published this year.
             [FullCitation(volume=1, reporter='Wis. 2d', page='1',
                           canonical_reporter='Wis.', lookup_index=0,
                           year=1854, reporter_index=1, reporter_found='W.2d')]),
            # 5.2: Wash. --> A non-variant that has more than one reporter for
            #      the key, but is resolvable by year
            ('1 Wash. 1 (1890)',
             [FullCitation(volume=1, reporter='Wash.', page='1',
                           canonical_reporter='Wash.', lookup_index=1,
                           year=1890, reporter_index=1, reporter_found='Wash.')]),
            # 6. Cr. --> A variant of Cranch, which is ambiguous, except with
            #    paired with this variation.
            ('1 Cra. 1',
             [FullCitation(volume=1, reporter='Cranch', page='1',
                           canonical_reporter='Cranch', lookup_index=0,
                           court='scotus', reporter_index=1,
                           reporter_found='Cra.')]),
            # 7. Cranch. --> Not a variant, but could refer to either Cranch's
            #    Supreme Court cases or his DC ones. In this case, we cannot
            #    disambiguate. Years are not known, and we have no further
            #    clues. We must simply drop Cranch from the results.
            ('1 Cranch 1 1 U.S. 23',
             [FullCitation(volume=1, reporter='U.S.', page='23',
                           canonical_reporter='U.S.', lookup_index=0,
                           court='scotus', reporter_index=4,
                           reporter_found='U.S.')]),
            # 8. Unsolved problem. In theory, we could use parallel citations
            #    to resolve this, because Rob is getting cited next to La., but
            #    we don't currently know the proximity of citations to each
            #    other, so can't use this.
            #  - Rob. --> Either:
            #                8.1: A variant of Robards (1862-1865) or
            #                8.2: Robinson's Louisiana Reports (1841-1846) or
            #                8.3: Robinson's Virgina Reports (1842-1865)
            # ('1 Rob. 1 1 La. 1',
            # [FullCitation(volume=1, reporter='Rob.', page='1',
            #                          canonical_reporter='Rob.',
            #                          lookup_index=0),
            #  FullCitation(volume=1, reporter='La.', page='1',
            #                          canonical_reporter='La.',
            #                          lookup_index=0)]),
            # 9. Johnson #1 should pass and identify the citation
            ('1 Johnson 1 (1890)',
             [FullCitation(volume=1, reporter='N.M. (J.)', page='1',
                           canonical_reporter='N.M. (J.)', lookup_index=0,
                           reporter_index=1, reporter_found='Johnson',
                           year=1890,
                           )]),
            # 10. Johnson #2 should fail to disambiguate with year alone
            ('1 Johnson 1 (1806)', []),
        ]
        # fmt: on
        for pair in test_pairs:
            print("Testing disambiguation for %s..." % pair[0], end=" ")
            citations = get_citations(pair[0], html=False)
            self.assertEqual(
                citations,
                pair[1],
                msg="%s\n%s != \n%s"
                % (
                    pair[0],
                    [cite.__dict__ for cite in citations],
                    [cite.__dict__ for cite in pair[1]],
                ),
            )
            print("✓")
