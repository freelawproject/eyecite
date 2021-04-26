import os
from copy import copy
from datetime import datetime
from unittest import TestCase

from eyecite import clean_text, get_citations

# by default tests use a cache for speed
# call tests with `EYECITE_CACHE_DIR= python ...` to disable cache
from eyecite.test_factories import (
    case_citation,
    id_citation,
    nonopinion_citation,
    supra_citation,
)
from eyecite.tokenizers import (
    EDITIONS_LOOKUP,
    EXTRACTORS,
    AhocorasickTokenizer,
    HyperscanTokenizer,
    Tokenizer,
)

cache_dir = os.environ.get("EYECITE_CACHE_DIR", ".test_cache") or None
tested_tokenizers = [
    Tokenizer(),
    AhocorasickTokenizer(),
    HyperscanTokenizer(cache_dir=cache_dir),
]


class FindTest(TestCase):
    def run_test_pairs(self, test_pairs, message, tokenizers=None):
        if tokenizers is None:
            tokenizers = tested_tokenizers
        for q, expected_cites, *kwargs in test_pairs:
            kwargs = kwargs[0] if kwargs else {}
            expect_fail = kwargs.pop("expect_fail", False)
            clean_steps = kwargs.pop("clean", [])
            clean_q = clean_text(q, clean_steps)
            for tokenizer in tokenizers:
                with self.subTest(
                    message, tokenizer=type(tokenizer).__name__, q=q
                ):
                    cites_found = get_citations(
                        clean_q, tokenizer=tokenizer, **kwargs
                    )
                    match_attrs = [
                        "token_index",
                        "reporter_found",
                        "year",
                        "court",
                        "plaintiff",
                        "defendant",
                        "extra",
                        "canonical_reporter",
                        "volume",
                        "page",
                        "reporter",
                        "antecedent_guess",
                        "pin_cite",
                        "parenthetical",
                    ]
                    try:
                        self.assertEqual(
                            [type(i) for i in cites_found],
                            [type(i) for i in expected_cites],
                            f"Extracted cite count doesn't match for {repr(q)}",
                        )
                        for a, b in zip(cites_found, expected_cites):
                            found_attrs = {
                                attr: getattr(a, attr, None)
                                for attr in match_attrs
                            }
                            expected_attrs = {
                                attr: getattr(b, attr, None)
                                for attr in match_attrs
                            }
                            self.assertEqual(
                                found_attrs,
                                expected_attrs,
                                f"Extracted cite attrs don't match for {repr(q)}",
                            )
                    except AssertionError:
                        if not expect_fail:
                            raise
                        print(f"Test failed as expected: {expect_fail}")
                    else:
                        if expect_fail:
                            self.fail(
                                "Test was expected to fail, but succeeded."
                            )

    def test_find_citations(self):
        """Can we find and make citation objects from strings?"""
        # fmt: off
        test_pairs = (
            # Basic test
            ('1 U.S. 1',
             [case_citation(0)]),
            # Basic test with a line break
            ('1 U.S.\n1',
             [case_citation(0)],
             {'clean': ['all_whitespace']}),
            # Basic test with a line break within a reporter
            ('1 U.\nS. 1',
             [case_citation(0, reporter_found='U. S.')],
             {'clean': ['all_whitespace']}),
            # Basic test of non-case name before citation (should not be found)
            ('lissner test 1 U.S. 1',
             [case_citation(2)]),
            # Test with plaintiff and defendant
            ('lissner v. test 1 U.S. 1',
             [case_citation(3, plaintiff='lissner', defendant='test')]),
            # Test with plaintiff, defendant and year
            ('lissner v. test 1 U.S. 1 (1982)',
             [case_citation(3, plaintiff='lissner', defendant='test',
                            year=1982)]),
            # Don't choke on misformatted year
            ('lissner v. test 1 U.S. 1 (198⁴)',
             [case_citation(3, plaintiff='lissner', defendant='test')]),
            # Test with different reporter than all of above.
            ('bob lissner v. test 1 F.2d 1 (1982)',
             [case_citation(4, reporter='F.2d', canonical_reporter='F.',
                            plaintiff='lissner', defendant='test',
                            year=1982)]),
            # Test with court and extra information
            ('bob lissner v. test 1 U.S. 12, 347-348 (4th Cir. 1982)',
             [case_citation(4, page='12', court='ca4',
                            plaintiff='lissner', defendant='test', year=1982,
                            pin_cite='347-348')]),
            # Parallel cite with parenthetical
            ('bob lissner v. test 1 U.S. 12, 347-348, 1 S. Ct. 2, 358 (4th Cir. 1982) (overruling foo)',
             [case_citation(4, page='12', court='ca4',
                            plaintiff='lissner', defendant='test', year=1982,
                            pin_cite='347-348', extra="1 S. Ct. 2, 358",
                            parenthetical='overruling foo'),
              case_citation(4, page='2', court='ca4', reporter='S. Ct.',
                            plaintiff='lissner', defendant='test 1 U.S. 12, 347-348,',
                            year=1982, pin_cite='358',
                            parenthetical='overruling foo'),
              ]),
            # Test with text before and after and a variant reporter
            ('asfd 22 U. S. 332 (1975) asdf',
             [case_citation(1, page='332', volume='22',
                            reporter_found='U. S.', year=1975)]),
            # Test with finding reporter when it's a second edition
            ('asdf 22 A.2d 332 asdf',
             [case_citation(1, page='332', reporter='A.2d',
                            canonical_reporter='A.', volume='22')]),
            # Test if reporter in string will find proper citation string
            ('A.2d 332 11 A.2d 333',
             [case_citation(2, page='333', reporter='A.2d',
                            canonical_reporter='A.', volume='11')]),
            # Test finding a variant second edition reporter
            ('asdf 22 A. 2d 332 asdf',
             [case_citation(1, page='332', reporter='A.2d',
                            canonical_reporter='A.', volume='22',
                            reporter_found='A. 2d')]),
            # Test finding a variant of an edition resolvable by variant alone.
            ('171 Wn.2d 1016',
             [case_citation(0, page='1016', reporter='Wash. 2d',
                            canonical_reporter='Wash.', volume='171',
                            reporter_found='Wn.2d')]),
            # Test finding two citations where one of them has abutting
            # punctuation.
            ('2 U.S. 3, 4-5 (3 Atl. 33)',
             [case_citation(0, page='3', volume='2', pin_cite='4-5'),
              case_citation(3, page='33', reporter="A.", volume='3',
                            reporter_found="Atl.")]),
            # Test with the page number as a Roman numeral
            ('12 Neb. App. lxiv (2004)',
             [case_citation(0, page='lxiv', reporter='Neb. Ct. App.',
                            canonical_reporter='Neb. Ct. App.', volume='12',
                            reporter_found='Neb. App.', year=2004)]),
            # Test with page range with a weird suffix
            ('559 N.W.2d 826|N.D.',
             [case_citation(0, page='826', reporter='N.W.2d',
                            canonical_reporter='N.W.', volume='559')]),
            # Test with malformed/missing page number
            ('1 U.S. f24601', []),
            # Test with the 'digit-REPORTER-digit' corner-case formatting
            ('2007-NMCERT-008',
             [case_citation(0, source_text='2007-NMCERT-008', page='008',
                            reporter='NMCERT', volume='2007')]),
            ('2006-Ohio-2095',
             [case_citation(0, source_text='2006-Ohio-2095', page='2095',
                            reporter='Ohio', volume='2006')]),
            ('2017 IL App (4th) 160407',
             [case_citation(0, page='160407', reporter='IL App (4th)',
                            volume='2017')]),
            ('2017 IL App (1st) 143684-B',
             [case_citation(0, page='143684-B', reporter='IL App (1st)',
                            volume='2017')]),
            # Test first kind of short form citation (meaningless antecedent)
            ('before asdf 1 U. S., at 2',
             [case_citation(2, page='2', reporter_found='U. S.',
                            short=True, antecedent_guess='asdf')]),
            # Test second kind of short form citation (meaningful antecedent)
            ('before asdf, 1 U. S., at 2',
             [case_citation(2, page='2', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            antecedent_guess='asdf')]),
            # Test short form citation with preceding ASCII quotation
            ('before asdf,” 1 U. S., at 2',
             [case_citation(2, page='2', reporter_found='U. S.',
                            short=True)]),
            # Test short form citation when case name looks like a reporter
            ('before Johnson, 1 U. S., at 2',
             [case_citation(2, page='2', reporter_found='U. S.',
                            short=True, antecedent_guess='Johnson')]),
            # Test short form citation with no comma after reporter
            ('before asdf, 1 U. S. at 2',
             [case_citation(2, page='2', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            antecedent_guess='asdf')]),
            # Test short form citation at end of document (issue #1171)
            ('before asdf, 1 U. S. end', []),
            # Test supra citation across line break
            ('before asdf, supra,\nat 2',
             [supra_citation(2, "supra,", antecedent_guess='asdf',
                             pin_cite='at 2')],
             {'clean': ['all_whitespace']}),
            # Test short form citation with a page range
            ('before asdf, 1 U. S., at 20-25',
             [case_citation(2, page='20', reporter_found='U. S.',
                            short=True, antecedent_guess='asdf',
                            pin_cite='20-25')]),
            # Test short form citation with a page range with weird suffix
            ('before asdf, 1 U. S., at 20-25\\& n. 4',
             [case_citation(2, page='20', reporter_found='U. S.',
                            short=True, antecedent_guess='asdf',
                            pin_cite='20-25')]),
            # Test first kind of supra citation (standard kind)
            ('before asdf, supra, at 2',
             [supra_citation(2, "supra,", antecedent_guess='asdf',
                             pin_cite='at 2')]),
            # Test second kind of supra citation (with volume)
            ('before asdf, 123 supra, at 2',
             [supra_citation(3, "supra,", antecedent_guess='asdf',
                             pin_cite='at 2', volume='123')]),
            # Test third kind of supra citation (sans page)
            ('before asdf, supra, foo bar',
             [supra_citation(2, "supra,", antecedent_guess='asdf')]),
            # Test third kind of supra citation (with period)
            ('before asdf, supra. foo bar',
             [supra_citation(2, "supra,", antecedent_guess='asdf')]),
            # Test supra citation at end of document (issue #1171)
            ('before asdf, supra end',
             [supra_citation(2, "supra,", antecedent_guess='asdf')]),
            # Test Ibid. citation
            ('foo v. bar 1 U.S. 12. asdf. Ibid. foo bar lorem ipsum.',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar'),
              id_citation(7, 'Ibid.')]),
            # Test italicized Ibid. citation
            ('<p>before asdf. <i>Ibid.</i></p> <p>foo bar lorem</p>',
             [id_citation(2, 'Ibid.')],
             {'clean': ['html', 'inline_whitespace']}),
            # Test Id. citation
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id., at 123. foo bar',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'Id.,', pin_cite='at 123')]),
            # Test Id. citation across line break
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id.,\nat 123. foo bar',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'Id.,', pin_cite='at 123')],
             {'clean': ['all_whitespace']}),
            # Test italicized Id. citation
            ('<p>before asdf. <i>Id.,</i> at 123.</p> <p>foo bar</p>',
             [id_citation(2, 'Id.,', pin_cite='at 123')],
             {'clean': ['html', 'inline_whitespace']}),
            # Test italicized Id. citation with another HTML tag in the way
            ('<p>before asdf. <i>Id.,</i> at <b>123.</b></p> <p>foo bar</p>',
             [id_citation(2, 'Id.,', pin_cite='at 123')],
             {'clean': ['html', 'inline_whitespace']}),
            # Test weirder Id. citations (#1344)
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. ¶ 34. foo bar',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'Id.', pin_cite='¶ 34')]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. at 62-63, 67-68. f b',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'Id.', pin_cite='at 62-63, 67-68')]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id., at *10. foo bar',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'Id.,', pin_cite='at *10')]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. at 7-9, ¶¶ 38-53. f b',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'Id.', pin_cite='at 7-9, ¶¶ 38-53')]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. at pp. 45, 64. foo bar',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'Id.', pin_cite='at pp. 45, 64')]),
            ('foo v. bar 1 U.S. 12, 347-348. asdf. id. 119:12-14. foo bar',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'id.', pin_cite='119:12-14')]),
            # Test Id. citation without page number
            ('foo v. bar 1 U.S. 12, 347-348. asdf. Id. No page number.',
             [case_citation(3, page='12', plaintiff='foo',
                            defendant='bar', pin_cite='347-348'),
              id_citation(8, 'Id.')]),
            # Test non-opinion citation
            ('lorem ipsum see §99 of the U.S. code.',
             [nonopinion_citation(3, '§99')]),
            # Test address that's not a citation (#1338)
            ('lorem 111 S.W. 12th St.',
             [],),
            ('lorem 111 N. W. 12th St.',
             [],),
            # Test Conn. Super. Ct. regex variation.
            ('Failed to recognize 1993 Conn. Super. Ct. 5243-P',
             [case_citation(3, volume='1993', reporter='Conn. Super. Ct.',
                            page='5243-P')]),
            # Test that the tokenizer handles commas after a reporter. In the
            # past, " U. S. " would match but not " U. S., "
            ('foo 1 U.S., 1 bar',
             [case_citation(0)]),
            # Test reporter with custom regex
            ('blah blah Bankr. L. Rep. (CCH) P12,345. blah blah',
             [case_citation(2, volume='', reporter='Bankr. L. Rep.',
                            reporter_found='Bankr. L. Rep. (CCH)', page='12,345')]),
            ('blah blah, 2009 12345 (La.App. 1 Cir. 05/10/10). blah blah',
             [case_citation(2, volume='2009', reporter='La.App. 1 Cir.',
                            page='12345')]),
            # Token scanning edge case -- incomplete paren at end of input
            ('1 U.S. 1 (', [case_citation(0)]),
            # Token scanning edge case -- missing plaintiff name at start of input
            ('v. Bar, 1 U.S. 1', [case_citation(0, defendant='Bar,')]),
            # Token scanning edge case -- short form start of input
            ('1 U.S., at 1', [case_citation(0, short=True)]),
            (', 1 U.S., at 1', [case_citation(0, short=True)]),
            # Token scanning edge case -- supra at start of input
            ('supra.', [supra_citation(0, "supra.")]),
            (', supra.', [supra_citation(0, "supra.")]),
            ('123 supra.', [supra_citation(0, "supra.", volume="123")]),
            # Token scanning edge case -- Id. at end of input
            ('Id.', [id_citation(0, 'Id.,')]),
            ('Id. at 1.', [id_citation(0, 'Id.,', pin_cite='at 1')]),
            ('Id. foo', [id_citation(0, 'Id.,')]),
            # Reject citations that are part of larger words
            ('foo1 U.S. 1, 1. U.S. 1foo', [],),
        )
        # fmt: on
        self.run_test_pairs(test_pairs, "Citation extraction")

    def test_find_tc_citations(self):
        """Can we parse tax court citations properly?"""
        # fmt: off
        test_pairs = (
            # Test with atypical formatting for Tax Court Memos
            ('the 1 T.C. No. 233',
             [case_citation(1, page='233', reporter='T.C. No.')]),
            ('word T.C. Memo. 2019-233',
             [case_citation(1, 'T.C. Memo. 2019-233',
                            page='233', reporter='T.C. Memo.',
                            volume='2019')]),
            ('something T.C. Summary Opinion 2019-233',
             [case_citation(1, 'T.C. Summary Opinion 2019-233',
                            page='233', reporter='T.C. Summary Opinion',
                            volume='2019')]),
            ('T.C. Summary Opinion 2018-133',
             [case_citation(0, 'T.C. Summary Opinion 2018-133',
                            page='133', reporter='T.C. Summary Opinion',
                            volume='2018')]),
            ('1     UNITED STATES TAX COURT REPORT   (2018)',
             [case_citation(0, '1 UNITED STATES TAX COURT REPORT (2018)',
                            volume='1', reporter='T.C.', page='2018',
                            reporter_found='UNITED STATES TAX COURT REPORT')],
             {'expect_fail': 'reporters.json needs UNITED STATES TAX COURT REPORT pattern with parens'}),
            ('U.S. of A. 1     UNITED STATES TAX COURT REPORT   (2018)',
             [case_citation(3, '1 UNITED STATES TAX COURT REPORT (2018)',
                            volume='1', reporter='T.C.', page='2018',
                            reporter_found='UNITED STATES TAX COURT REPORT')],
             {'expect_fail': 'reporters.json needs UNITED STATES TAX COURT REPORT pattern with parens'}),
            # Added this after failing in production
            ('     202                 140 UNITED STATES TAX COURT REPORTS                                   (200)',
             [case_citation(1, '140 UNITED STATES TAX COURT REPORTS (200)',
                            volume='140', reporter='T.C.', page='200',
                            reporter_found='UNITED STATES TAX COURT REPORTS')],
             {'expect_fail': 'reporters.json needs UNITED STATES TAX COURT REPORT pattern with parens'}),
            ('U.S. 1234 1 U.S. 1',
             [case_citation(2, volume='1', reporter='U.S.', page='1')]),
        )
        # fmt: on
        self.run_test_pairs(test_pairs, "Tax court citation extraction")

    def test_date_in_editions(self):
        test_pairs = [
            (EDITIONS_LOOKUP["S.E."], 1886, False),
            (EDITIONS_LOOKUP["S.E."], 1887, True),
            (EDITIONS_LOOKUP["S.E."], 1940, False),
            (EDITIONS_LOOKUP["S.E.2d"], 1940, True),
            (EDITIONS_LOOKUP["S.E.2d"], 2012, True),
            (EDITIONS_LOOKUP["T.C.M."], 1950, True),
            (EDITIONS_LOOKUP["T.C.M."], 1940, False),
            (EDITIONS_LOOKUP["T.C.M."], datetime.now().year + 1, False),
        ]
        for edition, year, expected in test_pairs:
            date_in_reporter = edition[0].includes_year(year)
            self.assertEqual(
                date_in_reporter,
                expected,
                msg="is_date_in_reporter(%s, %s) != "
                "%s\nIt's equal to: %s"
                % (edition[0], year, expected, date_in_reporter),
            )

    def test_disambiguate_citations(self):
        # fmt: off
        test_pairs = [
            # 1. P.R.R --> Correct abbreviation for a reporter.
            ('1 P.R.R. 1',
             [case_citation(0, reporter='P.R.R.')]),
            # 2. U. S. --> A simple variant to resolve.
            ('1 U. S. 1',
             [case_citation(0, reporter_found='U. S.')]),
            # 3. A.2d --> Not a variant, but needs to be looked up in the
            #    EDITIONS variable.
            ('1 A.2d 1',
             [case_citation(0, reporter='A.2d',
                            canonical_reporter='A.')]),
            # 4. A. 2d --> An unambiguous variant of an edition
            ('1 A. 2d 1',
             [case_citation(0, reporter='A.2d',
                            canonical_reporter='A.', reporter_found='A. 2d')]),
            # 5. P.R. --> A variant of 'Pen. & W.', 'P.R.R.', or 'P.' that's
            #    resolvable by year
            ('1 P.R. 1 (1831)',
             # Of the three, only Pen & W. was being published this year.
             [case_citation(0, reporter='Pen. & W.',
                            year=1831, reporter_found='P.R.')]),
            # 5.1: W.2d --> A variant of an edition that either resolves to
            #      'Wis. 2d' or 'Wash. 2d' and is resolvable by year.
            ('1 W.2d 1 (1854)',
             # Of the two, only Wis. 2d was being published this year.
             [case_citation(0, reporter='Wis. 2d', canonical_reporter='Wis.',
                            year=1854, reporter_found='W.2d')]),
            # 5.2: Wash. --> A non-variant that has more than one reporter for
            #      the key, but is resolvable by year
            ('1 Wash. 1 (1890)',
             [case_citation(0, reporter='Wash.', year=1890)]),
            # 6. Cr. --> A variant of Cranch, which is ambiguous, except with
            #    paired with this variation.
            ('1 Cra. 1',
             [case_citation(0, reporter='Cranch', reporter_found='Cra.',
                            court='scotus')]),
            # 7. Cranch. --> Not a variant, but could refer to either Cranch's
            #    Supreme Court cases or his DC ones. In this case, we cannot
            #    disambiguate. Years are not known, and we have no further
            #    clues. We must simply drop Cranch from the results.
            ('1 Cranch 1 1 U.S. 23',
             [case_citation(1, page='23')]),
            # 8. Unsolved problem. In theory, we could use parallel citations
            #    to resolve this, because Rob is getting cited next to La., but
            #    we don't currently know the proximity of citations to each
            #    other, so can't use this.
            #  - Rob. --> Either:
            #                8.1: A variant of Robards (1862-1865) or
            #                8.2: Robinson's Louisiana Reports (1841-1846) or
            #                8.3: Robinson's Virgina Reports (1842-1865)
            # ('1 Rob. 1 1 La. 1',
            # [case_citation(volume='1', reporter='Rob.', page='1',
            #                          canonical_reporter='Rob.',),
            #  case_citation(volume='1', reporter='La.', page='1',
            #                          canonical_reporter='La.',)]),
            # 9. Johnson #1 should pass and identify the citation
            ('1 Johnson 1 (1890)',
             [case_citation(0, reporter='N.M. (J.)', reporter_found='Johnson',
                            year=1890,
                            )]),
            # 10. Johnson #2 should fail to disambiguate with year alone
            ('1 Johnson 1 (1806)', []),
        ]
        # fmt: on
        # all tests in this suite require disambiguation:
        test_pairs = [
            pair + ({"remove_ambiguous": True},) for pair in test_pairs
        ]
        self.run_test_pairs(test_pairs, "Disambiguation")

    def test_custom_tokenizer(self):
        extractors = []
        for e in EXTRACTORS:
            e = copy(e)
            e.regex = e.regex.replace(r"\.", r"[.,]")
            if hasattr(e, "_compiled_regex"):
                del e._compiled_regex
            extractors.append(e)
        tokenizer = Tokenizer(extractors)

        # fmt: off
        test_pairs = [
            ('1 U,S, 1',
             [case_citation(0, reporter_found='U,S,')]),
        ]
        # fmt: on
        self.run_test_pairs(
            test_pairs, "Custom tokenizer", tokenizers=[tokenizer]
        )
