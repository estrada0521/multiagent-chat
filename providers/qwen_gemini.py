from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

from native_log_sync.gemini.messages import extract_gemini_message
from native_log_sync.gemini.resolve_log import resolve_gemini_native_log
from multiagent_chat.chat.sync.cursor import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
    _path_within_roots,
    _pick_latest_unclaimed_for_agent,
    _workspace_slug_variants,
)
from multiagent_chat.chat.thinking_kind import classify_gemini_message_kind
from multiagent_chat.jsonl_append import append_jsonl_entry


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

        workspace_aliases = self._workspace_aliases(workspace_text)
        
        session_path_str = resolve_gemini_native_log(
            agent=agent,
            workspace_aliases=workspace_aliases,
            native_log_path=native_log_path,
            gemini_cursors=self._gemini_cursors,
            should_stick_to_existing_cursor=self._should_stick_to_existing_cursor(agent),
            first_seen_ts=self._first_seen_for_agent(agent),
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
            global_claimed_paths=set(self._collect_global_native_log_claims().keys()),
        )
        
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
            ev = self._agent_turn_done_events.get(agent)
            if ev is not None:
                ev.set()
    except Exception as exc:
        if prev_cursor is None:
            self._gemini_cursors.pop(agent, None)
        else:
            self._gemini_cursors[agent] = prev_cursor
        logging.error(f"Failed to sync Gemini message for {agent}: {exc}", exc_info=True)