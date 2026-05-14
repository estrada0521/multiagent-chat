from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from message_delivery import send_message
from message_delivery.interaction import normalize_sender_payload


class _SendRuntimeStub:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.session_name = "test-session"
        self.tmux_prefix = ["tmux"]
        self._agent_last_send_ts = {}
        self.sent_payloads: list[str] = []

    def launch_pending(self) -> bool:
        return False

    def resolve_target_agents(self, target: str) -> list[str]:
        return [target]

    def active_agents(self) -> list[str]:
        return ["codex"]

    def pane_id_for_agent(self, agent: str) -> str:
        return f"%{agent}"

    def _wait_for_send_slot(self, _agent: str) -> None:
        return None

    def _mark_agent_sent(self, _agent: str) -> None:
        return None

    def _reply_preview_for(self, _reply_to: str) -> str:
        return ""


class _CompletedProcess:
    returncode = 0
    stdout = "1\n"


class UserSendHeadersTest(unittest.TestCase):
    def test_regular_user_send_does_not_add_from_header(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runtime = _SendRuntimeStub(Path(td) / ".agent-index.jsonl")

            def fake_run(cmd, *args, **kwargs):
                if "send-keys" in cmd and "-l" in cmd:
                    runtime.sent_payloads.append(cmd[cmd.index("-l") + 1])
                return _CompletedProcess()

            with patch("message_delivery.subprocess.run", side_effect=fake_run):
                status, body = send_message(runtime, "codex", "hello")

            self.assertEqual(200, status)
            self.assertTrue(body["ok"])
            self.assertEqual(["hello"], runtime.sent_payloads)
            entries = [
                json.loads(line)
                for line in runtime.index_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual("hello", entries[0]["message"])

    def test_agent_send_normalization_still_adds_sender_header(self) -> None:
        self.assertEqual("[From: codex]\nhello\n", normalize_sender_payload("codex", "hello"))


if __name__ == "__main__":
    unittest.main()
