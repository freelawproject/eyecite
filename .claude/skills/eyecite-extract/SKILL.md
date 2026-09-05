---
name: eyecite-extract
description: Extract structured legal citations from text or text files with eyecite.
---

# Extract legal citations

Use eyecite through `uvx`; do not reimplement citation parsing.

- For text, run `uvx eyecite extract "<text>"`.
- For a file, keep both the input and JSON output out of the tool transcript:
  `result_file=$(mktemp); uvx eyecite extract < "<file>" > "$result_file"`.
  Never run file extraction without the output redirection.
- When running inside an eyecite source checkout, substitute `--from .` to test
  that checkout rather than the published package.
- Run `uvx eyecite schema` when a consumer needs the output
  contract.
- Inspect or summarize the temporary JSON file according to the user's request,
  then delete it. Do not print the full file unless the user requests it.

Report the extracted citation data or requested summary. Do not modify the
input or repository.
