"""Cursor: native JSONL からツールコールを読み（ランタイム行用）。

旧 ``log_readout`` のうちツール周りだけ。
"""

from __future__ import annotations

import json

from native_log_sync.core.jsonl_tail_runtime import parse_jsonl_tail_for_runtime
from native_log_sync.core.runtime_display import runtime_event
from native_log_sync.core.runtime_paths import display_path

_QUIET: frozenset[str] = frozenset({"todowrite"})


def parse_jsonl_for_runtime(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return parse_jsonl_tail_for_runtime(
        filepath,
        limit,
        workspace,
        iter_tool_calls=iter_tool_calls,
        tool_events=runtime_tool_events,
        log_label="Cursor transcript JSONL",
    )


def iter_tool_calls(entry: dict) -> list[tuple[str, dict]]:
    if entry.get("role") != "assistant":
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


def _coerce(arguments: object) -> object:
    if not isinstance(arguments, str):
        return arguments
    text = arguments.strip()
    if not text:
        return ""
    if not text.startswith("{"):
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _pick(d: object, *keys: str) -> str:
    if not isinstance(d, dict):
        return ""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    raw = str(name or "").strip() or "tool"
    lower = raw.lower()
    if lower in _QUIET:
        return []
    ws = str(workspace or "")
    args_obj = _coerce(arguments)
    if not isinstance(args_obj, dict):
        return []

    if lower == "read":
        path = display_path(args_obj.get("path"), workspace=ws)
        bits: list[str] = []
        if "offset" in args_obj and args_obj.get("offset") is not None:
            bits.append(f"@{args_obj.get('offset')}")
        if "limit" in args_obj and args_obj.get("limit") is not None:
            bits.append(f"limit {args_obj.get('limit')}")
        suffix = f" ({', '.join(bits)})" if bits else ""
        sub = (path or "") + suffix
        if not sub.strip():
            return []
        return [runtime_event("Read", sub.strip(), source_id=_source_id("tool:read", sub))]

    if lower == "glob":
        pat = str(args_obj.get("glob_pattern") or "").strip()
        td = str(args_obj.get("target_directory") or "").strip()
        td_disp = display_path(td, workspace=ws) if td else ""
        if pat and td_disp:
            sub = f"{pat} in {td_disp}"
        elif pat:
            sub = pat
        else:
            sub = td_disp or "."
        return [runtime_event("Explore", sub, source_id=_source_id("tool:glob", sub))]

    if lower == "semanticsearch":
        q = str(args_obj.get("query") or "").strip()
        tds = args_obj.get("target_directories")
        extra = ""
        if isinstance(tds, list) and tds:
            t0 = str(tds[0] or "").strip()
            extra = display_path(t0, workspace=ws) if t0 else ""
        if q and extra:
            sub = f"{q} in {extra}"
        elif q:
            sub = q
        elif extra:
            sub = extra
        else:
            sub = "(semantic search)"
        return [runtime_event("Search", sub.strip(), source_id=_source_id("tool:semanticsearch", sub))]

    if lower == "readlints":
        paths_list = args_obj.get("paths")
        if isinstance(paths_list, list) and paths_list:
            parts = [display_path(p, workspace=ws) for p in paths_list[:3] if p]
            parts = [p for p in parts if p]
            if len(paths_list) > 3:
                sub = f"{', '.join(parts)} +{len(paths_list) - 3} more" if parts else f"{len(paths_list)} files"
            else:
                sub = ", ".join(parts) if parts else f"{len(paths_list)} files"
        else:
            sub = "lint"
        return [runtime_event("Lint", sub, source_id=_source_id("tool:readlints", sub))]

    if lower == "shell":
        cmd = str(args_obj.get("command") or args_obj.get("cmd") or "").strip()
        if not cmd:
            return []
        first = cmd.split("\n", 1)[0].strip()
        if len(first) > 120:
            first = first[:117] + "..."
        return [runtime_event("Shell", first, source_id=_source_id("tool:shell", first))]

    if lower == "grep":
        pat = _pick(args_obj, "pattern", "q", "query")
        raw_tgt = _pick(args_obj, "path", "dir_path")
        tgt = display_path(raw_tgt, workspace=ws) if raw_tgt else ""
        if pat and tgt:
            sub = f"{pat} in {tgt}"
        else:
            sub = pat or tgt
        if not sub:
            return []
        return [runtime_event("Search", sub, source_id=_source_id("tool:grep", sub))]

    if lower == "strreplace":
        path = display_path(_pick(args_obj, "path", "file_path"), workspace=ws)
        if not path:
            return []
        return [runtime_event("Edit", path, source_id=_source_id("tool:strreplace", path))]

    if lower == "write":
        path = display_path(_pick(args_obj, "path", "file_path"), workspace=ws)
        if not path:
            return []
        return [runtime_event("Write", path, source_id=_source_id("tool:write", path))]

    if lower == "delete":
        path = display_path(_pick(args_obj, "path", "file_path"), workspace=ws)
        if not path:
            return []
        return [runtime_event("Delete", path, source_id=_source_id("tool:delete", path))]

    if lower == "websearch":
        q = _pick(args_obj, "search_term", "query", "q")
        if not q:
            return []
        return [runtime_event("Search", q, source_id=_source_id("tool:websearch", q))]

    if lower == "webfetch":
        url = _pick(args_obj, "url", "uri")
        if not url:
            return []
        return [runtime_event("Fetch", url, source_id=_source_id("tool:webfetch", url))]

    return []
