from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.chat_core import ChatRuntime


class ChatCoreCommitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name) / "repo"
        (self.repo_root / "logs" / "demo").mkdir(parents=True)
        (self.repo_root / "bin").mkdir()
        self.index_path = self.repo_root / "logs" / "demo" / ".agent-index.jsonl"
        self.settings_patcher = patch("agent_index.chat_core.load_shared_hub_settings", return_value={})
        self.settings_patcher.start()
        self.runtime = ChatRuntime(
            index_path=self.index_path,
            limit=2000,
            filter_agent="",
            session_name="demo",
            follow_mode=False,
            port=8123,
            agent_send_path=self.repo_root / "bin" / "agent-send",
            workspace=str(self.repo_root),
            log_dir=str(self.repo_root / "logs"),
            targets=["claude"],
            tmux_socket="test-socket",
            hub_port=8788,
            repo_root=self.repo_root,
            session_is_active=True,
        )

    def tearDown(self) -> None:
        self.settings_patcher.stop()
        self.tempdir.cleanup()

    def _index_entries(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        entries = []
        with self.index_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
        return entries

    def test_record_git_commit_logs_once_for_same_commit(self) -> None:
        first = self.runtime.record_git_commit(
            commit_hash="abc123def456",
            commit_short="abc123d",
            subject="Fix duplicate commit entries",
        )
        second = self.runtime.record_git_commit(
            commit_hash="abc123def456",
            commit_short="abc123d",
            subject="Fix duplicate commit entries",
        )

        self.assertTrue(first)
        self.assertFalse(second)
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "git-commit")
        self.assertEqual(entries[0]["commit_hash"], "abc123def456")
        self.assertEqual(self.runtime.read_commit_state()["last_commit_hash"], "abc123def456")

    def test_ensure_commit_announcements_skips_already_logged_commit_when_state_is_stale(self) -> None:
        current = {
            "hash": "def456abc123",
            "short": "def456a",
            "subject": "Ship commit logging",
        }
        self.runtime.append_system_entry(
            f"Commit: {current['short']} {current['subject']}",
            kind="git-commit",
            commit_hash=current["hash"],
            commit_short=current["short"],
        )
        self.runtime.write_commit_state(
            {
                "hash": "older0000000",
                "short": "older00",
                "subject": "Older commit",
            }
        )

        with patch.object(self.runtime, "current_git_commit", return_value=current), patch.object(
            self.runtime, "git_commits_since", return_value=[current]
        ):
            self.runtime.ensure_commit_announcements()

        entries = [entry for entry in self._index_entries() if entry.get("kind") == "git-commit"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["commit_hash"], current["hash"])
        self.assertEqual(self.runtime.read_commit_state()["last_commit_hash"], current["hash"])

    def test_send_message_user_target_appends_local_memo_entry(self) -> None:
        status, payload = self.runtime.send_message("user", "local memo")
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "memo")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sender"], "user")
        self.assertEqual(entries[0]["targets"], ["user"])
        self.assertEqual(entries[0]["message"], "local memo")

    def test_send_message_without_target_defaults_to_local_memo(self) -> None:
        status, payload = self.runtime.send_message("", "implicit local memo")
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "memo")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sender"], "user")
        self.assertEqual(entries[0]["targets"], ["user"])
        self.assertEqual(entries[0]["message"], "implicit local memo")
