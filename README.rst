eyecite
==========

eyecite is an open source tool for extracting legal citations from text strings. Originally built for use with `Courtlistener.com <https://www.courtlistener.com/>`_, it is now a freestanding package.

Its main purpose is to facilitate the conversion of raw text into structured citation entities. It includes mechanisms to recognize and extract "full" citation references (e.g., `Bush v. Gore, 531 U.S. 98`), "short form" references (e.g., `531 U.S., at 99`), "supra" references (e.g., `Bush, supra, at 100`), "id." references (e.g., `Id., at 101`), and "ibid." references (e.g., `Ibid.`).

Further development is intended and all contributors, corrections, and additions are welcome.

Background
==========
This project is the culmination of `years <https://free.law/2012/05/11/building-a-citator-on-courtlistener/>`_ `of <https://free.law/2015/11/30/our-new-citation-finder/>`_ `work <https://free.law/2020/03/05/citation-data-gets-richer/>`_ to build a citator within Courtlistener.com. This project represents the next step in that development: Decoupling the parsing logic and exposing it for third-party use as a standalone Python package.

Quickstart
==========

Simply feed in a raw string of text (or HTML), and receive a list of structured citation objects, ordered in the sequence that they appear in the text.


::

    from eyecite.find_citations import get_citations

    text = 'bob lissner v. test 1 U.S. 12, 347-348 (4th Cir. 1982)'
    found_citations = get_citations(text)

    returns:
    [FullCitation(plaintiff='lissner', defendant='test', volume=1,
               reporter='U.S.', page='12', year=1982,
               extra='347-348', court='ca4',
               canonical_reporter='U.S.', lookup_index=0,
               reporter_index=5, reporter_found='U.S.')]



Once these `Citation` objects are obtained, you can find them in the original text by calling their `as_regex()` methods, which return a bespoke regex representation for each extracted citation.


::

    citation_regex = found_citations[0].as_regex()

    returns:
    '1(\s+)U\.S\.(\s+)12(\s?)'



::

    import re

    match = re.search(citation_regex, text)

    returns:
    <re.Match object; span=(20, 29), match='1 U.S. 12'>



Options
=======
:code:`get_citations()`, the main executable function, takes several parameters.

1. :code:`html` ==> bool; whether the passed string is HTML or not
2. :code:`do_post_citation` ==> bool; whether additional, post-citation information should be extracted (e.g., the court, year, and/or date range of the citation)
3. :code:`do_defendant` ==> bool; whether the pre-citation defendant (and possibily plaintiff) reference should be extracted
4. :code:`disambiguate` ==> bool; whether each citation's (possibly ambiguous) reporter should be resolved to its (unambiguous) form

Some notes
----------
Some things to keep in mind are:

1. This project depends on information made available in two other Free Law Project packages, `reporters-db <https://github.com/freelawproject/reporters-db>`_ and `courts-db <https://github.com/freelawproject/courts-db>`_.
2. This package performs no matching or resolution action. In other words, it is up to the user to decide what to do with the "short form," "supra," "id.," and "ibid." citations that this tool extracts. In theory, these citations are all references to "full" citations also mentioned in the text -- and are therefore in principle resolvable to those citations -- but this task is beyond the scope of this parsing package. See `here <https://github.com/freelawproject/courtlistener/tree/master/cl/citations>`_ for an example of how Courtlistener implements this package and handles this problem.


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


License
=======
This repository is available under the permissive BSD license, making it easy and safe to incorporate in your own libraries.

Pull and feature requests welcome. Online editing in GitHub is possible (and easy!).
