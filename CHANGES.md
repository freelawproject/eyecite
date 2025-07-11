# Change Log

## Upcoming

The following changes are not yet released, but are code complete:

Features:
-

Changes:
- Handle sequential citations (in close proximity) better

Fixes:
- Modifies rendering of AhocorasickTokenizer parameter in API docs II

## Current

**2.7.6 - 2025-06-25**

Features:
-

Changes:
- Move dependency management to uv.
  This shouldn’t have any visible impact to users, except from a few small metadata changes.

Fixes:
- Fixes rendering of AhocorasickTokenizer parameter definition in API docs #279
- Fix for parsing defendant name causing crash

**2.7.5 - 2025-05-22**

Features:
-

Changes:
- Add method to remove tags from markup to avoid diffing bug

Fixes:
-

**2.7.4 - 2025-05-15**

Features:
-

Changes:
-

Fixes:
- Fixes court detection with court/date parenthetical contains the month and day, e.g., `(C.D. Cal. Feb. 9, 2015)` #242
- Fixes over reference filtering in markup text

**2.7.2 - 2025-05-14**

Features:
- Add another short form style to short cite regex #252

Changes:
- Small tweak to placeholder citations regexes and added a few more known reps #256
- Tweak to plain text processing of supra tokens #258

Fixes:
- Add fix for reference citation filtering out bad matches #251
- Fix for hyperscan bug and whitespace bug #250
- Fix boundary scanning bug to not remove parts of words #258
- A citation in a parenthetical should not emit the warning "Unknown overlap case" #259

**2.7.1 - 2025-04-25**

Features:
- Add a `xml` clean function useful for Harvard XML

Changes:
- Now each citation saves a reference to the associated Document object. This
  is needed to create the SpanUpdater for annotation
- Add optional `offset_updater` argument to `annotate_citations`, to reuse
`plain_to_markup` SpanUpdater used when finding citations for markup sources

**2.7.0 - 2025-04-24**

Minor version update because `get_citations` Now performs text cleanup internally,
which will require users to update any code using `eyecite`

Features:
- Introduced `Document` object to encapsulate plain text, markup text, span updates, tokens, and citation strings.
- Simplifies citation processing by reducing parameter passing and improving maintainability (hopefully).
- Should enable more complex html parsing.
- Adds support for years preceding citations
- Improve markup plaintiff extraction
- Adds placeholder token/regex for placeholder citations

Changes:
- Moved text cleaning logic into `get_citations` for simpler call with markup
- Simplifies `is_parallel` logic
- moves `is_parallel_citation` to `FullCaseCitation`
- remove add defendant for separate html and plain text processing

Fixes:
- Fixes run on extra regex captures by capping at semicolons
- Prefer the other full citation on overlap with nominative reporter citations #237
- Update `maybe_balance_style_tags` to account for party names and intro words
  inside the style tag #231
- updated `.github/workflows/tests.yml` to use the latest ubuntu image


## Past

**2.6.11 - 2025-02-20**

Fixes:
- Add regex escapig to `utils.maybe_balance_style_tags`

**2.6.10 - 2025-02-20**

Features:
- Adds support to correct citation page

**2.6.9 - 2025-02-20**

Features:
- Adds helper function span_with_pincite() to get full citation with pin cite

Changes:
- None

Fixes:
- Strengthens error handling during the loading of the cached Hyperscan database. This ensures that an invalid cache triggers a rebuild.


**2.6.8 - 2025-02-19**

