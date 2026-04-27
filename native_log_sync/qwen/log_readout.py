"""Qwen Code: JSONL のランタイム表示とチャット index 同期。"""

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
)
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.core.jsonl_tail_runtime import parse_jsonl_tail_for_runtime
from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path

MAIN_LABEL: dict[str, str] = {
    "read_file": "Read",
    "write_file": "Write",
    "edit": "Edit",
    "glob": "Explore",
    "list_directory": "Explore",
    "grep_search": "Search",
    "run_shell_command": "Shell",
    "web_search": "Search",
    "web_fetch": "Fetch",
    "agent": "Agent",
    "skill": "Skill",
    "ask_user_question": "Ask",
    "todo_write": "Todo",
    "printf": "Printf",
}


def _coerce_args(arguments: object) -> object:
    if not isinstance(arguments, str):
        return arguments
    t = arguments.strip()
    if not t or not t.startswith("{"):
        return t
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return t


def _pick(d: object, *keys: str) -> str:
    if not isinstance(d, dict):
        return ""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _qwen_subline(tool_lower: str, args: dict, *, workspace: str) -> str:
    ws = str(workspace or "")

    if tool_lower == "read_file":
        return display_path(_pick(args, "file_path", "path"), workspace=ws)

    if tool_lower == "write_file":
        return display_path(_pick(args, "file_path", "path"), workspace=ws)

    if tool_lower == "edit":
        return display_path(_pick(args, "file_path", "path"), workspace=ws)

    if tool_lower == "glob":
        pat = str(args.get("pattern") or "").strip()
        td_raw = str(args.get("path") or "").strip()
        td = display_path(td_raw, workspace=ws) if td_raw else ""
        return f"{pat} in {td}" if pat and td else (pat or td or ".")

    if tool_lower == "list_directory":
        return display_path(_pick(args, "dir_path", "path"), workspace=ws)

    if tool_lower == "grep_search":
        pat = _pick(args, "pattern", "q", "query")
        tgt_raw = _pick(args, "path", "dir_path")
        tgt = display_path(tgt_raw, workspace=ws) if tgt_raw else ""
        return f"{pat} in {tgt}" if pat and tgt else (pat or tgt)

    if tool_lower == "run_shell_command":
        cmd = str(args.get("command") or args.get("cmd") or "").strip()
        if not cmd:
            return ""
        line = cmd.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "web_search":
        return _pick(args, "query", "q", "search_term")

    if tool_lower == "web_fetch":
        return _pick(args, "url", "uri")

    if tool_lower == "agent":
        d = _pick(args, "description", "prompt")
        if not d:
            return ""
        line = d.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "skill":
        return str(args.get("skill") or args.get("name") or "").strip() or "(skill)"

    if tool_lower == "ask_user_question":
        q = str(args.get("question") or args.get("prompt") or "").strip()
        if not q:
            return ""
        line = q.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "todo_write":
        todos = args.get("todos")
        n = len(todos) if isinstance(todos, list) else 0
        return f"{n} items" if n else "update"

    if tool_lower == "printf":
        body = str(args.get("arg1") or args.get("arg0") or "").strip()
        if not body:
            return "…"
        line = body.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    return ""


def iter_tool_calls(entry: dict) -> list[tuple[str, dict]]:
    """type=assistant の message.parts[].functionCall。"""
    if entry.get("type") != "assistant":
        return []
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return []
    out: list[tuple[str, dict]] = []
    for p in msg.get("parts") or []:
        if not isinstance(p, dict):
            continue
        fc = p.get("functionCall")
        if not isinstance(fc, dict):
            continue
        name = str(fc.get("name") or "tool").strip()
        inp = fc.get("args")
        if not isinstance(inp, dict):
            inp = {}
        out.append((name, inp))
    return out


def _sid(p: str, t: str) -> str:
    return f"{p}:{(t or '')[:120]}"


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    lower = str(name or "").strip().lower()
    main = MAIN_LABEL.get(lower)
    if main is None:
        return []
    a = _coerce_args(arguments)
    if not isinstance(a, dict):
        return []
    sub = _qwen_subline(lower, a, workspace=str(workspace or "")).strip()
    if not sub:
        return []
    return [runtime_event(main, sub, source_id=_sid(f"tool:{lower}", sub))]


def parse_jsonl_for_runtime(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return parse_jsonl_tail_for_runtime(
        filepath,
        limit,
        workspace,
        iter_tool_calls=iter_tool_calls,
        tool_events=runtime_tool_events,
        log_label="Qwen transcript JSONL",
    )


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
        from native_log_sync.qwen.log_location import resolve_qwen_chat_jsonl_path

        chat_path_str = resolve_qwen_chat_jsonl_path(
            self,
            agent,
            native_log_path,
            first_seen_grace_seconds=_FIRST_SEEN_GRACE_SECONDS,
        )
        if not chat_path_str:
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


