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

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import time
import unicodedata
import unittest
from datetime import UTC as dt_UTC, datetime as dt_datetime
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.jsonl_append import append_jsonl_entry
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
    _native_path_claim_key,
    _parse_native_codex_log,
    _parse_native_gemini_log,
    _parse_cursor_jsonl_runtime,
    _pick_latest_unclaimed,
    _pick_latest_unclaimed_for_agent,
    _resolve_native_log_file,
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

    def test_same_file_alias_path_keeps_existing_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real.jsonl"
            alias = root / "alias.jsonl"
            real.write_text("x" * 300, encoding="utf-8")
            alias.symlink_to(real)
            cursors = {"a": NativeLogCursor(str(real), 100)}
            result = _advance_native_cursor(cursors, "a", str(alias), 300)
            self.assertEqual(result, 100)
            self.assertEqual(cursors["a"], NativeLogCursor(str(real), 100))


class ResolveNativeLogFileTests(unittest.TestCase):
    def test_picks_most_recent_matching_open_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.jsonl"
            new = root / "new.jsonl"
            old.write_text("old", encoding="utf-8")
            new.write_text("new", encoding="utf-8")
            now = time.time()
            os.utime(old, (now - 60, now - 60))
            os.utime(new, (now, now))
            lsof_stdout = f"n{old}\n" f"n{new}\n"
            lsof_result = subprocess.CompletedProcess(
                args=["lsof"],
                returncode=0,
                stdout=lsof_stdout,
                stderr="",
            )
            with patch("agent_index.chat_core._get_process_tree", return_value={"123"}):
                with patch("agent_index.chat_core.subprocess.run", return_value=lsof_result):
                    picked = _resolve_native_log_file("123", r"\.jsonl$")
            self.assertEqual(picked, str(new))

    def test_prefers_existing_file_over_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "exists.jsonl"
            existing.write_text("x", encoding="utf-8")
            missing = root / "missing.jsonl"
            lsof_stdout = f"n{missing}\n" f"n{existing}\n"
            lsof_result = subprocess.CompletedProcess(
                args=["lsof"],
                returncode=0,
                stdout=lsof_stdout,
                stderr="",
            )
            with patch("agent_index.chat_core._get_process_tree", return_value={"123"}):
                with patch("agent_index.chat_core.subprocess.run", return_value=lsof_result):
                    picked = _resolve_native_log_file("123", r"\.jsonl$")
            self.assertEqual(picked, str(existing))


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

    def test_skips_claimed_file_when_path_is_alias(self) -> None:
        shared = self._make_file("shared.jsonl", 0)
        alias = self.root / "shared-alias.jsonl"
        alias.symlink_to(shared)
        cursors = {"claude-1": NativeLogCursor(str(alias), 500)}
        pick = _pick_latest_unclaimed([shared], cursors, "claude-2")
        self.assertIsNone(pick)

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

    def test_for_agent_first_bind_falls_back_when_min_mtime_excludes_all(self) -> None:
        """New agents should still bind to a local file for stable Sync Status."""
        old = self._make_file("old.jsonl", -300)
        min_mtime = time.time() + 100
        pick = _pick_latest_unclaimed_for_agent(
            [old],
            {},
            "agent-1",
            min_mtime=min_mtime,
        )
        self.assertEqual(pick, old)

    def test_for_agent_initial_fallback_can_be_disabled(self) -> None:
        old = self._make_file("old.jsonl", -300)
        min_mtime = time.time() + 100
        pick = _pick_latest_unclaimed_for_agent(
            [old],
            {},
            "agent-1",
            min_mtime=min_mtime,
            allow_initial_fallback=False,
        )
        self.assertIsNone(pick)

    def test_for_agent_bound_cursor_does_not_fallback_to_stale_file(self) -> None:
        """Once bound, we should not silently jump to stale files below min_mtime."""
        old = self._make_file("old.jsonl", -300)
        min_mtime = time.time() + 100
        pick = _pick_latest_unclaimed_for_agent(
            [old],
            {"agent-1": NativeLogCursor(str(old), old.stat().st_size)},
            "agent-1",
            min_mtime=min_mtime,
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

    def test_duplicate_alias_paths_keep_alphabetically_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "shared.jsonl"
            alias = root / "shared-link.jsonl"
            shared.write_text("x", encoding="utf-8")
            alias.symlink_to(shared)
            cursors = {
                "qwen-2": NativeLogCursor(str(alias), 100),
                "qwen-1": NativeLogCursor(str(shared), 50),
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

    def _append_user_target_entry(self, target: str) -> None:
        entry = {
            "timestamp": "2026-01-01 00:00:00",
            "session": "demo",
            "sender": "user",
            "targets": [target],
            "message": "[From: User]\nping",
            "msg_id": f"seed-{target}",
        }
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")


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

    @staticmethod
    def _assistant_line_with_timestamp(uuid: str, text: str, iso_ts: str) -> str:
        return json.dumps({
            "type": "assistant",
            "uuid": uuid,
            "timestamp": iso_ts,
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

    def test_first_bind_backfills_recent_assistant_entry(self) -> None:
        f = self._claude_dir() / "sess1.jsonl"
        now = time.time()
        self.runtime._agent_first_seen_ts["claude-1"] = now - 5
        iso_ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now))
        f.write_text(self._assistant_line_with_timestamp("u1", "first-reply", iso_ts))

        self.runtime._sync_claude_assistant_messages("claude-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("first-reply", entries[0]["message"])
        self.assertEqual(entries[0]["sender"], "claude-1")

    def test_backfill_window_recovers_entry_missed_by_cursor_advance(self) -> None:
        f = self._claude_dir() / "sess1.jsonl"
        f.write_text("")
        self.runtime._sync_claude_assistant_messages("claude-1")  # establish first bind/backfill window

        now = time.time()
        iso_ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now))
        with f.open("a") as h:
            h.write(self._assistant_line_with_timestamp("u1", "recover-me", iso_ts))
        # Simulate a cursor that already advanced beyond the new line.
        self.runtime._claude_cursors["claude-1"] = NativeLogCursor(str(f), f.stat().st_size)

        self.runtime._sync_claude_assistant_messages("claude-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("recover-me", entries[0]["message"])

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

    def test_single_shared_file_stays_with_first_claimer(self) -> None:
        """When separation is impossible (single Claude log), keep one owner."""
        shared = self._claude_dir() / "shared.jsonl"
        shared.write_text(self._assistant_line("u1", "history"))

        self.runtime._sync_claude_assistant_messages("claude-1")
        self.runtime._sync_claude_assistant_messages("claude-2")
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(shared))
        self.assertNotIn("claude-2", self.runtime._claude_cursors)

        with shared.open("a") as h:
            h.write(self._assistant_line("u2", "live-shared"))

        self.runtime._sync_claude_assistant_messages("claude-2")
        self.runtime._sync_claude_assistant_messages("claude-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sender"], "claude-1")
        self.assertIn("live-shared", entries[0]["message"])

    def test_existing_cursor_path_is_preferred_over_newer_candidate(self) -> None:
        d = self._claude_dir()
        old_path = d / "old.jsonl"
        old_path.write_text(self._assistant_line("u1", "old"))
        older = time.time() - 50
        os.utime(old_path, (older, older))
        self.runtime._agent_first_seen_ts["claude-2"] = time.time()
        self.runtime._claude_cursors["claude-1"] = NativeLogCursor(
            str(old_path),
            old_path.stat().st_size,
        )
        new_path = d / "new.jsonl"
        new_path.write_text(self._assistant_line("u2", "new"))

        self.runtime._sync_claude_assistant_messages("claude-1", workspace_hint=str(self.workspace))
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(old_path))
        self.assertEqual(self._index_entries(), [])

    def test_workspace_hint_falls_back_to_git_root_slug(self) -> None:
        repo_root = self.root / "repo-root"
        child_workspace = repo_root / "child"
        child_workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(child_workspace)
        self.runtime._workspace_git_root_cache[str(child_workspace)] = str(repo_root)
        self.runtime._agent_first_seen_ts["claude-1"] = time.time() - 60
        self._append_user_target_entry("claude-1")

        root_slug = "-" + str(repo_root).replace("/", "-").lstrip("-")
        root_dir = self.home / ".claude" / "projects" / root_slug
        root_dir.mkdir(parents=True, exist_ok=True)
        target = root_dir / "root.jsonl"
        target.write_text(self._assistant_line("u1", "old"))

        self.runtime._sync_claude_assistant_messages(
            "claude-1",
            workspace_hint=str(child_workspace),
        )
        self.assertIn("claude-1", self.runtime._claude_cursors)
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(target))

    def test_workspace_hint_git_root_fallback_is_delayed_on_cold_start(self) -> None:
        repo_root = self.root / "repo-root"
        child_workspace = repo_root / "child"
        child_workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(child_workspace)
        self.runtime._workspace_git_root_cache[str(child_workspace)] = str(repo_root)

        root_slug = "-" + str(repo_root).replace("/", "-").lstrip("-")
        root_dir = self.home / ".claude" / "projects" / root_slug
        root_dir.mkdir(parents=True, exist_ok=True)
        target = root_dir / "root.jsonl"
        target.write_text(self._assistant_line("u1", "old"))

        self.runtime._sync_claude_assistant_messages(
            "claude-1",
            workspace_hint=str(child_workspace),
        )
        self.assertNotIn("claude-1", self.runtime._claude_cursors)

        self.runtime._agent_first_seen_ts["claude-1"] = time.time() - 60
        self._append_user_target_entry("claude-1")
        self.runtime._sync_claude_assistant_messages(
            "claude-1",
            workspace_hint=str(child_workspace),
        )
        self.assertIn("claude-1", self.runtime._claude_cursors)
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(target))

    def test_workspace_hint_accepts_hyphenized_slug_variant(self) -> None:
        workspace = self.root / "project_with_underscores"
        workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(workspace)

        raw_slug = str(workspace).replace("/", "-").lstrip("-")
        hyphen_slug = "-" + raw_slug.replace("_", "-")
        alt_dir = self.home / ".claude" / "projects" / hyphen_slug
        alt_dir.mkdir(parents=True, exist_ok=True)
        target = alt_dir / "variant.jsonl"
        target.write_text(self._assistant_line("u1", "old"))

        self.runtime._sync_claude_assistant_messages(
            "claude-1",
            workspace_hint=str(workspace),
        )
        self.assertIn("claude-1", self.runtime._claude_cursors)
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(target))

    def test_workspace_hint_accepts_punctuation_heavy_slug_variant(self) -> None:
        workspace = self.root / "GoogleDrive-foo@gmail.com" / "マイドライブ" / "untitled folder2" / "test3"
        workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(workspace)

        raw_slug = unicodedata.normalize("NFC", str(workspace).replace("/", "-").lstrip("-"))
        provider_slug = "-" + re.sub(r"[^A-Za-z0-9-]", "-", raw_slug).strip("-")
        alt_dir = self.home / ".claude" / "projects" / provider_slug
        alt_dir.mkdir(parents=True, exist_ok=True)
        target = alt_dir / "variant.jsonl"
        target.write_text(self._assistant_line("u1", "old"))

        self.runtime._sync_claude_assistant_messages(
            "claude-1",
            workspace_hint=str(workspace),
        )
        self.assertIn("claude-1", self.runtime._claude_cursors)
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(target))

    def test_workspace_hint_parent_does_not_override_session_workspace(self) -> None:
        import os

        parent_workspace = self.root / "workspace-parent"
        session_workspace = parent_workspace / "child"
        parent_workspace.mkdir(parents=True, exist_ok=True)
        session_workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(session_workspace)

        parent_slug = "-" + str(parent_workspace).replace("/", "-").lstrip("-")
        parent_dir = self.home / ".claude" / "projects" / parent_slug
        parent_dir.mkdir(parents=True, exist_ok=True)
        parent_file = parent_dir / "parent.jsonl"
        parent_file.write_text(self._assistant_line("u1", "parent-history"))

        child_slug = "-" + str(session_workspace).replace("/", "-").lstrip("-")
        child_dir = self.home / ".claude" / "projects" / child_slug
        child_dir.mkdir(parents=True, exist_ok=True)
        child_file = child_dir / "child.jsonl"
        child_file.write_text(self._assistant_line("u2", "child-history"))
        now = time.time()
        os.utime(parent_file, (now + 20, now + 20))
        os.utime(child_file, (now, now))

        self.runtime._sync_claude_assistant_messages(
            "claude-1",
            workspace_hint=str(parent_workspace),
        )
        self.assertIn("claude-1", self.runtime._claude_cursors)
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, str(child_file))

    def test_workspace_hint_parent_without_child_files_does_not_bind_parent(self) -> None:
        parent_workspace = self.root / "workspace-parent"
        session_workspace = parent_workspace / "child"
        parent_workspace.mkdir(parents=True, exist_ok=True)
        session_workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(session_workspace)

        parent_slug = "-" + str(parent_workspace).replace("/", "-").lstrip("-")
        parent_dir = self.home / ".claude" / "projects" / parent_slug
        parent_dir.mkdir(parents=True, exist_ok=True)
        parent_file = parent_dir / "parent.jsonl"
        parent_file.write_text(self._assistant_line("u1", "parent-history"))

        self.runtime._sync_claude_assistant_messages(
            "claude-1",
            workspace_hint=str(parent_workspace),
        )
        self.assertNotIn("claude-1", self.runtime._claude_cursors)

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

    def test_workspace_hint_can_rebind_from_stale_session_workspace(self) -> None:
        """When a Claude pane runs in a workspace different from the session's
        stored workspace, the pane workspace hint must drive file selection."""
        import os

        stale_dir = self._claude_dir()
        stale = stale_dir / "stale.jsonl"
        stale.write_text(self._assistant_line("u1", "stale-history"))
        old = time.time() - 600
        os.utime(stale, (old, old))

        alt_workspace = self.root / "alt-ws"
        alt_workspace.mkdir(parents=True, exist_ok=True)
        alt_slug = "-" + str(alt_workspace).replace("/", "-").lstrip("-")
        alt_dir = self.home / ".claude" / "projects" / alt_slug
        alt_dir.mkdir(parents=True, exist_ok=True)
        active = alt_dir / "active.jsonl"
        active.write_text(self._assistant_line("u2", "history"))

        # Simulate a stale pre-existing claim to the wrong workspace.
        self.runtime._claude_cursors["claude-2"] = NativeLogCursor(str(stale), stale.stat().st_size)
        self.runtime._agent_first_seen_ts["claude-2"] = time.time() - 10

        self.runtime._sync_claude_assistant_messages("claude-2", workspace_hint=str(alt_workspace))
        self.assertEqual(self._index_entries(), [])
        self.assertEqual(self.runtime._claude_cursors["claude-2"].path, str(active))

        with active.open("a") as h:
            h.write(self._assistant_line("u3", "live-reply"))
        self.runtime._sync_claude_assistant_messages("claude-2", workspace_hint=str(alt_workspace))
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["sender"], "claude-2")
        self.assertIn("live-reply", entries[0]["message"])


