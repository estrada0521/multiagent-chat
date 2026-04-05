from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index.chat_core import _parse_native_copilot_log


class CopilotEventLogParseTests(unittest.TestCase):
    """Pins the raw-dump behaviour of the Copilot adapter.

    The adapter emits one event per Copilot log line, formatted as
    ``[type]\\n{pretty-printed json of the full entry}`` so nothing is
    elided. Tests cover the shape, per-event separation, malformed-line
    handling and limit tail.
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

    def test_dumps_full_event(self) -> None:
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
        text = out[0]["text"]
        self.assertTrue(text.startswith("[tool.execution_start]\n"))
        # Every field from the original entry must appear in the pretty-printed dump.
        self.assertIn('"toolCallId": "t1"', text)
        self.assertIn('"toolName": "bash"', text)
        self.assertIn('"command": "ls"', text)
        self.assertIn('"description": "list"', text)
        # indent=2 means JSON spans multiple lines.
        self.assertIn("\n  ", text)

    def test_each_event_becomes_one_row(self) -> None:
        path = self._write_log([
            {"type": "session.start", "data": {"sessionId": "s1"}},
            {"type": "tool.execution_complete", "data": {"toolCallId": "t1", "success": True}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 2)
        self.assertTrue(out[0]["text"].startswith("[session.start]\n"))
        self.assertTrue(out[1]["text"].startswith("[tool.execution_complete]\n"))

    def test_turn_start_and_turn_end_are_filtered(self) -> None:
        path = self._write_log([
            {"type": "assistant.turn_start", "data": {"turnId": "t1"}},
            {"type": "assistant.message", "data": {"content": "hi"}},
            {"type": "assistant.turn_end", "data": {"turnId": "t1"}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertIn("[assistant.message]", out[0]["text"])

    def test_preserves_non_ascii(self) -> None:
        path = self._write_log([
            {"type": "assistant.message", "data": {"content": "こんにちは"}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertIn("こんにちは", out[0]["text"])
        # json.dumps with ensure_ascii=False should NOT escape as \u3053...
        self.assertNotIn("\\u3053", out[0]["text"])

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
        self.assertIn("[assistant.message]", out[0]["text"])
        self.assertIn('"content": "OK"', out[0]["text"])

    def test_missing_type_falls_back_to_event(self) -> None:
        path = self._write_log([{"data": {"x": 1}}])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["text"].startswith("[event]\n"))

    def test_limit_keeps_tail(self) -> None:
        path = self._write_log([
            {"type": "tool.execution_start", "data": {"toolCallId": f"t{i}"}}
            for i in range(10)
        ])
        out = _parse_native_copilot_log(path, limit=3)
        self.assertEqual(len(out), 3)
        self.assertIn('"toolCallId": "t7"', out[0]["text"])
        self.assertIn('"toolCallId": "t9"', out[-1]["text"])

    def test_source_ids_are_unique_per_row(self) -> None:
        # Two identical events should still get unique source_ids via seq counter.
        path = self._write_log([
            {"type": "assistant.message", "data": {"content": "hi"}},
            {"type": "assistant.message", "data": {"content": "hi"}},
        ])
        out = _parse_native_copilot_log(path, limit=12)
        self.assertEqual(len(out), 2)
        self.assertNotEqual(out[0]["source_id"], out[1]["source_id"])


if __name__ == "__main__":
    unittest.main()
