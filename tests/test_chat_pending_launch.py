from __future__ import annotations

import io
import json
import unittest

import _bootstrap  # noqa: F401
from agent_index import chat_delivery_core, chat_routes_write


class _PendingLaunchRuntime:
    def __init__(self, *, pending: bool = True) -> None:
        self._pending = pending
        self._active_agents = ["claude"]

    def launch_pending(self) -> bool:
        return self._pending

    def resolve_target_agents(self, target: str) -> list[str]:
        normalized = str(target or "").strip().lower()
        return [normalized] if normalized else []

    def active_agents(self) -> list[str]:
        return list(self._active_agents)


class _SendBlockedRuntime:
    def launch_pending(self) -> bool:
        return True


class _JsonHandler:
    def __init__(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = io.BytesIO(body)
        self.response: tuple[int, dict] | None = None

    def _send_json(self, status: int, payload: dict) -> None:
        self.response = (status, payload)


class ChatPendingLaunchTests(unittest.TestCase):
    def test_launch_pending_session_requires_pending_state(self) -> None:
        status, body = chat_delivery_core.launch_pending_session(_PendingLaunchRuntime(pending=False), ["claude"])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "session is already active")

    def test_launch_pending_session_requires_exactly_one_initial_agent(self) -> None:
        status, body = chat_delivery_core.launch_pending_session(_PendingLaunchRuntime(), ["claude", "codex"])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "select exactly one initial agent")

    def test_launch_pending_session_calls_internal_launcher(self) -> None:
        runtime = _PendingLaunchRuntime()
        calls: list[list[str]] = []
        original = chat_delivery_core._launch_pending_session
        try:
            def _fake_launch(self, delivery_targets: list[str]):
                calls.append(list(delivery_targets))
                self._active_agents = ["claude"]
                return True, {"ok": True, "activated": True}

            chat_delivery_core._launch_pending_session = _fake_launch
            status, body = chat_delivery_core.launch_pending_session(runtime, ["claude"])
        finally:
            chat_delivery_core._launch_pending_session = original

        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(body["activated"])
        self.assertEqual(body["selected_agent"], "claude")
        self.assertEqual(body["targets"], ["claude"])
        self.assertEqual(calls, [["claude"]])

    def test_send_message_rejects_pending_session_before_launch(self) -> None:
        status, body = chat_delivery_core.send_message(_SendBlockedRuntime(), "claude", "hello")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "Start the session first by selecting an initial agent.")

    def test_post_launch_session_forwards_agent_list(self) -> None:
        handler = _JsonHandler({"agent": "claude"})
        captured: list[list[str]] = []

        def _launch_session(targets: list[str]):
            captured.append(list(targets))
            return 200, {"ok": True, "targets": ["claude"]}

        chat_routes_write._post_launch_session(
            handler,
            None,
            {
                "launch_session_fn": _launch_session,
            },
        )

        self.assertEqual(captured, [["claude"]])
        self.assertEqual(handler.response, (200, {"ok": True, "targets": ["claude"]}))


if __name__ == "__main__":
    unittest.main()
