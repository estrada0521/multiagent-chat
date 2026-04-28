from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path

from native_log_sync.agents._shared.path_state import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
)
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.agents._shared.jsonl_runtime import parse_jsonl_tail_for_runtime
from native_log_sync.agents._shared.runtime_display import runtime_event
from native_log_sync.agents._shared.runtime_paths import display_path

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
