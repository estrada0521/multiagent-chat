from __future__ import annotations

import io
import json
import tempfile
import types
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index import hub_server


class _DummyHandler:
    def __init__(self, body: bytes = b"", host: str = "127.0.0.1:9999") -> None:
        self.json_calls: list[tuple[int, dict]] = []
        self.html_calls: list[tuple[int, str]] = []
        self.response_codes: list[int] = []
        self.sent_headers: list[tuple[str, str]] = []
        self.ended = False
        self.headers = {
            "Content-Length": str(len(body)),
            "Host": host,
        }
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()

    def _send_json(self, status, payload) -> None:
        self.json_calls.append((status, payload))

    def _send_html(self, status, body) -> None:
        self.html_calls.append((status, body))

    def send_response(self, status) -> None:
        self.response_codes.append(status)

    def send_header(self, key, value) -> None:
        self.sent_headers.append((key, value))

    def end_headers(self) -> None:
        self.ended = True


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

    def test_get_hub_launch_shell_serves_html(self) -> None:
        handler = _DummyHandler()
        hub_server.Handler._get_hub_launch_shell(handler, None)
        self.assertEqual(handler.html_calls, [(200, hub_server.HUB_LAUNCH_SHELL_HTML)])

    def test_get_hub_manifest_uses_launch_shell_start_url(self) -> None:
        handler = _DummyHandler()
        hub_server.Handler._get_hub_manifest(handler, None)
        self.assertEqual(handler.response_codes, [200])
        manifest = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(manifest.get("start_url"), "/hub-launch-shell.html?target=%2F%3Flaunch_shell%3D1")

    def test_post_start_session_returns_json_error_on_unexpected_exception(self) -> None:
        handler = _DummyHandler()
        with patch("agent_index.hub_server._post_start_session_impl", side_effect=RuntimeError("boom")):
            hub_server.Handler._post_start_session(handler, None)
        self.assertEqual(handler.json_calls, [(500, {"ok": False, "error": "boom"})])

    def test_get_sessions_sets_running_flags_to_defaults(self) -> None:
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
        ):
            hub_server.Handler._get_sessions(handler, None)
        self.assertEqual(handler.json_calls[0][0], 200)
        payload = handler.json_calls[0][1]
        self.assertEqual(payload["active_sessions"][0]["running_agents"], [])
        self.assertFalse(payload["active_sessions"][0]["is_running"])

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
        parsed = urlparse(payload["chat_url"])
        params = parse_qs(parsed.query)
        self.assertEqual(params.get("compose"), ["1"])
        self.assertEqual(params.get("draft"), ["1"])
        self.assertEqual(params.get("draft_targets"), [",".join(hub_server.ALL_AGENT_NAMES)])

    def test_get_kill_session_deletes_pending_draft(self) -> None:
        handler = _DummyHandler()
        parsed = types.SimpleNamespace(query="session=draft-demo")
        with patch("agent_index.hub_server._is_pending_launch_session", return_value=True), patch(
            "agent_index.hub_server._delete_pending_draft_session", return_value=(True, "")
        ):
            hub_server.Handler._get_kill_session(handler, parsed)
        self.assertEqual(handler.response_codes, [302])
        self.assertIn(("Location", "/"), handler.sent_headers)

    def test_get_kill_session_returns_json_when_requested(self) -> None:
        handler = _DummyHandler()
        parsed = types.SimpleNamespace(query="session=demo&format=json")
        with patch("agent_index.hub_server._is_pending_launch_session", return_value=False), patch(
            "agent_index.hub_server.kill_repo_session", return_value=(True, "")
        ):
            hub_server.Handler._get_kill_session(handler, parsed)
        self.assertEqual(handler.json_calls, [(200, {"ok": True, "session": "demo", "action": "killed"})])

    def test_get_delete_archived_session_deletes_pending_draft(self) -> None:
        handler = _DummyHandler()
        parsed = types.SimpleNamespace(query="session=draft-demo")
        with patch("agent_index.hub_server._is_pending_launch_session", return_value=True), patch(
            "agent_index.hub_server._delete_pending_draft_session", return_value=(True, "")
        ):
            hub_server.Handler._get_delete_archived_session(handler, parsed)
        self.assertEqual(handler.response_codes, [302])
        self.assertIn(("Location", "/"), handler.sent_headers)

    def test_get_delete_archived_session_returns_json_when_requested(self) -> None:
        handler = _DummyHandler()
        parsed = types.SimpleNamespace(query="session=demo&format=json")
        with patch("agent_index.hub_server._is_pending_launch_session", return_value=False), patch(
            "agent_index.hub_server.delete_archived_session", return_value=(True, "")
        ):
            hub_server.Handler._get_delete_archived_session(handler, parsed)
        self.assertEqual(handler.json_calls, [(200, {"ok": True, "session": "demo", "action": "deleted"})])


if __name__ == "__main__":
    unittest.main()
