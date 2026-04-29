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

QUIET: frozenset[str] = frozenset({"write_stdin"})
MAIN_LABEL: dict[str, str] = {
    "apply_patch": "Patch",
    "exec_command": "Shell",
    "view_image": "Read",
    "list_mcp_resources": "MCP",
    "spawn_agent": "Agent",
    "update_plan": "Plan",
    "send_input": "Input",
    "wait_agent": "Wait",
    "close_agent": "Close",
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

_PATCH = re.compile(r"^\*\*\* Update File:\s*(.+)\s*$", re.MULTILINE)


def _patch_target_path(arg: object) -> str:
    text = arg if isinstance(arg, str) else ""
    if isinstance(arg, dict):
        for k in ("input", "patch", "content", "text"):
            v = arg.get(k)
            if isinstance(v, str) and v.strip():
                text = v
                break
    m = _PATCH.search(text)
    return m.group(1).strip() if m else "(patch)"


def _pick(d: object, *keys: str) -> str:
    if not isinstance(d, dict):
        return ""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _codex_subline(tool_lower: str, args: object, *, workspace: str) -> str:
    ws = str(workspace or "")

    if tool_lower == "apply_patch":
        return _patch_target_path(args)

    if not isinstance(args, dict):
        return ""

    if tool_lower == "exec_command":
        cmd = str(args.get("cmd") or args.get("command") or "").strip()
        if not cmd:
            return ""
        line = cmd.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "view_image":
        return display_path(_pick(args, "path", "file_path"), workspace=ws)

    if tool_lower == "list_mcp_resources":
        srv = str(args.get("server") or "").strip() or "(server)"
        return f"list_resources · {srv}"

    if tool_lower == "spawn_agent":
        d = _pick(args, "message", "description", "prompt")
        if not d:
            d = str(args.get("agent_type") or "").strip() or "(spawn_agent)"
        line = d.split("\n", 1)[0].strip()
        return line[:117] + "..." if len(line) > 120 else line

    if tool_lower == "update_plan":
        plan = args.get("plan")
        n = len(plan) if isinstance(plan, list) else 0
        return f"{n} steps" if n else "plan"

    if tool_lower == "send_input":
        msg = str(args.get("message") or "").strip()
        if not msg:
            return str(args.get("id") or "")
        line = msg.split("\n", 1)[0].strip()
        return line[:97] + "..." if len(line) > 100 else line

    if tool_lower == "wait_agent":
        targets = args.get("targets")
        if isinstance(targets, list) and targets:
            sub = ", ".join(str(t) for t in targets[:3])
            if len(targets) > 3:
                sub += f" +{len(targets) - 3}"
            return sub
        return "(wait)"

    if tool_lower == "close_agent":
        return str(args.get("target") or "").strip() or "(target)"

    return ""


def _sid(p: str, t: str) -> str:
    return f"{p}:{(t or '')[:120]}"


def iter_tool_calls(entry: dict) -> list[tuple[str, object]]:
    if entry.get("type") != "response_item":
        return []
    payload = entry.get("payload") or {}
    ptype = str(payload.get("type") or "").strip()
    if ptype == "custom_tool_call":
        return [(str(payload.get("name") or ""), payload.get("input", ""))]
    if ptype == "function_call":
        return [(str(payload.get("name") or ""), payload.get("arguments", ""))]
    return []


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    lower = str(name or "").strip().lower()
    if lower in QUIET:
        return []
    main = MAIN_LABEL.get(lower)
    if main is None:
        return []
    a = _coerce_args(arguments)
    sub = _codex_subline(lower, a, workspace=str(workspace or "")).strip()
    if not sub:
        return []
    return [runtime_event(main, sub, source_id=_sid(f"tool:{lower}", sub))]


def parse_native_codex_log(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    try:
        tail_bytes = 65_536
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - tail_bytes)
            f.seek(start)
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if start > 0 and lines:
            lines = lines[1:]

        events = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "response_item" and "payload" in data:
                payload = data["payload"]
                ptype = payload.get("type")

                if ptype == "reasoning":
                    summary = payload.get("summary") or []
                    for item in summary:
                        if not isinstance(item, dict):
                            continue
                        text = str(item.get("text") or "").strip()
                        if not text:
                            continue
                        events.append(
                            {
                                "kind": "fixed",
                                "text": f"✦ {text}",
                                "source_id": f"thought:codex:✦ {text}",
                            }
                        )
                elif ptype == "custom_tool_call":
                    name = payload.get("name", "")
                    inp = payload.get("input", "")
                    events.extend(runtime_tool_events(name, inp, workspace=workspace))
                elif ptype == "function_call":
                    name = payload.get("name", "")
                    args = payload.get("arguments", "")
                    events.extend(runtime_tool_events(name, args, workspace=workspace))
            if data.get("type") == "event_msg" and "payload" in data:
                payload = data["payload"] or {}
                if payload.get("type") == "agent_reasoning":
                    text = str(payload.get("text") or "").strip()
                    if text:
                        events.append(
                            {
                                "kind": "fixed",
                                "text": f"✦ {text}",
                                "source_id": f"thought:codex:✦ {text}",
                            }
                        )
        return _pane_runtime_gemini_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error("Failed to parse native codex log %s: %s", filepath, e)
        return None
