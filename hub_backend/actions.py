from __future__ import annotations

import time
from urllib.parse import parse_qs

from hub_backend.coordinated_restart import request_new_chat_on_active_session_ports


def get_open_session(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    session_name = (qs.get("session", [""])[0] or "").strip()
    fmt = qs.get("format", [""])[0]
    if not session_name:
        if fmt == "json":
            handler._send_json(404, {"ok": False, "error": "Session not found"})
        else:
            handler._send_html(404, ctx["error_page_fn"]("That session is not available in this repo."))
        return
    resolved = ctx["session_api"].resolve_session_chat_target(session_name)
    if resolved["status"] == "unhealthy":
        handler._send_unhealthy(fmt, resolved.get("detail", ""))
        return
    if resolved["status"] == "missing":
        if fmt == "json":
            handler._send_json(404, {"ok": False, "error": "Session not found"})
        else:
            handler._send_html(404, ctx["error_page_fn"]("That session is not available in this repo."))
        return
    if resolved["status"] != "ok":
        detail = str(resolved.get("detail") or "")
        if fmt == "json":
            handler._send_json(500, {"ok": False, "error": detail})
        else:
            handler._send_html(500, ctx["error_page_fn"](f"Failed to start chat for {session_name}: {detail}"))
        return
    chat_port = int(resolved.get("chat_port") or 0)
    location = ctx["format_session_chat_url_fn"](
        handler.headers.get("Host", "127.0.0.1"),
        session_name,
        chat_port,
        f"/?follow=1&ts={int(time.time() * 1000)}",
    )
    if fmt == "json":
        handler._send_json(200, {"ok": True, "chat_url": location, "session_record": resolved.get("session_record", {})})
    else:
        handler.send_response(302)
        handler.send_header("Location", location)
        handler.end_headers()


def get_revive_session(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    session_name = (qs.get("session", [""])[0] or "").strip()
    fmt = qs.get("format", [""])[0]
    if not session_name:
        if fmt == "json":
            handler._send_json(404, {"ok": False, "error": "Session not found"})
        else:
            handler._send_html(404, ctx["error_page_fn"]("That archived session is not available in this repo."))
        return
    ok, detail = ctx["revive_archived_session_fn"](session_name)
    if not ok:
        if "unresponsive" in (detail or ""):
            handler._send_unhealthy(fmt, detail)
            return
        if fmt == "json":
            handler._send_json(500, {"ok": False, "error": detail})
        else:
            handler._send_html(500, ctx["error_page_fn"](f"Failed to revive {session_name}: {detail}"))
        return
    ok, chat_port, detail = ctx["ensure_chat_server_fn"](session_name)
    if not ok:
        if fmt == "json":
            handler._send_json(500, {"ok": False, "error": detail})
        else:
            handler._send_html(500, ctx["error_page_fn"](f"Failed to start chat for {session_name}: {detail}"))
        return
    location = ctx["format_session_chat_url_fn"](
        handler.headers.get("Host", "127.0.0.1"),
        session_name,
        chat_port,
        f"/?follow=1&ts={int(time.time() * 1000)}",
    )
    if fmt == "json":
        query = ctx["active_session_records_query_fn"]()
        handler._send_json(200, {"ok": True, "chat_url": location, "session_record": query.records.get(session_name, {})})
    else:
        handler.send_response(302)
        handler.send_header("Location", location)
        handler.end_headers()


def get_kill_session(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    session_name = (qs.get("session", [""])[0] or "").strip()
    fmt = qs.get("format", [""])[0]
    if not session_name:
        if fmt == "json":
            handler._send_json(404, {"ok": False, "error": "Session not found"})
        else:
            handler._send_html(404, ctx["error_page_fn"]("That active session is not available in this repo."))
        return
    if ctx["session_api"].is_pending_launch_session(session_name):
        ok, detail = ctx["session_api"].delete_pending_draft_session(session_name)
        if not ok:
            if fmt == "json":
                handler._send_json(500, {"ok": False, "error": detail or f"Failed to delete draft session {session_name}"})
            else:
                handler._send_html(500, ctx["error_page_fn"](f"Failed to delete draft session {session_name}: {detail}"))
            return
        if fmt == "json":
            handler._send_json(200, {"ok": True, "session": session_name, "action": "deleted", "pending": True})
        else:
            handler.send_response(302)
            handler.send_header("Location", "/")
            handler.end_headers()
        return
    ok, detail = ctx["kill_repo_session_fn"](session_name)
    if not ok:
        if fmt == "json":
            handler._send_json(500, {"ok": False, "error": detail or f"Failed to kill {session_name}"})
        else:
            handler._send_html(500, ctx["error_page_fn"](f"Failed to kill {session_name}: {detail}"))
        return
    if fmt == "json":
        handler._send_json(200, {"ok": True, "session": session_name, "action": "killed"})
    else:
        handler.send_response(302)
        handler.send_header("Location", "/")
        handler.end_headers()


def get_delete_archived_session(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    session_name = (qs.get("session", [""])[0] or "").strip()
    fmt = qs.get("format", [""])[0]
    if not session_name:
        if fmt == "json":
            handler._send_json(404, {"ok": False, "error": "Session not found"})
        else:
            handler._send_html(404, ctx["error_page_fn"]("That archived session is not available in this repo."))
        return
    if ctx["session_api"].is_pending_launch_session(session_name):
        ok, detail = ctx["session_api"].delete_pending_draft_session(session_name)
        if not ok:
            if fmt == "json":
                handler._send_json(500, {"ok": False, "error": detail or f"Failed to delete draft session {session_name}"})
            else:
                handler._send_html(500, ctx["error_page_fn"](f"Failed to delete draft session {session_name}: {detail}"))
            return
        if fmt == "json":
            handler._send_json(200, {"ok": True, "session": session_name, "action": "deleted", "pending": True})
        else:
            handler.send_response(302)
            handler.send_header("Location", "/")
            handler.end_headers()
        return
    ok, detail = ctx["delete_archived_session_fn"](session_name)
    if not ok:
        if fmt == "json":
            handler._send_json(500, {"ok": False, "error": detail or f"Failed to delete archived session {session_name}"})
        else:
            handler._send_html(500, ctx["error_page_fn"](f"Failed to delete archived session {session_name}: {detail}"))
        return
    if fmt == "json":
        handler._send_json(200, {"ok": True, "session": session_name, "action": "deleted"})
    else:
        handler.send_response(302)
        handler.send_header("Location", "/")
        handler.end_headers()


def post_restart_hub(handler, _parsed, ctx) -> None:
    request_new_chat_on_active_session_ports(ctx["active_session_records_query_fn"])
    ctx["queue_hub_restart_fn"]()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(b'{"ok":true}')


def post_settings(handler, parsed, ctx) -> None:
    data = handler._read_form()
    ctx["save_hub_settings_fn"](data)
    qs = parse_qs(parsed.query)
    if qs.get("embed", ["0"])[0] == "1":
        handler._redirect("/settings?embed=1&saved=1")
        return
    handler._redirect("/settings?saved=1")
