from __future__ import annotations

import json
import logging
import os
import time
import uuid

from multiagent_chat.chat.sync.cursor import NativeLogCursor, _advance_native_cursor, _cursor_binding_changed
from multiagent_chat.jsonl_append import append_jsonl_entry


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
