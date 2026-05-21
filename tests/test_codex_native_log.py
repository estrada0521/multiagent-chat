from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from native_log_sync.agents._shared.path_state import NativeLogCursor
from native_log_sync.agents.codex.read_updates import sync_codex_native_log


class _RuntimeStub:
    def __init__(self, index_path: Path, native_log: Path) -> None:
        self._codex_cursors = {"codex": NativeLogCursor(path=str(native_log), offset=0)}
        self._synced_msg_ids = set()
        self.index_path = index_path
        self.session_name = "test-session"
        self.workspace = ""
        self.saved = 0
        self.idle = []
        self._idle_running_display_by_agent = {}

    def save_sync_state(self) -> None:
        self.saved += 1

    def pane_id_for_agent(self, _agent: str) -> str:
        return ""

    def _mark_idle(self, agent: str) -> None:
        self.idle.append(agent)

    def notify_session_state_changed(self, _keys, *, reason: str = "") -> None:
        del reason


class CodexNativeLogSyncTest(unittest.TestCase):
    def test_token_count_without_reached_type_does_not_emit_rate_limit_message(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tempdir = Path(td)
            native_log = tempdir / "codex.jsonl"
            index_path = tempdir / ".agent-index.jsonl"
            native_log.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-05-17T04:59:25.348Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "rate_limits": {
                                "primary": {
                                    "used_percent": 2.0,
                                    "window_minutes": 300,
                                    "resets_at": 1779011628,
                                },
                                "credits": None,
                                "rate_limit_reached_type": None,
                            },
                        },
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "timestamp": "2026-05-17T04:59:25.349Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "actual reply"}],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = _RuntimeStub(index_path, native_log)

            sync_codex_native_log(
                runtime,
                "codex",
                str(native_log),
                sync_bind_backfill_window_seconds=45.0,
            )

            entries = [
                json.loads(line)
                for line in index_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(["actual reply"], [entry["message"] for entry in entries])

    def test_token_count_with_empty_credits_but_without_reached_type_does_not_emit_limit_message(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tempdir = Path(td)
            native_log = tempdir / "codex.jsonl"
            index_path = tempdir / ".agent-index.jsonl"
            native_log.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-05-17T10:03:30.014Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "rate_limits": {
                                "primary": {
                                    "used_percent": 2.0,
                                    "window_minutes": 300,
                                    "resets_at": 1779030073,
                                },
                                "secondary": {
                                    "used_percent": 16.0,
                                    "window_minutes": 10080,
                                    "resets_at": 1779598428,
                                },
                                "credits": {
                                    "has_credits": False,
                                    "unlimited": False,
                                    "balance": "0",
                                },
                                "rate_limit_reached_type": None,
                            },
                        },
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "timestamp": "2026-05-17T10:03:30.187Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "call_ok",
                            "output": "tool output",
                        },
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "timestamp": "2026-05-17T10:03:31.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "still working"}],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = _RuntimeStub(index_path, native_log)

            sync_codex_native_log(
                runtime,
                "codex",
                str(native_log),
                sync_bind_backfill_window_seconds=45.0,
            )

            entries = [
                json.loads(line)
                for line in index_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(["still working"], [entry["message"] for entry in entries])

    def test_token_count_with_reached_type_emits_rate_limit_message(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tempdir = Path(td)
            native_log = tempdir / "codex.jsonl"
            index_path = tempdir / ".agent-index.jsonl"
            native_log.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-05-17T04:59:25.348Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "rate_limits": {
                                "primary": {
                                    "used_percent": 2.0,
                                    "window_minutes": 300,
                                },
                                "credits": None,
                                "rate_limit_reached_type": "primary",
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = _RuntimeStub(index_path, native_log)

            sync_codex_native_log(
                runtime,
                "codex",
                str(native_log),
                sync_bind_backfill_window_seconds=45.0,
            )

            entries = [
                json.loads(line)
                for line in index_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(["Rate limit reached. Resets in 300 minutes."], [entry["message"] for entry in entries])


if __name__ == "__main__":
    unittest.main()
