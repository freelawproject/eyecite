eyecite
==========

eyecite is an open source tool for extracting legal citations from text. It is used, among other things, to annotate millions of legal documents in the collections of `CourtListener <https://www.courtlistener.com/>`_ and the `Caselaw Access Project <https://case.law/>`_.

eyecite recognizes a wide variety of citations commonly appearing in American legal decisions, including:

* full case: ``Bush v. Gore, 531 U.S. 98, 99-100 (2000)``
* short case: ``531 U.S., at 99``
* statutory: ``Mass. Gen. Laws ch. 1, § 2``
* law journal: ``1 Minn. L. Rev. 1``
* supra: ``Bush, supra, at 100``
* id.: ``Id., at 101``

You can see all of the citation patterns eyecite looks for over in `reporters_db <https://github.com/freelawproject/reporters-db>`_.

All contributors, corrections, and additions are welcome!

Background
==========
This project is the culmination of `years <https://free.law/2012/05/11/building-a-citator-on-courtlistener/>`_ `of <https://free.law/2015/11/30/our-new-citation-finder/>`_ `work <https://free.law/2020/03/05/citation-data-gets-richer/>`_ to build a citator within CourtListener. This project represents the next step in that development: decoupling the parsing logic and exposing it for third-party use as a standalone Python package.

Since eyecite was factored out from the CourtListener codebase into a standalone package, it has been developed in collaboration with the Caselaw Access Project.

Contributions & Support
=======================

Please see the issues list on Github for things we need, or start a conversation if you have questions or need support. 

If you are fixing bugs or adding features, before you make your first contribution, we'll need a signed contributor license agreement. See the template in the root of the repo for how to get that taken care of.


Quickstart
==========

Install eyecite::

    pip install eyecite


Here's a short example of extracting citations and their metadata from text::

    from eyecite import get_citations

    text = """
        Mass. Gen. Laws ch. 1, § 2 (West 1999) (barring ...).
        Foo v. Bar, 1 U.S. 2, 3-4 (1999) (overruling ...).
        Id. at 3.
        Foo, supra, at 5.
    """

    get_citations(text)

    # returns:
    [
        FullLawCitation(
            'Mass. Gen. Laws ch. 1, § 2',
            groups={'reporter': 'Mass. Gen. Laws', 'chapter': '1', 'section': '2'},
            metadata=Metadata(parenthetical='barring ...', pin_cite=None, year='1999', publisher='West', ...)
        ),
        FullCaseCitation(
            '1 U.S. 2',
            groups={'volume': '1', 'reporter': 'U.S.', 'page': '2'},
            metadata=Metadata(parenthetical='overruling ...', pin_cite='3-4', year='1999', court='scotus', plaintiff='Foo', defendant='Bar,', ...)
        ),
        IdCitation(
            'Id.',
            metadata=Metadata(pin_cite='at 3')
        ),
        SupraCitation(
            'supra,',
            metadata=Metadata(antecedent_guess='Foo', pin_cite='at 5', ...)
        )
    ]

Tutorial
==========

Here's a full-featured example of efficiently extracting citations from an HTML document and annotating them with
links to documents in a database.

.. comment

    # mock database model to make the rest of the tutorial executable, in theory:
    class MyCaseModel:
        frontend_url = '/us/1/2/'
        @classmethod
        def get_by_citation(cls, citation):
            return cls()

First our imports::

    # imports
    from eyecite import get_citations, clean_text, resolve_citations, annotate
    from eyecite.models import FullCaseCitation
    from eyecite.resolve import resolve_full_citation
    from eyecite.tokenizers import HyperscanTokenizer

We want to insert links into a piece of HTML like this::

    text = """
        <p>1 <i>U.S.</i> 2, 1 S.Ct. 2.<p>
        <p>Id.</p>
        <p>Mass. Gen.    Laws ch. 1, § 2.</p>
    """

Note that tags may overlap with
citations and whitespace may be uneven. We want "1 U.S. 2", "1 S.Ct. 2" and "Id." to all
link to the same URL fetched from our database, since they all refer to the same case.
Any cites we don't have in our database will link to "/unknown_cite"

