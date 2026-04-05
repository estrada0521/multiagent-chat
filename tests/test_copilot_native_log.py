from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index.chat_core import _copilot_tool_summary, _parse_native_copilot_log


class CopilotToolSummaryTests(unittest.TestCase):
    """Pins the per-tool summary format for Copilot tool.execution_start events."""

    def test_bash_uses_description(self) -> None:
        self.assertEqual(
            _copilot_tool_summary("bash", {"command": "ls -la", "description": "list files"}),
            "bash list files",
        )

    def test_bash_falls_back_to_first_command_line(self) -> None:
        self.assertEqual(
            _copilot_tool_summary("bash", {"command": "echo hi\nline2"}),
            "bash echo hi",
        )

    def test_view_uses_path(self) -> None:
        self.assertEqual(
            _copilot_tool_summary("view", {"path": "src/main.py"}),
            "view src/main.py",
        )

    def test_grep_uses_pattern(self) -> None:
        self.assertEqual(
            _copilot_tool_summary("grep", {"pattern": "TODO", "glob": "*.py"}),
            "grep TODO",
        )

    def test_report_intent_shows_intent(self) -> None:
        self.assertEqual(
            _copilot_tool_summary("report_intent", {"intent": "Greeting user"}),
            "Greeting user",
        )

    def test_ask_user_shows_question(self) -> None:
        self.assertEqual(
            _copilot_tool_summary("ask_user", {"question": "Confirm?"}),
            "ask_user Confirm?",
        )

    def test_web_fetch_shows_url(self) -> None:
        self.assertEqual(
            _copilot_tool_summary("web_fetch", {"url": "https://example.com", "max_length": 1000}),
            "web_fetch https://example.com",
        )

    def test_unknown_tool_falls_back_to_first_arg(self) -> None:
        self.assertEqual(
            _copilot_tool_summary("mystery", {"foo": "bar"}),
            "mystery bar",
        )

    def test_missing_tool_name_defaults_to_tool(self) -> None:
        self.assertEqual(_copilot_tool_summary("", {}), "tool")


class CopilotEventLogParseTests(unittest.TestCase):
    def _write_log(self, entries: list[dict]) -> str:
        fh = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        try:
            for e in entries:
                fh.write(json.dumps(e) + "\n")
        finally:
            fh.close()
        self.addCleanup(Path(fh.name).unlink, missing_ok=True)
        return fh.name

    def test_returns_empty_on_empty_file(self) -> None:
        path = self._write_log([])
        self.assertEqual(_parse_native_copilot_log(path, limit=12), [])

    def test_returns_none_on_missing_file(self) -> None:
        self.assertIsNone(_parse_native_copilot_log("/nonexistent/path.jsonl", limit=12))

    def test_parses_assistant_message(self) -> None:
        path = self._write_log([
            {
                "type": "assistant.message",
                "data": {"messageId": "m1", "content": "Hello there"},
            },
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "● Hello there")
        self.assertIn("msg:copilot:m1", out[0]["source_id"])

    def test_parses_tool_execution_start(self) -> None:
        path = self._write_log([
            {
                "type": "tool.execution_start",
                "data": {
                    "toolCallId": "t1",
                    "toolName": "bash",
                    "arguments": {"command": "ls", "description": "list"},
                },
            },
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "● bash list")
        self.assertIn("tool:copilot:t1", out[0]["source_id"])

    def test_ignores_unknown_event_types(self) -> None:
        path = self._write_log([
            {"type": "session.start", "data": {"sessionId": "s1"}},
            {"type": "assistant.turn_start", "data": {}},
            {"type": "tool.execution_complete", "data": {}},
        ])
        self.assertEqual(_parse_native_copilot_log(path, limit=12), [])

    def test_skips_malformed_json(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("not json\n")
            fh.write(json.dumps({"type": "assistant.message", "data": {"content": "OK", "messageId": "x"}}) + "\n")
            fh.write("\n")
            path = fh.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "● OK")

    def test_limit_keeps_tail(self) -> None:
        path = self._write_log([
            {
                "type": "tool.execution_start",
                "data": {"toolCallId": f"t{i}", "toolName": "view", "arguments": {"path": f"f{i}.py"}},
            }
            for i in range(10)
        ])
        out = _parse_native_copilot_log(path, limit=3)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0]["text"], "● view f7.py")
        self.assertEqual(out[-1]["text"], "● view f9.py")


if __name__ == "__main__":
    unittest.main()
