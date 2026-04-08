from __future__ import annotations

import unittest
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index import hub_server


class _DummyHandler:
    def __init__(self) -> None:
        self.json_calls: list[tuple[int, dict]] = []

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


if __name__ == "__main__":
    unittest.main()