First we'll get the text ready for cite extraction::

    cleaned_text = clean_text(text, ['html', 'all_whitespace'])

    # cleaned_text:
    # "1 U.S. 2, 1 S.Ct. 2. Id. Mass. Gen. Laws ch. 1, § 2."

Next we'll extract citations using a custom tokenizer. Unlike the default
tokenizer this uses hyperscan for much faster extraction, with a precompiled
regular expression database stored in ``.test_cache/``.
(This step depends on installation of hyperscan dependencies, as described in the "Installation" section)::

    tokenizer = HyperscanTokenizer(cache_dir=".test_cache")
    citations = get_citations(cleaned_text, tokenizer=tokenizer)

    # citations:
    # [
    #   FullCaseCitation('1 U.S. 2'),
    #   FullCaseCitation('1 S.Ct. 2'),
    #   IdCitation(),
    #   FullLawCitation('Mass. Gen. Laws ch. 1, § 2'),
    # ]

Now we want to resolve all of the extracted cites into clusters indexed by
the resource they refer to, such as a case or statute. We'll use a custom
function to resolve a given full cite to its resource, so we can return our
own MyCaseModel for citations we recognize. We'll fall back on returning
:code:`resolve_full_citation()` for citations we don't recognize.

For this simplified example, we'll assume we have a database model :code:`MyCaseModel`
so that :code:`MyCaseModel.get_by_citation()` will return the case referred to by that
citation string. In real life this might be a Django model or Elasticsearch lookup.
We'll also assume that the same case has the parallel citations
"1 U.S. 2" and "1 S. Ct. 2", so :code:`MyCaseModel.get_by_citation("1 U.S. 2")` returns
the same case as :code:`MyCaseModel.get_by_citation("1 S. Ct. 2")`.

::

    def resolve_cite(cite):
        if isinstance(cite, FullCaseCitation):
            resource = MyCaseModel.get_by_citation(cite.corrected_citation())
            if resource:
                return resource
        return resolve_full_citation(cite)

    resolutions = resolve_citations(citations, resolve_full_citation=resolve_cite)

    # resolutions:
    # {
    #   MyCaseModel('1 U.S. 2'): [FullCaseCitation('1 U.S. 2'), FullCaseCitation('1 S.Ct. 2'), IdCitation()],
    #   eyecite.models.Resource(...): [FullLawCitation('Mass. Gen. Laws ch. 1, § 2')],
    # }

(Note the use of :code:`cite.corrected_citation()`, which returns "1 S. Ct. 2" for the matched citation "1 S.Ct. 2".
reporters_db includes many variations for reporter names, so it's useful to match cases by their corrected
reporters rather than the exact string found in the text.)

Finally we can prepare annotations for each citation in our clusters. An annotation is
text to insert back into cleaned_text, like :code:`((<start offset>, <end offset>), <before text>, <after text>)`::

    annotations = []
    for resource, cites in resolutions.items():
        if isinstance(resource, MyCaseModel):
            # add link to case we were able to resolve:
            url = resource.frontend_url
        else:
            # add link to case we weren't able to resolve:
            url = f"/unknown_cite?cite={resource.citation.matched_text()}"
        for cite in cites:
            annotations.append((cite.span(), f"<a href='{url}'>", f"</a>"))

Now we have annotations ready to add to :code:`clean_text`, but we actually want to insert them into our original
:code:`text` variable with HTML formatting. We can pass :code:`source_text=text` into :code:`annotate()` to have the
annotation positions adjusted and inserted into :code:`text` using the diff-match-patch library::

    annotated_text = annotate(cleaned_text, annotations, source_text=text)

    # annotated_text:
    # """
    #     <p><a href='/us/1/2/'>1 <i>U.S.</i> 2</a>, <a href='/us/1/2/'>1 S.Ct. 2</a>.<p>
    #     <p><a href='/us/1/2/'>Id.</a></p>
    #     <p><a href='/unknown_cite?cite=Mass. Gen. Laws ch. 1, § 2'>Mass. Gen.    Laws ch. 1, § 2</a>.</p>
    # """

