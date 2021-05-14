# Change Log

## Upcoming

The following changes are not yet released, but are code complete:

Features:
 - Adds `dump_citations()` to inspect extracted citations.

## Current

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
   
## Past

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
