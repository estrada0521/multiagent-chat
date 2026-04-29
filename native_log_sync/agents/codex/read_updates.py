from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path

from native_log_sync.agents._shared.path_state import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
)
from multiagent_chat.chat.runtime_format import _pane_runtime_gemini_with_occurrence_ids
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.agents._shared.runtime_display import runtime_event
from native_log_sync.agents._shared.runtime_paths import display_path
from native_log_sync.agents.codex.read_runtime import iter_tool_calls, runtime_tool_events
from native_log_sync.agents._shared.runtime_push import push_runtime_display

def sync_codex_native_log(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    sync_bind_backfill_window_seconds: float,
) -> None:
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    try:
        resolved_path = str(native_log_path or "").strip()
        if not resolved_path or not os.path.exists(resolved_path):
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

        turn_done_seen = False

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
                if (
                    entry.get("type") == "event_msg"
                    and str((entry.get("payload") or {}).get("type") or "").strip().lower() == "task_complete"
                ):
                    turn_done_seen = True
                tool_evs = []
                for name, inp in iter_tool_calls(entry):
                    tool_evs.extend(runtime_tool_events(name, inp, workspace=str(self.workspace or "")))
                if tool_evs:
                    push_runtime_display(self, agent, tool_evs)

        self._codex_cursors[agent] = NativeLogCursor(path=resolved_path, offset=file_size)
        self.save_sync_state()
        if turn_done_seen:
            self._agent_running.discard(agent)
    except Exception as exc:
        logging.error(f"Failed to sync Codex message for {agent}: {exc}")
