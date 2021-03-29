eyecite
==========

eyecite is an open source tool for extracting legal citations from text strings. Originally built for use with `Courtlistener.com <https://www.courtlistener.com/>`_, it is now a freestanding package.

Its main purpose is to facilitate the conversion of raw text into structured citation entities. It includes mechanisms to recognize and extract "full" citation references (e.g., :code:`Bush v. Gore, 531 U.S. 98`), "short form" references (e.g., :code:`531 U.S., at 99`), "supra" references (e.g., :code:`Bush, supra, at 100`), "id." references (e.g., :code:`Id., at 101`), and "ibid." references (e.g., :code:`Ibid.`).

Further development is intended and all contributors, corrections, and additions are welcome.

Background
==========
This project is the culmination of `years <https://free.law/2012/05/11/building-a-citator-on-courtlistener/>`_ `of <https://free.law/2015/11/30/our-new-citation-finder/>`_ `work <https://free.law/2020/03/05/citation-data-gets-richer/>`_ to build a citator within Courtlistener.com. This project represents the next step in that development: Decoupling the parsing logic and exposing it for third-party use as a standalone Python package.

Quickstart
==========

Simply feed in a raw string of text (or HTML), and receive a list of structured citation objects, ordered in the sequence that they appear in the text.


::

    from eyecite import get_citations

    text = 'bob lissner v. test 1 U.S. 12, 347-348 (4th Cir. 1982)'
    found_citations = get_citations(text)

    returns:
    [FullCaseCitation(plaintiff='lissner', defendant='test', volume=1,
               reporter='U.S.', page='12', year=1982,
               extra='347-348', court='ca4',
               canonical_reporter='U.S.', lookup_index=0,
               token_index=5, reporter_found='U.S.')]


Options
=======
:code:`get_citations()`, the main executable function, takes several parameters.

1. :code:`do_post_citation` ==> bool; whether additional, post-citation information should be extracted (e.g., the court, year, and/or date range of the citation)
2. :code:`do_defendant` ==> bool; whether the pre-citation defendant (and possibily plaintiff) reference should be extracted
3. :code:`disambiguate` ==> bool; whether each citation's (possibly ambiguous) reporter should be resolved to its (unambiguous) form
4. :code:`tokenizer` ==> Tokenizer; an instance of a Tokenizer object (see "Tokenizers" below)

Some notes
----------
Some things to keep in mind are:

1. This project depends on information made available in two other Free Law Project packages, `reporters-db <https://github.com/freelawproject/reporters-db>`_ and `courts-db <https://github.com/freelawproject/courts-db>`_.
2. This package performs no matching or resolution action. In other words, it is up to the user to decide what to do with the "short form," "supra," "id.," and "ibid." citations that this tool extracts. In theory, these citations are all references to "full" citations also mentioned in the text -- and are therefore in principle resolvable to those citations -- but this task is beyond the scope of this parsing package. See `here <https://github.com/freelawproject/courtlistener/tree/master/cl/citations>`_ for an example of how Courtlistener implements this package and handles this problem.


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

Tokenizers
==========

Internally, eyecite works by applying a list of regular expressions to the source text to convert it to a list
of tokens:

::

    In [1]: from eyecite.tokenizers import default_tokenizer

    In [2]: list(default_tokenizer.tokenize("Foo v. Bar, 123 U.S. 456 (2016). Id. at 457."))
    Out[2]:
    ['Foo',
     StopWordToken(data='v.', stop_word='v'),
     'Bar,',
     CitationToken(data='123 U.S. 456', volume='123', reporter='U.S.', page='456' ...),
     '(2016).',
     IdToken(data='Id.'),
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
but requires the optional :code:`hyperscan` dependency that is limited to the x86 platform.

Compiling the hyperscan database takes several seconds, so short-running scripts may want to
provide a cache directory where the database can be stored. The directory should be writeable
only by the user:

::

    hyperscan_tokenizer = HyperscanTokenizer(cache_dir='.hyperscan')

Installation
============
Installing eyecite is easy.

::

    sh
    pip install eyecite



Or install the latest dev version from github

::

    sh
    pip install git+https://github.com/freelawproject/eyecite.git@master



Deployment
==========

1. Update version info in :code:`setup.py` and in :code:`pyproject.toml`.

For an automated deployment, tag the commit with vx.y.z, and push it to master.
An automated deploy will be completed for you.

For a manual deployment, follow these steps:

1. Install the requirements using :code:`poetry install`

2. Set up a config file at :code:`~/.pypirc`

3. Generate a universal distribution that works in py2 and py3 (see setup.cfg)

::

    sh
    python setup.py sdist bdist_wheel


5. Upload the distributions
::

    sh
    twine upload dist/* -r pypi (or pypitest)



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
