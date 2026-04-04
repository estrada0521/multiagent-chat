"""Hub server entry module extracted from bin/agent-index."""

from __future__ import annotations

import base64 as _base64
import html
import json
import os
import re
import ssl
import subprocess
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote as url_quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from agent_index.agent_registry import AGENT_ICONS_DIR, ALL_AGENT_NAMES, icon_filename_map as _icon_filename_map
from agent_index.cron_core import (
    CronScheduler,
    delete_cron_job,
    get_cron_job,
    list_cron_jobs,
    save_cron_job,
    set_cron_enabled,
)
from agent_index.hub_core import HubRuntime
from agent_index.ensure_agent_clis import agent_launch_readiness
from agent_index.hub_header_assets import (
    HUB_PAGE_HEADER_CSS,
    HUB_PAGE_HEADER_JS,
    hub_header_logo_data_uri,
    read_hub_header_logo_bytes,
    render_hub_page_header,
)
from agent_index.push_core import HubPushMonitor, remove_hub_push_subscription, upsert_hub_push_subscription, vapid_public_key
from agent_index.state_core import available_theme_choices, theme_description

def _not_initialized(*_args, **_kwargs):
    raise RuntimeError("hub_server.initialize_from_argv() must run before serving requests")


_initialized = False
repo_root = Path()
script_path = Path()
port = 0
tmux_socket = ""
hub = None
load_hub_settings = _not_initialized
save_hub_settings = _not_initialized
repo_sessions = _not_initialized
repo_sessions_query = _not_initialized
archived_sessions = _not_initialized
active_session_records = _not_initialized
active_session_records_query = _not_initialized
archived_session_records = _not_initialized
compute_hub_stats = _not_initialized
ensure_chat_server = _not_initialized
wait_for_session_instances = _not_initialized
revive_archived_session = _not_initialized
kill_repo_session = _not_initialized
delete_archived_session = _not_initialized
host_without_port = _not_initialized
PUBLIC_HOST = ""
PUBLIC_HUB_PORT = 443
restart_lock = threading.Lock()
restart_pending = False
hub_server = None
hub_push_monitor = None
cron_scheduler = None
_scheme = "http"


def resolve_external_origin(host_header: str, local_port: int) -> dict[str, object]:
    host = host_without_port(host_header or "127.0.0.1")
    host_lc = host.lower()
    is_public = (PUBLIC_HOST and host_lc == PUBLIC_HOST) or host_lc.endswith(".ts.net")
    if is_public and local_port == port:
        external_port = PUBLIC_HUB_PORT
    else:
        external_port = local_port
    default_port = 443 if _scheme == "https" else 80
    port_part = "" if external_port == default_port else f":{external_port}"
    return {
        "host": host,
        "external_port": external_port,
        "is_public": bool(is_public),
        "origin": f"{_scheme}://{host}{port_part}",
    }


def format_external_url(host_header: str, local_port: int, path: str) -> str:
    resolved = resolve_external_origin(host_header, local_port)
    return f"{resolved['origin']}{path}"


def is_public_host(host_header: str) -> bool:
    return bool(resolve_external_origin(host_header, 0).get("is_public"))


def format_session_chat_url(host_header: str, session_name: str, local_port: int, path: str) -> str:
    resolved = resolve_external_origin(host_header, port)
    if resolved["is_public"]:
        base = f"{resolved['origin']}/session/{url_quote(session_name)}"
        return f"{base}{path}"
    return format_external_url(host_header, local_port, path)


def initialize_from_argv(argv: list[str] | None = None) -> None:
    global _initialized
    global repo_root, script_path, port, tmux_socket, hub
    global load_hub_settings, save_hub_settings, repo_sessions, repo_sessions_query
    global archived_sessions, active_session_records, active_session_records_query
    global archived_session_records, compute_hub_stats, ensure_chat_server
    global wait_for_session_instances, revive_archived_session, kill_repo_session
    global delete_archived_session, host_without_port, PUBLIC_HOST, PUBLIC_HUB_PORT
    global restart_pending, hub_server, hub_push_monitor, cron_scheduler, _PWA_STATIC_DIR

    if _initialized:
        return

    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 4:
        raise SystemExit(
            "usage: python -m agent_index.hub_server <repo_root> <script_path> <port> <tmux_socket>"
        )

    repo_root = Path(argv[0]).resolve()
    script_path = Path(argv[1]).resolve()
    port = int(argv[2])
    tmux_socket = argv[3]
    hub = HubRuntime(repo_root, script_path, tmux_socket, hub_port=port)
    load_hub_settings = hub.load_hub_settings
    save_hub_settings = hub.save_hub_settings
    repo_sessions = hub.repo_sessions
    repo_sessions_query = hub.repo_sessions_query
    archived_sessions = hub.archived_sessions
    active_session_records = hub.active_session_records
    active_session_records_query = hub.active_session_records_query
    archived_session_records = hub.archived_session_records
    compute_hub_stats = hub.compute_hub_stats
    ensure_chat_server = hub.ensure_chat_server
    wait_for_session_instances = hub.wait_for_session_instances
    revive_archived_session = hub.revive_archived_session
    kill_repo_session = hub.kill_repo_session
    delete_archived_session = hub.delete_archived_session
    host_without_port = hub.host_without_port
    PUBLIC_HOST = (os.environ.get("MULTIAGENT_PUBLIC_HOST", "") or "").strip().rstrip(".").lower()
    PUBLIC_HUB_PORT = int(os.environ.get("MULTIAGENT_PUBLIC_HUB_PORT", "443") or "443")
    restart_pending = False
    hub_server = None
    _PWA_STATIC_DIR = repo_root / "lib" / "agent_index" / "static" / "pwa"

    hub_push_monitor = HubPushMonitor(
        repo_root=repo_root,
        settings_loader=load_hub_settings,
        sessions_provider=lambda: repo_sessions_query().sessions,
    )
    cron_scheduler = CronScheduler(
        repo_root=repo_root,
        hub_runtime=hub,
        agent_send_path=script_path.parent / "agent-send",
    )
    threading.Thread(target=hub_push_monitor.run_forever, daemon=True, name="hub-push-monitor").start()
    threading.Thread(target=cron_scheduler.run_forever, daemon=True, name="cron-scheduler").start()
    _initialized = True


def restarting_page():
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Restarting Hub</title><style>:root{color-scheme:dark}body{margin:0;background:rgb(38,38,36);color:rgb(240,239,235);font-family:'SF Pro Text','Segoe UI',sans-serif;padding:24px}.panel{max-width:680px;margin:0 auto;background:rgb(25,25,24);border:0.5px solid rgba(255,255,255,0.09);border-radius:16px;padding:18px 18px 16px}.eyebrow{color:rgb(156,154,147);font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin:0 0 8px}h1{margin:0 0 10px;font-size:24px}p{margin:0;color:rgb(156,154,147);line-height:1.6}</style></head><body><div class="panel"><div class="eyebrow">multiagent</div><h1>Restarting Hub</h1><p>The Hub server is being replaced. This page will reconnect automatically as soon as the new server is ready.</p></div><script>const started=Date.now();const reconnect=async()=>{try{const res=await fetch(`/sessions?ts=${Date.now()}`,{cache:'no-store'});if(res.ok){window.location.replace('/');return;}}catch(_err){}if(Date.now()-started<15000){window.setTimeout(reconnect,500);}};window.setTimeout(reconnect,700);</script></body></html>"""


def queue_hub_restart():
    global restart_pending
    with restart_lock:
        if restart_pending:
            return False
        restart_pending = True

    restart_helper = (
        "import socket, subprocess, sys, time\n"
        "script_path, port, repo_root = sys.argv[1], int(sys.argv[2]), sys.argv[3]\n"
        "def port_open():\n"
        "    try:\n"
        "        with socket.create_connection(('127.0.0.1', port), timeout=0.2):\n"
        "            return True\n"
        "    except OSError:\n"
        "        return False\n"
        "for _ in range(150):\n"
        "    if not port_open():\n"
        "        break\n"
        "    time.sleep(0.1)\n"
        "subprocess.Popen(\n"
        "    ['bash', script_path, '--hub', '--hub-port', str(port), '--no-open'],\n"
        "    cwd=repo_root,\n"
        "    stdin=subprocess.DEVNULL,\n"
        "    stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL,\n"
        "    start_new_session=True,\n"
        "    close_fds=True,\n"
        ")\n"
    )
    subprocess.Popen(
        [sys.executable, "-c", restart_helper, str(script_path), str(port), str(repo_root)],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )

    def worker():
        try:
            time.sleep(0.15)
            if hub_server is not None:
                hub_server.shutdown()
                hub_server.server_close()
        finally:
            pass

    threading.Thread(target=worker, daemon=True).start()
    return True

NEW_SESSION_MAX_PER_AGENT = 5
_PWA_STATIC_DIR = Path()
_PWA_STATIC_ROUTES = {
    "/pwa-icon-192.png": ("icon-192.png", "image/png", "no-store"),
    "/pwa-icon-512.png": ("icon-512.png", "image/png", "no-store"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png", "no-store"),
    "/service-worker.js": ("service-worker.js", "application/javascript; charset=utf-8", "no-store"),
    "/hub-service-worker.js": ("service-worker.js", "application/javascript; charset=utf-8", "no-store"),
}
_PWA_ASSET_VERSION_OVERRIDES = {
    "/hub.webmanifest": str(int(Path(__file__).stat().st_mtime_ns)),
}


def _pwa_asset_version(path: str) -> str:
    if path in _PWA_ASSET_VERSION_OVERRIDES:
        return _PWA_ASSET_VERSION_OVERRIDES[path]
    route = _PWA_STATIC_ROUTES.get(path)
    if not route:
        return str(int(Path(__file__).stat().st_mtime_ns))
    filename = route[0]
    try:
        return str(int((_PWA_STATIC_DIR / filename).stat().st_mtime_ns))
    except OSError:
        return str(int(Path(__file__).stat().st_mtime_ns))

def _icon_data_uri(filename: str) -> str:
    try:
        icon_file = repo_root / AGENT_ICONS_DIR / filename
        if not icon_file.is_file():
            if filename == "grok.svg":
                fallback_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 5h9a4 4 0 0 1 4 4v10"/><path d="m6 19 12-14"/><path d="M9 19h9"/></svg>"""
                return "data:image/svg+xml;base64," + _base64.b64encode(fallback_svg.encode("utf-8")).decode("ascii")
            return ""
        return "data:image/svg+xml;base64," + _base64.b64encode(icon_file.read_bytes()).decode("ascii")
    except Exception:
        return ""


def _pwa_asset_url(path: str, base_path: str = "", *, bust: bool = False) -> str:
    prefix = (base_path or "").rstrip("/")
    url = f"{prefix}{path}" if prefix else path
    if bust:
        version = _pwa_asset_version(path)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}v={version}"
    return url


def _pwa_icon_entries(base_path: str = "") -> list[dict[str, str]]:
    return [
        {
            "src": _pwa_asset_url("/pwa-icon-192.png", base_path, bust=True),
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": _pwa_asset_url("/pwa-icon-512.png", base_path, bust=True),
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any",
        },
    ]


def _pwa_shortcut_entries(base_path: str = "") -> list[dict[str, object]]:
    icon_192 = _pwa_asset_url("/pwa-icon-192.png", base_path, bust=True)
    shortcut_icon = [{
        "src": icon_192,
        "sizes": "192x192",
        "type": "image/png",
    }]
    return [
        {
            "name": "New Session",
            "short_name": "New",
            "description": "Start a fresh multiagent session",
            "url": _pwa_asset_url("/new-session", base_path),
            "icons": shortcut_icon,
        },
        {
            "name": "Resume Sessions",
            "short_name": "Resume",
            "description": "Open active and archived sessions",
            "url": _pwa_asset_url("/resume", base_path),
            "icons": shortcut_icon,
        },
        {
            "name": "Settings",
            "short_name": "Settings",
            "description": "Open Hub settings and notification controls",
            "url": _pwa_asset_url("/settings#app-controls", base_path),
            "icons": shortcut_icon,
        },
    ]


_PWA_HUB_MANIFEST_URL = _pwa_asset_url("/hub.webmanifest", bust=True)
_PWA_ICON_192_URL = _pwa_asset_url("/pwa-icon-192.png", bust=True)
_PWA_APPLE_TOUCH_ICON_URL = _pwa_asset_url("/apple-touch-icon.png", bust=True)


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

_HUB_ICON_URIS = {name: _icon_data_uri(fname) for name, fname in _icon_filename_map().items()}
_HUB_LOGO_DATA_URI = hub_header_logo_data_uri(repo_root)
_HUB_PAGE_HEADER_CSS = HUB_PAGE_HEADER_CSS
_HUB_PAGE_HEADER_HTML = render_hub_page_header(logo_data_uri=_HUB_LOGO_DATA_URI)
_HUB_PAGE_HEADER_JS = HUB_PAGE_HEADER_JS

