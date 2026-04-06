from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index.multiagent_state_core import (
    acquire_topology_lock,
    build_state_lines,
    release_topology_lock,
    write_session_state_file,
)
from agent_index.multiagent_topology_core import parse_user_pane_spec


class MultiagentTopologyCoreTests(unittest.TestCase):
    def test_parse_user_pane_spec_accepts_valid_values(self) -> None:
        self.assertEqual(parse_user_pane_spec("none"), (0, 0))
        self.assertEqual(parse_user_pane_spec("top"), (1, 0))
        self.assertEqual(parse_user_pane_spec("bottom:2"), (0, 2))
        self.assertEqual(parse_user_pane_spec("top:3,bottom"), (3, 1))

    def test_parse_user_pane_spec_rejects_invalid_values(self) -> None:
        for bad in ("", "left:1", "top:0", "bottom:-1", "top:abc", "none,bottom:1"):
            with self.assertRaises(ValueError, msg=bad):
                parse_user_pane_spec(bad)


class MultiagentStateCoreTests(unittest.TestCase):
    def test_build_state_lines_uses_agents_and_pane_vars(self) -> None:
        lines = build_state_lines(
            "demo",
            "claude-1,codex",
            "\n".join(
                [
                    "MULTIAGENT_PANE_CLAUDE_1=%11",
                    "MULTIAGENT_PANE_CODEX=%22",
                    "UNRELATED=1",
                ]
            ),
        )
        self.assertEqual(lines[0], "MULTIAGENT_SESSION=demo")
        self.assertEqual(lines[1], "MULTIAGENT_AGENTS=claude-1,codex")
        self.assertIn("MULTIAGENT_PANE_CLAUDE_1=%11", lines)
        self.assertIn("MULTIAGENT_PANE_CODEX=%22", lines)

    def test_write_session_state_file_writes_expected_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.txt"
            write_session_state_file(
                path,
                "demo",
                "claude",
                "MULTIAGENT_PANE_CLAUDE=%13\n",
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("MULTIAGENT_SESSION=demo\n", text)
            self.assertIn("MULTIAGENT_AGENTS=claude\n", text)
            self.assertIn("MULTIAGENT_PANE_CLAUDE=%13\n", text)

    def test_acquire_and_release_topology_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "lockdir"
            self.assertTrue(acquire_topology_lock(lock_path, os.getpid(), max_attempts=2, sleep_seconds=0.0))
            self.assertTrue((lock_path / "pid").exists())
            self.assertFalse(acquire_topology_lock(lock_path, 12345, max_attempts=1, sleep_seconds=0.0))
            release_topology_lock(lock_path)
            self.assertFalse(lock_path.exists())

    def test_acquire_topology_lock_reclaims_stale_holder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "lockdir"
            lock_path.mkdir(parents=True, exist_ok=True)
            (lock_path / "pid").write_text("999999", encoding="utf-8")
            self.assertTrue(acquire_topology_lock(lock_path, os.getpid(), max_attempts=2, sleep_seconds=0.0))
            self.assertEqual((lock_path / "pid").read_text(encoding="utf-8").strip(), str(os.getpid()))


if __name__ == "__main__":
    unittest.main()
