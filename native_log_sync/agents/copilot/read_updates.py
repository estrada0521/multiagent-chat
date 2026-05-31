from __future__ import annotations

import hashlib
import json
import logging
import os
import time

from native_log_sync.agents._shared.path_state import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
)
from native_log_sync.agents._shared.runtime_push import push_runtime_display
from native_log_sync.agents.copilot.read_runtime import iter_tool_calls, runtime_tool_events
from backend_core.access.files import append_jsonl_entry
from native_log_sync.duplicate import already_synced_message, mark_message_synced


def _copilot_rate_limit_content(entry: dict) -> str:
    data = entry.get("data") if isinstance(entry, dict) else {}
    if not isinstance(data, dict):
        data = {}
    error_data = data.get("error", {}) if isinstance(data, dict) else {}
    if not isinstance(error_data, dict):
        error_data = {}
    error_type = str(data.get("errorType") or error_data.get("type") or "").strip().lower()
    if not ("rate_limit" in error_type or "quota" in error_type or "limit" in error_type):
        return ""
    return str(data.get("message") or error_data.get("message") or "").strip()


def _copilot_entry_payload(entry: dict, *, min_event_ts: float | None = None) -> tuple[str, str] | None:
    if min_event_ts is not None:
        event_ts = _parse_iso_timestamp_epoch(str(entry.get("timestamp") or ""))
        if event_ts is None or event_ts < min_event_ts:
            return None

    etype = str(entry.get("type") or "").strip()
    data = entry.get("data") if isinstance(entry, dict) else {}
    if not isinstance(data, dict):
        data = {}

    if etype == "assistant.message":
        content = str(data.get("content") or "").strip()
        raw_msg_id = str(data.get("messageId") or entry.get("id") or "").strip()
    elif etype == "session.error":
        content = _copilot_rate_limit_content(entry)
        raw_msg_id = str(entry.get("id") or "").strip()
    else:
        return None

    if not content:
        return None

    msg_id = raw_msg_id or hashlib.sha256(
        f"copilot:{etype}:{entry.get('timestamp')}:{content}".encode("utf-8")
    ).hexdigest()[:12]
    return content, msg_id


def sync_copilot_native_log(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
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

        prev_cursor = self._copilot_cursors.get(agent)
        file_size = os.path.getsize(resolved_path)
        offset = _advance_native_cursor(self._copilot_cursors, agent, resolved_path, file_size)

        def _append_copilot_entry(entry: dict, *, min_event_ts: float | None = None) -> bool:
            payload = _copilot_entry_payload(entry, min_event_ts=min_event_ts)
            if payload is None:
                return False
            content, msg_id = payload
            if already_synced_message(self, agent, content, msg_id):
                return False
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            jsonl_entry = {
                "timestamp": timestamp,
                "session": self.session_name,
                "sender": agent,
                "targets": ["user"],
                "message": content,
                "msg_id": msg_id,
            }
            append_jsonl_entry(self.index_path, jsonl_entry)
            mark_message_synced(self, agent, content, msg_id)
            return True

        def _scan_recent_copilot_entries(min_event_ts: float) -> bool:
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
                        if _append_copilot_entry(entry, min_event_ts=min_event_ts):
                            appended = True
            except Exception:
                return False
            return appended

        if offset is None:
            appended_on_bind = False
            binding_changed = _cursor_binding_changed(prev_cursor, self._copilot_cursors.get(agent))
            if binding_changed:
                min_event_ts = time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS
                appended_on_bind = _scan_recent_copilot_entries(min_event_ts)
            if appended_on_bind or binding_changed:
                self.save_sync_state()
            return

        _has_events = False
        _pending_turn_end = False

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
                tool_evs = []
                for name, inp in iter_tool_calls(entry):
                    tool_evs.extend(runtime_tool_events(name, inp, workspace=str(self.workspace or "")))
                if tool_evs:
                    push_runtime_display(self, agent, tool_evs)

                if etype == "assistant.turn_start":
                    _pending_turn_end = False
                elif etype == "session.error":
                    content = _copilot_rate_limit_content(entry)
                    if content and _append_copilot_entry(entry):
                        pane_id = self.pane_id_for_agent(agent)
                        if pane_id:
                            import subprocess
                            sock = os.environ.get("MULTIAGENT_TMUX_SOCKET")
                            tmux_cmd = ["tmux", "-S" if sock and "/" in sock else "-L", sock] if sock else ["tmux"]
                            subprocess.run([*tmux_cmd, "send-keys", "-t", pane_id, "Escape"], check=False)
                    if content:
                        _pending_turn_end = True
                elif etype == "assistant.message":
                    _append_copilot_entry(entry)
                elif etype == "assistant.turn_end":
                    _pending_turn_end = True

        self._copilot_cursors[agent] = NativeLogCursor(path=resolved_path, offset=file_size)
        self.save_sync_state()

        if _pending_turn_end:
            self._mark_idle(agent)
    except Exception as exc:
        logging.error("Failed to sync Copilot message for %s: %s", agent, exc, exc_info=True)
