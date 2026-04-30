from __future__ import annotations

import datetime
import json
import os
import re
import shlex
import subprocess
import uuid
from pathlib import Path
from urllib.parse import unquote as url_unquote


def _read_json_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8") or "{}"), None
    except json.JSONDecodeError:
        return None, "invalid json"


def _resolve_within_root(path_value: str, *, workspace_root: str, allowed_root: Path) -> Path:
    raw = str(path_value or "").strip()
    if not raw:
        raise ValueError("path required")
    if raw.startswith("~"):
        candidate = Path(raw).expanduser().resolve()
    elif os.path.isabs(raw):
        candidate = Path(raw).resolve()
    else:
        candidate = (Path(workspace_root).resolve() / raw.lstrip("/")).resolve()
    root = allowed_root.resolve()
    candidate.relative_to(root)
    return candidate


def _post_caffeinate(handler, _parsed, ctx) -> None:
    handler._send_json(200, ctx["caffeinate_toggle_fn"]())


def _post_auto_mode(handler, _parsed, ctx) -> None:
    current = ctx["auto_mode_status_fn"]()
    action = "off" if current["active"] else "on"
    bin_dir = Path(ctx["agent_send_path"]).parent
    try:
        subprocess.run(
            [str(bin_dir / "multiagent-auto-mode"), action, "--session", ctx["session_name"]],
            capture_output=True,
            text=True,
            env=ctx["clean_env_fn"](),
            check=False,
        )
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, {"ok": True, "active": not current["active"]})


def _post_new_chat(handler, _parsed, ctx) -> None:
    try:
        ctx["runtime"].refresh_native_log_bindings(reason="reload")
    except Exception:
        pass
    ok, detail = ctx["queue_chat_restart_fn"]()
    if not ok:
        handler._send_json(500, {"ok": False, "error": detail})
        return
    handler._send_json(200, {"ok": True, "port": ctx["port"], "restarting": True, "detail": detail})


