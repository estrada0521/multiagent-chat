"""Chat server entry module extracted from bin/agent-index."""

from __future__ import annotations

import json
import os
import random
import re
import shlex
import ssl
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from agent_index.agent_registry import AGENTS, ALL_AGENT_NAMES
from agent_index.chat_assets import (
    CHAT_APP_SCRIPT_ASSET,
    CHAT_MAIN_STYLE_ASSET,
    CHAT_HTML,
    render_chat_html,
    render_pane_trace_popup_html,
)
from agent_index import chat_git
from agent_index.chat_core import ChatRuntime
from agent_index.ensure_agent_clis import agent_launch_readiness
from agent_index.export_core import ExportRuntime
from agent_index.file_core import FileRuntime
from agent_index.hub_header_assets import hub_header_logo_data_uri, read_hub_header_logo_bytes
from agent_index.push_core import SessionPushMonitor, remove_push_subscription, upsert_push_subscription, vapid_public_key

_LOG_AUTOSAVE_INTERVAL_SEC = 120  # ~2 min: lighter than 45s, still fresher than 5–10 min
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
_CHAT_HUB_LOGO_DATA_URI = ""
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
export_runtime = None
push_monitor = None


def _clean_env():
    env = os.environ.copy()
    env["MULTIAGENT_AGENT_NAME"] = "user"
    return env


def initialize_from_argv(argv: list[str] | None = None) -> None:
    global _initialized
    global index_path, commit_state_path, limit, filter_agent, session_name, follow_mode
    global port, agent_send_path, workspace, log_dir, targets, tmux_socket, hub_port
    global PUBLIC_HOST, PUBLIC_HUB_PORT, _repo_root, runtime, _CHAT_HUB_LOGO_DATA_URI
    global _PWA_STATIC_DIR, server_instance, load_chat_settings, chat_font_settings_inline_style
    global payload, append_system_entry, caffeinate_status, caffeinate_toggle, auto_mode_status
    global send_message, agent_statuses, file_runtime, HTML, export_runtime, push_monitor

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

    _CHAT_HUB_LOGO_DATA_URI = hub_header_logo_data_uri(_repo_root)
    _PWA_STATIC_DIR = _repo_root / "lib" / "agent_index" / "static" / "pwa"
    server_instance = runtime.server_instance
    load_chat_settings = runtime.load_chat_settings
    chat_font_settings_inline_style = runtime.chat_font_settings_inline_style
    payload = runtime.payload
    append_system_entry = runtime.append_system_entry
    caffeinate_status = runtime.caffeinate_status
    caffeinate_toggle = runtime.caffeinate_toggle
    auto_mode_status = runtime.auto_mode_status
    send_message = runtime.send_message
    agent_statuses = runtime.agent_statuses
    file_runtime = FileRuntime(workspace=workspace)
    HTML = CHAT_HTML
    export_runtime = ExportRuntime(
        repo_root=_repo_root,
        html_template=HTML,
        payload_fn=payload,
        server_instance=server_instance,
    )
    export_runtime.render_html_fn = lambda: render_chat_html(
        icon_data_uris=export_runtime.icon_data_uris,
        logo_data_uri=_CHAT_HUB_LOGO_DATA_URI,
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
    threading.Thread(target=_periodic_log_autosave, daemon=True, name="log-autosave").start()
    threading.Thread(target=_periodic_jsonl_sync, daemon=True, name="jsonl-sync").start()
    threading.Thread(target=push_monitor.run_forever, daemon=True, name="push-monitor").start()
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


def _periodic_log_autosave():
    time.sleep(3)
    while True:
        try:
            if runtime.session_is_active:
                runtime.save_logs(reason="autosave")
        except Exception:
            pass
        time.sleep(_LOG_AUTOSAVE_INTERVAL_SEC)


_JSONL_SYNC_INTERVAL_SEC = 1.0


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
    import re as _re
    import subprocess as _subprocess

    time.sleep(1)
    while True:
        try:
            if not runtime.session_is_active:
                time.sleep(_JSONL_SYNC_INTERVAL_SEC)
                continue

            # Acquire an exclusive, non-blocking lock for this sync tick.
            # If another chat_server for the same session holds it, skip.
            lock_fd = None
            try:
                lock_fd = open(runtime.sync_lock_path, "w")
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, IOError):
                # Another process holds the lock — skip this tick
                if lock_fd:
                    lock_fd.close()
                time.sleep(_JSONL_SYNC_INTERVAL_SEC)
                continue

            try:
                try:
                    active_agents = runtime.active_agents()
                except Exception:
                    active_agents = []
                for agent in active_agents:
                    try:
                        base_name = (agent or "").lower().split("-")[0]
                        if base_name in ("claude", "gemini", "cursor", "qwen", "opencode"):
                            # These resolve their own paths internally
                            sync_method = getattr(runtime, f"_sync_{base_name}_assistant_messages", None)
                            if sync_method:
                                sync_method(agent)
                        elif base_name in ("codex", "copilot"):
                            # These need native log path resolution
                            pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
                            try:
                                r = _subprocess.run(
                                    [*runtime.tmux_prefix, "show-environment", "-t", runtime.session_name, pane_var],
                                    capture_output=True, text=True, timeout=2, check=False,
                                )
                                line = r.stdout.strip()
                                if r.returncode != 0 or "=" not in line:
                                    continue
                                pane_id = line.split("=", 1)[1]
                            except Exception:
                                continue
                            try:
                                pane_pid = _subprocess.run(
                                    [*runtime.tmux_prefix, "display-message", "-p", "-t", pane_id, "#{pane_pid}"],
                                    capture_output=True, text=True, timeout=2, check=False,
                                ).stdout.strip()
                                if not pane_pid:
                                    continue
                            except Exception:
                                continue

                            # Check cached path first
                            cached_path = runtime._pane_native_log_paths.get(pane_id)
                            if cached_path and os.path.exists(cached_path):
                                native_log_path = cached_path
                            else:
                                from agent_index.chat_core import _resolve_native_log_file
                                if base_name == "codex":
                                    native_log_path = _resolve_native_log_file(pane_pid, r"rollout-.*\.jsonl$", base_name=base_name)
                                else:
                                    native_log_path = _resolve_native_log_file(pane_pid, r"events\.jsonl$", base_name=base_name)
                                if native_log_path:
                                    runtime._pane_native_log_paths[pane_id] = native_log_path

                            if native_log_path and os.path.exists(native_log_path):
                                sync_method = getattr(runtime, f"_sync_{base_name}_assistant_messages", None)
                                if sync_method:
                                    sync_method(agent, native_log_path)
                    except Exception:
                        pass
            finally:
                # Release lock
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
        "        result = subprocess.run(['lsof', '-nP', '-tiTCP', f':{port}', '-sTCP:LISTEN'], capture_output=True, text=True, timeout=1, check=False)\n"
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


