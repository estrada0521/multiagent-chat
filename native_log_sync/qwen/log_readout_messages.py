from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path

from multiagent_chat.chat.sync.cursor import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
)
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.core.jsonl_tail_runtime import parse_jsonl_tail_for_runtime
from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path

def sync_qwen_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    first_seen_grace_seconds: float,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    prev_cursor = self._qwen_cursors.get(agent)
    try:
        from native_log_sync.qwen.log_location import resolve_qwen_chat_jsonl_path

        chat_path_str = resolve_qwen_chat_jsonl_path(
            self,
            agent,
            native_log_path,
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
        )
        if not chat_path_str:
            return
        file_size = os.path.getsize(chat_path_str)
        offset = _advance_native_cursor(self._qwen_cursors, agent, chat_path_str, file_size)

        def _append_qwen_entry(entry: dict, *, min_event_ts: float | None = None) -> bool:
            if str(entry.get("type") or "").strip() != "assistant":
                return False
            if min_event_ts is not None:
                event_ts = _parse_iso_timestamp_epoch(str(entry.get("timestamp") or ""))
                if event_ts is None or event_ts < min_event_ts:
                    return False
            msg_obj = entry.get("message") if isinstance(entry, dict) else {}
            if not isinstance(msg_obj, dict):
                return False
            parts = msg_obj.get("parts") or []
            texts = []
            thought_texts = []
            for part in parts:
                if not isinstance(part, dict) or "text" not in part:
                    continue
                text = str(part.get("text") or "").strip()
                if not text:
                    return False
                if part.get("thought"):
                    continue
                texts.append(text)
            if not texts and not thought_texts:
                return False
            if thought_texts and not texts:
                return False
            content = "\n".join(texts) if texts else "\n".join(thought_texts)
            msg_id = str(entry.get("uuid") or "").strip()
            if msg_id and msg_id in self._synced_msg_ids:
                return False
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
            return True

        def _scan_recent_qwen_entries(min_event_ts: float) -> bool:
            appended = False
            with open(chat_path_str, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if _append_qwen_entry(entry, min_event_ts=min_event_ts):
                        appended = True
            return appended

        if offset is None:
            appended_on_bind = False
            binding_changed = _cursor_binding_changed(prev_cursor, self._qwen_cursors.get(agent))
            if binding_changed:
                min_event_ts = time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS
                appended_on_bind = _scan_recent_qwen_entries(min_event_ts)
            if appended_on_bind or binding_changed:
                self.save_sync_state()
            return

        with open(chat_path_str, "r", encoding="utf-8") as f:
            f.seek(offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                _append_qwen_entry(entry)

        self._qwen_cursors[agent] = NativeLogCursor(path=chat_path_str, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        if prev_cursor is None:
            self._qwen_cursors.pop(agent, None)
        else:
            self._qwen_cursors[agent] = prev_cursor
        logging.error(f"Failed to sync Qwen message for {agent}: {exc}", exc_info=True)


