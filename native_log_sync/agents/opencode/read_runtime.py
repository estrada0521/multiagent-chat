from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path

from multiagent_chat.chat.runtime_format import _pane_runtime_with_occurrence_ids
from native_log_sync.io.cursor_state import OpenCodeCursor
from multiagent_chat.jsonl_append import append_jsonl_entry

from native_log_sync.agents._shared.runtime_display import runtime_event
from native_log_sync.agents._shared.runtime_paths import display_path
from native_log_sync.agents.opencode.resolve_path import opencode_db_path

QUIET: frozenset[str] = frozenset({"invalid"})
MAIN_LABEL: dict[str, str] = {
    "bash": "Shell",
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "glob": "Explore",
    "grep": "Search",
    "codesearch": "Search",
    "websearch": "Search",
    "webfetch": "Fetch",
    "task": "Task",
    "skill": "Skill",
    "question": "Ask",
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


def _opencode_subline(tool_lower: str, args: dict, *, workspace: str) -> str:
    ws = str(workspace or "")

    if tool_lower == "bash":
        cmd = str(args.get("command") or args.get("cmd") or "").strip()
        if not cmd:
            return ""
        line = cmd.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "read":
        return display_path(_pick(args, "path", "file_path"), workspace=ws)

    if tool_lower == "write":
        return display_path(_pick(args, "path", "file_path"), workspace=ws)

    if tool_lower == "edit":
        return display_path(_pick(args, "path", "file_path"), workspace=ws)

    if tool_lower == "glob":
        pat = str(args.get("pattern") or args.get("glob_pattern") or "").strip()
        td_raw = str(args.get("path") or args.get("target_directory") or "").strip()
        td = display_path(td_raw, workspace=ws) if td_raw else ""
        return f"{pat} in {td}" if pat and td else (pat or td or ".")

    if tool_lower == "grep":
        pat = _pick(args, "pattern", "q", "query")
        tgt_raw = _pick(args, "path", "dir_path")
        tgt = display_path(tgt_raw, workspace=ws) if tgt_raw else ""
        return f"{pat} in {tgt}" if pat and tgt else (pat or tgt)

    if tool_lower in {"codesearch", "websearch"}:
        return _pick(args, "query", "q", "search_term")

    if tool_lower == "webfetch":
        return _pick(args, "url", "uri")

    if tool_lower == "task":
        d = _pick(args, "description", "prompt", "name")
        if not d:
            return ""
        line = d.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "skill":
        return str(args.get("skill") or args.get("name") or "").strip() or "(skill)"

    if tool_lower == "question":
        q = str(args.get("question") or args.get("prompt") or "").strip()
        if not q:
            return ""
        line = q.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    return ""


def _sid(p: str, t: str) -> str:
    return f"{p}:{(t or '')[:120]}"


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    lower = str(name or "").strip().lower()
    if lower in QUIET:
        return []
    main = MAIN_LABEL.get(lower)
    if main is None:
        return []
    a = _coerce_args(arguments)
    if not isinstance(a, dict):
        return []
    sub = _opencode_subline(lower, a, workspace=str(workspace or "")).strip()
    if not sub:
        return []
    return [runtime_event(main, sub, source_id=_sid(f"tool:{lower}", sub))]


def parse_opencode_runtime(runtime, agent: str, limit: int) -> list[dict] | None:
    try:
        db_path = opencode_db_path()
        if not db_path.exists():
            return None
        oc = runtime._opencode_cursors.get(agent)
        if not oc or not oc.session_id:
            return None
        conn = sqlite3.connect(str(db_path), timeout=1)
        cur = conn.cursor()
        cur.execute(
            "SELECT p.data FROM part p JOIN message m ON p.message_id = m.id "
            "WHERE m.session_id = ? ORDER BY p.time_created DESC LIMIT 30",
            (oc.session_id,),
        )
        events: list[dict] = []
        for (pd,) in cur.fetchall():
            pdata = json.loads(pd)
            if pdata.get("type") != "tool":
                continue
            tool_name = pdata.get("tool", "tool")
            state = pdata.get("state") or {}
            inp = state.get("input") or {}
            events.extend(runtime_tool_events(tool_name, inp, workspace=runtime.workspace))
        conn.close()
        events.reverse()
        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error("Failed to parse OpenCode runtime for %s: %s", agent, e)
        return None
