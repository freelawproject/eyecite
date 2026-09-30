"""Opt-in end-to-end checks for the eyecite agent skill."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURE = Path("tests/assets/opinion.txt")
MAX_TRACE_CHARS = 50_000
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "citation_count": {"type": "integer"},
        "first_citation_text": {"type": "string"},
        "last_citation_text": {"type": "string"},
    },
    "required": [
        "citation_count",
        "first_citation_text",
        "last_citation_text",
    ],
    "additionalProperties": False,
}


@unittest.skipUnless(
    os.environ.get("EYECITE_AGENT_CLIENT"),
    "set EYECITE_AGENT_CLIENT=codex, claude, or all",
)
class AgentSkillTest(unittest.TestCase):
    def run_command(self, command, env, stdin=None):
        return subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=600,
            check=True,
        )

    def test_agent_skill(self):
        selected = os.environ["EYECITE_AGENT_CLIENT"]
        self.assertIn(selected, {"codex", "claude", "all"})
        clients = ["codex", "claude"] if selected == "all" else [selected]
        status_before = self.run_command(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            os.environ.copy(),
        ).stdout

        with tempfile.TemporaryDirectory(prefix="eyecite-agent-test-") as tmp:
            tmp_path = Path(tmp)
            env = os.environ.copy()
            env["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
            env["UV_TOOL_DIR"] = str(tmp_path / "uv-tools")
            env["UV_PYTHON"] = sys.executable
            baseline = json.loads(
                self.run_command(
                    ["uvx", "--from", ".", "eyecite", "extract"],
                    env,
                    (ROOT / FIXTURE).read_text(),
                ).stdout
            )["citations"]
            expected = {
                "citation_count": len(baseline),
                "first_citation_text": baseline[0]["text"],
                "last_citation_text": baseline[-1]["text"],
            }
            env["UV_OFFLINE"] = "1"

            for client in clients:
                with self.subTest(client=client):
                    self.assertTrue(
                        shutil.which(client), f"{client} CLI is not installed"
                    )
                    result, commands, trace_chars = getattr(
                        self, f"run_{client}"
                    )(tmp_path, env)
                    self.assertEqual(result, expected)
                    self.assertTrue(
                        any(
                            "uvx" in command and "eyecite" in command
                            for command in commands
                        ),
                        f"{client} did not execute eyecite through uvx",
                    )
                    self.assertTrue(
                        any("opinion.txt" in command for command in commands),
                        f"{client} did not process the opinion fixture",
                    )
                    self.assertLess(
                        trace_chars,
                        MAX_TRACE_CHARS,
                        f"{client} leaked the citation JSON into its trace",
                    )

        status_after = self.run_command(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            os.environ.copy(),
        ).stdout
        self.assertEqual(status_after, status_before)

    def run_codex(self, tmp_path, env):
        schema_path = tmp_path / "agent-result.schema.json"
        result_path = tmp_path / "codex-result.json"
        schema_path.write_text(json.dumps(RESULT_SCHEMA))
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--json",
            "--sandbox",
            "workspace-write",
            "--ignore-user-config",
            "-C",
            str(ROOT),
            "--output-schema",
            str(schema_path),
            "-o",
            str(result_path),
        ]
        if model := env.get("EYECITE_CODEX_MODEL"):
            command.extend(["--model", model])
        command.append(self.prompt("$eyecite-extract"))
        completed = self.run_command(command, env)
        events = [json.loads(line) for line in completed.stdout.splitlines()]
        commands = [
            event["item"]["command"]
            for event in events
            if event.get("type") in {"item.started", "item.completed"}
            and event.get("item", {}).get("type") == "command_execution"
        ]
        return (
            json.loads(result_path.read_text()),
            commands,
            len(completed.stdout),
        )

    def run_claude(self, tmp_path, env):
        command = [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--json-schema",
            json.dumps(RESULT_SCHEMA),
            "--no-session-persistence",
            "--setting-sources",
            "project",
            "--tools",
            "Bash",
            "--allowedTools",
            "Bash",
            "--permission-mode",
            "dontAsk",
            "--permission-prompts",
            "none",
        ]
        if model := env.get("EYECITE_CLAUDE_MODEL"):
            command.extend(["--model", model])
        command.append(self.prompt("/eyecite-extract"))
        completed = self.run_command(command, env)
        events = [json.loads(line) for line in completed.stdout.splitlines()]
        result_event = next(
            event
            for event in reversed(events)
            if event.get("type") == "result"
        )
        result = result_event.get("structured_output")
        if result is None:
            result = json.loads(result_event["result"])
        commands = []
        for event in events:
            message = event.get("message", {})
            for item in message.get("content", []):
                if (
                    item.get("type") == "tool_use"
                    and item.get("name") == "Bash"
                ):
                    commands.append(item.get("input", {}).get("command", ""))
        return result, commands, len(completed.stdout)

    @staticmethod
    def prompt(skill):
        return (
            f"Use {skill} to extract citations from {FIXTURE}. "
            "Run the skill's commands against this source checkout instead "
            "of the released package: replace the `--from` package specifier "
            "with `.`, so they read `uvx --from . eyecite ...`. Keep the raw "
            "JSON out of the tool transcript by writing it to a temporary "
            "file before inspecting it. Return only the citation count and "
            "the exact text of the first and last citations, matching the "
            "required schema. Do not modify files."
        )


if __name__ == "__main__":
    unittest.main()
