from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.hub_core import HubRuntime
from agent_index.hub_session_query_core import latest_message_preview


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

    def test_chat_launch_session_dir_migrates_existing_index_to_repo_logs(self) -> None:
        external_session_dir = Path(self.tempdir.name) / "workspace-logs" / "demo"
        external_session_dir.mkdir(parents=True, exist_ok=True)
        external_index = external_session_dir / ".agent-index.jsonl"
        external_index.write_text('{"sender":"user","message":"x"}\n', encoding="utf-8")
        with patch.object(self.runtime, "session_index_path", return_value=external_index):
            session_dir = self.runtime._chat_launch_session_dir("demo", "/tmp/workspace", "/tmp/workspace/logs")
        self.assertEqual(session_dir, self.runtime.repo_root / "logs" / "demo")
        canonical_index = session_dir / ".agent-index.jsonl"
        self.assertTrue(canonical_index.exists())
        self.assertIn('"message":"x"', canonical_index.read_text(encoding="utf-8"))

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

    def test_ensure_chat_server_reuses_matching_fallback_port_when_default_is_occupied(self) -> None:
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch.object(
            self.runtime, "chat_ready", side_effect=lambda port: port == 8124
        ), patch.object(
            self.runtime, "chat_server_matches", return_value=True
        ), patch(
            "agent_index.hub_core.port_is_bindable", return_value=False
        ), patch(
            "agent_index.hub_core.save_chat_port_override"
        ) as save_override, patch(
            "agent_index.hub_core.subprocess.Popen"
        ) as popen_mock:
            ok, port, detail = self.runtime.ensure_chat_server("demo")

        self.assertTrue(ok)
        self.assertEqual(port, 8124)
        self.assertEqual(detail, "")
        save_override.assert_called_once_with(self.runtime.repo_root, "demo", 8124)
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
        argv = args[0]
        # Pin only the launch invariants that matter to this boundary test.
        self.assertEqual(argv[:3], [sys.executable, "-m", "agent_index.chat_server"])
        self.assertEqual(argv[3], str(session_dir / ".agent-index.jsonl"))
        self.assertIn("2000", argv)
        self.assertIn("demo", argv)
        self.assertIn("1", argv)
        self.assertIn("8123", argv)
        self.assertIn(str(self.runtime.agent_send_path), argv)
        self.assertIn("/tmp/workspace", argv)
        self.assertIn(str(session_dir.parent), argv)
        self.assertIn("claude,codex", argv)
        self.assertEqual(argv[-2:], ["test-socket", "8788"])
        self.assertEqual(kwargs["cwd"], "/tmp/workspace")
        self.assertEqual(kwargs["env"]["SESSION_IS_ACTIVE"], "1")
        self.assertIn("PYTHONPATH", kwargs["env"])

    def test_chat_server_matches_treats_unavailable_state_as_match(self) -> None:
        with patch.object(self.runtime, "chat_server_state", return_value=None):
            self.assertTrue(self.runtime.chat_server_matches("demo", 8123))

    def test_ensure_chat_server_returns_timeout_error_when_tmux_query_times_out(self) -> None:
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch.object(
            self.runtime, "chat_ready", return_value=False
        ), patch(
            "agent_index.hub_core.port_is_bindable", return_value=True
        ), patch.object(
            self.runtime, "_chat_launch_workspace", return_value=("/tmp/workspace", True)
        ), patch.object(
            self.runtime, "tmux_env_query", return_value=("/tmp/workspace/logs", False)
        ), patch.object(
            self.runtime, "session_agents_query", return_value=(["claude"], False)
        ), patch(
            "agent_index.hub_core.subprocess.Popen"
        ) as popen_mock:
            ok, port, detail = self.runtime.ensure_chat_server("demo")

        self.assertFalse(ok)
        self.assertEqual(port, 8123)
        self.assertEqual(detail, "tmux query timed out while preparing chat server launch")
        popen_mock.assert_not_called()

    def test_ensure_chat_server_returns_error_when_server_never_becomes_ready(self) -> None:
        session_dir = self.repo_root / "logs" / "demo"
        session_dir.mkdir()
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch.object(
            self.runtime, "chat_ready", return_value=False
        ), patch("agent_index.hub_core.port_is_bindable", return_value=True), patch.object(
            self.runtime, "_chat_launch_workspace", return_value=("/tmp/workspace", False)
        ), patch.object(
            self.runtime, "tmux_env_query", return_value=("/tmp/workspace/logs", False)
        ), patch.object(
            self.runtime, "session_agents_query", return_value=(["claude"], False)
        ), patch.object(
            self.runtime, "_chat_launch_session_dir", return_value=session_dir
        ), patch(
            "agent_index.hub_core.time.sleep"
        ), patch(
            "agent_index.hub_core.subprocess.Popen"
        ) as popen_mock:
            ok, port, detail = self.runtime.ensure_chat_server("demo")

        self.assertFalse(ok)
        self.assertEqual(port, 8123)
        self.assertEqual(detail, "chat server did not become ready")
        launch_calls = [
            c for c in popen_mock.call_args_list
            if c and c[0] and isinstance(c[0][0], list) and "agent_index.chat_server" in c[0][0]
        ]
        self.assertEqual(len(launch_calls), 1)


    def test_stop_chat_server_returns_success_when_no_process_listening(self) -> None:
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch(
            "agent_index.hub_core.subprocess.run",
            return_value=type("R", (), {"stdout": "", "returncode": 0})(),
        ):
            ok, detail = self.runtime.stop_chat_server("demo")
        self.assertTrue(ok)
        self.assertEqual(detail, "")

    def test_stop_chat_server_returns_failure_when_lsof_fails(self) -> None:
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch(
            "agent_index.hub_core.subprocess.run",
            side_effect=OSError("lsof not found"),
        ):
            ok, detail = self.runtime.stop_chat_server("demo")
        self.assertFalse(ok)
        self.assertIn("lsof failed", detail)

    def test_stop_chat_server_returns_failure_when_process_survives_sigkill(self) -> None:
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch(
            "agent_index.hub_core.subprocess.run",
            return_value=type("R", (), {"stdout": "12345\n", "returncode": 0})(),
        ), patch("agent_index.hub_core.os.kill") as kill_mock, patch.object(
            self.runtime, "chat_ready", return_value=True
        ), patch("agent_index.hub_core.time.sleep"):
            ok, detail = self.runtime.stop_chat_server("demo")
        self.assertFalse(ok)
        self.assertIn("still running", detail)
        sigterm_calls = [c for c in kill_mock.call_args_list if c[0][1] == signal.SIGTERM]
        sigkill_calls = [c for c in kill_mock.call_args_list if c[0][1] == signal.SIGKILL]
        self.assertEqual(len(sigterm_calls), 1)
        self.assertEqual(len(sigkill_calls), 1)

    def test_ensure_chat_server_continues_launch_after_stop_failure(self) -> None:
        session_dir = self.repo_root / "logs" / "demo"
        session_dir.mkdir()
        with patch.object(self.runtime, "chat_port_for_session", return_value=8123), patch.object(
            self.runtime, "chat_ready", side_effect=[True, False, True]
        ), patch.object(
            self.runtime, "chat_server_matches", return_value=False
        ), patch.object(
            self.runtime, "stop_chat_server", return_value=(False, "lsof failed")
        ), patch("agent_index.hub_core.port_is_bindable", return_value=True), patch.object(
            self.runtime, "_chat_launch_workspace", return_value=("/tmp/workspace", False)
        ), patch.object(
            self.runtime, "tmux_env_query", return_value=("/tmp/workspace/logs", False)
        ), patch.object(
            self.runtime, "session_agents_query", return_value=(["claude"], False)
        ), patch.object(
            self.runtime, "_chat_launch_session_dir", return_value=session_dir
        ), patch(
            "agent_index.hub_core.subprocess.Popen"
        ) as popen_mock:
            ok, port, detail = self.runtime.ensure_chat_server("demo")

        self.assertTrue(ok)
        self.assertEqual(port, 8123)
        launch_calls = [
            c for c in popen_mock.call_args_list
            if c and c[0] and isinstance(c[0][0], list) and "agent_index.chat_server" in c[0][0]
        ]
        self.assertEqual(len(launch_calls), 1)

    def test_build_session_record_preview_prefers_primary_index(self) -> None:
        primary_dir = self.repo_root / "logs" / "demo"
        primary_dir.mkdir(parents=True, exist_ok=True)
        secondary_dir = Path(self.tempdir.name) / "workspace-logs" / "demo"
        secondary_dir.mkdir(parents=True, exist_ok=True)
        primary_index = primary_dir / ".agent-index.jsonl"
        secondary_index = secondary_dir / ".agent-index.jsonl"
        primary_index.write_text(
            json.dumps({
                "sender": "cursor",
                "message": "[From: cursor]\nテスト受信できました。",
            }) + "\n",
            encoding="utf-8",
        )
        secondary_index.write_text(
            json.dumps({
                "sender": "user",
                "message": "[From: User]\ntest",
            }) + "\n",
            encoding="utf-8",
        )
        now = time.time()
        os.utime(primary_index, (now, now))
        os.utime(secondary_index, (now + 60, now + 60))

        record = self.runtime._build_session_record(
            name="demo",
            workspace="/tmp/workspace",
            agents=["cursor"],
            status="attached",
            attached=1,
            dead_panes=0,
            explicit_log_dir=str(secondary_dir),
            index_paths=[secondary_index, primary_index],
            preferred_index_path=primary_index,
        )
        self.assertEqual(record["index_path"], str(primary_index))
        self.assertEqual(record["latest_message_sender"], "cursor")
        self.assertEqual(record["latest_message_preview"], "テスト受信できました。")

    def test_latest_message_preview_skips_malformed_jsonl_without_error_log(self) -> None:
        session_dir = self.repo_root / "logs" / "demo"
        session_dir.mkdir(parents=True, exist_ok=True)
        index_path = session_dir / ".agent-index.jsonl"
        index_path.write_text(
            "\n".join(
                [
                    '{"sender":"user","message":"broken',
                    json.dumps({"sender": "gemini", "message": "[From: gemini]\nReload finished"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        with patch("agent_index.hub_session_query_core.logging.error") as error_mock:
            preview = latest_message_preview(index_path)

        self.assertEqual(preview, {"sender": "gemini", "text": "Reload finished"})
        error_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
