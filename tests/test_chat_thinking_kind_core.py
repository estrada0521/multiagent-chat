from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.chat_thinking_kind_core import (
    classify_gemini_message_kind,
    infer_entry_kind,
    strip_sender_prefix,
)


class ChatThinkingKindCoreTests(unittest.TestCase):
    def test_classifies_thought_flag_as_agent_thinking(self) -> None:
        kind = classify_gemini_message_kind(["normal text"], has_thought_part=True)
        self.assertEqual(kind, "agent-thinking")

    def test_classifies_i_will_prefix_as_agent_thinking(self) -> None:
        kind = classify_gemini_message_kind(["I will inspect the project first."])
        self.assertEqual(kind, "agent-thinking")

    def test_non_planning_text_stays_untyped(self) -> None:
        kind = classify_gemini_message_kind(["Here is the final answer."])
        self.assertIsNone(kind)

    def test_strip_sender_prefix(self) -> None:
        body = strip_sender_prefix("[From: gemini]\nI will inspect this.")
        self.assertEqual(body, "I will inspect this.")

    def test_infer_entry_kind_for_non_user_sender(self) -> None:
        kind = infer_entry_kind("claude", "[From: claude]\nI'll check this now.")
        self.assertEqual(kind, "agent-thinking")

    def test_infer_entry_kind_requires_prefix_position(self) -> None:
        kind = infer_entry_kind("codex", "[From: codex] Ping first. I will send details next.")
        self.assertIsNone(kind)

    def test_infer_entry_kind_skips_user_and_system(self) -> None:
        self.assertIsNone(infer_entry_kind("user", "I will do this."))
        self.assertIsNone(infer_entry_kind("system", "I will do this."))


if __name__ == "__main__":
    unittest.main()