Ta da!

Getting Citations
=================

:code:`get_citations()`, the main executable function, takes several parameters.

1. :code:`remove_ambiguous` ==> bool, default :code:`False`: whether to remove citations
   that might refer to more than one reporter and can't be narrowed down by date.
2. :code:`tokenizer` ==> Tokenizer, default :code:`eyecite.tokenizers.default_tokenizer`: an instance of a Tokenizer object (see "Tokenizers" below)


Cleaning Input Text
===================

For a given citation text such as "... 1 Baldwin's Rep. 1 ...", eyecite expects that the text
will be "clean" before being passed to :code:`get_citation`. This means:

* Spaces will be single space characters, not multiple spaces or other whitespace.
* Quotes and hyphens will be standard quote and hyphen characters.
* No junk such as HTML tags inside the citation.

You can use :code:`clean_text` to help with this:

::

    from eyecite import clean_text, get_citations

    source_text = '<p>foo   1  U.S.  1   </p>'
    plain_text = clean_text(text, ['html', 'inline_whitespace', my_func])
    found_citations = get_citations(plain_text)

See the Annotating Citations section for how to insert links into the original text using
citations extracted from the cleaned text.

:code:`clean_text` currently accepts these values as cleaners:

1. :code:`inline_whitespace`: replace all runs of tab and space characters with a single space character
2. :code:`all_whitespace`: replace all runs of any whitespace character with a single space character
3. :code:`underscores`: remove two or more underscores, a common error in text extracted from PDFs
4. :code:`html`: remove non-visible HTML content using the lxml library
5. Custom function: any function taking a string and returning a string.


Annotating Citations
====================

For simple plain text, you can insert links to citations using the :code:`annotate` function:

::

    from eyecite import get_citations, annotate

    plain_text = 'bob lissner v. test 1 U.S. 12, 347-348 (4th Cir. 1982)'
    citations = get_citations(plain_text)
    linked_text = annotate(plain_text, [[c.span(), "<a>", "</a>"] for c in citations])

    returns:
    'bob lissner v. test <a>1 U.S. 12</a>, 347-348 (4th Cir. 1982)'

Each citation returned by get_citations keeps track of where it was found in the source text.
As a result, :code:`annotate` must be called with the *same* cleaned text used by :code:`get_citations`
to extract citations. If you do not, the offsets returned by the citation's :code:`span` method will
not align with the text, and your annotations will be in the wrong place.

If you want to clean text and then insert annotations into the original text, you can pass
the original text in as :code:`source_text`:

::

    from eyecite import get_citations, annotate, clean_text

    source_text = '<p>bob lissner v. <i>test   1 U.S.</i> 12,   347-348 (4th Cir. 1982)</p>'
    plain_text = clean_text(source_text, ['html', 'inline_whitespace'])
    citations = get_citations(plain_text)
    linked_text = annotate(plain_text, [[c.span(), "<a>", "</a>"] for c in citations], source_text=source_text)

    returns:
    '<p>bob lissner v. <i>test   <a>1 U.S.</i> 12</a>,   347-348 (4th Cir. 1982)</p>'

The above example extracts citations from :code:`plain_text` and applies them to
:code:`source_text`, using a diffing algorithm to insert annotations in the correct locations
in the original text.

Wrapping HTML Tags
------------------

Note that the above example includes mismatched HTML tags: "<a>1 U.S.</i> 12</a>".
To specify handling for unbalanced tags, use the :code:`unbalanced_tags` parameter:

* :code:`unbalanced_tags="skip"`: annotations that would result in unbalanced tags will not be inserted.
* :code:`unbalanced_tags="wrap"`: unbalanced tags will be wrapped, resulting in :code:`<a>1 U.S.</a></i><a> 12</a>`

**Important:** :code:`unbalanced_tags="wrap"` uses a simple regular expression and will only work for HTML where
angle brackets are properly escaped, such as the HTML emitted by :code:`lxml.html.tostring`. It is intended for
regularly formatted documents such as case text published by courts. It may have
unpredictable results for deliberately-constructed challenging inputs such as citations containing partial HTML
comments or :code:`<pre>` tags.

