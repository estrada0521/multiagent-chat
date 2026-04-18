from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from .chat_sync_cursor_core import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
    _path_within_roots,
    _pick_latest_unclaimed_for_agent,
    _workspace_slug_variants,
)
from .chat_thinking_kind_core import classify_gemini_message_kind
from .jsonl_append import append_jsonl_entry


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
    workspace_text = str(self.workspace or "").strip()
    if not workspace_text:
        return
    qwen_chat_dirs: list[Path] = []
    seen_qwen_dirs: set[Path] = set()

    def _add_qwen_chat_dirs(path_value: str) -> None:
        for slug in _workspace_slug_variants(path_value, include_lower=True):
            chats_dir = Path.home() / ".qwen" / "projects" / f"-{slug}" / "chats"
            if chats_dir.exists() and chats_dir not in seen_qwen_dirs:
                seen_qwen_dirs.add(chats_dir)
                qwen_chat_dirs.append(chats_dir)

    for alias in self._workspace_aliases(workspace_text):
        _add_qwen_chat_dirs(alias)
    if not qwen_chat_dirs:
        return

    chat_path_str = str(Path(native_log_path)) if native_log_path else ""
    if not chat_path_str:
        cursor = self._qwen_cursors.get(agent)
        if (
            cursor
            and cursor.path
            and os.path.exists(cursor.path)
            and self._should_stick_to_existing_cursor(agent)
            and _path_within_roots(cursor.path, qwen_chat_dirs)
        ):
            chat_path_str = cursor.path
        else:
            chat_candidates: list[Path] = []
            for qwen_chats_dir in qwen_chat_dirs:
                chat_candidates.extend(qwen_chats_dir.glob("*.jsonl"))
            first_seen_ts = self._first_seen_for_agent(agent)
            strict_first_bind = (
                agent not in self._qwen_cursors
                and self._should_stick_to_existing_cursor(agent)
            )
            min_mtime = first_seen_ts if strict_first_bind else first_seen_ts - _FIRST_SEEN_GRACE_SECONDS
            picked = _pick_latest_unclaimed_for_agent(
                chat_candidates,
                self._qwen_cursors,
                agent,
                min_mtime=min_mtime,
                exclude_paths=set(self._collect_global_native_log_claims().keys()),
            )
            if picked is None:
                return
            chat_path_str = str(picked)
    elif self._is_globally_claimed_path(chat_path_str):
        return
    if not os.path.exists(chat_path_str):
        return
    file_size = os.path.getsize(chat_path_str)
    prev_cursor = self._qwen_cursors.get(agent)
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
            else:
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
    workspace_text = str(self.workspace or "").strip()
    if not workspace_text:
        return
    gemini_chat_dirs: list[Path] = []
    seen_gemini_dirs: set[Path] = set()

    def _add_gemini_chat_dirs(path_value: str) -> None:
        workspace_name = Path(str(path_value or "")).name.strip()
        if not workspace_name:
            return
        for variant in _workspace_slug_variants(workspace_name, include_lower=True):
            chats_dir = Path.home() / ".gemini" / "tmp" / variant / "chats"
            if chats_dir.exists() and chats_dir not in seen_gemini_dirs:
                seen_gemini_dirs.add(chats_dir)
                gemini_chat_dirs.append(chats_dir)

    for alias in self._workspace_aliases(workspace_text):
        _add_gemini_chat_dirs(alias)
    if not gemini_chat_dirs:
        return

    session_path_str = str(Path(native_log_path)) if native_log_path else ""
    picked = None
    if not session_path_str:
        cursor = self._gemini_cursors.get(agent)
        if (
            cursor
            and cursor.path
            and os.path.exists(cursor.path)
            and self._should_stick_to_existing_cursor(agent)
            and _path_within_roots(cursor.path, gemini_chat_dirs)
        ):
            session_path_str = cursor.path
            picked = Path(session_path_str)
        else:
            candidates: list[Path] = []
            for chats_dir in gemini_chat_dirs:
                candidates.extend(chats_dir.glob("session-*.json"))
            first_seen_ts = self._first_seen_for_agent(agent)
            strict_first_bind = (
                agent not in self._gemini_cursors
                and self._should_stick_to_existing_cursor(agent)
            )
            min_mtime = first_seen_ts if strict_first_bind else first_seen_ts - _FIRST_SEEN_GRACE_SECONDS
            picked = _pick_latest_unclaimed_for_agent(
                candidates,
                self._gemini_cursors,
                agent,
                min_mtime=min_mtime,
                exclude_paths=set(self._collect_global_native_log_claims().keys()),
            )
            if picked is None:
                return
            session_path_str = str(picked)
    elif self._is_globally_claimed_path(session_path_str):
        return
    if not picked:
        picked = Path(session_path_str)
    if not os.path.exists(session_path_str):
        return
    file_size = picked.stat().st_size
    prev_cursor = self._gemini_cursors.get(agent)
    offset = _advance_native_cursor(self._gemini_cursors, agent, session_path_str, file_size)

    with open(session_path_str, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", []) if isinstance(data, dict) else []

    def _append_gemini_entry(message: dict, *, min_event_ts: float | None = None) -> bool:
        if message.get("type") != "gemini":
            return False
        if min_event_ts is not None:
            event_ts = _parse_iso_timestamp_epoch(str(message.get("timestamp") or ""))
            if event_ts is None or event_ts < min_event_ts:
                return False
        msg_id = str(message.get("id") or "")[:12]
        if not msg_id:
            return False

        content = message.get("content", [])
        texts = []
        has_thought_part = False
        if isinstance(content, str):
            if content.strip():
                texts.append(content)
        elif isinstance(content, list):
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("thought") is True:
                    has_thought_part = True
                text_raw = c.get("text")
                if text_raw:
                    text = str(text_raw).strip()
                    if text:
                        texts.append(text)

        if not texts:
            return False

        if msg_id in self._synced_msg_ids:
            return False

        kind = classify_gemini_message_kind(texts, has_thought_part=has_thought_part)
        if kind == "agent-thinking":
            self._synced_msg_ids.add(msg_id)
            return False

        display = "\n".join(texts)
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

    if offset is None:
        appended_on_bind = False
        binding_changed = _cursor_binding_changed(prev_cursor, self._gemini_cursors.get(agent))
        if binding_changed:
            min_event_ts = time.time() - _SYNC_BIND_BACKFILL_WINDOW_SECONDS
            for m in messages:
                if _append_gemini_entry(m, min_event_ts=min_event_ts):
                    appended_on_bind = True
        if appended_on_bind or binding_changed:
            self.save_sync_state()
        return

    for m in messages:
        _append_gemini_entry(m)

    self._gemini_cursors[agent] = NativeLogCursor(path=session_path_str, offset=file_size)
    self.save_sync_state()