HUB_APP_HTML = """<!doctype html>
<html lang="en" data-theme="__CHAT_THEME__"__STARFIELD_ATTR__ data-agent-font-mode="__AGENT_FONT_MODE__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="rgb(10, 10, 10)">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Session Hub">
  <link rel="manifest" href="__HUB_MANIFEST_URL__">
  <link rel="icon" type="image/png" sizes="192x192" href="__PWA_ICON_192_URL__">
  <link rel="apple-touch-icon" href="__APPLE_TOUCH_ICON_URL__">
  <script>
    (() => {
      if (!("serviceWorker" in navigator)) return;
      const isLocalHost = location.hostname === "localhost" || location.hostname === "127.0.0.1" || location.hostname === "[::1]";
      if (!(window.isSecureContext || isLocalHost)) return;
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/hub-service-worker.js", { scope: "/" }).catch((err) => {
          console.warn("hub service worker registration failed", err);
        });
      }, { once: true });
    })();
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap" rel="stylesheet">
  <title>Session Hub</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: rgb(10, 10, 10);
      --bg-rgb: 10, 10, 10;
      --panel: rgba(18, 18, 20, 0.7);
      --panel-2: rgba(25, 25, 28, 0.8);
      --line: rgba(255,255,255,0.06);
      --line-strong: rgba(255,255,255,0.12);
      --fg: rgb(240, 240, 240);
      --muted: rgb(140, 140, 145);
      --ok: rgb(120, 180, 130);
      --warn: rgb(220, 190, 110);
      --bad: rgb(200, 90, 100);
      --accent: rgb(70, 120, 230);
    }
    html[data-theme="soft-light"] {
      color-scheme: light;
      --bg: rgb(244, 244, 242);
      --bg-rgb: 244, 244, 242;
      --panel: rgba(255, 255, 255, 0.9);
      --panel-2: rgba(248, 248, 246, 0.95);
      --line: rgba(15, 20, 30, 0.12);
      --line-strong: rgba(15, 20, 30, 0.2);
      --fg: rgb(26, 30, 36);
      --muted: rgb(98, 106, 120);
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      min-height: 100%;
      background: var(--bg);
      color: var(--fg);
      font-family: "SF Pro Text", "Segoe UI", sans-serif;
    }
    body {
      padding: 0 0 max(20px, env(safe-area-inset-bottom)) 0;
    }
    .shell {
      max-width: 900px;
      margin: 0 auto;
    }
    .shell > :not(.hub-page-header) {
      padding-left: 14px;
      padding-right: 14px;
    }
    .hero {
      padding: 8px 2px 18px 2px;
    }
    .eyebrow {
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    h1 {
      margin: 0;
      font-size: clamp(26px, 5vw, 38px);
      line-height: 1.02;
      font-weight: 600;
      letter-spacing: -0.03em;
    }
    .sub {
      margin-top: 10px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
      max-width: 38rem;
    }
    .toolbar {
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .hub-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
      width: 100%;
      align-items: center;
    }
    .hub-nav a, .hub-nav button {
      color: var(--muted);
      text-decoration: none;
      border: 0.5px solid var(--line);
      background: var(--panel);
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 13px;
      line-height: 1;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      backdrop-filter: blur(10px);
      transition: all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      cursor: pointer;
      appearance: none;
      -webkit-appearance: none;
    }
    .hub-nav a:hover, .hub-nav button:hover {
      color: var(--fg);
      border-color: rgba(255,255,255,0.25);
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    }
    .hub-nav a.active {
      color: var(--fg);
      border-color: rgba(255,255,255,0.3);
      background: var(--panel-2);
      box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }
    .hub-nav .hub-restart-form {
      margin-left: auto;
    }

    .activity-grid-wrap {
      margin-bottom: 18px;
      overflow-x: auto;
    }
    .activity-filter-row {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 10px;
      padding: 4px;
      border: 0.5px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
    }
    .activity-filter-note {
      margin: 0 0 12px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
      max-width: 42rem;
    }
    .activity-filter-btn {
      border: none;
      background: transparent;
      color: var(--muted);
      border-radius: 999px;
      padding: 7px 12px;
      font: inherit;
      font-size: 11px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      cursor: pointer;
      transition: background 140ms ease, color 140ms ease;
    }
    .activity-filter-btn.active {
      background: var(--panel-2);
      color: var(--fg);
    }
    .activity-grid-label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--muted, #888);
      margin-bottom: 8px;
    }
    .activity-grid {
      display: inline-flex;
      flex-direction: row;
      gap: 3px;
      align-items: flex-start;
    }
    .activity-week {
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .activity-cell {
      width: 11px;
      height: 11px;
      border-radius: 2px;
      background: rgba(255,255,255,0.06);
      cursor: default;
      flex-shrink: 0;
      position: relative;
    }
    .activity-cell[data-level="1"] { background: rgba(217,119,87,0.25); }
    .activity-cell[data-level="2"] { background: rgba(217,119,87,0.50); }
    .activity-cell[data-level="3"] { background: rgba(217,119,87,0.75); }
    .activity-cell[data-level="4"] { background: rgba(217,119,87,1.00); }
    .activity-cell.thinking[data-level="1"] { background: rgba(217,119,87,0.25); }
    .activity-cell.thinking[data-level="2"] { background: rgba(217,119,87,0.50); }
    .activity-cell.thinking[data-level="3"] { background: rgba(217,119,87,0.75); }
    .activity-cell.thinking[data-level="4"] { background: rgba(217,119,87,1.00); }
    .activity-cell:hover::after {
      content: attr(data-tip);
      position: absolute;
      bottom: calc(100% + 5px);
      left: 50%;
      transform: translateX(-50%);
      background: rgba(30,30,30,0.95);
      color: #f8f8f8;
      font-size: 11px;
      white-space: nowrap;
      padding: 3px 7px;
      border-radius: 4px;
      pointer-events: none;
      z-index: 100;
    }
    .activity-month-labels {
      display: inline-flex;
      flex-direction: row;
      gap: 3px;
      margin-bottom: 3px;
    }
    .activity-month-label {
      font-size: 10px;
      color: var(--muted, #888);
      width: 11px;
      white-space: nowrap;
      overflow: visible;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }
    .stats-column {
      display: grid;
      align-content: start;
      gap: 10px;
      min-width: 0;
    }
    .stat-card {
      background: var(--panel);
      border: 0.5px solid var(--line);
      border-radius: 14px;
      padding: 12px 13px;
      min-width: 0;
      position: relative;
      overflow: hidden;
    }
    .stat-content {
      position: relative;
      z-index: 1;
    }
    .stat-trend {
      position: absolute;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      opacity: 0.8;
    }
    .stat-trend svg {
      width: 100%;
      height: 100%;
      display: block;
      clip-path: inset(0 100% 0 0);
    }
    .stat-trend .trend-fill {
      fill: rgba(255,255,255,0.04);
      opacity: 1;
    }
    .stat-trend .trend-line {
      fill: none;
      stroke: rgba(255,255,255,0.95);
      stroke-width: 1;
      vector-effect: non-scaling-stroke;
      stroke-linecap: round;
      stroke-linejoin: round;
      opacity: 1;
    }
    details.stat-card {
      padding: 0;
      overflow: clip;
    }
    .stat-summary {
      list-style: none;
      cursor: pointer;
      padding: 12px 13px;
    }
    .stat-summary::-webkit-details-marker { display: none; }
    .stat-breakdown {
      display: grid;
      gap: 8px;
      padding: 0 13px 12px;
      border-top: 0.5px solid var(--line);
    }
    .stat-breakdown-group {
      display: grid;
      gap: 8px;
    }
    .stat-breakdown-heading {
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .stat-breakdown-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      font-size: 13px;
      line-height: 1.4;
    }
    .stat-breakdown-label {
      color: var(--muted);
      text-transform: capitalize;
    }
    .stat-breakdown-value {
      color: var(--fg);
      font-variant-numeric: tabular-nums;
    }
    .stat-label {
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    .stat-value {
      font-size: 24px;
      line-height: 1;
      letter-spacing: -0.03em;
      font-weight: 600;
    }
    .stat-note {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      margin-top: 6px;
    }
    .list {
      display: grid;
      gap: 10px;
    }
    .section-block {
      display: grid;
      gap: 10px;
    }
    .section-label {
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 6px 2px 0;
    }
    .unhealthy-banner {
      background: rgba(255, 69, 58, 0.12);
      border: 0.5px solid rgba(255, 69, 58, 0.3);
      color: rgb(255, 69, 58);
      border-radius: 12px;
      padding: 12px 16px;
      margin-bottom: 18px;
      font-size: 13px;
      line-height: 1.5;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .unhealthy-icon {
      flex-shrink: 0;
      width: 20px;
      height: 20px;
      background: rgb(255, 69, 58);
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 14px;
    }
    .session-card {
      display: block;
      text-decoration: none;
      color: inherit;
      background: rgb(18, 18, 20);
      border: 0.5px solid var(--line);
      border-radius: 16px;
      padding: 16px 18px 15px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
      transition: transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1), box-shadow 0.2s ease, border-color 0.2s ease, opacity 0.2s ease;
      view-transition-name: var(--vt-name, none);
    }
    .session-card.navigating {
      opacity: 0.5;
      transform: scale(0.98);
      pointer-events: none;
    }
    ::view-transition-group(session-card-expand) {
      animation-duration: 0.4s;
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    .session-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
      border-color: var(--line-strong);
    }
    .active-card {
      cursor: pointer;
    }
    .archived-card {
      padding: 0;
      overflow: clip;
    }
    .session-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
    }
    .session-tools {
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      gap: 12px;
    }
    .archived-summary {
      list-style: none;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 14px 13px;
      cursor: pointer;
    }
    .archived-summary::-webkit-details-marker {
      display: none;
    }
    .archived-card[open] .archived-summary {
      border-bottom: 0.5px solid var(--line);
    }
    .archived-body {
      display: block;
      padding: 12px 14px 13px;
      color: inherit;
      text-decoration: none;
    }
    .archived-body > * + * {
      margin-top: 10px;
    }
    .session-name {
      font-size: 13px;
      line-height: 1.25;
      font-weight: 500;
      letter-spacing: -0.01em;
      min-width: 0;
      word-break: break-word;
    }
    .badge {
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 5px 8px;
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      border: 0.5px solid var(--line-strong);
      color: var(--muted);
    }
    .badge.idle { color: var(--ok); }
    .badge.attached { color: var(--warn); }
    .badge.degraded { color: var(--bad); }
    .path {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      margin-bottom: 10px;
      min-width: 0;
    }
    .path-marquee {
      position: relative;
      overflow: hidden;
      white-space: nowrap;
    }
    .path-marquee-track {
      display: inline-flex;
      align-items: center;
      gap: 0;
      min-width: 100%;
    }
    .path-marquee-text {
      flex: 0 0 auto;
      display: inline-block;
      padding-right: 0;
    }
    .path-marquee.is-overflowing .path-marquee-track {
      width: max-content;
      animation: sessionPathMarquee var(--path-marquee-duration, 18s) linear infinite;
    }
    .path-marquee.is-overflowing .path-marquee-text {
      padding-right: 44px;
    }
    @keyframes sessionPathMarquee {
      from { transform: translateX(0); }
      to { transform: translateX(calc(-1 * var(--path-marquee-distance, 0px))); }
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    .meta strong {
      color: var(--fg);
      font-weight: 500;
    }
    .card-link {
      display: inline-flex;
      align-items: center;
      min-height: auto;
      padding: 5px 8px;
      border-radius: 10px;
      border: 0.5px solid var(--line-strong);
      background: var(--panel-2);
      color: var(--fg);
      text-decoration: none;
      font-size: 11px;
      line-height: 1;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      transition: color 140ms ease, border-color 140ms ease, background 140ms ease;
    }
    .card-link.danger {
      color: var(--bad);
      background: var(--panel-2);
      border-color: rgba(214, 124, 124, 0.28);
    }
    .card-link.danger:hover {
      color: rgb(232, 146, 146);
      background: rgb(36, 30, 30);
      border-color: rgba(214, 124, 124, 0.4);
    }
    .empty {
      padding: 22px 16px;
      border-radius: 16px;
      background: var(--panel);
      border: 0.5px solid var(--line);
      color: var(--muted);
      line-height: 1.6;
    }
    .hub-view-resume #stats {
      display: none;
    }
    .hub-view-resume #activityWrap {
      display: none !important;
    }
    .hub-view-stats #list {
      display: none;
    }
    /* ── Card → flat row (all viewports) ── */
    .hub-nav { display: none !important; }
    .list { gap: 0; }
    .section-block { gap: 0; }
    .session-card {
      background: transparent !important;
      border: none !important;
      border-bottom: 0.5px solid var(--line) !important;
      border-radius: 0 !important;
      padding: 12px 0 !important;
    }
    .section-label + .session-card,
    .section-label + .empty { border-top: 0.5px solid var(--line) !important; }
    .archived-card {
      background: transparent !important;
      border: none !important;
      border-bottom: 0.5px solid var(--line) !important;
      border-radius: 0 !important;
      overflow: visible !important;
      padding: 0 !important;
    }
    .archived-summary { padding: 12px 0 !important; }
    .archived-card[open] .archived-summary { border-bottom: none; }
    .archived-body { padding: 0 0 12px !important; }
    .empty {
      background: transparent !important;
      border: none !important;
      border-bottom: 0.5px solid var(--line) !important;
      border-radius: 0 !important;
    }
    .card-link { background: transparent; }
    /* ── Stats grid → flat list ── */
    .stats-grid { display: block !important; gap: 0 !important; }
    .stats-column { display: block; }
    .stat-card {
      background: transparent !important;
      border: none !important;
      border-bottom: 0.5px solid var(--line) !important;
      border-radius: 0 !important;
      padding: 10px 0 !important;
      overflow: visible !important;
    }
    .stats-column:first-child .stat-card:first-child { border-top: 0.5px solid var(--line) !important; }
    details.stat-card { padding: 0 !important; }
    .stat-summary { padding: 10px 0 !important; }
    .stat-breakdown { padding: 0 0 10px !important; border-top: none; }
    .activity-grid-wrap { margin-bottom: 14px; }
    @keyframes hubRestartingPulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    .hub-nav button.restarting {
      animation: hubRestartingPulse 900ms ease-in-out infinite;
      pointer-events: none;
    }
    /* ── Black Hole overrides ───────────────────────────────────────────── */
    html[data-theme="black-hole"] .session-card,
    html[data-theme="black-hole"] .stat-card,
    html[data-theme="black-hole"] .empty,
    html[data-theme="black-hole"] .hub-nav a,
    html[data-theme="black-hole"] .hub-restart-form button,
    html[data-theme="black-hole"] .setting-item,
    html[data-theme="black-hole"] .new-session-form,
    html[data-theme="black-hole"] .home-card,
    html[data-theme="black-hole"] .panel,
    html[data-theme="black-hole"] input[type="text"],
    html[data-theme="black-hole"] input[type="number"],
    html[data-theme="black-hole"] select,
    html[data-theme="black-hole"] textarea {
      background: linear-gradient(145deg, rgb(20, 20, 20) 0%, rgb(10, 10, 10) 100%) !important;
      backdrop-filter: blur(20px) saturate(160%) !important;
      -webkit-backdrop-filter: blur(20px) saturate(160%) !important;
      border: 0.5px solid rgba(255, 255, 255, 0.1) !important;
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8) !important;
    }
    html[data-theme="black-hole"] .hub-nav a.active {
      background: var(--bg) !important;
      border-color: rgba(255, 255, 255, 0.2) !important;
    }
    html[data-theme="black-hole"] .activity-cell[data-level="1"] { background: rgba(252,252,252,0.25); }
    html[data-theme="black-hole"] .activity-cell[data-level="2"] { background: rgba(252,252,252,0.50); }
    html[data-theme="black-hole"] .activity-cell[data-level="3"] { background: rgba(252,252,252,0.75); }
    html[data-theme="black-hole"] .activity-cell[data-level="4"] { background: rgba(252,252,252,1.00); }
    html[data-theme="black-hole"] .activity-cell.thinking[data-level="1"] { background: rgba(252,252,252,0.25); }
    html[data-theme="black-hole"] .activity-cell.thinking[data-level="2"] { background: rgba(252,252,252,0.50); }
    html[data-theme="black-hole"] .activity-cell.thinking[data-level="3"] { background: rgba(252,252,252,0.75); }
    html[data-theme="black-hole"] .activity-cell.thinking[data-level="4"] { background: rgba(252,252,252,1.00); }
    html[data-theme="soft-light"] .activity-cell[data-level="1"] { background: rgba(15,20,30,0.16); }
    html[data-theme="soft-light"] .activity-cell[data-level="2"] { background: rgba(15,20,30,0.30); }
    html[data-theme="soft-light"] .activity-cell[data-level="3"] { background: rgba(15,20,30,0.48); }
    html[data-theme="soft-light"] .activity-cell[data-level="4"] { background: rgba(15,20,30,0.68); }
    html[data-theme="soft-light"] .activity-cell.thinking[data-level="1"] { background: rgba(25,75,140,0.18); }
    html[data-theme="soft-light"] .activity-cell.thinking[data-level="2"] { background: rgba(25,75,140,0.30); }
    html[data-theme="soft-light"] .activity-cell.thinking[data-level="3"] { background: rgba(25,75,140,0.46); }
    html[data-theme="soft-light"] .activity-cell.thinking[data-level="4"] { background: rgba(25,75,140,0.62); }
    .activity-cell:hover::after {
      background: rgba(0, 0, 0, 0.95);
    }
    .stat-trend .trend-fill {
      fill: rgba(255,255,255,0.045);
    }
    .stat-trend .trend-line {
      stroke: rgba(255,255,255,0.96);
      stroke-width: 1.1;
    }
    .card-link.danger:hover {
      background: rgb(10, 4, 4);
    }
    html[data-theme="soft-light"] .session-card,
    html[data-theme="soft-light"] .archived-card,
    html[data-theme="soft-light"] .stat-card,
    html[data-theme="soft-light"] .empty,
    html[data-theme="soft-light"] .hub-nav a,
    html[data-theme="soft-light"] .hub-restart-form button,
    html[data-theme="soft-light"] .setting-item,
    html[data-theme="soft-light"] .new-session-form,
    html[data-theme="soft-light"] .home-card,
    html[data-theme="soft-light"] .panel,
    html[data-theme="soft-light"] input[type="text"],
    html[data-theme="soft-light"] input[type="number"],
    html[data-theme="soft-light"] select,
    html[data-theme="soft-light"] textarea {
      background: linear-gradient(145deg, rgb(255, 255, 255) 0%, rgb(246, 246, 244) 100%) !important;
      border: 0.5px solid rgba(15, 20, 30, 0.14) !important;
      box-shadow: 0 8px 24px rgba(15, 20, 30, 0.08) !important;
      backdrop-filter: none !important;
      -webkit-backdrop-filter: none !important;
      color: var(--fg) !important;
    }
    html[data-theme="soft-light"] .home-card::before {
      background: radial-gradient(circle at top left, rgba(15, 20, 30, 0.05), transparent 60%);
    }
    #starfield {
      position: fixed;
      top: 0;
      left: 0;
      z-index: 1;
      width: 100%;
      height: 100%;
      display: none;
      pointer-events: none;
    }
    :not([data-starfield="off"]) #starfield {
      display: block;
    }
    :not([data-starfield="off"]) body {
      background: transparent !important;
    }
    :not([data-starfield="off"]) html {
      background: var(--bg) !important;
    }
    :not([data-starfield="off"]) .shell {
      background: transparent !important;
      position: relative;
      z-index: 2;
    }
    /* Black Hole: cancel glass effect on flat rows */
    html[data-theme="black-hole"] .session-card,
    html[data-theme="black-hole"] .archived-card,
    html[data-theme="black-hole"] .stat-card,
    html[data-theme="black-hole"] .empty {
      background: transparent !important;
      backdrop-filter: none !important;
      -webkit-backdrop-filter: none !important;
      border: none !important;
      border-bottom: 0.5px solid rgba(255,255,255,0.08) !important;
      box-shadow: none !important;
      border-radius: 0 !important;
    }
    html[data-theme="black-hole"] .section-label + .session-card,
    html[data-theme="black-hole"] .section-label + .empty,
    html[data-theme="black-hole"] .stats-column:first-child .stat-card:first-child {
      border-top: 0.5px solid rgba(255,255,255,0.08) !important;
    }
    /* Stats: hide home-duplicated cards, show remaining large and centered */
    .hub-view-stats [data-stat-key="activated-agents"] { display: none !important; }
    .hub-view-stats .stat-card { text-align: center !important; padding: 32px 0 !important; }
    .hub-view-stats .stat-label {
      font-size: 13px !important;
      opacity: 0.6 !important;
      margin-bottom: 8px !important;
      text-transform: uppercase !important;
      letter-spacing: 0.06em !important;
    }
    .hub-view-stats .stat-value {
      font-family: 'Inter', system-ui, sans-serif !important;
      font-size: 52px !important;
      font-weight: 700 !important;
      font-style: normal !important;
      letter-spacing: -0.03em !important;
      line-height: 1 !important;
      display: block !important;
    }
    .hub-view-stats .stat-note { display: none !important; }
    .hub-view-stats .stat-content { padding: 0 14px; }
    .hub-view-stats .stat-trend { inset: 8px 0 0 0; }
    .hub-view-stats details.stat-card > summary { justify-content: center !important; }
    .hub-view-stats details.stat-card > summary .stat-value { display: block !important; }
    .hub-view-stats .stat-card, .hub-view-stats details.stat-card > summary { -webkit-tap-highlight-color: transparent; }
    @keyframes statBreakdownIn {
      0%   { opacity: 0; transform: translateY(-14px); }
      100% { opacity: 1; transform: translateY(0); }
    }
    .hub-view-stats details[open] .stat-breakdown {
      animation: statBreakdownIn 180ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    html[data-theme="soft-light"] .hub-view-stats .stat-trend {
      display: none !important;
    }
  __HUB_HEADER_CSS__
  </style>
</head>
<body class="hub-view-__HUB_VIEW__">
  <canvas id="starfield"></canvas>
  <div class="shell">
    __HUB_HEADER_HTML__
    <section class="hero">
      <div class="eyebrow">multiagent</div>
      <h1>__HUB_TITLE__</h1>
      <div class="hub-nav">
        <a href="/" class="__HUB_NAV_HOME__">Hub</a>
        <a href="/new-session" class="__HUB_NAV_NEW__">New Session</a>
        <a href="/resume" class="__HUB_NAV_RESUME__">Resume Sessions</a>
        <a href="/stats" class="__HUB_NAV_STATS__">Statistics</a>
        <a href="/settings" class="__HUB_NAV_SETTINGS__">Settings</a>
        <form class="hub-restart-form" method="post" action="/restart-hub"><button type="submit">Restart Hub</button></form>
      </div>
    </section>
    <div class="stats-grid" id="stats"></div>
    <div class="activity-grid-wrap" id="activityWrap" style="display:none">
      <div class="activity-filter-row" id="activityFilterRow">
        <button type="button" class="activity-filter-btn active" data-scope="all">All</button>
        <button type="button" class="activity-filter-btn" data-scope="agent">Agent</button>
        <button type="button" class="activity-filter-btn" data-scope="user">User</button>
      </div>
      <div class="activity-filter-note">Switch the message heatmap between all non-system traffic, agent-only output, and user-only prompts. Thinking time stays repo-wide.</div>
      <div class="activity-grid-label">Messages per day</div>
      <div class="activity-month-labels" id="activityMonthLabels"></div>
      <div class="activity-grid" id="activityGrid"></div>
      <div class="activity-grid-label" style="margin-top:14px">Thinking time per day</div>
      <div class="activity-grid" id="thinkingGrid"></div>
    </div>
    <div class="list" id="list"></div>
  </div>
  <script>
    const list = document.getElementById("list");
    const stats = document.getElementById("stats");
    const activityFilterRow = document.getElementById("activityFilterRow");
    const openArchived = new Set();
    const openStatCards = new Set();
    let activityScope = "all";
    const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[char]));
    const renderPathMarquee = (workspace) => {
      const path = escapeHtml(workspace || "workspace unavailable");
      return `<div class="path path-marquee" data-path-marquee title="${path}"><div class="path-marquee-track"><span class="path-marquee-text">${path}</span><span class="path-marquee-text" aria-hidden="true">${path}</span></div></div>`;
    };
    const refreshPathMarquees = () => {
      requestAnimationFrame(() => {
        document.querySelectorAll("[data-path-marquee]").forEach((node) => {
          const first = node.querySelector(".path-marquee-text");
          if (!first) return;
          node.classList.remove("is-overflowing");
          node.style.removeProperty("--path-marquee-distance");
          node.style.removeProperty("--path-marquee-duration");
          const overflow = Math.ceil(first.scrollWidth) > Math.ceil(node.clientWidth + 2);
          if (!overflow) return;
          const distance = Math.ceil(first.scrollWidth + 44);
          const duration = Math.max(10, distance / 32);
          node.classList.add("is-overflowing");
          node.style.setProperty("--path-marquee-distance", `${distance}px`);
          node.style.setProperty("--path-marquee-duration", `${duration}s`);
        });
      });
    };
    const renderActiveCards = (sessions, { href, emptyText, showUpdated = false } = {}) => {
      if (!sessions.length) {
        return `<div class="empty">${escapeHtml(emptyText)}</div>`;
      }
      return sessions.map((session) => {
        const agents = session.agents.length ? session.agents.join(", ") : "none";
        const dead = session.dead_panes ? `, ${session.dead_panes} dead pane${session.dead_panes === 1 ? "" : "s"}` : "";
        const timeLabel = showUpdated ? "Updated" : "Created";
        const timeValue = showUpdated ? (session.updated_at || "unknown") : (session.created_at || "unknown");
        const chatCount = Number(session.chat_count || 0);
        return `
          <div class="session-card active-card" data-open-href="${href(session)}" role="link" tabindex="0">
            <div class="session-head">
              <div class="session-name">${escapeHtml(session.name)}</div>
              <div class="session-tools">
                <div class="badge ${escapeHtml(session.status)}">${escapeHtml(session.status)}</div>
                <a class="card-link danger" href="/kill-session?session=${encodeURIComponent(session.name)}">Kill</a>
              </div>
            </div>
            ${renderPathMarquee(session.workspace)}
            <div class="meta">
              <span><strong>Agents</strong> ${escapeHtml(agents)}</span>
              <span><strong>${timeLabel}</strong> ${escapeHtml(timeValue)}</span>
              <span><strong>Chats</strong> ${escapeHtml(chatCount)}</span>
              <span><strong>Address</strong> :${escapeHtml(session.chat_port)}</span>
              <span><strong>State</strong> ${escapeHtml(session.status)}${escapeHtml(dead)}</span>
            </div>
          </div>`;
      }).join("");
    };
    const renderArchivedCards = (sessions) => {
      if (!sessions.length) {
        return `<div class="empty">No archived sessions with reusable logs were found yet.</div>`;
      }
      return sessions.map((session) => {
        const agents = session.agents.length ? session.agents.join(", ") : "none";
        const isOpen = openArchived.has(session.name) ? " open" : "";
        const chatCount = Number(session.chat_count || 0);
        return `
          <details class="session-card archived-card"${isOpen} data-session-name="${escapeHtml(session.name)}">
            <summary class="archived-summary">
              <div class="session-name">${escapeHtml(session.name)}</div>
              <div class="badge archived">archived</div>
            </summary>
            <a class="archived-body" href="/revive-session?session=${encodeURIComponent(session.name)}">
              ${renderPathMarquee(session.workspace)}
              <div class="meta">
                <span><strong>Agents</strong> ${escapeHtml(agents)}</span>
                <span><strong>Updated</strong> ${escapeHtml(session.updated_at || "unknown")}</span>
                <span><strong>Chats</strong> ${escapeHtml(chatCount)}</span>
                <span><strong>Address</strong> :${escapeHtml(session.chat_port)}</span>
              </div>
            </a>
          </details>`;
      }).join("");
    };
    const renderStats = (statsData = {}) => {
      const ACTIVATED_AGENT_THRESHOLD = 10;
      const formatStatDuration = (seconds) => {
        const total = Math.max(0, Number(seconds || 0));
        if (total < 60) return `${Math.round(total)}s`;
        const mins = Math.floor(total / 60);
        const secs = Math.floor(total % 60);
        const hours = Math.floor(mins / 60);
        if (hours > 0) {
          const restMins = mins % 60;
          return `${hours}h ${restMins}m ${secs}s`;
        }
        return `${mins}m ${secs}s`;
      };
      const formatLabel = (value) => String(value || "").replace(/(^|-)([a-z])/g, (_, prefix, char) => `${prefix}${char.toUpperCase()}`);
      const buildTrendSvg = (series = []) => {
        if (!series.length) return "";
        const values = series.map((point) => Math.max(0, Number(point.value || 0)));
        const width = 320;
        const height = 124;
        const padX = 0;
        const padY = 12;
        const maxVal = Math.max(...values, 1);
        const minVal = Math.min(...values, 0);
        const usableW = width - padX * 2;
        const usableH = height - padY * 2;
        const points = values.map((value, index) => {
          const x = padX + (values.length === 1 ? usableW / 2 : (usableW * index) / (values.length - 1));
          const ratio = maxVal === minVal ? 0.5 : (value - minVal) / (maxVal - minVal);
          const y = height - padY - ratio * usableH;
          return [x, y];
        });
        const linePath = points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
        const areaPath = `${linePath} L ${points[points.length - 1][0].toFixed(2)} ${(height - padY).toFixed(2)} L ${points[0][0].toFixed(2)} ${(height - padY).toFixed(2)} Z`;
        return `<div class="stat-trend" aria-hidden="true"><svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"><path class="trend-fill" d="${areaPath}"></path><path class="trend-line" pathLength="100" d="${linePath}"></path></svg></div>`;
      };
      const sortedCountRows = (source = {}, formatter = (value) => String(value), labelMapper = (value) => value) =>
        Object.entries(source)
          .filter(([, value]) => Number(value || 0) > 0)
          .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
          .map(([label, value]) => ({
            label: labelMapper(label),
            value: formatter(value),
          }));
      const messageSenderRows = ["user", __ALL_AGENT_NAMES_JS__]
        .map((key) => ({ label: formatLabel(key), value: Number((statsData.messages_by_sender || {})[key] || 0) }))
        .filter((item) => item.value > 0)
        .map((item) => ({ label: item.label, value: String(item.value) }));
      const activatedAgentCount = [__ALL_AGENT_NAMES_JS__]
        .filter((key) => Number((statsData.messages_by_sender || {})[key] || 0) >= ACTIVATED_AGENT_THRESHOLD)
        .length;
      const messageSessionRows = sortedCountRows(statsData.messages_by_session || {}, (value) => String(value), (label) => label);
      const commitSessionRows = sortedCountRows(statsData.commits_by_session || {}, (value) => String(value), (label) => label);
      const thinkingAgentRows = Object.entries(statsData.thinking_by_agent || {})
        .filter(([, value]) => Number(value || 0) > 0)
        .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
        .map(([agent, value]) => ({
          label: formatLabel(agent),
          value: formatStatDuration(value),
        }));
      const thinkingSessionRows = Object.entries(statsData.thinking_by_session || {})
        .filter(([, value]) => Number((value || {}).seconds || 0) > 0)
        .sort((a, b) => Number((b[1] || {}).seconds || 0) - Number((a[1] || {}).seconds || 0))
        .map(([session, value]) => ({
          label: session,
          value: formatStatDuration((value || {}).seconds || 0),
        }));
      const cards = [
        {
          label: "Messages",
          value: Number(statsData.total_messages || 0),
          note: "Non-system messages across all stored sessions",
          key: "messages",
          trend: statsData.cumulative_messages_all || [],
          sections: [
            { label: "By sender", rows: messageSenderRows },
            { label: "By session", rows: messageSessionRows },
          ].filter((section) => section.rows.length)
        },
        {
          label: "Thinking Time",
          value: formatStatDuration(statsData.total_thinking_seconds || 0),
          note: thinkingAgentRows.length
            ? `Cumulative agent runtime across ${Number(statsData.thinking_session_count || 0)} session${Number(statsData.thinking_session_count || 0) === 1 ? "" : "s"}`
            : "No recorded runtime yet",
          key: "thinking-time",
          trend: statsData.cumulative_thinking || [],
          sections: [
            { label: "By agent", rows: thinkingAgentRows },
            { label: "By session", rows: thinkingSessionRows },
          ].filter((section) => section.rows.length)
        },
        {
          label: "Activated Agents",
          value: activatedAgentCount,
          note: `Agents with ${ACTIVATED_AGENT_THRESHOLD}+ messages`
        },
        {
          label: "Commits",
          value: Number(statsData.total_commits || 0),
          note: "Unique commits deduped across stored sessions",
          key: "commits",
          trend: statsData.cumulative_commits || [],
          sections: [
            { label: "By session", rows: commitSessionRows },
          ].filter((section) => section.rows.length)
        }
      ];
      const renderCard = (card) => {
        if (!card.sections || !card.sections.length) {
          const statKey = card.key || card.label.toLowerCase().replace(/\s+/g, "-");
          return `
            <div class="stat-card" data-stat-key="${escapeHtml(statKey)}">
              ${buildTrendSvg(card.trend || [])}
              <div class="stat-content">
                <div class="stat-label">${escapeHtml(card.label)}</div>
                <div class="stat-value">${escapeHtml(card.value)}</div>
                <div class="stat-note">${escapeHtml(card.note)}</div>
              </div>
            </div>
          `;
        }
        const open = openStatCards.has(card.key) ? " open" : "";
        return `
          <details class="stat-card"${open} data-stat-key="${escapeHtml(card.key)}">
            ${buildTrendSvg(card.trend || [])}
            <summary class="stat-summary">
              <div class="stat-content">
                <div class="stat-label">${escapeHtml(card.label)}</div>
                <div class="stat-value">${escapeHtml(card.value)}</div>
                <div class="stat-note">${escapeHtml(card.note)}</div>
              </div>
            </summary>
            <div class="stat-breakdown">
              ${card.sections.map((section) => `
                <div class="stat-breakdown-group">
                  <div class="stat-breakdown-heading">${escapeHtml(section.label)}</div>
                  ${section.rows.map((item) => `
                    <div class="stat-breakdown-row">
                      <div class="stat-breakdown-label">${escapeHtml(item.label)}</div>
                      <div class="stat-breakdown-value">${escapeHtml(item.value)}</div>
                    </div>
                  `).join("")}
                </div>
              `).join("")}
            </div>
          </details>
        `;
      };
      const columns = [[], []];
      cards.forEach((card, index) => {
        columns[index % 2].push(renderCard(card));
      });
      stats.innerHTML = columns.map((cardsHtml) => `
        <div class="stats-column">
          ${cardsHtml.join("")}
        </div>
      `).join("");
      const animateStatTrends = () => {
        stats.querySelectorAll(".stat-trend").forEach((node) => {
          const svg = node.querySelector("svg");
          if (svg) {
            svg.getAnimations().forEach((anim) => anim.cancel());
            svg.style.clipPath = "inset(0 100% 0 0)";
            svg.animate(
              [
                { clipPath: "inset(0 100% 0 0)" },
                { clipPath: "inset(0 0 0 0)" },
              ],
              {
                duration: 2800,
                delay: 40,
                easing: "cubic-bezier(0.22, 1, 0.36, 1)",
                fill: "forwards",
              },
            );
          }
        });
      };
      requestAnimationFrame(animateStatTrends);
      stats.querySelectorAll("details[data-stat-key]").forEach((node) => {
        node.addEventListener("toggle", () => {
          const key = node.dataset.statKey;
          if (!key) return;
          if (node.open) openStatCards.add(key);
          else openStatCards.delete(key);
        });
      });
    };
    const renderActivityGrid = (statsData = {}) => {
      const wrap = document.getElementById("activityWrap");
      const grid = document.getElementById("activityGrid");
      const thinkingGrid = document.getElementById("thinkingGrid");
      const monthLabels = document.getElementById("activityMonthLabels");
      if (!wrap || !grid) return;
      const scopeMap = {
        all: statsData.daily_messages_all || statsData.daily_messages || {},
        agent: statsData.daily_messages_agent || {},
        user: statsData.daily_messages_user || {},
      };
      const dailyMessages = scopeMap[activityScope] || scopeMap.all;
      const dailyThinking = statsData.daily_thinking || {};
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const year = today.getFullYear();
      // Start from the Sunday on or before Jan 1 of current year
      const jan1 = new Date(year, 0, 1);
      const startDate = new Date(jan1);
      startDate.setDate(jan1.getDate() - jan1.getDay());
      const dec31 = new Date(year, 11, 31);
      // Total weeks needed to cover Jan 1 through Dec 31
      const msPerWeek = 7 * 24 * 3600 * 1000;
      const WEEKS = Math.ceil((dec31 - startDate) / msPerWeek) + 1;
      const pad = (n) => String(n).padStart(2, "0");
      const toKey = (d) => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
      const MONTH_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
      const buildLevel = (data) => {
        const maxVal = Math.max(1, ...Object.values(data).map(Number));
        return (n) => {
          if (!n) return 0;
          if (n <= maxVal * 0.15) return 1;
          if (n <= maxVal * 0.40) return 2;
          if (n <= maxVal * 0.70) return 3;
          return 4;
        };
      };
      const fmtDur = (s) => {
        s = Math.round(s);
        if (s < 60) return `${s}s`;
        const m = Math.floor(s / 60), h = Math.floor(m / 60);
        return h > 0 ? `${h}h ${m % 60}m` : `${m}m`;
      };
      const weeks = [];
      const monthLabelData = [];
      let prevMonth = -1;
      for (let w = 0; w < WEEKS; w++) {
        const weekCells = [];
        for (let d = 0; d < 7; d++) {
          const date = new Date(startDate);
          date.setDate(startDate.getDate() + w * 7 + d);
          // Skip days outside current year or in the future
          if (date.getFullYear() !== year || date > today) { weekCells.push(null); continue; }
          const key = toKey(date);
          weekCells.push({ key, date: new Date(date) });
          if (d === 0 && date.getMonth() !== prevMonth) {
            monthLabelData.push({ week: w, month: date.getMonth() });
            prevMonth = date.getMonth();
          }
        }
        weeks.push(weekCells);
      }
      monthLabels.innerHTML = weeks.map((_, w) => {
        const lbl = monthLabelData.find((m) => m.week === w);
        return `<div class="activity-month-label">${lbl ? MONTH_SHORT[lbl.month] : ""}</div>`;
      }).join("");
      const levelMsg = buildLevel(dailyMessages);
      grid.innerHTML = weeks.map((weekCells) =>
        `<div class="activity-week">${weekCells.map((cell) => {
          if (!cell) return `<div class="activity-cell"></div>`;
          const count = Number(dailyMessages[cell.key] || 0);
          const tip = count ? `${cell.key}: ${count} msg` : cell.key;
          return `<div class="activity-cell" data-level="${levelMsg(count)}" data-tip="${tip}"></div>`;
        }).join("")}</div>`
      ).join("");
      if (thinkingGrid) {
        const levelThink = buildLevel(dailyThinking);
        thinkingGrid.innerHTML = weeks.map((weekCells) =>
          `<div class="activity-week">${weekCells.map((cell) => {
            if (!cell) return `<div class="activity-cell thinking"></div>`;
            const secs = Number(dailyThinking[cell.key] || 0);
            const tip = secs ? `${cell.key}: ${fmtDur(secs)}` : cell.key;
            return `<div class="activity-cell thinking" data-level="${levelThink(secs)}" data-tip="${tip}"></div>`;
          }).join("")}</div>`
        ).join("");
      }
      wrap.style.display = Object.keys(dailyMessages).length ? "" : "none";
      if (activityFilterRow) {
        activityFilterRow.querySelectorAll("[data-scope]").forEach((btn) => {
          btn.classList.toggle("active", btn.dataset.scope === activityScope);
        });
      }
    };
    const render = (activeSessions, archivedSessions, statsData, tmuxState, tmuxDetail) => {
      const activeCount = activeSessions.length;
      const archivedCount = archivedSessions.length;
      const totalMessages = Number(statsData.total_messages || 0);
      window._lastStatsData = statsData;
      renderStats(statsData);
      renderActivityGrid(statsData);

      let bannerHtml = "";
      if (tmuxState === "unhealthy") {
        bannerHtml = `
          <div class="unhealthy-banner">
            <div class="unhealthy-icon">!</div>
            <div>
              <strong>System Unstable:</strong> ${escapeHtml(tmuxDetail || "tmux is unresponsive")}<br>
              <span style="opacity:0.8;font-size:12px">Automatic recovery is paused to prevent double-startup. Please wait.</span>
            </div>
          </div>`;
      }

      list.innerHTML = `
        ${bannerHtml}
        <section class="section-block">
          <div class="section-label">Active Sessions</div>
          ${renderActiveCards(activeSessions, {
            href: (session) => `/open-session?session=${encodeURIComponent(session.name)}&ts=${Date.now()}`,
            emptyText: "No active multiagent tmux sessions were found for this repo.",
            showUpdated: false
          })}
        </section>
        <section class="section-block">
          <div class="section-label">Archived Sessions</div>
          ${renderArchivedCards(archivedSessions)}
        </section>`;
      list.querySelectorAll(".archived-card").forEach((item) => {
        item.addEventListener("toggle", () => {
          const name = item.dataset.sessionName || "";
          if (!name) return;
          if (item.open) openArchived.add(name);
          else openArchived.delete(name);
        });
      });
      list.querySelectorAll(".active-card").forEach((item) => {
        const openHref = item.dataset.openHref || "";
        if (!openHref) return;
        const navigateWithTransition = () => {
          if (document.startViewTransition) {
            item.style.setProperty("--vt-name", "session-card-expand");
            document.startViewTransition(() => {
              item.classList.add("navigating");
              window.location.href = openHref;
            });
          } else {
            item.classList.add("navigating");
            window.location.href = openHref;
          }
        };
        item.addEventListener("click", (event) => {
          if (event.target.closest("a, button, summary")) return;
          navigateWithTransition();
        });
        item.addEventListener("keydown", (event) => {
          if (event.target !== item) return;
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          navigateWithTransition();
        });
      });
      refreshPathMarquees();
    };
    const refresh = async () => {
      try {
        const res = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) throw new Error("failed to load sessions");
        const data = await res.json();

        // Prevent layout thrashing and animation re-triggering if data hasn't changed
        const sig = JSON.stringify({
          active: data.active_sessions || data.sessions || [],
          archived: data.archived_sessions || [],
          stats: data.stats || {},
          tmux_state: data.tmux_state || "ok",
        });
        if (window._lastRenderSig === sig) return;
        window._lastRenderSig = sig;

        render(
          data.active_sessions || data.sessions || [],
          data.archived_sessions || [],
          data.stats || {},
          data.tmux_state || "ok",
          data.tmux_detail || ""
        );
      } catch (error) {
        summary.textContent = "Failed to load sessions";
        stats.innerHTML = "";
        list.innerHTML = `<div class="empty">${escapeHtml(error.message || "unknown error")}</div>`;
      }
    };
    refresh();
    setInterval(refresh, 5000);
    if (activityFilterRow) {
      activityFilterRow.addEventListener("click", (event) => {
        const btn = event.target.closest("[data-scope]");
        if (!btn) return;
        const nextScope = btn.dataset.scope || "all";
        if (nextScope === activityScope) return;
        activityScope = nextScope;
        if (window._lastStatsData) renderActivityGrid(window._lastStatsData);
      });
    }
    const hubRestartForm = document.querySelector(".hub-restart-form");
    if (hubRestartForm) {
      hubRestartForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = e.currentTarget.querySelector("button");
        if (btn.classList.contains("restarting")) return;
        btn.classList.add("restarting");
        btn.disabled = true;
        btn.textContent = "Restarting\u2026";
        try { await fetch("/restart-hub", { method: "POST" }); } catch (_) {}
        const started = Date.now();
        const poll = async () => {
          try {
            const res = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
            if (res.ok) { window.location.replace(window.location.pathname); return; }
          } catch (_) {}
          if (Date.now() - started < 20000) { setTimeout(poll, 500); } else { window.location.reload(); }
        };
        setTimeout(poll, 700);
      });
    }

    // --- Starfield Animation ---
    const starCanvas = document.getElementById("starfield");
    const starCtx = starCanvas.getContext("2d");
    let stars = [];
    let shootingStars = [];
    const numStars = 360;
    let starAnimationId;
    let isStarAnimationRunning = false;

    function resizeStarCanvas() {
      starCanvas.width = window.innerWidth;
      starCanvas.height = window.innerHeight;
      initStars();
    }
    function initStars() {
      const diagonal = Math.sqrt(starCanvas.width ** 2 + starCanvas.height ** 2);
      stars = Array.from({ length: numStars }, () => ({
        angle: Math.random() * Math.PI * 2,
        radius: Math.random() * diagonal,
        speed: Math.random() * 0.0003 + 0.00015,
        size: Math.random() * 1.2 + 0.5,
      }));
    }
    function spawnShootingStar() {
      if (shootingStars.length === 0 && Math.random() < 0.01) {
        shootingStars.push({
          x: Math.random() * starCanvas.width * 0.5,
          y: Math.random() * starCanvas.height * 0.5,
          vx: 3 + Math.random() * 2,
          vy: 1 + Math.random() * 1.5,
          life: 80,
          initialLife: 80,
        });
      }
    }
    function animateStars() {
      if (!isStarAnimationRunning) return;
      const centerX = starCanvas.width;
      const centerY = starCanvas.height;
      starCtx.fillStyle = "rgb(10, 10, 10)";
      starCtx.fillRect(0, 0, starCanvas.width, starCanvas.height);
      stars.forEach((star, i) => {
        star.angle += star.speed;
        const x = centerX + star.radius * Math.cos(star.angle);
        const y = centerY + star.radius * Math.sin(star.angle);
        const flicker = 0.4 + Math.abs(Math.sin(Date.now() * 0.0015 + i)) * 0.5;
        starCtx.beginPath();
        starCtx.fillStyle = `rgba(255, 255, 255, ${flicker})`;
        starCtx.arc(x, y, star.size, 0, Math.PI * 2);
        starCtx.fill();
      });
      spawnShootingStar();
      for (let i = shootingStars.length - 1; i >= 0; i--) {
        const s = shootingStars[i];
        const opacity = s.life / s.initialLife;
        const grad = starCtx.createLinearGradient(s.x, s.y, s.x - s.vx * 35, s.y - s.vy * 35);
        grad.addColorStop(0, `rgba(255, 255, 255, ${opacity})`);
        grad.addColorStop(1, `rgba(255, 255, 255, 0)`);
        starCtx.strokeStyle = grad;
        starCtx.lineWidth = 2;
        starCtx.beginPath();
        starCtx.moveTo(s.x, s.y);
        starCtx.lineTo(s.x - s.vx * 18, s.y - s.vy * 18);
        starCtx.stroke();
        s.x += s.vx; s.y += s.vy; s.life -= 1;
        if (s.life <= 0) shootingStars.splice(i, 1);
      }
      starAnimationId = requestAnimationFrame(animateStars);
    }
    const updateStarAnimationState = () => {
      const shouldRun = document.documentElement.dataset.starfield !== "off";
      if (shouldRun && !isStarAnimationRunning) {
        isStarAnimationRunning = true;
        resizeStarCanvas();
        animateStars();
      } else if (!shouldRun && isStarAnimationRunning) {
        isStarAnimationRunning = false;
        cancelAnimationFrame(starAnimationId);
      }
    };
    window.addEventListener("resize", () => { if (isStarAnimationRunning) resizeStarCanvas(); });
    const themeObserver = new MutationObserver(updateStarAnimationState);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-starfield"] });
    updateStarAnimationState();
  __HUB_HEADER_JS__
  </script>
</body>
</html>
"""
_ALL_AGENT_NAMES_JS_ITEMS = ", ".join(f'"{n}"' for n in ALL_AGENT_NAMES)
HUB_APP_HTML = HUB_APP_HTML.replace("__ALL_AGENT_NAMES_JS__", _ALL_AGENT_NAMES_JS_ITEMS)

