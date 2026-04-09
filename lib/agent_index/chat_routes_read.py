from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs

from .request_base_path_core import request_base_path


def _send_bytes(
    handler,
    status: int,
    body: bytes,
    *,
    content_type: str,
    cache_control: str = "no-store",
    extra_headers: dict[str, str] | None = None,
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    if cache_control:
        handler.send_header("Cache-Control", cache_control)
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(key, value)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _get_messages(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    limit_override = None
    limit_raw = (qs.get("limit", [""])[0] or "").strip()
    before_msg_id = (qs.get("before_msg_id", [""])[0] or "").strip()
    around_msg_id = (qs.get("around_msg_id", [""])[0] or "").strip()
    light_mode = (qs.get("light", [""])[0] or "").strip() == "1"
    if limit_raw:
        try:
            limit_override = max(1, min(2000, int(limit_raw)))
        except ValueError:
            limit_override = None
    body = ctx["payload_fn"](
        limit_override=limit_override,
        before_msg_id=before_msg_id,
        around_msg_id=around_msg_id,
        light_mode=light_mode,
    )
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_message_entry(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    msg_id = (qs.get("msg_id", [""])[0] or "").strip()
    light_mode = (qs.get("light", [""])[0] or "").strip() == "1"
    entry = ctx["runtime"].entry_by_id(msg_id, light_mode=light_mode)
    if entry is None:
        handler.send_error(404)
        return
    body = json.dumps({"entry": entry}, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_normalized_events(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    msg_id = (qs.get("msg_id", [""])[0] or "").strip()
    payload_body = ctx["runtime"].normalized_events_for_msg(msg_id)
    if payload_body is None:
        handler.send_error(404)
        return
    body = json.dumps(payload_body, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_trace(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    agent = qs.get("agent", [""])[0].lower()
    tail_raw = (qs.get("lines", qs.get("tail", [""]))[0] or "").strip()
    tail_lines = None
    if tail_raw:
        try:
            tail_lines = int(tail_raw)
        except ValueError:
            tail_lines = None
        if tail_lines is not None:
            tail_lines = max(1, min(tail_lines, 10_000))
    content_str = ctx["runtime"].trace_content(agent, tail_lines=tail_lines)
    body = json.dumps({"content": content_str}, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_file_raw(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    rel = qs.get("path", [""])[0]
    try:
        metadata = ctx["file_runtime"].raw_response_metadata(rel, handler.headers.get("Range", ""))
    except PermissionError:
        handler.send_error(403)
        return
    except FileNotFoundError:
        handler.send_error(404)
        return
    if int(metadata.get("status", 500)) == 416:
        handler.send_response(416)
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Content-Range", f"bytes */{int(metadata.get('size', 0) or 0)}")
        handler.end_headers()
        return
    handler.send_response(int(metadata.get("status", 200)))
    handler.send_header("Content-Type", str(metadata.get("content_type") or "application/octet-stream"))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Accept-Ranges", "bytes")
    content_range = str(metadata.get("content_range") or "")
    if content_range:
        handler.send_header("Content-Range", content_range)
    handler.send_header("Content-Length", str(int(metadata.get("length", 0) or 0)))
    handler.end_headers()
    ctx["file_runtime"].stream_raw_response(metadata, handler.wfile.write)


def _get_file_content(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    rel = qs.get("path", [""])[0]
    try:
        payload_body = ctx["file_runtime"].file_content(rel)
    except PermissionError:
        handler.send_error(403)
        return
    except FileNotFoundError:
        handler.send_error(404)
        return
    body = json.dumps(payload_body, ensure_ascii=False).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_file_openability(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    rel = qs.get("path", [""])[0]
    try:
        payload_body = {"editable": ctx["file_runtime"].can_open_in_editor(rel)}
    except PermissionError:
        handler.send_error(403)
        return
    except FileNotFoundError:
        handler.send_error(404)
        return
    body = json.dumps(payload_body, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_file_view(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    rel = qs.get("path", [""])[0]
    embed = qs.get("embed", [""])[0] == "1"
    try:
        settings = ctx["load_chat_settings_fn"]()
        agent_font_mode = str(settings.get("agent_font_mode", "serif") or "serif").strip().lower()
        requested_font_mode = str(qs.get("agent_font_mode", [""])[0] or "").strip().lower()
        if requested_font_mode in {"serif", "gothic"}:
            agent_font_mode = requested_font_mode
        agent_message_font = str(
            settings.get(
                "agent_message_font",
                "preset-gothic" if agent_font_mode == "gothic" else "preset-mincho",
            )
            or ("preset-gothic" if agent_font_mode == "gothic" else "preset-mincho")
        ).strip()
        agent_text_size = settings.get("message_text_size")
        requested_text_size = str(qs.get("agent_text_size", [""])[0] or "").strip()
        if requested_text_size:
            try:
                agent_text_size = max(11, min(18, int(requested_text_size)))
            except ValueError:
                pass
        page = ctx["file_runtime"].file_view(
            rel,
            embed=embed,
            base_path=request_base_path(headers=handler.headers, query_string=parsed.query),
            agent_font_mode=agent_font_mode,
            agent_font_family=ctx["runtime"]._font_family_stack(agent_message_font, "agent"),
            agent_text_size=agent_text_size,
        )
    except PermissionError:
        handler.send_error(403)
        return
    except FileNotFoundError:
        handler.send_error(404)
        return
    body = page.encode("utf-8")
    _send_bytes(handler, 200, body, content_type="text/html; charset=utf-8")


def _get_files(handler, _parsed, ctx) -> None:
    try:
        files = ctx["file_runtime"].list_files()
    except Exception:
        files = []
    body = json.dumps(files, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_agents(handler, _parsed, ctx) -> None:
    body = json.dumps(ctx["agent_statuses_fn"](), ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_export(handler, parsed, ctx) -> None:
    try:
        qs = parse_qs(parsed.query)
        limit = int(qs.get("limit", ["100"])[0])
        html_content = ctx["export_runtime"].build_export_html(limit=limit)
        body = html_content.encode("utf-8")
        ts = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{ctx['session_name']}-{ts}.html"
        _send_bytes(
            handler,
            200,
            body,
            content_type="text/html; charset=utf-8",
            extra_headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Export-Filename": filename,
            },
        )
    except Exception as exc:
        _send_bytes(handler, 500, str(exc).encode("utf-8"), content_type="text/plain")


def _get_caffeinate(handler, _parsed, ctx) -> None:
    body = json.dumps(ctx["caffeinate_status_fn"](), ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_auto_mode(handler, _parsed, ctx) -> None:
    body = json.dumps(ctx["auto_mode_status_fn"](), ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_hub_settings(handler, _parsed, ctx) -> None:
    settings = ctx["load_chat_settings_fn"]()
    body = json.dumps(
        {
            "bold_mode_mobile": bool(settings.get("bold_mode_mobile", False)),
            "bold_mode_desktop": bool(settings.get("bold_mode_desktop", False)),
            "bold_mode": bool(settings.get("bold_mode_mobile", False) or settings.get("bold_mode_desktop", False)),
            "agent_font_mode": str(settings.get("agent_font_mode", "serif")),
            "chat_font_settings_css": ctx["chat_font_settings_inline_style_fn"](settings),
            "chat_auto_mode": bool(settings.get("chat_auto_mode", False)),
            "chat_awake": bool(settings.get("chat_awake", False)),
            "chat_sound": bool(settings.get("chat_sound", False)),
            "chat_browser_notifications": bool(settings.get("chat_browser_notifications", False)),
        },
        ensure_ascii=True,
    ).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_session_state(handler, _parsed, ctx) -> None:
    try:
        body = json.dumps(
            {
                "server_instance": ctx["server_instance"],
                "session": ctx["session_name"],
                "active": bool(ctx["runtime"].session_is_active),
                "launch_pending": bool(ctx["runtime"].launch_pending()),
                "targets": ctx["runtime"].active_agents(),
                "statuses": ctx["runtime"].agent_statuses(),
                "agent_runtime": ctx["runtime"].agent_runtime_state(),
                "totals": ctx["runtime"].load_thinking_totals(),
                "provider_runtime": ctx["runtime"].provider_runtime_state(),
            },
            ensure_ascii=True,
        ).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_git_branch_overview(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    raw_offset = (qs.get("offset", ["0"])[0] or "0").strip()
    raw_limit = (qs.get("limit", ["50"])[0] or "50").strip()
    try:
        body = json.dumps(
            ctx["chat_git_module"].git_branch_overview(offset=raw_offset, limit=raw_limit),
            ensure_ascii=True,
        ).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_git_diff(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    commit_hash = (qs.get("hash", [""])[0] or "").strip()
    root = Path(ctx["workspace"] or ctx["repo_root"])
    try:
        if commit_hash:
            result = subprocess.run(
                ["git", "-C", str(root), "diff", f"{commit_hash}~1", commit_hash],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        else:
            result = subprocess.run(
                ["git", "-C", str(root), "diff", "HEAD", "--"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        body = json.dumps({"diff": result.stdout or ""}, ensure_ascii=True).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_memory_path(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    agent = qs.get("agent", ["claude"])[0].lower()
    _, path, history_path = ctx["memory_paths_fn"](agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = ctx["read_memory_content_fn"](path)
    body = json.dumps(
        {"path": str(path), "history_path": str(history_path), "content": content},
        ensure_ascii=True,
    ).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_sync_status(handler, _parsed, ctx) -> None:
    body = json.dumps(ctx["runtime"].sync_cursor_status(), ensure_ascii=False).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_thinking_time(handler, _parsed, ctx) -> None:
    try:
        handler._send_json(200, {"ok": True, "totals": ctx["runtime"].load_thinking_totals()})
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})


_GET_ROUTES = {
    "/messages": _get_messages,
    "/message-entry": _get_message_entry,
    "/normalized-events": _get_normalized_events,
    "/trace": _get_trace,
    "/file-raw": _get_file_raw,
    "/file-content": _get_file_content,
    "/file-openability": _get_file_openability,
    "/file-view": _get_file_view,
    "/files": _get_files,
    "/agents": _get_agents,
    "/export": _get_export,
    "/caffeinate": _get_caffeinate,
    "/auto-mode": _get_auto_mode,
    "/hub-settings": _get_hub_settings,
    "/session-state": _get_session_state,
    "/git-branch-overview": _get_git_branch_overview,
    "/git-diff": _get_git_diff,
    "/memory-path": _get_memory_path,
    "/sync-status": _get_sync_status,
    "/thinking-time": _get_thinking_time,
}


def dispatch_get_read_route(handler, parsed, ctx) -> bool:
    route = _GET_ROUTES.get(parsed.path)
    if route is None:
        return False
    route(handler, parsed, ctx)
    return True
