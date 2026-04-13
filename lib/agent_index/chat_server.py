"""Chat server entry module extracted from bin/agent-index."""

from __future__ import annotations

import json
import logging
import os
import queue
import ssl
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from agent_index import chat_git
from agent_index.chat_assets import (
    CHAT_APP_SCRIPT_ASSET,
    CHAT_HTML,
    CHAT_MAIN_STYLE_ASSET,
    chat_app_script_asset,
    chat_main_style_asset,
    render_chat_html,
    render_pane_trace_popup_html,
)
from agent_index.chat_core import ChatRuntime
from agent_index.chat_delivery_core import pending_launch_preflight
from agent_index.chat_routes_assets import dispatch_get_assets_route
from agent_index.chat_routes_push import dispatch_get_push_route, dispatch_post_push_route
from agent_index.chat_routes_read import dispatch_get_read_route
from agent_index.chat_routes_write import dispatch_post_write_route
from agent_index.chat_sync_loop_core import sync_agent_assistant_messages
from agent_index.chat_asset_runtime_core import ChatAssetRuntime
from agent_index.file_core import FileRuntime
from agent_index.jsonl_append import append_jsonl_entry
from agent_index.push_core import SessionPushMonitor, remove_push_subscription, upsert_push_subscription, vapid_public_key

_PWA_STATIC_ROUTES = {
    "/pwa-icon-192.png": ("icon-192.png", "image/png", "public, max-age=3600"),
    "/pwa-icon-512.png": ("icon-512.png", "image/png", "public, max-age=3600"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png", "public, max-age=3600"),
    "/service-worker.js": ("service-worker.js", "application/javascript; charset=utf-8", "no-store"),
}


def _not_initialized(*_args, **_kwargs):
    raise RuntimeError("chat_server.initialize_from_argv() must run before serving requests")


_initialized = False
index_path = Path()
commit_state_path = Path()
limit = 0
filter_agent = ""
session_name = ""
follow_mode = False
port = 0
agent_send_path = ""
workspace = ""
log_dir = ""
targets: list[str] = []
tmux_socket = ""
hub_port = 0
PUBLIC_HOST = ""
PUBLIC_HUB_PORT = 443
_repo_root = Path()
runtime = None
_PWA_STATIC_DIR = Path()
server_instance = ""
load_chat_settings = _not_initialized
chat_font_settings_inline_style = _not_initialized
payload = _not_initialized
append_system_entry = _not_initialized
caffeinate_status = _not_initialized
caffeinate_toggle = _not_initialized
auto_mode_status = _not_initialized
send_message = _not_initialized
agent_statuses = _not_initialized
file_runtime = None
HTML = CHAT_HTML
asset_runtime = None
push_monitor = None
send_queue = None
send_queue_thread = None

_QUEUED_SEND_CONTROL_MESSAGES = {"save", "interrupt", "ctrlc", "enter", "restart", "resume"}


def _build_outbound_user_entry(*, targets: list[str], message: str, reply_to: str = "") -> dict:
    payload = f"[From: User]\n{message}"
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session": session_name,
        "sender": "user",
        "targets": list(targets),
        "message": payload,
        "msg_id": uuid.uuid4().hex[:12],
    }
    if reply_to:
        entry["reply_to"] = reply_to
        reply_preview = runtime._reply_preview_for(reply_to)
        if reply_preview:
            entry["reply_preview"] = reply_preview
    return entry


def _send_is_queueable(target: str, message: str, *, silent: bool = False, raw: bool = False) -> list[str] | None:
    if runtime is None or not (runtime.session_is_active or runtime.launch_pending()):
        return None
    if silent or raw:
        return None
    normalized_target = str(target or "").strip()
    normalized_message = str(message or "").strip()
    if not normalized_target or not normalized_message:
        return None
    if normalized_message in _QUEUED_SEND_CONTROL_MESSAGES:
        return None
    if runtime._parse_pane_direct_command(normalized_message):
        return None
    resolved_targets = runtime.resolve_target_agents(normalized_target)
    if not resolved_targets or resolved_targets == ["user"] or "user" in resolved_targets:
        return None
    return list(resolved_targets)