HUB_RESUME_HTML = (
    HUB_APP_HTML
    .replace("__HUB_MANIFEST_URL__", _PWA_HUB_MANIFEST_URL)
    .replace("__PWA_ICON_192_URL__", _PWA_ICON_192_URL)
    .replace("__APPLE_TOUCH_ICON_URL__", _PWA_APPLE_TOUCH_ICON_URL)
    .replace("__HUB_VIEW__", "resume")
    .replace("__HUB_TITLE__", "Resume Sessions")
    .replace("__HUB_NAV_HOME__", "")
    .replace("__HUB_NAV_RESUME__", "active")
    .replace("__HUB_NAV_STATS__", "")
    .replace("__HUB_NAV_SETTINGS__", "")
    .replace("__HUB_NAV_NEW__", "")
    .replace("__HUB_HEADER_CSS__", _HUB_PAGE_HEADER_CSS)
    .replace("__HUB_HEADER_HTML__", _HUB_PAGE_HEADER_HTML)
    .replace("__HUB_HEADER_JS__", _HUB_PAGE_HEADER_JS)
)

HUB_STATS_HTML = (
    HUB_APP_HTML
    .replace("__HUB_MANIFEST_URL__", _PWA_HUB_MANIFEST_URL)
    .replace("__PWA_ICON_192_URL__", _PWA_ICON_192_URL)
    .replace("__APPLE_TOUCH_ICON_URL__", _PWA_APPLE_TOUCH_ICON_URL)
    .replace("__HUB_VIEW__", "stats")
    .replace("__HUB_TITLE__", "Statistics")
    .replace("__HUB_NAV_HOME__", "")
    .replace("__HUB_NAV_RESUME__", "")
    .replace("__HUB_NAV_STATS__", "active")
    .replace("__HUB_NAV_SETTINGS__", "")
    .replace("__HUB_NAV_NEW__", "")
    .replace("__HUB_HEADER_CSS__", _HUB_PAGE_HEADER_CSS)
    .replace("__HUB_HEADER_HTML__", _HUB_PAGE_HEADER_HTML)
    .replace("__HUB_HEADER_JS__", _HUB_PAGE_HEADER_JS)
)

HUB_HOME_HTML = """<!doctype html>
<html lang="en" data-theme="__CHAT_THEME__"__STARFIELD_ATTR__>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="rgb(10, 10, 10)">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Session Hub">
  <link rel="manifest" href="__HUB_MANIFEST_URL__">
  <link rel="icon" type="image/png" sizes="192x192" href="__PWA_ICON_192_URL__">
  <link rel="apple-touch-icon" href="__APPLE_TOUCH_ICON_URL__">
  <script>
    (() => {
      if (!("serviceWorker" in navigator)) return;
      const isLocalHost = location.hostname === "localhost" || location.hostname === "127.0.0.1" || location.hostname === "[::1]";
      if (!(window.isSecureContext || isLocalHost)) return;
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/hub-service-worker.js", { scope: "/" }).catch((err) => {
          console.warn("hub service worker registration failed", err);
        });
      }, { once: true });
    })();
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap" rel="stylesheet">
  <title>Session Hub</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: rgb(10, 10, 10);
      --bg-rgb: 10, 10, 10;
      --panel: rgba(18, 18, 20, 0.7);
      --panel-2: rgba(25, 25, 28, 0.8);
      --line: rgba(255,255,255,0.06);
      --line-strong: rgba(255,255,255,0.12);
      --fg: rgb(245, 245, 245);
      --muted: rgb(140, 140, 145);
    }
    html[data-theme="soft-light"] {
      color-scheme: light;
      --bg: rgb(244, 244, 242);
      --bg-rgb: 244, 244, 242;
      --panel: rgba(255, 255, 255, 0.9);
      --panel-2: rgba(248, 248, 246, 0.95);
      --line: rgba(15, 20, 30, 0.12);
      --line-strong: rgba(15, 20, 30, 0.2);
      --fg: rgb(26, 30, 36);
      --muted: rgb(98, 106, 120);
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      min-height: 100%;
      background: var(--bg);
      color: var(--fg);
      font-family: "SF Pro Text", "Segoe UI", sans-serif;
    }
    body {
      padding: 0 0 max(20px, env(safe-area-inset-bottom)) 0;
    }
    .shell {
      max-width: 900px;
      margin: 0 auto;
    }
    .shell > :not(.hub-page-header):not(.mob-stats-bar):not(.mob-list-wrap) {
      padding-left: 14px;
      padding-right: 14px;
    }
    .hero {
      padding: 8px 2px 18px 2px;
    }
    .eyebrow {
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    h1 {
      margin: 0;
      font-size: clamp(28px, 5vw, 40px);
      line-height: 1.02;
      font-weight: 600;
      letter-spacing: -0.03em;
    }
    .sub {
      margin-top: 10px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
      max-width: 40rem;
    }
    .home-grid {
      display: grid;
      gap: 12px;
      margin-top: 8px;
    }
    .hub-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
      width: 100%;
      align-items: center;
    }
    .hub-nav a {
      color: var(--muted);
      text-decoration: none;
      border: 0.5px solid var(--line);
      background: var(--panel);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      line-height: 1;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .hub-nav form {
      margin: 0;
    }
    .hub-nav .hub-restart-form {
      margin-left: auto;
    }
    .hub-nav button {
      color: var(--muted);
      border: 0.5px solid var(--line);
      background: var(--panel);
      border-radius: 999px;
      padding: 6px 10px;
      font: inherit;
      font-size: 12px;
      font-weight: 400;
      line-height: 1;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      cursor: pointer;
      appearance: none;
      -webkit-appearance: none;
    }
    .hub-nav .hub-restart-form button { color: rgb(44, 132, 219); }
    @keyframes hubRestartingPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    .hub-nav button.restarting { animation: hubRestartingPulse 900ms ease-in-out infinite; pointer-events: none; }
    .home-card {
      display: block;
      text-decoration: none;
      color: inherit;
      background: var(--panel);
      border: 0.5px solid var(--line);
      border-radius: 20px;
      padding: 24px 22px 22px;
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15), inset 0 1px 1px rgba(255, 255, 255, 0.05);
      transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
      position: relative;
      overflow: hidden;
    }
    .home-card::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: radial-gradient(circle at top left, rgba(255,255,255,0.04), transparent 60%);
      opacity: 0;
      transition: opacity 0.3s ease;
      pointer-events: none;
    }
    .home-card:hover {
      transform: translateY(-4px) scale(1.01);
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.25), inset 0 1px 1px rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.15);
      background: var(--panel-2);
    }
    .home-card:hover::before {
      opacity: 1;
    }
    html[data-theme="soft-light"] .home-card {
      background: linear-gradient(145deg, rgb(255, 255, 255) 0%, rgb(246, 246, 244) 100%);
      border-color: rgba(15,20,30,0.14);
      box-shadow: 0 8px 24px rgba(15,20,30,0.08);
      color: var(--fg);
    }
    html[data-theme="soft-light"] .home-card:hover {
      background: rgb(248, 248, 246);
      border-color: rgba(15,20,30,0.2);
      box-shadow: 0 12px 28px rgba(15,20,30,0.12);
    }
    html[data-theme="soft-light"] .home-card .home-label,
    html[data-theme="soft-light"] .home-card .home-note {
      color: var(--muted);
    }
    html[data-theme="soft-light"] .home-card .home-title {
      color: var(--fg);
    }
    .home-label {
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    .home-title {
      font-size: 22px;
      line-height: 1.1;
      font-weight: 600;
      letter-spacing: -0.03em;
    }
    .home-note {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      margin-top: 10px;
      max-width: 34rem;
    }
    .hub-nav a.active {
      background: var(--bg) !important;
      border-color: rgba(255, 255, 255, 0.2) !important;
    }
    /* ── Hub home layout ── */
    body { padding: 0; }
    .hero, .home-grid, .hub-nav { display: none !important; }
    @keyframes mobSlideOutLeft {
      from { transform: translateX(0); opacity: 1; }
      to   { transform: translateX(-28%); opacity: 0; }
    }
    .mob-navigating { animation: mobSlideOutLeft 120ms cubic-bezier(0.4, 0, 0.6, 1) forwards; pointer-events: none; }
    __HUB_HEADER_CSS__
    .mob-stats-bar {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0;
      padding: 10px 14px 11px;
      border-bottom: 0.5px solid var(--line);
      border-top: none;
      font-size: 12px;
      color: var(--muted);
      max-width: 900px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
      background: color-mix(in srgb, var(--bg) 84%, transparent);
      position: relative;
      z-index: 2;
    }
    .mob-stats-bar .mob-stat {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 2px;
      min-width: 0;
    }
    .mob-stats-bar .mob-stat + .mob-stat {
      padding-left: 14px;
      border-left: 0.5px solid var(--line);
    }
    .mob-stats-bar .mob-stat-label {
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      white-space: nowrap;
    }
    .mob-stats-bar .mob-stat-val {
      font-size: 16px;
      font-weight: 650;
      color: var(--fg);
      letter-spacing: -0.03em;
      line-height: 1.1;
    }
    .mob-stats-bar.is-empty { display: none; }
    .mob-list-wrap {
      display: block;
      max-width: 900px;
      margin: 0 auto;
      width: 100%;
      padding-bottom: max(40px, env(safe-area-inset-bottom));
    }
    .mob-section-label {
      padding: 14px 14px 5px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .mob-session-row {
      display: block;
      padding: 14px;
      border-bottom: none;
      cursor: pointer;
      text-decoration: none;
      color: inherit;
      -webkit-tap-highlight-color: transparent;
      transition: background 80ms ease;
    }
    .mob-session-row:hover { background: var(--panel-2); }
    .mob-row-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 5px;
    }
    .mob-row-name { font-size: 20px; font-weight: 600; letter-spacing: -0.02em; min-width: 0; word-break: break-word; flex: 1; }
    .mob-row-preview {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
    }
    .mob-row-preview .sender {
      color: var(--fg);
      opacity: 0.72;
    }
    .mob-row-tools { flex: 0 0 auto; display: flex; align-items: center; gap: 8px; }
    .mob-badge { font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase; padding: 2px 7px; border-radius: 999px; border: 0.5px solid var(--line-strong); color: var(--muted); }
    .mob-badge.idle { color: var(--ok); }
    .mob-badge.attached { color: var(--warn); }
    .mob-badge.degraded { color: var(--bad); }
    .mob-kill-link { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; padding: 2px 7px; border-radius: 8px; border: 0.5px solid rgba(214,124,124,0.4); color: var(--bad); text-decoration: none; }
    .mob-row-path {
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 5px;
      line-height: 1.4;
      white-space: nowrap;
      overflow: hidden;
      position: relative;
      max-width: 100%;
      width: 100%;
      --mob-path-marquee-distance: 0px;
      --mob-path-marquee-duration: 12s;
    }
    .mob-row-path-track {
      display: inline-block;
      white-space: nowrap;
      min-width: 100%;
      font-size: inherit;
      line-height: inherit;
      will-change: transform;
    }
    .mob-row-path.is-overflowing .mob-row-path-track {
      padding-right: 28px;
      animation: mobPathMarquee var(--mob-path-marquee-duration) linear infinite;
      animation-delay: 0.5s;
    }
    @keyframes mobPathMarquee {
      0%, 16% { transform: translateX(0); }
      84%, 100% { transform: translateX(calc(-1 * var(--mob-path-marquee-distance))); }
    }
    .mob-row-meta { display: flex; flex-wrap: wrap; gap: 3px 10px; font-size: 12px; color: var(--muted); line-height: 1.4; }
    .mob-row-meta strong { color: var(--fg); font-weight: 500; }
    /* ── Expandable detail area ── */
    .mob-row-detail { display: none; margin-top: 8px; padding-top: 8px; border-top: 0.5px solid var(--line); min-width: 0; }
    .mob-session-row.expanded .mob-row-detail { display: block; }
    .mob-row-expand-btn {
      background: none; border: none; padding: 4px; cursor: pointer; color: var(--muted);
      transition: transform 180ms ease, color 120ms ease; flex-shrink: 0; display: flex; align-items: center;
    }
    .mob-row-expand-btn:hover { color: var(--fg); }
    .mob-session-row.expanded .mob-row-expand-btn { transform: rotate(90deg); }
    .mob-session-row.archived-row .mob-row-name,
    .mob-session-row.archived-row .mob-row-path,
    .mob-session-row.archived-row .mob-row-meta,
    .mob-session-row.archived-row .mob-badge { opacity: 0.55; }
    .mob-empty { padding: 48px 16px; color: var(--muted); font-size: 14px; text-align: center; }
    /* ── Swipe-to-reveal (touch + mouse) ── */
    .swipe-row { position: relative; overflow: hidden; border-bottom: 0.5px solid var(--line); }
    .swipe-act {
      position: absolute; top: 0; bottom: 0;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      min-width: 80px; padding: 0 18px; gap: 5px;
      font-size: 12px; font-weight: 600; color: #fff;
      user-select: none; -webkit-user-select: none; cursor: pointer;
      overflow: hidden;
    }
    .swipe-act svg { display: block; }
    .swipe-act-left  { left: 0; background: rgb(52, 199, 89); }
    .swipe-act-left.unpin { background: rgb(120, 120, 130); }
    .swipe-act-left.revive-act { background: rgb(44, 132, 219); }
    .swipe-act-right { right: 0; background: rgb(255, 59, 48); }
    .mob-session-row {
      background: var(--bg) !important;
      opacity: 1 !important;
      position: relative;
      z-index: 1;
      will-change: transform;
      border-bottom: none;
    }
    html[data-theme="black-hole"] .mob-session-row { background: rgb(10, 10, 10) !important; }
    html[data-theme="soft-light"] .mob-session-row { background: rgb(244, 244, 242) !important; }
    .mob-session-row.pinned-row .mob-row-name::before { content: "📌 "; font-size: 12px; }
    .swipe-row { border-bottom: 1px solid var(--line); }
    #starfield { position: fixed; top: 0; left: 0; z-index: 1; width: 100%; height: 100%; display: none; pointer-events: none; }
    :not([data-starfield="off"]) #starfield { display: block; }
    :not([data-starfield="off"]) body { background: transparent !important; }
    :not([data-starfield="off"]) html { background: var(--bg) !important; }
    :not([data-starfield="off"]) .shell { background: transparent !important; position: relative; z-index: 2; }
    :not([data-starfield="off"]) .mob-list-wrap { position: relative; z-index: 2; }
    /* ── Chat iframe overlay ── */
    /* overscroll contain は Safari の下端 UI ジェスチャを親 Hub に伝えにくくするため付けない */
    #chatOverlay { position: fixed; inset: 0; z-index: 9999; background: #000; }
    #chatOverlay[hidden] { display: none !important; }
    #chatFrame { position: absolute; inset: 0; width: 100%; height: 100%; border: none; display: block; }
    /* チャット iframe 表示中: Local のみ。親をわずかにスクロール可能にし、子から scroll-signal で親を動かす */
    html.hub-chat-overlay-active {
      overflow-y: auto;
      height: 100%;
    }
    body.hub-chat-overlay-active {
      overscroll-behavior-y: none;
      min-height: calc(100dvh + 24px);
    }
  </style>
</head>
<body>
  <canvas id="starfield"></canvas>
  <div id="chatOverlay" hidden><iframe id="chatFrame" src="about:blank" allow="camera; microphone; clipboard-write"></iframe></div>
  <div class="shell">
    __HUB_HEADER_HTML__
    <div class="mob-stats-bar" id="mobStatsBar"></div>
    <div class="mob-list-wrap" id="mobListWrap">
      <div class="mob-empty" id="mobLoading">Loading sessions\u2026</div>
    </div>
    <section class="hero">
      <div class="eyebrow">multiagent</div>
      <h1>Hub</h1>
      <div class="hub-nav">
        <a href="/">Hub</a>
        <a href="/new-session">New Session</a>
        <a href="/resume">Resume Sessions</a>
        <a href="/stats">Statistics</a>
        <a href="/settings">Settings</a>
        <form class="hub-restart-form" method="post" action="/restart-hub"><button type="submit">Restart Hub</button></form>
      </div>
    </section>
    <div class="home-grid">
      <a class="home-card" href="/new-session">
        <div class="home-label">New</div>
        <div class="home-title">New Session</div>
        <div class="home-note">Start a clean working room for a new task. Choose the workspace, set the session name, and decide how many agent panes you want up front.</div>
      </a>
      <a class="home-card" href="/resume">
        <div class="home-label">Resume</div>
        <div class="home-title">Resume Sessions</div>
        <div class="home-note">Jump back into something already running, or reopen archived work without hunting through tmux sessions and log folders by hand.</div>
      </a>
      <a class="home-card" href="/stats">
        <div class="home-label">Statistics</div>
        <div class="home-title">Session Stats</div>
        <div class="home-note">Read the repo-wide activity trail: message volume, commits, thinking time, and daily movement pulled from the session logs you have already accumulated.</div>
      </a>
      <a class="home-card" href="/settings">
        <div class="home-label">Settings</div>
        <div class="home-title">Global Settings</div>
        <div class="home-note">Tune defaults once for the whole Hub, including theme, fonts, message limits, and visual behavior that should stay consistent across sessions.</div>
      </a>
      <a class="home-card" href="/settings#app-controls">
        <div class="home-label">Install</div>
        <div class="home-title">App & Notifications</div>
        <div class="home-note">Add Hub or a session chat to the Home Screen, then enable browser notifications so background agent replies can call you back in.</div>
      </a>
    </div>
  </div>
  <script>
    // ── Chat iframe overlay ──
    const _chatOverlay = document.getElementById("chatOverlay");
    const _chatFrame = document.getElementById("chatFrame");
    let _hubChatParentLayoutMax = 0;
    let _hubMinParentChromeGap = Infinity;
    let _hubLayoutRefW = 0;
    let _hubLayoutRefH = 0;
    let _hubVVBridgeHandler = null;
    let _hubPreOverlayScrollY = 0;
    function _bumpHubChatParentLayoutMax() {
      if (_chatOverlay.hidden) return;
      const ih = window.innerHeight || 0;
      const ch = document.documentElement.clientHeight || 0;
      _hubChatParentLayoutMax = Math.max(_hubChatParentLayoutMax, ih, ch);
      _postHubLayoutToChat();
    }
    function _postHubLayoutToChat() {
      const w = _chatFrame.contentWindow;
      if (!w || _chatOverlay.hidden) return;
      const iw = window.innerWidth || 0;
      const ih = window.innerHeight || 0;
      if (_hubLayoutRefW > 0 && _hubLayoutRefH > 0) {
        const b0 = _hubLayoutRefH >= _hubLayoutRefW;
        const b1 = ih >= iw;
        const diffH = Math.abs(_hubLayoutRefH - ih);
        if (b0 !== b1 && diffH > 150) {
          _hubMinParentChromeGap = Infinity;
        }
      }
      _hubLayoutRefW = iw;
      _hubLayoutRefH = ih;
      const vv = window.visualViewport;
      const vvH = vv ? vv.height : ih;
      const vvTop = vv ? vv.offsetTop : 0;
      const raw = Math.max(0, Math.round(ih - vvTop - vvH));
      if (raw < 150) {
        _hubMinParentChromeGap = Math.min(_hubMinParentChromeGap, raw);
      }
      const effectiveGap = raw >= 150 ? raw : _hubMinParentChromeGap;
      try {
        w.postMessage(
          {
            type: "multiagent-hub-layout",
            layoutHeight: _hubChatParentLayoutMax,
            parentInnerHeight: ih,
            parentVvHeight: vvH,
            parentVvOffsetTop: vvTop,
            parentChromeGap: effectiveGap === Infinity ? raw : effectiveGap,
          },
          "*"
        );
      } catch (_) {}
    }
    function _attachHubViewportBridge() {
      if (_hubVVBridgeHandler) return;
      _hubVVBridgeHandler = () => { _bumpHubChatParentLayoutMax(); };
      window.addEventListener("resize", _hubVVBridgeHandler, { passive: true });
      if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", _hubVVBridgeHandler);
        window.visualViewport.addEventListener("scroll", _hubVVBridgeHandler);
      }
    }
    function _detachHubViewportBridge() {
      if (!_hubVVBridgeHandler) return;
      window.removeEventListener("resize", _hubVVBridgeHandler);
      if (window.visualViewport) {
        window.visualViewport.removeEventListener("resize", _hubVVBridgeHandler);
        window.visualViewport.removeEventListener("scroll", _hubVVBridgeHandler);
      }
      _hubVVBridgeHandler = null;
    }
    function _fitChatOverlay() {
      if (_chatOverlay.hidden) return;
      // 以前は visualViewport に合わせて #chatOverlay の top/height を縮めていた。
      // その結果 iframe 内の window.innerHeight / 100vh も「キーボード上の帯」だけになり、
      // チャットの .composer-overlay（flex 中央）が「画面全体の中央」ではなく
      // 「押し上げ後の領域の中央」に寄る。Public（トップレベル）との差の主因だった。
      // オーバーレイは CSS の position:fixed; inset:0 のままフルレイアウト高さを維持する。
      _chatOverlay.style.top = "";
      _chatOverlay.style.height = "";
    }
    function shouldUseChatOverlay() {
      const host = window.location.hostname || "";
      return host === "127.0.0.1" || host === "localhost" || host.startsWith("192.168.") || host.startsWith("10.") || /^172\.(1[6-9]|2\d|3[01])\./.test(host);
    }
    function openChatInFrame(url, name) {
      const useOverlay = shouldUseChatOverlay();
      if (!useOverlay) {
        window.location.href = url;
        return;
      }
      const freshUrl = url + (url.includes("?") ? "&" : "?") + "ts=" + Date.now();
      _hubMinParentChromeGap = Infinity;
      _hubLayoutRefW = window.innerWidth || 0;
      _hubLayoutRefH = window.innerHeight || 0;
      _hubChatParentLayoutMax = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
      _chatFrame.onload = function() {
        _bumpHubChatParentLayoutMax();
        _postHubLayoutToChat();
      };
      _attachHubViewportBridge();
      _hubPreOverlayScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.documentElement.classList.add("hub-chat-overlay-active");
      document.body.classList.add("hub-chat-overlay-active");
      _chatFrame.src = freshUrl;
      _chatOverlay.hidden = false;
      _fitChatOverlay();
      try { sessionStorage.setItem("hub_chat_frame", JSON.stringify({url: freshUrl, name})); } catch(_) {}
    }
    function closeChatFrame() {
      _detachHubViewportBridge();
      document.documentElement.classList.remove("hub-chat-overlay-active");
      document.body.classList.remove("hub-chat-overlay-active");
      try {
        window.scrollTo(0, _hubPreOverlayScrollY);
      } catch (_) {}
      _chatFrame.onload = null;
      _chatOverlay.hidden = true;
      _chatOverlay.style.top = "";
      _chatOverlay.style.height = "";
      _chatFrame.src = "about:blank";
      try { sessionStorage.removeItem("hub_chat_frame"); } catch(_) {}
    }
    function openSessionFrame(openHref, name) {
      if (!shouldUseChatOverlay()) {
        if (name && openHref.startsWith("/open-session")) {
          window.location.href = `/session/${encodeURIComponent(name)}/?follow=1&ts=${Date.now()}`;
        } else {
          window.location.href = openHref;
        }
        return;
      }
      const url = openHref + (openHref.includes("?") ? "&" : "?") + "format=json";
      fetch(url)
        .then(r => r.json())
        .then(d => { if (d.chat_url) openChatInFrame(d.chat_url, name); else window.location.href = openHref; })
        .catch(() => { window.location.href = openHref; });
    }
    window.addEventListener("message", function(e) {
      if (e.data === "hub_close_chat") closeChatFrame();
      if (e.data && e.data.type === "multiagent-open-hub-path") {
        const nextUrl = typeof e.data.url === "string" ? e.data.url : "";
        if (nextUrl) {
          closeChatFrame();
          window.location.href = nextUrl;
        }
        return;
      }
      if (e.data && e.data.type === "multiagent-chat-scroll-signal" && e.source === _chatFrame.contentWindow) {
        if (_chatOverlay.hidden) return;
        const y = window.scrollY || document.documentElement.scrollTop || 0;
        try {
          window.scrollTo(0, y + 1);
          window.scrollTo(0, y);
        } catch (_) {}
        return;
      }
      if (e.data && e.data.type === "multiagent-chat-request-hub-layout" && e.source === _chatFrame.contentWindow) {
        _bumpHubChatParentLayoutMax();
        _postHubLayoutToChat();
      }
    });
    // Restore active chat on PWA re-launch
    try {
      const saved = sessionStorage.getItem("hub_chat_frame");
      if (!shouldUseChatOverlay()) {
        sessionStorage.removeItem("hub_chat_frame");
      } else if (saved) {
        const {url, name} = JSON.parse(saved);
        if (url) openChatInFrame(url, name);
      }
    } catch (_) {}

    // --- Mobile session list ---
    (function() {
      const wrap = document.getElementById("mobListWrap");
      const statsBar = document.getElementById("mobStatsBar");
      if (!wrap) return;

      const esc = (v) => String(v || "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

      // ── Pin storage ──
      const PINNED_KEY = "multiagent_hub_pinned";
      const getPinned = () => { try { return JSON.parse(localStorage.getItem(PINNED_KEY) || "[]"); } catch { return []; } };
      const setPinned = (arr) => localStorage.setItem(PINNED_KEY, JSON.stringify(arr));
      const togglePin = (name) => { const p = getPinned(); const i = p.indexOf(name); if (i >= 0) p.splice(i, 1); else p.unshift(name); setPinned(p); };

      // ── Swipe logic ──
      const SNAP_W = 84;
      const THRESH = 48;
      let anyOpen = null;
      const closeRow = (sr, animate) => {
        const el = sr && sr.querySelector(".mob-session-row");
        if (!el) return;
        el.style.transition = animate ? "transform 220ms cubic-bezier(.25,.46,.45,.94)" : "none";
        el.style.transform = "";
        sr._snap = 0;
      };
      const initSwipeRow = (sr) => {
        const inner = sr.querySelector(".mob-session-row");
        const actL = sr.querySelector(".swipe-act-left");
        const actR = sr.querySelector(".swipe-act-right");
        if (!inner) return;
        sr._snap = 0;
        let sx = 0, sy = 0, dx = 0, axis = null, active = false, didSwipe = false;
        const startDrag = (clientX, clientY) => {
          if (anyOpen && anyOpen !== sr) { closeRow(anyOpen, true); anyOpen = null; }
          sx = clientX; sy = clientY;
          dx = 0; axis = null; active = true; didSwipe = false;
          inner.style.transition = "none";
        };
        const moveDrag = (clientX, clientY, preventDefault) => {
          if (!active) return;
          const cx = clientX - sx, cy = clientY - sy;
          if (!axis) {
            if (Math.abs(cy) > Math.abs(cx) + 4) { axis = "y"; return; }
            if (Math.abs(cx) > 6) axis = "x";
          }
          if (axis !== "x") return;
          if (preventDefault) preventDefault();
          didSwipe = true;
          dx = cx;
          const base = (sr._snap || 0) * SNAP_W;
          let x = Math.max(-SNAP_W, Math.min(SNAP_W, base + dx));
          if (!actR && x < 0) x = 0;
          if (!actL && x > 0) x = 0;
          inner.style.transform = x ? `translateX(${x}px)` : "";
        };
        const endDrag = () => {
          if (!active || axis !== "x") { active = false; return; }
          active = false;
          const base = (sr._snap || 0) * SNAP_W;
          const fx = base + dx;
          const ease = "transform 220ms cubic-bezier(.25,.46,.45,.94)";
          if (fx < -THRESH && actR) {
            inner.style.transition = ease; inner.style.transform = `translateX(${-SNAP_W}px)`;
            sr._snap = -1; anyOpen = sr;
          } else if (fx > THRESH && actL) {
            inner.style.transition = ease; inner.style.transform = `translateX(${SNAP_W}px)`;
            sr._snap = 1; anyOpen = sr;
          } else {
            inner.style.transition = ease; inner.style.transform = "";
            sr._snap = 0; if (anyOpen === sr) anyOpen = null;
          }
          dx = 0;
        };
        // Touch events
        inner.addEventListener("touchstart", (e) => startDrag(e.touches[0].clientX, e.touches[0].clientY), { passive: true });
        inner.addEventListener("touchmove", (e) => moveDrag(e.touches[0].clientX, e.touches[0].clientY, () => e.preventDefault()), { passive: false });
        inner.addEventListener("touchend", endDrag, { passive: true });
        // Mouse events (PC swipe)
        inner.addEventListener("mousedown", (e) => {
          if (e.target.closest(".mob-row-expand-btn, a, button")) return;
          e.preventDefault();
          startDrag(e.clientX, e.clientY);
          const onMove = (me) => moveDrag(me.clientX, me.clientY, () => me.preventDefault());
          const onUp = () => { endDrag(); document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); };
          document.addEventListener("mousemove", onMove);
          document.addEventListener("mouseup", onUp);
        });
        if (actR) actR.addEventListener("click", (e) => {
          e.stopPropagation();
          const n = sr.dataset.sessionName;
          const action = actR.dataset.action;
          if (action === "delete-archived") {
            if (confirm("Delete archived logs for " + n + "? This cannot be undone.")) {
              window.location.href = `/delete-archived-session?session=${encodeURIComponent(n)}`;
            }
            return;
          }
          if (confirm("Kill " + n + "?")) window.location.href = `/kill-session?session=${encodeURIComponent(n)}`;
        });
        if (actL) actL.addEventListener("click", (e) => {
          e.stopPropagation();
          const action = actL.dataset.action, n = sr.dataset.sessionName;
          if (action === "pin") { togglePin(n); refresh(); }
          else if (action === "revive") { openSessionFrame(`/revive-session?session=${encodeURIComponent(n)}&ts=${Date.now()}`, n); }
          closeRow(sr, true); anyOpen = null;
        });
        // Expand button
        inner.querySelectorAll(".mob-row-expand-btn").forEach(btn => {
          btn.addEventListener("click", (e) => {
            e.stopPropagation();
            inner.classList.toggle("expanded");
            requestAnimationFrame(() => setupMobPathMarquee(wrap));
            setTimeout(() => setupMobPathMarquee(wrap), 180);
          });
        });
        // tap/click on row body navigates (unless swipe was happening)
        inner.addEventListener("click", (e) => {
          if (didSwipe) { didSwipe = false; e.stopPropagation(); return; }
          if (sr._snap !== 0) { closeRow(sr, true); anyOpen = null; e.stopPropagation(); return; }
          if (e.target.closest(".swipe-act, .mob-row-expand-btn")) return;
          const href = inner.dataset.openHref;
          if (href) openSessionFrame(href, sr.dataset.sessionName || "");
        });
      };

      const updateStatsBar = (active, archived) => {
        if (!statsBar) return;
        const activeAgentCount = active.reduce((sum, session) => sum + ((session.agents || []).length || 0), 0);
        const stat = (val, label) =>
          `<div class="mob-stat"><span class="mob-stat-label">${label}</span><span class="mob-stat-val">${val}</span></div>`;
        statsBar.innerHTML =
          stat(active.length, "Active") +
          stat(archived.length, "Archived") +
          stat(activeAgentCount, "Agents");
        statsBar.classList.toggle("is-empty", active.length === 0 && archived.length === 0);
      };

      const setupMobPathMarquee = (root) => {
        if (!root) return;
        root.querySelectorAll(".mob-row-path").forEach((node) => {
          const track = node.querySelector(".mob-row-path-track");
          node.classList.remove("is-overflowing");
          node.style.removeProperty("--mob-path-marquee-distance");
          node.style.removeProperty("--mob-path-marquee-duration");
          if (!track) return;
          const overflow = Math.ceil(track.scrollWidth) > Math.ceil(node.clientWidth + 2);
          if (!overflow) return;
          const distance = Math.max(0, Math.ceil(track.scrollWidth - node.clientWidth + 24));
          const duration = Math.max(8, distance / 28);
          node.classList.add("is-overflowing");
          node.style.setProperty("--mob-path-marquee-distance", `${distance}px`);
          node.style.setProperty("--mob-path-marquee-duration", `${duration}s`);
        });
      };

      const renderRows = (active, archived) => {
        updateStatsBar(active, archived);
        const pinned = getPinned();
        const sortedActive = [...active].sort((a, b) => {
          const pa = pinned.indexOf(a.name), pb = pinned.indexOf(b.name);
          if (pa < 0 && pb < 0) return 0;
          if (pa < 0) return 1; if (pb < 0) return -1;
          return pa - pb;
        });
        let html = "";
        const pinSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/></svg>`;
        const trashSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>`;
        const reviveSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.62"/></svg>`;
        if (sortedActive.length) {
          html += `<div class="mob-section-label">Active</div>`;
          html += sortedActive.map((s) => {
            const agents = (s.agents && s.agents.length) ? s.agents.join(", ") : "none";
            const dead = s.dead_panes ? `, ${s.dead_panes} dead pane${s.dead_panes === 1 ? "" : "s"}` : "";
            const isPinned = pinned.includes(s.name);
            const preview = s.latest_message_preview ? `<div class="mob-row-preview"><span class="sender">${esc(s.latest_message_sender || "latest")}</span> ${esc(s.latest_message_preview)}</div>` : "";
            return `<div class="swipe-row" data-session-name="${esc(s.name)}">` +
              `<div class="swipe-act swipe-act-left${isPinned ? " unpin" : ""}" data-action="pin">${pinSvg}<span>${isPinned ? "Unpin" : "Pin"}</span></div>` +
              `<div class="swipe-act swipe-act-right" data-action="kill">${trashSvg}<span>Kill</span></div>` +
              `<div class="mob-session-row${isPinned ? " pinned-row" : ""}" data-open-href="/open-session?session=${encodeURIComponent(s.name)}" role="link" tabindex="0">` +
                `<div class="mob-row-head">` +
                  `<button class="mob-row-expand-btn" data-expand="1"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></button>` +
                  `<div class="mob-row-name">${esc(s.name)}</div>` +
                `<div class="mob-row-tools">` +
                  `<span class="mob-badge ${esc(s.status)}">${esc(s.status)}</span>` +
                `</div></div>` +
                preview +
                `<div class="mob-row-detail">` +
                  `<div class="mob-row-path"><span class="mob-row-path-track">${esc(s.workspace || "workspace unavailable")}</span></div>` +
                  `<div class="mob-row-meta">` +
                    `<span><strong>Agents</strong> ${esc(agents)}</span>` +
                    `<span><strong>Created</strong> ${esc(s.created_at || "unknown")}</span>` +
                    `<span><strong>Chats</strong> ${esc(String(s.chat_count || 0))}</span>` +
                    `<span><strong>Address</strong> :${esc(s.chat_port)}</span>` +
                    `<span><strong>State</strong> ${esc(s.status)}${esc(dead)}</span>` +
                  `</div>` +
                `</div>` +
              `</div></div>`;
          }).join("");
        }
        if (archived.length) {
          html += `<div class="mob-section-label">Archived</div>`;
          html += archived.map((s) => {
            const agents = (s.agents && s.agents.length) ? s.agents.join(", ") : "none";
            const preview = s.latest_message_preview ? `<div class="mob-row-preview"><span class="sender">${esc(s.latest_message_sender || "latest")}</span> ${esc(s.latest_message_preview)}</div>` : "";
            return `<div class="swipe-row" data-session-name="${esc(s.name)}">` +
              `<div class="swipe-act swipe-act-left revive-act" data-action="revive">${reviveSvg}<span>Revive</span></div>` +
              `<div class="swipe-act swipe-act-right" data-action="delete-archived">${trashSvg}<span>Delete</span></div>` +
              `<div class="mob-session-row archived-row" data-open-href="/revive-session?session=${encodeURIComponent(s.name)}" role="link" tabindex="0">` +
                `<div class="mob-row-head">` +
                  `<button class="mob-row-expand-btn" data-expand="1"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></button>` +
                  `<div class="mob-row-name">${esc(s.name)}</div>` +
                `<div class="mob-row-tools">` +
                  `<span class="mob-badge">archived</span>` +
                `</div></div>` +
                preview +
                `<div class="mob-row-detail">` +
                  `<div class="mob-row-path"><span class="mob-row-path-track">${esc(s.workspace || "workspace unavailable")}</span></div>` +
                  `<div class="mob-row-meta">` +
                    `<span><strong>Agents</strong> ${esc(agents)}</span>` +
                    `<span><strong>Updated</strong> ${esc(s.updated_at || "unknown")}</span>` +
                    `<span><strong>Chats</strong> ${esc(String(s.chat_count || 0))}</span>` +
                    `<span><strong>Address</strong> :${esc(s.chat_port)}</span>` +
                  `</div>` +
                `</div>` +
              `</div></div>`;
          }).join("");
        }
        if (!sortedActive.length && !archived.length) {
          html = `<div class="mob-empty">No sessions found</div>`;
        }
        wrap.innerHTML = html;
        wrap.querySelectorAll(".swipe-row").forEach(initSwipeRow);
        setupMobPathMarquee(wrap);
      };
      const refresh = async (force) => {
        try {
          const res = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
          if (!res.ok) throw new Error("failed");
          const data = await res.json();

          // Prevent layout thrashing and animation re-triggering if data hasn't changed
          const pinSig = JSON.stringify(getPinned());
          const sig = JSON.stringify({ active: data.active_sessions || data.sessions || [], archived: data.archived_sessions || [], _pin: pinSig });
          if (!force && window._lastMobRenderSig === sig) return;
          window._lastMobRenderSig = sig;

          renderRows(data.active_sessions || data.sessions || [], data.archived_sessions || []);
        } catch (_) {
          wrap.innerHTML = `<div class="mob-empty">Failed to load sessions</div>`;
        }
      };
      window.addEventListener("resize", () => setupMobPathMarquee(wrap), { passive: true });
      refresh();
      setInterval(refresh, 5000);
    })();

    // --- Starfield Animation ---
    const starCanvas = document.getElementById("starfield");
    const starCtx = starCanvas ? starCanvas.getContext("2d") : null;
    let stars = [];
    let shootingStars = [];
    const numStars = 360;
    let starAnimationId;
    let isStarAnimationRunning = false;

    function resizeStarCanvas() {
      if (!starCanvas) return;
      starCanvas.width = window.innerWidth;
      starCanvas.height = window.innerHeight;
      initStars();
    }
    function initStars() {
      if (!starCanvas) return;
      const diagonal = Math.sqrt(starCanvas.width ** 2 + starCanvas.height ** 2);
      stars = Array.from({ length: numStars }, () => ({
        angle: Math.random() * Math.PI * 2,
        radius: Math.random() * diagonal,
        speed: Math.random() * 0.0003 + 0.00015,
        size: Math.random() * 1.2 + 0.5,
      }));
    }
    function spawnShootingStar() {
      if (shootingStars.length === 0 && Math.random() < 0.01) {
        shootingStars.push({
          x: Math.random() * starCanvas.width * 0.5,
          y: Math.random() * starCanvas.height * 0.5,
          vx: 3 + Math.random() * 2,
          vy: 1 + Math.random() * 1.5,
          life: 80,
          initialLife: 80,
        });
      }
    }
    function animateStars() {
      if (!isStarAnimationRunning) return;
      const centerX = starCanvas.width;
      const centerY = starCanvas.height;
      starCtx.fillStyle = "rgb(10, 10, 10)";
      starCtx.fillRect(0, 0, starCanvas.width, starCanvas.height);
      stars.forEach((star, i) => {
        star.angle += star.speed;
        const x = centerX + star.radius * Math.cos(star.angle);
        const y = centerY + star.radius * Math.sin(star.angle);
        const flicker = 0.4 + Math.abs(Math.sin(Date.now() * 0.0015 + i)) * 0.5;
        starCtx.beginPath();
        starCtx.fillStyle = `rgba(255, 255, 255, ${flicker})`;
        starCtx.arc(x, y, star.size, 0, Math.PI * 2);
        starCtx.fill();
      });
      spawnShootingStar();
      for (let i = shootingStars.length - 1; i >= 0; i--) {
        const s = shootingStars[i];
        const opacity = s.life / s.initialLife;
        const grad = starCtx.createLinearGradient(s.x, s.y, s.x - s.vx * 35, s.y - s.vy * 35);
        grad.addColorStop(0, `rgba(255, 255, 255, ${opacity})`);
        grad.addColorStop(1, `rgba(255, 255, 255, 0)`);
        starCtx.strokeStyle = grad;
        starCtx.lineWidth = 2;
        starCtx.beginPath();
        starCtx.moveTo(s.x, s.y);
        starCtx.lineTo(s.x - s.vx * 18, s.y - s.vy * 18);
        starCtx.stroke();
        s.x += s.vx; s.y += s.vy; s.life -= 1;
        if (s.life <= 0) shootingStars.splice(i, 1);
      }
      starAnimationId = requestAnimationFrame(animateStars);
    }
    const updateStarAnimationState = () => {
      if (!starCanvas) return;
      const shouldRun = document.documentElement.dataset.starfield !== "off";
      if (shouldRun && !isStarAnimationRunning) {
        isStarAnimationRunning = true;
        resizeStarCanvas();
        animateStars();
      } else if (!shouldRun && isStarAnimationRunning) {
        isStarAnimationRunning = false;
        cancelAnimationFrame(starAnimationId);
      }
    };
    window.addEventListener("resize", () => { if (isStarAnimationRunning) resizeStarCanvas(); });
    const themeObserver = new MutationObserver(updateStarAnimationState);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-starfield"] });
    updateStarAnimationState();
  __HUB_HEADER_JS__
  </script>
</body>
</html>
"""
HUB_HOME_HTML = (
    HUB_HOME_HTML
    .replace("__HUB_MANIFEST_URL__", _PWA_HUB_MANIFEST_URL)
    .replace("__PWA_ICON_192_URL__", _PWA_ICON_192_URL)
    .replace("__APPLE_TOUCH_ICON_URL__", _PWA_APPLE_TOUCH_ICON_URL)
    .replace("__HUB_HEADER_CSS__", _HUB_PAGE_HEADER_CSS)
    .replace("__HUB_HEADER_HTML__", _HUB_PAGE_HEADER_HTML)
    .replace("__HUB_HEADER_JS__", _HUB_PAGE_HEADER_JS)
)


