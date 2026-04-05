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

from agent_index.agent_registry import (
    AGENT_ICONS_DIR,
    ALL_AGENT_NAMES,
    SELECTABLE_AGENT_NAMES,
    icon_filename_map as _icon_filename_map,
)
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

_HUB_CRONS_TEMPLATE = (Path(__file__).resolve().parent / "hub_crons_template.html").read_text()
_HUB_SETTINGS_TEMPLATE = (Path(__file__).resolve().parent / "hub_settings_template.html").read_text()

HUB_APP_HTML = (Path(__file__).resolve().parent / "hub_app_template.html").read_text()
_ALL_AGENT_NAMES_JS_ITEMS = ", ".join(f'"{n}"' for n in ALL_AGENT_NAMES)
_SELECTABLE_AGENT_NAMES_JS_ITEMS = ", ".join(f'"{n}"' for n in SELECTABLE_AGENT_NAMES)
HUB_APP_HTML = (
    HUB_APP_HTML.replace("__ALL_AGENT_NAMES_JS__", _ALL_AGENT_NAMES_JS_ITEMS).replace(
        "__SELECTABLE_AGENT_NAMES_JS__", _SELECTABLE_AGENT_NAMES_JS_ITEMS
    )
)

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

HUB_HOME_HTML = (Path(__file__).resolve().parent / "hub_home_template.html").read_text()
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
    _html = _HUB_SETTINGS_TEMPLATE
    _html = (
        _html
        .replace("__HUB_THEME__", theme)
        .replace("__STARFIELD_ATTR__", sf_attr)
        .replace("__HUB_MANIFEST_URL__", hub_manifest_url)
        .replace("__PWA_ICON_192_URL__", pwa_icon_192_url)
        .replace("__APPLE_TOUCH_ICON_URL__", apple_touch_icon_url)
        .replace("__THEME_HINT_HTML__", html.escape(theme_hint))
        .replace("__THEME_OPTIONS__", theme_options)
        .replace("__NOTICE_HTML__", notice)
        .replace("__USER_MESSAGE_FONT_OPTIONS__", font_options(user_message_font))
        .replace("__AGENT_MESSAGE_FONT_OPTIONS__", font_options(agent_message_font))
        .replace("__FONT_MODE__", font_mode)
        .replace("__MESSAGE_LIMIT__", str(message_limit))
        .replace("__MESSAGE_TEXT_SIZE__", str(message_text_size))
        .replace("__MESSAGE_MAX_WIDTH__", str(message_max_width))
        .replace("__USER_MSG_OPACITY__", f"{user_message_opacity_blackhole:.2f}")
        .replace("__AGENT_MSG_OPACITY__", f"{agent_message_opacity_blackhole:.2f}")
        .replace("__CHAT_AUTO_CHECKED__", " checked" if chat_auto else "")
        .replace("__CHAT_AWAKE_CHECKED__", " checked" if chat_awake else "")
        .replace("__CHAT_SOUND_CHECKED__", " checked" if chat_sound else "")
        .replace("__CHAT_BROWSER_NOTIF_CHECKED__", " checked" if chat_browser_notifications else "")
        .replace("__CHAT_TTS_CHECKED__", " checked" if chat_tts else "")
        .replace("__STARFIELD_CHECKED__", " checked" if starfield else "")
        .replace("__BOLD_MODE_CHECKED__", " checked" if bold_mode else "")
    )
    return (
        _html
        .replace("__HUB_HEADER_CSS__", _HUB_PAGE_HEADER_CSS)
        .replace("__HUB_HEADER_HTML__", _HUB_PAGE_HEADER_HTML)
        .replace("__HUB_HEADER_JS__", _HUB_PAGE_HEADER_JS)
    )

HUB_NEW_SESSION_HTML = (Path(__file__).resolve().parent / "hub_new_session_template.html").read_text()
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

    page = _HUB_CRONS_TEMPLATE
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
            if detail:
                logging.warning("Session %s terminated but cleanup incomplete: %s", session_name, detail)
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
        if parsed.path == "/mkdir":
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
            path_str = str(data.get("path") or "").strip()
            if not path_str:
                self._send_json(400, {"ok": False, "error": "path required"})
                return
            path = Path(path_str)
            try:
                path.mkdir(parents=True, exist_ok=True)
                self._send_json(200, {"ok": True, "path": str(path.resolve())})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
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
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert_file, key_file)
        hub_server.socket = ctx.wrap_socket(hub_server.socket, server_side=True)
    print(f"{_scheme}://127.0.0.1:{port}/", flush=True)
    hub_server.serve_forever()


if __name__ == "__main__":
    main()
