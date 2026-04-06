"""Tests for per-agent native-log cursor tracking in ChatRuntime.

These tests exercise the `NativeLogCursor` / `_advance_native_cursor` /
`_pick_latest_unclaimed` helpers and the sync path of each CLI (Claude,
Gemini, Qwen, Cursor, Codex, Copilot, OpenCode) to make sure:

1. On first sight of a file, the cursor anchors to the end (no flooding).
2. On appends, only the new bytes are processed.
3. On truncation (file shrank at same path), we reset to 0 and read again.
4. On path change (new "latest" file appeared), we anchor to the new end
   rather than reading from byte 0 — this is the Reload/Add-Agent flood fix.
5. Two agents of the same base type don't steal each other's files when
   both are active in the same workspace.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.chat_core import (
    ChatRuntime,
    NativeLogCursor,
    OpenCodeCursor,
    _advance_native_cursor,
    _coerce_native_cursor,
    _coerce_opencode_cursor,
    _dedup_cursor_claims,
    _load_cursor_dict,
    _load_opencode_dict,
    _parse_cursor_jsonl_runtime,
    _pick_latest_unclaimed,
)


class NativeLogCursorHelperTests(unittest.TestCase):
    def test_coerce_accepts_list_pair(self) -> None:
        cursor = _coerce_native_cursor(["/tmp/a.jsonl", 42])
        self.assertEqual(cursor, NativeLogCursor(path="/tmp/a.jsonl", offset=42))

    def test_coerce_accepts_tuple(self) -> None:
        cursor = _coerce_native_cursor(("/tmp/a.jsonl", 10))
        self.assertEqual(cursor, NativeLogCursor(path="/tmp/a.jsonl", offset=10))

    def test_coerce_rejects_bare_int(self) -> None:
        """Historic format was bare int offsets. Those are meaningless
        without the path binding and must be discarded."""
        self.assertIsNone(_coerce_native_cursor(42))

    def test_coerce_rejects_malformed(self) -> None:
        self.assertIsNone(_coerce_native_cursor(None))
        self.assertIsNone(_coerce_native_cursor([]))
        self.assertIsNone(_coerce_native_cursor(["only-path"]))
        self.assertIsNone(_coerce_native_cursor([1, 2, 3]))
        self.assertIsNone(_coerce_native_cursor([42, "path"]))  # wrong order

    def test_load_cursor_dict_drops_old_format(self) -> None:
        raw = {
            "claude-1": ["/tmp/a.jsonl", 100],
            "claude-2": 500,  # old format: bare int
            "claude-3": ["/tmp/b.jsonl", 200],
            123: ["/tmp/c.jsonl", 0],  # non-string key
        }
        loaded = _load_cursor_dict(raw)
        self.assertIn("claude-1", loaded)
        self.assertIn("claude-3", loaded)
        self.assertNotIn("claude-2", loaded)
        self.assertEqual(loaded["claude-1"].offset, 100)
        self.assertEqual(loaded["claude-3"].path, "/tmp/b.jsonl")

    def test_load_cursor_dict_handles_garbage(self) -> None:
        self.assertEqual(_load_cursor_dict(None), {})
        self.assertEqual(_load_cursor_dict("not a dict"), {})
        self.assertEqual(_load_cursor_dict([]), {})

    def test_coerce_opencode_cursor(self) -> None:
        self.assertEqual(
            _coerce_opencode_cursor(["ses_x", "msg_y"]),
            OpenCodeCursor(session_id="ses_x", last_msg_id="msg_y"),
        )
        self.assertIsNone(_coerce_opencode_cursor(["just_session"]))
        self.assertIsNone(_coerce_opencode_cursor(42))

    def test_load_opencode_dict(self) -> None:
        loaded = _load_opencode_dict(
            {
                "opencode-1": ["ses_a", "msg_1"],
                "opencode-2": "bogus",
            }
        )
        self.assertIn("opencode-1", loaded)
        self.assertNotIn("opencode-2", loaded)


class AdvanceNativeCursorTests(unittest.TestCase):
    def test_first_sight_anchors_to_end(self) -> None:
        cursors: dict[str, NativeLogCursor] = {}
        result = _advance_native_cursor(cursors, "claude-1", "/tmp/a.jsonl", 500)
        self.assertIsNone(result)
        self.assertEqual(cursors["claude-1"], NativeLogCursor("/tmp/a.jsonl", 500))

    def test_append_returns_prev_offset(self) -> None:
        cursors = {"a": NativeLogCursor("/x.jsonl", 100)}
        result = _advance_native_cursor(cursors, "a", "/x.jsonl", 300)
        self.assertEqual(result, 100)
        # Caller is responsible for updating the cursor after reading; the
        # helper only decides whether (and from where) to read.
        self.assertEqual(cursors["a"], NativeLogCursor("/x.jsonl", 100))

    def test_no_new_bytes_returns_none(self) -> None:
        cursors = {"a": NativeLogCursor("/x.jsonl", 100)}
        result = _advance_native_cursor(cursors, "a", "/x.jsonl", 100)
        self.assertIsNone(result)

    def test_truncation_returns_zero(self) -> None:
        cursors = {"a": NativeLogCursor("/x.jsonl", 500)}
        result = _advance_native_cursor(cursors, "a", "/x.jsonl", 100)
        self.assertEqual(result, 0)

    def test_path_change_anchors_to_end_not_zero(self) -> None:
        """The flood-prevention guarantee: switching the "latest file" for an
        agent must NOT cause us to replay the new file from byte 0."""
        cursors = {"a": NativeLogCursor("/old.jsonl", 100)}
        result = _advance_native_cursor(cursors, "a", "/new.jsonl", 9999)
        self.assertIsNone(result)
        self.assertEqual(cursors["a"], NativeLogCursor("/new.jsonl", 9999))


class PickLatestUnclaimedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _make_file(self, name: str, mtime_offset: float) -> Path:
        p = self.root / name
        p.write_text("x")
        now = time.time()
        import os
        os.utime(p, (now + mtime_offset, now + mtime_offset))
        return p

    def test_picks_latest_when_no_claims(self) -> None:
        self._make_file("old.jsonl", -100)
        newer = self._make_file("new.jsonl", 0)
        pick = _pick_latest_unclaimed(list(self.root.glob("*.jsonl")), {}, "agent-1")
        self.assertEqual(pick, newer)

    def test_skips_claimed_by_other_agent(self) -> None:
        older = self._make_file("a.jsonl", -100)
        newer = self._make_file("b.jsonl", 0)
        cursors = {"claude-1": NativeLogCursor(str(newer), 500)}
        pick = _pick_latest_unclaimed(
            list(self.root.glob("*.jsonl")), cursors, "claude-2"
        )
        self.assertEqual(pick, older)

    def test_own_claim_does_not_exclude_self(self) -> None:
        f = self._make_file("a.jsonl", 0)
        cursors = {"claude-1": NativeLogCursor(str(f), 10)}
        pick = _pick_latest_unclaimed([f], cursors, "claude-1")
        self.assertEqual(pick, f)

    def test_all_claimed_returns_none(self) -> None:
        """When every candidate is claimed by another agent, return None.

        The old fallback (return newest regardless) caused the qwen-1/qwen-2
        file-sharing bug. The correct behavior is to wait until the agent's
        CLI writes a new file whose mtime exceeds the min_mtime gate.
        """
        older = self._make_file("a.jsonl", -100)
        newer = self._make_file("b.jsonl", 0)
        cursors = {
            "claude-1": NativeLogCursor(str(newer), 1),
            "claude-2": NativeLogCursor(str(older), 1),
        }
        pick = _pick_latest_unclaimed(
            list(self.root.glob("*.jsonl")), cursors, "claude-3"
        )
        self.assertIsNone(pick)

    def test_min_mtime_filters_old_files(self) -> None:
        """Files with mtime before min_mtime are not eligible."""
        old = self._make_file("old.jsonl", -300)
        new = self._make_file("new.jsonl", 0)
        # min_mtime is after old but before new
        min_mtime = time.time() - 150
        pick = _pick_latest_unclaimed(
            list(self.root.glob("*.jsonl")), {}, "agent-1", min_mtime=min_mtime
        )
        self.assertEqual(pick, new)

    def test_min_mtime_filters_all(self) -> None:
        """If all candidates are older than min_mtime, return None."""
        self._make_file("old.jsonl", -300)
        min_mtime = time.time() + 100  # in the future
        pick = _pick_latest_unclaimed(
            list(self.root.glob("*.jsonl")), {}, "agent-1", min_mtime=min_mtime
        )
        self.assertIsNone(pick)

    def test_empty_candidates(self) -> None:
        self.assertIsNone(_pick_latest_unclaimed([], {}, "a"))


class DedupCursorClaimsTests(unittest.TestCase):
    def test_no_duplicates_unchanged(self) -> None:
        cursors = {
            "agent-1": NativeLogCursor("/a.jsonl", 10),
            "agent-2": NativeLogCursor("/b.jsonl", 20),
        }
        result = _dedup_cursor_claims(cursors)
        self.assertEqual(result, cursors)

    def test_duplicate_keeps_alphabetically_first(self) -> None:
        """Two agents pointing at the same file: keep the first by name."""
        cursors = {
            "qwen-2": NativeLogCursor("/shared.jsonl", 100),
            "qwen-1": NativeLogCursor("/shared.jsonl", 50),
        }
        result = _dedup_cursor_claims(cursors)
        self.assertIn("qwen-1", result)
        self.assertNotIn("qwen-2", result)

    def test_empty_dict(self) -> None:
        self.assertEqual(_dedup_cursor_claims({}), {})

    def test_triple_duplicate_keeps_one(self) -> None:
        cursors = {
            "c": NativeLogCursor("/same.jsonl", 1),
            "a": NativeLogCursor("/same.jsonl", 2),
            "b": NativeLogCursor("/same.jsonl", 3),
        }
        result = _dedup_cursor_claims(cursors)
        self.assertEqual(list(result.keys()), ["a"])


class _SyncTestBase(unittest.TestCase):
    """Common scaffolding: a ChatRuntime pointing at a temp workspace, with
    the per-CLI log directories also rooted at tempdir (via monkey-patching
    ``Path.home``)."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.home = self.root / "home"
        self.workspace = self.root / "ws"
        self.workspace.mkdir(parents=True)
        self.home.mkdir(parents=True)
        self.repo_root = self.root / "repo"
        (self.repo_root / "logs" / "demo").mkdir(parents=True)
        (self.repo_root / "bin").mkdir()
        self.index_path = self.repo_root / "logs" / "demo" / ".agent-index.jsonl"

        self.home_patcher = patch(
            "agent_index.chat_core.Path.home", return_value=self.home
        )
        self.home_patcher.start()
        self.settings_patcher = patch(
            "agent_index.chat_core.load_shared_hub_settings", return_value={}
        )
        self.settings_patcher.start()

        self.runtime = ChatRuntime(
            index_path=self.index_path,
            limit=2000,
            filter_agent="",
            session_name="demo",
            follow_mode=False,
            port=8123,
            agent_send_path=self.repo_root / "bin" / "agent-send",
            workspace=str(self.workspace),
            log_dir=str(self.repo_root / "logs"),
            targets=[],
            tmux_socket="test-socket",
            hub_port=8788,
            repo_root=self.repo_root,
            session_is_active=True,
        )

    def tearDown(self) -> None:
        self.home_patcher.stop()
        self.settings_patcher.stop()
        self.tempdir.cleanup()

    def _index_entries(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        out = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def _workspace_slug(self) -> str:
        return "-" + str(self.workspace).replace("/", "-").lstrip("-")


class ClaudeSyncTests(_SyncTestBase):
    def _claude_dir(self) -> Path:
        d = self.home / ".claude" / "projects" / self._workspace_slug()
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _assistant_line(uuid: str, text: str) -> str:
        return json.dumps({
            "type": "assistant",
            "uuid": uuid,
            "message": {"content": [{"type": "text", "text": text}]},
        }) + "\n"

    def test_cold_start_does_not_flood_existing(self) -> None:
        """The Reload/Add-Agent flood-fix. First sync call must NOT append
        any existing history to the chat index."""
        f = self._claude_dir() / "sess1.jsonl"
        f.write_text(self._assistant_line("u1", "hello") + self._assistant_line("u2", "world"))
        self.runtime._sync_claude_assistant_messages("claude-1")
        self.assertEqual(self._index_entries(), [])
        # cursor should now be bound to the file at its current end
        self.assertIn("claude-1", self.runtime._claude_cursors)
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(f))

    def test_append_is_synced_after_anchor(self) -> None:
        f = self._claude_dir() / "sess1.jsonl"
        f.write_text(self._assistant_line("u1", "old"))
        self.runtime._sync_claude_assistant_messages("claude-1")  # anchor
        with f.open("a") as h:
            h.write(self._assistant_line("u2", "new!"))
        self.runtime._sync_claude_assistant_messages("claude-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("new!", entries[0]["message"])
        self.assertEqual(entries[0]["sender"], "claude-1")

    def test_path_switch_does_not_flood(self) -> None:
        """Two sessions exist; syncer was anchored to sess1, but then sess2
        becomes the latest. The new file's existing content must NOT be
        appended — we anchor to its end instead."""
        d = self._claude_dir()
        sess1 = d / "sess1.jsonl"
        sess1.write_text(self._assistant_line("u1", "old"))
        import os
        old = time.time() - 100
        os.utime(sess1, (old, old))
        self.runtime._sync_claude_assistant_messages("claude-1")  # anchor to sess1

        # A new session file appears with pre-existing content
        sess2 = d / "sess2.jsonl"
        sess2.write_text(
            self._assistant_line("u2", "history-line-1")
            + self._assistant_line("u3", "history-line-2")
        )
        self.runtime._sync_claude_assistant_messages("claude-1")
        self.assertEqual(self._index_entries(), [])
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(sess2))

        # Subsequent appends to sess2 DO get synced.
        with sess2.open("a") as h:
            h.write(self._assistant_line("u4", "live-message"))
        self.runtime._sync_claude_assistant_messages("claude-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("live-message", entries[0]["message"])

    def test_multi_instance_claim_isolates_files(self) -> None:
        """claude-1 and claude-2 exist. Each should latch onto a different
        session file — claude-2 must not steal claude-1's file."""
        d = self._claude_dir()
        sess_a = d / "a.jsonl"
        sess_a.write_text(self._assistant_line("u1", "A1"))
        import os
        older = time.time() - 50
        os.utime(sess_a, (older, older))
        sess_b = d / "b.jsonl"
        sess_b.write_text(self._assistant_line("u2", "B1"))

        self.runtime._sync_claude_assistant_messages("claude-1")
        # claude-1 claimed the newest (sess_b)
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(sess_b))

        self.runtime._sync_claude_assistant_messages("claude-2")
        # claude-2 got the next candidate (sess_a), not a duplicate claim
        self.assertEqual(self.runtime._claude_cursors["claude-2"].path, str(sess_a))

    def test_truncation_resets_and_reads(self) -> None:
        """If the file shrinks at the same path (log rotation or the CLI
        overwrote the file), we reset to offset 0 and read from start."""
        f = self._claude_dir() / "sess.jsonl"
        f.write_text(self._assistant_line("u1", "original"))
        self.runtime._sync_claude_assistant_messages("claude-1")  # anchor
        # truncate and rewrite smaller content
        f.write_text(self._assistant_line("u9", "fresh"))
        self.runtime._sync_claude_assistant_messages("claude-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("fresh", entries[0]["message"])


class QwenSyncTests(_SyncTestBase):
    def _qwen_dir(self) -> Path:
        d = self.home / ".qwen" / "projects" / self._workspace_slug() / "chats"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _line(uuid: str, text: str) -> str:
        return json.dumps({
            "type": "assistant",
            "uuid": uuid,
            "message": {"parts": [{"text": text}]},
        }) + "\n"

    def test_cold_start_no_flood(self) -> None:
        f = self._qwen_dir() / "chat1.jsonl"
        f.write_text(self._line("u1", "hello") + self._line("u2", "world"))
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        self.assertEqual(self._index_entries(), [])
        self.assertEqual(self.runtime._qwen_cursors["qwen-1"].path, str(f))

    def test_append_synced(self) -> None:
        f = self._qwen_dir() / "chat1.jsonl"
        f.write_text(self._line("u1", "old"))
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        with f.open("a") as h:
            h.write(self._line("u2", "fresh"))
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("fresh", entries[0]["message"])

    def test_thought_parts_are_skipped(self) -> None:
        f = self._qwen_dir() / "chat.jsonl"
        f.write_text("")
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        # append an assistant message that only has thought parts → no entry
        with f.open("a") as h:
            h.write(json.dumps({
                "type": "assistant",
                "uuid": "u1",
                "message": {"parts": [{"text": "internal", "thought": True}]},
            }) + "\n")
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        self.assertEqual(self._index_entries(), [])


class GeminiSyncTests(_SyncTestBase):
    def _gemini_dir(self) -> Path:
        project = self.workspace.name
        d = self.home / ".gemini" / "tmp" / project / "chats"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _write(self, path: Path, msgs: list[dict]) -> None:
        path.write_text(json.dumps({"messages": msgs}))

    def test_cold_start_no_flood(self) -> None:
        f = self._gemini_dir() / "session-1.json"
        self._write(f, [
            {"type": "gemini", "id": "aaaaaaaaaaaa", "content": "hi"},
        ])
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        self.assertEqual(self._index_entries(), [])

    def test_new_message_synced(self) -> None:
        f = self._gemini_dir() / "session-1.json"
        self._write(f, [])
        self.runtime._sync_gemini_assistant_messages("gemini-1")  # anchor
        self._write(f, [
            {"type": "gemini", "id": "bbbbbbbbbbbb", "content": "new-response"},
        ])
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("new-response", entries[0]["message"])

    def test_empty_content_skipped_and_retried(self) -> None:
        """Gemini writes an empty placeholder first, then updates with the
        actual content. The empty version must NOT be recorded as synced,
        so we pick up the filled-in message on the next poll."""
        f = self._gemini_dir() / "session-1.json"
        self._write(f, [])
        self.runtime._sync_gemini_assistant_messages("gemini-1")  # anchor
        self._write(f, [{"type": "gemini", "id": "ccccccccccc1", "content": ""}])
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        self.assertEqual(self._index_entries(), [])
        self._write(f, [{"type": "gemini", "id": "ccccccccccc1", "content": "filled"}])
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("filled", entries[0]["message"])


class CursorSyncTests(_SyncTestBase):
    def _cursor_dir(self) -> Path:
        slug = str(self.workspace).replace("/", "-").lstrip("-")
        d = self.home / ".cursor" / "projects" / slug / "agent-transcripts" / "sess-a"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _assistant_line(text: str) -> str:
        return json.dumps({
            "role": "assistant",
            "message": {"content": [{"type": "text", "text": text}]},
        }) + "\n"

    def test_append_flow(self) -> None:
        f = self._cursor_dir() / "a.jsonl"
        f.write_text(self._assistant_line("old"))
        self.runtime._sync_cursor_assistant_messages("cursor-1")  # anchor
        with f.open("a") as h:
            h.write(self._assistant_line("new"))
        self.runtime._sync_cursor_assistant_messages("cursor-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("new", entries[0]["message"])

    def test_anchor_persists_sync_state_immediately(self) -> None:
        f = self._cursor_dir() / "a.jsonl"
        f.write_text(self._assistant_line("old"))
        self.runtime._sync_cursor_assistant_messages("cursor-1")
        reloaded = self.runtime.load_sync_state()
        cursors = _load_cursor_dict(reloaded.get("cursor_cursors"))
        self.assertIn("cursor-1", cursors)
        self.assertEqual(cursors["cursor-1"].path, str(f))

    def test_git_root_slug_is_considered_for_fallback(self) -> None:
        repo_root = self.root / "repo"
        child_workspace = repo_root / "child"
        child_workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(child_workspace)
        self.runtime._workspace_git_root_cache[str(child_workspace)] = str(repo_root)
        root_slug = str(repo_root).replace("/", "-").lstrip("-")
        transcripts = self.home / ".cursor" / "projects" / root_slug / "agent-transcripts" / "sess-root"
        transcripts.mkdir(parents=True, exist_ok=True)
        target_file = transcripts / "root.jsonl"
        target_file.write_text(self._assistant_line("old"))
        self.runtime._sync_cursor_assistant_messages("cursor-1")
        self.assertIn("cursor-1", self.runtime._cursor_cursors)
        self.assertEqual(self.runtime._cursor_cursors["cursor-1"].path, str(target_file))


class CodexSyncTests(_SyncTestBase):
    @staticmethod
    def _line(text: str) -> str:
        return json.dumps({
            "type": "response_item",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {
                "role": "assistant",
                "content": [{"text": text}],
            },
        }) + "\n"

    def test_first_call_anchors(self) -> None:
        f = self.root / "rollout-1.jsonl"
        f.write_text(self._line("old"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f))
        self.assertEqual(self._index_entries(), [])

    def test_append_synced(self) -> None:
        f = self.root / "rollout-1.jsonl"
        f.write_text(self._line("old"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f))
        with f.open("a") as h:
            h.write(self._line("fresh"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f))
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("fresh", entries[0]["message"])

    def test_path_change_does_not_flood(self) -> None:
        """codex/copilot get their path via lsof, but the same path-switch
        guard must still protect them when the CLI rotates to a new rollout."""
        f1 = self.root / "rollout-1.jsonl"
        f1.write_text(self._line("old"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f1))
        f2 = self.root / "rollout-2.jsonl"
        f2.write_text(self._line("line-a") + self._line("line-b"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f2))
        self.assertEqual(self._index_entries(), [])


class CopilotSyncTests(_SyncTestBase):
    @staticmethod
    def _line(mid: str, text: str) -> str:
        return json.dumps({
            "type": "assistant.message",
            "data": {"content": text, "messageId": mid},
        }) + "\n"

    def test_truncation_now_reads_from_zero(self) -> None:
        """Regression: the old code set offset=file_size on truncation and
        skipped new content. New behavior: offset resets to 0 and we read."""
        f = self.root / "events.jsonl"
        f.write_text(self._line("m1", "old") + self._line("m2", "old2"))
        self.runtime._sync_copilot_assistant_messages("copilot-1", str(f))  # anchor
        # Shrink the file (log rotation)
        f.write_text(self._line("m9", "rotated-fresh"))
        self.runtime._sync_copilot_assistant_messages("copilot-1", str(f))
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("rotated-fresh", entries[0]["message"])

    def test_append_dedupes_on_messageId(self) -> None:
        f = self.root / "events.jsonl"
        f.write_text("")
        self.runtime._sync_copilot_assistant_messages("copilot-1", str(f))
        with f.open("a") as h:
            h.write(self._line("m1", "hi"))
        self.runtime._sync_copilot_assistant_messages("copilot-1", str(f))
        # Write the same messageId again (shouldn't happen, but dedup guards)
        with f.open("a") as h:
            h.write(self._line("m1", "hi"))
        self.runtime._sync_copilot_assistant_messages("copilot-1", str(f))
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)


class OpenCodeSyncTests(_SyncTestBase):
    def _make_db(self) -> Path:
        db_path = self.home / ".local" / "share" / "opencode" / "opencode.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE session (
                id TEXT PRIMARY KEY,
                directory TEXT,
                time_updated INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE message (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                time_created INTEGER,
                data TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE part (
                id TEXT PRIMARY KEY,
                message_id TEXT,
                time_created INTEGER,
                data TEXT
            )
        """)
        conn.commit()
        conn.close()
        return db_path

    def _add_session(self, db: Path, sid: str, t: int) -> None:
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO session VALUES (?, ?, ?)",
            (sid, str(self.workspace), t),
        )
        conn.commit()
        conn.close()

    def _add_msg(self, db: Path, mid: str, sid: str, t: int, text: str) -> None:
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO message VALUES (?, ?, ?, ?)",
            (mid, sid, t, json.dumps({"role": "assistant"})),
        )
        conn.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?)",
            (f"part-{mid}", mid, t, json.dumps({"type": "text", "text": text})),
        )
        conn.commit()
        conn.close()

    def test_cold_start_anchors_and_skips_history(self) -> None:
        """First sync anchors to first_seen_ts; messages before that are skipped."""
        db = self._make_db()
        self._add_session(db, "ses_a", 100)
        # Messages created *before* runtime's first_seen_ts (5 sec) should be skipped
        self._add_msg(db, "msg_1", "ses_a", 1000, "history1")
        self._add_msg(db, "msg_2", "ses_a", 2000, "history2")
        # first_seen_ts is set on first call; set it to 5.0s => 5000ms
        self.runtime._agent_first_seen_ts["opencode-1"] = 5.0
        self.runtime._sync_opencode_assistant_messages("opencode-1")
        self.assertEqual(self._index_entries(), [])
        self.assertEqual(
            self.runtime._opencode_cursors["opencode-1"].session_id, "ses_a"
        )

    def test_new_message_after_anchor_is_synced(self) -> None:
        """Messages created after first_seen_ts are synced."""
        db = self._make_db()
        self._add_session(db, "ses_a", 100)
        # Set first_seen to 5.0s = 5000ms
        self.runtime._agent_first_seen_ts["opencode-1"] = 5.0
        self._add_msg(db, "msg_1", "ses_a", 1000, "history")  # before first_seen
        self.runtime._sync_opencode_assistant_messages("opencode-1")  # anchor
        self._add_msg(db, "msg_2", "ses_a", 6000, "live-msg")  # after first_seen
        self.runtime._sync_opencode_assistant_messages("opencode-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("live-msg", entries[0]["message"])

    def test_session_switch_picks_up_new_messages(self) -> None:
        """When the CLI switches sessions, the syncer follows and picks up new messages."""
        db = self._make_db()
        self._add_session(db, "ses_a", 100)
        self.runtime._agent_first_seen_ts["opencode-1"] = 5.0
        self._add_msg(db, "msg_1", "ses_a", 1000, "old-session")
        self.runtime._sync_opencode_assistant_messages("opencode-1")  # claims ses_a
        self.assertEqual(
            self.runtime._opencode_cursors["opencode-1"].session_id, "ses_a"
        )
        # CLI starts new session (ses_b is newer by time_updated)
        self._add_session(db, "ses_b", 300)
        self._add_msg(db, "msg_2", "ses_b", 6000, "pong-reply")
        self.runtime._sync_opencode_assistant_messages("opencode-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("pong-reply", entries[0]["message"])
        self.assertEqual(
            self.runtime._opencode_cursors["opencode-1"].session_id, "ses_b"
        )

    def test_multi_instance_claims_different_sessions(self) -> None:
        db = self._make_db()
        self._add_session(db, "ses_a", 100)
        self._add_session(db, "ses_b", 200)  # newer
        self.runtime._agent_first_seen_ts["opencode-1"] = 0.001
        self.runtime._agent_first_seen_ts["opencode-2"] = 0.001
        self.runtime._sync_opencode_assistant_messages("opencode-1")
        self.runtime._sync_opencode_assistant_messages("opencode-2")
        self.assertEqual(
            self.runtime._opencode_cursors["opencode-1"].session_id, "ses_b"
        )
        self.assertEqual(
            self.runtime._opencode_cursors["opencode-2"].session_id, "ses_a"
        )


class SyncStateMigrationTests(_SyncTestBase):
    def test_old_bare_int_offsets_are_discarded(self) -> None:
        """A state file written by the pre-refactor version used bare ints.
        On load, those entries must be dropped so the syncer re-anchors."""
        self.runtime.sync_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime.sync_state_path.write_text(json.dumps({
            "claude_offsets": {"claude-1": 500},
            "cursor_state": {"cursor-1": ["/tmp/x.jsonl", 100]},
        }))
        # Rebuild runtime to re-trigger load
        self.runtime._sync_state = self.runtime.load_sync_state()
        self.runtime._claude_cursors = _load_cursor_dict(
            self.runtime._sync_state.get("claude_cursors")
        )
        self.runtime._cursor_cursors = _load_cursor_dict(
            self.runtime._sync_state.get("cursor_cursors")
        ) or _load_cursor_dict(self.runtime._sync_state.get("cursor_state"))
        self.assertEqual(self.runtime._claude_cursors, {})
        self.assertIn("cursor-1", self.runtime._cursor_cursors)

    def test_save_and_reload_round_trips_cursors(self) -> None:
        self.runtime._claude_cursors["claude-1"] = NativeLogCursor("/x.jsonl", 42)
        self.runtime._opencode_cursors["opencode-1"] = OpenCodeCursor("ses", "msg")
        self.runtime.save_sync_state()
        reloaded = self.runtime.load_sync_state()
        self.assertEqual(
            _load_cursor_dict(reloaded["claude_cursors"])["claude-1"].offset, 42
        )
        self.assertEqual(
            _load_opencode_dict(reloaded["opencode_cursors"])["opencode-1"].last_msg_id,
            "msg",
        )

    def test_agent_first_seen_ts_round_trips(self) -> None:
        self.runtime._agent_first_seen_ts["claude-1"] = 1712345678.5
        self.runtime._agent_first_seen_ts["opencode-1"] = 1712345700.0
        self.runtime.save_sync_state()
        reloaded = self.runtime.load_sync_state()
        raw = reloaded.get("agent_first_seen_ts", {})
        self.assertAlmostEqual(raw["claude-1"], 1712345678.5)
        self.assertAlmostEqual(raw["opencode-1"], 1712345700.0)

    def test_dedup_cursor_claims_on_load(self) -> None:
        """If two agents have the same path in persisted state, dedup on load keeps first."""
        self.runtime._qwen_cursors = {
            "qwen-1": NativeLogCursor("/shared.jsonl", 10),
            "qwen-2": NativeLogCursor("/shared.jsonl", 20),
        }
        deduped = _dedup_cursor_claims(self.runtime._qwen_cursors)
        self.assertIn("qwen-1", deduped)
        self.assertNotIn("qwen-2", deduped)

    def test_sync_state_heartbeat_is_throttled(self) -> None:
        with patch.object(self.runtime, "save_sync_state", wraps=self.runtime.save_sync_state) as save_mock:
            with patch(
                "agent_index.chat_core.time.time",
                side_effect=[100.0, 100.5, 105.0, 112.0, 112.5],
            ):
                self.runtime.maybe_heartbeat_sync_state(interval_seconds=10.0)
                self.runtime.maybe_heartbeat_sync_state(interval_seconds=10.0)
                self.runtime.maybe_heartbeat_sync_state(interval_seconds=10.0)
        self.assertEqual(save_mock.call_count, 2)


class PaneCacheInvalidationTests(_SyncTestBase):
    @staticmethod
    def _ok_tmux_result() -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=["tmux"],
            returncode=0,
            stdout="",
            stderr="",
        )

    def test_restart_clears_native_log_cache(self) -> None:
        self.runtime._pane_native_log_paths["%31"] = ("1234", "/tmp/a.jsonl")
        with patch.object(self.runtime, "pane_id_for_agent", return_value="%31"):
            with patch("agent_index.chat_core.subprocess.run") as run_mock:
                run_mock.side_effect = [self._ok_tmux_result(), self._ok_tmux_result()]
                ok, _detail = self.runtime.restart_agent_pane("claude-1")
        self.assertTrue(ok)
        self.assertNotIn("%31", self.runtime._pane_native_log_paths)

    def test_resume_clears_native_log_cache(self) -> None:
        self.runtime._pane_native_log_paths["%32"] = ("5678", "/tmp/b.jsonl")
        with patch.object(self.runtime, "pane_id_for_agent", return_value="%32"):
            with patch("agent_index.chat_core.subprocess.run") as run_mock:
                run_mock.side_effect = [self._ok_tmux_result(), self._ok_tmux_result()]
                ok, _detail = self.runtime.resume_agent_pane("claude-1")
        self.assertTrue(ok)
        self.assertNotIn("%32", self.runtime._pane_native_log_paths)


class RuntimeEventParserTests(unittest.TestCase):
    """Tests for _parse_cursor_jsonl_runtime — extracts tool_use events for Running display."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write(self, name: str, lines: list[dict]) -> Path:
        p = self.root / name
        with p.open("w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
        return p

    def test_claude_tool_use_extracted(self) -> None:
        p = self._write("claude.jsonl", [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}},
            ]}},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=5)
        self.assertIsNotNone(events)
        self.assertEqual(len(events), 1)
        self.assertIn("Bash(git status)", events[0]["text"])

    def test_copilot_tool_execution_start(self) -> None:
        p = self._write("copilot.jsonl", [
            {"type": "tool.execution_start", "data": {
                "toolName": "view",
                "arguments": {"path": "/tmp/file.py"},
            }},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=5)
        self.assertIsNotNone(events)
        self.assertEqual(len(events), 1)
        self.assertIn("view(/tmp/file.py)", events[0]["text"])

    def test_cursor_role_assistant_tool_use(self) -> None:
        p = self._write("cursor.jsonl", [
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Grep", "input": {"pattern": "TODO"}},
            ]}},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=5)
        self.assertIsNotNone(events)
        self.assertEqual(len(events), 1)
        self.assertIn("Grep(TODO)", events[0]["text"])

    def test_non_tool_entries_skipped(self) -> None:
        p = self._write("mixed.jsonl", [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}},
            {"type": "user", "message": {"content": "hi"}},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=5)
        self.assertIsNotNone(events)
        self.assertEqual(len(events), 0)

    def test_empty_file(self) -> None:
        p = self.root / "empty.jsonl"
        p.write_text("")
        events = _parse_cursor_jsonl_runtime(str(p), limit=5)
        self.assertIsNotNone(events)
        self.assertEqual(len(events), 0)


if __name__ == "__main__":
    unittest.main()