def _normalized_font_label(name: str) -> str:
    label = re.sub(r"\.(ttf|ttc|otf)$", "", name, flags=re.IGNORECASE)
    label = re.sub(r"[-_](Variable|Italic|Italics|Roman|Romans|Regular|Medium|Light|Bold|Heavy|Black|Condensed|Rounded|Mono)\b", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+", " ", label).strip(" -_")
    return label


def available_chat_font_choices():
    seen = set()
    choices = [
        ("preset-gothic", "Default Gothic"),
        ("preset-mincho", "Default Mincho"),
    ]
    curated_families = [
        ("system:Hiragino Sans", "Hiragino Sans"),
        ("system:Hiragino Kaku Gothic ProN", "Hiragino Kaku Gothic ProN"),
        ("system:Hiragino Maru Gothic ProN", "Hiragino Maru Gothic ProN"),
        ("system:Hiragino Mincho ProN", "Hiragino Mincho ProN"),
        ("system:Yu Gothic", "Yu Gothic"),
        ("system:Yu Gothic UI", "Yu Gothic UI"),
        ("system:Yu Mincho", "Yu Mincho"),
        ("system:Meiryo", "Meiryo"),
        ("system:BIZ UDPGothic", "BIZ UDPGothic"),
        ("system:BIZ UDPMincho", "BIZ UDPMincho"),
        ("system:Noto Sans JP", "Noto Sans JP"),
        ("system:Noto Serif JP", "Noto Serif JP"),
        ("system:Zen Kaku Gothic New", "Zen Kaku Gothic New"),
        ("system:Zen Maru Gothic", "Zen Maru Gothic"),
        ("system:Shippori Mincho", "Shippori Mincho"),
        ("system:Sawarabi Gothic", "Sawarabi Gothic"),
        ("system:Sawarabi Mincho", "Sawarabi Mincho"),
    ]
    for value, label in curated_families:
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        choices.append((value, label))
    for root in (
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
        Path.home() / "Library/Fonts",
    ):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".ttf", ".ttc", ".otf"}:
                continue
            label = _normalized_font_label(path.name)
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            choices.append((f"system:{label}", label))
            if len(choices) >= 96:
                break
        if len(choices) >= 96:
            break
    return choices

