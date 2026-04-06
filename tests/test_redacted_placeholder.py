from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import _bootstrap  # noqa: F401
from agent_index.redacted_placeholder import (
    REDACTED_TOKEN,
    agent_index_entry_omit_for_redacted,
    compact_agent_index_jsonl,
    normalize_cursor_plaintext_for_index,
    rewrite_agent_index_message_strip_trailing_redacted,
)


class RedactedPlaceholderTests(unittest.TestCase):
    def test_normalize_skips_only_redacted(self) -> None:
        self.assertIsNone(normalize_cursor_plaintext_for_index(REDACTED_TOKEN))
        self.assertIsNone(normalize_cursor_plaintext_for_index("  " + REDACTED_TOKEN + "  "))
        self.assertEqual(normalize_cursor_plaintext_for_index("hi"), "hi")
        self.assertEqual(normalize_cursor_plaintext_for_index("hi" + REDACTED_TOKEN), "hi")

    def test_normalize_empty_after_suffix(self) -> None:
        self.assertIsNone(normalize_cursor_plaintext_for_index("  " + REDACTED_TOKEN))

    def test_omit_index_row_with_from_prefix(self) -> None:
        msg = "[From: cursor-1]\n" + REDACTED_TOKEN
        self.assertTrue(agent_index_entry_omit_for_redacted(msg))
        self.assertFalse(agent_index_entry_omit_for_redacted("[From: cursor-1]\nhello"))
        self.assertFalse(agent_index_entry_omit_for_redacted("[From: cursor-1]\nhello" + REDACTED_TOKEN))

    def test_rewrite_trailing(self) -> None:
        self.assertEqual(
            rewrite_agent_index_message_strip_trailing_redacted("[From: a]\nfoo" + REDACTED_TOKEN),
            "[From: a]\nfoo",
        )
        self.assertIsNone(rewrite_agent_index_message_strip_trailing_redacted("[From: a]\nfoo"))

    def test_compact_jsonl(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / ".agent-index.jsonl"
            rows = [
                {"msg_id": "1", "message": "[From: c]\n" + REDACTED_TOKEN, "sender": "c"},
                {"msg_id": "2", "message": "[From: c]\nok" + REDACTED_TOKEN, "sender": "c"},
                {"msg_id": "3", "message": "[From: c]\nkeep", "sender": "c"},
            ]
            p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
            kept, removed, rewritten = compact_agent_index_jsonl(p)
            self.assertEqual(removed, 1)
            self.assertEqual(rewritten, 1)
            self.assertEqual(kept, 2)
            out = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(out), 2)
            self.assertEqual(out[0]["message"], "[From: c]\nok")
            self.assertEqual(out[1]["message"], "[From: c]\nkeep")


if __name__ == "__main__":
    unittest.main()
