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
from agent_index.hub_settings_crons_view_core import (
    available_chat_font_choices as _available_chat_font_choices_impl,
    hub_crons_html as _hub_crons_html_impl,
    hub_settings_html as _hub_settings_html_impl,
    normalized_font_label as _normalized_font_label_impl,
)
from agent_index.hub_server_post_routes_core import (
    post_push_presence as _post_push_presence_impl,
    post_push_subscribe as _post_push_subscribe_impl,
    post_push_unsubscribe as _post_push_unsubscribe_impl,
    post_start_session as _post_start_session_impl,
)
from agent_index.hub_server_helpers_core import (
    build_hub_html_pages as _build_hub_html_pages_impl,
    clean_env as _clean_env_impl,
    cron_records_query as _cron_records_query_impl,
    cron_redirect_location as _cron_redirect_location_impl,
    error_page as _error_page_impl,
    format_external_url as _format_external_url_impl,
    format_session_chat_url as _format_session_chat_url_impl,
    icon_data_uri as _icon_data_uri_impl,
    is_public_host as _is_public_host_impl,
    launch_hub_restart as _launch_hub_restart_impl,
    pwa_asset_url as _pwa_asset_url_impl,
    pwa_asset_version as _pwa_asset_version_impl,
    pwa_icon_entries as _pwa_icon_entries_impl,
    pwa_shortcut_entries as _pwa_shortcut_entries_impl,
    resolve_external_origin as _resolve_external_origin_impl,
    restarting_page as _restarting_page_impl,
    serve_pwa_static as _serve_pwa_static_impl,
)

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
    return _resolve_external_origin_impl(
        host_header,
        local_port,
        host_without_port_fn=host_without_port,
        public_host=PUBLIC_HOST,
        public_hub_port=PUBLIC_HUB_PORT,
        hub_port=port,
        scheme=_scheme,
    )


def format_external_url(host_header: str, local_port: int, path: str) -> str:
    return _format_external_url_impl(
        host_header,
        local_port,
        path,
        resolve_external_origin_fn=resolve_external_origin,
    )


def is_public_host(host_header: str) -> bool:
    return _is_public_host_impl(
        host_header,
        resolve_external_origin_fn=resolve_external_origin,
        hub_port=0,
    )


def format_session_chat_url(host_header: str, session_name: str, local_port: int, path: str) -> str:
    return _format_session_chat_url_impl(
        host_header,
        session_name,
        local_port,
        path,
        resolve_external_origin_fn=lambda header, _port: resolve_external_origin(header, port),
        format_external_url_fn=format_external_url,
        url_quote_fn=url_quote,
    )


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

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 4:
        raise SystemExit(
            "usage: python -m agent_index.hub_server <repo_root> <script_path> <port> <tmux_socket>"
        )

    root_arg, script_arg, port_arg, tmux_socket = args
    repo_root = Path(root_arg).resolve()
    script_path = Path(script_arg).resolve()
    port = int(port_arg)
    hub = HubRuntime(repo_root, script_path, tmux_socket, hub_port=port)
    for attr in (
        "load_hub_settings",
        "save_hub_settings",
        "repo_sessions",
        "repo_sessions_query",
        "archived_sessions",
        "active_session_records",
        "active_session_records_query",
        "archived_session_records",
        "compute_hub_stats",
        "ensure_chat_server",
        "wait_for_session_instances",
        "revive_archived_session",
        "kill_repo_session",
        "delete_archived_session",
        "host_without_port",
    ):
        globals()[attr] = getattr(hub, attr)
    PUBLIC_HOST = (os.environ.get("MULTIAGENT_PUBLIC_HOST", "") or "").strip().rstrip(".").lower()
    PUBLIC_HUB_PORT = int(os.environ.get("MULTIAGENT_PUBLIC_HUB_PORT", "443") or "443")
    restart_pending, hub_server = False, None
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
    for target, name in (
        (hub_push_monitor.run_forever, "hub-push-monitor"),
        (cron_scheduler.run_forever, "cron-scheduler"),
    ):
        threading.Thread(target=target, daemon=True, name=name).start()
    _initialized = True


def restarting_page():
    return _restarting_page_impl()


def _clean_env():
    return _clean_env_impl(env_mapping=os.environ)