def hub_settings_html(saved=False):
    settings = load_hub_settings()
    theme = settings["theme"]
    font_mode = settings["agent_font_mode"]
    user_message_font = settings.get("user_message_font", "preset-gothic")
    agent_message_font = settings.get("agent_message_font", "preset-mincho")
    message_text_size = int(settings.get("message_text_size", 13) or 13)
    user_message_opacity_blackhole = float(settings.get("user_message_opacity_blackhole", 1.0) or 1.0)
    agent_message_opacity_blackhole = float(settings.get("agent_message_opacity_blackhole", 1.0) or 1.0)
    message_limit = settings["message_limit"]
    message_max_width = int(settings.get("message_max_width", 900) or 900)
    chat_auto = settings.get("chat_auto_mode", False)
    chat_awake = settings.get("chat_awake", False)
    chat_sound = settings.get("chat_sound", False)
    chat_browser_notifications = settings.get("chat_browser_notifications", False)
    chat_tts = settings.get("chat_tts", False)
    starfield = settings.get("starfield", False)
    bold_mode = settings.get("bold_mode", False)
    font_choices = available_chat_font_choices()
    theme_choices = available_theme_choices()
    theme_options = "".join(
        f'<option value="{html.escape(value)}"' + (' selected' if value == theme else '') + f'>{html.escape(label)}</option>'
        for value, label in theme_choices
    )
    theme_hint = theme_description(theme) or "Theme preset."
    font_options = lambda selected: "".join(
        f'<option value="{html.escape(value)}"' + (' selected' if value == selected else '') + f'>{html.escape(label)}</option>'
        for value, label in font_choices
    )
    notice = '<div style="margin:0 0 14px;color:rgb(170,190,172);font-size:13px;line-height:1.5;">Saved.</div>' if saved else ""
    sf_attr = "" if starfield else ' data-starfield="off"'
    hub_manifest_url = _PWA_HUB_MANIFEST_URL
    pwa_icon_192_url = _PWA_ICON_192_URL
    apple_touch_icon_url = _PWA_APPLE_TOUCH_ICON_URL
    _html = f"""<!doctype html>
<html lang="en" data-theme="{theme}"{sf_attr}>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="rgb(10, 10, 10)">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Session Hub">
  <link rel="manifest" href="{hub_manifest_url}">
  <link rel="icon" type="image/png" sizes="192x192" href="{pwa_icon_192_url}">
  <link rel="apple-touch-icon" href="{apple_touch_icon_url}">
  <title>Hub Settings</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: rgb(10, 10, 10);
      --bg-rgb: 10, 10, 10;
      --panel: rgb(20, 20, 20);
      --panel-2: rgb(15, 15, 15);
      --line: rgba(255,255,255,0.06);
      --line-strong: rgba(255,255,255,0.10);
      --fg: rgb(252, 252, 252);
      --muted: rgb(158, 158, 158);
      --accent: rgb(44, 132, 219);
    }}
    html[data-theme="soft-light"] {{
      color-scheme: light;
      --bg: rgb(244, 244, 242);
      --bg-rgb: 244, 244, 242;
      --panel: rgb(255, 255, 255);
      --panel-2: rgb(248, 248, 246);
      --line: rgba(15, 20, 30, 0.12);
      --line-strong: rgba(15, 20, 30, 0.2);
      --fg: rgb(26, 30, 36);
      --muted: rgb(98, 106, 120);
      --accent: rgb(44, 132, 219);
    }}
    #starfield {{
      position: fixed;
      top: 0;
      left: 0;
      z-index: 1;
      width: 100%;
      height: 100%;
      display: none;
      pointer-events: none;
    }}
    [data-starfield="on"] #starfield,
    :not([data-starfield="off"]) #starfield {{
      display: block;
    }}
    :not([data-starfield="off"]) body {{
      background: transparent !important;
    }}
    :not([data-starfield="off"]) html {{
      background: var(--bg) !important;
    }}
    :not([data-starfield="off"]) .shell {{
      background: transparent !important;
      position: relative;
      z-index: 2;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      min-height: 100%;
      background: var(--bg);
      color: var(--fg);
      font-family: "SF Pro Text", "Segoe UI", sans-serif;
    }}
    body {{
      padding: 0 0 max(20px, env(safe-area-inset-bottom)) 0;
    }}
    .shell {{ max-width: 900px; margin: 0 auto; }}
    .shell > :not(.hub-page-header) {{ padding-left: 14px; padding-right: 14px; }}
    .hero {{ padding: 8px 2px 18px 2px; }}
    .eyebrow {{ color: var(--muted); font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; }}
    h1 {{ margin: 0; font-size: clamp(28px, 5vw, 40px); line-height: 1.02; font-weight: 600; letter-spacing: -0.03em; }}
    .sub {{ margin-top: 10px; color: var(--muted); font-size: 14px; line-height: 1.55; max-width: 40rem; }}
    .hub-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
      width: 100%;
      align-items: center;
    }}
    .hub-nav a {{
      color: var(--muted);
      text-decoration: none;
      border: 0.5px solid var(--line);
      background: var(--panel);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      line-height: 1;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .hub-nav form {{ margin: 0; }}
    .hub-nav .hub-restart-form {{ margin-left: auto; }}
    .hub-nav button {{
      color: var(--muted);
      border: 0.5px solid var(--line);
      background: var(--panel);
      border-radius: 999px;
      padding: 6px 10px;
      font: inherit;
      font-size: 12px;
      font-weight: 400;
      line-height: 1;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      cursor: pointer;
      appearance: none;
      -webkit-appearance: none;
    }}
    .hub-nav .hub-restart-form button {{ color: rgb(44, 132, 219); }}
    .hub-nav a.active {{ color: var(--fg); border-color: var(--line-strong); }}
    .panel {{
      background: var(--panel);
      border: 0.5px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}
    .field + .field {{ margin-top: 16px; }}
    .label {{ display:block; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }}
    .hint {{ color: var(--muted); font-size: 13px; line-height: 1.5; margin-top: 8px; }}
    select, input[type="text"], input[type="number"] {{
      width: 100%;
      border: 0.5px solid var(--line-strong);
      background: var(--panel-2);
      color: var(--fg);
      border-radius: 12px;
      padding: 11px 13px;
      font-size: 16px;
      line-height: 1.25;
      outline: none;
      appearance: none;
      -webkit-appearance: none;
      font-family: inherit;
    }}
    select:focus, input[type="text"]:focus, input[type="number"]:focus {{
      border-color: rgba(255,255,255,0.22);
    }}
    html[data-theme="black-hole"] select,
    html[data-theme="black-hole"] input[type="text"],
    html[data-theme="black-hole"] input[type="number"] {{
      background: linear-gradient(145deg, rgb(20, 20, 20) 0%, rgb(10, 10, 10) 100%) !important;
      backdrop-filter: blur(20px) saturate(160%) !important;
      -webkit-backdrop-filter: blur(20px) saturate(160%) !important;
      border: 0.5px solid rgba(255, 255, 255, 0.1) !important;
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8) !important;
    }}
    html[data-theme="soft-light"] select,
    html[data-theme="soft-light"] input[type="text"],
    html[data-theme="soft-light"] input[type="number"] {{
      background: linear-gradient(145deg, rgb(255, 255, 255) 0%, rgb(246, 246, 244) 100%) !important;
      border: 0.5px solid rgba(15, 20, 30, 0.14) !important;
      box-shadow: 0 8px 24px rgba(15, 20, 30, 0.08) !important;
      backdrop-filter: none !important;
      -webkit-backdrop-filter: none !important;
      color: var(--fg) !important;
    }}
    .row {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .slider-field {{
      display: grid;
      gap: 10px;
    }}
    input[type="range"] {{
      -webkit-appearance: none;
      appearance: none;
      --slider-fill: rgba(252,252,252,0.96);
      --slider-fill-pct: 100%;
      height: 4px;
      border-radius: 2px;
      background: linear-gradient(to right, var(--slider-fill) 0 var(--slider-fill-pct), rgba(255,255,255,0.20) var(--slider-fill-pct) 100%);
      outline: none;
      cursor: pointer;
    }}
    input[type="range"]::-webkit-slider-runnable-track {{
      height: 4px;
      border-radius: 2px;
      background: transparent;
    }}
    input[type="range"]::-moz-range-track {{
      height: 4px;
      border-radius: 2px;
      background: rgba(255,255,255,0.20);
    }}
    input[type="range"]::-moz-range-progress {{
      height: 4px;
      border-radius: 2px;
      background: var(--slider-fill);
    }}
    input[type="range"]::-webkit-slider-thumb {{
      -webkit-appearance: none;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: var(--slider-fill);
      border: 1px solid rgba(0,0,0,0.18);
      cursor: pointer;
      margin-top: -8px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.3);
    }}
    input[type="range"]::-moz-range-thumb {{
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: var(--slider-fill);
      border: 1px solid rgba(0,0,0,0.18);
      cursor: pointer;
      box-shadow: 0 1px 4px rgba(0,0,0,0.3);
    }}
    html[data-theme="soft-light"] input[type="range"] {{
      background: linear-gradient(to right, var(--slider-fill) 0 var(--slider-fill-pct), rgba(15,20,30,0.12) var(--slider-fill-pct) 100%);
    }}
    html[data-theme="soft-light"] input[type="range"]::-moz-range-track {{
      background: rgba(15,20,30,0.12);
    }}
    .slider-topline {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .slider-value {{
      color: var(--fg);
      font-size: 15px;
      min-width: 36px;
      text-align: right;
      font-variant-numeric: tabular-nums;
      opacity: 0.9;
    }}
    .save {{
      margin-top: 18px;
      border: 0.5px solid var(--line-strong);
      background: none;
      color: rgba(252,252,252,0.96);
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 14px;
      line-height: 1;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      cursor: pointer;
    }}
    @keyframes hubRestartingPulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.4; }}
    }}
    .hub-nav button.restarting {{
      animation: hubRestartingPulse 900ms ease-in-out infinite;
      pointer-events: none;
    }}
    .hub-nav a.active {{
      background: var(--bg) !important;
      border-color: rgba(255, 255, 255, 0.2) !important;
    }}
    .hub-nav {{ display: none !important; }}
    __HUB_HEADER_CSS__
    .panel {{
      background: transparent !important;
      border: none !important;
      border-radius: 0 !important;
      padding: 0 14px !important;
    }}
    .field {{
      padding: 12px 0;
      border-bottom: 0.5px solid var(--line);
    }}
    .field + .field {{ margin-top: 0; }}
    .field:first-child {{ border-top: 0.5px solid var(--line); }}
    .chat-toggles {{ display: flex; flex-direction: column; gap: 2px; }}
    .toggle-row {{ display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 0.5px solid var(--line); font-size: 15px; cursor: pointer; }}
    .toggle-row:last-child {{ border-bottom: none; }}
    .toggle-row-copy {{ display: inline-flex; align-items: center; gap: 10px; min-width: 0; }}
    .toggle-row input[type="checkbox"] {{ width: 44px; height: 26px; -webkit-appearance: none; appearance: none; background: var(--line-strong); border-radius: 999px; cursor: pointer; transition: background 200ms; position: relative; flex-shrink: 0; }}
    .toggle-row input[type="checkbox"]:checked {{ background: var(--accent, rgb(44,132,219)); }}
    .toggle-row input[type="checkbox"]::before {{ content: ""; position: absolute; width: 22px; height: 22px; background: #fff; border-radius: 50%; top: 2px; left: 2px; transition: transform 200ms; }}
    .toggle-row input[type="checkbox"]:checked::before {{ transform: translateX(18px); }}
    .audio-preview-meter {{
      display: inline-flex;
      align-items: flex-end;
      gap: 2px;
      height: 14px;
      opacity: 0;
      transition: opacity 140ms ease;
      pointer-events: none;
    }}
    .audio-preview-meter.is-playing {{ opacity: 0.95; }}
    .audio-preview-meter-bar {{
      width: 3px;
      height: 2px;
      border-radius: 999px;
      background: rgba(252, 252, 252, 0.68);
      transform-origin: center bottom;
      transition: height 80ms linear;
    }}
    .save {{
      background: transparent !important;
      border: none !important;
      border-radius: 0 !important;
      padding: 14px 14px !important;
      color: rgba(252,252,252,0.96) !important;
      font-size: 15px !important;
      text-transform: none !important;
      letter-spacing: 0 !important;
      width: 100%;
      text-align: center;
      border-top: 0.5px solid var(--line) !important;
      margin-top: 0 !important;
    }}
    .app-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 12px;
    }}
    .app-button {{
      appearance: none;
      border: 0.5px solid var(--line-strong);
      background: rgba(255,255,255,0.04);
      color: rgba(252,252,252,0.94);
      border-radius: 12px;
      padding: 11px 14px;
      font-size: 14px;
      font-weight: 600;
      line-height: 1.25;
      cursor: pointer;
    }}
    .app-button[disabled] {{
      opacity: 0.48;
      cursor: default;
    }}
    .app-status-stack {{
      display: grid;
      gap: 6px;
      margin-top: 12px;
    }}
    .app-status {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}
    .app-help {{
      margin-top: 10px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 0.5px solid var(--line);
      background: rgba(255,255,255,0.03);
      color: rgba(252,252,252,0.9);
      font-size: 13px;
      line-height: 1.55;
    }}
  </style>
</head>
<body>
  <canvas id="starfield"></canvas>
  <div class="shell">
    __HUB_HEADER_HTML__
    <section class="hero">
      <div class="eyebrow">multiagent</div>
      <h1>Settings</h1>
      <div class="hub-nav">
        <a href="/">Hub</a>
        <a href="/new-session">New Session</a>
        <a href="/resume">Resume Sessions</a>
        <a href="/stats">Statistics</a>
        <a href="/settings" class="active">Settings</a>
        <form class="hub-restart-form" method="post" action="/restart-hub"><button type="submit">Restart Hub</button></form>
      </div>
    </section>
    <form class="panel" method="post" action="/settings">
      {notice}
      <div class="field">
        <label class="label" for="theme">Theme</label>
        <select id="theme" name="theme">
          {theme_options}
        </select>
        <div class="hint">{html.escape(theme_hint)}</div>
      </div>
      <div class="field">
        <div class="label">Chat Fonts</div>
        <div class="row">
          <div>
            <label class="label" for="user_message_font">User Messages</label>
            <select id="user_message_font" name="user_message_font">
              {font_options(user_message_font)}
            </select>
          </div>
          <div>
            <label class="label" for="agent_message_font">Agent Messages</label>
            <select id="agent_message_font" name="agent_message_font">
              {font_options(agent_message_font)}
            </select>
          </div>
        </div>
        <div class="hint">Pick independently for user and agent bubbles. The two built-in presets match the current Gothic and Mincho defaults, and the remaining choices come from fonts installed on this Mac.</div>
      </div>
      <div class="field">
        <label class="label" for="message_text_size">Message Text Size</label>
        <input id="message_text_size" name="message_text_size" type="number" min="11" max="18" step="1" value="{message_text_size}">
        <div class="hint">Applied in one shot to user and agent message bodies, file cards, inline code, code blocks, and tables.</div>
      </div>
      <input type="hidden" name="agent_font_mode" value="{font_mode}">
      <div class="field">
        <label class="label" for="message_limit">Default Message Count</label>
        <input id="message_limit" name="message_limit" type="number" min="10" max="2000" step="10" value="{message_limit}">
        <div class="hint">Single display default for chat reopen. Current practical ceiling is 2000.</div>
      </div>
      <div class="field">
        <label class="label" for="message_max_width">Message Max Width (px)</label>
        <input id="message_max_width" name="message_max_width" type="number" min="400" max="2000" step="10" value="{message_max_width}">
        <div class="hint">The horizontal constraint for the message display area. Desktop only. Mobile always fills the width. Default is 900.</div>
      </div>
      <div class="field">
        <div class="label">Chat Defaults</div>
        <div class="hint" style="margin-bottom:10px">Applied when a chat opens. Toggling from chat UI is disabled.</div>
        <div class="chat-toggles">
          <label class="toggle-row">
            <span>Auto mode</span>
            <input type="checkbox" name="chat_auto_mode" value="on"{' checked' if chat_auto else ''}>
          </label>
          <label class="toggle-row">
            <span class="toggle-row-copy">
              <span>Awake (prevent sleep)</span>
              <span class="audio-preview-meter" id="awakePreviewMeter" aria-hidden="true">
                <span class="audio-preview-meter-bar"></span>
                <span class="audio-preview-meter-bar"></span>
                <span class="audio-preview-meter-bar"></span>
              </span>
            </span>
            <input type="checkbox" name="chat_awake" value="on"{' checked' if chat_awake else ''}>
          </label>
          <label class="toggle-row">
            <span class="toggle-row-copy">
              <span>Sound notifications</span>
              <span class="audio-preview-meter" id="soundPreviewMeter" aria-hidden="true">
                <span class="audio-preview-meter-bar"></span>
                <span class="audio-preview-meter-bar"></span>
                <span class="audio-preview-meter-bar"></span>
              </span>
            </span>
            <input type="checkbox" name="chat_sound" value="on"{' checked' if chat_sound else ''}>
          </label>
          <label class="toggle-row">
            <span>Browser notifications</span>
            <input type="checkbox" name="chat_browser_notifications" value="on"{' checked' if chat_browser_notifications else ''}>
          </label>
          <label class="toggle-row">
            <span>Read aloud (TTS)</span>
            <input type="checkbox" name="chat_tts" value="on"{' checked' if chat_tts else ''}>
          </label>
        </div>
        <div class="hint" style="margin-top:10px">Browser notifications are managed at the Hub level. Once this Hub is installed and subscribed, background agent replies from any session can notify here.</div>
      </div>
      <div class="field" id="app-controls">
        <div class="label">App Install & Notifications</div>
        <div class="hint" style="margin-bottom:10px">Install Hub to the Home Screen, then allow browser notifications here. Hub will be the single notification endpoint for all sessions.</div>
        <div class="app-actions">
          <button class="app-button" type="button" id="installAppBtn">Install This App</button>
          <button class="app-button" type="button" id="notificationPermissionBtn">Allow Browser Notifications</button>
          <button class="app-button" type="button" id="testNotificationBtn">Send Test Notification</button>
        </div>
        <div class="app-status-stack">
          <div class="app-status" id="installStatus">Install status unavailable.</div>
          <div class="app-status" id="notificationStatus">Notification status unavailable.</div>
        </div>
        <div class="app-help" id="installHelp" hidden>
          On iPhone / iPad Safari, open the Share sheet and choose <strong>Add to Home Screen</strong>.<br>
          On other browsers, use the browser's install / add-to-home-screen action if the direct prompt does not appear.
        </div>
      </div>
      <div class="field">
        <div class="label">Visual Effects</div>
        <div class="chat-toggles">
          <label class="toggle-row">
            <span>Starfield background</span>
            <input type="checkbox" name="starfield" value="on"{' checked' if starfield else ''}>
          </label>
          <label class="toggle-row">
            <span>Bold mode (太字モード)</span>
            <input type="checkbox" name="bold_mode" value="on"{' checked' if bold_mode else ''}>
          </label>
        </div>
        <div class="hint">Animated starfield on Black Hole theme. Uncheck to disable. Claude theme never shows starfield. Bold mode makes all message text bold.</div>
      </div>
      <div class="field">
        <div class="label">Black Hole Text Opacity</div>
        <div class="row">
          <div class="slider-field">
            <div class="slider-topline">
              <label class="label" for="user_message_opacity_blackhole">User Messages</label>
              <span class="slider-value" id="user_message_opacity_blackhole_value">{user_message_opacity_blackhole:.2f}</span>
            </div>
            <input class="agent-slider-input" id="user_message_opacity_blackhole" name="user_message_opacity_blackhole" type="range" min="0.2" max="1" step="0.05" value="{user_message_opacity_blackhole:.2f}">
          </div>
          <div class="slider-field">
            <div class="slider-topline">
              <label class="label" for="agent_message_opacity_blackhole">Agent Messages</label>
              <span class="slider-value" id="agent_message_opacity_blackhole_value">{agent_message_opacity_blackhole:.2f}</span>
            </div>
            <input class="agent-slider-input" id="agent_message_opacity_blackhole" name="agent_message_opacity_blackhole" type="range" min="0.2" max="1" step="0.05" value="{agent_message_opacity_blackhole:.2f}">
          </div>
        </div>
        <div class="hint">Black Hole only. Lower values soften bright white text into gray without changing the rest of the theme.</div>
      </div>
      <button class="save" type="submit">Save Settings</button>
    </form>
  </div>
  <script>
    const hubRestartForm = document.querySelector(".hub-restart-form");
    if (hubRestartForm) {{
      hubRestartForm.addEventListener("submit", async (e) => {{
        e.preventDefault();
        const btn = e.currentTarget.querySelector("button");
        if (btn.classList.contains("restarting")) return;
        btn.classList.add("restarting");
        btn.disabled = true;
        btn.textContent = "Restarting\u2026";
        try {{ await fetch("/restart-hub", {{ method: "POST" }}); }} catch (_) {{}}
        const started = Date.now();
        const poll = async () => {{
          try {{
            const res = await fetch(`/sessions?ts=${{Date.now()}}`, {{ cache: "no-store" }});
            if (res.ok) {{ window.location.replace(window.location.pathname); return; }}
          }} catch (_) {{}}
          if (Date.now() - started < 20000) {{ setTimeout(poll, 500); }} else {{ window.location.reload(); }}
        }};
        setTimeout(poll, 700);
      }});
    }}

    // --- Starfield Animation ---
    const starCanvas = document.getElementById("starfield");
    const starCtx = starCanvas ? starCanvas.getContext("2d") : null;
    let stars = [];
    let shootingStars = [];
    const numStars = 360;
    let starAnimationId;
    let isStarAnimationRunning = false;

    function resizeStarCanvas() {{
      if (!starCanvas) return;
      starCanvas.width = window.innerWidth;
      starCanvas.height = window.innerHeight;
      initStars();
    }}
    function initStars() {{
      if (!starCanvas) return;
      const diagonal = Math.sqrt(starCanvas.width ** 2 + starCanvas.height ** 2);
      stars = Array.from({{ length: numStars }}, () => ({{
        angle: Math.random() * Math.PI * 2,
        radius: Math.random() * diagonal,
        speed: Math.random() * 0.0003 + 0.00015,
        size: Math.random() * 1.2 + 0.5,
      }}));
    }}
    function spawnShootingStar() {{
      if (shootingStars.length === 0 && Math.random() < 0.01) {{
        shootingStars.push({{
          x: Math.random() * starCanvas.width * 0.5,
          y: Math.random() * starCanvas.height * 0.5,
          vx: 3 + Math.random() * 2,
          vy: 1 + Math.random() * 1.5,
          life: 80,
          initialLife: 80,
        }});
      }}
    }}
    function animateStars() {{
      if (!isStarAnimationRunning) return;
      const centerX = starCanvas.width;
      const centerY = starCanvas.height;
      starCtx.fillStyle = "rgb(10, 10, 10)";
      starCtx.fillRect(0, 0, starCanvas.width, starCanvas.height);
      stars.forEach((star, i) => {{
        star.angle += star.speed;
        const x = centerX + star.radius * Math.cos(star.angle);
        const y = centerY + star.radius * Math.sin(star.angle);
        const flicker = 0.4 + Math.abs(Math.sin(Date.now() * 0.0015 + i)) * 0.5;
        starCtx.beginPath();
        starCtx.fillStyle = `rgba(255, 255, 255, ${{flicker}})`;
        starCtx.arc(x, y, star.size, 0, Math.PI * 2);
        starCtx.fill();
      }});
      spawnShootingStar();
      for (let i = shootingStars.length - 1; i >= 0; i--) {{
        const s = shootingStars[i];
        const opacity = s.life / s.initialLife;
        const grad = starCtx.createLinearGradient(s.x, s.y, s.x - s.vx * 35, s.y - s.vy * 35);
        grad.addColorStop(0, `rgba(255, 255, 255, ${{opacity}})`);
        grad.addColorStop(1, `rgba(255, 255, 255, 0)`);
        starCtx.strokeStyle = grad;
        starCtx.lineWidth = 2;
        starCtx.beginPath();
        starCtx.moveTo(s.x, s.y);
        starCtx.lineTo(s.x - s.vx * 18, s.y - s.vy * 18);
        starCtx.stroke();
        s.x += s.vx; s.y += s.vy; s.life -= 1;
        if (s.life <= 0) shootingStars.splice(i, 1);
      }}
      starAnimationId = requestAnimationFrame(animateStars);
    }}
    const updateStarAnimationState = () => {{
      if (!starCanvas) return;
      const shouldRun = document.documentElement.dataset.starfield !== "off";
      if (shouldRun && !isStarAnimationRunning) {{
        isStarAnimationRunning = true;
        resizeStarCanvas();
        animateStars();
      }} else if (!shouldRun && isStarAnimationRunning) {{
        isStarAnimationRunning = false;
        cancelAnimationFrame(starAnimationId);
      }}
    }};
    window.addEventListener("resize", () => {{ if (isStarAnimationRunning) resizeStarCanvas(); }});
    const themeObserver = new MutationObserver(updateStarAnimationState);
    themeObserver.observe(document.documentElement, {{ attributes: true, attributeFilter: ["data-theme", "data-starfield"] }});
    updateStarAnimationState();

    const setSliderFill = (input) => {{
      const min = Number(input.min || 0);
      const max = Number(input.max || 100);
      const value = Number(input.value || min);
      const ratio = max <= min ? 0 : (value - min) / (max - min);
      const pct = Math.max(0, Math.min(100, ratio * 100));
      input.style.setProperty("--slider-fill-pct", `${{pct}}%`);
    }};
    [["user_message_opacity_blackhole", "user_message_opacity_blackhole_value"], ["agent_message_opacity_blackhole", "agent_message_opacity_blackhole_value"]].forEach(([inputId, valueId]) => {{
      const input = document.getElementById(inputId);
      const output = document.getElementById(valueId);
      if (!input || !output) return;
      const sync = () => {{
        output.textContent = Number(input.value || 1).toFixed(2);
        setSliderFill(input);
      }};
      input.addEventListener("input", sync);
      sync();
    }});

    const chatSoundToggle = document.querySelector('input[name="chat_sound"]');
    if (chatSoundToggle) {{
      const previewAudio = new Audio('/notify-sound?name=mictest.ogg');
      previewAudio.preload = 'auto';
      const previewMeter = document.getElementById('soundPreviewMeter');
      const previewMeterBars = previewMeter ? Array.from(previewMeter.querySelectorAll('.audio-preview-meter-bar')) : [];
      let previewAudioCtx = null;
      let previewAnalyser = null;
      let previewSource = null;
      let previewMeterFrame = 0;
      let previewMeterData = null;
      const resetPreviewMeter = () => {{
        if (previewMeter) previewMeter.classList.remove('is-playing');
        previewMeterBars.forEach((bar) => {{
          bar.style.height = '2px';
        }});
      }};
      const stopPreviewMeter = () => {{
        if (previewMeterFrame) {{
          cancelAnimationFrame(previewMeterFrame);
          previewMeterFrame = 0;
        }}
        resetPreviewMeter();
      }};
      const ensurePreviewMeterAudio = async () => {{
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx || previewAnalyser) return;
        previewAudioCtx = new AudioCtx();
        previewAnalyser = previewAudioCtx.createAnalyser();
        previewAnalyser.fftSize = 64;
        previewAnalyser.smoothingTimeConstant = 0.82;
        previewMeterData = new Uint8Array(previewAnalyser.frequencyBinCount);
        previewSource = previewAudioCtx.createMediaElementSource(previewAudio);
        previewSource.connect(previewAnalyser);
        previewAnalyser.connect(previewAudioCtx.destination);
      }};
      const drawPreviewMeter = () => {{
        if (!previewAnalyser || !previewMeterData || previewAudio.paused || previewAudio.ended) {{
          stopPreviewMeter();
          return;
        }}
        previewAnalyser.getByteFrequencyData(previewMeterData);
        const groups = [
          previewMeterData.slice(1, 4),
          previewMeterData.slice(4, 10),
          previewMeterData.slice(10, 18),
        ];
        if (previewMeter) previewMeter.classList.add('is-playing');
        previewMeterBars.forEach((bar, index) => {{
          const group = groups[index] || [];
          const avg = group.length ? group.reduce((sum, value) => sum + value, 0) / group.length : 0;
          const nextHeight = Math.max(2, Math.min(14, Math.round((avg / 255) * 12) + 2));
          bar.style.height = `${{nextHeight}}px`;
        }});
        previewMeterFrame = requestAnimationFrame(drawPreviewMeter);
      }};
      const playSoundPreview = () => {{
        try {{
          previewAudio.pause();
          previewAudio.currentTime = 0;
          ensurePreviewMeterAudio()
            .then(async () => {{
              if (previewAudioCtx && previewAudioCtx.state === 'suspended') {{
                try {{
                  await previewAudioCtx.resume();
                }} catch (_) {{}}
              }}
              stopPreviewMeter();
              const result = previewAudio.play();
              if (result && typeof result.catch === 'function') {{
                result.catch(() => {{
                  stopPreviewMeter();
                }});
              }}
              drawPreviewMeter();
            }})
            .catch(() => {{
              resetPreviewMeter();
            }});
        }} catch (_) {{}}
      }};
      previewAudio.addEventListener('ended', stopPreviewMeter);
      previewAudio.addEventListener('pause', () => {{
        if (!previewAudio.ended) stopPreviewMeter();
      }});
      chatSoundToggle.addEventListener('change', () => {{
        if (chatSoundToggle.checked) {{
          playSoundPreview();
        }}
      }});
    }}

    const chatAwakeToggle = document.querySelector('input[name="chat_awake"]');
    if (chatAwakeToggle) {{
      const awakeAudio = new Audio('/notify-sound?name=awake.ogg');
      awakeAudio.preload = 'auto';
      const awakeMeter = document.getElementById('awakePreviewMeter');
      const awakeMeterBars = awakeMeter ? Array.from(awakeMeter.querySelectorAll('.audio-preview-meter-bar')) : [];
      let awakeAudioCtx = null;
      let awakeAnalyser = null;
      let awakeSource = null;
      let awakeMeterFrame = 0;
      let awakeMeterData = null;
      const resetAwakeMeter = () => {{
        if (awakeMeter) awakeMeter.classList.remove('is-playing');
        awakeMeterBars.forEach((bar) => {{ bar.style.height = '2px'; }});
      }};
      const stopAwakeMeter = () => {{
        if (awakeMeterFrame) {{ cancelAnimationFrame(awakeMeterFrame); awakeMeterFrame = 0; }}
        resetAwakeMeter();
      }};
      const ensureAwakeMeterAudio = async () => {{
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx || awakeAnalyser) return;
        awakeAudioCtx = new AudioCtx();
        awakeAnalyser = awakeAudioCtx.createAnalyser();
        awakeAnalyser.fftSize = 64;
        awakeAnalyser.smoothingTimeConstant = 0.82;
        awakeMeterData = new Uint8Array(awakeAnalyser.frequencyBinCount);
        awakeSource = awakeAudioCtx.createMediaElementSource(awakeAudio);
        awakeSource.connect(awakeAnalyser);
        awakeAnalyser.connect(awakeAudioCtx.destination);
      }};
      const drawAwakeMeter = () => {{
        if (!awakeAnalyser || !awakeMeterData || awakeAudio.paused || awakeAudio.ended) {{
          stopAwakeMeter(); return;
        }}
        awakeAnalyser.getByteFrequencyData(awakeMeterData);
        const groups = [awakeMeterData.slice(1, 4), awakeMeterData.slice(4, 10), awakeMeterData.slice(10, 18)];
        if (awakeMeter) awakeMeter.classList.add('is-playing');
        awakeMeterBars.forEach((bar, index) => {{
          const group = groups[index] || [];
          const avg = group.length ? group.reduce((sum, value) => sum + value, 0) / group.length : 0;
          bar.style.height = `${{Math.max(2, Math.min(14, Math.round((avg / 255) * 12) + 2))}}px`;
        }});
        awakeMeterFrame = requestAnimationFrame(drawAwakeMeter);
      }};
      awakeAudio.addEventListener('ended', stopAwakeMeter);
      awakeAudio.addEventListener('pause', () => {{ if (!awakeAudio.ended) stopAwakeMeter(); }});
      chatAwakeToggle.addEventListener('change', () => {{
        if (chatAwakeToggle.checked && chatSoundToggle && chatSoundToggle.checked) {{
          try {{
            awakeAudio.pause(); awakeAudio.currentTime = 0;
            ensureAwakeMeterAudio().then(async () => {{
              if (awakeAudioCtx && awakeAudioCtx.state === 'suspended') {{ try {{ await awakeAudioCtx.resume(); }} catch (_) {{}} }}
              stopAwakeMeter();
              const result = awakeAudio.play();
              if (result && typeof result.catch === 'function') {{ result.catch(() => {{ stopAwakeMeter(); }}); }}
              drawAwakeMeter();
            }}).catch(() => {{ resetAwakeMeter(); }});
          }} catch (_) {{}}
        }}
      }});
    }}

    const installAppBtn = document.getElementById('installAppBtn');
    const installStatus = document.getElementById('installStatus');
    const installHelp = document.getElementById('installHelp');
    const notificationPermissionBtn = document.getElementById('notificationPermissionBtn');
    const testNotificationBtn = document.getElementById('testNotificationBtn');
    const notificationStatus = document.getElementById('notificationStatus');
    const chatBrowserNotificationToggle = document.querySelector('input[name="chat_browser_notifications"]');
    let deferredInstallPrompt = null;
    const hubPushClientId = (() => {{
      const fallback = `hub-push-${{Date.now()}}-${{Math.random().toString(36).slice(2, 10)}}`;
      try {{
        const key = "multiagentHubPushClientId";
        const current = localStorage.getItem(key);
        if (current) return current;
        const created = (window.crypto && typeof window.crypto.randomUUID === 'function')
          ? window.crypto.randomUUID()
          : fallback;
        localStorage.setItem(key, created);
        return created;
      }} catch (_) {{
        return fallback;
      }}
    }})();
    const isStandaloneApp = () => window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    const isIOS = /iphone|ipad|ipod/i.test(window.navigator.userAgent || "");
    const isSafari = /^((?!chrome|android).)*safari/i.test(window.navigator.userAgent || "");
    const supportsNotificationApi = typeof window.Notification !== 'undefined';
    const supportsPushNotifications = 'serviceWorker' in navigator && 'PushManager' in window;
    const notificationIconUrl = `${{window.location.origin}}/pwa-icon-192.png`;
    const notificationTargetUrl = `${{window.location.origin}}${{window.location.pathname}}${{window.location.search || ''}}`;
    let hubPushActive = false;
    let hubPushSyncPromise = null;
    let lastHubPushPresenceSig = "";
    const urlB64ToUint8Array = (raw) => {{
      const text = String(raw || "").trim();
      if (!text) return new Uint8Array();
      const pad = "=".repeat((4 - (text.length % 4 || 4)) % 4);
      const normalized = (text + pad).replace(/-/g, "+").replace(/_/g, "/");
      const decoded = atob(normalized);
      return Uint8Array.from(decoded, (char) => char.charCodeAt(0));
    }};
    const uint8ArrayToUrlB64 = (raw) => {{
      const bytes = raw instanceof Uint8Array ? raw : new Uint8Array(raw || []);
      let binary = "";
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      return btoa(binary).replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/g, "");
    }};
    const hubPushSubscriptionPayload = (subscription) => {{
      if (!subscription) return null;
      const payload = subscription.toJSON ? subscription.toJSON() : {{}};
      const keys = {{ ...(payload?.keys || {{}}) }};
      try {{
        if (!keys.p256dh && typeof subscription.getKey === 'function') {{
          const p256dh = subscription.getKey('p256dh');
          if (p256dh) keys.p256dh = uint8ArrayToUrlB64(new Uint8Array(p256dh));
        }}
        if (!keys.auth && typeof subscription.getKey === 'function') {{
          const auth = subscription.getKey('auth');
          if (auth) keys.auth = uint8ArrayToUrlB64(new Uint8Array(auth));
        }}
      }} catch (_) {{}}
      return {{
        endpoint: subscription.endpoint || payload?.endpoint || "",
        expirationTime: subscription.expirationTime ?? payload?.expirationTime ?? null,
        keys,
      }};
    }};
    const postHubPushPresence = async ({{ force = false, keepalive = false }} = {{}}) => {{
      if (!hubPushActive) return;
      try {{
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        const body = {{
          client_id: hubPushClientId,
          endpoint: subscription?.endpoint || "",
          visible: !document.hidden,
          focused: typeof document.hasFocus === 'function' ? document.hasFocus() : !document.hidden,
        }};
        const sig = JSON.stringify(body);
        if (!force && sig === lastHubPushPresenceSig) return;
        lastHubPushPresenceSig = sig;
        await fetch('/push/presence', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          cache: 'no-store',
          keepalive,
          body: sig,
        }});
      }} catch (_) {{}}
    }};
    const syncHubPushSubscription = async ({{ unsubscribeOnly = false }} = {{}}) => {{
      if (!supportsPushNotifications || !supportsNotificationApi) {{
        hubPushActive = false;
        return false;
      }}
      if (hubPushSyncPromise) return hubPushSyncPromise;
      hubPushSyncPromise = (async () => {{
        const registration = await navigator.serviceWorker.ready;
        let subscription = await registration.pushManager.getSubscription();
        if (
          unsubscribeOnly
          || !chatBrowserNotificationToggle?.checked
          || Notification.permission !== 'granted'
        ) {{
          hubPushActive = false;
          lastHubPushPresenceSig = "";
          if (subscription) {{
            try {{
              await fetch('/push/unsubscribe', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                cache: 'no-store',
                keepalive: true,
                body: JSON.stringify({{
                  client_id: hubPushClientId,
                  endpoint: subscription.endpoint || "",
                }}),
              }});
            }} catch (_) {{}}
            try {{ await subscription.unsubscribe(); }} catch (_) {{}}
          }}
          return false;
        }}
        const configRes = await fetch(`/push-config?ts=${{Date.now()}}`, {{ cache: 'no-store' }});
        if (!configRes.ok) {{
          hubPushActive = false;
          return false;
        }}
        const config = await configRes.json();
        const publicKey = String(config?.public_key || '').trim();
        if (!publicKey || !config?.enabled) {{
          hubPushActive = false;
          return false;
        }}
        if (!subscription) {{
          subscription = await registration.pushManager.subscribe({{
            userVisibleOnly: true,
            applicationServerKey: urlB64ToUint8Array(publicKey),
          }});
        }}
        const subPayload = hubPushSubscriptionPayload(subscription);
        if (!subPayload || !subPayload.endpoint || !subPayload.keys?.p256dh || !subPayload.keys?.auth) {{
          hubPushActive = false;
          return false;
        }}
        const saveRes = await fetch('/push/subscribe', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          cache: 'no-store',
          body: JSON.stringify({{
            client_id: hubPushClientId,
            user_agent: navigator.userAgent || '',
            subscription: subPayload,
          }}),
        }});
        if (!saveRes.ok) {{
          hubPushActive = false;
          return false;
        }}
        hubPushActive = true;
        await postHubPushPresence({{ force: true }});
        return true;
      }})().catch(() => {{
        hubPushActive = false;
        return false;
      }}).finally(() => {{
        hubPushSyncPromise = null;
      }});
      return hubPushSyncPromise;
    }};
    const updateInstallUi = () => {{
      if (!installAppBtn || !installStatus || !installHelp) return;
      installHelp.hidden = true;
      if (isStandaloneApp()) {{
        installAppBtn.disabled = true;
        installAppBtn.textContent = 'Installed';
        installStatus.textContent = 'This page is already running in standalone app mode.';
        return;
      }}
      installAppBtn.disabled = false;
      if (deferredInstallPrompt) {{
        installAppBtn.textContent = 'Install This App';
        installStatus.textContent = 'Install prompt is ready on this device.';
        return;
      }}
      if (isIOS && isSafari) {{
        installAppBtn.textContent = 'Show iPhone Install Steps';
        installStatus.textContent = 'On iPhone / iPad, installation is done from Safari via the Share sheet.';
        return;
      }}
      installAppBtn.textContent = 'Show Install Help';
      installStatus.textContent = 'If no direct prompt appears, use the browser install / add-to-home-screen action.';
    }};
    const updateNotificationUi = () => {{
      if (!notificationPermissionBtn || !testNotificationBtn || !notificationStatus) return;
      const wantsBrowserNotifications = !!chatBrowserNotificationToggle?.checked;
      if (!supportsNotificationApi) {{
        notificationPermissionBtn.disabled = true;
        testNotificationBtn.disabled = true;
        notificationStatus.textContent = 'This browser does not expose the Web Notifications API.';
        return;
      }}
      const permission = Notification.permission;
      testNotificationBtn.hidden = permission !== 'granted';
      testNotificationBtn.disabled = permission !== 'granted';
      if (permission === 'granted') {{
        notificationPermissionBtn.disabled = true;
        notificationPermissionBtn.textContent = 'Browser Notifications Enabled';
        notificationStatus.textContent = wantsBrowserNotifications
          ? 'Permission granted. Save Settings to keep Hub notifications enabled for all sessions on this device.'
          : 'Permission granted. Turn on Browser notifications above and Save Settings if you want Hub notifications for all sessions.';
        return;
      }}
      if (permission === 'denied') {{
        notificationPermissionBtn.disabled = true;
        notificationPermissionBtn.textContent = 'Browser Notifications Blocked';
        notificationStatus.textContent = 'Browser notifications are blocked here. Re-enable them from browser settings if you want this feature.';
        return;
      }}
      notificationPermissionBtn.disabled = false;
      notificationPermissionBtn.textContent = 'Allow Browser Notifications';
      notificationStatus.textContent = wantsBrowserNotifications
        ? 'Permission not granted yet. Click Allow Browser Notifications, then Save Settings.'
        : 'Turn on Browser notifications above if you want the Hub to notify you in the background.';
    }};
    const showTestNotification = async () => {{
      if (!supportsNotificationApi || Notification.permission !== 'granted') return;
      try {{
        const registration = ('serviceWorker' in navigator) ? await navigator.serviceWorker.ready : null;
        if (registration && typeof registration.showNotification === 'function') {{
          await registration.showNotification('multiagent notifications', {{
            body: 'Browser notifications are working on this device.',
            tag: 'multiagent-notification-test',
            icon: notificationIconUrl,
            badge: notificationIconUrl,
            data: {{ url: notificationTargetUrl }},
          }});
          return;
        }}
      }} catch (_) {{}}
      try {{
        const notification = new Notification('multiagent notifications', {{
          body: 'Browser notifications are working on this device.',
          icon: notificationIconUrl,
          tag: 'multiagent-notification-test',
        }});
        notification.onclick = () => {{
          window.focus();
          notification.close();
        }};
      }} catch (_) {{}}
    }};
    if (chatBrowserNotificationToggle) {{
      chatBrowserNotificationToggle.addEventListener('change', () => {{
        updateNotificationUi();
        syncHubPushSubscription(chatBrowserNotificationToggle.checked ? {{}} : {{ unsubscribeOnly: true }}).catch(() => {{}});
      }});
    }}
    if (installAppBtn) {{
      installAppBtn.addEventListener('click', async () => {{
        if (deferredInstallPrompt) {{
          try {{
            deferredInstallPrompt.prompt();
            await deferredInstallPrompt.userChoice;
          }} catch (_) {{}}
          deferredInstallPrompt = null;
          updateInstallUi();
          return;
        }}
        if (installHelp) {{
          installHelp.hidden = false;
          installHelp.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
        }}
      }});
    }}
    window.addEventListener('beforeinstallprompt', (event) => {{
      event.preventDefault();
      deferredInstallPrompt = event;
      updateInstallUi();
    }});
    window.addEventListener('appinstalled', () => {{
      deferredInstallPrompt = null;
      updateInstallUi();
    }});
    if (notificationPermissionBtn) {{
      notificationPermissionBtn.addEventListener('click', async () => {{
        if (!supportsNotificationApi) return;
        try {{
          await Notification.requestPermission();
        }} catch (_) {{}}
        updateNotificationUi();
        syncHubPushSubscription().catch(() => {{}});
      }});
    }}
    if (testNotificationBtn) {{
      testNotificationBtn.addEventListener('click', () => {{
        showTestNotification();
      }});
    }}
    updateInstallUi();
    updateNotificationUi();
    syncHubPushSubscription().catch(() => {{}});
    document.addEventListener('visibilitychange', () => {{
      if (!document.hidden) {{
        syncHubPushSubscription().catch(() => {{}});
      }}
      postHubPushPresence({{ force: true, keepalive: document.hidden }}).catch(() => {{}});
    }});
    window.addEventListener('focus', () => {{ postHubPushPresence({{ force: true }}).catch(() => {{}}); }});
    window.addEventListener('blur', () => {{ postHubPushPresence({{ force: true, keepalive: true }}).catch(() => {{}}); }});
    window.addEventListener('pageshow', () => {{ postHubPushPresence({{ force: true }}).catch(() => {{}}); }});
    window.addEventListener('pagehide', () => {{ postHubPushPresence({{ force: true, keepalive: true }}).catch(() => {{}}); }});
    setInterval(() => {{ postHubPushPresence().catch(() => {{}}); }}, 20000);

  __HUB_HEADER_JS__
  </script>
</body>
</html>"""
    return (
        _html
        .replace("__HUB_HEADER_CSS__", _HUB_PAGE_HEADER_CSS)
        .replace("__HUB_HEADER_HTML__", _HUB_PAGE_HEADER_HTML)
        .replace("__HUB_HEADER_JS__", _HUB_PAGE_HEADER_JS)
    )

