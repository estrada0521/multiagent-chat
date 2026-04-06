from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index.session_path_core import (
    default_tmux_socket_name,
    multiagent_panes_state_path,
    session_topology_lock_path,
)


class SessionPathCoreTests(unittest.TestCase):
    def test_default_tmux_socket_name_uses_repo_realpath_hash(self) -> None:
        repo_root = Path(_bootstrap.REPO_ROOT).resolve()
        expected = f"multiagent-{hashlib.sha1(str(repo_root).encode('utf-8')).hexdigest()[:12]}"
        self.assertEqual(default_tmux_socket_name(repo_root), expected)

    def test_multiagent_panes_state_path_for_named_socket(self) -> None:
        path = multiagent_panes_state_path("multiagent-abc", "demo/session")
        self.assertEqual(str(path), "/tmp/multiagent_multiagent-abc_demo_session_panes")

    def test_multiagent_paths_for_absolute_socket_use_hashed_prefix(self) -> None:
        socket_path = "/tmp/tmux-1000/default"
        session = "demo"
        digest = hashlib.sha1(f"{socket_path}|{session}".encode("utf-8")).hexdigest()[:20]
        self.assertEqual(
            str(multiagent_panes_state_path(socket_path, session)),
            f"/tmp/multiagent_sock_{digest}_panes",
        )
        self.assertEqual(
            str(session_topology_lock_path(socket_path, session)),
            f"/tmp/multiagent_sock_{digest}_topology.lock",
        )


if __name__ == "__main__":
    unittest.main()
