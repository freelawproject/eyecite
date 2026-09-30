import io
import json
import tempfile
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
        opinion = (
            Path(__file__).parent / "assets" / "opinion.txt"
        ).read_text()
        schema = self.run_cli(["schema"])
        jsonschema.Draft202012Validator.check_schema(schema)
        result = self.run_cli(["extract"], opinion)
        self.assertGreater(len(result["citations"]), 100)
        jsonschema.validate(result, schema)

    def test_help_documents_the_interface(self):
        for argv, expected in (
            (["--help"], "Exit codes:"),
            (["extract", "--help"], "Output size:"),
        ):
            with self.subTest(argv=argv):
                output = io.StringIO()
                with (
                    redirect_stdout(output),
                    self.assertRaises(SystemExit) as error,
                ):
                    main(argv)
                self.assertEqual(error.exception.code, 0)
                # Lost if formatter_class stops preserving the epilog.
                self.assertIn(expected, output.getvalue())
                self.assertIn("Examples:", output.getvalue())

    def test_extract_accepts_empty_input(self):
        self.assertEqual(self.run_cli(["extract"], ""), {"citations": []})

    def test_extract_requires_input_on_a_tty(self):
        stdin = io.StringIO()
        stdin.isatty = lambda: True
        with (
            patch("sys.stdin", stdin),
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            main(["extract"])
        self.assertEqual(error.exception.code, 2)

    def test_output_file(self):
        text = "Foo v. Bar, 410 U.S. 113 (1973)."
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            with redirect_stderr(io.StringIO()) as stderr:
                main(["extract", text, "-o", str(path)])
            self.assertEqual(
                json.loads(path.read_text()), self.run_cli(["extract", text])
            )
            self.assertIn("wrote 1 citations", stderr.getvalue())

    def test_agent_skills_match(self):
        root = Path(__file__).parents[1]
        codex = root / ".agents/skills/eyecite-extract/SKILL.md"
        claude = root / ".claude/skills/eyecite-extract/SKILL.md"
        self.assertFalse(codex.is_symlink())
        self.assertEqual(codex.read_bytes(), claude.read_bytes())


if __name__ == "__main__":
    unittest.main()
