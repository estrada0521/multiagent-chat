from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index.multiagent_launch_core import (
    build_agent_launch_command,
    build_env_exports,
    build_user_launch_command,
)


class MultiagentLaunchCoreTests(unittest.TestCase):
    def test_build_env_exports_with_default_log_dir(self) -> None:
        exports = build_env_exports(
            script_dir="/tmp/bin",
            session_name="demo",
            workspace="/tmp/work",
            tmux_socket="sock",
            index_path="/tmp/work/logs/demo/.agent-index.jsonl",
            agent_name="claude-1",
            log_dir=None,
        )
        self.assertIn("PATH=/tmp/bin:$PATH", exports)
        self.assertIn("MULTIAGENT_SESSION=demo", exports)
        self.assertIn("MULTIAGENT_AGENT_NAME=claude-1", exports)
        self.assertIn("MULTIAGENT_LOG_DIR=/tmp/work/logs", exports)

    def test_build_env_exports_omits_log_dir_when_disabled(self) -> None:
        exports = build_env_exports(
            script_dir="/tmp/bin",
            session_name="demo",
            workspace="/tmp/work",
            tmux_socket="sock",
            index_path="/tmp/work/logs/demo/.agent-index.jsonl",
            log_dir="",
        )
        self.assertNotIn("MULTIAGENT_LOG_DIR=", exports)

    def test_build_agent_launch_command(self) -> None:
        cmd = build_agent_launch_command(
            env_exports="export FOO=1",
            executable="codex",
            launch_extra="--extra",
            launch_flags="--resume",
            launch_env="BAR=2",
        )
        self.assertEqual(cmd, "export FOO=1 BAR=2; exec --extra codex --resume")

    def test_build_user_launch_command(self) -> None:
        cmd = build_user_launch_command(env_exports="export FOO=1", script_dir="/tmp/bin")
        self.assertEqual(cmd, "export FOO=1; exec /tmp/bin/multiagent-user-shell")


if __name__ == "__main__":
    unittest.main()