def _memory_paths(agent: str):
    safe_agent = (agent or "claude").strip().lower() or "claude"
    base = index_path.parent / "memory" / safe_agent
    return safe_agent, base / "memory.md", base / "memory.jsonl"


def _brief_dir() -> Path:
    path = index_path.parent / "brief"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_brief_name(name: str) -> str:
    raw = (name or "").strip().lower()
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    safe = safe.strip("_-")
    return safe or "default"


def _brief_path(name: str) -> tuple[str, Path]:
    safe = _normalize_brief_name(name)
    return safe, _brief_dir() / f"brief_{safe}.md"


def _list_briefs():
    out = []
    for path in sorted(_brief_dir().glob("brief_*.md")):
        if not path.is_file():
            continue
        name = path.stem[6:] or "default"
        out.append({"name": name, "path": str(path)})
    return out


def _read_memory_content(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _extract_memory_timestamps(content: str):
    created_at = ""
    updated_at = ""
    for line in content.splitlines()[:12]:
        if line.startswith("Created At:"):
            created_at = line.split(":", 1)[1].strip()
        elif line.startswith("Updated At:"):
            updated_at = line.split(":", 1)[1].strip()
    return created_at, updated_at


def _append_memory_snapshot(agent: str, reason: str = "memory_button"):
    safe_agent, memory_md, memory_jsonl = _memory_paths(agent)
    current = _read_memory_content(memory_md)
    memory_md.parent.mkdir(parents=True, exist_ok=True)
    if current:
        memory_created_at, memory_updated_at = _extract_memory_timestamps(current)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "agent": safe_agent,
            "type": "memory_snapshot",
            "reason": reason,
            "format": "markdown",
            "memory_created_at": memory_created_at,
            "memory_updated_at": memory_updated_at,
            "line_count": len(current.splitlines()),
            "content": current,
        }
        with memory_jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False))
            f.write("\n")
    return {
        "agent": safe_agent,
        "path": str(memory_md),
        "history_path": str(memory_jsonl),
        "content": current,
        "snapshotted": bool(current),
    }

