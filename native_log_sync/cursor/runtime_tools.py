from __future__ import annotations

import os

from native_log_sync.core.runtime_display import (
    runtime_argument_object,
    runtime_display_path,
    runtime_event,
    runtime_tool_events as _core_runtime_tool_events,
)
from native_log_sync.cursor.tools import QUIET_TOOLS, TOOL_MAP


def _source_id(prefix: str, detail: str) -> str:
    return f"{prefix}:{(detail or '')[:120]}"


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    raw_name = str(name or "").strip() or "tool"
    lower = raw_name.lower()
    args_obj = runtime_argument_object(arguments)
    ws = str(workspace or "")

    if lower in QUIET_TOOLS:
        return []

    if lower == "read" and isinstance(args_obj, dict):
        path = runtime_display_path(args_obj.get("path"), workspace=ws)
        bits: list[str] = []
        if "offset" in args_obj and args_obj.get("offset") is not None:
            bits.append(f"@{args_obj.get('offset')}")
        if "limit" in args_obj and args_obj.get("limit") is not None:
            bits.append(f"limit {args_obj.get('limit')}")
        suffix = f" ({', '.join(bits)})" if bits else ""
        detail = (path or "") + suffix
        if not detail.strip():
            return []
        return [runtime_event("Read", detail.strip(), source_id=_source_id("tool:read", detail))]

    if lower == "glob" and isinstance(args_obj, dict):
        pat = str(args_obj.get("glob_pattern") or "").strip()
        td = str(args_obj.get("target_directory") or "").strip()
        where = runtime_display_path(td, workspace=ws) if td else ""
        if pat and where:
            detail = f"{pat} in {where}"
        elif pat:
            detail = pat
        else:
            detail = where or "."
        return [runtime_event("Explore", detail, source_id=_source_id("tool:glob", detail))]

    if lower == "semanticsearch" and isinstance(args_obj, dict):
        q = str(args_obj.get("query") or "").strip()
        tds = args_obj.get("target_directories")
        extra = ""
        if isinstance(tds, list) and tds:
            first = str(tds[0] or "").strip()
            if first:
                extra = runtime_display_path(first, workspace=ws)
        if q and extra:
            detail = f"{q} in {extra}"
        elif q:
            detail = q
        else:
            detail = extra
        if not detail.strip():
            detail = "(semantic search)"
        return [runtime_event("Search", detail.strip(), source_id=_source_id("tool:semanticsearch", detail))]

    if lower == "readlints" and isinstance(args_obj, dict):
        paths = args_obj.get("paths")
        if isinstance(paths, list) and paths:
            rels = [runtime_display_path(p, workspace=ws) for p in paths[:3] if p]
            rels = [r for r in rels if r]
            if len(paths) > 3:
                detail = f"{', '.join(rels)} +{len(paths) - 3} more" if rels else f"{len(paths)} files"
            else:
                detail = ", ".join(rels) if rels else f"{len(paths)} files"
        else:
            detail = "lint"
        return [runtime_event("Lint", detail, source_id=_source_id("tool:readlints", detail))]

    return _core_runtime_tool_events(
        raw_name, arguments, workspace=ws, tool_map=TOOL_MAP, quiet_tools=QUIET_TOOLS
    )