class QwenSyncTests(_SyncTestBase):
    def _qwen_dir(self) -> Path:
        d = self.home / ".qwen" / "projects" / self._workspace_slug() / "chats"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _line(uuid: str, text: str, *, timestamp: str | None = None) -> str:
        payload: dict = {
            "type": "assistant",
            "uuid": uuid,
            "message": {"parts": [{"text": text}]},
        }
        if timestamp:
            payload["timestamp"] = timestamp
        return json.dumps(payload) + "\n"

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

    def test_thought_parts_are_ignored_for_qwen(self) -> None:
        f = self._qwen_dir() / "chat.jsonl"
        f.write_text("")
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        # append an assistant message that only has thought parts
        with f.open("a") as h:
            h.write(json.dumps({
                "type": "assistant",
                "uuid": "u1",
                "message": {"parts": [{"text": "internal", "thought": True}]},
            }) + "\n")
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        self.assertEqual(self._index_entries(), [])

    def test_first_bind_backfills_recent_assistant_entry(self) -> None:
        now_iso = dt_datetime.now(dt_UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        f = self._qwen_dir() / "chat-recent.jsonl"
        f.write_text(self._line("u-recent", "recent-qwen", timestamp=now_iso))
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("recent-qwen", entries[0]["message"])

    def test_hyphenized_workspace_slug_variant_is_resolved(self) -> None:
        workspace = self.root / "Project_With_Underscores"
        workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(workspace)
        raw_slug = str(workspace).replace("/", "-").lstrip("-")
        hyphen_slug = "-" + raw_slug.replace("_", "-")
        alt_dir = self.home / ".qwen" / "projects" / hyphen_slug / "chats"
        alt_dir.mkdir(parents=True, exist_ok=True)
        f = alt_dir / "chat-alt.jsonl"
        f.write_text(self._line("u1", "history"))
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        self.assertIn("qwen-1", self.runtime._qwen_cursors)
        self.assertEqual(self.runtime._qwen_cursors["qwen-1"].path, str(f))
        self.assertEqual(self._index_entries(), [])

    def test_punctuation_heavy_workspace_slug_variant_is_resolved(self) -> None:
        workspace = self.root / "GoogleDrive-foo@gmail.com" / "マイドライブ" / "untitled folder2" / "test3"
        workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(workspace)
        raw_slug = str(workspace).replace("/", "-").lstrip("-")
        provider_slug = "-" + re.sub(r"[^A-Za-z0-9-]", "-", raw_slug).strip("-")
        alt_dir = self.home / ".qwen" / "projects" / provider_slug / "chats"
        alt_dir.mkdir(parents=True, exist_ok=True)
        f = alt_dir / "chat-alt.jsonl"
        f.write_text(self._line("u1", "history"))
        self.runtime._sync_qwen_assistant_messages("qwen-1")
        self.assertIn("qwen-1", self.runtime._qwen_cursors)
        self.assertEqual(self.runtime._qwen_cursors["qwen-1"].path, str(f))
        self.assertEqual(self._index_entries(), [])

    def test_existing_cursor_path_is_preferred_over_newer_candidate(self) -> None:
        old_file = self._qwen_dir() / "old.jsonl"
        old_file.write_text(self._line("u1", "old"))
        older = time.time() - 50
        os.utime(old_file, (older, older))
        self.runtime._agent_first_seen_ts["qwen-2"] = time.time()
        self.runtime._qwen_cursors["qwen-1"] = NativeLogCursor(
            str(old_file),
            old_file.stat().st_size,
        )
        new_file = self._qwen_dir() / "new.jsonl"
        new_file.write_text(self._line("u2", "new"))

        self.runtime._sync_qwen_assistant_messages("qwen-1")
        self.assertEqual(self.runtime._qwen_cursors["qwen-1"].path, str(old_file))
        self.assertEqual(self._index_entries(), [])

    def test_sticky_cursor_is_ignored_when_outside_workspace_dirs(self) -> None:
        stale_dir = self.home / ".qwen" / "projects" / "-other-workspace" / "chats"
        stale_dir.mkdir(parents=True, exist_ok=True)
        stale_file = stale_dir / "stale.jsonl"
        stale_file.write_text(self._line("u-old", "old"))
        self.runtime._agent_first_seen_ts["qwen-2"] = time.time()
        self.runtime._qwen_cursors["qwen-1"] = NativeLogCursor(
            str(stale_file),
            stale_file.stat().st_size,
        )
        workspace_file = self._qwen_dir() / "active.jsonl"
        workspace_file.write_text(self._line("u-new", "new"))

        self.runtime._sync_qwen_assistant_messages("qwen-1")
        self.assertIn("qwen-1", self.runtime._qwen_cursors)
        self.assertTrue(Path(self.runtime._qwen_cursors["qwen-1"].path).samefile(workspace_file))
        self.assertEqual(self._index_entries(), [])

    def test_peer_first_bind_does_not_claim_older_workspace_file(self) -> None:
        old_file = self._qwen_dir() / "old-peer.jsonl"
        old_file.write_text(self._line("u-old", "old"))
        now = time.time()
        os.utime(old_file, (now - 10, now - 10))
        self.runtime._agent_first_seen_ts["qwen-1"] = now
        self.runtime._agent_first_seen_ts["qwen-2"] = now
        self.runtime._sync_qwen_assistant_messages("qwen-2")
        self.assertNotIn("qwen-2", self.runtime._qwen_cursors)
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
        self.assertNotIn("kind", entries[0])

    def test_planning_style_text_becomes_runtime_only(self) -> None:
        f = self._gemini_dir() / "session-thinking.json"
        self._write(f, [])
        self.runtime._sync_gemini_assistant_messages("gemini-1")  # anchor
        self._write(
            f,
            [
                {
                    "type": "gemini",
                    "id": "planmsg000001",
                    "content": "I will inspect the files and report back.",
                },
            ],
        )
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        self.assertEqual(self._index_entries(), [])
        events = _parse_native_gemini_log(str(f), limit=5, workspace=str(self.workspace))
        self.assertTrue(events)
        self.assertTrue(events[-1]["text"].startswith("Reading "))

    def test_thought_flagged_content_part_becomes_runtime_only(self) -> None:
        f = self._gemini_dir() / "session-thinking-parts.json"
        self._write(f, [])
        self.runtime._sync_gemini_assistant_messages("gemini-1")  # anchor
        self._write(
            f,
            [
                {
                    "type": "gemini",
                    "id": "planmsg000002",
                    "content": [
                        {"text": "I'll check this first.", "thought": True},
                    ],
                },
            ],
        )
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        self.assertEqual(self._index_entries(), [])
        events = _parse_native_gemini_log(str(f), limit=5, workspace=str(self.workspace))
        self.assertTrue(events)
        self.assertTrue(events[-1]["text"].startswith("Reading "))

    def test_gemini_i_will_search_becomes_runtime_event(self) -> None:
        f = self._gemini_dir() / "session-search.json"
        self._write(
            f,
            [
                {
                    "type": "gemini",
                    "id": "searchmsg001",
                    "content": "I will search for `foo` in `lib/agent_index/chat_status_core.py`.",
                },
            ],
        )
        events = _parse_native_gemini_log(str(f), limit=5, workspace=str(self.workspace))
        self.assertTrue(events)
        self.assertEqual(events[-1]["text"], "Searching foo in lib/agent_index/chat_status_core.py")

    def test_gemini_i_will_update_becomes_runtime_event(self) -> None:
        f = self._gemini_dir() / "session-update.json"
        self._write(
            f,
            [
                {
                    "type": "gemini",
                    "id": "updatemsg001",
                    "content": "I will update `lib/agent_index/hub_home_mobile_template.html` to align spacing.",
                },
            ],
        )
        events = _parse_native_gemini_log(str(f), limit=5, workspace=str(self.workspace))
        self.assertTrue(events)
        self.assertEqual(events[-1]["text"], "Updating lib/agent_index/hub_home_mobile_template.html")

    def test_long_gemini_i_will_update_is_not_synced_to_jsonl(self) -> None:
        f = self._gemini_dir() / "session-long-plan.json"
        self._write(f, [])
        self.runtime._sync_gemini_assistant_messages("gemini-1")  # anchor
        self._write(
            f,
            [
                {
                    "type": "gemini",
                    "id": "longplan0001",
                    "content": "I will update `lib/agent_index/chat_template.html` "
                    + ("to remove transitions and transformations " * 20),
                },
            ],
        )
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        self.assertEqual(self._index_entries(), [])

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

    def test_first_bind_backfills_recent_message(self) -> None:
        f = self._gemini_dir() / "session-recent.json"
        now_iso = dt_datetime.now(dt_UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        self._write(
            f,
            [
                {
                    "type": "gemini",
                    "id": "recentmsg123",
                    "timestamp": now_iso,
                    "content": "recent-gemini",
                },
            ],
        )
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("recent-gemini", entries[0]["message"])

    def test_hyphenized_lowercase_workspace_dir_variant_is_resolved(self) -> None:
        workspace = self.root / "Test_after_Various"
        workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(workspace)
        variant_dir = self.home / ".gemini" / "tmp" / "test-after-various" / "chats"
        variant_dir.mkdir(parents=True, exist_ok=True)
        f = variant_dir / "session-alt.json"
        self._write(f, [{"type": "gemini", "id": "altmsg123456", "content": "history"}])
        self.runtime._sync_gemini_assistant_messages("gemini-1")
        self.assertIn("gemini-1", self.runtime._gemini_cursors)
        self.assertTrue(Path(self.runtime._gemini_cursors["gemini-1"].path).samefile(f))
        self.assertEqual(self._index_entries(), [])

    def test_existing_cursor_path_is_preferred_over_newer_candidate(self) -> None:
        old_file = self._gemini_dir() / "session-old.json"
        self._write(old_file, [{"type": "gemini", "id": "oldmsg123456", "content": "old"}])
        older = time.time() - 50
        os.utime(old_file, (older, older))
        self.runtime._agent_first_seen_ts["gemini-2"] = time.time()
        self.runtime._gemini_cursors["gemini-1"] = NativeLogCursor(
            str(old_file),
            old_file.stat().st_size,
        )
        new_file = self._gemini_dir() / "session-new.json"
        self._write(new_file, [{"type": "gemini", "id": "newmsg123456", "content": "new"}])

        self.runtime._sync_gemini_assistant_messages("gemini-1")
        self.assertEqual(self.runtime._gemini_cursors["gemini-1"].path, str(old_file))
        self.assertEqual(self._index_entries(), [])

    def test_sticky_cursor_is_ignored_when_outside_workspace_dirs(self) -> None:
        stale_dir = self.home / ".gemini" / "tmp" / "other-workspace" / "chats"
        stale_dir.mkdir(parents=True, exist_ok=True)
        stale_file = stale_dir / "session-stale.json"
        self._write(stale_file, [{"type": "gemini", "id": "stale00000001", "content": "old"}])
        self.runtime._agent_first_seen_ts["gemini-2"] = time.time()
        self.runtime._gemini_cursors["gemini-1"] = NativeLogCursor(
            str(stale_file),
            stale_file.stat().st_size,
        )
        workspace_file = self._gemini_dir() / "session-active.json"
        self._write(workspace_file, [{"type": "gemini", "id": "active0000001", "content": "new"}])

        self.runtime._sync_gemini_assistant_messages("gemini-1")
        self.assertIn("gemini-1", self.runtime._gemini_cursors)
        self.assertTrue(Path(self.runtime._gemini_cursors["gemini-1"].path).samefile(workspace_file))
        self.assertEqual(self._index_entries(), [])

    def test_peer_first_bind_does_not_claim_older_workspace_file(self) -> None:
        old_file = self._gemini_dir() / "session-old-peer.json"
        self._write(old_file, [{"type": "gemini", "id": "oldpeer111111", "content": "old"}])
        now = time.time()
        os.utime(old_file, (now - 10, now - 10))
        self.runtime._agent_first_seen_ts["gemini-1"] = now
        self.runtime._agent_first_seen_ts["gemini-2"] = now
        self.runtime._sync_gemini_assistant_messages("gemini-2")
        self.assertNotIn("gemini-2", self.runtime._gemini_cursors)
        self.assertEqual(self._index_entries(), [])


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

    def _cursor_store_db(self) -> Path:
        workspace_key = hashlib.md5(str(self.workspace).encode("utf-8")).hexdigest()
        d = self.home / ".cursor" / "chats" / workspace_key / "agent-a"
        d.mkdir(parents=True, exist_ok=True)
        db = d / "store.db"
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS blobs (id TEXT PRIMARY KEY, data BLOB)")
            conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('0', '7b7d')")
            conn.commit()
        finally:
            conn.close()
        return db

    @staticmethod
    def _insert_cursor_store_assistant_blob(db: Path, blob_id: str, text: str) -> None:
        payload = {
            "id": blob_id,
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        }
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO blobs(id, data) VALUES(?, ?)",
                (blob_id, json.dumps(payload, ensure_ascii=False).encode("utf-8")),
            )
            conn.commit()
        finally:
            conn.close()

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

    def test_store_db_append_flow(self) -> None:
        db = self._cursor_store_db()
        self._insert_cursor_store_assistant_blob(db, "old-msg-1", "old")
        self.runtime._sync_cursor_assistant_messages("cursor-1")  # anchor
        self._insert_cursor_store_assistant_blob(db, "new-msg-2", "new")
        self.runtime._sync_cursor_assistant_messages("cursor-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("new", entries[0]["message"])

    def test_store_db_workspace_md5_path_is_discovered(self) -> None:
        db = self._cursor_store_db()
        self._insert_cursor_store_assistant_blob(db, "old-msg-1", "old")
        self.runtime._sync_cursor_assistant_messages("cursor-1")
        self.assertIn("cursor-1", self.runtime._cursor_cursors)
        self.assertTrue(Path(self.runtime._cursor_cursors["cursor-1"].path).samefile(db))
        self.assertEqual(self._index_entries(), [])


class CodexSyncTests(_SyncTestBase):
    @staticmethod
    def _line(text: str, *, timestamp: str = "2026-01-01T00:00:00Z") -> str:
        return json.dumps({
            "type": "response_item",
            "timestamp": timestamp,
            "payload": {
                "role": "assistant",
                "content": [{"text": text}],
            },
        }) + "\n"

    @staticmethod
    def _reasoning_line(text: str, *, timestamp: str = "2026-01-01T00:00:00Z") -> str:
        return json.dumps(
            {
                "type": "response_item",
                "timestamp": timestamp,
                "payload": {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": text}],
                },
            }
        ) + "\n"

    @staticmethod
    def _agent_reasoning_event(text: str, *, timestamp: str = "2026-01-01T00:00:00Z") -> str:
        return json.dumps(
            {
                "type": "event_msg",
                "timestamp": timestamp,
                "payload": {"type": "agent_reasoning", "text": text},
            }
        ) + "\n"

    def _session_meta_line(self, cwd: str) -> str:
        return json.dumps({
            "type": "session_meta",
            "payload": {"cwd": cwd},
        }) + "\n"

    def _codex_rollout_file(self, name: str) -> Path:
        d = self.home / ".codex" / "sessions" / "2026" / "04" / "06"
        d.mkdir(parents=True, exist_ok=True)
        return d / name

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

    def test_reasoning_response_item_is_tagged_as_agent_thinking(self) -> None:
        f = self.root / "rollout-thinking.jsonl"
        f.write_text(self._line("old"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f))
        with f.open("a") as h:
            h.write(self._reasoning_line("**Planning edits**"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f))
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("Planning edits", entries[0]["message"])
        self.assertEqual(entries[0].get("kind"), "agent-thinking")

    def test_event_msg_agent_reasoning_is_tagged_as_agent_thinking(self) -> None:
        f = self.root / "rollout-agent-reasoning.jsonl"
        f.write_text(self._line("old"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f))
        with f.open("a") as h:
            h.write(self._agent_reasoning_event("Working through options"))
        self.runtime._sync_codex_assistant_messages("codex-1", str(f))
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("Working through options", entries[0]["message"])
        self.assertEqual(entries[0].get("kind"), "agent-thinking")

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

    def test_fallback_binds_workspace_rollout_without_lsof_path(self) -> None:
        rollout = self._codex_rollout_file("rollout-a.jsonl")
        rollout.write_text(self._session_meta_line(str(self.workspace)) + self._line("history"))
        self.runtime._sync_codex_assistant_messages("codex-1")
        self.assertIn("codex-1", self.runtime._codex_cursors)
        self.assertEqual(self.runtime._codex_cursors["codex-1"].path, str(rollout))
        self.assertEqual(self._index_entries(), [])

    def test_fallback_ignores_other_workspace_rollout(self) -> None:
        rollout = self._codex_rollout_file("rollout-other.jsonl")
        rollout.write_text(self._session_meta_line("/tmp/other-workspace") + self._line("history"))
        self.runtime._sync_codex_assistant_messages("codex-1")
        self.assertNotIn("codex-1", self.runtime._codex_cursors)
        self.assertEqual(self._index_entries(), [])

    def test_fallback_does_not_match_git_root_alias(self) -> None:
        repo_root = self.root / "repo-root"
        child_workspace = repo_root / "child"
        child_workspace.mkdir(parents=True, exist_ok=True)
        self.runtime.workspace = str(child_workspace)
        self.runtime._workspace_git_root_cache[str(child_workspace)] = str(repo_root)

        rollout = self._codex_rollout_file("rollout-root.jsonl")
        rollout.write_text(self._session_meta_line(str(repo_root)) + self._line("history"))
        self.runtime._sync_codex_assistant_messages("codex-1")
        self.assertNotIn("codex-1", self.runtime._codex_cursors)
        self.assertEqual(self._index_entries(), [])

    def test_fallback_bound_path_syncs_subsequent_append(self) -> None:
        rollout = self._codex_rollout_file("rollout-b.jsonl")
        rollout.write_text(self._session_meta_line(str(self.workspace)))
        self.runtime._sync_codex_assistant_messages("codex-1")
        with rollout.open("a") as h:
            h.write(self._line("live-codex"))
        self.runtime._sync_codex_assistant_messages("codex-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("live-codex", entries[0]["message"])

    def test_first_bind_backfills_recent_error_event(self) -> None:
        now_iso = dt_datetime.now(dt_UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        f = self.root / "rollout-recent.jsonl"
        f.write_text(
            json.dumps(
                {
                    "type": "event_msg",
                    "timestamp": now_iso,
                    "payload": {
                        "type": "error",
                        "message": "recent usage-limit warning",
                    },
                }
            )
            + "\n"
        )
        self.runtime._sync_codex_assistant_messages("codex-1", str(f))
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("recent usage-limit warning", entries[0]["message"])


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

    def _add_session(self, db: Path, sid: str, t: int, *, directory: str | None = None) -> None:
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO session VALUES (?, ?, ?)",
            (sid, str(directory or self.workspace), t),
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

    def test_first_bind_backfills_recent_message_near_first_seen(self) -> None:
        db = self._make_db()
        self._add_session(db, "ses_a", 100)
        now_ms = int(time.time() * 1000)
        self.runtime._agent_first_seen_ts["opencode-1"] = now_ms / 1000.0
        self._add_msg(db, "msg_recent", "ses_a", now_ms - 1000, "near-bind-reply")
        self.runtime._sync_opencode_assistant_messages("opencode-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("near-bind-reply", entries[0]["message"])

    def test_workspace_alias_directory_is_matched(self) -> None:
        db = self._make_db()
        self.runtime.workspace = "/tmp/opencode-alias-test"
        self._add_session(
            db,
            "ses_alias",
            100,
            directory="/private/tmp/opencode-alias-test",
        )
        now_ms = int(time.time() * 1000)
        self.runtime._agent_first_seen_ts["opencode-1"] = (now_ms - 2000) / 1000.0
        self._add_msg(db, "msg_alias", "ses_alias", now_ms - 1000, "alias-match")
        self.runtime._sync_opencode_assistant_messages("opencode-1")
        entries = self._index_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("alias-match", entries[0]["message"])


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


class GlobalClaimFilteringTests(_SyncTestBase):
    def _write_sync_state(self, session_name: str, payload: dict) -> Path:
        session_dir = self.repo_root / "logs" / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / ".agent-index-sync-state.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_collect_global_claims_skips_sessions_missing_in_tmux(self) -> None:
        alive_path = "/tmp/alive-claude.jsonl"
        ghost_path = "/tmp/ghost-claude.jsonl"
        self._write_sync_state("alive", {"claude_cursors": {"claude": [alive_path, 10]}})
        self._write_sync_state("ghost", {"claude_cursors": {"claude": [ghost_path, 20]}})
        self.runtime._global_log_claims_fetched_at = 0.0

        tmux_ok = subprocess.CompletedProcess(
            args=["tmux"],
            returncode=0,
            stdout="demo\nalive\n",
            stderr="",
        )
        with patch("agent_index.chat_core.subprocess.run", return_value=tmux_ok):
            claims = self.runtime._collect_global_native_log_claims()

        self.assertIn(alive_path, claims)
        self.assertNotIn(ghost_path, claims)

    def test_collect_global_claims_falls_back_when_tmux_query_fails(self) -> None:
        ghost_path = "/tmp/ghost-claude.jsonl"
        self._write_sync_state("ghost", {"claude_cursors": {"claude": [ghost_path, 20]}})
        self.runtime._global_log_claims_fetched_at = 0.0

        tmux_fail = subprocess.CompletedProcess(
            args=["tmux"],
            returncode=1,
            stdout="",
            stderr="tmux unavailable",
        )
        with patch("agent_index.chat_core.subprocess.run", return_value=tmux_fail):
            claims = self.runtime._collect_global_native_log_claims()

        self.assertIn(ghost_path, claims)

    def test_collect_global_claims_skips_expired_state_files(self) -> None:
        import os

        stale_path = "/tmp/stale-claude.jsonl"
        state_path = self._write_sync_state(
            "alive",
            {"claude_cursors": {"claude": [stale_path, 20]}},
        )
        old = time.time() - 360
        os.utime(state_path, (old, old))
        self.runtime._global_log_claims_fetched_at = 0.0

        tmux_ok = subprocess.CompletedProcess(
            args=["tmux"],
            returncode=0,
            stdout="demo\nalive\n",
            stderr="",
        )
        with patch("agent_index.chat_core.subprocess.run", return_value=tmux_ok):
            claims = self.runtime._collect_global_native_log_claims()

        self.assertNotIn(stale_path, claims)

    def test_collect_global_claims_tmux_failure_still_skips_expired_state_files(self) -> None:
        import os

        stale_path = "/tmp/ghost-stale-claude.jsonl"
        state_path = self._write_sync_state(
            "ghost",
            {"claude_cursors": {"claude": [stale_path, 20]}},
        )
        old = time.time() - 360
        os.utime(state_path, (old, old))
        self.runtime._global_log_claims_fetched_at = 0.0

        tmux_fail = subprocess.CompletedProcess(
            args=["tmux"],
            returncode=1,
            stdout="",
            stderr="tmux unavailable",
        )
        with patch("agent_index.chat_core.subprocess.run", return_value=tmux_fail):
            claims = self.runtime._collect_global_native_log_claims()

        self.assertNotIn(stale_path, claims)

    def test_global_claim_lookup_handles_path_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "shared.jsonl"
            alias = root / "shared-link.jsonl"
            shared.write_text("x", encoding="utf-8")
            alias.symlink_to(shared)
            self.runtime._global_log_claims = {str(shared): ("other", "claude-1")}
            self.runtime._global_log_claims_fetched_at = time.time()
            self.assertTrue(self.runtime._is_globally_claimed_path(str(alias)))
            self.assertEqual(
                _native_path_claim_key(str(shared)),
                _native_path_claim_key(str(alias)),
            )


class SyncClaimPruneTests(_SyncTestBase):
    def test_prune_sync_claims_keeps_only_active_agents(self) -> None:
        self.runtime._claude_cursors = {
            "claude": NativeLogCursor("/tmp/claude.jsonl", 10),
            "claude-1": NativeLogCursor("/tmp/claude-1.jsonl", 20),
        }
        self.runtime._cursor_cursors = {
            "cursor": NativeLogCursor("/tmp/cursor.jsonl", 10),
            "cursor-2": NativeLogCursor("/tmp/cursor-2.jsonl", 20),
        }
        self.runtime._opencode_cursors = {
            "opencode-1": OpenCodeCursor("ses_1", "msg_1"),
            "opencode-2": OpenCodeCursor("ses_2", "msg_2"),
        }
        self.runtime._agent_first_seen_ts = {
            "claude": 1.0,
            "claude-1": 2.0,
            "cursor": 3.0,
            "cursor-2": 4.0,
            "opencode-1": 5.0,
            "opencode-2": 6.0,
        }

        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime.prune_sync_claims_to_active_agents(
                ["claude-1", "cursor", "opencode-1"]
            )

        self.assertTrue(changed)
        self.assertEqual(set(self.runtime._claude_cursors.keys()), {"claude-1"})
        self.assertEqual(set(self.runtime._cursor_cursors.keys()), {"cursor"})
        self.assertEqual(set(self.runtime._opencode_cursors.keys()), {"opencode-1"})
        self.assertEqual(
            set(self.runtime._agent_first_seen_ts.keys()),
            {"claude-1", "cursor", "opencode-1"},
        )
        save_mock.assert_called_once()

    def test_prune_sync_claims_is_noop_when_active_agents_missing(self) -> None:
        self.runtime._claude_cursors = {
            "claude-1": NativeLogCursor("/tmp/claude-1.jsonl", 20),
        }
        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime.prune_sync_claims_to_active_agents([])
        self.assertFalse(changed)
        self.assertIn("claude-1", self.runtime._claude_cursors)
        save_mock.assert_not_called()

    def test_prune_migrates_base_claim_to_primary_numbered_instance(self) -> None:
        self.runtime._claude_cursors = {
            "claude": NativeLogCursor("/tmp/claude.jsonl", 10),
        }
        self.runtime._agent_first_seen_ts = {"claude": 1.0}

        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime.prune_sync_claims_to_active_agents(
                ["claude-1", "claude-2"]
            )

        self.assertTrue(changed)
        self.assertIn("claude-1", self.runtime._claude_cursors)
        self.assertNotIn("claude", self.runtime._claude_cursors)
        self.assertEqual(self.runtime._claude_cursors["claude-1"].path, "/tmp/claude.jsonl")
        self.assertIn("claude-1", self.runtime._agent_first_seen_ts)
        self.assertNotIn("claude", self.runtime._agent_first_seen_ts)
        save_mock.assert_called_once()

    def test_prune_migrates_numbered_claim_back_to_base(self) -> None:
        self.runtime._qwen_cursors = {
            "qwen-2": NativeLogCursor("/tmp/qwen-2.jsonl", 20),
        }
        self.runtime._agent_first_seen_ts = {"qwen-2": 2.0}

        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime.prune_sync_claims_to_active_agents(["qwen"])

        self.assertTrue(changed)
        self.assertIn("qwen", self.runtime._qwen_cursors)
        self.assertNotIn("qwen-2", self.runtime._qwen_cursors)
        self.assertEqual(self.runtime._qwen_cursors["qwen"].path, "/tmp/qwen-2.jsonl")
        self.assertIn("qwen", self.runtime._agent_first_seen_ts)
        self.assertNotIn("qwen-2", self.runtime._agent_first_seen_ts)
        save_mock.assert_called_once()


class SharedClaimHandoffTests(_SyncTestBase):
    def test_handoff_moves_single_same_base_claim_to_target(self) -> None:
        self.runtime._qwen_cursors = {
            "qwen-1": NativeLogCursor("/tmp/shared-qwen.jsonl", 42),
        }
        self.runtime._agent_first_seen_ts = {"qwen-1": 100.0}
        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime._handoff_shared_sync_claim("qwen-2")
        self.assertTrue(changed)
        self.assertNotIn("qwen-1", self.runtime._qwen_cursors)
        self.assertIn("qwen-2", self.runtime._qwen_cursors)
        self.assertEqual(self.runtime._qwen_cursors["qwen-2"].path, "/tmp/shared-qwen.jsonl")
        self.assertEqual(self.runtime._agent_first_seen_ts.get("qwen-2"), 100.0)
        save_mock.assert_called_once()

    def test_handoff_is_noop_when_target_already_has_claim(self) -> None:
        self.runtime._qwen_cursors = {
            "qwen-1": NativeLogCursor("/tmp/one.jsonl", 10),
            "qwen-2": NativeLogCursor("/tmp/two.jsonl", 20),
        }
        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime._handoff_shared_sync_claim("qwen-2")
        self.assertFalse(changed)
        self.assertIn("qwen-1", self.runtime._qwen_cursors)
        self.assertIn("qwen-2", self.runtime._qwen_cursors)
        save_mock.assert_not_called()

    def test_handoff_is_noop_when_no_single_donor_exists(self) -> None:
        self.runtime._qwen_cursors = {
            "qwen-1": NativeLogCursor("/tmp/one.jsonl", 10),
            "qwen-3": NativeLogCursor("/tmp/three.jsonl", 30),
        }
        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime._handoff_shared_sync_claim("qwen-2")
        self.assertFalse(changed)
        self.assertIn("qwen-1", self.runtime._qwen_cursors)
        self.assertIn("qwen-3", self.runtime._qwen_cursors)
        save_mock.assert_not_called()

    def test_handoff_moves_single_opencode_claim_to_target(self) -> None:
        self.runtime._opencode_cursors = {
            "opencode-1": OpenCodeCursor("ses-1", "msg-1"),
        }
        self.runtime._agent_first_seen_ts = {"opencode-1": 200.0}
        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime._handoff_shared_sync_claim("opencode-2")
        self.assertTrue(changed)
        self.assertNotIn("opencode-1", self.runtime._opencode_cursors)
        self.assertIn("opencode-2", self.runtime._opencode_cursors)
        self.assertEqual(self.runtime._opencode_cursors["opencode-2"].session_id, "ses-1")
        self.assertEqual(self.runtime._agent_first_seen_ts.get("opencode-2"), 200.0)
        save_mock.assert_called_once()

    def test_recent_targeted_handoff_uses_latest_single_target(self) -> None:
        self.runtime._qwen_cursors = {
            "qwen-1": NativeLogCursor("/tmp/shared-qwen.jsonl", 42),
        }
        now_ts = dt_datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        append_jsonl_entry(
            self.index_path,
            {
                "timestamp": now_ts,
                "session": "demo",
                "sender": "copilot-1",
                "targets": ["qwen-2"],
                "message": "[From: copilot-1]\\nping",
                "msg_id": "handoff-now",
            },
        )
        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime.apply_recent_targeted_claim_handoffs(["qwen-1", "qwen-2"])
        self.assertTrue(changed)
        self.assertIn("qwen-2", self.runtime._qwen_cursors)
        self.assertNotIn("qwen-1", self.runtime._qwen_cursors)
        save_mock.assert_called_once()

    def test_recent_targeted_handoff_ignores_stale_entries(self) -> None:
        self.runtime._qwen_cursors = {
            "qwen-1": NativeLogCursor("/tmp/shared-qwen.jsonl", 42),
        }
        stale_ts = dt_datetime.fromtimestamp(time.time() - 120).strftime("%Y-%m-%d %H:%M:%S")
        append_jsonl_entry(
            self.index_path,
            {
                "timestamp": stale_ts,
                "session": "demo",
                "sender": "copilot-1",
                "targets": ["qwen-2"],
                "message": "[From: copilot-1]\\nping",
                "msg_id": "handoff-stale",
            },
        )
        with patch.object(self.runtime, "save_sync_state") as save_mock:
            changed = self.runtime.apply_recent_targeted_claim_handoffs(
                ["qwen-1", "qwen-2"],
                lookback_seconds=45.0,
            )
        self.assertFalse(changed)
        self.assertIn("qwen-1", self.runtime._qwen_cursors)
        self.assertNotIn("qwen-2", self.runtime._qwen_cursors)
        save_mock.assert_not_called()


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
        self.assertIn("Bashing git status", events[0]["text"])

    def test_copilot_tool_execution_start(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()
        p = self._write("copilot.jsonl", [
            {"type": "tool.execution_start", "data": {
                "toolName": "view",
                "arguments": {"path": str(workspace / "tmp" / "file.py")},
            }},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=5, workspace=str(workspace))
        self.assertIsNotNone(events)
        self.assertEqual(len(events), 1)
        self.assertIn("Viewing tmp/file.py", events[0]["text"])

    def test_copilot_apply_patch_split_into_edit_events(self) -> None:
        patch = (
            "*** Begin Patch\n"
            "*** Update File: src/a.py\n"
            "@@\n"
            "-old\n"
            "+new\n"
            "*** Add File: src/b.py\n"
            "+x = 1\n"
            "*** End Patch\n"
        )
        p = self._write("copilot-apply-patch.jsonl", [
            {"type": "tool.execution_start", "data": {
                "toolName": "apply_patch",
                "arguments": {"patch": patch},
            }},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=8)
        self.assertIsNotNone(events)
        self.assertGreaterEqual(len(events), 2)
        texts = [str(item.get("text") or "") for item in events]
        self.assertTrue(any(text.startswith("Editing src/a.py") for text in texts))
        self.assertTrue(any(text.startswith("Creating src/b.py") for text in texts))

    def test_copilot_apply_patch_from_tool_request_json_string(self) -> None:
        patch = (
            "*** Begin Patch\n"
            "*** Delete File: docs/old.md\n"
            "*** End Patch\n"
        )
        p = self._write("copilot-apply-patch-req.jsonl", [
            {"type": "assistant.message", "data": {
                "toolRequests": [
                    {"name": "apply_patch", "arguments": json.dumps({"patch": patch})},
                ],
            }},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=8)
        self.assertIsNotNone(events)
        self.assertGreaterEqual(len(events), 1)
        self.assertTrue(any(str(item.get("text") or "").startswith("Deleting docs/old.md") for item in events))

    def test_cursor_role_assistant_tool_use(self) -> None:
        p = self._write("cursor.jsonl", [
            {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Grep", "input": {"pattern": "TODO"}},
            ]}},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=5)
        self.assertIsNotNone(events)
        self.assertEqual(len(events), 1)
        self.assertIn("Searching TODO", events[0]["text"])

    def test_apply_patch_relativizes_absolute_workspace_paths(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()
        patch = (
            "*** Begin Patch\n"
            f"*** Update File: {workspace / 'src' / 'main.py'}\n"
            "@@\n"
            "-old\n"
            "+new\n"
            "*** End Patch\n"
        )
        p = self._write("copilot-apply-patch-absolute.jsonl", [
            {"type": "tool.execution_start", "data": {
                "toolName": "apply_patch",
                "arguments": {"patch": patch},
            }},
        ])
        events = _parse_cursor_jsonl_runtime(str(p), limit=8, workspace=str(workspace))
        self.assertIsNotNone(events)
        texts = [str(item.get("text") or "") for item in events]
        self.assertTrue(any(text.startswith("Editing src/main.py") for text in texts))

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

    def test_codex_native_runtime_extracts_reasoning_and_tool_calls(self) -> None:
        patch = (
            "*** Begin Patch\n"
            "*** Update File: src/app.py\n"
            "@@\n"
            "-old\n"
            "+new\n"
            "*** End Patch\n"
        )
        p = self._write("codex-runtime.jsonl", [
            {"type": "event_msg", "payload": {"type": "agent_reasoning", "text": "**Planning next steps**"}},
            {"type": "response_item", "payload": {
                "type": "function_call",
                "name": "exec_command",
                "arguments": json.dumps({"cmd": "rg --files src"}),
            }},
            {"type": "response_item", "payload": {
                "type": "function_call",
                "name": "exec_command",
                "arguments": json.dumps({"cmd": "rg TODO lib/agent_index"}),
            }},
            {"type": "response_item", "payload": {
                "type": "function_call",
                "name": "exec_command",
                "arguments": json.dumps({"cmd": "sed -n '1,40p' lib/agent_index/chat_runtime_parse_core.py"}),
            }},
            {"type": "response_item", "payload": {
                "type": "function_call",
                "name": "write_stdin",
                "arguments": json.dumps({"chars": ""}),
            }},
            {"type": "response_item", "payload": {
                "type": "custom_tool_call",
                "name": "apply_patch",
                "input": patch,
            }},
        ])
        events = _parse_native_codex_log(str(p), limit=8)
        self.assertIsNotNone(events)
        texts = [str(item.get("text") or "") for item in events]
        self.assertTrue(any(text.startswith("✦ **Planning next steps**") for text in texts))
        self.assertTrue(any(text.startswith("Exploring src") for text in texts))
        self.assertTrue(any(text.startswith("Searching TODO in lib/agent_index") for text in texts))
        self.assertTrue(any(text.startswith("Reading lib/agent_index/chat_runtime_parse_core.py") for text in texts))
        self.assertFalse(any("write_stdin" in text for text in texts))
        self.assertTrue(any(text.startswith("Editing src/app.py") for text in texts))


class CodexStatusRuntimeTests(_SyncTestBase):
    @staticmethod
    def _tmux_result(stdout: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=["tmux"], returncode=0, stdout=stdout, stderr="")

    def test_agent_statuses_uses_codex_native_runtime_parser(self) -> None:
        rollout = self.root / "codex-status.jsonl"
        rollout.write_text(
            json.dumps({"type": "response_item", "payload": {
                "type": "function_call",
                "name": "exec_command",
                "arguments": json.dumps({"cmd": "rg --files src"}),
            }}) + "\n",
            encoding="utf-8",
        )
        self.runtime._codex_cursors["codex-1"] = NativeLogCursor(path=str(rollout), offset=0)
        self.runtime._pane_last_change["%41"] = time.monotonic()
        with patch.object(self.runtime, "active_agents", return_value=["codex-1"]):
            with patch("agent_index.chat_status_core.subprocess.run") as run_mock:
                run_mock.side_effect = [
                    self._tmux_result("MULTIAGENT_PANE_CODEX_1=%41\n"),
                    self._tmux_result("0\n"),
                    self._tmux_result("captured pane\n"),
                ]
                statuses = self.runtime.agent_statuses()
        self.assertEqual(statuses.get("codex-1"), "running")
        runtime_state = self.runtime.agent_runtime_state()
        self.assertIn("codex-1", runtime_state)
        self.assertIn("Exploring src", runtime_state["codex-1"]["current_event"]["text"])


if __name__ == "__main__":
    unittest.main()
