from __future__ import annotations

import json
import logging
import os
import time
import uuid

from native_log_sync.agents._shared.path_state import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
)
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.agents.claude.read_runtime import iter_tool_calls, runtime_tool_events
from native_log_sync.agents._shared.runtime_push import push_runtime_display


def _claude_entry_marks_turn_done(entry: dict) -> bool:
    if (
        entry.get("type") == "system"
        and entry.get("subtype") == "turn_duration"
        and not entry.get("isSidechain")
    ):
        return True
    if (
        entry.get("type") == "user"
        and not entry.get("isSidechain")
    ):
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("text") == "[Request interrupted by user]":
                        return True
    if entry.get("type") != "assistant" or entry.get("isSidechain"):
        return False
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return False
    stop_reason = str(msg.get("stop_reason") or "").strip().lower()
    if stop_reason and stop_reason != "tool_use":
        return True
    return bool(entry.get("isApiErrorMessage"))


def sync_claude_native_log(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    first_seen_grace_seconds: float,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    try:
        session_path_str = str(native_log_path or "").strip()
        if not session_path_str or not os.path.exists(session_path_str):
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
                min_event_ts = first_seen - _FIRST_SEEN_GRACE_SECONDS
                appended_on_bind = _scan_recent_claude_entries(min_event_ts)
            if appended_on_bind or _cursor_binding_changed(prev_cursor, self._claude_cursors.get(agent)):
                self.save_sync_state()
            return

        turn_done_seen = False
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
                if _claude_entry_marks_turn_done(entry):
                    turn_done_seen = True
                _append_claude_entry(entry)
                tool_evs = []
                for name, inp in iter_tool_calls(entry):
                    tool_evs.extend(runtime_tool_events(name, inp, workspace=str(self.workspace or "")))
                if tool_evs:
                    push_runtime_display(self, agent, tool_evs)
        if turn_done_seen:
            self._agent_running.discard(agent)

        self._claude_cursors[agent] = NativeLogCursor(path=session_path_str, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error("Failed to sync Claude message for %s: %s", agent, exc, exc_info=True)
