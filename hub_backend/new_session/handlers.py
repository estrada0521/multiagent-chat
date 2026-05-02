from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, quote as url_quote


def get_check_session_name(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    workspace = (qs.get("workspace", [""])[0] or "").strip()
    if not workspace:
        handler._send_json(400, {"ok": False, "error": "workspace required"})
        return
    try:
        resolved = str(Path(workspace).expanduser().resolve())
    except Exception as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    original = re.sub(r"[^a-zA-Z0-9_.\-]", "-", Path(resolved).name or "session").strip(".-")[:64] or "session"
    proposed = ctx["session_api"].unique_session_name_for_workspace(resolved)
    handler._send_json(200, {"ok": True, "name": proposed, "original": original, "conflict": proposed != original})


def post_pick_workspace(handler, _parsed, _ctx) -> None:
    if sys.platform != "darwin" or not shutil.which("osascript"):
        handler._send_json(501, {"ok": False, "error": "native workspace picker is unavailable on this device"})
        return
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        data = {}
    start_path = str(data.get("path") or "").strip()
    start_clause = ""
    if start_path:
        try:
            candidate = Path(start_path).expanduser().resolve()
            if candidate.exists():
                escaped = str(candidate).replace("\\", "\\\\").replace('"', '\\"')
                start_clause = f' default location POSIX file "{escaped}"'
        except Exception:
            start_clause = ""
    script = (
        'set chosenFolder to choose folder with prompt "Choose workspace folder"'
        f"{start_clause}\n"
        "return POSIX path of chosenFolder"
    )
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        handler._send_json(504, {"ok": False, "error": "workspace picker timed out"})
        return
    stderr_text = str(proc.stderr or "").strip()
    if proc.returncode != 0:
        if "-128" in stderr_text or "User canceled" in stderr_text:
            handler._send_json(200, {"ok": False, "canceled": True})
            return
        handler._send_json(500, {"ok": False, "error": stderr_text or "workspace picker failed"})
        return
    chosen = str(proc.stdout or "").strip()
    if not chosen:
        handler._send_json(500, {"ok": False, "error": "workspace picker returned an empty path"})
        return
    try:
        resolved = Path(chosen).expanduser().resolve()
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    if not resolved.is_dir():
        handler._send_json(400, {"ok": False, "error": f"Invalid workspace: {resolved}"})
        return
    handler._send_json(200, {"ok": True, "path": str(resolved)})


def post_mkdir(handler, _parsed, _ctx) -> None:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        handler._send_json(400, {"ok": False, "error": "invalid json"})
        return
    path_str = str(data.get("path") or "").strip()
    if not path_str:
        handler._send_json(400, {"ok": False, "error": "path required"})
        return
    path = Path(path_str)
    try:
        path.mkdir(parents=True, exist_ok=True)
        handler._send_json(200, {"ok": True, "path": str(path.resolve())})
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})


def post_start_session_draft(handler, _parsed, ctx) -> None:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        handler._send_json(400, {"ok": False, "error": "invalid json"})
        return
    workspace = str(data.get("workspace") or "").strip()
    if not workspace:
        handler._send_json(400, {"ok": False, "error": "workspace required"})
        return
    try:
        resolved_workspace = str(Path(workspace).expanduser().resolve())
    except Exception as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    if not Path(resolved_workspace).is_dir():
        handler._send_json(400, {"ok": False, "error": f"Invalid workspace: {resolved_workspace}"})
        return
    override_name = re.sub(r"[^a-zA-Z0-9_.\-]", "-", str(data.get("session_name") or "")).strip(".-")[:64]
    if override_name:
        query = ctx["active_session_records_query_fn"]()
        existing = set(query.records.keys())
        try:
            existing.update(ctx["archived_session_records_fn"](existing).keys())
        except Exception:
            pass
        if override_name in existing or ctx["session_api"].session_logs_dir(override_name).exists():
            handler._send_json(409, {"ok": False, "error": f"セッション名 '{override_name}' は既に使用されています"})
            return
        session_name = override_name
    else:
        session_name = ctx["session_api"].unique_session_name_for_workspace(resolved_workspace)
    try:
        session_state = ctx["session_api"].write_pending_session_files(
            session_name,
            resolved_workspace,
            list(ctx["all_agent_names"]),
        )
        ok, chat_port, detail = ctx["session_api"].ensure_pending_chat_server(
            session_name,
            resolved_workspace,
            list(ctx["all_agent_names"]),
        )
        if not ok:
            handler._send_json(500, {"ok": False, "error": detail})
            return
        record = ctx["session_api"].build_pending_session_record(
            session_name,
            resolved_workspace,
            list(ctx["all_agent_names"]),
            created_at=session_state.get("created_at", ""),
            updated_at=session_state.get("updated_at", ""),
        )
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    draft_query = f"follow=1&compose=1&ts={int(time.time() * 1000)}"
    draft_chat_url = f"/session/{url_quote(session_name, safe='')}/?{draft_query}"
    handler._send_json(
        200,
        {
            "ok": True,
            "session": session_name,
            "chat_url": draft_chat_url,
            "session_record": record,
        },
    )


def post_start_session(handler, _parsed, ctx) -> None:
    try:
        ctx["post_start_session_fn"](
            handler,
            all_agent_names=ctx["all_agent_names"],
            new_session_max_per_agent=ctx["new_session_max_per_agent"],
            script_path=ctx["script_path"],
            ensure_chat_server_fn=ctx["ensure_chat_server_fn"],
            active_session_records_query_fn=ctx["active_session_records_query_fn"],
            agent_launch_readiness_fn=ctx["agent_launch_readiness_fn"],
        )
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
