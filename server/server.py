from __future__ import annotations

import json
import logging
import os
import queue
import select
import ssl
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from hub_backend.presentation.chat.assets import render_chat_html
from server.runtime import ChatRuntime
from server.chat_process import launch_chat_server, wait_for_chat_server
from server.hub_session_events import notify_hub_session_messages_changed
from server.routes.assets import dispatch_get_assets_route
from server.routes.read import dispatch_get_read_route
from server.routes.write import dispatch_post_write_route
from server.asset_runtime import ChatAssetRuntime
from backend_core.access.pwa import pwa_icon_entries
from hub_backend.server_helpers import (
    pwa_asset_url as _pwa_asset_url_impl,
    pwa_asset_version as _pwa_asset_version_impl,
)
from backend_core.access.chat_server import read_chat_server_state
from backend_core.access.settings import (
    local_bind_host,
    local_bind_scheme,
    pwa_https_enabled,
    workspace_chat_port,
)
from workspace_sync.api import WorkspaceSyncApi

DEFAULT_HUB_PORT = 8788
DEFAULT_TMUX_SOCKET = "agent-window"
RELOAD_RUNNING_AGENTS_ENV = "AGENT_WINDOW_RELOAD_RUNNING_AGENTS"

_PWA_STATIC_ROUTES = {
    "/pwa-icon-192.png": ("icon-192.png", "image/png", "public, max-age=3600"),
    "/pwa-icon-512.png": ("icon-512.png", "image/png", "public, max-age=3600"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png", "public, max-age=3600"),
    "/service-worker.js": ("service-worker.js", "application/javascript; charset=utf-8", "no-store"),
}


def _not_initialized(*_args, **_kwargs):
    raise RuntimeError("chat_server.initialize_from_argv() must run before serving requests")


_initialized = False
port = 0
workspace = ""
tmux_socket = ""
hub_port = 0
PUBLIC_HOST = ""
PUBLIC_HUB_PORT = 443
_repo_root = Path()
runtime = None
_PWA_STATIC_DIR = Path()
server_instance = ""
payload = _not_initialized
send_message = _not_initialized
workspace_sync_api = None
asset_runtime = None
send_queue = None
send_queue_thread = None


def _message_index_watcher() -> None:
    while True:
        fd = None
        try:
            current_log_path = runtime.log_path
            kq = select.kqueue()
            fd = os.open(str(current_log_path), os.O_RDONLY)
            ev = select.kevent(
                fd,
                filter=select.KQ_FILTER_VNODE,
                flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                fflags=select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND | select.KQ_NOTE_RENAME | select.KQ_NOTE_DELETE,
            )
            kq.control([ev], 0)
            while True:
                events = kq.control(None, 4, None)
                for event in events:
                    if event.fflags & (select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND):
                        if runtime is not None:
                            runtime.notify_session_state_changed(["messages", "statuses"], reason="messages")
                            try:
                                notify_hub_session_messages_changed(
                                    hub_port,
                                    scheme="https" if pwa_https_enabled() else "http",
                                )
                            except Exception as exc:
                                logging.warning("Hub message notification failed: %s", exc)
                    if event.fflags & (select.KQ_NOTE_RENAME | select.KQ_NOTE_DELETE):
                        raise OSError("message log path changed")
        except Exception as exc:
            logging.error("message index watcher error: %s", exc)
            time.sleep(1.0)
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass


def _queued_send_worker() -> None:
    while True:
        job = send_queue.get()
        try:
            status, body = runtime.send_message(
                job.get("target", ""),
                job.get("message", ""),
                append_entry=False,
            )
            if status != 200 or not body.get("ok"):
                error = str(body.get("error") or "send failed").strip() or "send failed"
                runtime.append_system_entry(
                    f"Send failed: {error}",
                    kind="send-error",
                    failed_targets=list(job.get("targets") or []),
                )
        except Exception as exc:
            runtime.append_system_entry(
                f"Send failed: {exc}",
                kind="send-error",
                failed_targets=list(job.get("targets") or []),
            )
        finally:
            send_queue.task_done()


def _send_or_enqueue_message(
    target: str,
    message: str,
    client: str | None = None,
) -> tuple[int, dict]:
    """Append the entry and ack immediately; deliver to tmux in the background.

    Whether the message actually reaches the pane is a separate concern from
    whether the UI reflects it: delivery runs on send_queue/_queued_send_worker
    and reports failure later as a system entry, never blocking this return.
    """
    normalized_message = str(message or "").strip()
    if not normalized_message:
        return 400, {"ok": False, "error": "message is required"}
    normalized_target = str(target or "").strip()
    resolved_targets = runtime.resolve_target_agents(normalized_target) if normalized_target else []
    if not resolved_targets or resolved_targets == ["user"]:
        entry = runtime.append_user_entry(normalized_message, targets=["user"], client=client)
        return 200, {"ok": True, "mode": "note", "entry": entry}
    if "user" in resolved_targets:
        return 400, {"ok": False, "error": 'target "user" cannot be combined with other targets'}
    entry = runtime.append_user_entry(normalized_message, targets=resolved_targets, client=client)
    send_queue.put(
        {
            "target": ",".join(resolved_targets),
            "targets": resolved_targets,
            "message": normalized_message,
        }
    )
    return 200, {"ok": True, "entry": entry}


def _clean_env():
    env = os.environ.copy()
    env["AGENT_WINDOW_AGENT_NAME"] = "user"
    if runtime is None:
        raise RuntimeError("chat runtime is unavailable during reload")
    env[RELOAD_RUNNING_AGENTS_ENV] = json.dumps(runtime.running_agents_for_reload())
    return env


def initialize_from_argv(argv: list[str] | None = None) -> None:
    global _initialized
    global port, workspace, tmux_socket, hub_port
    global PUBLIC_HOST, PUBLIC_HUB_PORT, _repo_root, runtime
    global _PWA_STATIC_DIR, server_instance
    global payload
    global send_message, asset_runtime
    global send_queue, send_queue_thread, workspace_sync_api

    if _initialized:
        return

    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        raise SystemExit("usage: python -m server.server <workspace>")

    workspace = str(argv[0] or "").strip()
    if not workspace:
        raise SystemExit("usage: python -m server.server <workspace>")

    _repo_root = Path(__file__).resolve().parent.parent
    port = workspace_chat_port(workspace)
    tmux_socket = (os.environ.get("AGENT_WINDOW_TMUX_SOCKET") or DEFAULT_TMUX_SOCKET).strip()
    hub_port = int(os.environ.get("AGENT_INDEX_HUB_PORT") or DEFAULT_HUB_PORT)
    PUBLIC_HOST = (os.environ.get("AGENT_WINDOW_PUBLIC_HOST", "") or "").strip().rstrip(".").lower()
    PUBLIC_HUB_PORT = int(os.environ.get("AGENT_WINDOW_PUBLIC_HUB_PORT", "443") or "443")
    reload_running_raw = os.environ.pop(RELOAD_RUNNING_AGENTS_ENV, "")
    reload_running_agents = json.loads(reload_running_raw) if reload_running_raw else []
    if not isinstance(reload_running_agents, list) or any(
        not isinstance(agent, str) or not agent for agent in reload_running_agents
    ):
        raise RuntimeError(f"invalid {RELOAD_RUNNING_AGENTS_ENV}")

    runtime = ChatRuntime(
        port=port,
        workspace=workspace,
        tmux_socket=tmux_socket,
        hub_port=hub_port,
        repo_root=_repo_root,
        initial_running_agents=reload_running_agents,
    )

    _PWA_STATIC_DIR = _repo_root / "apps" / "shared" / "pwa"
    server_instance = runtime.server_instance
    payload = runtime.payload
    send_message = _send_or_enqueue_message
    workspace_sync_api = WorkspaceSyncApi(
        workspace=workspace,
        allowed_roots_fn=lambda: [runtime.session_dir],
        repo_root=_repo_root,
        runtime=runtime,
    )
    asset_runtime = ChatAssetRuntime(
        repo_root=_repo_root,
    )
    runtime.start_native_log_sync()
    try:
        runtime.ensure_commit_announcements()
    except Exception as exc:
        logging.error("commit announcement startup refresh failed: %s", exc)
    threading.Thread(
        target=_message_index_watcher,
        daemon=True,
        name="message-index-watch",
    ).start()
    send_queue = queue.Queue()
    send_queue_thread = threading.Thread(target=_queued_send_worker, daemon=True, name="send-queue")
    send_queue_thread.start()
    _initialized = True


def _pwa_asset_version(path: str) -> str:
    return _pwa_asset_version_impl(
        path,
        pwa_asset_version_overrides={},
        pwa_static_routes=_PWA_STATIC_ROUTES,
        pwa_static_dir=_PWA_STATIC_DIR,
        fallback_file=__file__,
    )


def _pwa_asset_url(path: str, base_path: str = "", *, bust: bool = False) -> str:
    return _pwa_asset_url_impl(
        path,
        base_path=base_path,
        bust=bust,
        pwa_asset_version_fn=_pwa_asset_version,
    )


def _pwa_icon_entries(base_path: str = "") -> list[dict[str, str]]:
    return pwa_icon_entries(
        base_path=base_path,
        pwa_asset_url_fn=lambda path, *, base_path="", bust=False: _pwa_asset_url(path, base_path, bust=bust),
    )


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


chat_restart_pending = False
chat_restart_lock = threading.Lock()
chat_restart_release_event = threading.Event()
server = None


def queue_chat_restart():
    global chat_restart_pending
    current_workspace = str(workspace or "").strip()
    if not current_workspace:
        return False, "workspace unavailable", False

    with chat_restart_lock:
        if chat_restart_pending:
            return False, "restart already pending", False
        chat_restart_pending = True

    done = threading.Event()
    result = {"ok": False}

    def worker():
        try:
            env = _clean_env()
            if server is not None:
                server.shutdown()
                server.server_close()
            process = launch_chat_server(current_workspace, env=env)
            expected_workspace = str(Path(current_workspace).expanduser().resolve())

            def _ready() -> bool:
                state = read_chat_server_state(port)
                reported_workspace = str((state or {}).get("workspace") or "").strip()
                return bool(
                    reported_workspace
                    and str(Path(reported_workspace).expanduser().resolve()) == expected_workspace
                )

            result["ok"] = wait_for_chat_server(
                process,
                _ready,
            )
        except OSError:
            result["ok"] = False
        finally:
            done.set()

    threading.Thread(target=worker, daemon=True, name="chat-restart").start()
    done.wait()
    return result["ok"], "" if result["ok"] else "reload failed", True


def release_chat_restart() -> None:
    chat_restart_release_event.set()


def _route_context() -> dict:
    current_session_name, _current_log_path = runtime.session_binding_snapshot()
    return {
        "session_name": current_session_name,
        "server_instance": server_instance,
        "runtime": runtime,
        "workspace": workspace,
        "hub_port": hub_port,
        "tmux_socket": tmux_socket,
        "public_host": PUBLIC_HOST,
        "public_hub_port": PUBLIC_HUB_PORT,
        "payload_fn": payload,
        "send_message_fn": send_message,
        "workspace_sync_api": workspace_sync_api,
        "asset_runtime": asset_runtime,
        "pwa_asset_url_fn": _pwa_asset_url,
        "pwa_icon_entries_fn": _pwa_icon_entries,
        "serve_pwa_static_fn": _serve_pwa_static,
        "render_chat_html_fn": render_chat_html,
        "queue_chat_restart_fn": queue_chat_restart,
        "release_chat_restart_fn": release_chat_restart,
    }


class Handler(BaseHTTPRequestHandler):
    _GET_ROUTE_DISPATCHERS = (
        dispatch_get_assets_route,
        dispatch_get_read_route,
    )
    _POST_ROUTE_DISPATCHERS = (
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


def main(argv: list[str] | None = None) -> None:
    global server

    initialize_from_argv(argv)
    cert_file = os.environ.get("AGENT_WINDOW_CERT_FILE", "")
    key_file = os.environ.get("AGENT_WINDOW_KEY_FILE", "")
    scheme = local_bind_scheme(cert_file=cert_file, key_file=key_file)
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((local_bind_host(), port), Handler)
    if scheme == "https":
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"{scheme}://127.0.0.1:{port}/", flush=True)
    server.serve_forever()
    if chat_restart_pending:
        chat_restart_release_event.wait()


if __name__ == "__main__":
    main()