def _queued_send_worker() -> None:
    while True:
        job = send_queue.get()
        try:
            status, body = runtime.send_message(
                job.get("target", ""),
                job.get("message", ""),
                job.get("reply_to", ""),
                silent=bool(job.get("silent", False)),
                raw=bool(job.get("raw", False)),
                append_entry=False,
            )
            if status != 200 or not body.get("ok"):
                error = str(body.get("error") or "send failed").strip() or "send failed"
                runtime.append_system_entry(
                    f"Send failed: {error}",
                    kind="send-error",
                    related_msg_id=job.get("msg_id", ""),
                    failed_targets=list(job.get("targets") or []),
                )
        except Exception as exc:
            runtime.append_system_entry(
                f"Send failed: {exc}",
                kind="send-error",
                related_msg_id=job.get("msg_id", ""),
                failed_targets=list(job.get("targets") or []),
            )
        finally:
            send_queue.task_done()


def _send_or_enqueue_message(
    target: str,
    message: str,
    reply_to: str = "",
    silent: bool = False,
    raw: bool = False,
) -> tuple[int, dict]:
    queue_targets = _send_is_queueable(target, message, silent=silent, raw=raw)
    if not queue_targets:
        return runtime.send_message(
            target,
            message,
            reply_to,
            silent=silent,
            raw=raw,
        )
    queue_launch_pending = bool(runtime.launch_pending())
    if queue_launch_pending:
        ready, payload = pending_launch_preflight(runtime.workspace, queue_targets)
        if not ready:
            return 400, payload
    entry = _build_outbound_user_entry(targets=queue_targets, message=message, reply_to=reply_to)
    append_jsonl_entry(runtime.index_path, entry)
    send_queue.put(
        {
            "target": ",".join(queue_targets),
            "targets": queue_targets,
            "message": str(message or "").strip(),
            "reply_to": str(reply_to or "").strip(),
            "silent": False,
            "raw": False,
            "msg_id": entry["msg_id"],
        }
    )
    return 200, {
        "ok": True,
        "queued": True,
        "launch_pending": queue_launch_pending,
        "msg_id": entry["msg_id"],
        "targets": queue_targets,
    }


def _clean_env():
    env = os.environ.copy()
    env["MULTIAGENT_AGENT_NAME"] = "user"
    return env