HUB_NEW_SESSION_HTML = """<!doctype html>
<html lang="en" data-theme="__CHAT_THEME__"__STARFIELD_ATTR__>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="rgb(10, 10, 10)">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Session Hub">
  <link rel="manifest" href="__HUB_MANIFEST_URL__">
  <link rel="icon" type="image/png" sizes="192x192" href="__PWA_ICON_192_URL__">
  <link rel="apple-touch-icon" href="__APPLE_TOUCH_ICON_URL__">
  <script>
    (() => {
      if (!("serviceWorker" in navigator)) return;
      const isLocalHost = location.hostname === "localhost" || location.hostname === "127.0.0.1" || location.hostname === "[::1]";
      if (!(window.isSecureContext || isLocalHost)) return;
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/hub-service-worker.js", { scope: "/" }).catch((err) => {
          console.warn("hub service worker registration failed", err);
        });
      }, { once: true });
    })();
  </script>
  <title>New Session \u00b7 Hub</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: rgb(10, 10, 10);
      --bg-rgb: 10, 10, 10;
      --panel: rgb(20, 20, 20);
      --panel-2: rgb(15, 15, 15);
      --line: rgba(255,255,255,0.06);
      --line-strong: rgba(255,255,255,0.10);
      --fg: rgb(252, 252, 252);
      --muted: rgb(158, 158, 158);
      --accent: rgb(44, 132, 219);
    }
    html[data-theme="soft-light"] {
      color-scheme: light;
      --bg: rgb(244, 244, 242);
      --bg-rgb: 244, 244, 242;
      --panel: rgb(255, 255, 255);
      --panel-2: rgb(248, 248, 246);
      --line: rgba(15, 20, 30, 0.12);
      --line-strong: rgba(15, 20, 30, 0.2);
      --fg: rgb(26, 30, 36);
      --muted: rgb(98, 106, 120);
      --accent: rgb(44, 132, 219);
    }
    #starfield {
      position: fixed;
      top: 0;
      left: 0;
      z-index: 1;
      width: 100%;
      height: 100%;
      display: none;
      pointer-events: none;
    }
    :not([data-starfield="off"]) #starfield {
      display: block;
    }
    html[data-theme="soft-light"] #starfield {
      display: none !important;
    }
    :not([data-starfield="off"]) body {
      background: transparent !important;
    }
    :not([data-starfield="off"]) html {
      background: var(--bg) !important;
    }
    :not([data-starfield="off"]) .shell {
      background: transparent !important;
      position: relative;
      z-index: 2;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; background: var(--bg); color: var(--fg); font-family: "SF Pro Text", "Segoe UI", sans-serif; }
    body { padding: 0 0 max(20px, env(safe-area-inset-bottom)) 0; }
    .shell { max-width: 900px; margin: 0 auto; }
    .shell > :not(.hub-page-header) { padding-left: 14px; padding-right: 14px; }
    .hero { padding: 8px 2px 18px 2px; }
    .eyebrow { color: var(--fg); opacity: 0.8; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; }
    h1 { margin: 0; font-size: clamp(26px, 5vw, 38px); line-height: 1.02; font-weight: 600; letter-spacing: -0.03em; }
    .sub { margin-top: 10px; color: var(--fg); opacity: 0.85; font-size: 14px; line-height: 1.55; max-width: 38rem; }
    .hub-nav { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; width: 100%; align-items: center; }
    .hub-nav a { color: var(--fg); opacity: 0.8; text-decoration: none; border: 0.5px solid var(--line); background: var(--panel); border-radius: 999px; padding: 6px 10px; font-size: 12px; line-height: 1; letter-spacing: 0.04em; text-transform: uppercase; }
    .hub-nav a.active { color: var(--fg); opacity: 1; border-color: var(--line-strong); }
    .hub-nav form { margin: 0; }
    .hub-nav .hub-restart-form { margin-left: auto; }
    .hub-nav button { color: var(--fg); opacity: 0.8; border: 0.5px solid var(--line); background: var(--panel); border-radius: 999px; padding: 6px 10px; font: inherit; font-size: 12px; font-weight: 400; line-height: 1; letter-spacing: 0.04em; text-transform: uppercase; cursor: pointer; appearance: none; -webkit-appearance: none; }
    .hub-nav .hub-restart-form button { color: var(--accent); opacity: 1; }
    @keyframes hubRestartingPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    .hub-nav button.restarting { animation: hubRestartingPulse 900ms ease-in-out infinite; pointer-events: none; }
    .hub-nav { display: none !important; }
    .form-panel {
      background: transparent !important;
      border: none !important;
      border-bottom: 0.5px solid var(--line) !important;
      border-radius: 0 !important;
      padding: 14px 14px !important;
      margin-bottom: 0 !important;
    }
    .form-panel:first-of-type { border-top: 0.5px solid var(--line) !important; }
    .field-label { display: block; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--fg); opacity: 0.9; margin-bottom: 10px; }
    .field-note { margin: -2px 0 10px; color: var(--fg); opacity: 0.66; font-size: 13px; line-height: 1.45; }
    .field-label .opt { opacity: 0.65; text-transform: none; font-size: 11px; letter-spacing: 0; }
    input[type="text"] { width: 100%; border: 0.5px solid var(--line-strong); background: var(--panel-2); color: var(--fg); border-radius: 12px; padding: 11px 13px; font-size: 16px; line-height: 1.25; outline: none; font-family: inherit; appearance: none; -webkit-appearance: none; position: relative; z-index: 4; }
    input[type="text"]::placeholder { color: var(--muted); }
    input[type="text"]:focus { border-color: rgba(255,255,255,0.22); }
    html[data-theme="black-hole"] input[type="text"] {
      background: linear-gradient(145deg, rgb(20, 20, 20) 0%, rgb(10, 10, 10) 100%) !important;
      backdrop-filter: blur(20px) saturate(160%) !important;
      -webkit-backdrop-filter: blur(20px) saturate(160%) !important;
      border: 0.5px solid rgba(255, 255, 255, 0.1) !important;
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8) !important;
    }
    html[data-theme="soft-light"] input[type="text"] {
      background: linear-gradient(145deg, rgb(255, 255, 255) 0%, rgb(246, 246, 244) 100%) !important;
      border: 0.5px solid rgba(15, 20, 30, 0.14) !important;
      box-shadow: 0 8px 24px rgba(15, 20, 30, 0.08) !important;
      backdrop-filter: none !important;
      -webkit-backdrop-filter: none !important;
      color: var(--fg) !important;
    }
    .workspace-stack { display: flex; flex-direction: column; gap: 10px; }
    .workspace-input-wrap { position: relative; flex: 1; min-width: 0; }
    .workspace-icon {
      position: absolute;
      left: 13px;
      top: 50%;
      transform: translateY(-50%);
      width: 18px;
      height: 18px;
      color: var(--muted);
      opacity: 0.72;
      pointer-events: none;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    #workspace-path { padding-left: 40px; }
    #workspace-path:focus + .workspace-icon,
    .workspace-input-wrap:focus-within .workspace-icon { color: var(--fg); opacity: 0.95; }
    .recent-list { margin: 0; display: flex; flex-direction: column; border: 0.5px solid var(--line-strong); background: var(--panel-2); border-radius: 12px; position: relative; }
    .recent-list:empty { display: none; }
    .recent-item { display: flex; align-items: center; padding: 12px 14px; border-top: 0.5px solid var(--line); background: transparent; cursor: pointer; gap: 14px; transition: background 150ms ease; }
    .recent-item:first-child { border-top: none; }
    .recent-item:hover { background: rgba(255,255,255,0.03); }
    .recent-item:active { background: rgba(255,255,255,0.06); }
    .recent-item.selected { background: rgba(255, 255, 255, 0.05); border-left: 2px solid var(--fg); padding-left: 12px; }
    .recent-name { font-size: 14px; font-weight: 600; color: var(--fg); }
    .recent-path { font-size: 11px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: "SF Mono", "Fira Code", monospace; opacity: 0.7; }
    .browse-toggle {
      width: 100%;
      min-width: 0;
      padding: 12px 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      background: var(--panel-2);
      border: 0.5px solid var(--line-strong);
      color: var(--muted);
      border-radius: 12px;
      font: inherit;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.01em;
      cursor: pointer;
      transition: all 150ms ease;
      appearance: none;
      -webkit-appearance: none;
      box-sizing: border-box;
      white-space: nowrap;
    }
    .browse-toggle:hover { color: var(--fg); background: rgba(255,255,255,0.03); }
    .browse-toggle[data-open="1"] { color: var(--fg); background: rgba(255,255,255,0.05); }
    .browse-toggle svg { width: 15px; height: 15px; flex-shrink: 0; }
    .dir-browser { margin: 0; border: 0.5px solid var(--line-strong); border-radius: 12px; background: var(--panel-2); position: relative; overflow: hidden; box-sizing: border-box; }
    .dir-breadcrumb { padding: 10px 14px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--fg); border-bottom: 0.5px solid var(--line); background: rgba(255,255,255,0.02); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: "SF Mono", "Fira Code", monospace; display: flex; align-items: center; gap: 6px; }
    .dir-breadcrumb::before { content: "$"; opacity: 0.5; font-weight: 700; }
    .dir-entries { max-height: 320px; overflow-y: auto; }
    .dir-entries::-webkit-scrollbar { width: 4px; }
    .dir-entries::-webkit-scrollbar-thumb { background: var(--line-strong); }
    .dir-entry { display: flex; align-items: center; padding: 10px 14px; font-size: 13px; cursor: pointer; border-bottom: 0.5px solid var(--line); gap: 10px; transition: background 120ms ease, color 120ms ease; color: var(--muted); }
    .dir-entry:last-child { border-bottom: none; }
    .dir-entry:hover { background: rgba(255,255,255,0.04); color: var(--fg); }
    .dir-entry .chevron { margin-left: auto; color: var(--muted); opacity: 0.4; display: flex; align-items: center; }
    .dir-entry .dir-icon { flex-shrink: 0; display: flex; align-items: center; color: inherit; opacity: 0.8; }
    .dir-use { display: block; padding: 12px 14px; text-align: center; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--fg); border-top: 0.5px solid var(--line); cursor: pointer; background: rgba(255,255,255,0.02); border-left: none; border-right: none; border-bottom: none; font-family: inherit; width: 100%; transition: background 150ms ease, opacity 150ms ease; }
    .dir-use:hover { background: rgba(255, 255, 255, 0.06); }
    .agent-sliders { display: flex; flex-direction: column; }
    .agent-slider-row { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 0.5px solid var(--line); }
    .agent-slider-row:last-child { border-bottom: none; }
    .agent-slider-name { display: inline-flex; align-items: center; gap: 8px; font-size: 15px; color: var(--fg); min-width: 92px; }
    .agent-slider-name.zero { color: var(--muted); }
    .agent-slider-icon { width: 16px; height: 16px; object-fit: contain; flex-shrink: 0; filter: brightness(0) invert(1); opacity: 0.95; }
    .agent-slider-wrap { flex: 1; display: flex; align-items: center; gap: 10px; }
    .agent-slider-input {
      flex: 1; -webkit-appearance: none; appearance: none; height: 4px; border-radius: 2px;
      --slider-fill: rgba(252,252,252,0.96);
      --slider-fill-pct: 5%;
      background: linear-gradient(to right, var(--slider-fill) 0 var(--slider-fill-pct), rgba(255,255,255,0.20) var(--slider-fill-pct) 100%);
      outline: none; cursor: pointer;
    }
    .agent-slider-input::-webkit-slider-runnable-track {
      height: 4px;
      border-radius: 2px;
      background: transparent;
    }
    .agent-slider-input::-moz-range-track {
      height: 4px;
      border-radius: 2px;
      background: rgba(255,255,255,0.20);
    }
    .agent-slider-input::-moz-range-progress {
      height: 4px;
      border-radius: 2px;
      background: var(--slider-fill);
    }
    .agent-slider-input::-webkit-slider-thumb {
      -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%;
      background: var(--slider-fill); border: 1px solid rgba(0,0,0,0.18); cursor: pointer;
      margin-top: -8px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.3);
    }
    .agent-slider-input::-moz-range-thumb {
      width: 20px; height: 20px; border-radius: 50%;
      background: var(--slider-fill); border: 1px solid rgba(0,0,0,0.18); cursor: pointer;
    }
    .agent-slider-val { font-size: 15px; min-width: 20px; text-align: center; font-variant-numeric: tabular-nums; color: var(--fg); }
    .agent-slider-val.zero { color: var(--muted); }
    html[data-theme="soft-light"] .agent-slider-icon {
      filter: brightness(0) invert(0);
      opacity: 1;
    }
    html[data-theme="soft-light"] .agent-slider-input {
      background: linear-gradient(to right, var(--slider-fill) 0 var(--slider-fill-pct), rgba(15,20,30,0.12) var(--slider-fill-pct) 100%);
    }
    html[data-theme="soft-light"] .agent-slider-input::-moz-range-track {
      background: rgba(15,20,30,0.12);
    }
    .start-btn { margin: 8px 14px 0; width: calc(100% - 28px); padding: 14px; background: rgba(255,255,255,0.05); border: 0.5px solid var(--line-strong); border-radius: 14px; color: rgba(252,252,252,0.96); font-size: 16px; font-weight: 600; font-family: inherit; cursor: pointer; letter-spacing: -0.01em; transition: all 200ms ease; }
    .start-btn:hover:not(:disabled) { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.25); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
    .start-btn:active:not(:disabled) { transform: translateY(0); }
    .start-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .error-msg { margin: 14px 14px 0; padding: 12px 16px; border-radius: 12px; background: rgba(214,124,124,0.1); border: 0.5px solid rgba(214,124,124,0.25); color: rgb(232, 146, 146); font-size: 14px; line-height: 1.4; }
    .hub-nav a.active {
      background: var(--bg) !important;
      border-color: rgba(255, 255, 255, 0.2) !important;
    }
    html[data-theme="soft-light"] .recent-item:hover { background: rgba(15,20,30,0.03); }
    html[data-theme="soft-light"] .recent-item.selected { background: rgba(15,20,30,0.04); border-left-color: var(--fg); }
    html[data-theme="soft-light"] .dir-entry:hover { background: rgba(15,20,30,0.03); }
    html[data-theme="soft-light"] .browse-toggle:hover { background: rgba(15,20,30,0.02); }
    html[data-theme="soft-light"] .browse-toggle[data-open="1"] { background: rgba(15,20,30,0.05); }
    html[data-theme="soft-light"] .dir-breadcrumb { color: var(--fg); background: rgba(15,20,30,0.02); }
    html[data-theme="soft-light"] .dir-use { color: var(--fg); background: rgba(15,20,30,0.02); }
    html[data-theme="soft-light"] .dir-use:hover { background: rgba(15, 20, 30, 0.05); }
    html[data-theme="soft-light"] .start-btn { background: rgba(15,20,30,0.03); border-color: var(--line); color: var(--fg); }
    html[data-theme="soft-light"] .start-btn:hover:not(:disabled) { background: rgba(15,20,30,0.06); border-color: var(--line-strong); }
  __HUB_HEADER_CSS__
  </style>
</head>
<body>
  <canvas id="starfield"></canvas>
  <div class="shell">
    __HUB_HEADER_HTML__
    <section class="hero">
      <div class="eyebrow">multiagent</div>
      <h1>New Session</h1>
      <div class="hub-nav">
        <a href="/">Hub</a>
        <a href="/new-session" class="active">New Session</a>
        <a href="/resume">Resume Sessions</a>
        <a href="/stats">Statistics</a>
        <a href="/settings">Settings</a>
        <form class="hub-restart-form" method="post" action="/restart-hub"><button type="submit">Restart Hub</button></form>
      </div>
    </section>

    <div class="form-panel">
      <label class="field-label" for="session-name">Session Name <span class="opt">(optional \u2014 defaults to folder name)</span></label>
      <input type="text" id="session-name" placeholder="e.g. myproject">
    </div>

    <div class="form-panel">
      <label class="field-label" for="workspace-path">Workspace</label>
      <div class="workspace-stack">
        <div class="workspace-input-wrap">
          <input type="text" id="workspace-path" placeholder="/path/to/project">
          <span class="workspace-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></span>
        </div>
        <div id="recent-list" class="recent-list"></div>
        <button type="button" class="browse-toggle" id="browse-toggle" aria-expanded="false"></button>
        <div class="dir-browser" id="dir-browser" hidden>
          <div class="dir-breadcrumb" id="dir-breadcrumb"></div>
          <div class="dir-entries" id="dir-entries"></div>
          <button type="button" class="dir-use" id="dir-use">Use this folder</button>
        </div>
      </div>
    </div>

    <div class="form-panel">
      <span class="field-label">Agents</span>
      <div class="agent-sliders">
        <div class="agent-slider-row" data-agent="claude">
          <span class="agent-slider-name"><img class="agent-slider-icon" src="__CLAUDE_ICON__" alt=""><span>Claude</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="1">
            <span class="agent-slider-val">1</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="codex">
          <span class="agent-slider-name"><img class="agent-slider-icon invert" src="__CODEX_ICON__" alt=""><span>Codex</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="1">
            <span class="agent-slider-val">1</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="gemini">
          <span class="agent-slider-name"><img class="agent-slider-icon" src="__GEMINI_ICON__" alt=""><span>Gemini</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="0">
            <span class="agent-slider-val">0</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="kimi">
          <span class="agent-slider-name"><img class="agent-slider-icon" src="__KIMI_ICON__" alt=""><span>Kimi</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="0">
            <span class="agent-slider-val">0</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="copilot">
          <span class="agent-slider-name"><img class="agent-slider-icon invert" src="__COPILOT_ICON__" alt=""><span>Copilot</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="0">
            <span class="agent-slider-val">0</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="cursor">
          <span class="agent-slider-name"><img class="agent-slider-icon" src="__CURSOR_ICON__" alt=""><span>Cursor</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="0">
            <span class="agent-slider-val">0</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="grok">
          <span class="agent-slider-name"><img class="agent-slider-icon" src="__GROK_ICON__" alt=""><span>Grok</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="0">
            <span class="agent-slider-val">0</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="opencode">
          <span class="agent-slider-name"><img class="agent-slider-icon" src="__OPENCODE_ICON__" alt=""><span>OpenCode</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="0">
            <span class="agent-slider-val">0</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="qwen">
          <span class="agent-slider-name"><img class="agent-slider-icon" src="__QWEN_ICON__" alt=""><span>Qwen</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="0">
            <span class="agent-slider-val">0</span>
          </div>
        </div>
        <div class="agent-slider-row" data-agent="aider">
          <span class="agent-slider-name"><img class="agent-slider-icon" src="__AIDER_ICON__" alt=""><span>Aider</span></span>
          <div class="agent-slider-wrap">
            <input type="range" class="agent-slider-input" min="0" max="__NEW_SESSION_MAX_PER_AGENT__" value="0">
            <span class="agent-slider-val">0</span>
          </div>
        </div>
      </div>
    </div>

    <button class="start-btn" id="start-btn">Start Session</button>
    <div id="error-msg" class="error-msg" hidden></div>
  </div>
  <script>
    const esc = s => String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    const workspaceInput = document.getElementById("workspace-path");
    const recentList = document.getElementById("recent-list");
    const browseToggle = document.getElementById("browse-toggle");
    const dirBrowser = document.getElementById("dir-browser");
    const dirBreadcrumb = document.getElementById("dir-breadcrumb");
    const dirEntries = document.getElementById("dir-entries");
    const dirUse = document.getElementById("dir-use");
    const startBtn = document.getElementById("start-btn");
    const errorMsg = document.getElementById("error-msg");
    let currentDirPath = "";
    const setBrowseToggle = (isOpen) => {
      const icon = isOpen
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="6" x2="18" y2="18"></line><line x1="18" y1="6" x2="6" y2="18"></line></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
      const label = isOpen ? "Close" : "Browse";
      browseToggle.dataset.open = isOpen ? "1" : "0";
      browseToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      browseToggle.innerHTML = `${icon}<span>${label}</span>`;
    };
    setBrowseToggle(false);

    const showError = msg => { errorMsg.textContent = msg; errorMsg.hidden = false; };

    // Recent workspaces
    fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" }).then(r => r.json()).then(data => {
      const all = [...(data.active_sessions || []), ...(data.archived_sessions || [])];
      const seen = new Set();
      const paths = all.map(s => s.workspace).filter(w => w && w !== "-" && !seen.has(w) && seen.add(w)).slice(0, 3);
      if (!paths.length) return;
      recentList.innerHTML = paths.map(p => {
        const name = p.split("/").filter(Boolean).pop() || p;
        return `<div class="recent-item" data-path="${esc(p)}"><div style="min-width:0"><div class="recent-name">${esc(name)}</div><div class="recent-path">${esc(p)}</div></div></div>`;
      }).join("");
      recentList.querySelectorAll(".recent-item").forEach(el => {
        el.addEventListener("click", () => {
          workspaceInput.value = el.dataset.path;
          recentList.querySelectorAll(".recent-item").forEach(x => x.classList.remove("selected"));
          el.classList.add("selected");
        });
      });
    }).catch(() => {});

    // Directory browser
    const renderDir = data => {
      currentDirPath = data.path;
      dirBreadcrumb.textContent = data.path;
      const rows = [];
      if (data.parent) rows.push({name: "..", path: data.parent, has_children: true, up: true});
      rows.push(...data.entries);
      const folderSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
      const upSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>';
      const chevronSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 6 15 12 9 18"/></svg>';
      dirEntries.innerHTML = rows.map(e =>
        `<div class="dir-entry" data-path="${esc(e.path)}">
          <span class="dir-icon">${e.up ? upSvg : folderSvg}</span>
          <span>${esc(e.name)}</span>
          ${e.has_children ? '<span class="chevron">' + chevronSvg + '</span>' : ""}
        </div>`
      ).join("");
      dirEntries.querySelectorAll(".dir-entry").forEach(el => {
        el.addEventListener("click", () => browsePath(el.dataset.path));
      });
    };
    const browsePath = path => {
      fetch(`/dirs?path=${encodeURIComponent(path || "")}`, { cache: "no-store" })
        .then(r => r.json()).then(renderDir).catch(() => {});
    };
    browseToggle.addEventListener("click", () => {
      if (dirBrowser.hidden) {
        dirBrowser.hidden = false;
        setBrowseToggle(true);
        browsePath(workspaceInput.value || "");
      } else {
        dirBrowser.hidden = true;
        setBrowseToggle(false);
      }
    });
    dirUse.addEventListener("click", () => {
      if (currentDirPath) {
        workspaceInput.value = currentDirPath;
        dirBrowser.hidden = true;
        setBrowseToggle(false);
      }
    });

    // Agent sliders
    document.querySelectorAll(".agent-slider-row").forEach(el => {
      const nameEl = el.querySelector(".agent-slider-name");
      const inputEl = el.querySelector(".agent-slider-input");
      const valEl = el.querySelector(".agent-slider-val");
      const setSliderFill = () => {
        const min = Number(inputEl.min || 0);
        const max = Number(inputEl.max || 100);
        const value = Number(inputEl.value || min);
        const ratio = max <= min ? 0 : (value - min) / (max - min);
        const pct = Math.max(0, Math.min(100, ratio * 100));
        inputEl.style.setProperty("--slider-fill-pct", `${pct}%`);
      };
      const update = () => {
        const n = parseInt(inputEl.value) || 0;
        valEl.textContent = n;
        valEl.classList.toggle("zero", n === 0);
        nameEl.classList.toggle("zero", n === 0);
        inputEl.classList.toggle("zero", n === 0);
        setSliderFill();
      };
      inputEl.addEventListener("input", update);
      update();
    });

    // Start session
    startBtn.addEventListener("click", async () => {
      const workspace = workspaceInput.value.trim();
      if (!workspace) { showError("Please enter a workspace path."); return; }
      const agents = [];
      document.querySelectorAll(".agent-slider-row").forEach(el => {
        const count = parseInt(el.querySelector(".agent-slider-input").value) || 0;
        for (let i = 0; i < count; i++) agents.push(el.dataset.agent);
      });
      if (!agents.length) { showError("Select at least one agent."); return; }
      startBtn.disabled = true;
      startBtn.textContent = "Starting\u2026";
      errorMsg.hidden = true;
      try {
        const res = await fetch("/start-session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspace, session_name: document.getElementById("session-name").value.trim(), agents })
        });
        const data = await res.json();
        if (data.ok && data.chat_url) {
          try { sessionStorage.removeItem("hub_chat_frame"); } catch (_) {}
          window.location.href = data.chat_url;
        } else {
          showError(data.error || "Failed to start session.");
          startBtn.disabled = false;
          startBtn.textContent = "Start Session";
        }
      } catch (err) {
        showError("Network error: " + err.message);
        startBtn.disabled = false;
        startBtn.textContent = "Start Session";
      }
    });

    // Restart hub
    const hubRestartForm = document.querySelector(".hub-restart-form");
    if (hubRestartForm) {
      hubRestartForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = e.currentTarget.querySelector("button");
        if (btn.classList.contains("restarting")) return;
        btn.classList.add("restarting");
        btn.disabled = true;
        btn.textContent = "Restarting\u2026";
        try { await fetch("/restart-hub", { method: "POST" }); } catch (_) {}
        const started = Date.now();
        const poll = async () => {
          try {
            const res = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
            if (res.ok) { window.location.replace(window.location.pathname); return; }
          } catch (_) {}
          if (Date.now() - started < 20000) { setTimeout(poll, 500); } else { window.location.reload(); }
        };
        setTimeout(poll, 700);
      });
    }

    // --- Starfield Animation ---
    const starCanvas = document.getElementById("starfield");
    const starCtx = starCanvas.getContext("2d");
    let stars = [];
    let shootingStars = [];
    const numStars = 360;
    let starAnimationId;
    let isStarAnimationRunning = false;

    function resizeStarCanvas() {
      starCanvas.width = window.innerWidth;
      starCanvas.height = window.innerHeight;
      initStars();
    }
    function initStars() {
      const diagonal = Math.sqrt(starCanvas.width ** 2 + starCanvas.height ** 2);
      stars = Array.from({ length: numStars }, () => ({
        angle: Math.random() * Math.PI * 2,
        radius: Math.random() * diagonal,
        speed: Math.random() * 0.0003 + 0.00015,
        size: Math.random() * 1.2 + 0.5,
      }));
    }
    function spawnShootingStar() {
      if (shootingStars.length === 0 && Math.random() < 0.01) {
        shootingStars.push({
          x: Math.random() * starCanvas.width * 0.5,
          y: Math.random() * starCanvas.height * 0.5,
          vx: 3 + Math.random() * 2,
          vy: 1 + Math.random() * 1.5,
          life: 80,
          initialLife: 80,
        });
      }
    }
    function animateStars() {
      if (!isStarAnimationRunning) return;
      const centerX = starCanvas.width;
      const centerY = starCanvas.height;
      starCtx.fillStyle = "rgb(10, 10, 10)";
      starCtx.fillRect(0, 0, starCanvas.width, starCanvas.height);
      stars.forEach((star, i) => {
        star.angle += star.speed;
        const x = centerX + star.radius * Math.cos(star.angle);
        const y = centerY + star.radius * Math.sin(star.angle);
        const flicker = 0.4 + Math.abs(Math.sin(Date.now() * 0.0015 + i)) * 0.5;
        starCtx.beginPath();
        starCtx.fillStyle = `rgba(255, 255, 255, ${flicker})`;
        starCtx.arc(x, y, star.size, 0, Math.PI * 2);
        starCtx.fill();
      });
      spawnShootingStar();
      for (let i = shootingStars.length - 1; i >= 0; i--) {
        const s = shootingStars[i];
        const opacity = s.life / s.initialLife;
        const grad = starCtx.createLinearGradient(s.x, s.y, s.x - s.vx * 35, s.y - s.vy * 35);
        grad.addColorStop(0, `rgba(255, 255, 255, ${opacity})`);
        grad.addColorStop(1, `rgba(255, 255, 255, 0)`);
        starCtx.strokeStyle = grad;
        starCtx.lineWidth = 2;
        starCtx.beginPath();
        starCtx.moveTo(s.x, s.y);
        starCtx.lineTo(s.x - s.vx * 18, s.y - s.vy * 18);
        starCtx.stroke();
        s.x += s.vx; s.y += s.vy; s.life -= 1;
        if (s.life <= 0) shootingStars.splice(i, 1);
      }
      starAnimationId = requestAnimationFrame(animateStars);
    }
    const updateStarAnimationState = () => {
      const shouldRun = document.documentElement.dataset.starfield !== "off";
      if (shouldRun && !isStarAnimationRunning) {
        isStarAnimationRunning = true;
        resizeStarCanvas();
        animateStars();
      } else if (!shouldRun && isStarAnimationRunning) {
        isStarAnimationRunning = false;
        cancelAnimationFrame(starAnimationId);
      }
    };
    window.addEventListener("resize", () => { if (isStarAnimationRunning) resizeStarCanvas(); });
    const themeObserver = new MutationObserver(updateStarAnimationState);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-starfield"] });
    updateStarAnimationState();
  __HUB_HEADER_JS__
  </script>
</body>
</html>
"""
HUB_NEW_SESSION_HTML = (
    HUB_NEW_SESSION_HTML
    .replace("__HUB_MANIFEST_URL__", _PWA_HUB_MANIFEST_URL)
    .replace("__PWA_ICON_192_URL__", _PWA_ICON_192_URL)
    .replace("__APPLE_TOUCH_ICON_URL__", _PWA_APPLE_TOUCH_ICON_URL)
    .replace("__HUB_HEADER_CSS__", _HUB_PAGE_HEADER_CSS)
    .replace("__HUB_HEADER_HTML__", _HUB_PAGE_HEADER_HTML)
    .replace("__HUB_HEADER_JS__", _HUB_PAGE_HEADER_JS)
    .replace("__NEW_SESSION_MAX_PER_AGENT__", str(NEW_SESSION_MAX_PER_AGENT))
    .replace("__CLAUDE_ICON__", _HUB_ICON_URIS["claude"])
    .replace("__CODEX_ICON__", _HUB_ICON_URIS["codex"])
    .replace("__GEMINI_ICON__", _HUB_ICON_URIS["gemini"])
    .replace("__KIMI_ICON__", _HUB_ICON_URIS["kimi"])
    .replace("__COPILOT_ICON__", _HUB_ICON_URIS["copilot"])
    .replace("__CURSOR_ICON__", _HUB_ICON_URIS["cursor"])
    .replace("__GROK_ICON__", _HUB_ICON_URIS["grok"])
    .replace("__OPENCODE_ICON__", _HUB_ICON_URIS["opencode"])
    .replace("__QWEN_ICON__", _HUB_ICON_URIS["qwen"])
    .replace("__AIDER_ICON__", _HUB_ICON_URIS["aider"])
)

