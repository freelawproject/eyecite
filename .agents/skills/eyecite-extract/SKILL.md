---
name: eyecite-extract
description: >
  Extract legal citations from text or documents as structured JSON — case
  citations, short forms, `Id.` and `supra`, statutes (U.S.C., C.F.R., state
  codes), and law-journal cites, each with its character span, reporter,
  court, year, and pin cite. Use this skill whenever the user supplies a
  brief, opinion, memo, or any legal document and asks what it cites, or asks
  to list, count, extract, or normalize citations — even if they never say
  "citation" or "eyecite". Prefer it over identifying citations by eye or by
  regex: formats are irregular, and short forms like `Id.` only resolve
  against the surrounding text. It reports what a document cites, not whether
  those cites are sound: it is not a citator and does not cite-check, so it
  cannot tell you whether a case exists, is still good law, is quoted
  accurately, or follows a style guide. A citation that parses cleanly may
  still be fabricated.
compatibility: Requires uv (for uvx) and, on first run, network access to PyPI.
---

# Extract legal citations

Use eyecite through `uvx`; do not reimplement citation parsing.

- For text, run `uvx --from 'eyecite>=2.8,<3' eyecite extract "<text>"`.
- For a file, choose a temporary output path appropriate for the current
  platform so the JSON stays out of the tool transcript. `-o` prints the
  citation count to stderr; never omit it for file input.

      uvx --from 'eyecite>=2.8,<3' eyecite extract -o "<temporary-file>" < "<file>"
- Substitute `schema` for `extract` when a consumer needs the output
  contract, or `extract --help` for flags and exit codes. Exit `2` means bad
  arguments, not a parse failure; text with no citations exits `0` with an
  empty `citations` array.
- Inspect only what is needed from the temporary JSON file, then delete it.
  If `jq` is available, for example, run
  `jq -r '.citations[].text' "<temporary-file>"`. Otherwise use Python's
  standard-library JSON parser, substituting `python3` if needed:
  `python -c "import json,sys; data=json.load(open(sys.argv[1], encoding='utf-8')); print(*(c['text'] for c in data['citations']), sep='\n')" "<temporary-file>"`.
  If neither is available, read the file in bounded chunks. Do not print the
  full file unless the user requests it.

Report the extracted citation data or requested summary. Do not modify the
input or repository.

**Extraction, not cite-checking.** A parsed citation is only well-formed — it
may be fabricated, overruled, or misquoted. Never call results verified,
valid, or confirmed. If the user asks whether cites are real or still good
law, say eyecite cannot answer that.