def initialize_from_argv(argv: list[str] | None = None) -> None:
    global _initialized
    global index_path, commit_state_path, limit, filter_agent, session_name, follow_mode
    global port, agent_send_path, workspace, log_dir, targets, tmux_socket, hub_port
    global PUBLIC_HOST, PUBLIC_HUB_PORT, _repo_root, runtime
    global _PWA_STATIC_DIR, server_instance, load_chat_settings, chat_font_settings_inline_style
    global payload, append_system_entry, caffeinate_status, caffeinate_toggle, auto_mode_status
    global send_message, agent_statuses, file_runtime, HTML, asset_runtime, push_monitor
    global send_queue, send_queue_thread

    if _initialized:
        return

    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 12:
        raise SystemExit(
            "usage: python -m agent_index.chat_server "
            "<index_path> <limit> <filter_agent> <session_name> <follow_mode> "
            "<port> <agent_send_path> <workspace> <log_dir> <targets_csv> <tmux_socket> <hub_port>"
        )

    index_path = Path(argv[0])
    commit_state_path = index_path.parent / ".agent-index-commit-state.json"
    limit = int(argv[1])
    filter_agent = argv[2].strip().lower()
    session_name = argv[3]
    follow_mode = argv[4] == "1"
    port = int(argv[5])
    agent_send_path = argv[6]
    workspace = argv[7]
    log_dir = argv[8]
    targets = [item for item in argv[9].split(",") if item]
    tmux_socket = argv[10]
    hub_port = int(argv[11])
    PUBLIC_HOST = (os.environ.get("MULTIAGENT_PUBLIC_HOST", "") or "").strip().rstrip(".").lower()
    PUBLIC_HUB_PORT = int(os.environ.get("MULTIAGENT_PUBLIC_HUB_PORT", "443") or "443")

    _repo_root = Path(agent_send_path).parent.parent
    runtime = ChatRuntime(
        index_path=index_path,
        limit=limit,
        filter_agent=filter_agent,
        session_name=session_name,
        follow_mode=follow_mode,
        port=port,
        agent_send_path=agent_send_path,
        workspace=workspace,
        log_dir=log_dir,
        targets=targets,
        tmux_socket=tmux_socket,
        hub_port=hub_port,
        repo_root=_repo_root,
        session_is_active=(os.environ.get("SESSION_IS_ACTIVE", "0") == "1"),
    )

    _PWA_STATIC_DIR = _repo_root / "lib" / "agent_index" / "static" / "pwa"
    server_instance = runtime.server_instance
    load_chat_settings = runtime.load_chat_settings
    chat_font_settings_inline_style = runtime.chat_font_settings_inline_style
    payload = runtime.payload
    append_system_entry = runtime.append_system_entry
    caffeinate_status = runtime.caffeinate_status
    caffeinate_toggle = runtime.caffeinate_toggle
    auto_mode_status = runtime.auto_mode_status
    send_message = _send_or_enqueue_message
    agent_statuses = runtime.agent_statuses
    file_runtime = FileRuntime(
        workspace=workspace,
        allowed_roots=[index_path.parent],
        repo_root=_repo_root,
    )
    asset_runtime = ChatAssetRuntime(
        repo_root=_repo_root,
    )
    HTML = render_chat_html(
        icon_data_uris=asset_runtime.icon_data_uris,
        server_instance=server_instance,
        hub_port=hub_port,
        chat_settings=load_chat_settings(),
        agent_font_mode_inline_style=chat_font_settings_inline_style,
        follow="0",
        chat_base_path="",
    )
    push_monitor = SessionPushMonitor(
        repo_root=_repo_root,
        session_name=session_name,
        workspace=workspace,
        index_path=index_path,
        settings_loader=load_chat_settings,
    )
    chat_git.configure(
        workspace=workspace,
        repo_root=_repo_root,
        index_path=index_path,
        runtime=runtime,
    )
    threading.Thread(target=_periodic_jsonl_sync, daemon=True, name="jsonl-sync").start()
    threading.Thread(target=push_monitor.run_forever, daemon=True, name="push-monitor").start()
    send_queue = queue.Queue()
    send_queue_thread = threading.Thread(target=_queued_send_worker, daemon=True, name="send-queue")
    send_queue_thread.start()
    _initialized = True


def _pwa_asset_url(path: str, base_path: str = "") -> str:
    prefix = (base_path or "").rstrip("/")
    return f"{prefix}{path}" if prefix else path


def _pwa_icon_entries(base_path: str = "") -> list[dict[str, str]]:
    return [
        {
            "src": _pwa_asset_url("/pwa-icon-192.png", base_path),
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": _pwa_asset_url("/pwa-icon-512.png", base_path),
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any",
        },
    ]


def _serve_pwa_static(handler, path: str) -> bool:
    spec = _PWA_STATIC_ROUTES.get(path)
    if spec is None:
        return False
    filename, content_type, cache_control = spec
    try:
        body = (_PWA_STATIC_DIR / filename).read_bytes()
    except Exception:
        handler.send_response(404)
        handler.end_headers()
        return True
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", cache_control)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
    return True


_JSONL_SYNC_INTERVAL_SEC = 1.0
_SYNC_STATE_HEARTBEAT_SEC = 30.0


