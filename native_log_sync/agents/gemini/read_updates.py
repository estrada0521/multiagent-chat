from __future__ import annotations

import json
import logging
import os
import time

from native_log_sync.agents._shared.path_state import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
)
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.agents.gemini.resolve_path import resolve_gemini_native_log
from native_log_sync.agents.gemini.read_runtime import extract_gemini_message


def sync_gemini_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    first_seen_grace_seconds: float,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    prev_cursor = self._gemini_cursors.get(agent)
    try:
        workspace_text = str(self.workspace or "").strip()
        if not workspace_text:
            return

        session_path_str = resolve_gemini_native_log(self, agent, native_log_path)

        if not session_path_str:
            return

        file_size = os.path.getsize(session_path_str)
        offset = _advance_native_cursor(self._gemini_cursors, agent, session_path_str, file_size)

        def _append_gemini_entry(entry: dict, *, min_event_ts: float | None = None) -> bool:
            extracted = extract_gemini_message(entry, min_event_ts=min_event_ts)
            if not extracted:
                return False
            
            msg_id = extracted["msg_id"]
            if msg_id in self._synced_msg_ids:
                return False
                
            self._synced_msg_ids.add(msg_id)
            
            if extracted["is_thought"]:
                return False

            jsonl_entry = {
                "timestamp": extracted["timestamp"],
                "session": self.session_name,
                "sender": agent,
                "targets": ["user"],
                "message": f"[From: {agent}]\n{extracted['display_text']}",
                "msg_id": msg_id,
            }
            append_jsonl_entry(self.index_path, jsonl_entry)
            return True

        def _scan_recent_gemini_entries(min_event_ts: float) -> bool:
            appended = False
            try:
                with open(session_path_str, "r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if _append_gemini_entry(entry, min_event_ts=min_event_ts):
                            appended = True
            except Exception:
                return False
            return appended

        if offset is None:
            appended_on_bind = False
            binding_changed = _cursor_binding_changed(prev_cursor, self._gemini_cursors.get(agent))
            if binding_changed:
                min_event_ts = time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS
                appended_on_bind = _scan_recent_gemini_entries(min_event_ts)
            if appended_on_bind or binding_changed:
                self.save_sync_state()
            return

        _assistant_appended = False
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
                if _append_gemini_entry(entry):
                    _assistant_appended = True

        self._gemini_cursors[agent] = NativeLogCursor(path=session_path_str, offset=file_size)
        self.save_sync_state()
        if _assistant_appended:
            self._agent_last_turn_done_ts[agent] = time.time()
    except Exception as exc:
        if prev_cursor is None:
            self._gemini_cursors.pop(agent, None)
        else:
            self._gemini_cursors[agent] = prev_cursor
        logging.error(f"Failed to sync Gemini message for {agent}: {exc}", exc_info=True)