def hub_crons_html(*, jobs, session_records, notice="", prefill_session="", prefill_agent="", edit_job=None):
    settings = load_hub_settings()
    session_map = {}
    for record in session_records or []:
        if not isinstance(record, dict):
            continue
        name = str(record.get("name") or "").strip()
        if not name or name in session_map:
            continue
        session_map[name] = {
            "name": name,
            "agents": [str(agent).strip() for agent in (record.get("agents") or []) if str(agent).strip()],
            "status": str(record.get("status") or "").strip(),
        }

    selected_session = str((edit_job or {}).get("session") or prefill_session or "").strip()
    selected_agent = str((edit_job or {}).get("agent") or prefill_agent or "").strip()
    if selected_session and selected_session not in session_map:
        session_map[selected_session] = {
            "name": selected_session,
            "agents": [selected_agent] if selected_agent else [],
            "status": "unknown",
        }
    if selected_session and selected_agent and selected_agent not in session_map.get(selected_session, {}).get("agents", []):
        session_map[selected_session]["agents"] = [*session_map[selected_session].get("agents", []), selected_agent]

    all_agents = []
    seen_agents = set()
    for agent in ALL_AGENT_NAMES:
        if agent not in seen_agents:
            seen_agents.add(agent)
            all_agents.append(agent)
    for record in session_map.values():
        for agent in record.get("agents", []):
            if agent not in seen_agents:
                seen_agents.add(agent)
                all_agents.append(agent)
    if selected_agent and selected_agent not in seen_agents:
        seen_agents.add(selected_agent)
        all_agents.append(selected_agent)

    def _session_option(name: str, label: str, is_selected: bool) -> str:
        selected_attr = ' selected' if is_selected else ''
        return f'<option value="{html.escape(name)}"{selected_attr}>{html.escape(label)}</option>'

    session_options = ['<option value="">Select session</option>']
    for name in sorted(session_map.keys(), key=lambda item: item.lower()):
        record = session_map[name]
        status = str(record.get("status") or "").strip()
        label = name if not status else f"{name} ({status})"
        session_options.append(_session_option(name, label, name == selected_session))
    session_options_html = "".join(session_options)

    initial_agent_options = ['<option value="">Select agent</option>']
    for agent in (session_map.get(selected_session, {}).get("agents") or all_agents):
        selected_attr = ' selected' if agent == selected_agent else ''
        initial_agent_options.append(f'<option value="{html.escape(agent)}"{selected_attr}>{html.escape(agent)}</option>')
    initial_agent_values = {
        str(agent).strip()
        for agent in (session_map.get(selected_session, {}).get("agents") or all_agents)
        if str(agent).strip()
    }
    if selected_agent and selected_agent not in initial_agent_values:
        initial_agent_options.append(
            f'<option value="{html.escape(selected_agent)}" selected>{html.escape(selected_agent)}</option>'
        )
    agent_options_html = "".join(initial_agent_options)

    notice_html = (
        f'<div class="notice">{html.escape(str(notice or "").strip())}</div>'
        if str(notice or "").strip()
        else ""
    )

    jobs_html = []
    for job in jobs or []:
        job_id = str(job.get("id") or "").strip()
        name = html.escape(str(job.get("name") or "").strip() or "Untitled cron")
        session_name = str(job.get("session") or "").strip()
        agent = str(job.get("agent") or "").strip()
        schedule = html.escape(str(job.get("schedule_label") or "").strip() or "Daily")
        next_run = html.escape(str(job.get("next_run_at") or "").strip() or "—")
        last_run = html.escape(str(job.get("last_run_at") or "").strip() or "—")
        last_status = html.escape(str(job.get("last_status") or "").strip() or "idle")
        last_detail = html.escape(str(job.get("last_status_detail") or "").strip() or "")
        enabled = bool(job.get("enabled"))
        checked_attr = " checked" if enabled else ""
        open_href = f"/open-session?session={url_quote(session_name)}" if session_name else "/"
        edit_href = f"/crons?edit={url_quote(job_id)}"
        prompt_source = str(job.get("prompt") or "").strip()
        prompt_preview_raw = next((line.strip() for line in prompt_source.splitlines() if line.strip()), "")
        if not prompt_preview_raw:
            prompt_preview_raw = "No prompt"
        if len(prompt_preview_raw) > 180:
            prompt_preview_raw = f"{prompt_preview_raw[:179].rstrip()}…"
        prompt_preview = html.escape(prompt_preview_raw)
        jobs_html.append(
            f'''
            <div class="swipe-row" data-job-id="{html.escape(job_id)}">
              <div class="swipe-act swipe-act-right" data-action="delete">
                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                <span>Delete</span>
              </div>
              <div class="mob-session-row cron-job-row" tabindex="0">
                <div class="mob-row-head">
                  <button class="mob-row-expand-btn" data-expand-row="1" type="button" aria-label="Toggle cron details">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                  </button>
                  <div class="mob-row-name">{name}</div>
                  <div class="mob-row-tools">
                    <form class="cron-enable-form" method="post" action="/crons/toggle" data-stop-row="1">
                      <input type="hidden" name="id" value="{html.escape(job_id)}">
                      <input type="hidden" name="enabled" value="{'1' if enabled else '0'}">
                      <label class="cron-switch" data-stop-row="1" title="Enable or disable this cron">
                        <input class="cron-switch-input" type="checkbox"{checked_attr} data-stop-row="1" aria-label="Enable or disable this cron">
                        <span class="cron-switch-ui" aria-hidden="true"></span>
                      </label>
                    </form>
                  </div>
                </div>
                <div class="mob-row-preview">{schedule} · {html.escape(session_name or "—")} · {html.escape(agent or "—")}</div>
                <div class="mob-row-detail">
                  <div class="cron-detail-copy">{prompt_preview}</div>
                  <div class="mob-row-meta">
                    <span><strong>Next</strong> {next_run}</span>
                    <span><strong>Last</strong> {last_run}</span>
                    <span><strong>Status</strong> {last_status}</span>
                  </div>
                  {f'<div class="cron-detail-note">{last_detail}</div>' if last_detail else ''}
                  <div class="cron-detail-actions" data-stop-row="1">
                    <a class="card-link" href="{edit_href}" data-stop-row="1">Edit</a>
                    <a class="card-link" href="{open_href}" data-stop-row="1">Open</a>
                    <form method="post" action="/crons/run" data-stop-row="1">
                      <input type="hidden" name="id" value="{html.escape(job_id)}">
                      <button class="card-link" type="submit">Run now</button>
                    </form>
                  </div>
                </div>
              </div>
              <form class="cron-delete-form" method="post" action="/crons/delete" onsubmit="return window.confirm('Delete this cron?');">
                <input type="hidden" name="id" value="{html.escape(job_id)}">
              </form>
            </div>
            '''
        )
    jobs_html_str = "".join(jobs_html) or '<div class="mob-empty">No cron jobs yet.</div>'

    current_name = html.escape(str((edit_job or {}).get("name") or "").strip())
    current_time = html.escape(str((edit_job or {}).get("time") or "").strip())
    current_prompt = html.escape(str((edit_job or {}).get("prompt") or "").strip())
    current_enabled = bool((edit_job or {}).get("enabled", True))
    current_id = html.escape(str((edit_job or {}).get("id") or "").strip())
    form_enabled_value = "1" if current_enabled else "0"
    form_row_html = (
        "Edit Cron"
        if edit_job
        else '<span class="cron-compose-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg><span>New Cron</span></span>'
    )
    form_expanded = " expanded" if (edit_job or not jobs or prefill_session or prefill_agent) else ""
    total_jobs = len(jobs or [])
    enabled_jobs = sum(1 for job in (jobs or []) if bool(job.get("enabled")))
    paused_jobs = max(0, total_jobs - enabled_jobs)
    sessions_json = json.dumps(list(session_map.values()), ensure_ascii=False).replace("</", "<\\/")
    all_agents_json = json.dumps(all_agents, ensure_ascii=False).replace("</", "<\\/")
    preferred_agent_json = json.dumps(selected_agent or "", ensure_ascii=False).replace("</", "<\\/")

    page = """<!doctype html>
<html lang="en" data-theme="__CHAT_THEME__"__STARFIELD_ATTR__>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="rgb(10, 10, 10)">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Session Hub">
  <link rel="manifest" href="__HUB_MANIFEST_URL__">
  <link rel="icon" type="image/png" sizes="192x192" href="__PWA_ICON_192_URL__">
  <link rel="apple-touch-icon" href="__APPLE_TOUCH_ICON_URL__">
  <script>
    (() => {
      if (!("serviceWorker" in navigator)) return;
      const isLocalHost = location.hostname === "localhost" || location.hostname === "127.0.0.1" || location.hostname === "[::1]";
      if (!(window.isSecureContext || isLocalHost)) return;
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/hub-service-worker.js", { scope: "/" }).catch((err) => {
          console.warn("hub service worker registration failed", err);
        });
      }, { once: true });
    })();
  </script>
  <title>Cron · Hub</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: rgb(10, 10, 10);
      --bg-rgb: 10, 10, 10;
      --panel: rgb(20, 20, 20);
      --panel-2: rgb(15, 15, 15);
      --line: rgba(255,255,255,0.06);
      --line-strong: rgba(255,255,255,0.10);
      --fg: rgb(252, 252, 252);
      --muted: rgb(158, 158, 158);
      --accent: rgb(44, 132, 219);
      --bad: rgb(214, 124, 124);
    }
    html[data-theme="soft-light"] {
      color-scheme: light;
      --bg: rgb(244, 244, 242);
      --bg-rgb: 244, 244, 242;
      --panel: rgb(255, 255, 255);
      --panel-2: rgb(248, 248, 246);
      --line: rgba(15, 20, 30, 0.12);
      --line-strong: rgba(15, 20, 30, 0.2);
      --fg: rgb(26, 30, 36);
      --muted: rgb(98, 106, 120);
      --accent: rgb(44, 132, 219);
      --bad: rgb(180, 84, 84);
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; background: var(--bg); color: var(--fg); font-family: "SF Pro Text", "Segoe UI", sans-serif; }
    body { padding: 0; }
    .shell { max-width: 900px; margin: 0 auto; width: 100%; }
    .mob-stats-bar {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0;
      padding: 10px 14px 11px;
      border-bottom: 0.5px solid var(--line);
      max-width: 900px;
      width: 100%;
      margin: 0 auto;
      box-sizing: border-box;
      background: color-mix(in srgb, var(--bg) 84%, transparent);
      position: relative;
      z-index: 2;
    }
    .mob-stat {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 2px;
      min-width: 0;
    }
    .mob-stat + .mob-stat {
      padding-left: 14px;
      border-left: 0.5px solid var(--line);
    }
    .mob-stat-label {
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      white-space: nowrap;
    }
    .mob-stat-val {
      font-size: 16px;
      font-weight: 650;
      color: var(--fg);
      letter-spacing: -0.03em;
      line-height: 1.1;
    }
    .mob-list-wrap {
      display: block;
      max-width: 900px;
      margin: 0 auto;
      width: 100%;
      padding-bottom: max(40px, env(safe-area-inset-bottom));
    }
    .mob-section-label {
      padding: 14px 14px 5px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .notice {
      margin: 0 14px 10px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 0.5px solid rgba(44,132,219,0.24);
      background: rgba(44,132,219,0.08);
      color: var(--fg);
      font-size: 13px;
      line-height: 1.55;
    }
    .swipe-row { position: relative; overflow: hidden; border-bottom: 1px solid var(--line); }
    .swipe-act {
      position: absolute; top: 0; bottom: 0;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      min-width: 88px; padding: 0 18px; gap: 5px;
      font-size: 12px; font-weight: 600; color: #fff;
      user-select: none; -webkit-user-select: none; cursor: pointer;
      overflow: hidden;
    }
    .swipe-act svg { display: block; }
    .swipe-act-right { right: 0; background: rgb(255, 59, 48); }
    .mob-session-row {
      display: block;
      padding: 14px;
      text-decoration: none;
      color: inherit;
      -webkit-tap-highlight-color: transparent;
      transition: background 80ms ease, transform 160ms ease;
      position: relative;
      z-index: 1;
      will-change: transform;
      background: var(--bg) !important;
      opacity: 1 !important;
      touch-action: pan-y;
    }
    html[data-theme="black-hole"] .mob-session-row { background: rgb(10, 10, 10) !important; }
    html[data-theme="soft-light"] .mob-session-row { background: rgb(244, 244, 242) !important; }
    .mob-session-row:hover { background: var(--panel-2) !important; }
    .mob-row-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 5px;
    }
    .mob-row-name {
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
      min-width: 0;
      word-break: break-word;
      flex: 1;
    }
    .mob-row-preview {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
    }
    .mob-row-tools { flex: 0 0 auto; display: flex; align-items: center; gap: 8px; }
    .mob-badge {
      font-size: 10px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 2px 7px;
      border-radius: 999px;
      border: 0.5px solid var(--line-strong);
      color: var(--muted);
    }
    .cron-compose-row .mob-row-head {
      margin-bottom: 0;
    }
    .cron-compose-row .mob-row-name {
      font-size: 15px;
      font-weight: 400;
      letter-spacing: 0;
      color: var(--fg);
    }
    .cron-compose-title {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: inherit;
    }
    .cron-compose-title svg {
      width: 14px;
      height: 14px;
      flex: 0 0 auto;
      opacity: 0.72;
    }
    .mob-row-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 3px 10px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.4;
      margin-top: 8px;
    }
    .mob-row-meta strong { color: var(--fg); font-weight: 500; }
    .mob-row-detail {
      display: none;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 0.5px solid var(--line);
      min-width: 0;
    }
    .mob-session-row.expanded .mob-row-detail { display: block; }
    /* New Cron / compose card: smooth open (grid rows + fade + slide) */
    .shell .mob-session-row.cron-compose-row:not(.expanded) .mob-row-detail {
      display: grid;
      grid-template-rows: 0fr;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 0.5px solid transparent;
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      transition:
        grid-template-rows 0.42s cubic-bezier(0.32, 0.72, 0, 1),
        opacity 0.3s ease,
        border-color 0.28s ease,
        visibility 0s linear 0.42s;
    }
    .shell .mob-session-row.cron-compose-row.expanded .mob-row-detail {
      display: grid;
      grid-template-rows: 1fr;
      border-top-color: var(--line);
      opacity: 1;
      visibility: visible;
      pointer-events: auto;
      transition:
        grid-template-rows 0.42s cubic-bezier(0.32, 0.72, 0, 1),
        opacity 0.32s ease 0.04s,
        border-color 0.28s ease,
        visibility 0s linear 0s;
    }
    .shell .mob-session-row.cron-compose-row .mob-row-detail > .cron-compose-form {
      min-height: 0;
      overflow: hidden;
      transform: translateY(-10px);
      transition: transform 0.42s cubic-bezier(0.32, 0.72, 0, 1);
    }
    .shell .mob-session-row.cron-compose-row.expanded .mob-row-detail > .cron-compose-form {
      transform: translateY(0);
    }
    @media (prefers-reduced-motion: reduce) {
      .shell .mob-session-row.cron-compose-row:not(.expanded) .mob-row-detail,
      .shell .mob-session-row.cron-compose-row.expanded .mob-row-detail,
      .shell .mob-session-row.cron-compose-row .mob-row-detail > .cron-compose-form {
        transition: none !important;
      }
      .shell .mob-session-row.cron-compose-row:not(.expanded) .mob-row-detail {
        transition: visibility 0s linear 0s !important;
      }
    }
    .mob-row-expand-btn {
      background: none; border: none; padding: 4px; cursor: pointer; color: var(--muted);
      transition: transform 180ms ease, color 120ms ease; flex-shrink: 0; display: flex; align-items: center;
    }
    .mob-row-expand-btn:hover { color: var(--fg); }
    .mob-session-row.expanded .mob-row-expand-btn { transform: rotate(90deg); }
    .cron-compose-row .mob-row-preview { white-space: normal; }
    .cron-compose-form { margin: 0; }
    .cron-field-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .cron-field-grid .field-wide { grid-column: 1 / -1; }
    .cron-field-grid label { display: block; }
    .field-label {
      display: block;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--fg);
      opacity: 0.9;
      margin-bottom: 10px;
    }
    input[type="text"], input[type="time"], select, textarea {
      width: 100%;
      border: 0.5px solid var(--line-strong);
      background: var(--panel-2);
      color: var(--fg);
      border-radius: 12px;
      padding: 11px 13px;
      font-size: 16px;
      line-height: 1.25;
      outline: none;
      font-family: inherit;
      appearance: none;
      -webkit-appearance: none;
    }
    textarea { min-height: 180px; resize: vertical; }
    input:focus, select:focus, textarea:focus { border-color: rgba(255,255,255,0.22); }
    .cron-compose-save-wrap {
      margin-top: 14px;
      display: flex;
      justify-content: center;
    }
    .cron-compose-save-wrap .start-btn {
      margin: 0;
      width: calc(100% - 28px);
      max-width: 100%;
      padding: 14px;
      background: rgba(255,255,255,0.05);
      border: 0.5px solid var(--line-strong);
      border-radius: 14px;
      color: rgba(252,252,252,0.96);
      font-size: 16px;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      letter-spacing: -0.01em;
      transition: all 200ms ease;
    }
    .cron-compose-save-wrap .start-btn:hover:not(:disabled) {
      background: rgba(255,255,255,0.08);
      border-color: rgba(255,255,255,0.25);
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .cron-compose-save-wrap .start-btn:active:not(:disabled) { transform: translateY(0); }
    .cron-compose-save-wrap .start-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    html[data-theme="soft-light"] .cron-compose-save-wrap .start-btn {
      background: rgba(15,20,30,0.03);
      border-color: var(--line);
      color: var(--fg);
    }
    html[data-theme="soft-light"] .cron-compose-save-wrap .start-btn:hover:not(:disabled) {
      background: rgba(15,20,30,0.06);
      border-color: var(--line-strong);
    }
    .cron-detail-copy,
    .cron-detail-note {
      font-size: 13px;
      line-height: 1.55;
      color: var(--fg);
      opacity: 0.82;
    }
    .cron-detail-note { margin-top: 8px; opacity: 0.72; }
    .cron-detail-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
      align-items: center;
    }
    .cron-detail-actions form { margin: 0; }
    .card-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: auto;
      padding: 7px 10px;
      border-radius: 10px;
      border: 0.5px solid var(--line-strong);
      background: transparent;
      color: var(--fg);
      text-decoration: none;
      font: inherit;
      font-size: 11px;
      line-height: 1;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      cursor: pointer;
      transition: color 140ms ease, border-color 140ms ease, background 140ms ease;
      appearance: none;
      -webkit-appearance: none;
    }
    .card-link.primary {
      color: var(--accent);
      border-color: rgba(44,132,219,0.35);
      background: rgba(44,132,219,0.06);
    }
    .card-link.danger {
      color: var(--bad);
      border-color: rgba(214,124,124,0.28);
    }
    .cron-enable-form { margin: 0; }
    .cron-switch {
      display: inline-flex;
      align-items: center;
      cursor: pointer;
    }
    .cron-switch-input {
      position: absolute;
      width: 1px;
      height: 1px;
      margin: -1px;
      padding: 0;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      border: 0;
    }
    .cron-switch-ui {
      width: 44px;
      height: 26px;
      border-radius: 999px;
      background: var(--line-strong);
      position: relative;
      transition: background 200ms ease;
    }
    .cron-switch-ui::before {
      content: "";
      position: absolute;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: #fff;
      top: 2px;
      left: 2px;
      transition: transform 200ms ease;
    }
    .cron-switch-input:checked + .cron-switch-ui {
      background: var(--accent);
    }
    .cron-switch-input:checked + .cron-switch-ui::before {
      transform: translateX(18px);
    }
    .mob-empty {
      padding: 22px 14px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
      border-bottom: 0.5px solid var(--line);
    }
    html[data-theme="black-hole"] input[type="text"],
    html[data-theme="black-hole"] input[type="time"],
    html[data-theme="black-hole"] select,
    html[data-theme="black-hole"] textarea {
      background: linear-gradient(145deg, rgb(20, 20, 20) 0%, rgb(10, 10, 10) 100%) !important;
      backdrop-filter: blur(20px) saturate(160%) !important;
      -webkit-backdrop-filter: blur(20px) saturate(160%) !important;
      border: 0.5px solid rgba(255, 255, 255, 0.1) !important;
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8) !important;
    }
    html[data-theme="soft-light"] input[type="text"],
    html[data-theme="soft-light"] input[type="time"],
    html[data-theme="soft-light"] select,
    html[data-theme="soft-light"] textarea {
      background: linear-gradient(145deg, rgb(255, 255, 255) 0%, rgb(246, 246, 244) 100%) !important;
      border: 0.5px solid rgba(15, 20, 30, 0.14) !important;
      box-shadow: 0 8px 24px rgba(15, 20, 30, 0.08) !important;
      backdrop-filter: none !important;
      -webkit-backdrop-filter: none !important;
      color: var(--fg) !important;
    }
    #starfield {
      position: fixed;
      top: 0;
      left: 0;
      z-index: 1;
      width: 100%;
      height: 100%;
      display: none;
      pointer-events: none;
    }
    :not([data-starfield="off"]) #starfield { display: block; }
    html[data-theme="soft-light"] #starfield { display: none !important; }
    :not([data-starfield="off"]) body { background: transparent !important; }
    :not([data-starfield="off"]) html { background: var(--bg) !important; }
    :not([data-starfield="off"]) .shell { background: transparent !important; position: relative; z-index: 2; }
    @media (max-width: 900px) {
      .cron-field-grid { grid-template-columns: 1fr; }
    }
  __HUB_HEADER_CSS__
  </style>
</head>
<body>
  <canvas id="starfield"></canvas>
  <div class="shell">
    __HUB_HEADER_HTML__
    <div class="mob-stats-bar">
      <div class="mob-stat"><span class="mob-stat-label">Total</span><span class="mob-stat-val">__CRON_TOTAL__</span></div>
      <div class="mob-stat"><span class="mob-stat-label">Enabled</span><span class="mob-stat-val">__CRON_ENABLED__</span></div>
      <div class="mob-stat"><span class="mob-stat-label">Paused</span><span class="mob-stat-val">__CRON_PAUSED__</span></div>
    </div>
    <div class="mob-list-wrap">
      __NOTICE_HTML__
      <div class="swipe-row">
        <div class="mob-session-row cron-compose-row__FORM_EXPANDED__" id="cronComposeCard">
          <div class="mob-row-head">
            <div class="mob-row-name">__FORM_ROW_HTML__</div>
          </div>
          <div class="mob-row-detail">
            <form class="cron-compose-form" method="post" action="/crons/save">
              <input type="hidden" name="id" value="__FORM_ID__">
              <input type="hidden" name="enabled" value="__FORM_ENABLED_VALUE__">
              <div class="cron-field-grid">
                <label>
                  <span class="field-label">Name</span>
                  <input type="text" name="name" value="__FORM_NAME__" placeholder="Daily review">
                </label>
                <label>
                  <span class="field-label">Daily Time</span>
                  <input type="time" name="time" value="__FORM_TIME__" required>
                </label>
                <label>
                  <span class="field-label">Session</span>
                  <select name="session" id="cronSessionSelect" required>__SESSION_OPTIONS__</select>
                </label>
                <label>
                  <span class="field-label">Agent</span>
                  <select name="agent" id="cronAgentSelect" required>__AGENT_OPTIONS__</select>
                </label>
                <label class="field-wide">
                  <span class="field-label">Prompt</span>
                  <textarea name="prompt" required placeholder="Write the daily task that should be sent to the target agent.">__FORM_PROMPT__</textarea>
                </label>
              </div>
              <div class="cron-compose-save-wrap">
                <button type="submit" class="start-btn">Save</button>
              </div>
            </form>
          </div>
        </div>
      </div>
      <div class="mob-section-label">Jobs</div>
      <div class="cron-jobs-list">__CRON_ROWS__</div>
    </div>
  </div>
  <script>
    const sessionRecords = __CRON_SESSIONS_JSON__;
    const allAgents = __CRON_ALL_AGENTS_JSON__;
    const sessionSelect = document.getElementById("cronSessionSelect");
    const agentSelect = document.getElementById("cronAgentSelect");
    const preferredAgent = __PREFERRED_AGENT__;
    const composeCard = document.getElementById("cronComposeCard");
    const syncAgentOptions = () => {
      const selectedSession = sessionSelect ? sessionSelect.value : "";
      const record = sessionRecords.find((item) => item && item.name === selectedSession) || null;
      const candidates = (record && Array.isArray(record.agents) && record.agents.length)
        ? record.agents
        : allAgents;
      const previous = agentSelect ? agentSelect.value : "";
      if (!agentSelect) return;
      const selected = candidates.includes(previous) ? previous : (candidates.includes(preferredAgent) ? preferredAgent : (candidates[0] || ""));
      agentSelect.innerHTML = '<option value="">Select agent</option>' + candidates.map((agent) => {
        const value = String(agent || "");
        const isSelected = value === selected ? ' selected' : '';
        return `<option value="${value.replace(/"/g, '&quot;')}"${isSelected}>${value.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</option>`;
      }).join("");
      if (!candidates.length) agentSelect.innerHTML = '<option value="">Select agent</option>';
    };
    composeCard?.addEventListener("click", (event) => {
      if (event.target.closest('input, textarea, select, label, button, a, form')) return;
      composeCard.classList.toggle("expanded");
    });
    sessionSelect?.addEventListener("change", () => {
      syncAgentOptions();
    });
    syncAgentOptions();

    document.querySelectorAll('.mob-row-expand-btn[data-expand-row="1"]').forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        btn.closest('.mob-session-row')?.classList.toggle('expanded');
      });
    });

    document.querySelectorAll('[data-stop-row="1"], .cron-detail-actions a, .cron-detail-actions button, .cron-detail-actions form, .cron-compose-form button, .cron-compose-form input, .cron-compose-form select, .cron-compose-form textarea, .cron-compose-form label').forEach((node) => {
      node.addEventListener('click', (event) => event.stopPropagation());
    });

    document.querySelectorAll('.cron-enable-form').forEach((form) => {
      const checkbox = form.querySelector('.cron-switch-input');
      const hidden = form.querySelector('input[name="enabled"]');
      if (!checkbox || !hidden) return;
      checkbox.addEventListener('change', () => {
        hidden.value = checkbox.checked ? '1' : '0';
        form.submit();
      });
    });

    (() => {
      let anyOpen = null;
      const closeRow = (row, animate = false) => {
        const inner = row && row.querySelector('.mob-session-row');
        const actR = row && row.querySelector('.swipe-act-right');
        if (!row || !inner) return;
        if (animate) inner.style.transition = 'transform 160ms ease';
        inner.style.transform = 'translateX(0px)';
        if (actR) actR.style.width = '0px';
        row._snap = 0;
        if (animate) setTimeout(() => { inner.style.transition = ''; }, 180);
      };
      const initSwipeRow = (row) => {
        const inner = row.querySelector('.mob-session-row');
        const actR = row.querySelector('.swipe-act-right');
        const deleteForm = row.querySelector('.cron-delete-form');
        if (!inner || !actR || !deleteForm) return;
        let startX = 0;
        let startY = 0;
        let dragging = false;
        let didSwipe = false;
        let pointerId = null;
        const maxX = () => Math.max(88, actR.offsetWidth || 88);
        const setX = (x) => {
          row._snap = x;
          inner.style.transform = `translateX(${x}px)`;
          actR.style.width = `${Math.max(0, -x)}px`;
        };
        const finish = () => {
          if (!dragging) return;
          dragging = false;
          const snap = row._snap || 0;
          if (snap < -maxX() * 0.55) {
            setX(-maxX());
            anyOpen = row;
          } else {
            closeRow(row, true);
            if (anyOpen === row) anyOpen = null;
          }
        };
        inner.addEventListener('pointerdown', (event) => {
          if (event.pointerType === 'mouse' && event.button !== 0) return;
          if (event.target.closest('[data-stop-row="1"], a, button, input, textarea, select, label, form')) return;
          if (anyOpen && anyOpen !== row) {
            closeRow(anyOpen, true);
            anyOpen = null;
          }
          dragging = true;
          didSwipe = false;
          startX = event.clientX;
          startY = event.clientY;
          pointerId = event.pointerId;
          row._baseX = row._snap || 0;
          inner.setPointerCapture?.(pointerId);
        });
        inner.addEventListener('pointermove', (event) => {
          if (!dragging) return;
          const dx = event.clientX - startX;
          const dy = event.clientY - startY;
          if (Math.abs(dy) > 8 && Math.abs(dy) > Math.abs(dx) + 4) {
            dragging = false;
            return;
          }
          if (Math.abs(dx) < 4) return;
          didSwipe = true;
          const next = Math.min(0, Math.max(-maxX(), (row._baseX || 0) + dx));
          setX(next);
          event.preventDefault();
        });
        inner.addEventListener('pointerup', finish);
        inner.addEventListener('pointercancel', finish);
        inner.addEventListener('pointerleave', finish);
        actR.addEventListener('click', (event) => {
          event.stopPropagation();
          if (deleteForm.requestSubmit) deleteForm.requestSubmit();
          else deleteForm.submit();
        });
        inner.addEventListener('click', (event) => {
          if (didSwipe) {
            didSwipe = false;
            event.stopPropagation();
            return;
          }
          if ((row._snap || 0) !== 0) {
            closeRow(row, true);
            anyOpen = null;
            event.stopPropagation();
          }
        });
      };
      document.querySelectorAll('.swipe-row[data-job-id]').forEach(initSwipeRow);
    })();
  __HUB_HEADER_JS__
  </script>
</body>
</html>
"""
    return (
        page
        .replace("__CHAT_THEME__", settings.get("theme", "black-hole"))
        .replace("__STARFIELD_ATTR__", "" if settings.get("starfield", False) else ' data-starfield="off"')
        .replace("__HUB_MANIFEST_URL__", _PWA_HUB_MANIFEST_URL)
        .replace("__PWA_ICON_192_URL__", _PWA_ICON_192_URL)
        .replace("__APPLE_TOUCH_ICON_URL__", _PWA_APPLE_TOUCH_ICON_URL)
        .replace("__HUB_HEADER_CSS__", _HUB_PAGE_HEADER_CSS)
        .replace("__HUB_HEADER_HTML__", _HUB_PAGE_HEADER_HTML)
        .replace("__HUB_HEADER_JS__", _HUB_PAGE_HEADER_JS)
        .replace("__NOTICE_HTML__", notice_html)
        .replace("__FORM_ID__", current_id)
        .replace("__FORM_NAME__", current_name)
        .replace("__FORM_TIME__", current_time)
        .replace("__FORM_PROMPT__", current_prompt)
        .replace("__FORM_ENABLED_VALUE__", form_enabled_value)
        .replace("__FORM_ROW_HTML__", form_row_html)
        .replace("__FORM_EXPANDED__", form_expanded)
        .replace("__SESSION_OPTIONS__", session_options_html)
        .replace("__AGENT_OPTIONS__", agent_options_html)
        .replace("__CRON_ROWS__", jobs_html_str)
        .replace("__CRON_TOTAL__", str(total_jobs))
        .replace("__CRON_ENABLED__", str(enabled_jobs))
        .replace("__CRON_PAUSED__", str(paused_jobs))
        .replace("__CRON_SESSIONS_JSON__", sessions_json)
        .replace("__CRON_ALL_AGENTS_JSON__", all_agents_json)
        .replace("__PREFERRED_AGENT__", preferred_agent_json)
    )


