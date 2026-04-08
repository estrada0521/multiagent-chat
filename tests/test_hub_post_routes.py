from __future__ import annotations

import io
import tempfile
import types
import unittest
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index import hub_server


class _DummyHandler:
    def __init__(self, body: bytes = b"", host: str = "127.0.0.1:9999") -> None:
        self.json_calls: list[tuple[int, dict]] = []
        self.headers = {
            "Content-Length": str(len(body)),
            "Host": host,
        }
        self.rfile = io.BytesIO(body)

    def _send_json(self, status, payload) -> None:
        self.json_calls.append((status, payload))


class HubPostRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        hub_server.initialize_from_argv([".", "bin/agent-index", "9999", "multiagent"])

    def test_post_start_session_passes_agent_names(self) -> None:
        handler = _DummyHandler()
        with patch("agent_index.hub_server._post_start_session_impl") as impl:
            hub_server.Handler._post_start_session(handler, None)
        impl.assert_called_once()
        self.assertEqual(impl.call_args.kwargs["all_agent_names"], hub_server.ALL_AGENT_NAMES)

    def test_post_start_session_returns_json_error_on_unexpected_exception(self) -> None:
        handler = _DummyHandler()
        with patch("agent_index.hub_server._post_start_session_impl", side_effect=RuntimeError("boom")):
            hub_server.Handler._post_start_session(handler, None)
        self.assertEqual(handler.json_calls, [(500, {"ok": False, "error": "boom"})])

    def test_get_sessions_includes_running_agents(self) -> None:
        handler = _DummyHandler()
        active_query = types.SimpleNamespace(
            records={
                "demo": {
                    "name": "demo",
                    "workspace": "/tmp/demo",
                    "status": "idle",
                }
            },
            state="ok",
            detail="",
        )
        with patch("agent_index.hub_server.active_session_records_query", return_value=active_query), patch(
            "agent_index.hub_server.archived_session_records", return_value={}
        ), patch(
            "agent_index.hub_server.load_session_running_agents", return_value=["codex-1"]
        ):
            hub_server.Handler._get_sessions(handler, None)
        self.assertEqual(handler.json_calls[0][0], 200)
        payload = handler.json_calls[0][1]
        self.assertEqual(payload["active_sessions"][0]["running_agents"], ["codex-1"])
        self.assertTrue(payload["active_sessions"][0]["is_running"])

    def test_get_sessions_promotes_pending_archived_records(self) -> None:
        handler = _DummyHandler()
        active_query = types.SimpleNamespace(records={}, state="ok", detail="")
        archived_record = {
            "name": "draft-demo",
            "workspace": "/tmp/demo",
            "status": "archived",
        }
        with patch("agent_index.hub_server.active_session_records_query", return_value=active_query), patch(
            "agent_index.hub_server.archived_session_records", return_value={"draft-demo": archived_record}
        ), patch(
            "agent_index.hub_server._is_pending_launch_session", return_value=True
        ):
            hub_server.Handler._get_sessions(handler, None)
        payload = handler.json_calls[0][1]
        self.assertEqual(payload["archived_sessions"], [])
        self.assertEqual(payload["active_sessions"][0]["name"], "draft-demo")
        self.assertTrue(payload["active_sessions"][0]["launch_pending"])

    def test_post_start_session_draft_returns_chat_url(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            body = f'{{"workspace": "{workspace}"}}'.encode("utf-8")
            handler = _DummyHandler(body=body)
            with patch("agent_index.hub_server._unique_session_name_for_workspace", return_value="draft-demo"), patch(
                "agent_index.hub_server._write_pending_session_files",
                return_value={"created_at": "2026-04-08 12:00", "updated_at": "2026-04-08 12:00"},
            ), patch(
                "agent_index.hub_server._ensure_pending_chat_server",
                return_value=(True, 45678, ""),
            ), patch(
                "agent_index.hub_server._build_pending_session_record",
                return_value={"name": "draft-demo", "launch_pending": True},
            ):
                hub_server.Handler._post_start_session_draft(handler, None)
        self.assertEqual(handler.json_calls[0][0], 200)
        payload = handler.json_calls[0][1]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"], "draft-demo")
        self.assertIn("compose=1", payload["chat_url"])


if __name__ == "__main__":
    unittest.main()
