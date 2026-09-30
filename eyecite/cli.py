"""Command-line interface for eyecite."""

import argparse
import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from eyecite import get_citations

try:
    VERSION = version("eyecite")
except PackageNotFoundError:  # running from an uninstalled checkout
    VERSION = "unknown"

SPAN_SCHEMA = {
    "type": "array",
    "prefixItems": [{"type": "integer"}, {"type": "integer"}],
    "minItems": 2,
    "maxItems": 2,
}

OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "text": {"type": "string"},
                    "span": SPAN_SCHEMA,
                    "full_span": SPAN_SCHEMA,
                    "groups": {"type": "object"},
                    "metadata": {"type": "object"},
                    "year": {"type": ["integer", "null"]},
                },
                "required": [
                    "type",
                    "text",
                    "span",
                    "full_span",
                    "groups",
                    "metadata",
                    "year",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["citations"],
    "additionalProperties": False,
}


def citation_to_dict(citation: Any) -> dict[str, Any]:
    """Convert an eyecite citation to JSON-compatible data."""
    dumped = citation.dump()
    return {
        "type": type(citation).__name__,
        "text": citation.matched_text(),
        "span": citation.span(),
        "full_span": citation.full_span(),
        "groups": dumped["groups"],
        "metadata": dumped["metadata"],
        "year": dumped.get("year"),
    }


MAIN_EPILOG = """\
Exit codes:
  0  success
  2  invalid arguments, or no text supplied on an interactive terminal

Examples:
  eyecite extract "Roe v. Wade, 410 U.S. 113 (1973)"
  eyecite extract < opinion.txt
  eyecite extract -o citations.json < opinion.txt
  eyecite schema
"""

EXTRACT_DESCRIPTION = """\
Extract citations from TEXT, or from stdin when TEXT is omitted. Prints a
JSON object with a "citations" array; run `eyecite schema` for the full
contract. Diagnostics go to stderr, never stdout. Empty input yields an
empty array.
"""

EXTRACT_EPILOG = """\
Output size:
  Roughly 40 KB of JSON per 90 KB of input. Use -o for whole documents;
  many agent harnesses truncate tool output past 10-30 KB.

Examples:
  eyecite extract "410 U.S. 113"
  eyecite extract < opinion.txt | jq -r '.citations[].text'
  eyecite extract -o citations.json < opinion.txt
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eyecite",
        description="Extract legal citations from text and print them as JSON.",
        epilog=MAIN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser(
        "extract",
        help="extract citations as JSON",
        description=EXTRACT_DESCRIPTION,
        epilog=EXTRACT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    extract.add_argument("text", nargs="?", help="text; defaults to stdin")
    extract.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help=(
            "write JSON to FILE instead of stdout, and print the citation "
            "count to stderr"
        ),
    )
    commands.add_parser("schema", help="print the extraction JSON Schema")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    result: dict[str, Any]
    if args.command == "schema":
        result = OUTPUT_SCHEMA
    else:
        if args.text is not None:
            text = args.text
        elif sys.stdin.isatty():
            parser.error("extract requires text as an argument or on stdin")
        else:
            text = sys.stdin.read()
        # get_citations() rejects empty text; an empty file has no cites.
        citations = get_citations(text) if text else []
        result = {"citations": [citation_to_dict(c) for c in citations]}

    payload = json.dumps(result, ensure_ascii=False) + "\n"
    output = getattr(args, "output", None)
    if output is None:
        sys.stdout.write(payload)
    else:
        Path(output).write_text(payload, encoding="utf-8")
        count = len(result["citations"])
        print(f"wrote {count} citations to {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
