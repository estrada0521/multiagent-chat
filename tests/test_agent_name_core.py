from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.agent_name_core import agent_base_name, agent_instance_number


class AgentNameCoreTests(unittest.TestCase):
    def test_agent_base_name_normalizes_case_and_instance(self) -> None:
        self.assertEqual(agent_base_name("Claude-2"), "claude")

    def test_agent_base_name_keeps_plain_name(self) -> None:
        self.assertEqual(agent_base_name("gemini"), "gemini")

    def test_agent_instance_number_parses_suffix(self) -> None:
        self.assertEqual(agent_instance_number("cursor-12"), 12)

    def test_agent_instance_number_returns_none_for_base_name(self) -> None:
        self.assertIsNone(agent_instance_number("qwen"))


if __name__ == "__main__":
    unittest.main()
