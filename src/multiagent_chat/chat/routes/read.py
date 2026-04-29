from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import parse_qs

from ...transport.request_base_path import request_base_path


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


def _send_not_modified(
    handler,
    *,
    cache_control: str = "no-cache",
    extra_headers: dict[str, str] | None = None,
) -> None:
    handler.send_response(304)
    if cache_control:
        handler.send_header("Cache-Control", cache_control)
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(key, value)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def _etag_for_body(body: bytes) -> str:
    digest = hashlib.blake2s(body, digest_size=12).hexdigest()
    return f'"ma-{digest}"'


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
    etag = _etag_for_body(body)
    headers = {"ETag": etag}
    if (handler.headers.get("If-None-Match") or "").strip() == etag:
        _send_not_modified(handler, extra_headers=headers)
        return
    _send_bytes(
        handler,
        200,
        body,
        content_type="application/json; charset=utf-8",
        cache_control="no-cache",
        extra_headers=headers,
    )


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
        metadata = ctx["workspace_sync_api"].raw_response_metadata(rel, handler.headers.get("Range", ""))
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
    ctx["workspace_sync_api"].stream_raw_response(metadata, handler.wfile.write)


def _get_file_content(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    rel = qs.get("path", [""])[0]
    try:
        payload_body = ctx["workspace_sync_api"].file_content(rel)
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
        payload_body = ctx["workspace_sync_api"].openability(rel)
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
    pane = qs.get("pane", [""])[0] == "1"
    force_progressive_text = qs.get("progressive", [""])[0] == "1"
    try:
        settings = ctx["load_chat_settings_fn"]()
        user_message_font = str(settings.get("user_message_font", "preset-gothic") or "preset-gothic").strip()
        preview_font_mode = "serif" if user_message_font == "preset-mincho" else "gothic"
        preview_text_size = settings.get("message_text_size")
        requested_text_size = str(qs.get("agent_text_size", [""])[0] or "").strip()
        if requested_text_size:
            try:
                preview_text_size = max(11, min(18, int(requested_text_size)))
            except ValueError:
                pass
        requested_message_bold = str(qs.get("message_bold", [""])[0] or "").strip().lower()
        if requested_message_bold in {"1", "true", "yes", "on"}:
            message_bold = True
        elif requested_message_bold in {"0", "false", "no", "off"}:
            message_bold = False
        else:
            message_bold = bool(settings.get("bold_mode_mobile", False) or settings.get("bold_mode_desktop", False))
        page = ctx["workspace_sync_api"].file_view(
            rel,
            embed=embed,
            pane=pane,
            base_path=request_base_path(headers=handler.headers, query_string=parsed.query),
            agent_font_mode=preview_font_mode,
            agent_font_family=ctx["runtime"]._font_family_stack(user_message_font, "user"),
            agent_text_size=preview_text_size,
            message_bold=message_bold,
            force_progressive_text=force_progressive_text,
        )
    except PermissionError:
        handler.send_error(403)
        return
    except FileNotFoundError:
        handler.send_error(404)
        return
    body = page.encode("utf-8")
    _send_bytes(handler, 200, body, content_type="text/html; charset=utf-8")


def _get_files(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    force_refresh = (qs.get("refresh", [""])[0] or "").lower() in ("1", "true", "yes")
    try:
        files = ctx["workspace_sync_api"].list_files(force_refresh=force_refresh)
    except Exception:
        files = []
    body = json.dumps(files, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_files_dir(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    rel = (qs.get("path", [""])[0] or "").strip()
    try:
        entries = ctx["workspace_sync_api"].list_dir(rel)
    except PermissionError:
        handler.send_error(403)
        return
    except (FileNotFoundError, NotADirectoryError):
        handler.send_error(404)
        return
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    body = json.dumps({"path": rel, "entries": entries}, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_files_search(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    query = (qs.get("q", qs.get("query", [""]))[0] or "").strip()
    limit_raw = (qs.get("limit", [""])[0] or "").strip()
    limit = 60
    if limit_raw:
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 60
    try:
        files = ctx["workspace_sync_api"].search_files(query, limit=limit, force_refresh=False)
    except Exception:
        files = []
    body = json.dumps(files, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_agents(handler, _parsed, ctx) -> None:
    body = json.dumps(ctx["agent_statuses_fn"](), ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


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
            "open_files_direct_external_editor": bool(
                settings.get("open_files_direct_external_editor", False)
            ),
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
    force_refresh = (qs.get("refresh", [""])[0] or "").lower() in ("1", "true", "yes")
    try:
        offset = max(0, int(raw_offset))
    except ValueError:
        offset = 0
    try:
        limit = max(1, min(int(raw_limit), 200))
    except ValueError:
        limit = 50
    try:
        data = ctx["workspace_sync_api"].git_branch_overview(
            offset=offset, limit=limit, force_refresh=force_refresh
        )
        body = json.dumps(data, ensure_ascii=True).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_git_diff(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    commit_hash = (qs.get("hash", [""])[0] or "").strip()
    file_path = (qs.get("path", [""])[0] or "").strip()
    root = Path(ctx["workspace"] or ctx["repo_root"])
    try:
        path_args = ["--", file_path] if file_path else ["--"]
        if commit_hash:
            result = subprocess.run(
                ["git", "-C", str(root), "diff", f"{commit_hash}~1", commit_hash] + path_args,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        else:
            result = subprocess.run(
                ["git", "-C", str(root), "diff", "HEAD"] + path_args,
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


def _get_debug_native_log_sync(handler, _parsed, ctx) -> None:
    try:
        from debug.native_log_sync.payload import build_native_log_resolved_paths_payload
    except ImportError:
        body = json.dumps(
            {"ok": False, "error": "debug bundle missing (expected debug/native_log_sync/)"},
            ensure_ascii=True,
        ).encode("utf-8")
        _send_bytes(handler, 503, body, content_type="application/json; charset=utf-8")
        return
    try:
        payload = build_native_log_resolved_paths_payload(ctx["runtime"])
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_git_diff_files(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    commit_hash = (qs.get("hash", [""])[0] or "").strip()
    try:
        body = json.dumps(
            ctx["workspace_sync_api"].git_diff_files(commit_hash=commit_hash),
            ensure_ascii=True,
        ).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


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
    "/files-search": _get_files_search,
    "/files-dir": _get_files_dir,
    "/agents": _get_agents,
    "/caffeinate": _get_caffeinate,
    "/auto-mode": _get_auto_mode,
    "/hub-settings": _get_hub_settings,
    "/session-state": _get_session_state,
    "/debug/native-log-sync": _get_debug_native_log_sync,
    "/git-branch-overview": _get_git_branch_overview,
    "/git-diff": _get_git_diff,
    "/git-diff-files": _get_git_diff_files,
}


def dispatch_get_read_route(handler, parsed, ctx) -> bool:
    route = _GET_ROUTES.get(parsed.path)
    if route is None:
        return False
    route(handler, parsed, ctx)
    return True