Fixes:
- Properly name loggers and demote errors to warnings [#222](https://github.com/freelawproject/eyecite/pull/222)

**2.6.7 - 2025-02-18**

Features:

- Update regexes to allow for square brackets common in NY and California [#219](https://github.com/freelawproject/eyecite/pull/219)
- Cleanup plaintiff/defendant names with parentheses/whitespace. See #219
- Update regexes, helpers and tests.py


**2.6.6 - 2025-02-18**

Features:

- Added a new optional argument `markup_text` to `get_citations`. Passing this
argument makes eyecite use a new extractor `find_reference_citations_from_markup`
which uses HTML/XML style tags to find references. [#203](https://github.com/freelawproject/eyecite/pull/203).
- Updated the benchmark to use the new argument to `get_citations`. See #203.
- Added antecedent_guess to FullCaseCitation.Metadata via `PRE_FULL_CITATION_REGEX`. See #203.
- Add workflow to check for new entries in CHANGES.md file [#217](https://github.com/freelawproject/eyecite/pull/217)

Fixes:
- Fixed variant regexes for ShortCites [#214](https://github.com/freelawproject/eyecite/pull/214).
- Added an optional space to antecedent regexes [#211](https://github.com/freelawproject/eyecite/pull/211).
- Corrected full span calculations. See [#205](https://github.com/freelawproject/eyecite/pull/205) and #203.


**2.6.5 - 2025-01-28**

Features:

- Add ReferenceCitation model and associated logic

Fixes:

- Fix court string matching with whitespace
- Fix court name issues

**2.6.4 - 2024-06-03**

Fixes:

- Bump eyecite to for InvalidError/hyperscan bug

**2.6.3 - 2024-04-09**

Fixes:

- Addresses compatibility issues identified with the current version of hyperscan(0.7.7).

**2.6.2 - 2024-03-19**

Fixes:

- Adds missing closing parentheses to the corrected_citation_full method in FullCaseCitation and FullJournalCitation classes.

**2.6.1 - 2024-02-29**

Fixes:

 - Improves reliability of utils.hash_sha256() by providing a default function to handle non-serializable objects.

**2.6.0 - 2024-02-07**

Features:

 - Removes Python 3.8 and 3.9 support
 - Adds Python 3.12 support

Changes:

- The hashing and equality behavior of `CitationBase` objects has changed in subtle ways in order to conform with user intuitions and define previously ill-defined behavior. Most importantly, to compare two `eyecite` objects going forward, simply use the native Python syntax `citation1 == citation2`. You can also take the hash of each object and compare that with identical results: `hash(citation1) == hash(citation2)`. This broad change has several more specific implications:
  - Citation objects that are created from text with a normalized/corrected reporter are now treated as equal to objects created from text *without* a normalized/corrected reporter (e.g., `1 U.S. 1` versus `1 U. S. 1` are now treated as equal)
  - Citation objects that are created from text with a nominative reporter are now treated as equal to objects created from text *without* a nominative reporter (e.g., `5 U.S. 137` versus `5 U.S. (1 Cranch) 137` are now treated as equal)
  - Any `IdCitation` and `UnknownCitation` object will always be treated as unequal to any other object
  - Previously, `CitationBase` objects had a `comparison_hash()` method. This method was never intended to be a "public" method and has been removed.
  - Citation hashes are now stable and reproducible across module loadings of `eyecite`, as we are now using `hashlib.sha256` under the hood. However, note that due to `hashlib`'s implementation details, hashes with NOT be consistent across 32 and 64 machines.

- As noted in 2.3.3 (2021-03-23), the old `NonopinionCitation` class was renamed `UnknownCitation` to better reflect its purpose. Support for the old class name has now been completely deprecated. This change is purely semantic -- there is no change in how these citations are handled.

Fixes:

 - Update dependencies for reporters-db

**2.5.5 - 2024-01-10**

Yanked.

**2.5.4 - 2024-01-10**

Yanked.

**2.5.3 - 2024-01-10**

Yanked.

**2.5.2 - 2023-05-23**

Fixes:
 - Update dependencies and add Python 3.11 support.

**2.5.1 - 2023-03-09**

Fixes:
 - Fix & update dependencies


**2.5.0 - 2023-01-20**

Features:
 - Citations now have a `full_span` property that returns the start and end indexes for the full citation, including any pre- or post-citation attributes.


**2.4.0 - 2022-07-22**

Features:
 - Unnumbered citations like "22 U.S. ___" are now identified by eyecite. They will have a page attribute set to `None`, but otherwise work just like everything else.

**2.3.3 - 2021-03-23**

Features:
- None

Changes:
- The `NonopinionCitation` class has been renamed `UnknownCitation` to better reflect its purpose. This change is purely semantic -- there is no change in how these citations are handled.
- Updates to courts-db

Fixes:
- Initial support for finding short cites with non-standard regexes, including fixing short cite extraction for `Mich.`, `N.Y.2d` and `Pa.`.


**2.3.2 - 2021-03-23**

Yanked.

**2.3.1 - 2021-03-23**

Yanked.

**2.3.0 - 2021-09-23**

Features:
 - Greatly improved documentation
 - Autogenerated documentation

Changes:
 - This version lands one more iteration of the APIs to make them more consistent. Sorry. Hopefully this will be the last of its kind for a while. The need for these changes became obvious when we began generating documentation. The changes are all in name only, not in functionality. So: 1) the `annotate` function is renamed as `annotate_citations`; 2) The `find_citations` module has been renamed `find` (so, do `from eyecite.find import get_citations` instead of `from eyecite.find_citations import get_citations`); 3) The `cleaners` module is now named `clean`; and 4) The `clean_text` function has been moved from `utils` to `clean` (so, do `from eyecite.clean import clean_text` instead of `from eyecite.utils import clean_text`).


**2.2.0 - 2021-06-04**

Features:
 - Adds support for parsing statutes and journals and includes new json files with associated regular expressions and data. This introduces `FullLawCitation` and `FullJournalCitation`.
 - Id and Supra citations now have a `metadata.parenethical` attribute, to mirror `FullCaseCitation` objects and make them more useful. [PR #71][71]
 - A new tool, `dump_citations()` is added to inspect extracted citations.
 - The readme is updated with a new tutorial.
 - We now use page-based heuristics while looking up the citation that a pin cite refers to. For example, if an opinion says:

    > 1 U.S. 200. blah blah. 2 We Missed This 20. blah blah. Id. at 22.

    We might miss the second citation for whatever reason. The pin cite refers to the second citation, not the first, and you can be sure of that because the first citation begins on page 200 and the pin cite references page 22. When resolving the pin cite, we will no longer link it up to the first citation.

    Similarly, an analysis of the Caselaw Access Project's dataset indicates that all but the longest ~300 cases are shorter than 150 pages, so we also now ignore pin cites that don't make sense according to that heuristic. For example, this (made up) pin cite is also likely wrong because it's overwhelmingly unlikely that `1 U.S. 200` is 632 pages long:

    > 1 U.S. 200 blah blah 1 U.S. 832

    The longest case in the Caselaw Access Project collection is [United States v. Philip Morris USA, Inc](https://cite.case.law/f-supp-2d/449/1/), at 986 pages, in case you were wondering. Figures.

    [Issue #74][74], [PR #79][79].

Changes:
 - To harmonize the API while adding laws and journals, a large API reorganization was completed. See [PR 64][64] for discussion. Here are the details:
    - All of the metdata that we capture before and after each citation is now organized into a `metadata` object. Thus, if they make sense for the citation type, all of the following attributes are now in `some_citation.metadata`: `publisher`, `day`, `month`, `antecedent_guess`, `court`, `extra`, `defendant`, `plaintiff`, `parenthetical`, `pin_cite`.
    - The `canonical_reporter` attribute is removed from citation objects. It wasn't used much and was duplicated in `edition_guess.reporter.short_name`. Where applicable, use that instead going forward.
     - The `reporter_found` attribute is removed from citation objects in favor of `groups['reporter']`.
     - Similarly, the `volume` and `page` attributes are removed from citation objects in favor of `groups["volume"]`and `groups["page"]`.
     - The `reporter` attribute has been removed from citations and replaced with the `corrected_reporter()` method.
     - Similarly, the `base_citation()` method has been renamed as `corrected_citation()`, and the `formatted()` method has been renamed as `corrected_citation_full()`.
     - The `do_defendant` and `do_post_citation` arguments to `get_citations` have been removed. They're fast enough to just always do. No need to think about these further.\
     - The `resolve_fullcase_citation` parameter in the `resolve_citations` function has been renamed to `resolve_full_citation`.

Fixes:
 - Support for reporter citations with `volume=None` is added. Some reporters don't use volumes, for example, "Bankr. L. Rep. (CCH) P12,345".
 - Upgrades courts-db subdependency to latest that provides lazy-loading. This should speed up imports of eyecite.

[64]: https://github.com/freelawproject/eyecite/pull/64
[71]: https://github.com/freelawproject/eyecite/pull/71
[74]: https://github.com/freelawproject/eyecite/issues/74
[79]: https://github.com/freelawproject/eyecite/pull/79


**2.1.0 - 2021-05-13**

Features:
 - Adds support for resolving id, supra, and short form citations into
   their targets. See readme for details on "Resolving Citations."
 - Pin cites are now matched across more citation types.
 - Summarizing parentheticals are now included in the match.

Changes:
 - The shape of various citation objects has changed to better handle pages and
   pin citations. See #61 for details.

Fixes:
 - Fixes crashing errors on some partial supra, id, and short form citations.
 - Fixes unbalanced tags created by annotation.
 - Fixes year parsing to move away from `isdigit`, which can capture
   unicode superscript numbers like "123 U.S. 456 (196⁴)"
 - Allow years all the way back to 1600 instead of 1754. Anybody got a citation
   from before then?
 - Page number matching is tightened to be much more strict about how it
   matches Roman numerals. This change will prevent some citations from being
   matched if they have extremely common Roman numerals. See #56 for a full
   discussion.

**2.0.2** - Adds missing dependency to toml file, nukes setup.py and
requirements.txt. We're now fully in the poetry world.

**2.0.1** - Major rewrite to efficiently build and use hundreds of regular
expressions to parse the text, and to use merging algorithms to annotate it.
These changes bring better speed, accuracy, and flexibility to the library.

**2.0.0** - Broken, bad release process.

**1.1.0** - Standardize the `__eq__()` and `__hash__()` methods and remove the
unused fuzzy_hash() method.

**0.0.1** - Initial release with CL-compatible API.

**0.0.1 to 0.0.5** - Continuous deployment debugging
