from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def _append_index_entry(self, entry: dict) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

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

    def test_restart_command_records_system_entry(self) -> None:
        with patch.object(self.runtime, "resolve_target_agents", return_value=["claude"]):
            with patch.object(self.runtime, "restart_agent_pane", return_value=(True, "%1")):
                status, payload = self.runtime.send_message("claude", "restart")
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "restart")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sender"], "system")
        self.assertEqual(entries[0]["kind"], "agent-control")
        self.assertEqual(entries[0]["command"], "restart")
        self.assertEqual(entries[0]["targets"], ["claude"])
        self.assertIn("Restarted: claude", entries[0]["message"])

    def test_resume_command_records_system_entry(self) -> None:
        with patch.object(self.runtime, "resolve_target_agents", return_value=["claude"]):
            with patch.object(self.runtime, "resume_agent_pane", return_value=(True, "%1")):
                status, payload = self.runtime.send_message("claude", "resume")
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "resume")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sender"], "system")
        self.assertEqual(entries[0]["kind"], "agent-control")
        self.assertEqual(entries[0]["command"], "resume")
        self.assertEqual(entries[0]["targets"], ["claude"])
        self.assertIn("Resumed: claude", entries[0]["message"])

    def test_read_entries_infers_agent_thinking_kind_for_i_will_prefix(self) -> None:
        self._append_index_entry(
            {
                "timestamp": "2026-04-07 00:00:00",
                "session": "demo",
                "sender": "gemini",
                "targets": ["user"],
                "message": "[From: gemini]\nI will inspect the files first.",
                "msg_id": "a1b2c3d4e5f6",
            }
        )
        entries = self.runtime.read_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get("kind"), "agent-thinking")

    def test_read_entries_infers_agent_thinking_for_other_agents_too(self) -> None:
        self._append_index_entry(
            {
                "timestamp": "2026-04-07 00:00:00",
                "session": "demo",
                "sender": "claude",
                "targets": ["user"],
                "message": "I'll check this step by step.",
                "msg_id": "b1b2c3d4e5f6",
            }
        )
        entries = self.runtime.read_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get("kind"), "agent-thinking")

    def test_read_entries_keeps_user_message_untyped(self) -> None:
        self._append_index_entry(
            {
                "timestamp": "2026-04-07 00:00:00",
                "session": "demo",
                "sender": "user",
                "targets": ["user"],
                "message": "I will write this memo.",
                "msg_id": "c1b2c3d4e5f6",
            }
        )
        entries = self.runtime.read_entries()
        self.assertEqual(len(entries), 1)
        self.assertNotIn("kind", entries[0])

    def test_read_entries_keeps_existing_kind(self) -> None:
        self._append_index_entry(
            {
                "timestamp": "2026-04-07 00:00:00",
                "session": "demo",
                "sender": "gemini",
                "targets": ["user"],
                "message": "I will inspect this.",
                "kind": "git-commit",
                "msg_id": "d1b2c3d4e5f6",
            }
        )
        entries = self.runtime.read_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get("kind"), "git-commit")

    def test_send_message_to_agent_returns_ok_and_appends_entry(self) -> None:
        def fake_run(argv, **kwargs):
            if "show-environment" in argv:
                return SimpleNamespace(returncode=0, stdout="MULTIAGENT_PANE_CLAUDE=%1\n", stderr="")
            if "send-keys" in argv:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected argv: {argv}")

        with patch("agent_index.chat_delivery_core.subprocess.run", side_effect=fake_run), patch.object(
            self.runtime, "_wait_for_send_slot"
        ), patch.object(self.runtime, "_wait_for_agent_prompt", return_value=True), patch.object(
            self.runtime, "_handoff_shared_sync_claim"
        ):
            status, payload = self.runtime.send_message("claude", "hello world")

        self.assertEqual(status, 200)
        self.assertTrue(payload.get("ok"))
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sender"], "user")
        self.assertEqual(entries[0]["targets"], ["claude"])
        self.assertEqual(entries[0]["message"], "[From: User]\nhello world")

    def test_send_message_to_qwen_uses_inline_submission_payload(self) -> None:
        sent_payloads: list[str] = []

        def fake_run(argv, **kwargs):
            if "show-environment" in argv:
                return SimpleNamespace(returncode=0, stdout="MULTIAGENT_PANE_QWEN=%9\n", stderr="")
            if "capture-pane" in argv:
                return SimpleNamespace(returncode=0, stdout="? for shortcuts\n", stderr="")
            if "send-keys" in argv:
                if "-l" in argv:
                    sent_payloads.append(argv[argv.index("-l") + 1])
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected argv: {argv}")

        with patch("agent_index.chat_delivery_core.subprocess.run", side_effect=fake_run), patch.object(
            self.runtime, "_wait_for_send_slot"
        ), patch.object(self.runtime, "_handoff_shared_sync_claim"):
            status, payload = self.runtime.send_message("qwen", "hello world")

        self.assertEqual(status, 200)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(sent_payloads, ["[From: User] hello world"])
        entries = self._index_entries()
        self.assertEqual(entries[-1]["message"], "[From: User]\nhello world")

    def test_pending_launch_send_returns_activated_targets(self) -> None:
        pending_path = self.index_path.parent / ".pending-launch.json"
        self.runtime.session_is_active = False
        pending_path.write_text(
            json.dumps({"session": "demo", "available_agents": ["claude", "codex"]}, ensure_ascii=False),
            encoding="utf-8",
        )

        def fake_run(argv, **kwargs):
            if "show-environment" in argv:
                return SimpleNamespace(returncode=0, stdout="MULTIAGENT_PANE_CLAUDE=%1\n", stderr="")
            if "send-keys" in argv:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected argv: {argv}")

        with patch("agent_index.chat_delivery_core._launch_pending_session", return_value=(True, {"ok": True, "activated": True, "targets": ["claude"]})), patch(
            "agent_index.chat_delivery_core.subprocess.run", side_effect=fake_run
        ), patch.object(self.runtime, "_wait_for_send_slot"), patch.object(
            self.runtime, "_wait_for_agent_prompt", return_value=True
        ), patch.object(self.runtime, "_handoff_shared_sync_claim"):
            status, payload = self.runtime.send_message("claude", "boot")

        self.assertEqual(status, 200)
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("activated"))
        self.assertEqual(payload.get("targets"), ["claude"])

    def test_payload_includes_launch_pending_for_draft_session(self) -> None:
        pending_path = self.index_path.parent / ".pending-launch.json"
        self.runtime.session_is_active = False
        pending_path.write_text(
            json.dumps({"session": "demo", "available_agents": ["claude", "codex"]}, ensure_ascii=False),
            encoding="utf-8",
        )

        payload = json.loads(self.runtime.payload().decode("utf-8"))
        self.assertFalse(payload["active"])
        self.assertTrue(payload["launch_pending"])
        self.assertEqual(payload["targets"], ["claude"])