Customizing Annotation
----------------------

If inserting text before and after isn't sufficient, supply a callable under the :code:`annotator` parameter
that takes :code:`(before, span_text, after)` and returns the annotated text:

::

    def annotator(before, span_text, after):
        return before + span_text.lower() + after
    linked_text = annotate(plain_text, [[c.span(), "<a>", "</a>"] for c in citations], annotator=annotator)

    returns:
    'bob lissner v. test <a>1 u.s. 12</a>, 347-348 (4th Cir. 1982)'

Resolving Citations
===================

Once you have extracted citations from a document, you may wish to resolve them to their common references.
To do so, just pass the results of :code:`get_citations()` into :code:`resolve_citations()`. This function will
do its best to resolve each "full," "short form," "supra," and "id" citation to a common :code:`Resource` object,
returning a dictionary that maps resources to lists of associated citations:

::

    from eyecite import get_citations, resolve_citations

    text = 'first citation: 1 U.S. 12. second citation: 2 F.3d 2. third citation: Id.'
    found_citations = get_citations(text)
    resolved_citations = resolve_citations(found_citations)

    returns (pseudo):
    {
        <Resource object>: [FullCaseCitation('1 U.S. 12')],
        <Resource object>: [FullCaseCitation('2 F.3d 2'), IdCitation('Id.')]
    }

Importantly, eyecite performs these resolutions using only its immanent knowledge about each citation's
textual representation. If you want to perform more sophisticated resolution (e.g., by augmenting each
citation with information from a third-party API), simply pass custom :code:`resolve_id_citation()`,
:code:`resolve_supra_citation()`, :code:`resolve_shortcase_citation()`, and :code:`resolve_full_citation()`
functions to :code:`resolve_citations()` as keyword arguments. You can also configure those functions to
return a more complex resource object (such as a Django model), so long as that object inherits the
:code:`eyecite.models.ResourceType` type (which simply requires hashability). For example, you might implement
a custom full citation resolution function as follows, using the default resolution logic as a fallback:

::

    def my_resolve(full_cite):
        # special handling for resolution of known cases in our database
        resource = MyOpinion.objects.get(full_cite)
        if resource:
            return resource
        # allow normal clustering of other citations
        return resolve_full_citation(full_cite)

    resolve_citations(citations, resolve_full_citation=my_resolve)

    returns (pseudo):
    {
        <MyOpinion object>: [<full_cite>, <short_cite>, <id_cite>],
        <Resource object>: [<full cite>, <short cite>],
    }

Dumping Citations
=================

