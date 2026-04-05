from __future__ import annotations

import os
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index.chat_core import (
    _extract_pane_runtime_events,
    _pane_runtime_line_allowed,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    path = FIXTURES_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class PaneRuntimeParserTests(unittest.TestCase):
    """Fixture-based tests for pane runtime event extraction.

    Each test loads a real pane capture and asserts structural invariants
    that should hold regardless of CLI version changes.
    """

    def test_claude_events_have_valid_structure(self) -> None:
        content = _load_fixture("pane_claude.txt")
        if not content.strip():
            self.skipTest("fixture not available")
        events = _extract_pane_runtime_events("claude", content)
        for event in events:
            self.assertIn("kind", event)
            self.assertIn(event["kind"], ("fixed", "stream"))
            self.assertIn("text", event)
            self.assertTrue(event["text"].strip())
            self.assertIn("source_id", event)
            self.assertTrue(event["source_id"].strip())

    def test_codex_events_have_valid_structure(self) -> None:
        content = _load_fixture("pane_codex-1.txt")
        if not content.strip():
            self.skipTest("fixture not available")
        events = _extract_pane_runtime_events("codex-1", content)
        for event in events:
            self.assertIn("kind", event)
            self.assertIn(event["kind"], ("fixed", "stream"))
            self.assertIn("text", event)
            self.assertTrue(event["text"].strip())

    def test_gemini_events_have_valid_structure(self) -> None:
        content = _load_fixture("pane_gemini-1.txt")
        if not content.strip():
            self.skipTest("fixture not available")
        events = _extract_pane_runtime_events("gemini-1", content)
        for event in events:
            self.assertIn("kind", event)
            self.assertIn(event["kind"], ("fixed", "stream"))
            self.assertIn("text", event)
            self.assertTrue(event["text"].strip())

    def test_cursor_events_have_valid_structure(self) -> None:
        content = _load_fixture("pane_cursor-1.txt")
        if not content.strip():
            self.skipTest("fixture not available")
        events = _extract_pane_runtime_events("cursor-1", content)
        for event in events:
            self.assertIn("kind", event)
            self.assertIn(event["kind"], ("fixed", "stream"))
            self.assertIn("text", event)
            self.assertTrue(event["text"].strip())

    def test_copilot_events_have_valid_structure(self) -> None:
        content = _load_fixture("pane_copilot-1.txt")
        if not content.strip():
            self.skipTest("fixture not available")
        events = _extract_pane_runtime_events("copilot-1", content)
        for event in events:
            self.assertIn("kind", event)
            self.assertIn(event["kind"], ("fixed", "stream"))
            self.assertIn("text", event)
            self.assertTrue(event["text"].strip())

    def test_empty_content_returns_no_events(self) -> None:
        for agent in ("claude", "codex", "gemini", "cursor", "copilot"):
            events = _extract_pane_runtime_events(agent, "")
            self.assertEqual(events, [], f"expected no events for {agent} with empty input")

    def test_unknown_agent_returns_no_events(self) -> None:
        events = _extract_pane_runtime_events("unknown-agent", "some pane content\nmore lines")
        self.assertEqual(events, [])

    def test_event_count_respects_limit(self) -> None:
        content = _load_fixture("pane_codex-1.txt")
        if not content.strip():
            self.skipTest("fixture not available")
        limited = _extract_pane_runtime_events("codex-1", content, limit=3)
        self.assertLessEqual(len(limited), 3)

    def test_source_ids_include_occurrence_suffix(self) -> None:
        content = _load_fixture("pane_codex-1.txt")
        if not content.strip():
            self.skipTest("fixture not available")
        events = _extract_pane_runtime_events("codex-1", content)
        for event in events:
            source_id = event.get("source_id", "")
            self.assertRegex(source_id, r"#\d+$", f"source_id missing occurrence suffix: {source_id}")


class PaneRuntimeLineFilterTests(unittest.TestCase):
    """Tests for the line-level filter that excludes noise."""

    def test_rejects_empty_and_whitespace(self) -> None:
        self.assertFalse(_pane_runtime_line_allowed(""))
        self.assertFalse(_pane_runtime_line_allowed("   "))

    def test_rejects_working_lines(self) -> None:
        self.assertFalse(_pane_runtime_line_allowed("Currently working on the task"))

    def test_rejects_esc_to_cancel(self) -> None:
        self.assertFalse(_pane_runtime_line_allowed("Press Esc to cancel"))

    def test_rejects_claude_noise(self) -> None:
        self.assertFalse(_pane_runtime_line_allowed("✻ Summary of changes", agent="claude"))
        self.assertFalse(_pane_runtime_line_allowed("Tip: Use /help for more", agent="claude"))

    def test_rejects_claude_token_lines(self) -> None:
        self.assertFalse(_pane_runtime_line_allowed("Used 1234 tokens in this response", agent="claude"))

    def test_accepts_normal_tool_lines(self) -> None:
        self.assertTrue(_pane_runtime_line_allowed("⏺ Read lib/agent_index/hub_core.py"))
        self.assertTrue(_pane_runtime_line_allowed("· Ran python3 -m unittest"))


class PaneRuntimeSyntheticTests(unittest.TestCase):
    """Tests against synthetic pane output to pin parser behavior."""

    def test_claude_tool_call_extraction(self) -> None:
        content = "\n".join([
            "⏺ Read lib/agent_index/hub_core.py",
            "  Reading 120 lines from offset 840",
            "",
            "⏺ Edit lib/agent_index/hub_core.py",
            "  ⎿ Updated stop_chat_server return type",
            "",
            "⏺ Bash",
            "  ⎿ python3 -m unittest discover -s tests",
        ])
        events = _extract_pane_runtime_events("claude", content)
        self.assertGreaterEqual(len(events), 2)
        texts = [e["text"] for e in events]
        self.assertTrue(any("hub_core.py" in t for t in texts))

    def test_codex_tool_call_extraction(self) -> None:
        content = "\n".join([
            "· Ran python3 -m unittest discover -s tests",
            "· Edited lib/agent_index/hub_core.py",
            "· Explored tests/",
        ])
        events = _extract_pane_runtime_events("codex", content)
        self.assertEqual(len(events), 3)
        self.assertIn("Ran", events[0]["text"])
        self.assertIn("Edited", events[1]["text"])
        self.assertIn("Explored", events[2]["text"])

    def test_gemini_tool_call_extraction(self) -> None:
        content = "\n".join([
            "│ ✓ ReadFile lib/agent_index/hub_core.py                │",
            "│ ✓ Edit lib/agent_index/hub_core.py                    │",
            "│ ✓ Shell python3 -m unittest discover -s tests          │",
        ])
        events = _extract_pane_runtime_events("gemini", content)
        self.assertGreaterEqual(len(events), 3)
        labels = [e["text"] for e in events]
        self.assertTrue(any("ReadFile" in l for l in labels))
        self.assertTrue(any("Edit" in l for l in labels))
        self.assertTrue(any("Shell" in l for l in labels))

    def test_gemini_thought_extraction(self) -> None:
        content = "\n".join([
            "✦ Analyzing the exception handling patterns",
            "  across hub_core.py to classify each catch block",
            "",
            "│ ✓ ReadFile lib/agent_index/hub_core.py                │",
        ])
        events = _extract_pane_runtime_events("gemini", content)
        thought_events = [e for e in events if "✦" in e["text"]]
        self.assertGreaterEqual(len(thought_events), 1)

    def test_gemini_thought_interleaved_before_tools_in_tail(self) -> None:
        """Chronological merge: last N events must include ✦, not only trailing tool rows."""
        blocks = []
        for i in range(16):
            blocks.append(f"✦ step {i}\n  continuation {i}")
            blocks.append(f"│ ✓ ReadFile module{i}.py │")
        content = "\n".join(blocks)
        events = _extract_pane_runtime_events("gemini", content, limit=12)
        self.assertTrue(any("✦" in e["text"] for e in events), events)

    def test_gemini_latest_thought_kept_after_long_tool_run(self) -> None:
        """If the pane ends with many tools after the last ✦, shift the window to include that ✦."""
        tools = "\n".join([f"│ ✓ ReadFile path/file{i:02d}.py │" for i in range(22)])
        content = "✦ Final planning line before tools\n  second line of thought\n" + tools
        events = _extract_pane_runtime_events("gemini", content, limit=12)
        self.assertTrue(
            any("Final planning" in e["text"] for e in events),
            [e.get("text") for e in events],
        )

    def test_gemini_thought_stops_at_frame_separator(self) -> None:
        content = "\n".join([
            "✦ Should not include frame chars",
            "▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀",
            "next line",
        ])
        events = _extract_pane_runtime_events("gemini", content, limit=8)
        thought = next((e["text"] for e in events if "✦" in e["text"]), "")
        self.assertNotIn("▀", thought)
        self.assertNotIn("next line", thought)

    def test_cursor_tool_call_extraction(self) -> None:
        content = "\n".join([
            "⬢ Read lib/agent_index/hub_core.py",
            "⬢ Grepped _extract_pane_runtime",
        ])
        events = _extract_pane_runtime_events("cursor", content)
        self.assertGreaterEqual(len(events), 2)

    def test_copilot_bullet_extraction(self) -> None:
        content = "\n".join([
            "⏺ Reading lib/agent_index/hub_core.py",
            "● Searching for exception handling patterns",
        ])
        events = _extract_pane_runtime_events("copilot", content)
        self.assertGreaterEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
