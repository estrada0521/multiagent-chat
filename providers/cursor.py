from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

from multiagent_chat.chat.sync.cursor import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _pick_latest_unclaimed_for_agent,
)
from multiagent_chat.jsonl_append import append_jsonl_entry
from multiagent_chat.redacted_placeholder import normalize_cursor_plaintext_for_index


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
