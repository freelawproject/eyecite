"""Command-line interface for eyecite."""

import argparse
import json
import sys
from typing import Any

from eyecite import get_citations

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eyecite")
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="extract citations as JSON")
    extract.add_argument("text", nargs="?", help="text; defaults to stdin")
    commands.add_parser("schema", help="print the extraction JSON Schema")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "schema":
        result = OUTPUT_SCHEMA
    else:
        text = args.text if args.text is not None else sys.stdin.read()
        if not text:
            parser.error("extract requires text as an argument or on stdin")
        result = {
            "citations": [
                citation_to_dict(citation) for citation in get_citations(text)
            ]
        }

    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