If you want to see what metadata eyecite is able to extract for each citation, you can use :code:`dump_citations`.
This is primarily useful for developing eyecite, but may also be useful for exploring what data is available to you::

    In [1]: from eyecite import dump_citations, get_citations

    In [2]: text="Mass. Gen. Laws ch. 1, § 2. Foo v. Bar, 1 U.S. 2, 3-4 (1999). Id. at 3. Foo, supra, at 5."

    In [3]: cites=get_citations(text)

    In [4]: print(dump_citations(get_citations(text), text))
    FullLawCitation: Mass. Gen. Laws ch. 1, § 2. Foo v. Bar, 1 U.S. 2, 3-4 (1
      * groups
        * reporter='Mass. Gen. Laws'
        * chapter='1'
        * section='2'
    FullCaseCitation: Laws ch. 1, § 2. Foo v. Bar, 1 U.S. 2, 3-4 (1999). Id. at 3. Foo, s
      * groups
        * volume='1'
        * reporter='U.S.'
        * page='2'
      * metadata
        * pin_cite='3-4'
        * year='1999'
        * court='scotus'
        * plaintiff='Foo'
        * defendant='Bar,'
      * year=1999
    IdCitation: v. Bar, 1 U.S. 2, 3-4 (1999). Id. at 3. Foo, supra, at 5.
      * metadata
        * pin_cite='at 3'
    SupraCitation: 2, 3-4 (1999). Id. at 3. Foo, supra, at 5.
      * metadata
        * antecedent_guess='Foo'
        * pin_cite='at 5'

In the real terminal, the :code:`span()` of each extracted citation will be highlighted.
You can use the :code:`context_chars=30` parameter to control how much text is shown before and after.

Tokenizers
==========

Internally, eyecite works by applying a list of regular expressions to the source text to convert it to a list
of tokens:

::

    In [1]: from eyecite.tokenizers import default_tokenizer

    In [2]: list(default_tokenizer.tokenize("Foo v. Bar, 123 U.S. 456 (2016). Id. at 457."))
    Out[2]:
    ['Foo',
     StopWordToken(data='v.', ...),
     'Bar,',
     CitationToken(data='123 U.S. 456', volume='123', reporter='U.S.', page='456', ...),
     '(2016).',
     IdToken(data='Id.', ...),
     'at',
     '457.']

Tokens are then scanned to determine values like the citation year or case name for citation resolution.

Alternate tokenizers can be substituted by providing a tokenizer instance to :code:`get_citations()`:

::

    from eyecite.tokenizers import HyperscanTokenizer
    hyperscan_tokenizer = HyperscanTokenizer(cache_dir='.hyperscan')
    cites = get_citations(text, tokenizer=hyperscan_tokenizer)

test_FindTest.py includes a simplified example of using a custom tokenizer that uses modified
regular expressions to extract citations with OCR errors.

eyecite ships with two tokenizers:

AhocorasickTokenizer (default)
------------------------------

The default tokenizer uses the pyahocorasick library to filter down eyecite's list of
extractor regexes. It then performs extraction using the builtin :code:`re` library.

HyperscanTokenizer
------------------

The alternate HyperscanTokenizer compiles all extraction regexes into a hyperscan database
so they can be extracted in a single pass. This is far faster than the default tokenizer
(exactly how much faster depends on how many citation formats are included in the target text),
but requires the optional :code:`hyperscan` dependency that has limited platform support.
See the "Installation" section for hyperscan installation instructions and limitations.

Compiling the hyperscan database takes several seconds, so short-running scripts may want to
provide a cache directory where the database can be stored. The directory should be writeable
only by the user:

::

    hyperscan_tokenizer = HyperscanTokenizer(cache_dir='.hyperscan')

Installation
============
Installing eyecite is easy.

::

    poetry add eyecite


Or via pip::

    pip install eyecite


Or install the latest dev version from github::

    pip install https://github.com/freelawproject/eyecite/archive/main.zip#egg=eyecite

Hyperscan installation
----------------------

To use :code:`HyperscanTokenizer` you must additionally install the python `hyperscan <https://pypi.org/project/hyperscan/>`_
library and its dependencies. **python-hyperscan officially supports only x86 linux,** though other configurations may be
possible.

Hyperscan installation example on x86 Ubuntu 20.04:

::

    apt install libhyperscan-dev
    pip install hyperscan

Hyperscan installation example on x86 Debian Buster:

::

    echo 'deb http://deb.debian.org/debian buster-backports main' > /etc/apt/sources.list.d/backports.list
    apt install -t buster-backports libhyperscan-dev
    pip install hyperscan

Hyperscan installation example with homebrew on x86 MacOS:

::

    brew install hyperscan
    pip install hyperscan


Deployment
==========

1. Update version info in :code:`pyproject.toml`.

For an automated deployment, tag the commit with vx.y.z, and push it to master.
An automated deploy will be completed for you.

For a manual deployment, run:

::

    poetry publish --build



Testing
=======
eyecite comes with a robust test suite of different citation strings that it is equipped to handle. Run these tests as follows:

::

    python3 -m unittest discover -s tests -p 'test_*.py'

If you would like to create mock citation objects to assist you in writing your own local tests, import and use the following functions for convenience:

::

    from eyecite.test_factories import (
        case_citation,
        id_citation,
        nonopinion_citation,
        supra_citation,
    )

License
=======
This repository is available under the permissive BSD license, making it easy and safe to incorporate in your own libraries.

Pull and feature requests welcome. Online editing in GitHub is possible (and easy!).
