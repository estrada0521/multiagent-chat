from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.multiagent_agent_core import (
    agents_to_csv,
    append_instance,
    next_instance_name,
    parse_agents_csv,
    remove_instance,
    renumber_exact_instance,
    resolve_canonical_instance,
)


class MultiagentAgentCoreTests(unittest.TestCase):
    def test_parse_and_serialize_agents_csv(self) -> None:
        self.assertEqual(parse_agents_csv(""), [])
        self.assertEqual(parse_agents_csv("-"), [])
        self.assertEqual(parse_agents_csv("claude-1, codex ,"), ["claude-1", "codex"])
        self.assertEqual(agents_to_csv(["claude-1", "codex"]), "claude-1,codex")

    def test_next_instance_name(self) -> None:
        self.assertEqual(next_instance_name([], "claude"), "claude")
        self.assertEqual(next_instance_name(["claude"], "claude"), "claude-2")
        self.assertEqual(next_instance_name(["claude-1", "claude-2"], "claude"), "claude-3")
        self.assertEqual(next_instance_name(["claude-2", "claude-x"], "claude"), "claude-3")

    def test_renumber_exact_instance(self) -> None:
        updated, rename = renumber_exact_instance(["claude", "codex"], "claude")
        self.assertEqual(updated, ["claude-1", "codex"])
        self.assertEqual(rename, ("claude", "claude-1"))

        unchanged, no_rename = renumber_exact_instance(["claude", "claude-1"], "claude")
        self.assertEqual(unchanged, ["claude", "claude-1"])
        self.assertIsNone(no_rename)

    def test_resolve_and_remove_instance(self) -> None:
        agents = ["claude-1", "Codex-2", "gemini"]
        self.assertEqual(resolve_canonical_instance(agents, "codex-2"), "Codex-2")
        self.assertIsNone(resolve_canonical_instance(agents, "qwen"))
        self.assertEqual(remove_instance(agents, "Codex-2"), ["claude-1", "gemini"])

    def test_append_instance(self) -> None:
        self.assertEqual(append_instance(["claude-1"], "codex"), ["claude-1", "codex"])
        self.assertEqual(append_instance([], ""), [])


if __name__ == "__main__":
    unittest.main()
