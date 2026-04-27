from __future__ import annotations

import json
import logging
import os
import time
import uuid

from native_log_sync.core.cursors import (
    NativeLogCursor,
    _advance_native_cursor,
    _cursor_binding_changed,
    _parse_iso_timestamp_epoch,
)
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.claude.log_location import resolve_claude_session_jsonl_path
from native_log_sync.core.jsonl_tail_runtime import parse_jsonl_tail_for_runtime
from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path

_QUIET: frozenset[str] = frozenset({"write_stdin", "todoread"})
_MAIN_LABEL: dict[str, str] = {
    "bash": "Shell",
    "read": "Read",
    "glob": "Explore",
    "toolsearch": "ToolSearch",
    "agent": "Agent",
    "mcp__ccd_session__mark_chapter": "MCP",
    "todowrite": "Todo",
    "write": "Write",
    "edit": "Edit",
}


def parse_jsonl_for_runtime(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return parse_jsonl_tail_for_runtime(
        filepath,
        limit,
        workspace,
        iter_tool_calls=iter_tool_calls,
        tool_events=runtime_tool_events,
        log_label="Claude transcript JSONL",
    )


def iter_tool_calls(entry: dict) -> list[tuple[str, dict]]:
    if entry.get("type") != "assistant":
        return []
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return []
    out: list[tuple[str, dict]] = []
    for c in msg.get("content") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") != "tool_use":
            continue
        name = str(c.get("name") or "tool").strip()
        inp = c.get("input")
        if not isinstance(inp, dict):
            inp = c.get("arguments")
        if not isinstance(inp, dict):
            inp = {}
        out.append((name, inp))
    return out


def _source_id(prefix: str, tail: str) -> str:
    return f"{prefix}:{(tail or '')[:120]}"


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


def _claude_tool_subline(tool_lower: str, args: dict, *, workspace: str) -> str:
    ws = str(workspace or "")
    if tool_lower == "bash":
        cmd = str(args.get("command") or args.get("cmd") or "").strip()
        if not cmd:
            return ""
        line = cmd.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line
    if tool_lower == "read":
        path = display_path(_pick(args, "path", "file_path", "notebook_path"), workspace=ws)
        bits: list[str] = []
        if "offset" in args and args.get("offset") is not None:
            bits.append(f"@{args.get('offset')}")
        if "limit" in args and args.get("limit") is not None:
            bits.append(f"limit {args.get('limit')}")
        suf = f" ({', '.join(bits)})" if bits else ""
        return (path or "") + suf
    if tool_lower == "glob":
        pat = str(args.get("glob_pattern") or args.get("pattern") or "").strip()
        base_raw = str(args.get("target_directory") or args.get("path") or "").strip()
        base = display_path(base_raw, workspace=ws) if base_raw else ""
        if pat and base:
            return f"{pat} in {base}"
        if pat:
            return pat
        return base or "."
    if tool_lower == "toolsearch":
        return str(args.get("query") or "").strip()
    if tool_lower == "agent":
        d = _pick(args, "description", "prompt")
        if not d:
            return ""
        line = d.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line
    if tool_lower == "mcp__ccd_session__mark_chapter":
        t = _pick(args, "title", "summary")
        if len(t) > 120:
            t = t[:117] + "…"
        return f"mark_chapter · {t}" if t else "mark_chapter"
    if tool_lower == "todowrite":
        todos = args.get("todos")
        n = len(todos) if isinstance(todos, list) else 0
        if n <= 0:
            return "update"
        if n == 1 and isinstance(todos, list):
            t0 = todos[0]
            if isinstance(t0, dict):
                c = str(t0.get("content") or t0.get("activeForm") or "").strip()
                return (c[:100] + ("…" if len(c) > 100 else "")) if c else "1 item"
            return "1 item"
        return f"{n} items"
    if tool_lower == "write":
        return display_path(_pick(args, "file_path", "path"), workspace=ws)
    if tool_lower == "edit":
        return display_path(_pick(args, "file_path", "path"), workspace=ws)
    return ""


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    lower = str(name or "").strip().lower()
    if lower in _QUIET:
        return []
    main = _MAIN_LABEL.get(lower)
    if main is None:
        return []
    a = _coerce_args(arguments)
    if not isinstance(a, dict):
        return []
    sub = _claude_tool_subline(lower, a, workspace=str(workspace or "")).strip()
    if not sub:
        return []
    return [runtime_event(main, sub, source_id=_source_id(f"tool:{lower}", sub))]


