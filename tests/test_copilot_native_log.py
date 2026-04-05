from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index.chat_core import _format_copilot_event, _parse_native_copilot_log


class CopilotEventLogParseTests(unittest.TestCase):
    """Pins the compact per-event summary emitted by the Copilot adapter.

    Each kept event type is rendered to a single line by
    :func:`_format_copilot_event`, picking only high-signal fields.
    """

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

    def test_tool_execution_start_shows_name_and_hint(self) -> None:
        path = self._write_log([
            {
                "type": "tool.execution_start",
                "data": {
                    "toolCallId": "t1",
                    "toolName": "bash",
                    "arguments": {"command": "ls -la", "description": "list"},
                },
            },
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "→ bash: ls -la")

    def test_tool_execution_complete_marks_success(self) -> None:
        path = self._write_log([
            {"type": "tool.execution_complete", "data": {"toolCallId": "t1", "success": True, "result": "done"}},
            {"type": "tool.execution_complete", "data": {"toolCallId": "t2", "success": False, "result": "boom"}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(out[0]["text"], "✓ tool: done")
        self.assertEqual(out[1]["text"], "✗ tool: boom")

    def test_assistant_message_shows_content(self) -> None:
        path = self._write_log([
            {"type": "assistant.message", "data": {"messageId": "m1", "content": "hello world"}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(out[0]["text"], "assistant: hello world")

    def test_assistant_message_with_tool_requests(self) -> None:
        path = self._write_log([
            {
                "type": "assistant.message",
                "data": {
                    "content": "",
                    "toolRequests": [{"toolName": "bash"}, {"toolName": "read"}],
                },
            },
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(out[0]["text"], "assistant → bash, read")

    def test_turn_start_end_and_user_message_are_filtered(self) -> None:
        path = self._write_log([
            {"type": "assistant.turn_start", "data": {"turnId": "t1"}},
            {"type": "user.message", "data": {"content": "hello"}},
            {"type": "assistant.message", "data": {"content": "hi"}},
            {"type": "assistant.turn_end", "data": {"turnId": "t1"}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "assistant: hi")

    def test_preserves_non_ascii(self) -> None:
        path = self._write_log([
            {"type": "assistant.message", "data": {"content": "こんにちは"}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(out[0]["text"], "assistant: こんにちは")

    def test_skips_malformed_json(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("not json\n")
            fh.write(json.dumps({"type": "assistant.message", "data": {"content": "OK"}}) + "\n")
            fh.write("\n")
            path = fh.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "assistant: OK")

    def test_missing_type_falls_back_to_bracket_event(self) -> None:
        path = self._write_log([{"data": {"x": 1}}])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "[event]")

    def test_limit_keeps_tail(self) -> None:
        path = self._write_log([
            {"type": "tool.execution_start", "data": {"toolName": "bash", "arguments": {"command": f"cmd{i}"}}}
            for i in range(10)
        ])
        out = _parse_native_copilot_log(path, limit=3)
        self.assertEqual(len(out), 3)
        self.assertIn("cmd7", out[0]["text"])
        self.assertIn("cmd9", out[-1]["text"])

    def test_source_ids_are_unique_per_row(self) -> None:
        path = self._write_log([
            {"type": "assistant.message", "data": {"content": "hi"}},
            {"type": "assistant.message", "data": {"content": "hi"}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 2)
        self.assertNotEqual(out[0]["source_id"], out[1]["source_id"])

    def test_long_content_is_not_truncated(self) -> None:
        long_text = "x" * 500
        out_text = _format_copilot_event("assistant.message", {"content": long_text})
        self.assertIn(long_text, out_text)
        self.assertFalse(out_text.endswith("…"))

    def test_preserves_inner_newlines(self) -> None:
        out_text = _format_copilot_event(
            "assistant.message", {"content": "line1\nline2\nend"}
        )
        self.assertEqual(out_text, "assistant: line1\nline2\nend")

    def test_model_change_shows_transition(self) -> None:
        out = _format_copilot_event(
            "session.model_change",
            {"previousModel": "gpt-4o", "newModel": "claude-opus-4-6"},
        )
        self.assertEqual(out, "model: gpt-4o → claude-opus-4-6")

    def test_session_error_formats_both_fields(self) -> None:
        out = _format_copilot_event(
            "session.error", {"errorType": "TimeoutError", "message": "took too long"}
        )
        self.assertEqual(out, "error: TimeoutError: took too long")

    def test_subagent_uses_display_name(self) -> None:
        out = _format_copilot_event(
            "subagent.started",
            {"agentName": "explore", "agentDisplayName": "Explore"},
        )
        self.assertEqual(out, "subagent start: Explore")

    def test_session_context_changed_branch_and_head(self) -> None:
        out = _format_copilot_event(
            "session.context_changed",
            {"branch": "main", "headCommit": "abcdef1234567890"},
        )
        self.assertEqual(out, "context: main@abcdef1")

    def test_compaction_events(self) -> None:
        self.assertEqual(_format_copilot_event("session.compaction_start", {}), "compacting…")
        self.assertEqual(_format_copilot_event("session.compaction_complete", {}), "compacted")


if __name__ == "__main__":
    unittest.main()