def _chat_notification_sound_filenames(sounds_dir: Path) -> list[str]:
    """Basenames of notify_*.ogg files; chat plays one at random per notification."""
    if not sounds_dir.is_dir():
        return []
    names: list[str] = []
    for path in sorted(sounds_dir.glob("notify_*.ogg")):
        if path.is_file():
            names.append(path.name)
    return names


def _default_session_notify_sound_basename(sounds_dir: Path):
    """Basename for /notify-sound with no ?name= — random notify_*.ogg, or None if none."""
    candidates = _chat_notification_sound_filenames(sounds_dir)
    if candidates:
        return random.choice(candidates)
    return None


class Handler(BaseHTTPRequestHandler):
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

    def do_GET(self):
        parsed = urlparse(self.path)
        if _serve_pwa_static(self, parsed.path):
            return
        if parsed.path == "/app.webmanifest":
            base_path = (self.headers.get("X-Forwarded-Prefix", "") or "").rstrip("/")
            body = json.dumps({
                "name": f"{session_name} chat",
                "short_name": session_name,
                "display": "standalone",
                "background_color": "rgb(38, 38, 36)",
                "theme_color": "rgb(38, 38, 36)",
                "start_url": _pwa_asset_url("/?follow=1", base_path),
                "scope": _pwa_asset_url("/", base_path),
                "icons": _pwa_icon_entries(base_path),
            }, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/chat-assets/chat-app.js":
            body = CHAT_APP_SCRIPT_ASSET.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/chat-assets/chat-app.css":
            body = CHAT_MAIN_STYLE_ASSET.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/messages":
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
            body = payload(
                limit_override=limit_override,
                before_msg_id=before_msg_id,
                around_msg_id=around_msg_id,
                light_mode=light_mode,
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/message-entry":
            qs = parse_qs(parsed.query)
            msg_id = (qs.get("msg_id", [""])[0] or "").strip()
            light_mode = (qs.get("light", [""])[0] or "").strip() == "1"
            entry = runtime.entry_by_id(msg_id, light_mode=light_mode)
            if entry is None:
                self.send_error(404)
                return
            body = json.dumps({"entry": entry}, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/normalized-events":
            qs = parse_qs(parsed.query)
            msg_id = (qs.get("msg_id", [""])[0] or "").strip()
            payload_body = runtime.normalized_events_for_msg(msg_id)
            if payload_body is None:
                self.send_error(404)
                return
            body = json.dumps(payload_body, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/pane-trace-popup":
            qs = parse_qs(parsed.query)
            agent = (qs.get("agent", [""])[0] or "").strip()
            agents_str = (qs.get("agents", [""])[0] or "").strip()
            agents = [a.strip() for a in agents_str.split(",") if a.strip()] if agents_str else [agent] if agent else []
            bg = (qs.get("bg", [""])[0] or "").strip()
            text = (qs.get("text", [""])[0] or "").strip()
            body = render_pane_trace_popup_html(agent=agent, agents=agents, bg=bg, text=text).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/trace":
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
            content_str = runtime.trace_content(agent, tail_lines=tail_lines)
            body = json.dumps({"content": content_str}, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/file-raw":
            qs = parse_qs(parsed.query)
            rel = qs.get("path", [""])[0]
            try:
                metadata = file_runtime.raw_response_metadata(rel, self.headers.get("Range", ""))
            except PermissionError:
                self.send_error(403)
                return
            except FileNotFoundError:
                self.send_error(404)
                return
            if int(metadata.get("status", 500)) == 416:
                self.send_response(416)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes */{int(metadata.get('size', 0) or 0)}")
                self.end_headers()
                return
            self.send_response(int(metadata.get("status", 200)))
            self.send_header("Content-Type", str(metadata.get("content_type") or "application/octet-stream"))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Accept-Ranges", "bytes")
            content_range = str(metadata.get("content_range") or "")
            if content_range:
                self.send_header("Content-Range", content_range)
            self.send_header("Content-Length", str(int(metadata.get("length", 0) or 0)))
            self.end_headers()
            file_runtime.stream_raw_response(metadata, self.wfile.write)
            return
        if parsed.path == "/file-content":
            qs = parse_qs(parsed.query)
            rel = qs.get("path", [""])[0]
            try:
                payload_body = file_runtime.file_content(rel)
            except PermissionError:
                self.send_error(403)
                return
            except FileNotFoundError:
                self.send_error(404)
                return
            body = json.dumps(payload_body, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/file-openability":
            qs = parse_qs(parsed.query)
            rel = qs.get("path", [""])[0]
            try:
                payload_body = {"editable": file_runtime.can_open_in_editor(rel)}
            except PermissionError:
                self.send_error(403)
                return
            except FileNotFoundError:
                self.send_error(404)
                return
            body = json.dumps(payload_body, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/file-view":
            qs = parse_qs(parsed.query)
            rel = qs.get("path", [""])[0]
            embed = qs.get("embed", [""])[0] == "1"
            try:
                settings = load_chat_settings()
                agent_font_mode = str(settings.get("agent_font_mode", "serif") or "serif").strip().lower()
                agent_message_font = str(
                    settings.get(
                        "agent_message_font",
                        "preset-gothic" if agent_font_mode == "gothic" else "preset-mincho",
                    )
                    or ("preset-gothic" if agent_font_mode == "gothic" else "preset-mincho")
                ).strip()
                page = file_runtime.file_view(
                    rel,
                    embed=embed,
                    base_path=(self.headers.get("X-Forwarded-Prefix", "") or "").rstrip("/"),
                    agent_font_mode=agent_font_mode,
                    agent_font_family=runtime._font_family_stack(agent_message_font, "agent"),
                )
            except PermissionError:
                self.send_error(403)
                return
            except FileNotFoundError:
                self.send_error(404)
                return
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/files":
            try:
                files = file_runtime.list_files()
            except Exception:
                files = []
            body = json.dumps(files, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/agents":
            body = json.dumps(agent_statuses(), ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/export":
            import time as _time
            try:
                qs = parse_qs(parsed.query)
                limit = int(qs.get("limit", ["100"])[0])
                html_content = export_runtime.build_export_html(limit=limit)
                body = html_content.encode("utf-8")
                ts = _time.strftime("%Y%m%d-%H%M%S")
                filename = f"{session_name}-{ts}.html"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("X-Export-Filename", filename)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(str(e).encode())
            return
        if parsed.path == "/caffeinate":
            body = json.dumps(caffeinate_status(), ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/auto-mode":
            body = json.dumps(auto_mode_status(), ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/hub-settings":
            s = load_chat_settings()
            body = json.dumps({
                "theme":                  str(s.get("theme", "default")),
                "starfield":              bool(s.get("starfield", False)),
                "bold_mode_mobile":       bool(s.get("bold_mode_mobile", False)),
                "bold_mode_desktop":      bool(s.get("bold_mode_desktop", False)),
                # Deprecated: true if either viewport mode is on (legacy clients).
                "bold_mode": bool(s.get("bold_mode_mobile", False) or s.get("bold_mode_desktop", False)),
                "agent_font_mode":        str(s.get("agent_font_mode", "serif")),
                "chat_font_settings_css": chat_font_settings_inline_style(s),
                "message_max_width":      int(s.get("message_max_width", 900) or 900),
                "chat_auto_mode":         bool(s.get("chat_auto_mode", False)),
                "chat_awake":             bool(s.get("chat_awake", False)),
                "chat_sound":             bool(s.get("chat_sound", False)),
                "chat_browser_notifications": bool(s.get("chat_browser_notifications", False)),
                "chat_tts":               bool(s.get("chat_tts", False)),
            }, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/push-config":
            settings = load_chat_settings()
            body = json.dumps({
                "enabled": bool(settings.get("chat_browser_notifications", False)),
                "public_key": vapid_public_key(_repo_root),
            }, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/session-state":
            try:
                body = json.dumps({
                    "server_instance": server_instance,
                    "session": session_name,
                    "active": bool(runtime.session_is_active),
                    "targets": runtime.active_agents(),
                    "statuses": runtime.agent_statuses(),
                    "agent_runtime": runtime.agent_runtime_state(),
                    "totals": runtime.load_thinking_totals(),
                    "provider_runtime": runtime.provider_runtime_state(),
                }, ensure_ascii=True).encode("utf-8")
            except Exception as exc:
                body = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/git-branch-overview":
            qs = parse_qs(parsed.query)
            raw_offset = (qs.get("offset", ["0"])[0] or "0").strip()
            raw_limit = (qs.get("limit", ["50"])[0] or "50").strip()
            try:
                body = json.dumps(
                    chat_git.git_branch_overview(offset=raw_offset, limit=raw_limit),
                    ensure_ascii=True,
                ).encode("utf-8")
            except Exception as exc:
                body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/git-diff":
            qs = parse_qs(parsed.query)
            commit_hash = (qs.get("hash", [""])[0] or "").strip()
            root = Path(workspace or _repo_root)
            try:
                if commit_hash:
                    result = subprocess.run(
                        ["git", "-C", str(root), "diff", f"{commit_hash}~1", commit_hash],
                        capture_output=True, text=True, timeout=10, check=False,
                    )
                else:
                    result = subprocess.run(
                        ["git", "-C", str(root), "diff", "HEAD", "--"],
                        capture_output=True, text=True, timeout=10, check=False,
                    )
                diff_text = result.stdout or ""
                body = json.dumps({"diff": diff_text}, ensure_ascii=True).encode("utf-8")
            except Exception as exc:
                body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/memory-path":
            qs = parse_qs(parsed.query)
            agent = qs.get("agent", ["claude"])[0].lower()
            _, p, history_path = _memory_paths(agent)
            p.parent.mkdir(parents=True, exist_ok=True)
            mem_path = str(p)
            content = _read_memory_content(p)
            body = json.dumps(
                {"path": mem_path, "history_path": str(history_path), "content": content},
                ensure_ascii=True,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/briefs":
            body = json.dumps({"briefs": _list_briefs()}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/brief-content":
            qs = parse_qs(parsed.query)
            name = qs.get("name", ["default"])[0]
            safe_name, path = _brief_path(name)
            content = _read_memory_content(path)
            body = json.dumps(
                {"name": safe_name, "path": str(path), "content": content, "exists": path.exists()},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path.startswith("/icon/"):
            name = parsed.path[6:]
            body = export_runtime.icon_bytes(name)
            if body is not None:
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()
            return
        if parsed.path.startswith("/font/"):
            name = parsed.path[6:]
            body = export_runtime.font_bytes(name)
            if body is not None:
                self.send_response(200)
                self.send_header("Content-Type", "font/ttf")
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()
            return
        if parsed.path == "/hub-logo":
            body = read_hub_header_logo_bytes(_repo_root)
            if not body:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/webp")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/notify-sounds":
            _sounds_dir = _repo_root / "sounds"
            names = list(_chat_notification_sound_filenames(_sounds_dir))
            random.shuffle(names)
            body = json.dumps(names, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/notify-sounds-all":
            _sounds_dir = _repo_root / "sounds"
            names = []
            if _sounds_dir.is_dir():
                for path in sorted(_sounds_dir.glob("*.ogg")):
                    if path.is_file():
                        names.append(path.name)
            body = json.dumps(names, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/notify-sound":
            qs = parse_qs(parsed.query)
            name = (qs.get("name", [""])[0] or "").strip()
            _sounds_dir = _repo_root / "sounds"
            if not name:
                picked = _default_session_notify_sound_basename(_sounds_dir)
                if not picked:
                    self.send_response(404)
                    self.end_headers()
                    return
                name = picked
            path = (_sounds_dir / name).resolve()
            try:
                if path.parent != _sounds_dir.resolve() or path.suffix.lower() != ".ogg":
                    raise FileNotFoundError
                body = path.read_bytes()
            except Exception:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/ogg")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/" or parsed.path == "/index.html":
            qs = parse_qs(parsed.query)
            follow = "1" if qs.get("follow", ["0"])[0] == "1" else "0"
            chat_settings = load_chat_settings()
            request_host = (self.headers.get("Host", "") or "").strip()
            request_host_only = request_host.split(":", 1)[0].rstrip(".").lower()
            forwarded_public_host = (self.headers.get("X-Forwarded-Public-Host", "") or "").strip()
            forwarded_public_proto = (self.headers.get("X-Forwarded-Public-Proto", "") or "").strip().lower()
            effective_hub_port = (
                PUBLIC_HUB_PORT
                if (
                    forwarded_public_host
                    or ((PUBLIC_HOST and request_host_only == PUBLIC_HOST) or request_host_only.endswith(".ts.net"))
                )
                else hub_port
            )
            body = render_chat_html(
                icon_data_uris=export_runtime.icon_data_uris,
                logo_data_uri=_CHAT_HUB_LOGO_DATA_URI,
                server_instance=server_instance,
                hub_port=effective_hub_port,
                chat_settings=chat_settings,
                agent_font_mode_inline_style=chat_font_settings_inline_style,
                follow=follow,
                chat_base_path=(self.headers.get("X-Forwarded-Prefix", "") or "").rstrip("/"),
                externalize_app_script=True,
                externalize_main_style=True,
                eager_optional_vendors=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/sync-status":
            body = json.dumps(runtime.sync_cursor_status(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/caffeinate":
            self._send_json(200, caffeinate_toggle())
            return
        if parsed.path == "/auto-mode":
            current = auto_mode_status()
            action = "off" if current["active"] else "on"
            bin_dir = Path(agent_send_path).parent
            try:
                subprocess.run(
                    [str(bin_dir / "multiagent-auto-mode"), action, "--session", session_name],
                    capture_output=True, text=True, env=_clean_env(), check=False,
                )
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, {"ok": True, "active": not current["active"]})
            return
        if parsed.path == "/new-chat":
            ok, detail = queue_chat_restart()
            if not ok:
                self._send_json(500, {"ok": False, "error": detail})
                return
            self._send_json(200, {"ok": True, "port": port, "restarting": True, "detail": detail})
            return
        if parsed.path == "/add-agent":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            agent = (data.get("agent") or "").strip().lower()
            if not agent:
                self._send_json(400, {"ok": False, "error": "agent required"})
                return
            bin_dir = Path(agent_send_path).parent
            try:
                proc = subprocess.run(
                    [str(bin_dir / "multiagent"), "add-agent", "--session", session_name, "--agent", agent],
                    capture_output=True,
                    text=True,
                    env=_clean_env(),
                    check=False,
                )
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            if proc.returncode != 0:
                self._send_json(500, {"ok": False, "error": stderr or stdout or f"add-agent failed ({proc.returncode})"})
                return
            self._send_json(200, {
                "ok": True,
                "agent": agent,
                "message": stdout or f"Added agent {agent}",
                "targets": runtime.active_agents(),
            })
            return
        if parsed.path == "/remove-agent":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            agent = (data.get("agent") or "").strip()
            if not agent:
                self._send_json(400, {"ok": False, "error": "agent required"})
                return
            bin_dir = Path(agent_send_path).parent
            try:
                proc = subprocess.run(
                    [str(bin_dir / "multiagent"), "remove-agent", "--session", session_name, "--agent", agent],
                    capture_output=True,
                    text=True,
                    env=_clean_env(),
                    check=False,
                )
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            if proc.returncode != 0:
                self._send_json(500, {"ok": False, "error": stderr or stdout or f"remove-agent failed ({proc.returncode})"})
                return
            self._send_json(200, {
                "ok": True,
                "agent": agent,
                "message": stdout or f"Removed agent {agent}",
                "targets": runtime.active_agents(),
            })
            return
        if parsed.path == "/log-system":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            msg = (data.get("message") or "").strip()
            if not msg:
                self._send_json(400, {"ok": False, "error": "message required"})
                return
            append_system_entry(msg)
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/memory-snapshot":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            agent = (data.get("agent") or "").strip().lower()
            if not agent:
                self._send_json(400, {"ok": False, "error": "agent required"})
                return
            reason = (data.get("reason") or "memory_button").strip() or "memory_button"
            try:
                result = _append_memory_snapshot(agent, reason=reason)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            result["ok"] = True
            self._send_json(200, result)
            return
        if parsed.path == "/brief-content":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            safe_name, path = _brief_path(data.get("name", "default"))
            content = str(data.get("content", ""))
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, {"ok": True, "name": safe_name, "path": str(path)})
            return
        if parsed.path == "/save-logs":
            qs = parse_qs(parsed.query)
            reason = (qs.get("reason", ["autosave"])[0] or "autosave").strip()[:64]
            try:
                status, payload = runtime.save_logs(reason=reason)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc), "reason": reason})
                return
            self._send_json(status, payload)
            return
        if parsed.path == "/push/subscribe":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            try:
                result = upsert_push_subscription(
                    _repo_root,
                    session_name,
                    workspace,
                    data.get("subscription") or {},
                    client_id=str(data.get("client_id") or "").strip(),
                    user_agent=str(data.get("user_agent") or "").strip(),
                )
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            endpoint = str((data.get("subscription") or {}).get("endpoint") or "").strip()
            if endpoint:
                try:
                    push_monitor.record_presence(
                        str(data.get("client_id") or "").strip(),
                        visible=not bool(data.get("hidden", False)),
                        focused=not bool(data.get("hidden", False)),
                        endpoint=endpoint,
                    )
                except Exception:
                    pass
            self._send_json(200, {"ok": True, **result})
            return
        if parsed.path == "/push/unsubscribe":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            endpoint = str(data.get("endpoint") or "").strip()
            if not endpoint:
                self._send_json(400, {"ok": False, "error": "endpoint required"})
                return
            try:
                removed = remove_push_subscription(_repo_root, session_name, workspace, endpoint)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, {"ok": True, "removed": bool(removed)})
            return
        if parsed.path == "/push/presence":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            client_id = str(data.get("client_id") or "").strip()
            if not client_id:
                self._send_json(400, {"ok": False, "error": "client_id required"})
                return
            try:
                push_monitor.record_presence(
                    client_id,
                    visible=bool(data.get("visible", False)),
                    focused=bool(data.get("focused", False)),
                    endpoint=str(data.get("endpoint") or "").strip(),
                )
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/thinking-time" and self.command == "GET":
            try:
                self._send_json(200, {"ok": True, "totals": runtime.load_thinking_totals()})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/upload":
            import datetime as _dt
            import re as _re
            from urllib.parse import unquote as _url_unquote
            content_type = self.headers.get("Content-Type", "application/octet-stream")
            raw_name = self.headers.get("X-Filename", "upload.bin") or "upload.bin"
            try:
                filename = _url_unquote(raw_name)
            except Exception:
                filename = raw_name
            filename = _re.sub(r"[\x00-\x1f\x7f\u200b-\u200f\u2028\u2029]", "", str(filename)).strip()
            filename = Path(filename).name or "upload.bin"
            if filename in (".", ".."):
                filename = "upload.bin"
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            data = self.rfile.read(length)
            upload_dir = Path(log_dir) / session_name / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            import uuid as _uuid
            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
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
            save_name = f"{ts}_{_uuid.uuid4().hex[:6]}{ext}"
            save_path = upload_dir / save_name
            save_path.write_bytes(data)
            try:
                rel_path = str(save_path.relative_to(Path(workspace)))
            except ValueError:
                rel_path = str(save_path)
            self._send_json(200, {"ok": True, "path": rel_path})
            return
        if parsed.path == "/rename-upload":
            import json as _json_rename, re as _re_rename
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            body = _json_rename.loads(self.rfile.read(length) or b"{}")
            old_rel = body.get("path", "")
            label = body.get("label", "").strip()
            if not old_rel or not label:
                self._send_json(400, {"ok": False, "error": "path and label required"})
                return
            old_path = Path(workspace) / old_rel
            if not old_path.is_file():
                self._send_json(404, {"ok": False, "error": "file not found"})
                return
            label = _re_rename.sub(r"[\x00-\x1f\x7f\u200b-\u200f\u2028\u2029/\\]", "", label)
            label = _re_rename.sub(r"[^\w\-. ]", "_", label).strip()[:80]
            if not label:
                self._send_json(400, {"ok": False, "error": "invalid label"})
                return
            ext = old_path.suffix
            new_name = f"{label}{ext}"
            new_path = old_path.parent / new_name
            if new_path.exists() and new_path != old_path:
                import uuid as _uuid_rename
                new_name = f"{label}_{_uuid_rename.uuid4().hex[:4]}{ext}"
                new_path = old_path.parent / new_name
            old_path.rename(new_path)
            try:
                new_rel = str(new_path.relative_to(Path(workspace)))
            except ValueError:
                new_rel = str(new_path)
            self._send_json(200, {"ok": True, "path": new_rel})
            return
        if parsed.path == "/open-terminal":
            try:
                socket_flag = "-S" if "/" in tmux_socket else "-L"
                cols, rows = 200, 60
                try:
                    size_result = subprocess.run(
                        [
                            "tmux",
                            socket_flag,
                            tmux_socket,
                            "display-message",
                            "-p",
                            "-t",
                            f"={session_name}:0",
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
                    f"{shlex.quote(tmux_socket)} attach-session -t {shlex.quote(session_name)}"
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
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self._send_json(200, {"ok": True})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/open-finder":
            try:
                target = Path(workspace or _repo_root).resolve()
                if not target.exists():
                    self._send_json(404, {"ok": False, "error": "workspace not found"})
                    return
                subprocess.Popen(
                    ["open", str(target)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._send_json(200, {"ok": True, "path": str(target)})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/files-exist":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            paths = data.get("paths", [])
            if not isinstance(paths, list):
                self._send_json(400, {"ok": False, "error": "paths must be a list"})
                return
            result = file_runtime.files_exist(paths)
            self._send_json(200, result)
            return
        if parsed.path == "/open-file-in-editor":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            rel = (data.get("path") or "").strip()
            line = int(data.get("line", 0) or 0)
            if not rel:
                self._send_json(400, {"ok": False, "error": "path required"})
                return
            try:
                result = file_runtime.open_in_editor(rel, line=line)
            except PermissionError:
                self._send_json(403, {"ok": False, "error": "forbidden"})
                return
            except FileNotFoundError:
                self._send_json(404, {"ok": False, "error": "file not found"})
                return
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, result)
            return
        if parsed.path == "/git-commit-file":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            rel = (data.get("path") or "").strip()
            message = (data.get("message") or "").strip()
            agent = (data.get("agent") or "").strip()
            if not rel:
                self._send_json(400, {"ok": False, "error": "path required"})
                return
            if not message:
                self._send_json(400, {"ok": False, "error": "message required"})
                return
            try:
                result = chat_git.git_commit_file(rel_path=rel, message=message, agent=agent)
            except PermissionError:
                self._send_json(403, {"ok": False, "error": "forbidden"})
                return
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, result)
            return
        if parsed.path == "/git-commit-all":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            message = (data.get("message") or "").strip()
            agent = (data.get("agent") or "").strip()
            if not message:
                self._send_json(400, {"ok": False, "error": "message required"})
                return
            try:
                result = chat_git.git_commit_all(message=message, agent=agent)
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, result)
            return
        if parsed.path == "/git-restore-file":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"ok": False, "error": "invalid json"})
                return
            rel = (data.get("path") or "").strip()
            if not rel:
                self._send_json(400, {"ok": False, "error": "path required"})
                return
            try:
                result = chat_git.git_restore_file(rel_path=rel)
            except PermissionError:
                self._send_json(403, {"ok": False, "error": "forbidden"})
                return
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, result)
            return
        if parsed.path != "/send":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json"})
            return
        status, body = send_message(
            data.get("target", ""),
            data.get("message", ""),
            data.get("reply_to", ""),
            silent=bool(data.get("silent", False)),
            raw=bool(data.get("raw", False)),
            provider_direct=data.get("provider_direct", ""),
            provider_model=data.get("provider_model", ""),
        )
        self._send_json(status, body)

def _kill_stale_sync_processes(index_path_str: str) -> None:
    """Kill other chat_server processes syncing the same JSONL file.

    When a new chat_server starts for a session, any leftover process from a
    previous launch (e.g. after a Hub reload that spawned a new server without
    cleanly stopping the old one) will continue its sync loop and produce
    duplicate JSONL entries.  This function finds those processes and kills them.
    """
    import signal
    my_pid = os.getpid()
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"agent_index.chat_server.*{index_path_str}"],
            capture_output=True, text=True, timeout=5, check=False,
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
