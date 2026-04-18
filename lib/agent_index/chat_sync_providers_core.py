from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

from .chat_sync_cursor_core import (
    NativeLogCursor,
    OpenCodeCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
    _workspace_slug_variants,
    _pick_latest_unclaimed_for_agent,
)
from .chat_sync_providers_qwen_gemini_core import (
    sync_gemini_assistant_messages as _sync_gemini_assistant_messages_impl,
    sync_qwen_assistant_messages as _sync_qwen_assistant_messages_impl,
)
from .jsonl_append import append_jsonl_entry
from .redacted_placeholder import normalize_cursor_plaintext_for_index


def sync_codex_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    try:
        resolved_path = str(Path(native_log_path)) if native_log_path else ""
        if not resolved_path:
            cursor = self._codex_cursors.get(agent)
            if cursor and cursor.path and os.path.exists(cursor.path):
                resolved_path = cursor.path
            else:
                picked = self._pick_codex_rollout_for_agent(agent)
                if picked is None:
                    return
                resolved_path = str(picked)
        if self._is_globally_claimed_path(resolved_path):
            return
        if not os.path.exists(resolved_path):
            return

        def _append_codex_entry(entry: dict, *, min_event_ts: float | None = None) -> bool:
            if min_event_ts is not None:
                event_ts = _parse_iso_timestamp_epoch(str(entry.get("timestamp") or ""))
                if event_ts is None or event_ts < min_event_ts:
                    return False

            display = ""
            kind = ""
            entry_type = entry.get("type", "")
            if entry_type == "response_item":
                payload = entry.get("payload", {})
                payload_type = str(payload.get("type") or "").strip().lower()
                if payload_type == "reasoning":
                    summary = payload.get("summary") or []
                    reasoning_lines = []
                    if isinstance(summary, list):
                        for item in summary:
                            if not isinstance(item, dict):
                                continue
                            text = str(item.get("text") or "").strip()
                            if text:
                                reasoning_lines.append(text)
                    if not reasoning_lines:
                        return False
                    display = "\n".join(reasoning_lines)
                    kind = "agent-thinking"
                else:
                    if payload.get("role") != "assistant":
                        return False
                    content = payload.get("content", [])
                    texts = []
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict):
                                t = c.get("text") or c.get("output_text", {}).get("text", "")
                                if t and str(t).strip():
                                    texts.append(str(t).strip())
                    if not texts:
                        return False
                    display = "\n".join(texts)
            elif entry_type == "event_msg":
                payload = entry.get("payload", {})
                payload_type = str(payload.get("type") or "").strip().lower()
                if payload_type == "error":
                    display = str(payload.get("message") or "").strip()
                elif payload_type == "agent_reasoning":
                    display = str(payload.get("text") or payload.get("message") or "").strip()
                    kind = "agent-thinking"
                else:
                    return False
                if not display:
                    return False
            else:
                return False

            src_ts = str(entry.get("timestamp") or "")
            key = f"codex:{agent}:{src_ts}:{display}"
            msg_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
            if msg_id in self._synced_msg_ids:
                return False

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            jsonl_entry = {
                "timestamp": timestamp,
                "session": self.session_name,
                "sender": agent,
                "targets": ["user"],
                "message": f"[From: {agent}]\n{display}",
                "msg_id": msg_id,
            }
            if kind:
                jsonl_entry["kind"] = kind
            append_jsonl_entry(self.index_path, jsonl_entry)
            self._synced_msg_ids.add(msg_id)
            return True

        def _scan_recent_codex_entries(min_event_ts: float) -> bool:
            appended = False
            try:
                with open(resolved_path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if _append_codex_entry(entry, min_event_ts=min_event_ts):
                            appended = True
            except Exception:
                return False
            return appended

        file_size = os.path.getsize(resolved_path)
        prev_cursor = self._codex_cursors.get(agent)
        offset = _advance_native_cursor(self._codex_cursors, agent, resolved_path, file_size)
        if offset is None:
            appended_on_bind = False
            if _cursor_binding_changed(prev_cursor, self._codex_cursors.get(agent)):
                min_event_ts = time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS
                appended_on_bind = _scan_recent_codex_entries(min_event_ts)
            if appended_on_bind or _cursor_binding_changed(prev_cursor, self._codex_cursors.get(agent)):
                self.save_sync_state()
            return

        with open(resolved_path, "r", encoding="utf-8") as f:
            f.seek(offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                _append_codex_entry(entry)

        self._codex_cursors[agent] = NativeLogCursor(path=resolved_path, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error(f"Failed to sync Codex message for {agent}: {exc}")


def sync_cursor_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    first_seen_grace_seconds: float,
) -> None:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    try:
        workspace = self.workspace or ""
        if not workspace:
            return
        transcript_path = str(Path(native_log_path)) if native_log_path else ""
        if not transcript_path:
            cursor = self._cursor_cursors.get(agent)
            if (
                cursor
                and cursor.path
                and os.path.exists(cursor.path)
                and self._should_stick_to_existing_cursor(agent)
            ):
                transcript_path = cursor.path
            else:
                candidates: list[Path] = []
                for root in self._cursor_transcript_roots(workspace):
                    candidates.extend(root.glob("*/*.jsonl"))
                candidates.extend(self._cursor_storedb_candidates(workspace))
                if not candidates:
                    return
                min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                picked = _pick_latest_unclaimed_for_agent(
                    candidates,
                    self._cursor_cursors,
                    agent,
                    min_mtime=min_mtime,
                    exclude_paths=set(self._collect_global_native_log_claims().keys()),
                )
                if picked is None:
                    return
                transcript_path = str(picked)
        elif self._is_globally_claimed_path(transcript_path):
            return
        if not os.path.exists(transcript_path):
            return
        if Path(transcript_path).name == "store.db":
            self._sync_cursor_storedb_assistant_messages(agent, transcript_path)
            return
        file_size = os.path.getsize(transcript_path)
        prev_cursor = self._cursor_cursors.get(agent)
        offset = _advance_native_cursor(self._cursor_cursors, agent, transcript_path, file_size)
        if offset is None:
            if _cursor_binding_changed(prev_cursor, self._cursor_cursors.get(agent)):
                self.save_sync_state()
            return

        with open(transcript_path, "r", encoding="utf-8") as f:
            f.seek(offset)
            while True:
                line_start = f.tell()
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                display = ""
                role = entry.get("role", "")
                if role == "assistant":
                    msg_obj = entry.get("message") if isinstance(entry, dict) else {}
                    if not isinstance(msg_obj, dict):
                        continue
                    content = msg_obj.get("content", [])
                    if isinstance(content, str) and content.strip():
                        display = content.strip()
                    elif isinstance(content, list):
                        texts = []
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                text = str(c.get("text") or "").strip()
                                if text:
                                    texts.append(text)
                        if not texts:
                            continue
                        display = "\n".join(texts)
                elif role == "system":
                    msg_obj = entry.get("message") if isinstance(entry, dict) else {}
                    if isinstance(msg_obj, dict):
                        content = msg_obj.get("content", "")
                        if isinstance(content, str) and content.strip():
                            display = content.strip()
                    elif isinstance(msg_obj, str) and msg_obj.strip():
                        display = msg_obj.strip()

                if not display:
                    continue

                display = normalize_cursor_plaintext_for_index(display)
                if not display:
                    continue

                key = f"cursor:{agent}:{transcript_path}:{line_start}:{display}"
                msg_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
                if msg_id in self._synced_msg_ids:
                    continue
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                jsonl_entry = {
                    "timestamp": timestamp,
                    "session": self.session_name,
                    "sender": agent,
                    "targets": ["user"],
                    "message": f"[From: {agent}]\n{display}",
                    "msg_id": msg_id,
                }
                append_jsonl_entry(self.index_path, jsonl_entry)
                self._synced_msg_ids.add(msg_id)

        self._cursor_cursors[agent] = NativeLogCursor(path=transcript_path, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error(f"Failed to sync Cursor message for {agent}: {exc}")


def sync_cursor_storedb_assistant_messages(self, agent: str, store_db_path: str) -> None:
    store_db = Path(store_db_path)
    wal_path = store_db.with_name(store_db.name + "-wal")
    file_size = store_db.stat().st_size
    if wal_path.exists():
        file_size += wal_path.stat().st_size

    def _extract_display(payload: dict) -> str:
        role = str(payload.get("role") or "").strip()
        if role == "assistant":
            content = payload.get("content", [])
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                texts: list[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    item_type = str(item.get("type") or "").strip()
                    if item_type not in {"text", "output_text"}:
                        continue
                    text = str(item.get("text") or item.get("value") or "").strip()
                    if text:
                        texts.append(text)
                if texts:
                    return "\n".join(texts)
            return ""
        if role == "system":
            content = payload.get("content", "")
            if isinstance(content, str):
                return content.strip()
        return ""

    def _message_id(row_id: str, payload: dict, display: str) -> str:
        msg_id = str(payload.get("id") or row_id or "").strip()[:12]
        if msg_id:
            return msg_id
        key = f"cursor:{agent}:{store_db}:{row_id}:{display}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]

    def _load_rows() -> list[tuple[str, bytes | bytearray | memoryview]]:
        conn = sqlite3.connect(str(store_db), timeout=1.0)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, data FROM blobs")
            return cur.fetchall()
        finally:
            conn.close()

    prev_cursor = self._cursor_cursors.get(agent)
    offset = _advance_native_cursor(self._cursor_cursors, agent, str(store_db), file_size)
    binding_changed = _cursor_binding_changed(prev_cursor, self._cursor_cursors.get(agent))
    if offset is None and binding_changed:
        try:
            for row_id, blob_data in _load_rows():
                if not blob_data:
                    continue
                if isinstance(blob_data, memoryview):
                    blob_bytes = blob_data.tobytes()
                elif isinstance(blob_data, (bytes, bytearray)):
                    blob_bytes = bytes(blob_data)
                else:
                    continue
                try:
                    payload = json.loads(blob_bytes.decode("utf-8"))
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                display = normalize_cursor_plaintext_for_index(_extract_display(payload))
                if not display:
                    continue
                self._synced_msg_ids.add(_message_id(str(row_id), payload, display))
        except Exception as exc:
            logging.error(f"Failed to seed Cursor store.db baseline for {agent}: {exc}")
        self.save_sync_state()
        return

    try:
        rows = _load_rows()
    except Exception as exc:
        logging.error(f"Failed to read Cursor store.db for {agent}: {exc}")
        return

    for row_id, blob_data in rows:
        if not blob_data:
            continue
        if isinstance(blob_data, memoryview):
            blob_bytes = blob_data.tobytes()
        elif isinstance(blob_data, (bytes, bytearray)):
            blob_bytes = bytes(blob_data)
        else:
            continue
        try:
            payload = json.loads(blob_bytes.decode("utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        display = _extract_display(payload)
        if not display:
            continue
        display = normalize_cursor_plaintext_for_index(display)
        if not display:
            continue
        msg_id = _message_id(str(row_id), payload, display)
        if msg_id in self._synced_msg_ids:
            continue
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        jsonl_entry = {
            "timestamp": timestamp,
            "session": self.session_name,
            "sender": agent,
            "targets": ["user"],
            "message": f"[From: {agent}]\n{display}",
            "msg_id": msg_id,
        }
        append_jsonl_entry(self.index_path, jsonl_entry)
        self._synced_msg_ids.add(msg_id)

    self._cursor_cursors[agent] = NativeLogCursor(path=str(store_db), offset=file_size)
    self.save_sync_state()


def sync_copilot_assistant_messages(self, agent: str, native_log_path: str) -> None:
    try:
        file_size = os.path.getsize(native_log_path)
        prev_cursor = self._copilot_cursors.get(agent)
        offset = _advance_native_cursor(self._copilot_cursors, agent, native_log_path, file_size)
        if offset is None:
            if _cursor_binding_changed(prev_cursor, self._copilot_cursors.get(agent)):
                self.save_sync_state()
            return

        with open(native_log_path, "r", encoding="utf-8") as f:
            f.seek(offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = str(entry.get("type") or "").strip()
                if etype != "assistant.message":
                    continue
                data = entry.get("data") if isinstance(entry, dict) else {}
                if not isinstance(data, dict):
                    data = {}
                content = str(data.get("content") or "").strip()
                if not content:
                    continue
                msg_id = str(data.get("messageId") or entry.get("id") or "").strip()
                if msg_id and msg_id in self._synced_msg_ids:
                    continue
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                jsonl_entry = {
                    "timestamp": timestamp,
                    "session": self.session_name,
                    "sender": agent,
                    "targets": ["user"],
                    "message": f"[From: {agent}]\n{content}",
                    "msg_id": msg_id or uuid.uuid4().hex[:12],
                }
                append_jsonl_entry(self.index_path, jsonl_entry)
                if msg_id:
                    self._synced_msg_ids.add(msg_id)

        self._copilot_cursors[agent] = NativeLogCursor(path=native_log_path, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error(f"Failed to sync Copilot message for {agent}: {exc}", exc_info=True)


def sync_claude_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    workspace_hint: str | None = None,
    first_seen_grace_seconds: float,
    sync_bind_backfill_window_seconds: float,
    claude_bind_backfill_window_seconds: float,
) -> None:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    _CLAUDE_BIND_BACKFILL_WINDOW_SECONDS = float(claude_bind_backfill_window_seconds)
    try:
        session_path_str = str(Path(native_log_path)) if native_log_path else ""
        if not session_path_str:
            cursor = self._claude_cursors.get(agent)
            if (
                cursor
                and cursor.path
                and os.path.exists(cursor.path)
                and self._should_stick_to_existing_cursor(agent)
            ):
                session_path_str = cursor.path
            else:
                jsonl_candidates: list[Path] = []
                seen_dirs: set[Path] = set()

                def _add_workspace_candidates(workspace: str | None) -> None:
                    ws = str(workspace or "").strip()
                    if not ws:
                        return
                    for slug in _workspace_slug_variants(ws):
                        workspace_dir = Path.home() / ".claude" / "projects" / f"-{slug}"
                        if workspace_dir in seen_dirs or not workspace_dir.exists():
                            continue
                        seen_dirs.add(workspace_dir)
                        jsonl_candidates.extend(workspace_dir.glob("*.jsonl"))

                hint_workspace = str(workspace_hint or "").strip()
                session_workspace = str(self.workspace or "").strip()
                prefer_session_then_hint = False
                if hint_workspace and session_workspace:
                    try:
                        hint_resolved = str(Path(hint_workspace).resolve())
                    except Exception:
                        hint_resolved = hint_workspace
                    try:
                        session_resolved = str(Path(session_workspace).resolve())
                    except Exception:
                        session_resolved = session_workspace
                    if session_resolved.startswith(hint_resolved.rstrip("/") + "/"):
                        prefer_session_then_hint = True
                if prefer_session_then_hint:
                    _add_workspace_candidates(session_workspace)
                else:
                    if hint_workspace and session_workspace:
                        if session_workspace == hint_workspace:
                            _add_workspace_candidates(session_workspace)
                        else:
                            _add_workspace_candidates(hint_workspace)
                            _add_workspace_candidates(session_workspace)
                    else:
                        _add_workspace_candidates(hint_workspace)
                        _add_workspace_candidates(session_workspace)

                cursor = self._claude_cursors.get(agent)
                if cursor and cursor.path:
                    cursor_dir = Path(cursor.path).parent
                    if cursor_dir not in seen_dirs and cursor_dir.exists():
                        seen_dirs.add(cursor_dir)
                        jsonl_candidates.extend(cursor_dir.glob("*.jsonl"))

                if not jsonl_candidates:
                    return
                min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                session_path = _pick_latest_unclaimed_for_agent(
                    jsonl_candidates,
                    self._claude_cursors,
                    agent,
                    min_mtime=min_mtime,
                    exclude_paths=set(self._collect_global_native_log_claims().keys()),
                )
                if session_path is None:
                    return
                session_path_str = str(session_path)
        elif self._is_globally_claimed_path(session_path_str):
            return
        if not os.path.exists(session_path_str):
            return
        file_size = os.path.getsize(session_path_str)
        prev_cursor = self._claude_cursors.get(agent)
        offset = _advance_native_cursor(self._claude_cursors, agent, session_path_str, file_size)

        def _append_claude_entry(entry: dict, *, min_event_ts: float | None = None) -> bool:
            if entry.get("type") != "assistant":
                return False
            if min_event_ts is not None:
                event_ts = _parse_iso_timestamp_epoch(
                    str(entry.get("timestamp") or entry.get("created_at") or "")
                )
                if event_ts is None or event_ts < min_event_ts:
                    return False
            msg = entry.get("message") if isinstance(entry, dict) else {}
            if not isinstance(msg, dict):
                return False
            content = msg.get("content", [])
            if not isinstance(content, list):
                return False
            texts = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    text = str(c.get("text") or "").strip()
                    if text:
                        texts.append(text)
            if not texts:
                return False
            display = "\n".join(texts)
            msg_id = str(entry.get("uuid") or entry.get("id") or "")[:12]
            if not msg_id:
                msg_id = uuid.uuid4().hex[:12]
            if msg_id in self._synced_msg_ids:
                return False
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            jsonl_entry = {
                "timestamp": timestamp,
                "session": self.session_name,
                "sender": agent,
                "targets": ["user"],
                "message": f"[From: {agent}]\n{display}",
                "msg_id": msg_id,
            }
            append_jsonl_entry(self.index_path, jsonl_entry)
            self._synced_msg_ids.add(msg_id)
            return True

        def _scan_recent_claude_entries(min_event_ts: float) -> bool:
            appended = False
            try:
                with open(session_path_str, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if _append_claude_entry(entry, min_event_ts=min_event_ts):
                            appended = True
            except Exception:
                return False
            return appended

        if offset is None:
            appended_on_bind = False
            if prev_cursor is None:
                first_seen = self._first_seen_for_agent(agent)
                self._claude_bind_backfill_until[agent] = max(
                    self._claude_bind_backfill_until.get(agent, 0.0),
                    first_seen + _CLAUDE_BIND_BACKFILL_WINDOW_SECONDS,
                )
                min_event_ts = first_seen - _FIRST_SEEN_GRACE_SECONDS
                appended_on_bind = _scan_recent_claude_entries(min_event_ts)
            else:
                backfill_deadline = self._claude_bind_backfill_until.get(agent, 0.0)
                if backfill_deadline:
                    if time.time() <= backfill_deadline:
                        min_event_ts = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                        appended_on_bind = _scan_recent_claude_entries(min_event_ts)
                    else:
                        self._claude_bind_backfill_until.pop(agent, None)
            if appended_on_bind or _cursor_binding_changed(prev_cursor, self._claude_cursors.get(agent)):
                self.save_sync_state()
            return

        backfill_deadline = self._claude_bind_backfill_until.get(agent, 0.0)
        if backfill_deadline:
            if time.time() <= backfill_deadline:
                min_event_ts = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                _scan_recent_claude_entries(min_event_ts)
            else:
                self._claude_bind_backfill_until.pop(agent, None)

        with open(session_path_str, "r", encoding="utf-8") as f:
            f.seek(offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                _append_claude_entry(entry)

        self._claude_cursors[agent] = NativeLogCursor(path=session_path_str, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error(f"Failed to sync Claude message for {agent}: {exc}", exc_info=True)


def sync_qwen_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    first_seen_grace_seconds: float,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _sync_qwen_assistant_messages_impl(
        self,
        agent,
        native_log_path=native_log_path,
        first_seen_grace_seconds=first_seen_grace_seconds,
        sync_bind_backfill_window_seconds=sync_bind_backfill_window_seconds,
    )


def sync_gemini_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    first_seen_grace_seconds: float,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _sync_gemini_assistant_messages_impl(
        self,
        agent,
        native_log_path=native_log_path,
        first_seen_grace_seconds=first_seen_grace_seconds,
        sync_bind_backfill_window_seconds=sync_bind_backfill_window_seconds,
    )


def sync_opencode_assistant_messages(
    self,
    agent: str,
    *,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    try:
        db_path = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
        if not db_path.exists():
            return

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        claimed_session_ids = {
            c.session_id
            for other_agent, c in self._opencode_cursors.items()
            if other_agent != agent and c.session_id
        }

        prev_cursor = self._opencode_cursors.get(agent)
        prev_session_id = prev_cursor.session_id if prev_cursor else ""
        last_msg_id = prev_cursor.last_msg_id if prev_cursor else ""

        workspace_aliases = self._workspace_aliases(self.workspace or "")
        if not workspace_aliases:
            workspace_aliases = [str(self.workspace or "")]
        placeholders = ",".join("?" for _ in workspace_aliases)
        cur.execute(
            f"""
                SELECT s.id FROM session s
                WHERE s.directory IN ({placeholders})
                ORDER BY s.time_updated DESC
                """,
            workspace_aliases,
        )
        session_id = ""
        for (candidate_id,) in cur.fetchall():
            if candidate_id == prev_session_id:
                session_id = candidate_id
                break
            if candidate_id not in claimed_session_ids:
                session_id = candidate_id
                break

        if not session_id:
            conn.close()
            return

        if last_msg_id and prev_session_id == session_id:
            where_clause = "AND m.time_created > (SELECT time_created FROM message WHERE id = ?)"
            anchor_value = last_msg_id
        else:
            first_seen_ms = int(self._first_seen_for_agent(agent) * 1000)
            backfill_floor_ms = int((time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS) * 1000)
            where_clause = "AND m.time_created >= ?"
            anchor_value = min(first_seen_ms, backfill_floor_ms)

        query = f"""
                SELECT m.id, m.time_created, m.data
                FROM message m
                WHERE m.session_id = ? {where_clause}
                ORDER BY m.time_created ASC
            """
        params: list = [session_id]
        if where_clause and anchor_value:
            params.append(anchor_value)

        cur.execute(query, params)
        new_last_msg_id = last_msg_id

        for msg_id, ts_ms, msg_data in cur.fetchall():
            obj = json.loads(msg_data)
            if obj.get("role") != "assistant":
                continue

            cur2 = conn.cursor()
            cur2.execute(
                "SELECT p.data FROM part p WHERE p.message_id = ? ORDER BY p.time_created ASC",
                (msg_id,),
            )

            texts = []
            error_parts = []
            for (pd,) in cur2.fetchall():
                pdata = json.loads(pd)
                pt = pdata.get("type", "")
                if pt == "text":
                    t = pdata.get("text", "").strip()
                    if t:
                        texts.append(t)
                elif pt == "tool-result" and pdata.get("isError"):
                    err_name = pdata.get("name", "?")
                    err_content = str(pdata.get("content", ""))[:200]
                    error_parts.append(f"{err_name}: {err_content}")

            if not texts and not error_parts:
                continue

            display = "\n".join(texts) if texts else ""
            if error_parts:
                error_text = "Errors: " + " | ".join(error_parts)
                display = f"{display}\n\n{error_text}".strip() if display else error_text

            if not display:
                continue

            sync_key = f"opencode:{agent}:{msg_id}:{display[:100]}"
            msg_id_hash = hashlib.sha256(sync_key.encode("utf-8")).hexdigest()[:12]
            if msg_id_hash in self._synced_msg_ids:
                new_last_msg_id = msg_id
                continue

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            jsonl_entry = {
                "timestamp": timestamp,
                "session": self.session_name,
                "sender": agent,
                "targets": ["user"],
                "message": f"[From: {agent}]\n{display}",
                "msg_id": msg_id_hash,
            }
            append_jsonl_entry(self.index_path, jsonl_entry)
            self._synced_msg_ids.add(msg_id_hash)
            new_last_msg_id = msg_id

        conn.close()

        if new_last_msg_id or prev_session_id != session_id:
            self._opencode_cursors[agent] = OpenCodeCursor(
                session_id=session_id,
                last_msg_id=new_last_msg_id or "",
            )
            self.save_sync_state()
    except Exception as exc:
        logging.error(f"Failed to sync OpenCode message for {agent}: {exc}", exc_info=True)
