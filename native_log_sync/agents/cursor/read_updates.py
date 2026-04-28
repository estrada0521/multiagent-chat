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
)
from multiagent_chat.jsonl_append import append_jsonl_entry
from multiagent_chat.redacted_placeholder import normalize_cursor_plaintext_for_index


def _cursor_assistant_message_has_no_tool_use(entry: dict) -> bool:
    """True when this line is an assistant message whose content blocks include no tool_use."""
    if entry.get("role") != "assistant":
        return False
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return False
    content = msg.get("content")
    if isinstance(content, list):
        return not any(isinstance(c, dict) and c.get("type") == "tool_use" for c in content)
    if isinstance(content, str):
        return True
    return False


def _cursor_turn_done_from_batch(batch: list[tuple[int, dict]]) -> bool:
    return any(_cursor_assistant_message_has_no_tool_use(entry) for _ls, entry in batch)


def _extract_cursor_sync_display_text(entry: dict) -> str:
    role = entry.get("role", "")
    if role == "assistant":
        msg_obj = entry.get("message") if isinstance(entry, dict) else {}
        if not isinstance(msg_obj, dict):
            return ""
        content = msg_obj.get("content", [])
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            texts: list[str] = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    text = str(c.get("text") or "").strip()
                    if text:
                        texts.append(text)
            if not texts:
                return ""
            return "\n".join(texts)
        return ""
    if role == "system":
        msg_obj = entry.get("message") if isinstance(entry, dict) else {}
        if isinstance(msg_obj, dict):
            content = msg_obj.get("content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
        elif isinstance(msg_obj, str) and msg_obj.strip():
            return msg_obj.strip()
        return ""
    return ""


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
        transcript_path = str(native_log_path or "").strip()
        if not transcript_path:
            existing = self._cursor_cursors.get(agent)
            if existing and existing.path:
                transcript_path = existing.path
        if not transcript_path:
            return

        if not os.path.exists(transcript_path):
            return
        file_size = os.path.getsize(transcript_path)
        prev_cursor = self._cursor_cursors.get(agent)
        offset = _advance_native_cursor(self._cursor_cursors, agent, transcript_path, file_size)
        if offset is None:
            if _cursor_binding_changed(prev_cursor, self._cursor_cursors.get(agent)):
                self.save_sync_state()
            return

        batch: list[tuple[int, dict]] = []
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
                batch.append((line_start, entry))

        turn_done_seen = _cursor_turn_done_from_batch(batch)

        for line_start, entry in batch:
            display = _extract_cursor_sync_display_text(entry)
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

        if turn_done_seen:
            self._agent_running.discard(agent)

        self._cursor_cursors[agent] = NativeLogCursor(path=transcript_path, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error("Failed to sync Cursor message for %s: %s", agent, exc)
