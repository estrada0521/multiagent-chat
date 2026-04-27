"""ツール呼び出し→ランタイム表示イベント。TOOL_MAP / QUIET_TOOLS は呼び出し側（エージェント別）で必ず渡す。"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import unquote, urlparse


def runtime_workspace_roots(workspace: str = "") -> list[str]:
    roots: list[str] = []
    for raw_root in (workspace, os.getcwd()):
        root = str(raw_root or "").strip()
        if not root:
            continue
        normalized = os.path.realpath(root)
        if normalized not in roots:
            roots.append(normalized)
    return roots


def runtime_display_path(value: object, *, workspace: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.match(r"^[a-z][a-z0-9+.-]*://", text, re.IGNORECASE):
        if not text.lower().startswith("file://"):
            return text
        try:
            parsed = urlparse(text)
            text = unquote(parsed.path or "").strip()
        except Exception:
            return text
    if not text:
        return ""
    normalized = os.path.normpath(text)
    if not os.path.isabs(normalized):
        return normalized.replace(os.sep, "/")
    normalized_real = os.path.realpath(normalized)
    for root in runtime_workspace_roots(workspace):
        try:
            rel = os.path.relpath(normalized_real, root)
        except Exception:
            continue
        if rel == ".":
            return "."
        if rel != ".." and not rel.startswith(f"..{os.sep}"):
            return rel.replace(os.sep, "/")
    return normalized_real.replace(os.sep, "/")


def runtime_display_text(action: str, detail: str = "") -> str:
    label = str(action or "").strip() or "Run"
    clean_detail = str(detail or "").strip()
    return f"{label} {clean_detail}".strip()


def runtime_search_detail(pattern: object, target: object = "", *, workspace: str = "") -> str:
    query = str(pattern or "").strip()
    where = runtime_display_path(target, workspace=workspace)
    if query and where:
        return f"{query} in {where}"
    return query or where


def runtime_argument_object(arguments: object) -> object:
    if not isinstance(arguments, str):
        return arguments
    text = arguments.strip()
    if not text:
        return ""
    if not text.startswith("{"):
        return text
    try:
        parsed = json.loads(text)
    except Exception:
        return text
    return parsed


def runtime_event(label: str, summary: str, *, source_id: str) -> dict:
    return {
        "kind": "fixed",
        "text": runtime_display_text(label, summary),
        "source_id": source_id,
    }


def runtime_first_arg(args_obj: object, *keys: str) -> str:
    if not isinstance(args_obj, dict):
        return ""
    for key in keys:
        value = args_obj.get(key)
        if value and isinstance(value, str):
            return value.strip()
    return ""


def apply_tool_entry(entry, args_obj: object, *, tool_name: str, workspace: str) -> list[dict]:
    label, mode, arg_keys = entry.label, entry.mode, entry.arg_keys
    target_keys = entry.target_keys
    if mode == "path":
        target = runtime_display_path(runtime_first_arg(args_obj, *arg_keys), workspace=workspace)
        if target:
            return [runtime_event(label, target, source_id=f"tool:{tool_name}:{label.lower()}:{target[:80]}")]
        return []
    if mode == "query":
        detail = str(runtime_first_arg(args_obj, *arg_keys) or "").strip()
        if detail or label:
            return [runtime_event(label, detail, source_id=f"tool:{tool_name}:{label.lower()}:{detail[:80]}")]
        return []
    if mode == "search":
        pattern = runtime_first_arg(args_obj, *arg_keys)
        target_raw = runtime_first_arg(args_obj, *target_keys) if target_keys else ""
        summary = runtime_search_detail(pattern, target_raw, workspace=workspace)
        if summary:
            return [runtime_event(label, summary, source_id=f"tool:{tool_name}:search:{summary[:80]}")]
        return []
    return []


def runtime_named_tool_events(
    tool_name: str,
    args_obj: object,
    *,
    workspace: str = "",
    tool_map: dict,
    quiet_tools: frozenset,
) -> list[dict]:
    lower_name = str(tool_name or "").strip().lower()

    if lower_name in quiet_tools:
        return []

    entry = tool_map.get(lower_name)
    if entry is not None:
        return apply_tool_entry(entry, args_obj, tool_name=lower_name, workspace=workspace)

    return []


def runtime_tool_events(
    name: object,
    arguments: object,
    *,
    workspace: str = "",
    tool_map: dict,
    quiet_tools: frozenset,
) -> list[dict]:
    tool_name = str(name or "tool").strip() or "tool"
    args_obj = runtime_argument_object(arguments)
    return runtime_named_tool_events(
        tool_name, args_obj, workspace=workspace, tool_map=tool_map, quiet_tools=quiet_tools
    )
