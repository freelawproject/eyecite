import os
from copy import copy
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

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
            # Test with month/day in court parenthetical
            ('Commonwealth v. Muniz, 164 A.3d 1189 (Pa. Feb. 9, 2017)',
             [case_citation(page='1189', reporter='A.3d', volume='164', year=2017,
                            metadata={'plaintiff': 'Commonwealth',
                                      'defendant': 'Muniz',
                                      'month': 'Feb.',
                                      'day': '9',
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
            # Test short form citation with at p. format
            ('174 Cal.App.2d at p. 651',
             [case_citation(volume='174', page='651', reporter='Cal.App.2d', short=True,
                            metadata={'pin_cite': '651'})]),
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
            ('Rogers v Rogers (63 NY2d 582 [1984])',
             [case_citation(volume='63', reporter='NY2d', page='582',
                            metadata={'plaintiff': 'Rogers',
                                      'defendant': 'Rogers',
                                      'year': '1984'})]
             ),
            # test citation always breaks at ; even at year
            ('(1963); Reece v. State of Washington, 310 F.2d 139 (1962)',
             [case_citation(volume='310', reporter='F.2d', page='139',
                            metadata={'plaintiff': 'Reece',
                                      'defendant': 'State of Washington',
                                      'year': '1962'})]
             ),
            # As seen in /107252/miranda-v-arizona/
            ('(Mo.); Bean v. State, — Nev. —, 398 P. 2d 251; ',
             [case_citation(volume='398', reporter='P. 2d', page='251',
                            metadata={'plaintiff': 'Bean',
                                      'defendant': 'State'})]
             ),
            # https://www.courtlistener.com/opinion/4439963/mark-a-twilegar/
            # Common em-dash format
            ('Hurst v. Florida, — U.S. —, 136 S.Ct. 616, 193 L.Ed.2d 504 (2016)',
             [case_citation(volume='136', reporter='S.Ct.', page='616',
                            metadata={'plaintiff': 'Hurst',
                                      'defendant': 'Florida',
                                      'year': '2016',
                                      'court': 'scotus',
                                      'extra': '193 L.Ed.2d 504'
                                      }),
              case_citation(volume='193', reporter='L.Ed.2d', page='504',
                            metadata={'plaintiff': 'Hurst',
                                      'defendant': 'Florida',
                                      'year': '2016',
                                      })
              ]
             ),
            # https://www.courtlistener.com/opinion/9502461/balderas
            # Single underscore placeholder
            ('In Viking River Cruises v. Moriana (2022) _ U.S. _ [213 L.Ed.2d 179, 200-201] (Viking River)',
             [case_citation(volume='213', reporter='L.Ed.2d', page='179',
                            metadata={'plaintiff': 'Viking River Cruises',
                                      'defendant': 'Moriana',
                                      'year': '2022',
                                      'pin_cite': '200-201',
                                      })
              ]
             ),
            # Two underscore placeholder
            # https://www.courtlistener.com/opinion/5290606/williams
            ('decision in Epic Systems Corporation v. Lewis (2018) __ U.S. __ [138 S.Ct. 1612] (Epic Systems)',
             [case_citation(volume='138', reporter='S.Ct.', page='1612',
                            metadata={'plaintiff': 'Epic Systems Corporation',
                                      'defendant': 'Lewis',
                                      'year': '2018',
                                      'court': 'scotus',
                                      })
              ]
             ),
            # https://www.courtlistener.com/opinion/9780755/touchard
            # test complicated multiple citations with placeholders
            ('speech.” Houston Cmty. Coll. Sys. v. Wilson, ---- U.S. ----, '
             '142 S. Ct. 1253, 1259, ---- L. Ed. 2d ---- (2022) (emphasis added) '
             '(quoting Nieves v. Bartlett, ---- U.S. ----, 139 S. Ct. 1715, '
             '1722, 204 L. Ed. 2d 1 (2019);',
             [case_citation(volume='142', reporter='S. Ct.', page='1253',
                            metadata={'plaintiff': 'Sys.',
                                      'defendant': 'Wilson',
                                      'year': '2022',
                                      'pin_cite': '1259',
                                      'court': 'scotus',
                                      'extra': '---- L. Ed. 2d ----',
                                      'parenthetical': 'emphasis added',
                                      }),
              case_citation(volume='139', reporter='S. Ct.', page='1715',
                            metadata={'plaintiff': 'Nieves',
                                      'defendant': 'Bartlett',
                                      'year': '2019',
                                      'extra': '204 L. Ed. 2d 1',
                                      'court': 'scotus',
                                      'pin_cite': '1722',
                                      }),
              case_citation(volume='204', reporter='L. Ed. 2d', page='1',
                            metadata={'plaintiff': 'Nieves',
                                      'defendant': 'Bartlett',
                                      'year': '2019',
                                      })
              ]
             ),
            # test lower case sentence
            ('curiams. Spano v. People of State of New York, 360 U.S. 315',
             [case_citation(volume='360', reporter='U.S.', page='315',
                            metadata={'plaintiff': 'Spano',
                                      'defendant': 'People of State of New York'})]
             ),
            # Test capitalized word
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
              reference_citation('Amick at 795', metadata={'plaintiff': 'Amick', 'pin_cite': 'at 795'})]),
            # Test reference citation
            ('Foo v. Bar 1 U.S. 12, 347-348. something something, In Foo at 62, we see that',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'}),
              reference_citation('Foo at 62', metadata={'plaintiff': 'Foo', 'pin_cite': 'at 62'})]),
            ('Foo v. United States 1 U.S. 12, 347-348. something something ... the United States at 1776 we see that and Foo at 62',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'United States',
                                      'pin_cite': '347-348'}),
              reference_citation('Foo at 62', metadata={'plaintiff': 'Foo', 'pin_cite': 'at 62'})]),
            # Test that reference citation must occur after full case citation
            ('In Foo at 62 we see that, Foo v. Bar 1 U.S. 12, 347-348. something something,',
             [case_citation(page='12',
                            metadata={'plaintiff': 'Foo',
                                      'defendant': 'Bar',
                                      'pin_cite': '347-348'})]),
            # Test reference against defendant name
            ('In re Foo 1 Mass. 12, 347-348. something something, in Foo at 62, we see that, ',
             [case_citation(page='12', reporter="Mass.", volume="1",
                            metadata={'defendant': 'Foo', 'pin_cite': '347-348'}),
              reference_citation('Foo at 62',
                                 metadata={'defendant': 'Foo',
                                           "pin_cite": "at 62"})]),
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
                                 metadata={'defendant': 'Mancari', "pin_cite": "at 665"})]),
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
            ("Corp. v. Nature's Farm Prods., No. 99 Civ. 9404 (SHS), 2000 U.S. Dist. LEXIS 12335 (S.D.N.Y. Aug. 25, 2000)",
             [case_citation(
                 volume='2000',
                 reporter='U.S. Dist. LEXIS',
                 page='12335',
                 year=2000,
                 metadata={'plaintiff': "Corp.", 'defendant': "Nature's Farm Prods., No. 99 Civ. 9404 (SHS)", "month": "Aug.", "day": "25", "court": "nysd"})
              ],),
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
            # extract no page citations
            ("\n 576 U.S. ___, 13",
             [case_citation(volume='576', reporter='U.S.', page=None, metadata={'pin_cite': '13', "court": 'scotus'})],
             {"clean_steps": ["all_whitespace"]},
             ),
            # test handling zero width whitespace
            ("Shady Grove Farms \u200bv Goldsmith Seeds 1 U.S. 1",
             [case_citation(metadata={'defendant': 'Goldsmith Seeds', "plaintiff": 'Shady Grove Farms'})],
             {"clean_steps": ["all_whitespace"]},
             ),
            # Test unprintable characters # /recap-documents/429621284"
            ("Shady Grove Farms v Goldsmith Seeds 1 U.S. 1  \x08*\x07\x07\u038bþİ\u038b\u202cڋ\u202a-\x14V\u202c\u202c",
             [case_citation(metadata={'defendant': 'Goldsmith Seeds', "plaintiff": 'Shady Grove Farms'})],
             {"clean_steps": ["all_whitespace"]},
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
            ]),
            # ignore bad reference matching in plain text
            ("In Foo v. Bar 1 U.S. 1, ... yadda yadda yadda the case of Foo v. Bar, supra, was affirmed", [
                case_citation(metadata={'plaintiff': 'Foo', "defendant": "Bar",
                                        "court": "scotus"}),
                supra_citation("supra.", metadata={'antecedent_guess': "Bar"})
            ]),
            # Dont make second foo a reference citation
            ('<p>In <i>Foo</i> v. <i>Bar,</i> 1 U.S. 1, ... yadda yadda yadda the case of <i>Foo</i> v. <i>Bar, supra</i><i>,</i> was affirmed.</p>',
             [
                case_citation(metadata={'plaintiff': 'Foo', "defendant": "Bar", "court": "scotus"}),
                supra_citation("supra.", metadata={'antecedent_guess': "Bar"})
             ], {'clean_steps': ['html', 'inline_whitespace']}),
            ("""<em>Grant </em>v. <em>Esquire, Inc. </em>(S.D.N.Y. 1973) 367 F.Supp. 876, 879.) ...
             <em>Grant </em>v. <em>Esquire, Inc., supra, </em>316 F.Supp. at 884.)</p>
             <p id="b883-5">III. </p> """,
             [
                 case_citation(page='876', reporter='F.Supp.', volume='367',
                               metadata={'plaintiff': 'Grant', "defendant": "Esquire, Inc.", "pin_cite": "879"}),
                 case_citation(volume="316", reporter="F.Supp.", page="884", short=True,
                               metadata={'antecedent_guess': "Esquire, Inc., supra", "pin_cite": "884"}),
             ], {'clean_steps': ['html', 'inline_whitespace']}),
            ("""However, as we explained in Kaiser Foundation, supra, 13 Cal.App.5th at 1146""",
             [
                 case_citation(page='1146', reporter='Cal.App.5th', volume='13',
                               short=True,
                               metadata={"pin_cite": "1146",
                                         "antecedent_guess": "Kaiser Foundation"}),
              ]),
            ("Angelopoulos v. Keystone Orthopedic Specialists, S.C., Wachn, LCC, 2015 WL 2375225, at p. *4. yadda yadda yadda... Angelopoulos p. *4;",
             [
                 case_citation(volume="2015", reporter="WL", page="2375225",
                               metadata={"plaintiff": "Angelopoulos",
                                         "defendant": "Keystone Orthopedic Specialists, S.C., Wachn, LCC",
                                         "pin_cite": "at p. *4"}),
                 reference_citation("Angelopoulos at 4",
                                    metadata={"plaintiff": "Angelopoulos", "pin_cite": "p. *4"}),
             ]),
            # properly not remove An from the start of the final word
            ("Angelopoulos v. Keystone Orthopedic Specialists, S.C., Wachn, LCC, 2015 WL 2375225",
             [case_citation(volume="2015", reporter="WL", page="2375225",
                            metadata={"plaintiff": "Angelopoulos", "defendant": "Keystone Orthopedic Specialists, S.C., Wachn, LCC"})]
             ),
            ("See <em>Bivens </em>v. <em>Six Unknown Fed. Narcotics Agents, </em>403 U. S. 388 (1971). "
             "The legal issue there was whether a <em>Bivens </em> at 122, action can be employed...",
             [case_citation(volume="403", reporter="U. S.", page="388",
                            metadata={"plaintiff": "Bivens",
                                      "defendant": "Six Unknown Fed. Narcotics Agents",
                                      "court": "scotus",
                                      "year": "1971"},
                            ),
              reference_citation("Bivens", metadata={"plaintiff": "Bivens", "pin_cite": "at 122"})],
             {'clean_steps': ['html', 'inline_whitespace']}),
            # Fix for index error when searching for case name
            ("<p>State v. Luna-Benitez (S53965). Alternative writ issued, dismissed, 342 Or 255</p>",
            [case_citation(volume="342", reporter="Or", page="255")],
            {'clean_steps': ['html', 'inline_whitespace']})
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
                msg=(
                    f"is_date_in_reporter({edition[0]}, {year}) != {expected}\n"
                    "It's equal to: {date_in_reporter}"
                ),
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
            "Corp. v. Nature's Farm Prods., No. 99 Civ. 9404 (SHS), 2000 U.S. Dist. LEXIS 12335 (S.D.N.Y. Aug. 25, 2000)",
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
                any(isinstance(cite, ReferenceCitation) for cite in citations)
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
            (
                "Craig v. Harrah, ___ Nev. ___ [201 P.2d 1081]. (",
                [
                    case_citation(
                        page="1081",
                        volume="201",
                        reporter="P.2d",
                        short=False,
                        metadata={
                            "plaintiff": "Craig",
                            "defendant": "Harrah",
                        },
                    )
                ],
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
                        metadata={
                            "plaintiff": "Nobelman",
                            "pin_cite": "at 332",
                        },
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
            # handle page numbers interfering in short cases
            (
                """immunity outlined by the Supreme Court in <em>Saucier, </em><page-number citation-index=\"1\" label=\"1029\">*1029</page-number>533 U.S. at 201, 121 S.Ct. 2151""",
                [
                    case_citation(
                        page="201",
                        volume="533",
                        reporter="U.S.",
                        short=True,
                        metadata={
                            "antecedent_guess": "Saucier",
                            "pin_cite": "201",
                            "court": "scotus",
                        },
                    ),
                    case_citation(
                        page="2151",
                        volume="121",
                        reporter="S.Ct.",
                        short=False,
                        metadata={
                            "plaintiff": None,
                            "defendant": "Saucier",
                            "court": "scotus",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # handle bad html
            (
                """this Court.\n  <em>\n   Holm; In Re Carroll’s Estate\n  </em>\n  (1921), 59 Mont. 403, 413.""",
                [
                    case_citation(
                        page="403",
                        volume="59",
                        reporter="Mont.",
                        short=False,
                        metadata={
                            "plaintiff": None,
                            "defendant": "Carroll’s Estate",
                            "pin_cite": "413",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # handle bad html in antecedent guesses
            (
                """party.”
              <em>
               Anderson, 477
              </em>
              U.S. at 248""",
                [
                    case_citation(
                        volume="477",
                        reporter="U.S.",
                        page="248",
                        short=True,
                        metadata={
                            "antecedent_guess": "Anderson",
                            "court": "scotus",
                            "pin_cite": "248",
                        },
                    )
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # deal with merged citation and case name html
            (
                """and <em>In re Spellman, 4 </em>A.D.2d 215 (N.Y.App.Div.1957). <em>""",
                [
                    case_citation(
                        volume="4",
                        reporter="A.D.2d",
                        page="215",
                        short=False,
                        metadata={
                            "plaintiff": None,
                            "defendant": "Spellman",
                        },
                    )
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
            (
                'the trial court.â€™â€ (quoting Ohree v. Commonwealth, </pre><span class="citation no-link"><span class="volume">26</span> <span class="reporter">Va. App.</span> <span class="page">299</span>',
                [
                    case_citation(
                        page="299",
                        volume="26",
                        reporter="Va. App.",
                        metadata={
                            "plaintiff": "Ohree",
                            "defendant": "Commonwealth",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Can we ignore the random (1) or (2)
            (
                'See id.; see also Harper v. State, </pre><span class="citation no-link">286 Ga. 216</span><pre class="inline">, 218\n(1) (686 SE2d 786) (2009)',
                [
                    case_citation(
                        page="216",
                        volume="286",
                        reporter="Ga.",
                        metadata={
                            "plaintiff": "Harper",
                            "defendant": "State",
                        },
                    ),
                    case_citation(
                        page="786",
                        volume="686",
                        reporter="SE2d",
                        metadata={
                            "plaintiff": "Harper",
                            "defendant": "State",
                            "extra": ")",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
            # Can we parse ex. rel.
            (
                """\n\nLynch v. State ex rel. Killebrew, 179 Tenn. 339""",
                [
                    case_citation(
                        page="339",
                        volume="179",
                        reporter="Tenn.",
                        short=False,
                        metadata={
                            "plaintiff": "Lynch",
                            "defendant": "State ex rel. Killebrew",
                        },
                    ),
                ],
                {"clean_steps": ["html", "all_whitespace"]},
            ),
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

    @patch("eyecite.helpers.logger.warning")
    def test_citation_in_parenthetical_does_not_emit_warning(self, mock_warn):
        """
        These two citations are overlapping, but they are not parallel citations. No
        warning should be emitted.
        """
        text = "Gotthelf v. Toyota Motor Sales, U.S.A., Inc., 525 F. App’x 94, 103 n.15 (3d Cir. 2013) (quoting Iqbal, 556 U.S. at 686-87)."
        citations = get_citations(text)
        self.assertEqual(len(citations), 2)
        mock_warn.assert_not_called()
