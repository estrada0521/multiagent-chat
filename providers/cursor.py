from __future__ import annotations

import hashlib
import json
import logging
import os
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


def _cursor_jsonl_assistant_turn_complete(entry: dict) -> bool:
    """True when Cursor appended a final assistant message without tool calls (turn idle)."""
    if entry.get("role") != "assistant":
        return False
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return False
    parts = [c for c in (msg.get("content") or []) if isinstance(c, dict)]
    if not parts:
        return False
    if any(c.get("type") == "tool_use" for c in parts):
        return False
    return True


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
        file_size = os.path.getsize(transcript_path)
        prev_cursor = self._cursor_cursors.get(agent)
        offset = _advance_native_cursor(self._cursor_cursors, agent, transcript_path, file_size)
        if offset is None:
            if _cursor_binding_changed(prev_cursor, self._cursor_cursors.get(agent)):
                self.save_sync_state()
            return

        turn_done_seen = False
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

                if _cursor_jsonl_assistant_turn_complete(entry):
                    turn_done_seen = True

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

        if turn_done_seen:
            self._agent_last_turn_done_ts[agent] = time.time()
            ev = self._agent_turn_done_events.get(agent)
            if ev is not None:
                ev.set()

        self._cursor_cursors[agent] = NativeLogCursor(path=transcript_path, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error(f"Failed to sync Cursor message for {agent}: {exc}")
