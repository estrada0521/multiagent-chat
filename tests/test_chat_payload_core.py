from __future__ import annotations

import json
import unittest

import _bootstrap  # noqa: F401
from agent_index.chat_payload_core import (
    attachment_paths,
    build_payload_document,
    encode_payload_document,
    summarize_light_entry,
)


class ChatPayloadCoreTests(unittest.TestCase):
    def test_attachment_paths_extracts_markers(self) -> None:
        message = "See files\n[Attached: logs/a.txt]\n[Attached: docs/note.md]"
        self.assertEqual(attachment_paths(message), ["logs/a.txt", "docs/note.md"])

    def test_summarize_light_entry_keeps_small_message(self) -> None:
        entry = {"message": "hello\n[Attached: logs/a.txt]"}
        summary = summarize_light_entry(
            entry,
            message_char_limit=100,
            code_threshold=500,
            attachment_preview_limit=3,
        )
        self.assertEqual(summary["message"], entry["message"])
        self.assertEqual(summary["attached_paths"], ["logs/a.txt"])
        self.assertNotIn("deferred_body", summary)

    def test_summarize_light_entry_truncates_long_message(self) -> None:
        entry = {"message": ("x" * 150) + "\n[Attached: logs/a.txt]"}
        summary = summarize_light_entry(
            entry,
            message_char_limit=40,
            code_threshold=500,
            attachment_preview_limit=3,
        )
        self.assertTrue(summary["deferred_body"])
        self.assertIn("[Public preview truncated. Load full message.]", summary["message"])
        self.assertEqual(summary["message_length"], len(entry["message"]))

    def test_summarize_light_entry_truncates_heavy_code(self) -> None:
        entry = {"message": "```python\n" + ("x" * 40) + "\n```"}
        summary = summarize_light_entry(
            entry,
            message_char_limit=200,
            code_threshold=10,
            attachment_preview_limit=3,
        )
        self.assertTrue(summary["deferred_body"])
        self.assertIn("[Public preview truncated. Load full message.]", summary["message"])

    def test_build_and_encode_payload_document(self) -> None:
        doc = build_payload_document(
            meta={"session": "demo", "port": 1234},
            filter_agent="claude",
            follow_mode=True,
            targets=["claude-1"],
            has_older=False,
            light_mode=True,
            entries=[{"msg_id": "abc"}],
        )
        payload = encode_payload_document(doc)
        parsed = json.loads(payload.decode("utf-8"))
        self.assertEqual(parsed["session"], "demo")
        self.assertEqual(parsed["filter"], "claude")
        self.assertTrue(parsed["follow"])
        self.assertEqual(parsed["targets"], ["claude-1"])
        self.assertTrue(parsed["light_mode"])
        self.assertEqual(parsed["entries"][0]["msg_id"], "abc")


if __name__ == "__main__":
    unittest.main()