def _cron_records_query():
    query = active_session_records_query()
    records_by_name = {name: record for name, record in query.records.items()}
    if query.state != "unhealthy":
        for name, record in archived_session_records(query.records.keys()).items():
            records_by_name.setdefault(name, record)
    records = [records_by_name[name] for name in sorted(records_by_name.keys(), key=lambda item: item.lower())]
    return query, records


def _cron_redirect_location(*, notice="", session_name="", agent="", edit_id="") -> str:
    params = []
    text = str(notice or "").strip()
    if text:
        params.append(("notice", text))
    session_value = str(session_name or "").strip()
    if session_value:
        params.append(("session", session_value))
    agent_value = str(agent or "").strip()
    if agent_value:
        params.append(("agent", agent_value))
    edit_value = str(edit_id or "").strip()
    if edit_value:
        params.append(("edit", edit_value))
    if not params:
        return "/crons"
    query = "&".join(f"{url_quote(key)}={url_quote(value)}" for key, value in params)
    return f"/crons?{query}"

def error_page(message):
    text = html.escape(message)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Session Hub</title><style>:root{{color-scheme:dark}}body{{margin:0;background:rgb(38,38,36);color:rgb(240,239,235);font-family:'SF Pro Text','Segoe UI',sans-serif;padding:24px}}.panel{{max-width:680px;margin:0 auto;background:rgb(25,25,24);border:0.5px solid rgba(255,255,255,0.09);border-radius:16px;padding:18px 18px 16px}}a{{color:rgb(240,239,235)}}</style></head><body><div class="panel"><h1 style="margin:0 0 10px;font-size:24px">Session Hub</h1><p style="margin:0 0 14px;color:rgb(156,154,147);line-height:1.6">{text}</p><p style="margin:0"><a href=\"/\">Back</a></p></div></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Permissions-Policy", "camera=(self), microphone=(self)")
        super().end_headers()

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, page):
        if "__CHAT_THEME__" in page:
            settings = load_hub_settings()
            page = page.replace("__CHAT_THEME__", settings.get("theme", "claude"))
            sf_attr = "" if settings.get("starfield", False) else ' data-starfield="off"'
            page = page.replace("__STARFIELD_ATTR__", sf_attr)
        body = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_unhealthy(self, fmt, detail):
        msg = f"tmux is currently unresponsive ({detail}). Please wait a few seconds."
        if fmt == "json":
            self._send_json(503, {"ok": False, "error": "tmux_unhealthy", "detail": msg})
        else:
            self._send_html(503, error_page(msg))

    def _read_form(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        return {key: values[-1] for key, values in parse_qs(raw).items() if values}

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _render_crons(self, *, notice="", prefill_session="", prefill_agent="", edit_job=None, status=200):
        query, session_records = _cron_records_query()
        message = str(notice or "").strip()
        if query.state == "unhealthy":
            unhealthy_note = f"tmux is currently unresponsive ({query.detail}). Session list may be incomplete."
            message = f"{message} {unhealthy_note}".strip() if message else unhealthy_note
        page = hub_crons_html(
            jobs=list_cron_jobs(repo_root),
            session_records=session_records,
            notice=message,
            prefill_session=prefill_session,
            prefill_agent=prefill_agent,
            edit_job=edit_job,
        )
        self._send_html(status, page)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/session/"):
            self._proxy_session_request("GET", parsed)
            return
        if _serve_pwa_static(self, parsed.path):
            return
        if parsed.path == "/hub.webmanifest":
            body = json.dumps({
                "name": "Session Hub",
                "short_name": "Hub",
                "display": "standalone",
                "background_color": "rgb(38, 38, 36)",
                "theme_color": "rgb(38, 38, 36)",
                "start_url": "/",
                "scope": "/",
                "icons": _pwa_icon_entries(),
                "shortcuts": _pwa_shortcut_entries(),
            }, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/sessions":
            query = active_session_records_query()
            active_map = query.records
            active = list(active_map.values())
            if query.state == "unhealthy":
                # Suppress archived to avoid duplicates from partial scan
                archived = []
            else:
                archived = list(archived_session_records(active_map.keys()).values())
            stats = compute_hub_stats(active, archived)
            self._send_json(200, {
                "sessions": active,
                "active_sessions": active,
                "archived_sessions": archived,
                "stats": stats,
                "tmux_state": query.state,
                "tmux_detail": query.detail,
            })
            return
        if parsed.path == "/notify-sound":
            qs = parse_qs(parsed.query)
            name = (qs.get("name", [""])[0] or "").strip()
            if not name:
                name = "mictest.ogg"
            sounds_dir = repo_root / "sounds"
            try:
                path = (sounds_dir / name).resolve()
                if path.parent != sounds_dir.resolve() or path.suffix.lower() != ".ogg":
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
        if parsed.path == "/open-session":
            qs = parse_qs(parsed.query)
            session_name = (qs.get("session", [""])[0] or "").strip()
            fmt = qs.get("format", [""])[0]
            query = active_session_records_query()
            if not session_name or session_name not in query.records:
                if query.state == "unhealthy":
                    self._send_unhealthy(fmt, query.detail)
                    return
                if fmt == "json":
                    self._send_json(404, {"ok": False, "error": "Session not found"})
                else:
                    self._send_html(404, error_page("That session is not available in this repo."))
                return
            active = query.records
            ok, chat_port, detail = ensure_chat_server(session_name)
            if not ok:
                if fmt == "json":
                    self._send_json(500, {"ok": False, "error": detail})
                else:
                    self._send_html(500, error_page(f"Failed to start chat for {session_name}: {detail}"))
                return
            location = format_session_chat_url(
                self.headers.get("Host", "127.0.0.1"),
                session_name,
                chat_port,
                f"/?follow=1&ts={int(time.time() * 1000)}",
            )
            if fmt == "json":
                self._send_json(200, {"ok": True, "chat_url": location, "session_record": active.get(session_name, {})})
            else:
                self.send_response(302)
                self.send_header("Location", location)
                self.end_headers()
            return
        if parsed.path == "/revive-session":
            qs = parse_qs(parsed.query)
            session_name = (qs.get("session", [""])[0] or "").strip()
            fmt = qs.get("format", [""])[0]
            if not session_name:
                if fmt == "json":
                    self._send_json(404, {"ok": False, "error": "Session not found"})
                else:
                    self._send_html(404, error_page("That archived session is not available in this repo."))
                return
            ok, detail = revive_archived_session(session_name)
            if not ok:
                if "unresponsive" in (detail or ""):
                    self._send_unhealthy(fmt, detail)
                    return
                if fmt == "json":
                    self._send_json(500, {"ok": False, "error": detail})
                else:
                    self._send_html(500, error_page(f"Failed to revive {session_name}: {detail}"))
                return
            ok, chat_port, detail = ensure_chat_server(session_name)
            if not ok:
                if fmt == "json":
                    self._send_json(500, {"ok": False, "error": detail})
                else:
                    self._send_html(500, error_page(f"Failed to start chat for {session_name}: {detail}"))
                return
            location = format_session_chat_url(
                self.headers.get("Host", "127.0.0.1"),
                session_name,
                chat_port,
                f"/?follow=1&ts={int(time.time() * 1000)}",
            )
            if fmt == "json":
                query = active_session_records_query()
                self._send_json(200, {"ok": True, "chat_url": location, "session_record": query.records.get(session_name, {})})
            else:
                self.send_response(302)
                self.send_header("Location", location)
                self.end_headers()
            return
        if parsed.path == "/kill-session":
            qs = parse_qs(parsed.query)
            session_name = (qs.get("session", [""])[0] or "").strip()
            if not session_name:
                self._send_html(404, error_page("That active session is not available in this repo."))
                return
            ok, detail = kill_repo_session(session_name)
            if not ok:
                self._send_html(500, error_page(f"Failed to kill {session_name}: {detail}"))
                return
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if parsed.path == "/delete-archived-session":
            qs = parse_qs(parsed.query)
            session_name = (qs.get("session", [""])[0] or "").strip()
            if not session_name:
                self._send_html(404, error_page("That archived session is not available in this repo."))
                return
            ok, detail = delete_archived_session(session_name)
            if not ok:
                self._send_html(500, error_page(f"Failed to delete archived session {session_name}: {detail}"))
                return
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if parsed.path == "/" or parsed.path == "/index.html":
            self._send_html(200, HUB_HOME_HTML)
            return
        if parsed.path == "/resume":
            self._send_html(200, HUB_RESUME_HTML)
            return
        if parsed.path == "/stats":
            self._send_html(200, HUB_STATS_HTML)
            return
        if parsed.path == "/crons":
            qs = parse_qs(parsed.query)
            edit_id = (qs.get("edit", [""])[0] or "").strip()
            edit_job = get_cron_job(repo_root, edit_id) if edit_id else None
            notice = (qs.get("notice", [""])[0] or "").strip()
            if edit_id and edit_job is None and not notice:
                notice = "Cron not found."
            self._render_crons(
                notice=notice,
                prefill_session=(qs.get("session", [""])[0] or "").strip(),
                prefill_agent=(qs.get("agent", [""])[0] or "").strip(),
                edit_job=edit_job,
            )
            return
        if parsed.path == "/settings":
            saved = (parse_qs(parsed.query).get("saved", ["0"])[0] == "1")
            self._send_html(200, hub_settings_html(saved=saved))
            return
        if parsed.path == "/push-config":
            settings = load_hub_settings()
            self._send_json(200, {
                "enabled": bool(settings.get("chat_browser_notifications", False)),
                "public_key": vapid_public_key(repo_root),
            })
            return
        if parsed.path == "/new-session":
            self._send_html(200, HUB_NEW_SESSION_HTML)
            return
        if parsed.path == "/dirs":
            import os as _os
            qs = parse_qs(parsed.query)
            req_path = (qs.get("path", [""])[0] or "").strip()
            home = str(Path.home())
            if not req_path:
                req_path = home
            try:
                real = str(Path(req_path).resolve())
            except Exception:
                real = home
            if not real.startswith(home):
                real = home
            _SKIP = frozenset({"node_modules", "__pycache__"})
            entries = []
            try:
                with _os.scandir(real) as it:
                    for entry in sorted(it, key=lambda e: e.name.lower()):
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                        if entry.name.startswith("."):
                            continue
                        if entry.name in _SKIP:
                            continue
                        has_ch = False
                        try:
                            has_ch = any(True for e2 in _os.scandir(entry.path) if e2.is_dir(follow_symlinks=False) and not e2.name.startswith("."))
                        except PermissionError:
                            pass
                        entries.append({"name": entry.name, "path": entry.path, "has_children": has_ch})
            except PermissionError:
                pass
            parent = str(Path(real).parent) if real != home else None
            self._send_json(200, {"path": real, "parent": parent, "home": home, "entries": entries})
            return
        if parsed.path == "/hub-logo":
            body = read_hub_header_logo_bytes(repo_root)
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
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/session/"):
            self._proxy_session_request("POST", parsed)
            return
        if parsed.path == "/restart-hub":
            queue_hub_restart()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        if parsed.path == "/crons/save":
            data = self._read_form()
            enabled = str(data.get("enabled") or "").strip().lower() in {"1", "true", "yes", "on"}
            draft = {
                "id": str(data.get("id") or "").strip(),
                "name": str(data.get("name") or "").strip(),
                "time": str(data.get("time") or "").strip(),
                "session": str(data.get("session") or "").strip(),
                "agent": str(data.get("agent") or "").strip(),
                "prompt": str(data.get("prompt") or "").replace("\r\n", "\n").strip(),
                "enabled": enabled,
            }
            try:
                saved = save_cron_job(repo_root, draft)
            except ValueError as exc:
                self._render_crons(
                    notice=str(exc),
                    prefill_session=draft["session"],
                    prefill_agent=draft["agent"],
                    edit_job=draft,
                    status=400,
                )
                return
            self._redirect(_cron_redirect_location(notice=f"Saved cron: {saved.get('name') or saved.get('id') or 'cron'}"))
            return
        if parsed.path == "/crons/delete":
            data = self._read_form()
            job_id = str(data.get("id") or "").strip()
            job = get_cron_job(repo_root, job_id)
            removed = delete_cron_job(repo_root, job_id)
            label = (job or {}).get("name") or job_id or "cron"
            notice = f"Deleted cron: {label}" if removed else "Cron not found."
            self._redirect(_cron_redirect_location(notice=notice))
            return
        if parsed.path == "/crons/toggle":
            data = self._read_form()
            job_id = str(data.get("id") or "").strip()
            enabled = str(data.get("enabled") or "").strip().lower() in {"1", "true", "yes", "on"}
            updated = set_cron_enabled(repo_root, job_id, enabled)
            if updated is None:
                self._redirect(_cron_redirect_location(notice="Cron not found."))
                return
            label = updated.get("name") or job_id or "cron"
            state = "enabled" if enabled else "disabled"
            self._redirect(_cron_redirect_location(notice=f"{label} {state}."))
            return
        if parsed.path == "/crons/run":
            data = self._read_form()
            job_id = str(data.get("id") or "").strip()
            job = get_cron_job(repo_root, job_id)
            ok, detail = cron_scheduler.run_now(job_id)
            if ok:
                label = (job or {}).get("name") or job_id or "cron"
                self._redirect(_cron_redirect_location(notice=f"Dispatched cron: {label}"))
            else:
                self._redirect(_cron_redirect_location(notice=detail or "Failed to run cron."))
            return
        if parsed.path == "/settings":
            data = self._read_form()
            save_hub_settings(data)
            self._redirect("/settings?saved=1")
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
                result = upsert_hub_push_subscription(
                    repo_root,
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
                    hub_push_monitor.record_presence(
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
                removed = remove_hub_push_subscription(repo_root, endpoint)
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
                hub_push_monitor.record_presence(
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
        if parsed.path == "/start-session":
            import json as _json
            import re as _re
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length)
            try:
                data = _json.loads(raw)
            except Exception:
                self._send_json(400, {"ok": False, "error": "invalid JSON"})
                return
            workspace = (data.get("workspace") or "").strip()
            session_name = (data.get("session_name") or "").strip()
            agents = [a for a in (data.get("agents") or []) if a in ALL_AGENT_NAMES]
            if not workspace or not Path(workspace).is_dir():
                self._send_json(400, {"ok": False, "error": f"Invalid workspace: {workspace or '(empty)'}"})
                return
            if not agents:
                self._send_json(400, {"ok": False, "error": "Select at least one agent."})
                return
            agent_counts = {}
            for agent in agents:
                agent_counts[agent] = agent_counts.get(agent, 0) + 1
            if any(count > NEW_SESSION_MAX_PER_AGENT for count in agent_counts.values()):
                self._send_json(400, {"ok": False, "error": f"Each agent is limited to {NEW_SESSION_MAX_PER_AGENT} instances."})
                return
            if not session_name:
                session_name = Path(workspace).name
            session_name = _re.sub(r"[^a-zA-Z0-9_.\-]", "-", session_name)[:64]
            launch_agents = agents
            preflight = []
            seen_bases = set()
            for agent in launch_agents:
                base = str(agent or "").split("-", 1)[0]
                if not base or base in seen_bases:
                    continue
                seen_bases.add(base)
                readiness = agent_launch_readiness(Path(workspace), base)
                if readiness.get("status") != "ok":
                    preflight.append(readiness)
            if preflight:
                first = preflight[0]
                self._send_json(
                    400,
                    {
                        "ok": False,
                        "error": first.get("error") or "Selected agent is not ready to launch.",
                        "reason": first.get("status") or "preflight_failed",
                        "agent": first.get("agent") or "",
                        "problems": preflight,
                    },
                )
                return
            agents_str = ",".join(launch_agents)
            multiagent_bin = str(script_path.parent / "multiagent")
            try:
                subprocess.Popen(
                    [multiagent_bin, "--detach", "--session", session_name, "--workspace", workspace, "--agents", agents_str],
                    cwd=workspace, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
                return
            if not wait_for_session_instances(session_name, launch_agents):
                self._send_json(500, {"ok": False, "error": "session panes did not become ready"})
                return
            ok, chat_port, detail = ensure_chat_server(session_name)
            if ok:
                query = active_session_records_query()
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "session": session_name,
                        "chat_url": format_session_chat_url(
                            self.headers.get("Host", "127.0.0.1"),
                            session_name,
                            chat_port,
                            "/?follow=1",
                        ),
                        "session_record": query.records.get(session_name, {}),
                    },
                )
            else:
                self._send_json(500, {"ok": False, "error": detail})
            return
        self.send_response(404)
        self.end_headers()

    def _proxy_session_request(self, method: str, parsed):
        match = re.match(r"^/session/([^/]+)(/.*)?$", parsed.path)
        if not match:
            self.send_response(404)
            self.end_headers()
            return
        session_name = match.group(1)
        suffix = match.group(2) or "/"
        query = active_session_records_query()
        if session_name not in query.records:
            if query.state == "unhealthy":
                self._send_unhealthy("plain", query.detail)
                return
            self._send_html(404, error_page("That session is not available in this repo."))
            return
        ok, chat_port, detail = ensure_chat_server(session_name)
        if not ok:
            self._send_html(500, error_page(f"Failed to start chat for {session_name}: {detail}"))
            return
        body = None
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            body = self.rfile.read(length)
        query = f"?{parsed.query}" if parsed.query else ""
        upstream = f"https://127.0.0.1:{chat_port}{suffix}{query}"
        headers = {}
        for key, value in self.headers.items():
            key_lc = key.lower()
            if key_lc in {"host", "content-length", "connection", "accept-encoding"}:
                continue
            headers[key] = value
        headers["Host"] = f"127.0.0.1:{chat_port}"
        headers["Accept-Encoding"] = "identity"
        headers["X-Forwarded-Prefix"] = f"/session/{session_name}"
        req = Request(upstream, data=body, method=method, headers=headers)
        ctx = ssl._create_unverified_context()
        try:
            # multiagent-public-edge のプロキシと同様 30s（セッション・リロード時の並列転送向け）
            resp = urlopen(req, context=ctx, timeout=30)
            resp_body = resp.read()
            status = resp.status
            resp_headers = resp.headers
        except HTTPError as exc:
            resp_body = exc.read()
            status = exc.code
            resp_headers = exc.headers
        except URLError as exc:
            self._send_html(502, error_page(f"Chat proxy failed for {session_name}: {exc}"))
            return
        self.send_response(status)
        for key, value in resp_headers.items():
            key_lc = key.lower()
            if key_lc in {"transfer-encoding", "connection", "content-length", "content-encoding"}:
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)

def main(argv: list[str] | None = None) -> None:
    global _scheme, hub_server

    initialize_from_argv(argv)

    cert_file = os.environ.get("MULTIAGENT_CERT_FILE", "")
    key_file = os.environ.get("MULTIAGENT_KEY_FILE", "")
    use_https = bool(cert_file and key_file)
    _scheme = "https" if use_https else "http"
    ThreadingHTTPServer.allow_reuse_address = True
    hub_server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    if use_https:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        hub_server.socket = ctx.wrap_socket(hub_server.socket, server_side=True)
    print(f"{_scheme}://127.0.0.1:{port}/", flush=True)
    hub_server.serve_forever()


if __name__ == "__main__":
    main()
