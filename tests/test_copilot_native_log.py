from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native_log_sync.agents.copilot.read_updates import sync_copilot_native_log


class _RuntimeStub:
    def __init__(self, index_path: Path) -> None:
        self._copilot_cursors = {}
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


class CopilotNativeLogSyncTest(unittest.TestCase):
    def test_first_bind_backfills_recent_assistant_messages(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tempdir = Path(td)
            native_log = tempdir / "events.jsonl"
            index_path = tempdir / ".agent-index.jsonl"
            recent_ts = "2026-05-04T11:14:49.399Z"
            stale_ts = "2026-05-04T11:13:00.000Z"
            native_log.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "assistant.message",
                                "timestamp": stale_ts,
                                "id": "old-entry",
                                "data": {
                                    "messageId": "old-message",
                                    "content": "too old",
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant.message",
                                "timestamp": recent_ts,
                                "id": "recent-entry",
                                "data": {
                                    "messageId": "recent-message",
                                    "content": "fresh reply",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = _RuntimeStub(index_path)

            with patch("native_log_sync.agents.copilot.read_updates.time.time", return_value=1_777_893_310.0):
                sync_copilot_native_log(
                    runtime,
                    "copilot",
                    str(native_log),
                    sync_bind_backfill_window_seconds=45.0,
                )

            entries = []
            if index_path.exists():
                entries = [
                    json.loads(line)
                    for line in index_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            self.assertEqual(1, len(entries))
            self.assertEqual("[From: copilot]\nfresh reply", entries[0]["message"])
            self.assertEqual("recent-message", entries[0]["msg_id"])
            self.assertIn("recent-message", runtime._synced_msg_ids)
            self.assertNotIn("old-message", runtime._synced_msg_ids)


if __name__ == "__main__":
    unittest.main()