def queue_hub_restart():
    global restart_pending
    with restart_lock:
        if restart_pending:
            return False
        restart_pending = True
    return _launch_hub_restart_impl(
        script_path=script_path,
        port=port,
        repo_root=repo_root,
        clean_env_fn=_clean_env,
        subprocess_module=subprocess,
        sys_module=sys,
        hub_server_getter=lambda: hub_server,
        threading_module=threading,
        time_module=time,
    )

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
    return _pwa_asset_version_impl(
        path,
        pwa_asset_version_overrides=_PWA_ASSET_VERSION_OVERRIDES,
        pwa_static_routes=_PWA_STATIC_ROUTES,
        pwa_static_dir=_PWA_STATIC_DIR,
        fallback_file=__file__,
    )

def _icon_data_uri(filename: str) -> str:
    return _icon_data_uri_impl(
        filename,
        repo_root=repo_root,
        agent_icons_dir=AGENT_ICONS_DIR,
        base64_module=_base64,
    )


def _pwa_asset_url(path: str, base_path: str = "", *, bust: bool = False) -> str:
    return _pwa_asset_url_impl(
        path,
        base_path=base_path,
        bust=bust,
        pwa_asset_version_fn=_pwa_asset_version,
    )


def _pwa_icon_entries(base_path: str = "") -> list[dict[str, str]]:
    return _pwa_icon_entries_impl(
        base_path=base_path,
        pwa_asset_url_fn=_pwa_asset_url,
    )


def _pwa_shortcut_entries(base_path: str = "") -> list[dict[str, object]]:
    return _pwa_shortcut_entries_impl(
        base_path=base_path,
        pwa_asset_url_fn=_pwa_asset_url,
    )


_PWA_HUB_MANIFEST_URL = _pwa_asset_url("/hub.webmanifest", bust=True)
_PWA_ICON_192_URL = _pwa_asset_url("/pwa-icon-192.png", bust=True)
_PWA_APPLE_TOUCH_ICON_URL = _pwa_asset_url("/apple-touch-icon.png", bust=True)


def _serve_pwa_static(handler, path: str) -> bool:
    return _serve_pwa_static_impl(
        handler,
        path,
        pwa_static_routes=_PWA_STATIC_ROUTES,
        pwa_static_dir=_PWA_STATIC_DIR,
    )

_HUB_ICON_URIS = {name: _icon_data_uri(fname) for name, fname in _icon_filename_map().items()}
_HUB_LOGO_DATA_URI = hub_header_logo_data_uri(repo_root)
_HUB_PAGE_HEADER_CSS = HUB_PAGE_HEADER_CSS
_HUB_PAGE_HEADER_HTML = render_hub_page_header(logo_data_uri=_HUB_LOGO_DATA_URI)
_HUB_PAGE_HEADER_JS = HUB_PAGE_HEADER_JS

_HUB_CRONS_TEMPLATE = (Path(__file__).resolve().parent / "hub_crons_template.html").read_text()
_HUB_SETTINGS_TEMPLATE = (Path(__file__).resolve().parent / "hub_settings_template.html").read_text()
_hub_pages = _build_hub_html_pages_impl(
    template_dir=Path(__file__).resolve().parent,
    all_agent_names=ALL_AGENT_NAMES,
    selectable_agent_names=SELECTABLE_AGENT_NAMES,
    pwa_hub_manifest_url=_PWA_HUB_MANIFEST_URL,
    pwa_icon_192_url=_PWA_ICON_192_URL,
    pwa_apple_touch_icon_url=_PWA_APPLE_TOUCH_ICON_URL,
    hub_header_css=_HUB_PAGE_HEADER_CSS,
    hub_header_html=_HUB_PAGE_HEADER_HTML,
    hub_header_js=_HUB_PAGE_HEADER_JS,
    new_session_max_per_agent=NEW_SESSION_MAX_PER_AGENT,
    hub_icon_uris=_HUB_ICON_URIS,
)
HUB_APP_HTML = _hub_pages["hub_app_html"]
HUB_RESUME_HTML = _hub_pages["hub_resume_html"]
HUB_STATS_HTML = _hub_pages["hub_stats_html"]
HUB_HOME_HTML = _hub_pages["hub_home_html"]


def _normalized_font_label(name: str) -> str:
    return _normalized_font_label_impl(name)


def available_chat_font_choices():
    return _available_chat_font_choices_impl(
        path_class=Path,
        normalized_font_label_fn=_normalized_font_label,
    )

