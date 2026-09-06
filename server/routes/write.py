from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from urllib.parse import unquote as url_unquote

from backend_core.access.settings import hub_settings_path, workspace_upload_dir
from backend_core.tmux.control import SessionControlError, add_agent, remove_agent
from backend_core.tmux.window import tmux_prefix_args
from shortcut_command.execute import run_shortcut_command

_MAX_UPLOAD_BYTES = 100 * 1024 * 1024


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


def _resolve_within_root(path_value: str, *, workspace_root: str) -> Path:
    raw = str(path_value or "").strip()
    if not raw:
        raise ValueError("path required")
    if raw.startswith("~"):
        return Path(raw).expanduser().resolve()
    if os.path.isabs(raw):
        return Path(raw).resolve()
    return (Path(workspace_root).resolve() / raw.lstrip("/")).resolve()


def _post_new_chat(handler, _parsed, ctx) -> None:
    owns_restart = False
    try:
        ok, detail, owns_restart = ctx["queue_chat_restart_fn"]()
        handler._send_json(
            200 if ok else 503,
            {"ok": ok, "error": "" if ok else detail},
        )
        handler.wfile.flush()
    finally:
        if owns_restart:
            ctx["release_chat_restart_fn"]()


def _post_add_agent(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    agent = (data.get("agent") or "").strip().lower()
    if not agent:
        handler._send_json(400, {"ok": False, "error": "agent required"})
        return
    try:
        instance = add_agent(
            session_name=ctx["session_name"],
            agent=agent,
            tmux_socket=str(getattr(ctx["runtime"], "tmux_socket", "") or ""),
        )
    except SessionControlError as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return

    # The mutation above already succeeded (the agent exists in tmux now).
    # Nothing past this point should turn that success into a reported
    # failure - a client that saw a 500 here and retried would add a
    # second agent on top of the one that's already there. Each step below
    # is independent of the others, so each gets its own try/except: one
    # failing must not stop the rest from running.
    warnings: list[str] = []
    try:
        targets = ctx["runtime"].active_agents()
    except Exception as exc:
        targets = []
        warnings.append(str(exc))
    ctx["runtime"].invalidate_payload_cache()
    ctx["runtime"].invalidate_pane_id_cache()
    try:
        ctx["runtime"].on_agent_pane_added(instance)
    except Exception as exc:
        warnings.append(str(exc))
    try:
        ctx["runtime"].refresh_native_log_bindings([instance])
    except Exception as exc:
        warnings.append(str(exc))
    try:
        ctx["runtime"].notify_session_state_changed(["targets", "statuses"], reason="targets-changed")
    except Exception as exc:
        warnings.append(str(exc))
    payload = {
        "ok": True,
        "agent": instance,
        "message": f"Added agent {instance}",
        "targets": targets,
    }
    if warnings:
        payload["warning"] = "; ".join(warnings)
    handler._send_json(200, payload)


def _post_remove_agent(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    agent = (data.get("agent") or "").strip()
    if not agent:
        handler._send_json(400, {"ok": False, "error": "agent required"})
        return
    try:
        instance, _scheduled = remove_agent(
            session_name=ctx["session_name"],
            agent=agent,
            tmux_socket=str(getattr(ctx["runtime"], "tmux_socket", "") or ""),
        )
    except SessionControlError as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return

    # The mutation above already succeeded (the agent is gone from tmux
    # now). Nothing past this point should turn that success into a
    # reported failure. Each step below is independent of the others, so
    # each gets its own try/except: one failing must not stop the rest.
    warnings: list[str] = []
    try:
        targets = ctx["runtime"].active_agents()
    except Exception as exc:
        targets = []
        warnings.append(str(exc))
    ctx["runtime"].invalidate_payload_cache()
    ctx["runtime"].invalidate_pane_id_cache()
    try:
        ctx["runtime"].refresh_native_log_bindings()
    except Exception as exc:
        warnings.append(str(exc))
    try:
        ctx["runtime"].notify_session_state_changed(["targets", "statuses"], reason="targets-changed")
    except Exception as exc:
        warnings.append(str(exc))
    payload = {
        "ok": True,
        "agent": instance,
        "message": f"Removed agent {instance}",
        "targets": targets,
    }
    if warnings:
        payload["warning"] = "; ".join(warnings)
    handler._send_json(200, payload)


def _post_upload(handler, _parsed, ctx) -> None:
    content_type = handler.headers.get("Content-Type", "application/octet-stream")
    raw_name = handler.headers.get("X-Filename", "upload.bin") or "upload.bin"
    try:
        filename = url_unquote(raw_name)
    except Exception:
        filename = raw_name
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    if length > _MAX_UPLOAD_BYTES:
        handler._send_json(413, {"ok": False, "error": f"upload exceeds {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit"})
        return
    data = handler.rfile.read(length)
    upload_dir = workspace_upload_dir(ctx["workspace"])
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


def _post_delete_upload(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    path_rel = data.get("path", "")
    if not path_rel:
        handler._send_json(400, {"ok": False, "error": "path required"})
        return
    try:
        target = _resolve_within_root(path_rel, workspace_root=ctx["workspace"])
    except ValueError as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    try:
        target.unlink(missing_ok=True)
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})
        return
    handler._send_json(200, {"ok": True})


def _switch_front_terminal_client(prefix: list[str], tmux_name: str) -> bool:
    terminal_tty = subprocess.run(
        ["osascript", "-e", 'tell application "Terminal" to get tty of selected tab of front window'],
        capture_output=True,
        text=True,
        check=False,
    )
    tty = (terminal_tty.stdout or "").strip()
    if terminal_tty.returncode != 0 or not tty:
        return False
    clients = subprocess.run(
        [*prefix, "list-clients", "-F", "#{client_tty}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if clients.returncode != 0 or tty not in {(line or "").strip() for line in (clients.stdout or "").splitlines()}:
        return False
    switched = subprocess.run(
        [*prefix, "switch-client", "-c", tty, "-t", tmux_name],
        capture_output=True,
        text=True,
        check=False,
    )
    return switched.returncode == 0


def _raise_terminal_window_for_tty(tty: str) -> bool:
    """Bring the specific Terminal.app window whose selected tab has this tty
    to the front. Plain "activate" only focuses the app, not any particular
    window -- if an unrelated (non-tmux) Terminal window was more recently
    focused, that's what surfaces instead of the one actually attached to
    this tmux session."""
    apple_script = (
        f'tell application "Terminal"\n'
        f"  set targetTTY to {json.dumps(tty)}\n"
        f"  repeat with w in windows\n"
        f"    if (tty of selected tab of w) is targetTTY then\n"
        f"      set index of w to 1\n"
        f"      activate\n"
        f"      return true\n"
        f"    end if\n"
        f"  end repeat\n"
        f"  return false\n"
        f"end tell"
    )
    result = subprocess.run(
        ["osascript", "-e", apple_script],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0 and (result.stdout or "").strip() == "true"


def _open_terminal(handler, ctx, *, agent: str = "", pane_required: bool = False) -> None:
    runtime = ctx["runtime"]
    if not runtime.session_is_active:
        handler._send_json(409, {"ok": False, "error": "tmux session is not active"})
        return
    tmux_name = runtime.tmux_session_name
    if agent:
        try:
            pane_id = runtime.pane_id_for_agent(agent)
        except Exception as exc:
            handler._send_json(500, {"ok": False, "error": str(exc)})
            return
        if not pane_id and pane_required:
            handler._send_json(404, {"ok": False, "error": f"pane not found for {agent}"})
            return
        if pane_id:
            prefix = tmux_prefix_args(ctx["tmux_socket"])
            win_res = subprocess.run(
                [*prefix, "display-message", "-p", "-t", pane_id, "#{window_id}"],
                capture_output=True, text=True, check=False,
            )
            window_id = (win_res.stdout or "").strip()
            if window_id:
                subprocess.run(
                    [*prefix, "select-window", "-t", window_id],
                    capture_output=True, check=False,
                )
            subprocess.run(
                [*prefix, "select-pane", "-t", pane_id],
                capture_output=True, check=False,
            )
            if _switch_front_terminal_client(prefix, tmux_name):
                subprocess.Popen(
                    ["osascript", "-e", 'tell application "Terminal" to activate'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                handler._send_json(200, {"ok": True})
                return
            clients_res = subprocess.run(
                [*prefix, "list-clients", "-t", tmux_name, "-F", "#{client_tty}"],
                capture_output=True, text=True, check=False,
            )
            if clients_res.returncode != 0:
                handler._send_json(500, {"ok": False, "error": "could not determine tmux session attachment"})
                return
            attached_ttys = [line.strip() for line in (clients_res.stdout or "").splitlines() if line.strip()]
            if attached_ttys:
                if not _raise_terminal_window_for_tty(attached_ttys[0]):
                    # The attached client's window vanished from Terminal's
                    # own list (rare) -- fall back to a plain activate rather
                    # than silently doing nothing.
                    subprocess.Popen(
                        ["osascript", "-e", 'tell application "Terminal" to activate'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                handler._send_json(200, {"ok": True})
                return
    try:
        prefix = tmux_prefix_args(ctx["tmux_socket"])
        socket_flag = prefix[1]
        cols, rows = 200, 40
        try:
            size_result = subprocess.run(
                [
                    *prefix,
                    "display-message",
                    "-p",
                    "-t",
                    f"={tmux_name}:0",
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
            f"{shlex.quote(ctx['tmux_socket'])} attach-session -t {shlex.quote(tmux_name)}"
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


def _post_open_terminal(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    _open_terminal(handler, ctx, agent=str((data or {}).get("agent") or "").strip())


def _post_open_pane(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    if str(data.get("client") or "").strip().lower() == "mobile":
        handler._send_json(403, {"ok": False, "error": "open-pane is available on desktop only"})
        return
    runtime = ctx["runtime"]
    raw_targets = [item.strip() for item in str(data.get("target") or "").split(",") if item.strip()]
    resolved = runtime.resolve_target_agents(",".join(raw_targets)) if raw_targets else []
    agents = [item for item in resolved if item]
    if len(agents) != 1:
        handler._send_json(400, {"ok": False, "error": "select exactly one target"})
        return
    _open_terminal(handler, ctx, agent=agents[0], pane_required=True)


def _post_open_finder(handler, _parsed, ctx) -> None:
    workspace = str(ctx["workspace"] or "").strip()
    if not workspace:
        handler._send_json(400, {"ok": False, "error": "workspace unavailable"})
        return
    try:
        target = Path(workspace).resolve()
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


def _post_open_shell(handler, _parsed, ctx) -> None:
    workspace = str(ctx["workspace"] or "").strip()
    if not workspace:
        handler._send_json(400, {"ok": False, "error": "workspace unavailable"})
        return
    try:
        target = Path(workspace).resolve()
        if not target.exists():
            handler._send_json(404, {"ok": False, "error": "workspace not found"})
            return
        apple_script = (
            f'tell application "Terminal"\n'
            f'  do script "cd " & quoted form of {json.dumps(str(target))}\n'
            f"  activate\n"
            f"end tell"
        )
        subprocess.Popen(
            ["osascript", "-e", apple_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        handler._send_json(200, {"ok": True, "path": str(target)})
    except Exception as exc:
        handler._send_json(500, {"ok": False, "error": str(exc)})


def _post_open_settings_file(handler, _parsed, ctx) -> None:
    try:
        target = hub_settings_path()
        if not target.exists():
            handler._send_json(404, {"ok": False, "error": "settings file not found"})
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


def _post_open_file(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    rel = (data.get("path") or "").strip()
    if not rel:
        handler._send_json(400, {"ok": False, "error": "path required"})
        return
    try:
        result = ctx["workspace_sync_api"].open_with_default_app(rel)
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


def _post_reveal_file(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    rel = (data.get("path") or "").strip()
    if not rel:
        handler._send_json(400, {"ok": False, "error": "path required"})
        return
    try:
        result = ctx["workspace_sync_api"].reveal_in_finder(rel)
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


def _post_open_diff(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    rel = (data.get("path") or "").strip()
    if not rel:
        handler._send_json(400, {"ok": False, "error": "path required"})
        return
    try:
        result = ctx["workspace_sync_api"].open_diff_tool(rel)
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


def _run_nativelog_command(ctx, *, target: str) -> tuple[int, dict]:
    rt = ctx["runtime"]
    workspace_sync_api = ctx["workspace_sync_api"]
    raw_targets = [t.strip() for t in target.split(",") if t.strip()] if target.strip() else []
    resolved = [t for t in rt.resolve_target_agents(raw_targets[0]) if t] if raw_targets else []
    if not resolved:
        msg = "target is required"
        return 400, {"ok": False, "error": msg, "status_message": msg}
    agent = resolved[0]
    watched = rt.native_log_watched_paths()
    path = (watched.get(agent) or "").strip()
    if not path:
        msg = f"native log path not found for {agent}"
        return 404, {"ok": False, "error": msg, "status_message": msg}
    try:
        workspace_sync_api.reveal_in_finder(path)
    except FileNotFoundError:
        msg = f"native log file not found: {path}"
        return 404, {"ok": False, "error": msg, "status_message": msg}
    except Exception as exc:
        msg = str(exc)
        return 500, {"ok": False, "error": msg, "status_message": msg}
    return 200, {"ok": True, "status_message": f"revealed native log for {agent} in Finder"}


def _post_native_log(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    if str(data.get("client") or "").strip().lower() == "mobile":
        handler._send_json(403, {"ok": False, "error": "nativelog is available on desktop only"})
        return
    status, body = _run_nativelog_command(ctx, target=str(data.get("target") or ""))
    handler._send_json(status, body)


def _post_shortcut_command(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    command_id = str(data.get("command_id") or "")
    status, body = run_shortcut_command(
        ctx["runtime"],
        command_id=command_id,
        arg=str(data.get("arg") or ""),
        target=str(data.get("target") or ""),
    )
    handler._send_json(status, body)


def _post_send(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    status, body = ctx["send_message_fn"](
        data.get("target", ""),
        data.get("message", ""),
        data.get("client"),
    )
    handler._send_json(status, body)


def _post_agent_running(handler, _parsed, ctx) -> None:
    data, err = _read_json_body(handler)
    if err:
        handler._send_json(400, {"ok": False, "error": err})
        return
    requested = data.get("targets")
    if not isinstance(requested, list):
        handler._send_json(400, {"ok": False, "error": "targets must be an array"})
        return
    active = set(ctx["runtime"].active_agents())
    targets = [str(item or "").strip() for item in requested]
    if not targets or any(not target or target not in active for target in targets):
        handler._send_json(400, {"ok": False, "error": "targets must name active agents"})
        return
    ctx["runtime"].mark_agents_running(list(dict.fromkeys(targets)))
    handler._send_json(200, {"ok": True})


_POST_ROUTES = {
    "/new-chat": _post_new_chat,
    "/add-agent": _post_add_agent,
    "/remove-agent": _post_remove_agent,
    "/upload": _post_upload,
    "/delete-upload": _post_delete_upload,
    "/open-terminal": _post_open_terminal,
    "/open-pane": _post_open_pane,
    "/open-finder": _post_open_finder,
    "/open-shell": _post_open_shell,
    "/open-settings-file": _post_open_settings_file,
    "/files-exist": _post_files_exist,
    "/files-resolve": _post_files_resolve,
    "/open-file": _post_open_file,
    "/reveal-file": _post_reveal_file,
    "/open-diff": _post_open_diff,
    "/shortcut-command": _post_shortcut_command,
    "/native-log": _post_native_log,
    "/agent-running": _post_agent_running,
    "/send": _post_send,
}


def dispatch_post_write_route(handler, parsed, ctx) -> bool:
    route = _POST_ROUTES.get(parsed.path)
    if route is None:
        return False
    route(handler, parsed, ctx)
    return True
