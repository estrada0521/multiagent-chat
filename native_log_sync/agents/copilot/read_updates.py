from __future__ import annotations

import json
import logging
import os
import time
import uuid

from native_log_sync.agents._shared.path_state import NativeLogCursor, _advance_native_cursor, _cursor_binding_changed
from multiagent_chat.jsonl_append import append_jsonl_entry

def sync_copilot_native_log(self, agent: str, native_log_path: str | None = None) -> None:
    try:
        resolved_path = str(native_log_path) if native_log_path else ""
        if not resolved_path:
            cursor = self._copilot_cursors.get(agent)
            if cursor and cursor.path and os.path.exists(cursor.path):
                resolved_path = cursor.path
            else:
                from native_log_sync.agents.copilot.resolve_path import resolve_path

                pane_id = self.pane_id_for_agent(agent)
                pane_pid = self.pane_field(pane_id, "#{pane_pid}")
                if pane_id and pane_pid:
                    resolved_path = resolve_path(self, agent, pane_pid)
                if not resolved_path or not os.path.exists(resolved_path):
                    return

        file_size = os.path.getsize(resolved_path)
        prev_cursor = self._copilot_cursors.get(agent)
        offset = _advance_native_cursor(self._copilot_cursors, agent, resolved_path, file_size)
        if offset is None:
            if _cursor_binding_changed(prev_cursor, self._copilot_cursors.get(agent)):
                self.save_sync_state()
            return

        _has_events = False
        _assistant_appended = False
        _cur_turn_has_tools = False
        _final_turn_ended = False  # turn_end with no tools = final answer

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
                etype = str(entry.get("type") or "").strip()
                if not etype:
                    continue
                _has_events = True
                data = entry.get("data") if isinstance(entry, dict) else {}
                if not isinstance(data, dict):
                    data = {}

                if etype == "assistant.turn_start":
                    _cur_turn_has_tools = False
                elif etype == "tool.execution_start":
                    _cur_turn_has_tools = True
                elif etype == "assistant.message":
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
                    _assistant_appended = True
                elif etype == "assistant.turn_end":
                    _final_turn_ended = not _cur_turn_has_tools

        self._copilot_cursors[agent] = NativeLogCursor(path=resolved_path, offset=file_size)
        self.save_sync_state()

        if _has_events and agent not in self._agent_running:
            self._agent_running.add(agent)

        if _final_turn_ended:
            self._agent_running.discard(agent)
    except Exception as exc:
        logging.error("Failed to sync Copilot message for %s: %s", agent, exc, exc_info=True)
