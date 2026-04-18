from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import _bootstrap  # noqa: F401
from agent_index import hub_server


class HubServerPendingProxyTests(unittest.TestCase):
    def test_resolve_session_chat_target_uses_pending_draft_when_not_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            original_repo_root = hub_server.repo_root
            original_active_query = hub_server.active_session_records_query
            original_ensure_chat = hub_server.ensure_chat_server
            original_pending_record = hub_server._pending_session_record
            original_ensure_pending = hub_server._ensure_pending_chat_server
            calls: list[tuple[str, str, list[str]]] = []
            try:
                hub_server.repo_root = repo_root
                hub_server.active_session_records_query = lambda: SimpleNamespace(records={}, state="ok", detail="")
                hub_server.ensure_chat_server = lambda session_name: (_ for _ in ()).throw(AssertionError(session_name))
                hub_server._pending_session_record = lambda session_name: {
                    "name": session_name,
                    "workspace": str(repo_root),
                    "agents": ["claude", "codex"],
                    "launch_pending": True,
                }

                def _fake_ensure_pending(session_name: str, workspace: str, targets: list[str]):
                    calls.append((session_name, workspace, list(targets)))
                    return True, 8760, ""

                hub_server._ensure_pending_chat_server = _fake_ensure_pending

                resolved = hub_server._resolve_session_chat_target("draft-demo")
            finally:
                hub_server.repo_root = original_repo_root
                hub_server.active_session_records_query = original_active_query
                hub_server.ensure_chat_server = original_ensure_chat
                hub_server._pending_session_record = original_pending_record
                hub_server._ensure_pending_chat_server = original_ensure_pending

        self.assertEqual(resolved["status"], "ok")
        self.assertEqual(resolved["chat_port"], 8760)
        self.assertEqual(calls, [("draft-demo", str(repo_root), ["claude", "codex"])])
        self.assertEqual(resolved["session_record"]["name"], "draft-demo")
        self.assertTrue(resolved["session_record"]["launch_pending"])

    def test_resolve_session_chat_target_prefers_active_session(self) -> None:
        active_record = {"name": "live-demo", "workspace": "/tmp/live"}
        original_active_query = hub_server.active_session_records_query
        original_ensure_chat = hub_server.ensure_chat_server
        original_pending_record = hub_server._pending_session_record
        try:
            hub_server.active_session_records_query = lambda: SimpleNamespace(
                records={"live-demo": active_record},
                state="ok",
                detail="",
            )
            hub_server.ensure_chat_server = lambda session_name: (True, 8316, "")
            hub_server._pending_session_record = lambda session_name: {
                "name": session_name,
                "workspace": "/tmp/should-not-use",
                "agents": ["claude"],
                "launch_pending": True,
            }

            resolved = hub_server._resolve_session_chat_target("live-demo")
        finally:
            hub_server.active_session_records_query = original_active_query
            hub_server.ensure_chat_server = original_ensure_chat
            hub_server._pending_session_record = original_pending_record

        self.assertEqual(resolved["status"], "ok")
        self.assertEqual(resolved["chat_port"], 8316)
        self.assertIs(resolved["session_record"], active_record)

    def test_resolve_session_chat_target_reports_unhealthy_when_missing(self) -> None:
        original_active_query = hub_server.active_session_records_query
        original_pending_record = hub_server._pending_session_record
        try:
            hub_server.active_session_records_query = lambda: SimpleNamespace(records={}, state="unhealthy", detail="tmux bad")
            hub_server._pending_session_record = lambda session_name: None

            resolved = hub_server._resolve_session_chat_target("missing-demo")
        finally:
            hub_server.active_session_records_query = original_active_query
            hub_server._pending_session_record = original_pending_record

        self.assertEqual(resolved, {"status": "unhealthy", "detail": "tmux bad"})


if __name__ == "__main__":
    unittest.main()