def hub_settings_html(saved=False):
    return _hub_settings_html_impl(
        saved=bool(saved),
        load_hub_settings_fn=load_hub_settings,
        available_theme_choices_fn=available_theme_choices,
        theme_description_fn=theme_description,
        available_chat_font_choices_fn=available_chat_font_choices,
        settings_template=_HUB_SETTINGS_TEMPLATE,
        pwa_hub_manifest_url=_PWA_HUB_MANIFEST_URL,
        pwa_icon_192_url=_PWA_ICON_192_URL,
        pwa_apple_touch_icon_url=_PWA_APPLE_TOUCH_ICON_URL,
        hub_header_css=_HUB_PAGE_HEADER_CSS,
        hub_header_html=_HUB_PAGE_HEADER_HTML,
        hub_header_js=_HUB_PAGE_HEADER_JS,
    )

HUB_NEW_SESSION_HTML = _hub_pages["hub_new_session_html"]


def hub_crons_html(*, jobs, session_records, notice="", prefill_session="", prefill_agent="", edit_job=None):
    return _hub_crons_html_impl(
        jobs=jobs,
        session_records=session_records,
        notice=notice,
        prefill_session=prefill_session,
        prefill_agent=prefill_agent,
        edit_job=edit_job,
        load_hub_settings_fn=load_hub_settings,
        all_agent_names=ALL_AGENT_NAMES,
        crons_template=_HUB_CRONS_TEMPLATE,
        pwa_hub_manifest_url=_PWA_HUB_MANIFEST_URL,
        pwa_icon_192_url=_PWA_ICON_192_URL,
        pwa_apple_touch_icon_url=_PWA_APPLE_TOUCH_ICON_URL,
        hub_header_css=_HUB_PAGE_HEADER_CSS,
        hub_header_html=_HUB_PAGE_HEADER_HTML,
        hub_header_js=_HUB_PAGE_HEADER_JS,
    )


def _cron_records_query():
    return _cron_records_query_impl(
        active_session_records_query_fn=active_session_records_query,
        archived_session_records_fn=archived_session_records,
    )

def _cron_redirect_location(*, notice="", session_name="", agent="", edit_id="") -> str:
    return _cron_redirect_location_impl(
        notice=notice,
        session_name=session_name,
        agent=agent,
        edit_id=edit_id,
        url_quote_fn=url_quote,
    )

def error_page(message):
    return _error_page_impl(message, html_escape_fn=html.escape)

_GET_ROUTE_HANDLERS = {
    "/hub.webmanifest": "_get_hub_manifest",
    "/sessions": "_get_sessions",
    "/notify-sound": "_get_notify_sound",
    "/open-session": "_get_open_session",
    "/revive-session": "_get_revive_session",
    "/kill-session": "_get_kill_session",
    "/delete-archived-session": "_get_delete_archived_session",
    "/": "_get_home",
    "/index.html": "_get_home",
    "/resume": "_get_resume",
    "/stats": "_get_stats",
    "/crons": "_get_crons",
    "/settings": "_get_settings",
    "/push-config": "_get_push_config",
    "/new-session": "_get_new_session",
    "/dirs": "_get_dirs",
    "/hub-logo": "_get_hub_logo",
}

_POST_ROUTE_HANDLERS = {
    "/restart-hub": "_post_restart_hub",
    "/crons/save": "_post_crons_save",
    "/crons/delete": "_post_crons_delete",
    "/crons/toggle": "_post_crons_toggle",
    "/crons/run": "_post_crons_run",
    "/settings": "_post_settings",
    "/push/subscribe": "_post_push_subscribe",
    "/push/unsubscribe": "_post_push_unsubscribe",
    "/push/presence": "_post_push_presence",
    "/mkdir": "_post_mkdir",
    "/start-session": "_post_start_session",
}

