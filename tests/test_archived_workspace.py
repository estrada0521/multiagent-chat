from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend_core.access.session_meta import write_session_meta_file
from hub_backend.chat_supervisor import chat_server_state_matches, ensure_chat_server
from hub_backend.session_api import resolve_session_chat_target
from hub_backend.session_query import archived_sessions
from workspace_sync import git as workspace_git


class _Query:
    def __init__(self, records, warnings, state="ok", detail=""):
        self.records = records
        self.warnings = warnings
        self.state = state
        self.detail = detail

    @property
    def non_archived_names(self):
        return set(self.records) | set(self.warnings)


class ArchivedWorkspaceTests(unittest.TestCase):
    def test_hub_reload_stops_archived_chat_servers_before_restart(self) -> None:
        from hub_backend import hub_server

        fake_hub = object()
        with (
            patch.object(hub_server, "hub", fake_hub),
            patch.object(hub_server, "stop_inactive_chat_servers", return_value=""),
            patch.object(hub_server, "restart_pending", False),
            patch.object(hub_server, "_launch_hub_restart_impl", return_value=True) as launch,
        ):
            ok, detail, owns_restart = hub_server.queue_hub_restart()
            self.assertTrue(hub_server.restart_pending)

        self.assertTrue(ok)
        self.assertEqual(detail, "")
        self.assertTrue(owns_restart)
        launch.assert_called_once()

    def test_hub_reload_does_not_restart_when_archived_cleanup_fails(self) -> None:
        from hub_backend import hub_server

        fake_hub = object()
        with (
            patch.object(hub_server, "hub", fake_hub),
            patch.object(hub_server, "stop_inactive_chat_servers", return_value="cleanup failed"),
            patch.object(hub_server, "restart_pending", False),
            patch.object(hub_server, "_launch_hub_restart_impl") as launch,
        ):
            ok, detail, owns_restart = hub_server.queue_hub_restart()
            self.assertFalse(hub_server.restart_pending)

        self.assertFalse(ok)
        self.assertEqual(detail, "cleanup failed")
        self.assertFalse(owns_restart)
        launch.assert_not_called()

    def test_warning_session_meta_is_not_reparsed_as_archived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "broken-session"
            session_dir.mkdir()
            (session_dir / ".meta").write_text("[]", encoding="utf-8")
            with patch("hub_backend.session_query.agent_window_session_root", return_value=root):
                sessions = archived_sessions(excluded_names={"broken-session"})

            self.assertEqual(sessions, [])

    def test_archived_sessions_keep_logs_when_meta_has_no_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "Even-Parity"
            session_dir.mkdir()
            (session_dir / ".log.jsonl").write_text("", encoding="utf-8")
            (session_dir / ".meta").write_text(
                json.dumps(
                    {
                        "session": "Even-Parity",
                        "agents": ["codex"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            hub_repo = "/Users/okadaharuto/workspace/Agent-Window"
            with patch("hub_backend.session_query.agent_window_session_root", return_value=root):
                sessions = archived_sessions(excluded_names=set())
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["name"], "Even-Parity")
            self.assertEqual(sessions[0]["workspace"], "")
            self.assertNotEqual(sessions[0]["workspace"], hub_repo)

    def test_archived_sessions_keep_logs_when_meta_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "Broken"
            session_dir.mkdir()
            (session_dir / ".log.jsonl").write_text("", encoding="utf-8")
            with patch("hub_backend.session_query.agent_window_session_root", return_value=root):
                sessions = archived_sessions(excluded_names=set())
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["name"], "Broken")
            self.assertEqual(sessions[0]["workspace"], "")

    def test_archived_sessions_keep_a_non_git_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "Lab-workspace"
            workspace.mkdir()
            session_dir = root / "Lab"
            session_dir.mkdir()
            (session_dir / ".log.jsonl").write_text("", encoding="utf-8")
            (session_dir / ".meta").write_text(
                json.dumps(
                    {
                        "workspace": str(workspace),
                        "agents": ["codex"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            hub_repo = "/Users/okadaharuto/workspace/Agent-Window"
            with patch("hub_backend.session_query.agent_window_session_root", return_value=root):
                sessions = archived_sessions(excluded_names=set())
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["name"], "Lab")
            self.assertEqual(sessions[0]["workspace"], str(workspace))
            self.assertNotEqual(sessions[0]["workspace"], hub_repo)
            self.assertFalse((workspace / ".git").exists())

    def test_write_session_meta_does_not_keep_an_old_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "Lab"
            session_dir.mkdir()
            meta_path = session_dir / ".meta"
            meta_path.write_text(
                json.dumps({"workspace": "/old/lab"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "AGENT_WINDOW_WORKSPACE"):
                write_session_meta_file("Lab", "codex", "")
            self.assertEqual(json.loads(meta_path.read_text(encoding="utf-8"))["workspace"], "/old/lab")

    def test_archived_open_passes_saved_workspace_not_hub_root(self) -> None:
        captured = {}

        def ensure_chat_server(_hub, *, expected_active=True, workspace=""):
            captured["expected_active"] = expected_active
            captured["workspace"] = workspace
            return True, 8206, ""

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "Even-Parity"
            workspace.mkdir()
            with (
                patch("hub_backend.session_api.active_session_records_query", return_value=_Query({}, {})),
                patch(
                    "hub_backend.session_api.archived_session_records",
                    return_value={
                        "Even-Parity": {
                            "name": "Even-Parity",
                            "workspace": str(workspace),
                        }
                    },
                ),
                patch("hub_backend.session_api.ensure_chat_server", side_effect=ensure_chat_server),
            ):
                resolved = resolve_session_chat_target(object(), "Even-Parity")
        self.assertEqual(resolved["status"], "ok")
        self.assertFalse(captured["expected_active"])
        self.assertEqual(captured["workspace"], str(workspace))
        self.assertNotEqual(captured["workspace"], "/Users/okadaharuto/workspace/Agent-Window")

    def test_chat_server_state_rejects_wrong_workspace(self) -> None:
        repo_root = "/Users/okadaharuto/workspace/Agent-Window"
        state = {
            "session": "Even-Parity",
            "repo_root": repo_root,
            "workspace": repo_root,
            "targets": [],
            "active": False,
        }
        hub = SimpleNamespace(
            repo_root=Path(repo_root),
        )
        self.assertFalse(
            chat_server_state_matches(
                hub,
                state,
                workspace="/Users/okadaharuto/workspace/Even-Parity",
            )
        )
        self.assertFalse(chat_server_state_matches(hub, state, workspace=""))
        self.assertTrue(
            chat_server_state_matches(
                hub,
                state,
                workspace=repo_root,
            )
        )

    def test_archived_launch_argv_is_the_saved_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "Even-Parity"
            workspace.mkdir()
            hub = SimpleNamespace(
                repo_root=Path("/Users/okadaharuto/workspace/Agent-Window"),
                _get_launch_lock=lambda _name: threading.Lock(),
            )
            with (
                patch("hub_backend.chat_supervisor.workspace_chat_port", return_value=8206),
                patch("hub_backend.chat_supervisor.port_is_bindable", return_value=True),
                patch("hub_backend.chat_supervisor.chat_server_state", return_value=None),
                patch("hub_backend.chat_supervisor.stop_inactive_chat_servers", return_value=""),
                patch("hub_backend.chat_supervisor.chat_launch_env", return_value={}),
                patch("hub_backend.chat_supervisor.launch_chat_server", return_value=object()) as launch,
                patch("hub_backend.chat_supervisor.wait_for_chat_server", return_value=True),
            ):
                ok, port, detail = ensure_chat_server(
                    hub,
                    expected_active=False,
                    workspace=str(workspace),
                )
        self.assertTrue(ok)
        self.assertEqual(port, 8206)
        self.assertEqual(detail, "")
        self.assertEqual(launch.call_args.args, (str(workspace.resolve()),))

    def test_chat_launch_cwd_is_not_a_workspace_that_contains_server_py(self) -> None:
        from server.chat_process import launch_chat_server

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "xray-structure-factor"
            workspace.mkdir()
            (workspace / "server.py").write_text("raise SystemExit('shadow')\n", encoding="utf-8")
            with patch("server.chat_process.subprocess.Popen") as popen:
                launch_chat_server(workspace, env={})
        launch_cwd = popen.call_args.kwargs["cwd"]
        self.assertEqual(launch_cwd, "/Users/okadaharuto/workspace/Agent-Window")
        self.assertNotEqual(launch_cwd, str(workspace))

    def test_git_overview_does_not_use_hub_repo_as_the_project(self) -> None:
        workspace_git.configure(workspace="")
        with self.assertRaisesRegex(RuntimeError, "git workspace is not configured"):
            workspace_git.git_overview()
        with tempfile.TemporaryDirectory() as tmp:
            workspace_git.configure(workspace=tmp)
            self.assertEqual(str(workspace_git._git_root()), tmp)
            self.assertNotEqual(str(workspace_git._git_root()), "/Users/okadaharuto/workspace/Agent-Window")
        workspace_git.configure(workspace="/no/such/even-parity")
        with self.assertRaisesRegex(RuntimeError, "workspace is not available"):
            workspace_git.git_overview()
        workspace_git.configure(workspace="")

    def test_mirrors_do_not_create_a_missing_workspace(self) -> None:
        from backend_core.access.settings import ensure_session_workspace_mirrors

        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "Even-Parity"
            ensure_session_workspace_mirrors("Even-Parity", str(missing))
            self.assertFalse(missing.exists())

    def test_mirrors_link_inside_an_existing_workspace(self) -> None:
        from backend_core.access.settings import (
            SESSION_LOG_FILENAME,
            NATIVE_LOG_STATE_FILENAME,
            ensure_session_workspace_mirrors,
        )

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "Lab"
            workspace.mkdir()
            canonical = Path(tmp) / "session"
            canonical.mkdir()
            log_target = canonical / SESSION_LOG_FILENAME
            native_target = canonical / NATIVE_LOG_STATE_FILENAME
            log_target.write_text("", encoding="utf-8")
            native_target.write_text("", encoding="utf-8")
            with patch("backend_core.access.settings.session_log_path", return_value=log_target), patch(
                "backend_core.access.settings.session_native_log_state_path",
                return_value=native_target,
            ):
                ensure_session_workspace_mirrors("Lab", str(workspace))
            link = workspace / ".agent-window" / SESSION_LOG_FILENAME
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), log_target.resolve())

if __name__ == "__main__":
    unittest.main()