def _periodic_jsonl_sync():
    """Independently sync agent messages to JSONL, decoupled from UI polling.

    Runs in its own daemon thread. Resolves native log paths via tmux/lsof
    and calls the appropriate _sync_* method for each agent every ~1 second.
    This ensures JSONL append happens regardless of browser tab state.

    Uses an advisory flock on a per-session lock file so that multiple
    chat_server processes for the same session never sync simultaneously.
    If the lock is already held by another process, this tick is skipped.
    """
    import fcntl

    time.sleep(1)
    while True:
        try:
            if not runtime.session_is_active:
                time.sleep(_JSONL_SYNC_INTERVAL_SEC)
                continue

            lock_fd = None
            try:
                lock_fd = open(runtime.sync_lock_path, "w")
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, IOError):
                if lock_fd:
                    lock_fd.close()
                time.sleep(_JSONL_SYNC_INTERVAL_SEC)
                continue

            try:
                try:
                    active_agents = runtime.active_agents()
                except Exception:
                    active_agents = []
                if active_agents:
                    try:
                        for agent in active_agents:
                            runtime._first_seen_for_agent(agent)
                    except Exception:
                        pass
                    try:
                        runtime.prune_sync_claims_to_active_agents(active_agents)
                    except Exception:
                        pass
                    try:
                        runtime.apply_recent_targeted_claim_handoffs(active_agents)
                    except Exception:
                        pass
                for agent in active_agents:
                    try:
                        sync_agent_assistant_messages(runtime, agent)
                    except Exception:
                        pass
                try:
                    runtime.maybe_heartbeat_sync_state(interval_seconds=_SYNC_STATE_HEARTBEAT_SEC)
                except Exception:
                    pass
            finally:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(_JSONL_SYNC_INTERVAL_SEC)


chat_restart_pending = False
chat_restart_lock = threading.Lock()
server = None


def queue_chat_restart():
    global chat_restart_pending
    with chat_restart_lock:
        if chat_restart_pending:
            return True, "restart already pending"
        chat_restart_pending = True

    bin_dir = Path(agent_send_path).parent
    script_path = str(bin_dir / "agent-index")
    restart_helper = (
        "import os, signal, socket, subprocess, sys, time\n"
        "script_path, port, repo_root, session_name = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]\n"
        "def port_open():\n"
        "    try:\n"
        "        with socket.create_connection(('127.0.0.1', port), timeout=0.2):\n"
        "            return True\n"
        "    except OSError:\n"
        "        return False\n"
        "for _ in range(50):\n"
        "    if not port_open():\n"
        "        break\n"
        "    time.sleep(0.1)\n"
        "if port_open():\n"
        "    try:\n"
        "        result = subprocess.run(['lsof', '-nP', f'-tiTCP:{port}', '-sTCP:LISTEN'], capture_output=True, text=True, timeout=1, check=False)\n"
        "        pids = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]\n"
        "    except Exception:\n"
        "        pids = []\n"
        "    for pid in pids:\n"
        "        try:\n"
        "            os.kill(pid, signal.SIGTERM)\n"
        "        except Exception:\n"
        "            pass\n"
        "    for _ in range(20):\n"
        "        if not port_open():\n"
        "            break\n"
        "        time.sleep(0.1)\n"
        "    if port_open():\n"
        "        for pid in pids:\n"
        "            try:\n"
        "                os.kill(pid, signal.SIGKILL)\n"
        "            except Exception:\n"
        "                pass\n"
        "        for _ in range(20):\n"
        "            if not port_open():\n"
        "                break\n"
        "            time.sleep(0.1)\n"
        "env = os.environ.copy()\n"
        "env['MULTIAGENT_AGENT_NAME'] = 'user'\n"
        "subprocess.Popen(\n"
        "    [script_path, '--follow', '--chat', '--no-open', '--session', session_name],\n"
        "    cwd=repo_root,\n"
        "    env=env,\n"
        "    stdin=subprocess.DEVNULL,\n"
        "    stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL,\n"
        "    start_new_session=True,\n"
        "    close_fds=True,\n"
        ")\n"
    )
    try:
        subprocess.Popen(
            [sys.executable, "-c", restart_helper, script_path, str(port), str(_repo_root), session_name],
            cwd=str(_repo_root),
            env=_clean_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as exc:
        with chat_restart_lock:
            chat_restart_pending = False
        return False, str(exc)

    def worker():
        time.sleep(0.15)
        if server is None:
            return
        try:
            server.shutdown()
        finally:
            try:
                server.server_close()
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True, name="chat-restart").start()
    return True, ""


