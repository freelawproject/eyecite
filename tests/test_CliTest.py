import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import jsonschema

from eyecite.cli import main


class CliTest(unittest.TestCase):
    def run_cli(self, argv, stdin=""):
        output = io.StringIO()
        with patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(output):
            main(argv)
        return json.loads(output.getvalue())

    def test_extract_argument_and_stdin(self):
        text = "Foo v. Bar, 410 U.S. 113 (1973)."
        argument_result = self.run_cli(["extract", text])
        stdin_result = self.run_cli(["extract"], text)

        self.assertEqual(argument_result, stdin_result)
        self.assertEqual(len(argument_result["citations"]), 1)
        self.assertEqual(
            argument_result["citations"][0],
            {
                "type": "FullCaseCitation",
                "text": "410 U.S. 113",
                "span": [12, 24],
                "full_span": [0, 31],
                "groups": {
                    "volume": "410",
                    "reporter": "U.S.",
                    "page": "113",
                },
                "metadata": {
                    "year": "1973",
                    "court": "scotus",
                    "plaintiff": "Foo",
                    "defendant": "Bar",
                },
                "year": 1973,
            },
        )

    def test_schema_validates_output(self):
        schema = self.run_cli(["schema"])
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(
            self.run_cli(["extract", "Id. at 3."]), schema
        )

    def test_extract_requires_input(self):
        with (
            patch("sys.stdin", io.StringIO()),
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            main(["extract"])
        self.assertEqual(error.exception.code, 2)

    def test_agent_skills_match(self):
        root = Path(__file__).parents[1]
        codex = root / ".agents/skills/eyecite-extract/SKILL.md"
        claude = root / ".claude/skills/eyecite-extract/SKILL.md"
        self.assertEqual(codex.read_bytes(), claude.read_bytes())


if __name__ == "__main__":
    unittest.main()
