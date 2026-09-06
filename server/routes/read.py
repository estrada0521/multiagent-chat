from __future__ import annotations

import hashlib
import json
import logging
from urllib.parse import parse_qs

from appearance.typography import CODE_FONT, MESSAGE_FONT, MOBILE_TEXT_SIZE
from hub_backend.transport.request_base_path import request_base_path
from server.runtime import ENTRY_WINDOW_LIMIT
from shortcut_command.catalog import public_slash_command_dicts


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
    offset_raw = (qs.get("offset", [""])[0] or "").strip()
    if limit_raw:
        try:
            limit_override = max(1, min(ENTRY_WINDOW_LIMIT, int(limit_raw)))
        except ValueError:
            limit_override = None
    try:
        offset = max(0, int(offset_raw)) if offset_raw else 0
    except ValueError:
        offset = 0
    body = ctx["payload_fn"](
        limit_override=limit_override,
        offset=offset,
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


DEFAULT_TRACE_TAIL_LINES = 160  # matches the only caller, apps/mobile/chat/panes/pane-viewer.js


def _get_trace(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    agent = qs.get("agent", [""])[0].lower()
    tail_raw = (qs.get("lines", qs.get("tail", [""]))[0] or "").strip()
    tail_lines = DEFAULT_TRACE_TAIL_LINES
    if tail_raw:
        try:
            tail_lines = max(1, min(int(tail_raw), 10_000))
        except ValueError:
            pass
    try:
        content_str = ctx["runtime"].trace_content(agent, tail_lines=tail_lines)
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
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


def _get_file_view(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    rel = qs.get("path", [""])[0]
    embed = qs.get("embed", [""])[0] == "1"
    force_progressive_text = qs.get("progressive", [""])[0] == "1"
    try:
        preview_text_size = MOBILE_TEXT_SIZE
        requested_text_size = str(qs.get("agent_text_size", [""])[0] or "").strip()
        if requested_text_size:
            try:
                preview_text_size = int(requested_text_size)
            except ValueError:
                pass
        page = ctx["workspace_sync_api"].file_view(
            rel,
            embed=embed,
            base_path=request_base_path(headers=handler.headers, query_string=parsed.query),
            preview_base_theme=str(qs.get("base_theme", [""])[0] or "").strip(),
            agent_font_family=MESSAGE_FONT,
            agent_code_font=CODE_FONT,
            agent_text_size=preview_text_size,
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
        body = json.dumps(files, ensure_ascii=True).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_session_state(handler, _parsed, ctx) -> None:
    qs = parse_qs(_parsed.query)
    projections = (qs.get("projections", [""])[0] or "").strip()
    try:
        body = json.dumps(ctx["runtime"].session_state_payload(projections or None), ensure_ascii=True).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_session_state_events(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    try:
        after_seq = max(0, int((qs.get("after", ["0"])[0] or "0").strip() or "0"))
    except ValueError:
        after_seq = 0
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Connection", "keep-alive")
    handler.end_headers()
    runtime = ctx["runtime"]
    try:
        while True:
            event = runtime.wait_for_session_state_change(after_seq, timeout=15.0)
            if event is None:
                handler.wfile.write(b": keepalive\n\n")
                handler.wfile.flush()
            else:
                after_seq = int(event.get("seq") or after_seq)
                body = (f"event: state\ndata: {json.dumps(event, ensure_ascii=True)}\n\n").encode("utf-8")
                handler.wfile.write(body)
                handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        return
    except Exception:
        logging.exception("SSE stream failed")
        return


def _get_workspace_sync_events(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    try:
        after_seq = max(0, int((qs.get("after", ["0"])[0] or "0").strip() or "0"))
    except ValueError:
        after_seq = 0
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Connection", "keep-alive")
    handler.end_headers()

    def _write_event(name: str, payload: dict) -> None:
        body = (
            f"event: {name}\n"
            f"data: {json.dumps(payload, ensure_ascii=True)}\n\n"
        ).encode("utf-8")
        handler.wfile.write(body)
        handler.wfile.flush()

    try:
        initial = ctx["workspace_sync_api"].workspace_sync_state()
        _write_event("sync", initial)
        last_seq = max(after_seq, int(initial.get("seq") or 0))
        while True:
            state = ctx["workspace_sync_api"].wait_for_sync_event(last_seq, timeout=15.0)
            if state is None:
                handler.wfile.write(b": keepalive\n\n")
                handler.wfile.flush()
                continue
            last_seq = int(state.get("seq") or last_seq)
            _write_event("sync", state)
    except (BrokenPipeError, ConnectionResetError):
        return
    except Exception:
        logging.exception("SSE stream failed")
        return


def _get_git_overview(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    raw_offset = (qs.get("offset", ["0"])[0] or "0").strip()
    raw_limit = (qs.get("limit", ["50"])[0] or "50").strip()
    force_refresh = (qs.get("refresh", [""])[0] or "").lower() in ("1", "true", "yes")
    summary_only = (qs.get("summary", [""])[0] or "").lower() in ("1", "true", "yes")
    try:
        offset = int(raw_offset)
        limit = int(raw_limit)
        data = ctx["workspace_sync_api"].git_overview(
            offset=offset, limit=limit, force_refresh=force_refresh, include_commits=not summary_only
        )
        body = json.dumps(data, ensure_ascii=True).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_git_diff_files(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    commit_hash = (qs.get("hash", [""])[0] or "").strip()
    scope = (qs.get("scope", [""])[0] or "").strip()
    try:
        body = json.dumps(
            ctx["workspace_sync_api"].git_diff_files(commit_hash=commit_hash, scope=scope),
            ensure_ascii=True,
        ).encode("utf-8")
    except Exception as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
        _send_bytes(handler, 500, body, content_type="application/json; charset=utf-8")
        return
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_shortcut_commands(handler, _parsed, ctx) -> None:
    del ctx
    body = json.dumps({"commands": public_slash_command_dicts()}, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


_GET_ROUTES = {
    "/messages": _get_messages,
    "/trace": _get_trace,
    "/file-raw": _get_file_raw,
    "/file-view": _get_file_view,
    "/files-search": _get_files_search,
    "/files-dir": _get_files_dir,
    "/session-state": _get_session_state,
    "/session-state-events": _get_session_state_events,
    "/workspace-sync-events": _get_workspace_sync_events,
    "/git-overview": _get_git_overview,
    "/git-diff-files": _get_git_diff_files,
    "/shortcut-commands": _get_shortcut_commands,
}


def dispatch_get_read_route(handler, parsed, ctx) -> bool:
    route = _GET_ROUTES.get(parsed.path)
    if route is None:
        return False
    route(handler, parsed, ctx)
    return True