def _post_add_agent(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    agent = (data.get("agent") or "").strip().lower()
    if not agent:
        handler._send_json(400, {"ok": False, "error": "agent required"})
        return
    bin_dir = Path(ctx["agent_send_path"]).parent
    try:
        proc = subprocess.run(
            [str(bin_dir / "multiagent"), "add-agent", "--session", ctx["session_name"], "--agent", agent],
            capture_output=True,
            text=True,
            env=ctx["clean_env_fn"](),
            check=False,
        )
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        handler._send_json(500, {"ok": False, "error": stderr or stdout or f"add-agent failed ({proc.returncode})"})
        return
    handler._send_json(
        200,
        {
            "ok": True,
            "agent": agent,
            "message": stdout or f"Added agent {agent}",
            "targets": ctx["runtime"].active_agents(),
        },
    )
    try:
        ctx["runtime"].refresh_native_log_bindings([agent], reason="add-agent")
    except Exception:
        pass
    try:
        ctx["runtime"].notify_session_state_changed()
    except Exception:
        pass


def _post_remove_agent(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    agent = (data.get("agent") or "").strip()
    if not agent:
        handler._send_json(400, {"ok": False, "error": "agent required"})
        return
    bin_dir = Path(ctx["agent_send_path"]).parent
    try:
        proc = subprocess.run(
            [str(bin_dir / "multiagent"), "remove-agent", "--session", ctx["session_name"], "--agent", agent],
            capture_output=True,
            text=True,
            env=ctx["clean_env_fn"](),
            check=False,
        )
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        handler._send_json(
            500,
            {"ok": False, "error": stderr or stdout or f"remove-agent failed ({proc.returncode})"},
        )
        return
    handler._send_json(
        200,
        {
            "ok": True,
            "agent": agent,
            "message": stdout or f"Removed agent {agent}",
            "targets": ctx["runtime"].active_agents(),
        },
    )
    try:
        ctx["runtime"].refresh_native_log_bindings(reason="remove-agent")
    except Exception:
        pass
    try:
        ctx["runtime"].notify_session_state_changed()
    except Exception:
        pass


def _post_log_system(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    msg = (data.get("message") or "").strip()
    if not msg:
        handler._send_json(400, {"ok": False, "error": "message required"})
        return
    ctx["append_system_entry_fn"](msg)
    handler._send_json(200, {"ok": True})
def _post_upload(handler, _parsed, ctx) -> None:
    content_type = handler.headers.get("Content-Type", "application/octet-stream")
    raw_name = handler.headers.get("X-Filename", "upload.bin") or "upload.bin"
    try:
        filename = url_unquote(raw_name)
    except Exception:
        filename = raw_name
    filename = re.sub(r"[\x00-\x1f\x7f\u200b-\u200f\u2028\u2029]", "", str(filename)).strip()
    filename = Path(filename).name or "upload.bin"
    if filename in (".", ".."):
        filename = "upload.bin"
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    data = handler.rfile.read(length)
    upload_dir = Path(ctx["workspace"]) / "logs" / ctx["session_name"] / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(filename).stem or "upload"
    ext = Path(filename).suffix
    if not ext:
        mt = (content_type or "").split(";")[0].strip().lower()
        ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }.get(mt, ".bin")
    save_name = f"{stem}{ext}"
    save_path = upload_dir / save_name
    if save_path.exists():
        counter = 1
        while (upload_dir / f"{stem}_{counter}{ext}").exists():
            counter += 1
        save_name = f"{stem}_{counter}{ext}"
        save_path = upload_dir / save_name
    save_path.write_bytes(data)
    try:
        rel_path = str(save_path.relative_to(Path(ctx["workspace"])))
    except ValueError:
        rel_path = str(save_path)
    handler._send_json(200, {"ok": True, "path": rel_path})


def _post_rename_upload(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    old_rel = data.get("path", "")
    label = data.get("label", "").strip()
    if not old_rel or not label:
        handler._send_json(400, {"ok": False, "error": "path and label required"})
        return
    upload_dir = Path(ctx["workspace"]) / "logs" / ctx["session_name"] / "uploads"
    try:
        old_path = _resolve_within_root(old_rel, workspace_root=ctx["workspace"], allowed_root=upload_dir)
    except ValueError as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    except Exception:
        handler._send_json(403, {"ok": False, "error": "forbidden"})
        return
    if not old_path.is_file():
        handler._send_json(404, {"ok": False, "error": "file not found"})
        return
    label = re.sub(r"[\x00-\x1f\x7f\u200b-\u200f\u2028\u2029/\\]", "", label)
    label = re.sub(r"[^\w\-. ]", "_", label).strip()[:80]
    if not label:
        handler._send_json(400, {"ok": False, "error": "invalid label"})
        return
    ext = old_path.suffix
    new_name = f"{label}{ext}"
    new_path = old_path.parent / new_name
    if new_path.exists() and new_path != old_path:
        new_name = f"{label}_{uuid.uuid4().hex[:4]}{ext}"
        new_path = old_path.parent / new_name
    old_path.rename(new_path)
    try:
        new_rel = str(new_path.relative_to(Path(ctx["workspace"])))
    except ValueError:
        new_rel = str(new_path)
    handler._send_json(200, {"ok": True, "path": new_rel})


def _post_delete_upload(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    path_rel = data.get("path", "")
    if not path_rel:
        handler._send_json(400, {"ok": False, "error": "path required"})
        return
    upload_dir = Path(ctx["workspace"]) / "logs" / ctx["session_name"] / "uploads"
    try:
        target = _resolve_within_root(path_rel, workspace_root=ctx["workspace"], allowed_root=upload_dir)
    except ValueError as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    try:
        target.unlink(missing_ok=True)
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, {"ok": True})


def _post_open_terminal(handler, _parsed, ctx) -> None:
    try:
        socket_flag = "-S" if "/" in ctx["tmux_socket"] else "-L"
        cols, rows = 200, 60
        try:
            size_result = subprocess.run(
                [
                    "tmux",
                    socket_flag,
                    ctx["tmux_socket"],
                    "display-message",
                    "-p",
                    "-t",
                    f"={ctx['session_name']}:0",
                    "#{window_width} #{window_height}",
                ],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            if size_result.returncode == 0:
                parts = (size_result.stdout or "").strip().split()
                if len(parts) == 2:
                    parsed_cols = int(parts[0])
                    parsed_rows = int(parts[1])
                    if parsed_cols > 0 and parsed_rows > 0:
                        cols, rows = parsed_cols, parsed_rows
        except Exception:
            pass
        attach_cmd = (
            f"env -u TMUX -u TMUX_PANE tmux {socket_flag} "
            f"{shlex.quote(ctx['tmux_socket'])} attach-session -t {shlex.quote(ctx['session_name'])}"
        )
        apple_script = (
            f'tell application "Terminal"\n'
            f'  do script "{attach_cmd}"\n'
            f'  set targetWindow to front window\n'
            f'  set number of columns of targetWindow to {cols}\n'
            f'  set number of rows of targetWindow to {rows}\n'
            f'  activate\n'
            f'end tell'
        )
        subprocess.Popen(
            ["osascript", "-e", apple_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        handler._send_json(200, {"ok": True})
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})


def _post_open_finder(handler, _parsed, ctx) -> None:
    try:
        target = Path(ctx["workspace"] or ctx["repo_root"]).resolve()
        if not target.exists():
            handler._send_json(404, {"ok": False, "error": "workspace not found"})
            return
        subprocess.Popen(
            ["open", str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        handler._send_json(200, {"ok": True, "path": str(target)})
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})


def _post_files_exist(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    paths = data.get("paths", [])
    if not isinstance(paths, list):
        handler._send_json(400, {"ok": False, "error": "paths must be a list"})
        return
    result = ctx["workspace_sync_api"].files_exist(paths)
    handler._send_json(200, result)


def _post_files_resolve(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    queries = data.get("queries", [])
    if not isinstance(queries, list):
        handler._send_json(400, {"ok": False, "error": "queries must be a list"})
        return
    try:
        resolved = ctx["workspace_sync_api"].resolve_file_references([str(item or "") for item in queries])
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, {"ok": True, "resolved": resolved})


def _post_open_file_in_editor(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    rel = (data.get("path") or "").strip()
    line = int(data.get("line", 0) or 0)
    diff_mode = bool(data.get("diff"))
    commit_hash = str(data.get("commit_hash") or "").strip()
    allow_native_log_home = bool(data.get("allow_native_log_home"))
    if not rel:
        handler._send_json(400, {"ok": False, "error": "path required"})
        return
    try:
        if diff_mode:
            result = ctx["workspace_sync_api"].open_diff_in_editor(rel, commit_hash=commit_hash)
        else:
            result = ctx["workspace_sync_api"].open_in_editor(rel, line=line, allow_native_log_home=allow_native_log_home)
    except PermissionError:
        handler._send_json(403, {"ok": False, "error": "forbidden"})
        return
    except FileNotFoundError:
        handler._send_json(404, {"ok": False, "error": "file not found"})
        return
    except ValueError as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, result)


def _post_git_restore_file(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    rel = (data.get("path") or "").strip()
    if not rel:
        handler._send_json(400, {"ok": False, "error": "path required"})
        return
    try:
        result = ctx["workspace_sync_api"].git_restore_file(rel_path=rel)
    except PermissionError:
        handler._send_json(403, {"ok": False, "error": "forbidden"})
        return
    except ValueError as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, result)


def _post_send(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    status, body = ctx["send_message_fn"](
        data.get("target", ""),
        data.get("message", ""),
        data.get("reply_to", ""),
        silent=bool(data.get("silent", False)),
        raw=bool(data.get("raw", False)),
    )
    handler._send_json(status, body)


def _post_launch_session(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    targets: list[str] = []
    raw_targets = data.get("targets")
    if isinstance(raw_targets, list):
        targets.extend(str(item).strip() for item in raw_targets if str(item).strip())
    agent = str(data.get("agent") or "").strip()
    if agent:
        targets.append(agent)
    status, body = ctx["launch_session_fn"](targets)
    handler._send_json(status, body)


_POST_ROUTES = {
    "/caffeinate": _post_caffeinate,
    "/auto-mode": _post_auto_mode,
    "/new-chat": _post_new_chat,
    "/add-agent": _post_add_agent,
    "/remove-agent": _post_remove_agent,
    "/log-system": _post_log_system,
    "/upload": _post_upload,
    "/rename-upload": _post_rename_upload,
    "/delete-upload": _post_delete_upload,
    "/open-terminal": _post_open_terminal,
    "/open-finder": _post_open_finder,
    "/files-exist": _post_files_exist,
    "/files-resolve": _post_files_resolve,
    "/open-file-in-editor": _post_open_file_in_editor,
    "/git-restore-file": _post_git_restore_file,
    "/launch-session": _post_launch_session,
    "/send": _post_send,
}


def dispatch_post_write_route(handler, parsed, ctx) -> bool:
    route = _POST_ROUTES.get(parsed.path)
    if route is None:
        return False
    route(handler, parsed, ctx)
    return True