class Handler(BaseHTTPRequestHandler):
    _GET_ROUTE_HANDLERS = _GET_ROUTE_HANDLERS
    _POST_ROUTE_HANDLERS = _POST_ROUTE_HANDLERS

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

    def _dispatch_route(self, parsed, route_map: dict[str, str]) -> bool:
        handler_name = route_map.get(parsed.path)
        if not handler_name:
            return False
        getattr(self, handler_name)(parsed)
        return True

    def _get_hub_manifest(self, _parsed):
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

    def _get_sessions(self, _parsed):
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

    def _get_notify_sound(self, parsed):
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

    def _get_open_session(self, parsed):
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

    def _get_revive_session(self, parsed):
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

    def _get_kill_session(self, parsed):
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

    def _get_delete_archived_session(self, parsed):
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

    def _get_home(self, _parsed):
        self._send_html(200, HUB_HOME_HTML)

    def _get_resume(self, _parsed):
        self._send_html(200, HUB_RESUME_HTML)

    def _get_stats(self, _parsed):
        self._send_html(200, HUB_STATS_HTML)

    def _get_crons(self, parsed):
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

    def _get_settings(self, parsed):
        saved = (parse_qs(parsed.query).get("saved", ["0"])[0] == "1")
        self._send_html(200, hub_settings_html(saved=saved))

    def _get_push_config(self, _parsed):
        settings = load_hub_settings()
        self._send_json(200, {
            "enabled": bool(settings.get("chat_browser_notifications", False)),
            "public_key": vapid_public_key(repo_root),
        })

    def _get_new_session(self, _parsed):
        self._send_html(200, HUB_NEW_SESSION_HTML)

    def _get_dirs(self, parsed):
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
                        has_ch = any(
                            True
                            for e2 in _os.scandir(entry.path)
                            if e2.is_dir(follow_symlinks=False) and not e2.name.startswith(".")
                        )
                    except PermissionError:
                        pass
                    entries.append({"name": entry.name, "path": entry.path, "has_children": has_ch})
        except PermissionError:
            pass
        parent = str(Path(real).parent) if real != home else None
        self._send_json(200, {"path": real, "parent": parent, "home": home, "entries": entries})

    def _get_hub_logo(self, _parsed):
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

    def _post_restart_hub(self, _parsed):
        queue_hub_restart()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def _post_crons_save(self, _parsed):
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

    def _post_crons_delete(self, _parsed):
        data = self._read_form()
        job_id = str(data.get("id") or "").strip()
        job = get_cron_job(repo_root, job_id)
        removed = delete_cron_job(repo_root, job_id)
        label = (job or {}).get("name") or job_id or "cron"
        notice = f"Deleted cron: {label}" if removed else "Cron not found."
        self._redirect(_cron_redirect_location(notice=notice))

    def _post_crons_toggle(self, _parsed):
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

    def _post_crons_run(self, _parsed):
        data = self._read_form()
        job_id = str(data.get("id") or "").strip()
        job = get_cron_job(repo_root, job_id)
        ok, detail = cron_scheduler.run_now(job_id)
        if ok:
            label = (job or {}).get("name") or job_id or "cron"
            self._redirect(_cron_redirect_location(notice=f"Dispatched cron: {label}"))
        else:
            self._redirect(_cron_redirect_location(notice=detail or "Failed to run cron."))

    def _post_settings(self, _parsed):
        data = self._read_form()
        save_hub_settings(data)
        self._redirect("/settings?saved=1")

    def _post_push_subscribe(self, _parsed):
        _post_push_subscribe_impl(
            self,
            repo_root=repo_root,
            upsert_hub_push_subscription_fn=upsert_hub_push_subscription,
            hub_push_monitor=hub_push_monitor,
        )

    def _post_push_unsubscribe(self, _parsed):
        _post_push_unsubscribe_impl(
            self,
            repo_root=repo_root,
            remove_hub_push_subscription_fn=remove_hub_push_subscription,
        )

    def _post_push_presence(self, _parsed):
        _post_push_presence_impl(self, hub_push_monitor=hub_push_monitor)

    def _post_mkdir(self, _parsed):
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

    def _post_start_session(self, _parsed):
        _post_start_session_impl(
            self,
            all_agent_names=ALL_AGENT_NAMES,
            new_session_max_per_agent=NEW_SESSION_MAX_PER_AGENT,
            script_path=script_path,
            wait_for_session_instances_fn=wait_for_session_instances,
            ensure_chat_server_fn=ensure_chat_server,
            active_session_records_query_fn=active_session_records_query,
            format_session_chat_url_fn=format_session_chat_url,
            agent_launch_readiness_fn=agent_launch_readiness,
        )

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/session/"):
            self._proxy_session_request("GET", parsed)
            return
        if _serve_pwa_static(self, parsed.path):
            return
        if self._dispatch_route(parsed, self._GET_ROUTE_HANDLERS):
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/session/"):
            self._proxy_session_request("POST", parsed)
            return
        if self._dispatch_route(parsed, self._POST_ROUTE_HANDLERS):
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
