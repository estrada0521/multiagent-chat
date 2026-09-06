from __future__ import annotations

import json
import time
from urllib.parse import parse_qs

from backend_core.access.settings import agent_window_session_root, save_hub_settings
from hub_backend.chat_supervisor import (
    delete_archived_session,
    ensure_chat_server,
    kill_repo_session,
    revive_archived_session,
)
from hub_backend.session_api import resolve_session_chat_target
from hub_backend.session_query import active_session_records_query


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
    resolved = resolve_session_chat_target(ctx["hub"], session_name)
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
        f"/?ts={int(time.time() * 1000)}",
    )
    if fmt == "json":
        handler._send_json(200, {"ok": True, "chat_url": location})
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
    ok, detail = revive_archived_session(ctx["hub"], session_name)
    if not ok:
        if "unresponsive" in (detail or ""):
            handler._send_unhealthy(fmt, detail)
            return
        if fmt == "json":
            handler._send_json(500, {"ok": False, "error": detail})
        else:
            handler._send_html(500, ctx["error_page_fn"](f"Failed to revive {session_name}: {detail}"))
        return
    query = active_session_records_query(ctx["hub"])
    workspace = str((query.records.get(session_name) or {}).get("workspace") or "").strip()
    ok, chat_port, detail = ensure_chat_server(
        ctx["hub"],
        expected_active=True,
        workspace=workspace,
    )
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
        f"/?ts={int(time.time() * 1000)}",
    )
    if fmt == "json":
        handler._send_json(200, {"ok": True, "chat_url": location})
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
    ok, detail = kill_repo_session(ctx["hub"], session_name)
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
    ok, detail = delete_archived_session(ctx["hub"], session_name)
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
    ok, detail, owns_restart = ctx["queue_hub_restart_fn"]()
    body = json.dumps(
        {"ok": ok, "error": "" if ok else detail},
        ensure_ascii=True,
    ).encode("utf-8")
    try:
        handler.send_response(200 if ok else 503)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        handler.wfile.flush()
    finally:
        # queue_hub_restart_fn() may have left this process's request
        # threads as the only thing keeping it alive (see
        # release_restart_hold's docstring) -- only safe to let it exit
        # once the response above has actually gone out.
        if owns_restart:
            ctx["release_restart_hold_fn"]()


def post_settings(handler, _parsed, ctx) -> None:
    data = handler._read_form()
    save_hub_settings(data)
    handler._send_json(200, {"ok": True})


def post_rename_session(handler, _parsed, _ctx) -> None:
    data = handler._read_form()
    old_name = str(data.get("old_name") or "").strip()
    new_name = str(data.get("new_name") or "").strip()
    if any(not name or name in {".", ".."} or "/" in name or "\0" in name for name in (old_name, new_name)):
        handler._send_json(409, {"ok": False, "error": "Session name is not a valid folder name."})
        return
    source = agent_window_session_root() / old_name
    target = agent_window_session_root() / new_name
    if not source.is_dir():
        handler._send_json(409, {"ok": False, "error": f"Session not found: {old_name}"})
        return
    if old_name != new_name and (target.exists() or target.is_symlink()):
        handler._send_json(409, {"ok": False, "error": f"A session named {new_name} already exists."})
        return
    try:
        if old_name != new_name:
            source.rename(target)
    except OSError as exc:
        handler._send_json(409, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, {"ok": True, "old_name": old_name, "new_name": new_name})
