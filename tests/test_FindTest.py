import os
from copy import copy
from datetime import datetime
from unittest import TestCase

from eyecite import get_citations
from eyecite.find import extract_reference_citations
from eyecite.helpers import filter_citations

# by default tests use a cache for speed
# call tests with `EYECITE_CACHE_DIR= python ...` to disable cache
from eyecite.models import (
    Document,
    FullCaseCitation,
    ReferenceCitation,
    ResourceCitation,
)
from eyecite.test_factories import (
    case_citation,
    id_citation,
    journal_citation,
    law_citation,
    reference_citation,
    supra_citation,
    unknown_citation,
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
    maxDiff = None

    def run_test_pairs(self, test_pairs, message, tokenizers=None):
        def get_comparison_attrs(cite):
            # Remove pin_cite start and end from metadata for this test
            cite.metadata.pin_cite_span_start = None
            cite.metadata.pin_cite_span_end = None
            out = {
                "groups": cite.groups,
                "metadata": cite.metadata,
            }
            if isinstance(cite, ResourceCitation):
                out["year"] = cite.year
                out["corrected_reporter"] = cite.corrected_reporter()
            return out

        if tokenizers is None:
            tokenizers = tested_tokenizers
        for q, expected_cites, *kwargs in test_pairs:
            kwargs = kwargs[0] if kwargs else {}
            clean_steps = kwargs.get("clean_steps", [])
            for tokenizer in tokenizers:
                with self.subTest(
                    message, tokenizer=type(tokenizer).__name__, q=q
                ):
                    if "html" in clean_steps:
                        kwargs["markup_text"] = q
                    else:
                        kwargs["plain_text"] = q

                    cites_found = get_citations(tokenizer=tokenizer, **kwargs)
                    self.assertEqual(
                        [type(i) for i in cites_found],
                        [type(i) for i in expected_cites],
                        f"Extracted cite count doesn't match for {repr(q)}",
                    )
                    for a, b in zip(cites_found, expected_cites):
                        found_attrs = get_comparison_attrs(a)
                        expected_attrs = get_comparison_attrs(b)
                        self.assertEqual(
                            found_attrs,
                            expected_attrs,
                            f"Extracted cite attrs don't match for {repr(q)}",
                        )

    def test_find_citations(self):
        """Can we find and make citation objects from strings?"""
        # fmt: off
        test_pairs = (
            # Basic test
            ('1 U.S. 1',
             [case_citation()]),
            # Basic test with a line break
            ('1 U.S.\n1',
             [case_citation()],
             {'clean_steps': ['all_whitespace']}),
            # Basic test with a line break within a reporter
            ('1 U.\nS. 1',
             [case_citation(reporter_found='U. S.')],
             {'clean_steps': ['all_whitespace']}),
            # Basic test of non-case name before citation (should not be found)
            ('lissner test 1 U.S. 1',
             [case_citation()]),
            # Test with plaintiff and defendant
            ('Lissner v. Test 1 U.S. 1',
             [case_citation(metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test'})]),
            # Test with plaintiff, defendant and year
            ('Lissner v. Test 1 U.S. 1 (1982)',
             [case_citation(metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test'},
                            year=1982)]),
            # Don't choke on misformatted year
            ('Lissner v. Test 1 U.S. 1 (198⁴)',
             [case_citation(metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test'})]),
            # Test with different reporter than all of above.
            ('bob Lissner v. Test 1 F.2d 1 (1982)',
             [case_citation(reporter='F.2d', year=1982,
                            metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test'})]),
            # Test with comma after defendant's name
            ('Lissner v. Test, 1 U.S. 1 (1982)',
             [case_citation(metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test'},
                            year=1982)]),
            # can we handle variations with parenthesis
            ('1 So.2d at 1',
             [case_citation(volume="1", reporter="So.2d", page="1", short=True,
              metadata={'pin_cite': '1'})]),
            # Test with court and extra information
            ('bob Lissner v. Test 1 U.S. 12, 347-348 (4th Cir. 1982)',
             [case_citation(page='12', year=1982,
                            metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test',
                                      'court': 'ca4',
                                      'pin_cite': '347-348'})]),
            # Test with court string without space
            ('bob Lissner v. Test 1 U.S. 12, 347-348 (Pa.Super. 1982)',
             [case_citation(page='12', year=1982,
                            metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test',
                                      'court': 'pasuperct',
                                      'pin_cite': '347-348'})]),
            # Test with court string exact match
            ('Commonwealth v. Muniz, 164 A.3d 1189 (Pa. 2017)',
             [case_citation(page='1189', reporter='A.3d', volume='164', year=2017,
                            metadata={'plaintiff': 'Commonwealth',
                                      'defendant': 'Muniz',
                                      'court': 'pa'})]),
            # Parallel cite with parenthetical
            ('Bob Lissner v. Test 1 U.S. 12, 347-348, 1 S. Ct. 2, 358 (4th Cir. 1982) (overruling foo)',
             [case_citation(page='12', year=1982,
                            metadata={'plaintiff': 'Bob Lissner',
                                      'defendant': 'Test',
                                      'court': 'ca4',
                                      'pin_cite': '347-348',
                                      'extra': "1 S. Ct. 2, 358",
                                      'parenthetical': 'overruling foo'}),
              case_citation(page='2', reporter='S. Ct.', year=1982,
                            metadata={'plaintiff': 'Bob Lissner',
                                      'defendant': 'Test',
                                      'court': 'ca4',
                                      'pin_cite': '358',
                                      'parenthetical': 'overruling foo'}),
              ]),
            # Test full citation with nested parenthetical
            ('Lissner v. Test 1 U.S. 1 (1982) (discussing abc (Holmes, J., concurring))',
             [case_citation(metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test',
                                      'parenthetical': 'discussing abc (Holmes, J., concurring)'},
                            year=1982)]),
            # Test full citation with parenthetical and subsequent unrelated parenthetical
            ('Lissner v. Test 1 U.S. 1 (1982) (discussing abc); blah (something).',
             [case_citation(metadata={'plaintiff': 'Lissner',
                                      'defendant': 'Test',
                                      'parenthetical': 'discussing abc'},
                            year=1982)]),
            # Test with text before and after and a variant reporter
            ('asfd 22 U. S. 332 (1975) asdf',
             [case_citation(page='332', volume='22',
                            reporter_found='U. S.', year=1975)]),
            # Test with finding reporter when it's a second edition
            ('asdf 22 A.2d 332 asdf',
             [case_citation(page='332', reporter='A.2d', volume='22')]),
            # Test if reporter in string will find proper citation string
            ('A.2d 332 11 A.2d 333',
             [case_citation(page='333', reporter='A.2d', volume='11')]),
            # Test finding a variant second edition reporter
            ('asdf 22 A. 2d 332 asdf',
             [case_citation(page='332', reporter='A.2d', volume='22',
                            reporter_found='A. 2d')]),
            # Test finding a variant of an edition resolvable by variant alone.
            ('171 Wn.2d 1016',
             [case_citation(page='1016', reporter='Wash. 2d', volume='171',
                            reporter_found='Wn.2d')]),
            # Test finding two citations where one of them has abutting
            # punctuation.
            ('2 U.S. 3, 4-5 (3 Atl. 33)',
             [case_citation(page='3', volume='2', metadata={'pin_cite': '4-5'}),
              case_citation(page='33', reporter="A.", volume='3',
                            reporter_found="Atl.")]),
            # Test with the page number as a Roman numeral
            ('12 Neb. App. lxiv (2004)',
             [case_citation(page='lxiv', reporter='Neb. Ct. App.',
                            volume='12',
                            reporter_found='Neb. App.', year=2004)]),
            # Test with page range with a weird suffix
            ('559 N.W.2d 826|N.D.',
             [case_citation(page='826', reporter='N.W.2d', volume='559')]),
            # Test with malformed page number
            ('1 U.S. f24601', []),
            # Test with page number that is indicated as missing
            ('1 U.S. ___',
             [case_citation(volume='1', reporter='U.S.', page=None)]),
            # Test with page number that is indicated as missing, followed by
            # a comma (cf. eyecite#137)
            ('1 U. S. ___,',
             [case_citation(volume='1', reporter_found='U. S.', page=None)]),
            # Test with the 'digit-REPORTER-digit' corner-case formatting
            ('2007-NMCERT-008',
             [case_citation(source_text='2007-NMCERT-008', page='008',
                            reporter='NMCERT', volume='2007')]),
            ('2006-Ohio-2095',
             [case_citation(source_text='2006-Ohio-2095', page='2095',
                            reporter='Ohio', volume='2006')]),
            ('2017 IL App (4th) 160407',
             [case_citation(page='160407', reporter='IL App (4th)',
                            volume='2017')]),
            ('2017 IL App (1st) 143684-B',
             [case_citation(page='143684-B', reporter='IL App (1st)',
                            volume='2017')]),
            # Test first kind of short form citation (meaningless antecedent)
            ('before Foo 1 U. S., at 2',
             [case_citation(page='2', reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo'})]),
            # Test second kind of short form citation (meaningful antecedent)
            ('before Foo, 1 U. S., at 2',
             [case_citation(page='2', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo'})]),
            # Test short form citation with preceding ASCII quotation
            ('before Foo,” 1 U. S., at 2',
             [case_citation(page='2', reporter_found='U. S.',
                            short=True)]),
            # Test short form citation when case name looks like a reporter
            ('before Johnson, 1 U. S., at 2',
             [case_citation(page='2', reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Johnson'})]),
            # Test short form citation with no comma after reporter
            ('before Foo, 1 U. S. at 2',
             [case_citation(page='2', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo'})]),
            # Test short form citation at end of document (issue #1171)
            ('before Foo, 1 U. S. end', []),
            # Test supra citation across line break
            ('before Foo, supra,\nat 2',
             [supra_citation("supra,",
                             metadata={'pin_cite': 'at 2',
                                       'antecedent_guess': 'Foo'})],
             {'clean_steps': ['all_whitespace']}),
            # Test short form citation with a page range
            ('before Foo, 1 U. S., at 20-25',
             [case_citation(page='20', reporter_found='U. S.', short=True,
                            metadata={'pin_cite': '20-25',
                                      'antecedent_guess': 'Foo'})]),
            # Test short form citation with a page range with weird suffix
            ('before Foo, 1 U. S., at 20-25\\& n. 4',
             [case_citation(page='20', reporter_found='U. S.', short=True,
                            metadata={'pin_cite': '20-25',
                                      'antecedent_guess': 'Foo'})]),
            # Test short form citation with a parenthetical
            ('before Foo, 1 U. S., at 2 (overruling xyz)',
             [case_citation(page='2', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo',
                                      'parenthetical': 'overruling xyz'}
                            )]),
            # Test short form citation with no space before parenthetical
            ('before Foo, 1 U. S., at 2(overruling xyz)',
             [case_citation(page='2', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo',
                                      'parenthetical': 'overruling xyz'}
                            )]),
            # Test short form citation with nested parentheticals
            ('before Foo, 1 U. S., at 2 (discussing xyz (Holmes, J., concurring))',
             [case_citation(page='2', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo',
                                      'parenthetical': 'discussing xyz (Holmes, J., concurring)'}
                            )]),
            # Test that short form citation doesn't treat year as parenthetical
            ('before Foo, 1 U. S., at 2 (2016)',
             [case_citation(page='2', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo'}
                            )]),
            # Test short form citation with page range and parenthetical
            ('before Foo, 1 U. S., at 20-25 (overruling xyz)',
             [case_citation(page='20', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo',
                                      'pin_cite': '20-25',
                                      'parenthetical': 'overruling xyz'}
                            )]),
            # Test short form citation with subsequent unrelated parenthetical
            ('Foo, 1 U. S., at 4 (discussing abc). Some other nonsense (clarifying nonsense)',
             [case_citation(page='4', reporter='U.S.',
                            reporter_found='U. S.', short=True,
                            metadata={'antecedent_guess': 'Foo',
                                      'parenthetical': 'discussing abc'}
                            )]
             ),
            # Test short form citation generated from non-standard regex for full cite
            ('1 Mich. at 1',
             [case_citation(reporter='Mich.', short=True)]),
            # Test parenthetical matching with multiple citations
            ('1 U. S., at 2. Foo v. Bar 3 U. S. 4 (2010) (overruling xyz).',
             [case_citation(page='2', reporter='U.S.',
                            reporter_found='U. S.',
                            short=True, volume='1',
                            metadata={'pin_cite': '2'}),
              case_citation(page='4', reporter='U.S.',
                            reporter_found='U. S.', short=False,
                            year=2010, volume='3',
                            metadata={'parenthetical': 'overruling xyz',
                                      'plaintiff': 'Foo', 'defendant': 'Bar'})
              ]),
            # Test with multiple citations and parentheticals
            ('1 U. S., at 2 (criticizing xyz). Foo v. Bar 3 U. S. 4 (2010) (overruling xyz).',
             [case_citation(page='2', reporter='U.S.',
                            reporter_found='U. S.',
                            short=True, volume='1',
                            metadata={'pin_cite': '2',
                                      'parenthetical': 'criticizing xyz'}),
              case_citation(page='4', reporter='U.S.',
                            reporter_found='U. S.', short=False,
                            year=2010, volume='3',
                            metadata={'parenthetical': 'overruling xyz',
                                      'plaintiff': 'Foo', 'defendant': 'Bar'})
              ]),
            # Test first kind of supra citation (standard kind)
            ('before asdf, supra, at 2',
             [supra_citation("supra,",
                             metadata={'pin_cite': 'at 2',
                                       'antecedent_guess': 'asdf'})]),
            # Test second kind of supra citation (with volume)
            ('before asdf, 123 supra, at 2',
             [supra_citation("supra,",
                             metadata={'pin_cite': 'at 2',
                                       'volume': '123',
                                       'antecedent_guess': 'asdf'})]),
            # Test third kind of supra citation (sans page)
            ('before Asdf, supra, foo bar',
             [supra_citation("supra,",
                             metadata={'antecedent_guess': 'Asdf'})]),
            # Test third kind of supra citation (with period)
            ('before Asdf, supra. foo bar',
             [supra_citation("supra,",
                             metadata={'antecedent_guess': 'Asdf'})]),
            # Test supra citation at end of document (issue #1171)
            ('before asdf, supra end',
             [supra_citation("supra,",
                             metadata={'antecedent_guess': 'asdf'})]),
            # Supra with parenthetical
            ('Foo, supra (overruling ...) (ignore this)',
             [supra_citation("supra",
                             metadata={'antecedent_guess': 'Foo',
                                       'parenthetical': 'overruling ...'})]),
            ('Foo, supra, at 2 (overruling ...)',
             [supra_citation("supra",
                             metadata={'antecedent_guess': 'Foo',
                                       'pin_cite': 'at 2',
                                       'parenthetical': 'overruling ...'})]),
            # Test Ibid. citation
            ('Foo v. Bar 1 U.S. 12. asdf. Ibid. foo bar lorem ipsum.',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar'}),
              id_citation('Ibid.')]),
            # Test italicized Ibid. citation
            ('<p>before asdf. <i>Ibid.</i></p> <p>foo bar lorem</p>',
             [id_citation('Ibid.')],
             {'clean_steps': ['html', 'inline_whitespace']}),
            # Test Id. citation
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. Id., at 123. foo bar',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('Id.,',
                          metadata={'pin_cite': 'at 123'})]),
            # Test Id. citation across line break
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. Id.,\nat 123. foo bar',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('Id.,', metadata={'pin_cite': 'at 123'})],
             {'clean_steps': ['all_whitespace']}),
            # Test italicized Id. citation
            ('<p>before asdf. <i>Id.,</i> at 123.</p> <p>foo bar</p>',
             [id_citation('Id.,', metadata={'pin_cite': 'at 123'})],
             {'clean_steps': ['html', 'inline_whitespace']}),
            # Test italicized Id. citation with another HTML tag in the way
            ('<p>before asdf. <i>Id.,</i> at <b>123.</b></p> <p>foo bar</p>',
             [id_citation('Id.,', metadata={'pin_cite': 'at 123'})],
             {'clean_steps': ['html', 'inline_whitespace']}),
            # Test weirder Id. citations (#1344)
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. Id. ¶ 34. foo bar',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('Id.', metadata={'pin_cite': '¶ 34'})]),
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. Id. at 62-63, 67-68. f b',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('Id.', metadata={'pin_cite': 'at 62-63, 67-68'})]),
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. Id., at *10. foo bar',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('Id.,', metadata={'pin_cite': 'at *10'})]),
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. Id. at 7-9, ¶¶ 38-53. f b',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('Id.', metadata={'pin_cite': 'at 7-9, ¶¶ 38-53'})]),
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. Id. at pp. 45, 64. foo bar',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('Id.', metadata={'pin_cite': 'at pp. 45, 64'})]),
            # Cleanup parentheses and square brackets
            (' (Newbold v Arvidson, 105 Idaho 663, 672 P2d 231 [1983]); and something else (Newbold, 105 Idaho at 667, 672 P2d at 235).',
             [case_citation(volume='105', reporter='Idaho', page='663',
                            metadata={'plaintiff': 'Newbold',
                                      'defendant': 'Arvidson',
                                      'extra': '672 P2d 231',
                                      'year': '1983'}),
              case_citation(volume='672', reporter='P2d', page='231',
                            metadata={'plaintiff': 'Newbold',
                                      'defendant': 'Arvidson',
                                      'year': '1983'}),
              case_citation(volume='105', reporter='Idaho', page='667',
                            short=True,
                            metadata={'antecedent_guess': 'Newbold', 'pin_cite': '667'}),
              case_citation(volume='672', reporter='P2d', page='235',
                            short=True,
                            metadata={'antecedent_guess': "Newbold",  'pin_cite': '235'})
              ]),
            # Square brackets around year
            ('Rogers v Rogers 63 NY2d 582 [1984]',
             [case_citation(volume='63', reporter='NY2d', page='582',
                            metadata={'plaintiff': 'Rogers',
                                      'defendant': 'Rogers',
                                      'year': '1984'})]
             ),
            #
            ('(Mo.); Bean v. State, — Nev. —, 398 P. 2d 251; ',
             [case_citation(volume='398', reporter='P. 2d', page='251',
                            metadata={'plaintiff': 'Bean',
                                      'defendant': 'State, — Nev. —'})]
             ),
            # Spano v. People of State of New York, 360 U.S. 315, 321, n. 2, 79 S.Ct. 1202, 1206, 3 L.Ed.2d 1265, collects 28 cases.
            ('curiams. Spano v. People of State of New York, 360 U.S. 315',
             [case_citation(volume='360', reporter='U.S.', page='315',
                            metadata={'plaintiff': 'Spano',
                                      'defendant': 'People of State of New York'})]
             ),
            # Spano v. People of State of New York, 360 U.S. 315, 321, n. 2, 79 S.Ct. 1202, 1206, 3 L.Ed.2d 1265, collects 28 cases.
            ('curiams. Spano v. People of State of New York, 360 U.S. 315',
             [case_citation(volume='360', reporter='U.S.', page='315',
                            metadata={'plaintiff': 'Spano',
                                      'defendant': 'People of State of New York'})]
             ),

            # Capitlized to end before quote
            ('Per Curiams. Spano v. People of State of New York, 360 U.S. 315',
             [case_citation(volume='360', reporter='U.S.', page='315',
                            metadata={'plaintiff': 'Spano',
                                      'defendant': 'People of State of New York'})]
             ),

            # Square brackets around year and court
            ('Mavrovich v Vanderpool, 427 F Supp 2d 1084 [D Kan 2006]',
             [case_citation(volume='427', reporter='F Supp 2d', page='1084',
                            metadata={'plaintiff': 'Mavrovich',
                                      'defendant': 'Vanderpool',
                                      'court': 'ksd',
                                      'year': '2006'})]),
            # Parentheses not square brackets
            ('Mavrovich v Vanderpool, 427 F Supp 2d 1084 (D Kan 2006)',
             [case_citation(volume='427', reporter='F Supp 2d', page='1084',
                            metadata={'plaintiff': 'Mavrovich',
                                      'defendant': 'Vanderpool',
                                      'court': 'ksd',
                                      'year': '2006'})]),
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. id. 119:12-14. foo bar',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('id.', metadata={'pin_cite': '119:12-14'})]),
            # Test Id. citation without page number
            ('Foo v. Bar 1 U.S. 12, 347-348. asdf. Id. No page number.',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              id_citation('Id.')]),
            # Id. with parenthetical
            ('Id. (overruling ...) (ignore this)',
             [id_citation("Id.", metadata={'parenthetical': 'overruling ...'})]),
            ('Id. at 2 (overruling ...)',
             [id_citation("Id.",
                          metadata={'pin_cite': 'at 2',
                                    'parenthetical': 'overruling ...'})]),
            # Test unknown citation
            ('lorem ipsum see §99 of the U.S. code.',
             [unknown_citation('§99')]),
            # Test address that's not a citation (#1338)
            ('lorem 111 S.W. 12th St.',
             [],),
            ('lorem 111 N. W. 12th St.',
             [],),
            # Test filtering overlapping citations - this finds four citations
            # but should filter down to three
            ("Miles v. Smith 1 Ga. 1; asdfasdf asd Something v. Else, 1 Miles 3; 1 Miles at 10",
             [case_citation(page='1',
                            volume="1",
                            reporter="Ga.",
                            metadata={'plaintiff': 'Miles',
                                      'defendant': 'Smith'}),
              case_citation(page='3',
                            volume="1",
                            reporter="Miles",
                            metadata={'plaintiff': 'Something',
                                      'defendant': 'Else'}
                            ),
              case_citation(volume="1", page='10', reporter='Miles',
                            short=True,
                            metadata={'pin_cite': '10'})]),
            ('General Casualty cites as compelling Amick v. Liberty Mut. Ins. Co., 455 A.2d 793 (R.I. 1983). In that case ... Stats, do. See Amick at 795',
             [case_citation(page='793',
                            volume="455",
                            reporter="A.2d",
                            year=1983,
                            metadata={'plaintiff': 'Amick',
                                      'defendant': 'Liberty Mut. Ins. Co.',
                                      'court': 'ri'
                                      }),
              reference_citation('Amick at 795', metadata={'plaintiff': 'Amick', 'pin_cite': '795'})]),
            # Test reference citation
            ('Foo v. Bar 1 U.S. 12, 347-348. something something, In Foo at 62 we see that',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              reference_citation('Foo at 62', metadata={'plaintiff': 'Foo', 'pin_cite': '62'})]),
            ('Foo v. United States 1 U.S. 12, 347-348. something something ... the United States at 1776 we see that and Foo at 62',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'United States',
                                      'pin_cite': '347-348'}),
              reference_citation('Foo at 62', metadata={'plaintiff': 'Foo', 'pin_cite': '62'})]),
            # Test that reference citation must occur after full case citation
            ('In Foo at 62 we see that, Foo v. Bar 1 U.S. 12, 347-348. something something,',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'})]),
            # Test reference against defendant name
            ('In re Foo 1 Mass. 12, 347-348. something something, in Foo at 62 we see that, ',
             [case_citation(page='12', reporter="Mass.", volume="1",
                            metadata={'defendant': 'Foo', 'pin_cite': '347-348'}),
              reference_citation('Foo at 62',
                                 metadata={'defendant': 'Foo',
                                           "pin_cite": "62"})]),
            # Test reference citation that contains at
            ('In re Foo 1 Mass. 12, 347-348. something something, in at we see that',
             [case_citation(page='12', reporter="Mass.", volume="1",
                            metadata={'defendant': 'Foo', 'pin_cite': '347-348'})]),
            # Test U.S. as plaintiff with reference citations
            ('U.S. v. Boch Oldsmobile, Inc., 909 F.2d 657, 660 (1st Cir.1990); Piper Aircraft, 454 U.S. at 241',
             [case_citation(page='657', reporter="F.2d", volume="909",
                            metadata={'plaintiff': 'U.S.', 'defendant': 'Boch Oldsmobile, Inc.', 'pin_cite': '660'}),
              case_citation(volume="454", page='241', reporter_found='U.S.', short=True,
                            metadata={'antecedent_guess': 'Piper Aircraft', 'court': "scotus", 'pin_cite': "241"})]),
            # Test reference citation after an id citation
            ('we said in Morton v. Mancari, 417 U. S. 535, 552 (1974) “Literally every piece ....”. “asisovereign tribal entities . . . .” Id. In Mancari at 665',
             [case_citation(page='535', year=1974, volume="417",
                            reporter="U. S.",
                            metadata={'plaintiff': 'Morton', 'defendant': 'Mancari', "pin_cite": "552", "court": "scotus"}),
              id_citation('Id.,', metadata={}),
              reference_citation('Mancari',
                                 metadata={'defendant': 'Mancari', "pin_cite": "665"})]),
            # Test Conn. Super. Ct. regex variation.
            ('Failed to recognize 1993 Conn. Super. Ct. 5243-P',
             [case_citation(volume='1993', reporter='Conn. Super. Ct.',
                            page='5243-P')]),
            # Test that the tokenizer handles commas after a reporter. In the
            # past, " U. S. " would match but not " U. S., "
            ('foo 1 U.S., 1 bar',
             [case_citation()]),
            # Test reporter with custom regex
            ('blah blah Bankr. L. Rep. (CCH) P12,345. blah blah',
             [case_citation(volume=None, reporter='Bankr. L. Rep.',
                            reporter_found='Bankr. L. Rep. (CCH)', page='12,345')]),
            ('blah blah, 2009 12345 (La.App. 1 Cir. 05/10/10). blah blah',
             [case_citation(volume='2009', reporter='La.App. 1 Cir.',
                            page='12345', groups={'date_filed': '05/10/10'})]),
            # Token scanning edge case -- incomplete paren at end of input
            ('1 U.S. 1 (', [case_citation()]),
            # Token scanning edge case -- missing plaintiff name at start of input
            ('v. Bar, 1 U.S. 1', [case_citation(metadata={'antecedent_guess': 'Bar'})]),
            # Token scanning edge case -- short form start of input
            ('1 U.S., at 1', [case_citation(short=True)]),
            (', 1 U.S., at 1', [case_citation(short=True)]),
            # Token scanning edge case -- supra at start of input
            ('supra.', [supra_citation("supra.")]),
            (', supra.', [supra_citation("supra.")]),
            ('123 supra.', [supra_citation("supra.", metadata={'volume': "123"})]),
            # Token scanning edge case -- Id. at end of input
            ('Id.', [id_citation('Id.,')]),
            ('Id. at 1.', [id_citation('Id.,', metadata={'pin_cite': 'at 1'})]),
            ('Id. foo', [id_citation('Id.,')]),
            # Reject citations that are part of larger words
            ('foo1 U.S. 1, 1. U.S. 1foo', [],),
            # Long pin cite -- make sure no catastrophic backtracking in regex
            ('1 U.S. 1, 2277, 2278, 2279, 2280, 2281, 2282, 2283, 2284, 2286, 2287, 2288, 2289, 2290, 2291',
             [case_citation(metadata={'pin_cite': '2277, 2278, 2279, 2280, 2281, 2282, 2283, 2284, 2286, 2287, 2288, 2289, 2290, 2291'})]),
            ('Commonwealth v. Muniz, 164 A.3d 1189 (Pa. 2017)', [
                case_citation(volume='164', reporter='A.3d', year=2017,
                              page='1189',
                              metadata={'plaintiff': 'Commonwealth', 'defendant': 'Muniz',
                                        'court': 'pa'})]),
            ('Foo v. Bar,  1 F.Supp. 1 (SC 1967)', [case_citation(volume='1', reporter='F.Supp.', year=1967, page='1', metadata={'plaintiff': 'Foo', 'defendant': 'Bar', 'court': 'sc'})]),
            ('trial court’s ruling. (See In re K.F. (2009) 1 U.S. 1 ', [
                case_citation(
                 year=2009, metadata={'defendant': 'K.F.', "year": "2009"})]
             ),
            ('(See In re K.F. (2009) 1 U.S. 1, 4 [92 Cal.Rptr.3d 784]; Yield Dynamics, Inc. v. TEA Systems Corp. (2007) 154 Cal.App.4th 547, 558 [66 Cal.Rptr.3d 1].)”', [
                case_citation(
                    year=2009,
                    metadata={'defendant': 'K.F.', "year": "2009", 'pin_cite': '4'}
                ),
                case_citation(
                    year=2009, volume='92', reporter='Cal.Rptr.3d', page='784',
                    metadata={'defendant': 'K.F.', "year": "2009"}
                ),
                case_citation(
                    year=2007, volume='154', reporter='Cal.App.4th', page='547',
                    metadata={'plaintiff': 'Yield Dynamics, Inc.', 'defendant': 'TEA Systems Corp.', "year": "2007", "pin_cite": "558"}
                ),
                case_citation(
                    year=2007, volume='66', reporter='Cal.Rptr.3d', page='1',
                    metadata={'plaintiff': 'Yield Dynamics, Inc.', 'defendant': 'TEA Systems Corp.', "year": "2007"}
                ),
            ])
        )

        # fmt: on
        self.run_test_pairs(test_pairs, "Citation extraction")

    def test_find_law_citations(self):
        """Can we find citations from laws.json?"""
        # fmt: off
        """
        see Ariz. Rev. Stat. Ann. § 36-3701 et seq. (West 2009)
        63 Stat. 687 (emphasis added)
        18 U. S. C. §§4241-4243
        Fla. Stat. § 120.68 (2007)
        """
        test_pairs = (
            # Basic test
            ('Mass. Gen. Laws ch. 1, § 2',
             [law_citation('Mass. Gen. Laws ch. 1, § 2',
                           reporter='Mass. Gen. Laws',
                           groups={'chapter': '1', 'section': '2'})]),
            ('1 Stat. 2',
             [law_citation('1 Stat. 2',
                           reporter='Stat.',
                           groups={'volume': '1', 'page': '2'})]),
            # year
            ('Fla. Stat. § 120.68 (2007)',
             [law_citation('Fla. Stat. § 120.68 (2007)',
                           reporter='Fla. Stat.', year=2007,
                           groups={'section': '120.68'})]),
            # et seq, publisher, year
            ('Ariz. Rev. Stat. Ann. § 36-3701 et seq. (West 2009)',
             [law_citation('Ariz. Rev. Stat. Ann. § 36-3701 et seq. (West 2009)',
                           reporter='Ariz. Rev. Stat. Ann.',
                           metadata={'pin_cite': 'et seq.', 'publisher': 'West'},
                           groups={'section': '36-3701'},
                           year=2009)]),
            # multiple sections
            ('Mass. Gen. Laws ch. 1, §§ 2-3',
             [law_citation('Mass. Gen. Laws ch. 1, §§ 2-3',
                           reporter='Mass. Gen. Laws',
                           groups={'chapter': '1', 'section': '2-3'})]),
            # parenthetical
            ('Kan. Stat. Ann. § 21-3516(a)(2) (repealed) (ignore this)',
             [law_citation('Kan. Stat. Ann. § 21-3516(a)(2) (repealed)',
                           reporter='Kan. Stat. Ann.',
                           metadata={'pin_cite': '(a)(2)', 'parenthetical': 'repealed'},
                           groups={'section': '21-3516'})]),
            # Supp. publisher
            ('Ohio Rev. Code Ann. § 5739.02(B)(7) (Lexis Supp. 2010)',
             [law_citation('Ohio Rev. Code Ann. § 5739.02(B)(7) (Lexis Supp. 2010)',
                           reporter='Ohio Rev. Code Ann.',
                           metadata={'pin_cite': '(B)(7)', 'publisher': 'Lexis Supp.'},
                           groups={'section': '5739.02'},
                           year=2010)]),
            # Year range
            ('Wis. Stat. § 655.002(2)(c) (2005-06)',
             [law_citation('Wis. Stat. § 655.002(2)(c) (2005-06)',
                           reporter='Wis. Stat.',
                           metadata={'pin_cite': '(2)(c)'},
                           groups={'section': '655.002'},
                           year=2005)]),
            # 'and' pin cite
            ('Ark. Code Ann. § 23-3-119(a)(2) and (d) (1987)',
             [law_citation('Ark. Code Ann. § 23-3-119(a)(2) and (d) (1987)',
                           reporter='Ark. Code Ann.',
                           metadata={'pin_cite': '(a)(2) and (d)'},
                           groups={'section': '23-3-119'},
                           year=1987)]),
            # Cite to multiple sections
            ('Mass. Gen. Laws ch. 1, §§ 2-3',
             [law_citation('Mass. Gen. Laws ch. 1, §§ 2-3',
                           reporter='Mass. Gen. Laws',
                           groups={'chapter': '1', 'section': '2-3'})]),
        )
        # fmt: on
        self.run_test_pairs(test_pairs, "Law citation extraction")

    def test_find_journal_citations(self):
        """Can we find citations from journals.json?"""
        # fmt: off
        test_pairs = (
            # Basic test
            ('1 Minn. L. Rev. 1',
             [journal_citation()]),
            # Pin cite
            ('1 Minn. L. Rev. 1, 2-3',
             [journal_citation(metadata={'pin_cite': '2-3'})]),
            # Year
            ('1 Minn. L. Rev. 1 (2007)',
             [journal_citation(year=2007)]),
            # Pin cite and year
            ('1 Minn. L. Rev. 1, 2-3 (2007)',
             [journal_citation(metadata={'pin_cite': '2-3'}, year=2007)]),
            # Pin cite and year and parenthetical
            ('1 Minn. L. Rev. 1, 2-3 (2007) (discussing ...) (ignore this)',
             [journal_citation(year=2007,
                               metadata={'pin_cite': '2-3', 'parenthetical': 'discussing ...'})]),
            # Year range
            ('77 Marq. L. Rev. 475 (1993-94)',
             [journal_citation(volume='77', reporter='Marq. L. Rev.',
                               page='475', year=1993)]),
        )
        # fmt: on
        self.run_test_pairs(test_pairs, "Journal citation extraction")

    def test_find_tc_citations(self):
        """Can we parse tax court citations properly?"""
        # fmt: off
        test_pairs = (
            # Test with atypical formatting for Tax Court Memos
            ('the 1 T.C. No. 233',
             [case_citation(page='233', reporter='T.C. No.')]),
            ('word T.C. Memo. 2019-233',
             [case_citation('T.C. Memo. 2019-233',
                            page='233', reporter='T.C. Memo.',
                            volume='2019')]),
            ('something T.C. Summary Opinion 2019-233',
             [case_citation('T.C. Summary Opinion 2019-233',
                            page='233', reporter='T.C. Summary Opinion',
                            volume='2019')]),
            ('T.C. Summary Opinion 2018-133',
             [case_citation('T.C. Summary Opinion 2018-133',
                            page='133', reporter='T.C. Summary Opinion',
                            volume='2018')]),
            # ('U.S. 1234 1 U.S. 1',
            #  [case_citation(volume='1', reporter='U.S.', page='1')]),
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

    def test_citation_filtering(self):
        """Ensure citations with overlapping spans are correctly filtered

        Imagine a scenario where a bug incorrectly identifies the following
        .... at Conley v. Gibson, 355 Mass. 41, 42 (1999) ...
        this returns two reference citations Conley, Gibson and the full cite
        this shouldn't occur but if it did we would be able to filter these
        correcly
        """
        citations = [
            case_citation(
                volume="355",
                page="41",
                reporter_found="U.S.",
                short=False,
                span_start=26,
                span_end=38,
                full_span_start=8,
                full_span_end=49,
                metadata={"plaintiff": "Conley", "defendant": "Gibson"},
            ),
            reference_citation("Conley", span_start=8, span_end=14),
            reference_citation("Gibson", span_start=18, span_end=24),
        ]
        self.assertEqual(len(citations), 3)
        filtered_citations = filter_citations(citations)
        self.assertEqual(len(filtered_citations), 1)
        self.assertEqual(type(filtered_citations[0]), FullCaseCitation)

    def test_disambiguate_citations(self):
        # fmt: off
        test_pairs = [
            # 1. P.R.R --> Correct abbreviation for a reporter.
            ('1 P.R.R. 1',
             [case_citation(reporter='P.R.R.')]),
            # 2. U. S. --> A simple variant to resolve.
            ('1 U. S. 1',
             [case_citation(reporter_found='U. S.')]),
            # 3. A.2d --> Not a variant, but needs to be looked up in the
            #    EDITIONS variable.
            ('1 A.2d 1',
             [case_citation(reporter='A.2d')]),
            # 4. A. 2d --> An unambiguous variant of an edition
            ('1 A. 2d 1',
             [case_citation(reporter='A.2d', reporter_found='A. 2d')]),
            # 5. P.R. --> A variant of 'Pen. & W.', 'P.R.R.', or 'P.' that's
            #    resolvable by year
            ('1 P.R. 1 (1831)',
             # Of the three, only Pen & W. was being published this year.
             [case_citation(reporter='Pen. & W.',
                            year=1831, reporter_found='P.R.')]),
            # 5.1: W.2d --> A variant of an edition that either resolves to
            #      'Wis. 2d' or 'Wash. 2d' and is resolvable by year.
            ('1 W.2d 1 (1854)',
             # Of the two, only Wis. 2d was being published this year.
             [case_citation(reporter='Wis. 2d',
                            year=1854, reporter_found='W.2d')]),
            # 5.2: Wash. --> A non-variant that has more than one reporter for
            #      the key, but is resolvable by year
            ('1 Wash. 1 (1890)',
             [case_citation(reporter='Wash.', year=1890)]),
            # 6. Cr. --> A variant of Cranch, which is ambiguous, except with
            #    paired with this variation.
            ('1 Cra. 1',
             [case_citation(reporter='Cranch', reporter_found='Cra.',
                            metadata={'court': 'scotus'})]),
            # 7. Cranch. --> Not a variant, but could refer to either Cranch's
            #    Supreme Court cases or his DC ones. In this case, we cannot
            #    disambiguate. Years are not known, and we have no further
            #    clues. We must simply drop Cranch from the results.
            ('1 Cranch 1 1 U.S. 23',
             [case_citation(page='23')]),
            # 8. Unsolved problem. In theory, we could use parallel citations
            #    to resolve this, because Rob is getting cited next to La., but
            #    we don't currently know the proximity of citations to each
            #    other, so can't use this.
            #  - Rob. --> Either:
            #                8.1: A variant of Robards (1862-1865) or
            #                8.2: Robinson's Louisiana Reports (1841-1846) or
            #                8.3: Robinson's Virgina Reports (1842-1865)
            # ('1 Rob. 1 1 La. 1',
            # [case_citation(volume='1', reporter='Rob.', page='1'),
            #  case_citation(volume='1', reporter='La.', page='1')]),
            # 9. Johnson #1 should pass and identify the citation
            ('1 Johnson 1 (1890)',
             [case_citation(reporter='N.M. (J.)', reporter_found='Johnson',
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

    def test_nominative_reporter_overlaps(self):
        """Can we parse a full citation where a name looks like a nominative
        reporter?"""
        pairs = [
            (
                "In re Cooke, 93 Wn. App. 526, 529",
                case_citation(volume="93", reporter="Wn. App.", page="526"),
            ),
            (
                "Shapiro v. Thompson, 394 U. S. 618",
                case_citation(volume="394", reporter="U. S.", page="618"),
            ),
            (
                "MacArdell v. Olcott, 82 N.E. 161",
                case_citation(volume="82", reporter="N.E.", page="161"),
            ),
            (
                "Connecticut v. Holmes, 221 A.3d 407",
                case_citation(volume="221", reporter="A.3d", page="407"),
            ),
            (
                "Kern v Taney, 11 Pa. D. & C.5th 558 [2010])",
                case_citation(
                    volume="11", reporter="Pa. D. & C.5th", page="558"
                ),
            ),
            (
                "Ellenburg v. Chase, 2004 MT 66",
                case_citation(volume="2004", reporter="MT", page="66"),
            ),
            (
                "Gilmer, 500 U.S. at 25;",
                case_citation(
                    volume="500", reporter="U. S.", page="25", short=True
                ),
            ),
            (
                "Bison Bee, 778 F. 13 App’x at 73.",
                case_citation(volume="778", reporter="F.", page="13"),
            ),
        ]
        for cite_string, cite_object in pairs:
            parsed_cite = get_citations(cite_string)[0]
            self.assertEqual(
                parsed_cite,
                cite_object,
                f"Nominative reporters getting in the way of parsing: {parsed_cite}",
            )

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
             [case_citation(reporter_found='U,S,')]),
        ]
        # fmt: on
        self.run_test_pairs(
            test_pairs, "Custom tokenizer", tokenizers=[tokenizer]
        )

    def test_citation_fullspan(self):
        """Check that the full_span function returns the correct indices."""

        # Make sure it works with several citations in one string
        combined_example = "citation number one is Wilson v. Mar. Overseas Corp., 150 F.3d 1, 6-7 ( 1st Cir. 1998); This is different from Commonwealth v. Bauer, 604 A.2d 1098 (Pa.Super. 1992), my second example"
        extracted = get_citations(combined_example)
        # answers format is (citation_index, (full_span_start, full_span_end))
        answers = [(0, (23, 86)), (1, (111, 164))]
        for cit_idx, (start, end) in answers:
            self.assertEqual(
                extracted[cit_idx].full_span()[0],
                start,
                f"full_span start index doesn't match for {extracted[cit_idx]}",
            )
            self.assertEqual(
                extracted[cit_idx].full_span()[1],
                end,
                f"full_span end index doesn't match for {extracted[cit_idx]}",
            )

        # full_span should cover the whole string
        simple_examples = [
            "66 B.U. L. Rev. 71 (1986)",
            "5 Minn. L. Rev. 1339, 1341 (1991)",
            "42 U.S.C. § 405(r)(2) (2019)",
            "37 A.L.R.4th 972, 974 (1985)",
            "497 Fed. Appx. 274 (4th Cir. 2012)",
            # "Smart Corp. v. Nature's Farm Prods., No. 99 Civ. 9404 (SHS), 2000 U.S. Dist. LEXIS 12335 (S.D.N.Y. Aug. 25, 2000)",
            "Alderson v. Concordia Par. Corr. Facility, 848 F.3d 415 (5th Cir. 2017)",
        ]
        for example in simple_examples:
            extracted = get_citations(example)[0]
            error_msg = "Full span indices for a simple example should be (0, len(example)) "
            self.assertEqual(
                extracted.full_span(), (0, len(example)), error_msg
            )
        # Sentence and correct start_index
        stopword_examples = [
            ("See 66 B.U. L. Rev. 71 (1986)", 4),
            ("Citing 66 B.U. L. Rev. 71 (1986)", 7),
        ]
        for sentence, start_idx in stopword_examples:
            extracted = get_citations(sentence)[0]
            error_msg = "Wrong span for stopword example"
            self.assertEqual(
                extracted.full_span(), (start_idx, len(sentence)), error_msg
            )

    def test_reference_extraction_using_resolved_names(self):
        """Can we extract a reference citation using resolved metadata?"""
        texts = [
            # In this case the reference citation got with the
            # resolved_case_name is redundant, was already got in the regular
            # process. Can we deduplicate?
            """See, e.g., State v. Wingler, 135 A. 2d 468 (1957);
            [State v. Wingler at 175, citing, Minnesota ex rel.]""",
            # In this case the resolved_case_name actually helps getting the
            # reference citation
            """See, e.g., State v. W1ngler, 135 A. 2d 468 (1957);
            [State v. Wingler at 175, citing, Minnesota ex rel.]""",
        ]
        for plain_text in texts:
            citations = get_citations(plain_text)
            found_cite = citations[0]
            found_cite.metadata.resolved_case_name = "State v. Wingler"
            document = Document(plain_text=plain_text, markup_text="")
            references = extract_reference_citations(
                citation=found_cite, document=document
            )
            final_citations = filter_citations(citations + references)
            self.assertEqual(
                len(final_citations), 2, "There should only be 2 citations"
            )
            self.assertEqual(
                len(references),
                1,
                "Only a reference citation should had been picked up",
            )

    def test_reference_extraction_from_markup(self):
        """Can we extract references from markup text?"""
        # https://www.courtlistener.com/api/rest/v4/opinions/1985850/
        markup_text = """
        <i>citing, </i><i>U.S. v. Halper,</i> 490 <i>U.S.</i> 435, 446, 109 <i>
        S.Ct.</i> 1892, 1901, 104 <i>L.Ed.</i>2d 487 (1989).
        ; and see, <i>Bae v. Shalala,</i> 44 <i>F.</i>3d 489 (7th Cir.1995).
        <p>In <i>Bae,</i> the 7th Circuit Court further interpreted
        the holding of <i>Halper.</i> In <i>Bae,</i> the court... by the
        <i>ex post facto</i> clause of the U.S. Constitution...</p>
        <p>In <i>Bae,</i> the circuit court rejected the defendant's
        argument that since debarment served both remedial <i>and</i>
        punitive goals it must be characterized as punishment. Bae's argument
        evidently relied on the <i>Halper</i> court's use of the word \"solely\"
        in the discussion leading to its holding. The circuit court's
        interpretation was much more pragmatic: \"A civil sanction that can
        fairly be said solely to serve remedial goals will not fail under
        <i>ex post facto</i> scrutiny simply because it is consistent with
        punitive goals as well.\" 44 <i>F.</i>3d at 493.</p>"""

        citations = get_citations(
            markup_text=markup_text, clean_steps=["html", "all_whitespace"]
        )
        references = [c for c in citations if isinstance(c, ReferenceCitation)]
        # Tests both for the order and exact counts. Note that there is one
        # "Bae" in the text that should not be picked up: "Bae's argument"...
        self.assertListEqual(
            [ref.matched_text().strip(",.") for ref in references],
            ["Bae", "Halper", "Bae", "Bae", "Halper"],
        )

    def test_reference_filtering(self):
        """Can we filter out ReferenceCitation that overlap other citations?"""
        texts = [
            # https://www.courtlistener.com/api/rest/v4/opinions/9435339/
            # Test no overlap with supra citations
            """<em>Bell Atlantic Corp. </em>v. <em>Twombly, </em>550 U. S. 544 (2007),
            which discussed... apellate court’s core competency.
             <em>Twombly, </em>550 U. S., at 557. Evaluating...
            In <em>Twombly</em>, supra, at 553-554, the Court found...
            Another, in <em>Twombly, supra</em>, at 553-554, the Court found
            """,
            # From the previous source; test no overlap with single-name
            # full case citation
            """
            <em>Johnson </em>v. <em>Jones, </em>515 U. S. 304, 309 (1995)
             something... with,” <em>Swint </em>v. <em>Chambers County Comm’n,
             </em>514 U. S. 35, 51 (1995), and “directly implicated by,”
             <em>Hartman, supra, </em>at 257, n. 5, the qualified-immunity
             defense.</p>\n<p id=\"b773-6\">Respondent counters that our
             holding in <em>Johnson, </em>515 U. S. 304, confirms
            """,
            # https://www.courtlistener.com/opinion/8524158/in-re-cahill/
            # Test no overlap with single-name-and-pincite full case citation
            """ was not con-firmable. <em>Nobelman v. Am. Sav. Bank, </em>
            508 U.S. 324, 113 S.Ct. 2106, 124 L.Ed.2d 228 (1993). That plan
             residence.” <em>Nobelman </em>at 332, 113 S.Ct. 2106.
             Section 1123(b)(5) codifies the
            """,
        ]
        for markup_text in texts:
            citations = get_citations(
                markup_text=markup_text, clean_steps=["html", "all_whitespace"]
            )
            self.assertFalse(
                any(
                    [isinstance(cite, ReferenceCitation) for cite in citations]
                )
            )

    def test_markup_plaintiff_and_antecedent_guesses(self) -> None:
        # Can we identify full case names in markup text
        test_pairs = (
            # Case Name unbalanced across two tags
            (
                (
                    "and more and more <em>Jin Fuey Moy</em><em>v. United States,</em>\n"
                    "            254 U.S. 189. Petitioner contends"
                ),
                [
                    case_citation(
                        volume="254",
                        reporter="U.S.",
                        page="189",
                        metadata={
                            "plaintiff": "Jin Fuey Moy",
                            "defendant": "United States",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Extract from one tag and ignore the other
            (
                (
                    "<em>Overruled</em> and so on <em>Jin Fuey Moy v. United States,</em> "
                    "254 U.S. 189. Petitioner contends"
                ),
                [
                    case_citation(
                        volume="254",
                        reporter="U.S.",
                        page="189",
                        metadata={
                            "plaintiff": "Jin Fuey Moy",
                            "defendant": "United States",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # split across tags with v. in defendant
            (
                (
                    "<em>Overruled</em> and so on <em>Jin Fuey Moy</em> <em>v. United States,</em> "
                    "254 U.S. 189. Petitioner contends"
                ),
                [
                    case_citation(
                        volume="254",
                        reporter="U.S.",
                        page="189",
                        metadata={
                            "plaintiff": "Jin Fuey Moy",
                            "defendant": "United States",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # corporation name threew ords
            (
                "<em>Bell Atlantic Corp. </em>v. <em>Twombly, </em>550 U. S. 544 (2007),",
                [
                    case_citation(
                        volume="550",
                        reporter="U. S.",
                        page="544",
                        year=2007,
                        metadata={
                            "plaintiff": "Bell Atlantic Corp.",
                            "defendant": "Twombly",
                            "year": "2007",
                            "court": "scotus",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # two word plaintiff
            (
                "con-firmable. <em>United States v. Am. Sav. Bank, </em> 508 U.S. 324 (1993). That plan "
                "proposed to bifurcate the claim and",
                [
                    case_citation(
                        volume="508",
                        reporter="U.S.",
                        page="324",
                        year=1993,
                        metadata={
                            "plaintiff": "United States",
                            "defendant": "Am. Sav. Bank",
                            "year": "1993",
                            "court": "scotus",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Extract reference citation full name
            (
                (
                    ". <em>Jin Fuey Moy</em> <em>v. United States,</em> 254 U.S. 189. Petitioner contends.  "
                    "Regardless in <em>Jin Fuey Moy</em> the court ruled"
                ),
                [
                    case_citation(
                        volume="254",
                        reporter="U.S.",
                        page="189",
                        metadata={
                            "plaintiff": "Jin Fuey Moy",
                            "defendant": "United States",
                        },
                    ),
                    reference_citation(
                        "Jin Fuey Moy", metadata={"plaintiff": "Jin Fuey Moy"}
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Extract out with whitespace across two tags
            (
                (
                    '<p id="b453-6">\n'
                    "  The supreme court of Connecticut, in\n"
                    "  <em>\n"
                    "   Beardsley\n"
                    "  </em>\n"
                    "  v.\n"
                    "  <em>\n"
                    "   Hartford,\n"
                    "  </em>\n"
                    "  50 Conn. 529, 541-542, after quoting the maxim of the common law;\n"
                    "  <em>\n"
                    "   cessante ratione legis-, cessat ipsa lex,\n"
                    "  </em>"
                ),
                [
                    case_citation(
                        volume="50",
                        reporter="Conn.",
                        page="529",
                        metadata={
                            "plaintiff": "Beardsley",
                            "defendant": "Hartford",
                            "pin_cite": "541-542",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # identify reference
            (
                (
                    " partially secured by a debtor’s principal residence was not "
                    "con-firmable. <em>Smart Nobelman v. Am. Sav. Bank, </em>"
                    "508 U.S. 324 (1993). That plan proposed to bifurcate the claim and... pay the unsecured"
                    "... only by a lien on the debtor’s principal residence.” "
                    "codifies the <em>Smart Nobelman </em>decision in individual debtor chapter 11 cases."
                ),
                [
                    case_citation(
                        volume="508",
                        reporter="U.S.",
                        page="324",
                        metadata={
                            "plaintiff": "Smart Nobelman",
                            "defendant": "Am. Sav. Bank",
                            "year": "1993",
                        },
                    ),
                    reference_citation(
                        "Smart Nobelman",
                        metadata={"plaintiff": "Smart Nobelman"},
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # add antecedent guess to check
            (
                "the court in <em>Smith Johnson</em>, 1 U. S., at 2",
                [
                    case_citation(
                        page="2",
                        reporter_found="U. S.",
                        short=True,
                        metadata={"antecedent_guess": "Smith Johnson"},
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # make sure not to overwrite good data if this method doesnt work
            (
                "Judge Regan (dissenting) in <i>Thrift Funds Canal,</i> Inc. v. Foy, 242 So.2d 253, 257 (La.App. 4 Cir. 1970), calls",
                [
                    case_citation(
                        page="253",
                        reporter="So.2d",
                        volume="242",
                        short=False,
                        metadata={
                            "plaintiff": "Thrift Funds Canal, Inc.",
                            "defendant": "Foy",
                            "pin_cite": "257",
                            "year": "1970",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Eyecite has issue with linebreaks when identifying defendants and
            # previously could store defendant as only whitespace
            (
                "<em>\n   Smart v. Tatum,\n  </em>\n \n  541 U.S. 1085 (2004);\n  <em>\n",
                [
                    case_citation(
                        page="1085",
                        volume="541",
                        reporter="U.S.",
                        year=2004,
                        metadata={
                            "plaintiff": "Smart",
                            "defendant": "Tatum",
                            "court": "scotus",
                        },
                    )
                ],
                {"clean_steps": ["html", "inline_whitespace"]},
            ),
            # tricky scotus fake cites if junk is inbetween remove it
            (
                " <i>United States</i> v. <i>Hodgson,</i> ___ Iowa ___, 44 N.J. 151, 207 A. 2d 542;",
                [
                    case_citation(
                        page="151",
                        volume="44",
                        reporter="N.J.",
                        short=False,
                        metadata={
                            "plaintiff": "United States",
                            "defendant": "Hodgson",
                        },
                    ),
                    case_citation(
                        page="542",
                        volume="207",
                        reporter="A. 2d",
                        short=False,
                        metadata={
                            "plaintiff": "United States",
                            "defendant": "Hodgson",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # tricky scotus fake cites if junk is inbetween remove it
            (
                " <i>United States ex rel. Russo v. New Jersey</i>, 351 F.2d 429 something something",
                [
                    case_citation(
                        page="429",
                        volume="351",
                        reporter="F.2d",
                        short=False,
                        metadata={
                            "plaintiff": "United States ex rel. Russo",
                            "defendant": "New Jersey",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Identify pincite reference
            (
                (
                    " partially secured by a debtor’s principal residence was not "
                    "con-firmable. <em>Nobelman v. Am. Sav. Bank, </em>"
                    "508 U.S. 324 (1993). That plan proposed to bifurcate the claim and... pay the unsecured"
                    "... only by a lien on the debtor’s principal residence.” "
                    "codifies the  a lien on the debtor’s principal residence.” "
                    "<em>Nobelman </em>at 332, decision in individual debtor chapter 11 cases."
                ),
                [
                    case_citation(
                        volume="508",
                        reporter="U.S.",
                        page="324",
                        metadata={
                            "plaintiff": "Nobelman",
                            "defendant": "Am. Sav. Bank",
                            "year": "1993",
                        },
                    ),
                    reference_citation(
                        "Nobelman",
                        metadata={"plaintiff": "Nobelman", "pin_cite": "332"},
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # remove the See at the start and handle other tags
            (
                """<i>See <span class="SpellE">DeSantis</span> v. Wackenhut Corp.</i>, 793 S.W.2d 670;""",
                [
                    case_citation(
                        page="670",
                        reporter="S.W.2d",
                        volume="793",
                        short=False,
                        metadata={
                            "plaintiff": "DeSantis",
                            "defendant": "Wackenhut Corp.",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Antecedent guess
            (
                """</span>§ 3.1 (2d ed. 1977), <i>Strawberry Hill</i>, 725 S.W.2d at 176 (Gonzalez, J., dissenting);""",
                [
                    unknown_citation("§"),
                    case_citation(
                        page="176",
                        reporter="S.W.2d",
                        volume="725",
                        short=True,
                        metadata={
                            "antecedent_guess": "Strawberry Hill",
                            "pin_cite": "176",
                            "parenthetical": "Gonzalez, J., dissenting",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Stop word inside tag
            (
                """</span>§ 3.1 (2d ed. 1977), <i>(See Hill</i>, 725 S.W.2d at 176 (Gonzalez, J., dissenting));""",
                [
                    unknown_citation("§"),
                    case_citation(
                        page="176",
                        reporter="S.W.2d",
                        volume="725",
                        short=True,
                        metadata={
                            "antecedent_guess": "Hill",
                            "pin_cite": "176",
                            "parenthetical": "Gonzalez, J., dissenting",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Handle embedded pagnation
            (
                """<i>United States</i> v. <i>Carignan,</i> <span class="star-pagination">*528</span> 342 U. S. 36, 41;""",
                [
                    case_citation(
                        page="36",
                        volume="342",
                        reporter="U. S.",
                        short=False,
                        metadata={
                            "plaintiff": "United States",
                            "defendant": "Carignan",
                            "pin_cite": "41",
                            "court": "scotus",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Better support Louisiana with proper extraction of defendant
            (
                """objection. <i>Our Lady of the Lake Hosp. v. Vanner,</i> 95-0754, p. 3 (La.App. 1 Cir. 12/15/95), 669 So.2d 463, 464;""",
                [
                    case_citation(
                        page="463",
                        volume="669",
                        reporter="So.2d",
                        short=False,
                        metadata={
                            "plaintiff": "Our Lady of the Lake Hosp.",
                            "defendant": "Vanner",
                            "pin_cite": "464",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            (
                """<em>Cf. Akins v. State, </em>104 So.3d 1173 (Fla. 1st DCA 2012)""",
                [
                    case_citation(
                        page="1173",
                        volume="104",
                        reporter="So.3d",
                        short=False,
                        metadata={
                            "plaintiff": "Akins",
                            "defendant": "State",
                            "year": "2012",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            (
                """<em>
   In re Dixon,
  </em>
  41 Cal.2d 756 (1953).""",
                [
                    case_citation(
                        page="756",
                        volume="41",
                        reporter="Cal.2d",
                        short=False,
                        metadata={
                            "plaintiff": None,
                            "defendant": "Dixon",
                            "year": "1953",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # can we extract out the citation if its not wrapped in html but in html
            (
                "dentification. Stovall v. Denno, 388 U.S. 293, ",
                [
                    case_citation(
                        page="293",
                        volume="388",
                        reporter="U.S.",
                        short=False,
                        metadata={
                            "plaintiff": "Stovall",
                            "defendant": "Denno",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # can we remove see also
            (
                """<em>see also Cass v. Stephens</em>,\r\n156 S.W.3d 38""",
                [
                    case_citation(
                        page="38",
                        volume="156",
                        reporter="S.W.3d",
                        short=False,
                        metadata={
                            "plaintiff": "Cass",
                            "defendant": "Stephens",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # technically this is incorrect in determing plaintiff/defendant but we have no way to deal with that
            (
                """ <i>See </i><i>Loup-Miller Const. Co. v. City and County of Denver,</i> 676 P.2d 1170 (Colo.1984) .... <i>See </i><i>Loup-Miller,</i> 676 P.2d 1170 and so on <i>Loup-Miller</i>""",
                [
                    case_citation(
                        page="1170",
                        volume="676",
                        reporter="P.2d",
                        short=False,
                        metadata={
                            "plaintiff": "Loup-Miller Const. Co.",
                            "defendant": "City and County of Denver",
                        },
                    ),
                    case_citation(
                        page="1170",
                        volume="676",
                        reporter="P.2d",
                        short=False,
                        metadata={
                            "defendant": "Loup-Miller",
                        },
                    ),
                    reference_citation(
                        "Loup-Miller",
                        metadata={"defendant": "Loup-Miller"},
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
        )
        self.run_test_pairs(test_pairs, "Citation extraction")


#
# # '<div>\n<center><b>702 S.W.2d 869 (1985)</b></center>\n<center><h1>STATE of Missouri, Respondent,<br>\nv.<br>\nPaul FREEMAN, a/k/a Paul Washington, Appellant.</h1></center>\n<center>No. 13842.</center>\n<center><p><b>Missouri Court of Appeals, Southern District, Division Three.</b></p></center>\n<center>November 26, 1985.</center>\n<center>Motion for Rehearing or to Transfer Denied December 17, 1985.</center>\n<center>Application to Transfer Denied February 18, 1986.</center>\n<p><span class="star-pagination">*870</span> Holly G. Simons, Asst. Public Defender, Columbia, for appellant.</p>\n<p>William L. Webster, Atty. Gen., Michael H. Finkelstein, Asst. Atty. Gen., Jefferson City, for respondent.</p>\n<p>FLANIGAN, Judge.</p>\n<p>A jury found defendant guilty of assault in the first degree, § 565.050,<sup>[1]</sup> robbery in the first degree, § 569.020, and armed criminal action, § 571.015, and assessed the punishment at life imprisonment for each offense. The trial court ordered that the sentences run consecutively. Defendant appeals.</p>\n<p>In the early morning of December 27, 1983, defendant, armed with a gun, entered a Piggley Wiggley store in Sikeston and <span class="star-pagination">*871</span> asked store employee Wesley Francis for change for a $20 bill. While Francis was complying with the request, defendant knocked him to the floor and took over $70 from the cash register. Defendant then shot Francis three times in the head. Although Francis survived, his injuries were severe and rendered him blind in his left eye and deaf in his left ear. The events were witnessed by another store employee, Melvin Moon.</p>\n<p>Defendant\'s first point is that the trial court erred "in not allowing defendant to proceed pro se at the trial level in that defendant asserted his right to so proceed and was denied this constitutionally recognized right with no inquiry into defendant\'s ability to conduct his own defense."</p>\n<p>Defendant\'s first point was not included in his motion for new trial and accordingly has not been preserved for appellate review. Rule 29.11(d). Defendant has requested review under the "plain error" standards prescribed by Rule 29.12(b). This court affords plain error review and finds no merit in defendant\'s first point.</p>\n<p>A defendant in a state criminal trial has a constitutional right to proceed without counsel when he voluntarily and intelligently elects to do so. <i>Faretta v. California,</i> 422 U.S. 806, 95 S.Ct. 2525, 45 L.Ed.2d 562 (1975). "Missouri, prior to <i>Faretta</i><i>,</i> recognized a criminal defendant\'s right to represent himself. The right is based on Art. 1, § 18(a) of the Missouri Constitution, and Rule 31.02(a). See <i>Bibbs v. State,</i> 542 S.W.2d 549, 550 (Mo.App.1976), and the authorities cited there." <i>State v. Ehlers,</i> 685 S.W.2d 942, 945 (Mo.App.1985).</p>\n<p>In <i>State v. McCafferty,</i> 587 S.W.2d 611 (Mo.App.1979), the court of appeals held that in the absence of any request by defendant to represent himself the trial court did not err in failing to inform him of his right to do so and that the right to self-representation is one which the defendant "must clearly and unequivocally assert before trial." The following authorities support the corollary principle that there can be no denial of the right to self-representation in the absence of an unequivocal request to exercise that right. <i>United States v. Bennett,</i> 539 F.2d 45, 50[3] (10th Cir. 1976); <i>People v. Potter,</i> 77 Cal.App.3d 45, 143 Cal.Rptr. 379, 382[2] (1978); <i>Russell v. State,</i> 270 Ind. 55, 383 N.E.2d 309, 313[6] (1978); <i>Anderson v. State,</i> 267 Ind. 289, 370 N.E.2d 318, 320[2] (1977); <i>Block v. State,</i> 95 Nev. 933, 604 P.2d 338, 340[2] (1979); <i>Stowe v. State,</i> 590 P.2d 679, 682[1] (Okla.Crim.1979); <i>Felts v. Oklahoma,</i> 588 P.2d 572, 576[3] (Okla.Crim.1978). See 98 A.L.R.3d 13, 61, § 13.</p>\n<p>Several hearings were held prior to the trial itself which was held on May 17, 1984. At all of these hearings the prosecutor appeared and the defendant appeared in person and by his attorney, Daniel A. Beatty, an assistant public defender.</p>\n<p>On February 9, 1984, a hearing was held which was prompted by a letter which defendant sent to the court. Defendant informed the court that he did not feel that he was being represented properly and indicated he had had difficulty getting in contact with Mr. Beatty. Mr. Beatty informed the court that he was on active duty with the Navy in Seattle, Washington, when the defendant attempted to contact him. Mr. Beatty also said, "There was a letter from [defendant] regarding possible self-representation, <i>which I understand he did not want to do at this time.</i> However, it is also my understanding that he is trying to hire his own lawyer but has not been able to do so. His family may still be working on it." At the conclusion of that hearing defendant told the court that he wanted "to keep his attorney."</p>\n<p>On March 10, 1984, a hearing was held. At that time the court ordered the case, at defendant\'s request, sent back to Scott County, from which defendant earlier had taken a change of venue. There was no mention of any dissatisfaction with attorney Beatty.</p>\n<p>On April 26, 1984, a hearing was held. Attorney Beatty stated to the court, "[Defendant] has instructed me to file a motion to withdraw. <i>He desires to retain his own counsel or to represent himself.</i> I don\'t <span class="star-pagination">*872</span> think he is satisfied with the way the case is going at this point."</p>\n<p>The court asked the defendant what the problem was and defendant stated, "Mr. Beatty and I have not had communications I feel I am entitled to.... I have requested certain things of Mr. Beatty I would appreciate for him to do for me. Mr. Beatty told me he had done them, and when everything comes to a certain point, they have not been done."</p>\n<p>The court asked the defendant, "What is your plan?" The defendant answered that he had been writing "to the U.S. District Court and Bar Association and <i>trying to see if they will send me a lawyer."</i> Defendant also said that he had been writing the NAACP. The court asked the defendant if he was going to hire an attorney and the defendant responded, "I didn\'t tell Mr. Beatty I was going to hire an attorney. I was telling Mr. Beatty <i>I was going to see what would happen.</i>"</p>\n<p>There was some discussion of obtaining another public defender for defendant but a representative of the public defender\'s office said, "There is just no provision for doing that."</p>\n<p>The court asked the defendant what it was which he had asked attorney Beatty to do and which Beatty had not done. The defendant mentioned that he had requested Beatty to obtain a transcript of the preliminary hearing. Mr. Beatty stated he did not recall that request and that the hearing was not transcribed.</p>\n<p>The following then occurred:</p>\n<blockquote>"THE COURT: Mr. Freeman, <i>I am not going to let you represent yourself,</i> because they would switch over to capital murder (sic) and put you in the gas chamber. You don\'t have that capability and that training to defend yourself....</blockquote>\n<blockquote>My job is to see that you have adequate representation. If there is a personality conflict, that\'s one thing; but I am not going to let you represent yourself for your protection. They would take you out like a sitting duck and you wouldn\'t have a chance.</blockquote>\n<blockquote>Now, the problem for me is to get you represented, but, at the same time, try to get you somebody that you can work with. The NAACP is not going to spend 10 cents on you. The Bar Association is not going to spend any money on you. If they did, it would take 50 million a year to represent people.</blockquote>\n<blockquote>If I can\'t work it out with my defenders, why don\'t you see if the defender system will transfer Gary down here to take this case and maybe trade off something?</blockquote>\n<blockquote>[REPRESENTATIVE OF THE PUBLIC DEFENDER\'S OFFICE]: I can call my state office, but the policy has been in the past, and this has come up before in the other counties, where they have not made me come when other judges have requested me.</blockquote>\n<blockquote>THE COURT: Let\'s see what we can work out, if there is an alternative available. If there is not, then Mr. Freeman, you may have to stay married to him, because, actually, the job to decide whether he\'s competent or not is left to me, and I have great faith in him. He is kind of quiet, but he knows his job. I will look into it, and if it is possible, change attorneys for you.</blockquote>\n<blockquote>You have to understand if it\'s not possible and I cannot, you will have to stay hooked. <i>I will not let you go in alone.</i> This world is a war world. They are adversaries. You are not an adversary, and I will not let you walk in that meat grinder alone. You don\'t necessarily have to like the guy that defends you. That\'s something you need to know."</blockquote>\n<p>The defendant then informed the court that he had contacted a St. Louis lawyer and "he said due to my financial background that he couldn\'t." The following then occurred:</p>\n<blockquote>"THE COURT: I cannot assure you that I will take Mr. Beatty off the case, <i>because I won\'t let you represent yourself.</i> I don\'t think you can. That\'s the only reason. I am not going to have you knocked plumb in the puddle without somebody standing there. Even if they <span class="star-pagination">*873</span> don\'t like you, they will do their best to defend you.</blockquote>\n<blockquote>. . . . .</blockquote>\n<blockquote>THE COURT: Are you happy with the venue right now?</blockquote>\n<blockquote>THE DEFENDANT: Yes.</blockquote>\n<blockquote>THE COURT: <i>The only real complaint you have right now is you would like to change attorneys,</i> if possible?</blockquote>\n<blockquote>THE DEFENDANT: <i>Yes.</i>\n</blockquote>\n<blockquote>MR. BEATTY: Your Honor, can I say just a couple of things? I don\'t have a conflict representing Mr. Freeman. I have been trying to do what he tells me to do. I think his personality conflict\x97 it\'s on his part, not mine. I will be glad to represent him all the way through.</blockquote>\n<blockquote>THE COURT: I understand. We will see if I can roll him another defender. If I cannot, what Mr. Beatty is saying, he is ready to go. Let\'s set this for trial."</blockquote>\n<p>The case was set for May 17, 1984. The court asked the defendant if that setting was all right and the defendant answered, "That\'s all right with me."</p>\n<p>On May 10, 1984, the defendant informed the court that he had again been in touch with the St. Louis attorney and that the latter had said "he would charge me a total of $5,000 to represent the case." Defendant added, "I was going to see if I could get on the family." After being informed that the case was set for trial on May 17, the defendant said, "I wanted a little more time. It really doesn\'t make any more difference if the prosecutor is ready."</p>\n<p>On May 17, prior to the commencement of the trial, in response to questioning by the court, defendant stated that he was "satisfied with Mr. Beatty now."</p>\n<p>The record shows that although defendant was unsatisfied with his attorney during some of the preliminary proceedings, and attempted without success to engage other counsel, at no time did defendant make an unequivocal request to the trial court that he be permitted to represent himself. The record further demonstrates that defendant\'s dissatisfaction with his attorney no longer existed when the trial commenced. It is true that some of the remarks made by the trial court show an unwillingness to accede to a request for self-representation if such a request had been made. The trial court, however, cannot be convicted of error in denying the defendant his right to self-representation in the absence of an unequivocal request to exercise that right. There was no such request and defendant\'s first point lacks factual support. The record fails to show that the pretrial proceedings dealing with the matter of defendant\'s representation resulted in "manifest injustice or miscarriage of justice." Rule 29.12(b). Defendant\'s first point has no merit.</p>\n<p>Defendant\'s second point is that the trial court erred in denying defendant\'s motion for a continuance, made at the close of the state\'s evidence, on account of the absence of defense witness Sadie Washington. The witness, defendant\'s sister, had been subpoenaed but failed to appear. Rule 24.09 requires that an application for continuance be made by a written motion accompanied by the affidavit of the applicant or some other credible person setting forth the facts upon which the application is based, unless the adverse party consents that the application for continuance be made orally. Rule 24.10 sets forth the requirements of an application for continuance on account of the absence of witnesses.</p>\n<p>Defendant filed a written motion for continuance which failed to meet the requirements of Rule 24.10. The written motion was not accompanied by an affidavit. The motion failed to set forth facts showing the materiality of the evidence sought to be obtained and due diligence on the part of defendant to obtain such witness. It failed to set forth the address of the witness and also failed to set forth facts showing reasonable grounds for belief that the attendance of the witness would be procured within a reasonable time. The motion failed to set forth "what particular facts the witness will prove," Rule 24.10(c), and it also failed to state "that such witness is not absent by the connivance, consent or procurement of the applicant." <span class="star-pagination">*874</span> Rule 24.10(d). Although counsel for defendant made some remarks in support of the written motion, those remarks did not cure the foregoing deficiencies. The officer who served the subpoena upon the witness informed the court that the witness stated to him, "I will not be there. I am not going to get on the stand and lie for Paul." Defendant made no objection to the giving of that information.</p>\n<p>An application for continuance in a criminal case is addressed to the sound discretion of the trial court and the appellate court will not interfere unless it clearly appears that such discretion has been abused. <i>State v. Oliver,</i> 572 S.W.2d 440, 445[2] (Mo. banc 1978). In exercising the discretion the trial court is entitled to consider whether the application meets the requirements of The Rules of Criminal Procedure. <i>State v. McGinnis,</i> 622 S.W.2d 416, 420 (Mo.App.1981). The trial court did not abuse its discretion in denying the motion. Defendant\'s second point has no merit.</p>\n<p>Defendant\'s third point is that the trial court abused its discretion by sentencing defendant to three consecutive life terms "because such punishment is shocking to the conscience in that each count arose from a single incident and the elements of the three counts overlap to such an extent that consecutive sentences constitute cruel and unusual punishment under the Missouri and United States Constitutions."</p>\n<p>The jury found defendant guilty of assault in the first degree, committed by means of a deadly weapon, § 565.050.2, which at the time of the instant event was a class A felony. He was also convicted of robbery in the first degree, a class A felony, § 569.020. Life imprisonment is an authorized term of imprisonment for a class A felony, § 558.011.1(1). Defendant was also convicted of armed criminal action, § 571.015, which, under that statute, is punishable "by imprisonment by the division of corrections for a term of not less than three years." Life imprisonment is an authorized punishment for armed criminal action. <i>State v. Kirksey,</i> 647 S.W.2d 799, 801 (Mo. banc 1983). The punishment for armed criminal action "shall be in addition to any punishment provided by law for the crime committed by, with or through the use, assistance or aid of a dangerous instrument or deadly weapon." § 571.015.1. The language just quoted does not require that a sentence imposed for armed criminal action be consecutive to a sentence for the felony conviction upon which the armed criminal action charge is based. <i>State v. Treadway,</i> 558 S.W.2d 646, 653[16] (Mo. banc 1977), overruled on other grounds, <i>Sours v. State,</i> 593 S.W.2d 208 (Mo. banc 1980). There the Supreme Court said: "[T]he trial court should be able to sentence a defendant consecutively or concurrently as it sees fit."</p>\n<p>Shortly after 4:00 a.m. on December 27, 1983, defendant entered the Piggley Wiggley store at which Wesley Francis was employed. Francis gave the following description of what next occurred:</p>\n<blockquote>"I was standing at my register and I heard the door open. I looked up, and Paul Freeman walked in the door. He was waving a bill and he said it was a 20, but I couldn\'t see it.</blockquote>\n<blockquote>He walked through the last checkout and I said, `You will have to come over here so I can change it for you.\' When he walked beside me, I looked at him and I said, `I will have to get my manager up here to see if I can change it first.\'</blockquote>\n<blockquote>He said, `No, my cab is going to leave me.\' It was snowing outside and I didn\'t want him walking, so I opened my register and his hands were maybe four inches from my face and he was already swinging at me. He hit me in my left eye and knocked me down, and I looked up and I saw him digging money out of the register as fast as he could and putting it in his right pocket. He came around behind me and said, `Sorry I have to do this, but I can\'t leave no witnesses,\' and he shot me in the\x97</blockquote>\n<blockquote>Q. Show the jury where the shots hit you.</blockquote>\n<blockquote>A. One here, one here, one here.</blockquote>\n<blockquote>\n<span class="star-pagination">*875</span> Q. That\'s on the top of your left eye and also on your left ear; is that right?</blockquote>\n<blockquote>A. Yes, sir."</blockquote>\n<p>Francis described the weapon used by defendant as "a small caliber handgun." Francis\' description of the occurrence was generally confirmed by Melvin Moon, 22, who had attended school with defendant. After describing the shooting, Moon testified, "I saw Paul Freeman running out the door. He had his back to me. He stopped at the door because he saw my reflection. Before he got ready to step on the mat he turned around and said, `Moon, don\'t tell what you just seen.\'" Moon testified defendant\'s weapon was a "22 handgun." Moon also testified, "I knew Freeman for 15 or 16 years. Couldn\'t have been nobody else that looked that much like him. I have known him a long time."</p>\n<p>Mark Sever, M.D., testified that he examined Francis at 4:50 a.m. at "our emergency facility," and Francis had three gunshot wounds to the head. Dr. Sever testified he did not expect Francis to live.</p>\n<p>The trial court had the power to order that the three life sentences run consecutively. § 558.026.1. <i>State v. Greathouse,</i> 694 S.W.2d 903, 911[20] (Mo.App. 1985). Where the defendant is convicted of separate offenses and the sentences imposed are within statutory limits, the consecutive effect of the sentences does not constitute cruel and unusual punishment. <i>State v. Repp,</i> 603 S.W.2d 569, 571[5] (Mo. banc 1980); <i>State v. Jackson,</i> 676 S.W.2d 304, 305[3] (Mo.App.1984). Punishment within the statutory limit is not cruel and unusual unless it is so disproportionate to the offense committed as to shock the moral sense of all reasonable men as to what is right and proper. <i>State v. Rider,</i> 664 S.W.2d 617, 621[10] (Mo.App.1984). Although the three offenses arose out of the same incident, they were separate offenses. Defendant does not claim otherwise and defendant makes no claim of a double jeopardy violation.<sup>[2]</sup></p>\n<p>In <i>Solem v. Helm,</i> 463 U.S. 277, 103 S.Ct. 3001, 77 L.Ed.2d 637 (1983), the Supreme Court held that the final clause of the Eighth Amendment ["nor cruel and unusual punishments inflicted"] prohibits not only barbaric punishments, but also sentences that are disproportionate to the crime committed.</p>\n<p>At p. 3009 of 103 S.Ct. the Court said:</p>\n<blockquote>"In sum, we hold as a matter of principle that a criminal sentence must be proportionate to the crime for which the defendant has been convicted. Reviewing courts, of course, should grant substantial deference to the broad authority that legislatures necessarily possess in determining the types and limits of punishments for crimes, as well as to the discretion that trial courts possess in sentencing convicted criminals. But no penalty is per se constitutional."</blockquote>\n<blockquote>Also at p. 3009, n. 16, the Court said:</blockquote>\n<blockquote>"Absent specific authority, it is not the role of an appellate court to substitute its judgment for that of the sentencing court as to the appropriateness of a particular sentence; rather, in applying the Eighth Amendment the appellate court decides only whether the sentence under review is within constitutional limits. In view of the substantial deference that must be accorded legislatures and sentencing courts, a reviewing court rarely will be required to engage in extended analysis to determine that a sentence is not constitutionally disproportionate." Finally, at pp. 3010-3011, the Court said:</blockquote>\n<blockquote>"In sum, a court\'s proportionality analysis under the Eighth Amendment should be guided by objective criteria, including (i) the gravity of the offense and the harshness of the penalty; (ii) the sentences imposed on other criminals in the same jurisdiction; and (iii) the sentences <span class="star-pagination">*876</span> imposed for commission of the same crime in other jurisdictions."</blockquote>\n<p>The punishment of life imprisonment which the jury assessed for each of the three offenses was within the statutory limit. This court must accord "substantial deference," <i>Solem,</i> supra, at 3009, to the legislature and to the sentencing court. Each of the three offenses which the defendant committed is a very serious one. Life imprisonment sentences have been imposed on other criminals in Missouri for these offenses.<sup>[3]</sup> This court does not have access to a computer system which might disclose actual sentences imposed for the same crimes in other jurisdictions. This court has examined the statutes of the nearby states of Arkansas, Illinois, Kansas, Kentucky, Oklahoma, Tennessee and Texas.</p>\n<p>With respect to the offense of robbery in the first degree, life imprisonment is an authorized punishment in Arkansas [Ark. Stat.Ann. §§ 41-901(1)(b), 41-2102], Kansas [Kan.Stat.Ann. §§ 21-3427, 21-4501], Oklahoma [Okla.Stat.Ann. tit. 21, § 801], Tennessee [Tenn.Code Ann. § 39-2-501], and Texas [Tex.Penal Code Ann. §§ 12.32, 29.03]. In Illinois the maximum punishment for that offense is 30 years imprisonment [Ill.Rev.Stat. ch. 38, §§ 18-2, 1005-8-1(a)(3)], and in Kentucky the maximum punishment is 20 years [Ky.Rev.Stat.Ann. §§ 515.020, 532.060(2)(b)].</p>\n<p>Although each of those seven states has a statute dealing with the type of assault involved here, none authorizes life imprisonment for that offense. The respective maximum punishments for that offense in those states are: Arkansas\x9720 years [Ark. Stat.Ann. §§ 41-901(1)(c), 41-1601], Illinois \x975 years [Ill.Rev.Stat. ch. 38, §§ 12-4, 1005-8-1(a)(6)], Kansas\x9720 years [Kan. Stat.Ann. §§ 21-3414, 21-4501(c)], Kentucky\x9720 years [Ky.Rev.Stat.Ann. §§ 508.010, 532.060(2)(b)], Oklahoma\x9710 years [Okla.Stat.Ann. tit. 21, § 645], Tennessee\x97 10 years [Tenn.Code Ann. § 39-2-101], Texas\x9710 years [Tex.Penal Code Ann §§ 12.34(a), 22.02].</p>\n<p>The offense of armed criminal action is not defined by statute in Arkansas, Kansas, Kentucky and Texas. In Illinois the maximum punishment for that offense is 15 years [Ill.Rev.Stat. ch. 38, § 33A-1 et seq.]. In Oklahoma, for the first such offense, the maximum is 10 years [Okla.Stat. Ann. tit. 21, § 1287] and in Tennessee the maximum is 5 years [Tenn.Code Ann. § 39-6-1710].</p>\n<p>This court has no jurisdiction to declare unconstitutional any of the Missouri statutes authorizing the punishment of life imprisonment for each of the three instant offenses. Defendant has not attacked the constitutionality of any of those statutes. This court does not believe that the "proportionality analysis" enunciated in <i>Solem</i> requires this court to find that a life sentence for armed criminal action is disproportionate merely because some other states, which define the offense, do not authorize that punishment or merely because the offense is not defined as such in other states.</p>\n<p>This court holds that the sentence imposed for each of the three offenses was proportionate and was within constitutional limits. This court further holds that the ordering of the sentences to run consecutively did not constitute an infliction of cruel and unusual punishment. Defendant\'s third point has no merit.</p>\n<p>Defendant\'s fourth point is that the evidence was insufficient to support the verdict, in that the testimony of state\'s witnesses Moon and Francis, identifying defendant as the robber, "was tainted by unreliable procedures attending their out-of-court <span class="star-pagination">*877</span> identification of defendant." At the time of the offense both Freeman and Moon had an adequate opportunity to observe and identify defendant. Indeed Moon, whom defendant called by name, had known defendant for many years. Defendant\'s fourth point has no merit.</p>\n<p>The judgment is affirmed.</p>\n<p>PREWITT, C.J., CROW, P.J., and MAUS, J., concur.</p>\n<h2>NOTES</h2>\n<p>[1]  Unless otherwise indicated, all references to statutes are to RSMo 1978, V.A.M.S., and all references to rules are to Missouri Rules of Court, V.A.M.R.</p>\n<p>[2]  In <i>Missouri v. Hunter,</i> 459 U.S. 359, 103 S.Ct. 673, 74 L.Ed.2d 535 (1983), the Supreme Court held that the Double Jeopardy Clause does not prohibit conviction and sentence of a criminal defendant in a single trial on both a charge of armed criminal action and a charge of first degree robbery, the underlying felony.</p>\n<p>[3]  In <i>State v. Kirksey,</i> 647 S.W.2d 799 (Mo. banc 1983), a life sentence for armed criminal action was affirmed. In the following cases, life sentences for assault were affirmed: <i>State v. Hayes,</i> 624 S.W.2d 16 (Mo.1981); <i>State v. Barmann,</i> 689 S.W.2d 758 (Mo.App.1985); <i>Davis v. State,</i> 657 S.W.2d 677 (Mo.App.1983); <i>State v. Mayhue,</i> 653 S.W.2d 227 (Mo.App.1983). In the following cases, life sentences for first degree robbery were affirmed: <i>State v. Hayes,</i> supra, <i>State v. Rider,</i> 664 S.W.2d 617 (Mo.App.1984); <i>State v. Johnson,</i> 603 S.W.2d 683 (Mo.App.1980); <i>State v. Battle,</i> 588 S.W.2d 65 (Mo.App.1979); <i>State v. Rapheld,</i> 587 S.W.2d 881 (Mo.App.1979).</p>\n\n</div>'
#
#
# """ll v. State,</i> 270 Ind. 55, 383 N.E.2d 309, 313[6] (1978); <i>Anderson v. State,</i> 267 Ind. 289, 370 N.E.2d 318, 320[2] (1977); <i>Block v. State,</i> 95 Nev. 933, 604 P.2d 338, 340[2] (1979); <i>Stowe v. State,</i> 590 P.2d 679, 682[1] (Okla.Crim.1979); <i>Felts v. Oklahoma,</i> 588 P.2d 572, 576[3] (Okla.Crim.1978). See 98 A.L.R.3d 13, 61, § 13.</p>\n<p>Several hearings were held prior to the trial itself which was held on May 17, 1984. At all of these hearings the prosecutor appeared and the defendant appeared in person and by his attorney, Daniel A. Beatty, an assistant public defender.</p>\n<p>On February 9, 1984, a hearing was held which was prompted by a letter which defendant sent to the court. Defendant informed the court that he did not feel that he was being represented properly and indicated he had had difficulty getting in contact with Mr. Beatty. Mr. Beatty informed the court that he was on active duty with the Navy in Seattle, Washington, when the defendant attempted to contact him. Mr. Beatty also said, "There was a letter from [defendant] regarding possible self-representation, <i>which I understand he did not want to do at this time.</i> However, it is also my understanding that he is trying to hire his own lawyer but has not been able to do so. His family may still be working on it." At the conclusion of that hearing defendant told the court that he wanted "to keep his attorney."</p>\n<p>On March 10, 1984, a hearing was held. At that time the court ordered the case, at defendant\'s request, sent back to Scott County, from which defendant earlier had taken a change of venue. There was no mention of any dissatisfaction with attorney Beatty.</p>\n<p>On April 26, 1984, a hearing was held. Attorney Beatty stated to the court, "[Defendant] has instructed me to file a motion to withdraw. <i>He desires to retain his own counsel or to represent himself.</i> I don\'t <span class="star-pagination">*872</span> think he is satisfied with the way the case is going at this point."</p>\n<p>The court asked the defendant what the problem was and defendant stated, "Mr. Beatty and I have not had communications I feel I am entitled to.... I have requested certain things of Mr. Beatty I would appreciate for him to do for me. Mr. Beatty told me he had done them, and when everything comes to a certain point, they have not been done."</p>\n<p>The court asked the defendant, "What is your plan?" The defendant answered that he had been writing "to the U.S. District Court and Bar Association and <i>trying to see if they will send me a lawyer."</i> Defendant also said that he had been writing the NAACP. The court asked the defendant if he was going to hire an attorney and the defendant responded, "I didn\'t tell Mr. Beatty I was going to hire an attorney. I was telling Mr. Beatty <i>I was going to see what would happen.</i>"</p>\n<p>There was some discussion of obtaining another public defender for defendant but a representative of the public defender\'s office said, "There is just no provision for doing that."</p>\n<p>The court asked the defendant what it was which he had asked attorney Beatty to do and which Beatty had not done. The defendant mentioned that he had requested Beatty to obtain a transcript of the preliminary hearing. Mr. Beatty stated he did not recall that request and that the hearing was not transcribed.</p>\n<p>The following then occurred:</p>\n<blockquote>"THE COURT: Mr. Freeman, <i>I am not going to let you represent yourself,</i> b"""