def _route_context() -> dict:
    return {
        "session_name": session_name,
        "server_instance": server_instance,
        "runtime": runtime,
        "workspace": workspace,
        "session_dir": str(index_path.parent),
        "log_dir": log_dir,
        "port": port,
        "hub_port": hub_port,
        "tmux_socket": tmux_socket,
        "agent_send_path": agent_send_path,
        "repo_root": _repo_root,
        "public_host": PUBLIC_HOST,
        "public_hub_port": PUBLIC_HUB_PORT,
        "payload_fn": payload,
        "append_system_entry_fn": append_system_entry,
        "caffeinate_status_fn": caffeinate_status,
        "caffeinate_toggle_fn": caffeinate_toggle,
        "auto_mode_status_fn": auto_mode_status,
        "send_message_fn": send_message,
        "agent_statuses_fn": agent_statuses,
        "file_runtime": file_runtime,
        "asset_runtime": asset_runtime,
        "push_monitor": push_monitor,
        "load_chat_settings_fn": load_chat_settings,
        "chat_font_settings_inline_style_fn": chat_font_settings_inline_style,
        "pwa_asset_url_fn": _pwa_asset_url,
        "pwa_icon_entries_fn": _pwa_icon_entries,
        "serve_pwa_static_fn": _serve_pwa_static,
        "chat_app_script_asset": CHAT_APP_SCRIPT_ASSET,
        "chat_main_style_asset": CHAT_MAIN_STYLE_ASSET,
        "chat_app_script_asset_fn": chat_app_script_asset,
        "chat_main_style_asset_fn": chat_main_style_asset,
        "render_chat_html_fn": render_chat_html,
        "render_pane_trace_popup_html_fn": render_pane_trace_popup_html,
        "vapid_public_key_fn": vapid_public_key,
        "upsert_push_subscription_fn": upsert_push_subscription,
        "remove_push_subscription_fn": remove_push_subscription,
        "clean_env_fn": _clean_env,
        "queue_chat_restart_fn": queue_chat_restart,
        "chat_git_module": chat_git,
    }


class Handler(BaseHTTPRequestHandler):
    _GET_ROUTE_DISPATCHERS = (
        dispatch_get_assets_route,
        dispatch_get_push_route,
        dispatch_get_read_route,
    )
    _POST_ROUTE_DISPATCHERS = (
        dispatch_post_push_route,
        dispatch_post_write_route,
    )

    def log_message(self, format, *args):
        return

    def _send_json(self, status, body):
        payload_bytes = json.dumps(body, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def _dispatch_routes(self, parsed, dispatchers, ctx) -> bool:
        for dispatch in dispatchers:
            if dispatch(self, parsed, ctx):
                return True
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        if self._dispatch_routes(parsed, self._GET_ROUTE_DISPATCHERS, _route_context()):
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if self._dispatch_routes(parsed, self._POST_ROUTE_DISPATCHERS, _route_context()):
            return
        self.send_response(404)
        self.end_headers()


def _kill_stale_sync_processes(index_path_str: str) -> None:
    """Kill other chat_server processes syncing the same JSONL file.

    When a new chat_server starts for a session, any leftover process from a
    previous launch (e.g. after a Hub reload that spawned a new server without
    cleanly stopping the old one) will continue its sync loop and produce
    duplicate JSONL entries. This function finds those processes and kills them.
    """
    import signal

    my_pid = os.getpid()
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"agent_index.chat_server.*{index_path_str}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        for line in result.stdout.strip().splitlines():
            pid_str = line.strip()
            if not pid_str:
                continue
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            if pid == my_pid:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                logging.info("Killed stale chat_server PID %d for %s", pid, index_path_str)
            except OSError:
                pass
    except Exception as exc:
        logging.debug("_kill_stale_sync_processes: %s", exc)


def main(argv: list[str] | None = None) -> None:
    global server

    initialize_from_argv(argv)
    _kill_stale_sync_processes(str(index_path))

    cert_file = os.environ.get("MULTIAGENT_CERT_FILE", "")
    key_file = os.environ.get("MULTIAGENT_KEY_FILE", "")
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    if cert_file and key_file:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    else:
        scheme = "http"
    print(f"{scheme}://127.0.0.1:{port}/?follow={'1' if follow_mode else '0'}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
