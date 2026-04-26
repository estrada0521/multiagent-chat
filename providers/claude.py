from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path

from multiagent_chat.chat.sync.cursor import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
    _pick_latest_unclaimed_for_agent,
    _workspace_slug_variants,
)
from multiagent_chat.jsonl_append import append_jsonl_entry


def sync_claude_assistant_messages(
    self,
    agent: str,
    native_log_path: str | None = None,
    *,
    workspace_hint: str | None = None,
    first_seen_grace_seconds: float,
    sync_bind_backfill_window_seconds: float,
    claude_bind_backfill_window_seconds: float,
) -> None:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    _SYNC_BIND_BACKFILL_WINDOW_SECONDS = float(sync_bind_backfill_window_seconds)
    _CLAUDE_BIND_BACKFILL_WINDOW_SECONDS = float(claude_bind_backfill_window_seconds)
    try:
        session_path_str = str(Path(native_log_path)) if native_log_path else ""
        if not session_path_str:
            cursor = self._claude_cursors.get(agent)
            if (
                cursor
                and cursor.path
                and os.path.exists(cursor.path)
                and self._should_stick_to_existing_cursor(agent)
            ):
                session_path_str = cursor.path
            else:
                jsonl_candidates: list[Path] = []
                seen_dirs: set[Path] = set()

                def _add_workspace_candidates(workspace: str | None) -> None:
                    ws = str(workspace or "").strip()
                    if not ws:
                        return
                    candidate_paths = [ws]
                    git_root = self._workspace_git_root(ws)
                    if git_root and git_root != ws:
                        candidate_paths.append(git_root)
                    for candidate_path in candidate_paths:
                        for slug in _workspace_slug_variants(candidate_path):
                            workspace_dir = Path.home() / ".claude" / "projects" / f"-{slug}"
                            if workspace_dir in seen_dirs or not workspace_dir.exists():
                                continue
                            seen_dirs.add(workspace_dir)
                            jsonl_candidates.extend(workspace_dir.glob("*.jsonl"))

                hint_workspace = str(workspace_hint or "").strip()
                session_workspace = str(self.workspace or "").strip()
                prefer_session_then_hint = False
                if hint_workspace and session_workspace:
                    try:
                        hint_resolved = str(Path(hint_workspace).resolve())
                    except Exception:
                        hint_resolved = hint_workspace
                    try:
                        session_resolved = str(Path(session_workspace).resolve())
                    except Exception:
                        session_resolved = session_workspace
                    if session_resolved.startswith(hint_resolved.rstrip("/") + "/"):
                        prefer_session_then_hint = True
                if prefer_session_then_hint:
                    _add_workspace_candidates(session_workspace)
                else:
                    if hint_workspace and session_workspace:
                        if session_workspace == hint_workspace:
                            _add_workspace_candidates(session_workspace)
                        else:
                            _add_workspace_candidates(hint_workspace)
                            _add_workspace_candidates(session_workspace)
                    else:
                        _add_workspace_candidates(hint_workspace)
                        _add_workspace_candidates(session_workspace)

                cursor = self._claude_cursors.get(agent)
                if cursor and cursor.path:
                    cursor_dir = Path(cursor.path).parent
                    if cursor_dir not in seen_dirs and cursor_dir.exists():
                        seen_dirs.add(cursor_dir)
                        jsonl_candidates.extend(cursor_dir.glob("*.jsonl"))

                if not jsonl_candidates:
                    return
                min_mtime = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                session_path = _pick_latest_unclaimed_for_agent(
                    jsonl_candidates,
                    self._claude_cursors,
                    agent,
                    min_mtime=min_mtime,
                    exclude_paths=set(self._collect_global_native_log_claims().keys()),
                )
                if session_path is None:
                    return
                session_path_str = str(session_path)
        elif self._is_globally_claimed_path(session_path_str):
            return
        if not os.path.exists(session_path_str):
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
                self._claude_bind_backfill_until[agent] = max(
                    self._claude_bind_backfill_until.get(agent, 0.0),
                    first_seen + _CLAUDE_BIND_BACKFILL_WINDOW_SECONDS,
                )
                min_event_ts = first_seen - _FIRST_SEEN_GRACE_SECONDS
                appended_on_bind = _scan_recent_claude_entries(min_event_ts)
            else:
                backfill_deadline = self._claude_bind_backfill_until.get(agent, 0.0)
                if backfill_deadline:
                    if time.time() <= backfill_deadline:
                        min_event_ts = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                        appended_on_bind = _scan_recent_claude_entries(min_event_ts)
                    else:
                        self._claude_bind_backfill_until.pop(agent, None)
            if appended_on_bind or _cursor_binding_changed(prev_cursor, self._claude_cursors.get(agent)):
                self.save_sync_state()
            return

        backfill_deadline = self._claude_bind_backfill_until.get(agent, 0.0)
        if backfill_deadline:
            if time.time() <= backfill_deadline:
                min_event_ts = self._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
                _scan_recent_claude_entries(min_event_ts)
            else:
                self._claude_bind_backfill_until.pop(agent, None)

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
                if (
                    entry.get("type") == "system"
                    and entry.get("subtype") == "turn_duration"
                    and not entry.get("isSidechain")
                ):
                    turn_done_seen = True
                _append_claude_entry(entry)
        if turn_done_seen:
            self._agent_last_turn_done_ts[agent] = time.time()
            ev = self._agent_turn_done_events.get(agent)
            if ev is not None:
                ev.set()

        self._claude_cursors[agent] = NativeLogCursor(path=session_path_str, offset=file_size)
        self.save_sync_state()
    except Exception as exc:
        logging.error(f"Failed to sync Claude message for {agent}: {exc}", exc_info=True)
