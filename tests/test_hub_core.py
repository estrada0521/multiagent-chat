from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.hub_core import HubRuntime


class HubCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name) / "repo"
        (self.repo_root / "bin").mkdir(parents=True)
        (self.repo_root / "logs").mkdir()
        self.runtime = HubRuntime(
            self.repo_root,
            self.repo_root / "bin" / "agent-index",
            "test-socket",
            hub_port=8788,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_chat_launch_env_sets_flags_and_preserves_pythonpath(self) -> None:
        with patch.dict(os.environ, {"PYTHONPATH": "/existing/path"}, clear=False):
            env = self.runtime._chat_launch_env()
        self.assertEqual(env["MULTIAGENT_TMUX_SOCKET"], "test-socket")
        self.assertEqual(env["SESSION_IS_ACTIVE"], "1")
        self.assertEqual(
            env["PYTHONPATH"],
            os.pathsep.join(
                [
                    str(self.runtime.repo_root / "lib"),
                    str(self.runtime.repo_root),
                    "/existing/path",
                ]
            ),
        )

    def test_chat_launch_workspace_prefers_tmux_value(self) -> None:
        with patch.object(self.runtime, "tmux_env_query", return_value=("/tmp/workspace", False)):
            workspace, timed_out = self.runtime._chat_launch_workspace("demo")
        self.assertEqual(workspace, "/tmp/workspace")
        self.assertFalse(timed_out)

    def test_chat_launch_session_dir_prefers_repo_logs(self) -> None:
        repo_session_dir = self.runtime.repo_root / "logs" / "demo"
        repo_session_dir.mkdir()
        session_dir = self.runtime._chat_launch_session_dir("demo", "/tmp/workspace", "/tmp/workspace/logs")
        self.assertEqual(session_dir, repo_session_dir)

    def test_ensure_chat_server_reuses_matching_running_server(self) -> None:
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch.object(
            self.runtime, "chat_ready", return_value=True
        ), patch.object(self.runtime, "chat_server_matches", return_value=True), patch(
            "agent_index.hub_core.subprocess.Popen"
        ) as popen_mock:
            ok, port, detail = self.runtime.ensure_chat_server("demo")
        self.assertTrue(ok)
        self.assertEqual(port, 8123)
        self.assertEqual(detail, "")
        popen_mock.assert_not_called()

    def test_ensure_chat_server_launches_python_module_directly(self) -> None:
        session_dir = self.repo_root / "logs" / "demo"
        session_dir.mkdir()
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch.object(
            self.runtime, "chat_ready", side_effect=[False, True]
        ), patch("agent_index.hub_core.port_is_bindable", return_value=True), patch.object(
            self.runtime, "_chat_launch_workspace", return_value=("/tmp/workspace", False)
        ), patch.object(
            self.runtime, "tmux_env_query", return_value=("/tmp/workspace/logs", False)
        ), patch.object(
            self.runtime, "session_agents_query", return_value=(["claude", "codex"], False)
        ), patch.object(
            self.runtime, "_chat_launch_session_dir", return_value=session_dir
        ), patch(
            "agent_index.hub_core.subprocess.Popen"
        ) as popen_mock:
            ok, port, detail = self.runtime.ensure_chat_server("demo")

        self.assertTrue(ok)
        self.assertEqual(port, 8123)
        self.assertEqual(detail, "")
        args, kwargs = popen_mock.call_args
        self.assertEqual(
            args[0],
            [
                sys.executable,
                "-m",
                "agent_index.chat_server",
                str(session_dir / ".agent-index.jsonl"),
                "2000",
                "",
                "demo",
                "1",
                "8123",
                str(self.runtime.agent_send_path),
                "/tmp/workspace",
                str(session_dir.parent),
                "claude,codex",
                "test-socket",
                "8788",
            ],
        )
        self.assertEqual(kwargs["cwd"], "/tmp/workspace")
        self.assertEqual(kwargs["env"]["SESSION_IS_ACTIVE"], "1")
        self.assertIn("PYTHONPATH", kwargs["env"])


if __name__ == "__main__":
    unittest.main()
