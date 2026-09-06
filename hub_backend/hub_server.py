from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote as url_quote, urlparse

from hub_backend.runtime import HubRuntime
from backend_core.access.pwa import pwa_icon_entries as _pwa_icon_entries_impl
from backend_core.access.settings import apply_font_tokens, load_hub_settings, workspace_chat_port
from hub_backend.chat_supervisor import stop_inactive_chat_servers
from hub_backend.presentation.hub.header_assets import (
    DEFAULT_HUB_HEADER_ACTIONS,
    DEFAULT_HUB_HEADER_PANELS,
    PAGE_HEADER_CSS,
    PAGE_HEADER_JS,
    MOBILE_HUB_HEADER_ACTIONS,
    render_page_header,
)
from hub_backend.session_query import (
    active_session_records_query,
    archived_session_records,
    host_without_port,
)

from hub_backend.branding import APP_DISPLAY_NAME
from hub_backend.color_constants import apply_color_tokens, resolve_theme_palette
from hub_backend.new_session.handlers import (
    post_pick_workspace as _post_pick_workspace_action,
    post_start_session_draft as _post_start_session_draft_action,
)
from hub_backend.actions import (
    get_delete_archived_session as _get_delete_archived_session_action,
    get_kill_session as _get_kill_session_action,
    get_open_session as _get_open_session_action,
    get_revive_session as _get_revive_session_action,
    post_rename_session as _post_rename_session_action,
    post_restart_hub as _post_restart_hub_action,
    post_settings as _post_settings_action,
)
from hub_backend.server_helpers import (
    build_hub_html_pages as _build_hub_html_pages_impl,
    clean_env as _clean_env_impl,
    error_page as _error_page_impl,
    _expand_hub_template_includes,
    format_external_url as _format_external_url_impl,
    format_session_chat_url as _format_session_chat_url_impl,
    launch_hub_restart as _launch_hub_restart_impl,
    pwa_asset_url as _pwa_asset_url_impl,
    pwa_asset_version as _pwa_asset_version_impl,
    resolve_external_origin as _resolve_external_origin_impl,
    serve_pwa_static as _serve_pwa_static_impl,
)
from hub_backend.transport.request_view import request_view_variant

_initialized = False
repo_root = Path()
script_path = Path()
port = 0
tmux_socket = ""
hub = None
PUBLIC_HOST = ""
PUBLIC_HUB_PORT = 443
restart_lock = threading.Lock()
restart_pending = False
_restart_release_event = threading.Event()
hub_server = None
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
    global PUBLIC_HOST, PUBLIC_HUB_PORT
    global restart_pending, hub_server, _PWA_STATIC_DIR

    if _initialized:
        return

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 4:
        raise SystemExit(
            "usage: python -m hub_backend.hub_server <repo_root> <script_path> <port> <tmux_socket>"
        )

    root_arg, script_arg, port_arg, tmux_socket = args
    repo_root = Path(root_arg).resolve()
    script_path = Path(script_arg).resolve()
    port = int(port_arg)
    hub = HubRuntime(repo_root, tmux_socket, hub_port=port)
    PUBLIC_HOST = (os.environ.get("AGENT_WINDOW_PUBLIC_HOST", "") or "").strip().rstrip(".").lower()
    PUBLIC_HUB_PORT = int(os.environ.get("AGENT_WINDOW_PUBLIC_HUB_PORT", "443") or "443")
    restart_pending, hub_server = False, None
    _PWA_STATIC_DIR = repo_root / "apps" / "shared" / "pwa"

    _initialized = True


def error_page(message: str) -> str:
    return _error_page_impl(message)


def queue_hub_restart():
    global restart_pending
    with restart_lock:
        if restart_pending:
            return False, "restart already pending", False
        cleanup_detail = stop_inactive_chat_servers(hub)
        if cleanup_detail:
            return False, cleanup_detail, False
        restart_pending = True
    ok = _launch_hub_restart_impl(
        script_path=script_path,
        port=port,
        repo_root=repo_root,
        clean_env_fn=_clean_env_impl,
        hub_server_getter=lambda: hub_server,
    )
    return ok, "" if ok else "reload failed", True


def release_restart_hold():
    """Signal that it's now safe for this process to exit.

    ThreadingHTTPServer's request-handling threads run as daemon threads
    here, so once serve_forever() returns and main() would otherwise fall
    off the end of the script, the interpreter tears down every remaining
    daemon thread immediately -- including whichever one is still in the
    middle of spawning the replacement process or writing this request's
    HTTP response. main() blocks on _restart_release_event after
    serve_forever() returns specifically so that work gets to finish;
    call this once it actually has (see post_restart_hub).
    """
    _restart_release_event.set()

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

_PAGE_HEADER_CSS = PAGE_HEADER_CSS
_PAGE_HEADER_HTML = render_page_header()
_PAGE_HEADER_HTML_MOBILE = render_page_header(actions_html=MOBILE_HUB_HEADER_ACTIONS)
_PAGE_HEADER_JS = PAGE_HEADER_JS
_HUB_LAUNCH_SHELL_BODY_HTML = (
    '<div class="launch-shell-card" id="launchShellCard">'
    '<span class="launch-shell-title">Agent Window</span>'
    "</div>"
)
HUB_LAUNCH_SHELL_HTML = f"""<!doctype html>
<html lang="en" data-theme-desktop="__THEME_DESKTOP__" data-theme-mobile="__THEME_MOBILE__" data-view="__VIEW_VARIANT__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="__DARK_BG__">
  <title>{APP_DISPLAY_NAME}</title>
  <style>
    :root {{ color-scheme: __COLOR_SCHEME__; --bg: __DARK_BG__; --fg: __LIGHT_FG__; }}
    html[data-theme-desktop="dark"] {{ --launch-shell-title-fg: rgb(255,255,255); }}
    html, body {{
      margin: 0;
      min-height: 100%;
      background: var(--bg);
      color: var(--fg);
    }}
    html[data-view="mobile"] {{ --bg: __MOBILE_HUB_DARK_BG__; }}
    html[data-view="mobile"][data-theme-mobile="light"] {{ --bg: __MOBILE_HUB_LIGHT_BG__; }}
    html[data-tauri-app="1"],
    html[data-tauri-app="1"] body {{ background: transparent; }}
    @media (prefers-color-scheme: light) {{
      html[data-theme-desktop="system"] {{
        color-scheme: light;
        --fg: __SYSTEM_LIGHT_FG__;
      }}
      html[data-view="mobile"][data-theme-mobile="system"] {{ --bg: __MOBILE_HUB_LIGHT_BG__; }}
    }}
    @media (prefers-color-scheme: dark) {{
      html[data-theme-desktop="system"] {{ --launch-shell-title-fg: rgb(255,255,255); }}
    }}
    body {{
      display: grid;
      place-items: center;
      padding: 24px;
      font-family: var(--font-main);
    }}
    .launch-shell {{
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      min-height: calc(100dvh - 48px);
    }}
    .launch-shell-card {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: auto;
      height: auto;
      border-radius: 0;
      background: transparent;
      border: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      box-shadow: none;
    }}
    @keyframes titleFadeIn {{
      0% {{ opacity: 0; }}
      100% {{ opacity: 1; }}
    }}
    .launch-shell-title {{
      color: var(--launch-shell-title-fg, var(--fg));
      font-family: "Snell Roundhand", "Apple Chancery", cursive;
      font-size: 30px;
      font-weight: 200;
      letter-spacing: -0.04em;
      line-height: 1;
      white-space: nowrap;
      opacity: 0;
      animation: titleFadeIn 800ms ease-out forwards;
    }}
    html[data-view="mobile"] .launch-shell-title {{
      color: rgb(__TEXT_SESSION_MOBILE_DARK_CHANNELS__);
      font-size: 26px;
      font-weight: 900;
      padding: 0 12px;
    }}
    html[data-view="mobile"][data-theme-mobile="light"] .launch-shell-title {{ color: rgb(__TEXT_SESSION_MOBILE_LIGHT_CHANNELS__); }}
    @media (prefers-color-scheme: light) {{
      html[data-view="mobile"][data-theme-mobile="system"] .launch-shell-title {{ color: rgb(__TEXT_SESSION_MOBILE_LIGHT_CHANNELS__); }}
    }}
    .launch-shell-card.is-error {{
      width: auto;
      height: auto;
      font-size: 13px;
      line-height: 1.5;
      color: var(--fg);
    }}
  </style>
</head>
<body>
  <div class="launch-shell">
    {_HUB_LAUNCH_SHELL_BODY_HTML}
  </div>
  <script>
    (() => {{
      const params = new URLSearchParams(window.location.search || "");
      const shellPath = "/hub-launch-shell.html";
      const requestedRestart = params.get("restart") === "1";
      let restartRequested = false;
      const requestHubRestart = async () => {{
        if (!requestedRestart || restartRequested) return true;
        restartRequested = true;
        try {{
          const res = await fetch("/restart-hub", {{ method: "POST" }});
          return res.ok;
        }} catch (_err) {{
          return false;
        }}
      }};
      const ensureLaunchShellFlag = (rawTarget) => {{
        try {{
          const next = new URL(rawTarget || "/", window.location.origin);
          if (next.pathname === shellPath) return "/";
          if (!next.searchParams.has("launch_shell")) next.searchParams.set("launch_shell", "1");
          return next.pathname + next.search + next.hash;
        }} catch (_err) {{
          return "/?launch_shell=1";
        }}
      }};
      const requestedTarget = (params.get("target") || "").trim();
      const current = window.location.pathname + window.location.search + window.location.hash;
      let target = "/";
      if (requestedTarget) {{
        try {{
          const next = new URL(requestedTarget, window.location.origin);
          if (next.origin === window.location.origin && next.pathname !== shellPath) {{
            target = next.pathname + next.search + next.hash;
          }}
        }} catch (_err) {{}}
      }} else if (window.location.pathname !== shellPath) {{
        target = current;
      }}
      target = ensureLaunchShellFlag(target);
      const adoptTargetUrl = () => {{
        try {{
          window.history.replaceState(window.history.state, "", target);
          return true;
        }} catch (_err) {{
          try {{
            window.location.replace(target);
          }} catch (_replaceErr) {{
            window.location.href = target;
          }}
          return false;
        }}
      }};
      const launchShellCard = document.getElementById("launchShellCard");
      const showLaunchShellError = (message) => {{
        if (!launchShellCard) return;
        launchShellCard.classList.add("is-error");
        launchShellCard.textContent = String(message || "Hub is not responding.");
      }};
      const attemptLoad = async () => {{
        const response = await fetch(target, {{ cache: "no-store" }});
        if (!response.ok) throw new Error(`load failed: ${{response.status}}`);
        const html = await response.text();
        if (!adoptTargetUrl()) return;
        document.open();
        document.write(html);
        document.close();
      }};
      const load = async () => {{
        if (requestedRestart) {{
          const restarted = await requestHubRestart();
          if (!restarted) {{
            showLaunchShellError("restart failed");
            return;
          }}
        }}
        try {{
          await attemptLoad();
        }} catch (_err) {{
          showLaunchShellError();
        }}
      }};
      load();
    }})();
  </script>
</body>
</html>"""

_HUB_SHARED_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "apps" / "shared" / "hub" / "templates"
_HUB_DESKTOP_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "apps" / "desktop" / "hub"
_HUB_MOBILE_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "apps" / "mobile" / "hub"
_hub_pages = _build_hub_html_pages_impl(
    desktop_template_dir=_HUB_DESKTOP_TEMPLATE_DIR,
    mobile_template_dir=_HUB_MOBILE_TEMPLATE_DIR,
    shared_template_dir=_HUB_SHARED_TEMPLATE_DIR,
    pwa_hub_manifest_url=_PWA_HUB_MANIFEST_URL,
    pwa_icon_192_url=_PWA_ICON_192_URL,
    pwa_apple_touch_icon_url=_PWA_APPLE_TOUCH_ICON_URL,
    hub_header_css=_PAGE_HEADER_CSS,
    hub_header_html=_PAGE_HEADER_HTML,
    hub_header_html_mobile=_PAGE_HEADER_HTML_MOBILE,
    hub_header_js=_PAGE_HEADER_JS,
)
HUB_HOME_DESKTOP_HTML = _hub_pages["hub_home_html_desktop"]
HUB_HOME_MOBILE_HTML = _hub_pages["hub_home_html_mobile"]


def _hub_action_context() -> dict[str, object]:
    return {
        "hub": hub,
        "error_page_fn": error_page,
        "format_session_chat_url_fn": format_session_chat_url,
        "queue_hub_restart_fn": queue_hub_restart,
        "release_restart_hold_fn": release_restart_hold,
    }


_GET_ROUTE_HANDLERS = {
    "/hub.webmanifest": "_get_hub_manifest",
    "/hub-launch-shell.html": "_get_hub_launch_shell",
    "/sessions": "_get_sessions",
    "/session-messages-events": "_get_session_messages_events",
    "/open-session": _get_open_session_action,
    "/revive-session": _get_revive_session_action,
    "/kill-session": _get_kill_session_action,
    "/delete-archived-session": _get_delete_archived_session_action,
    "/": "_get_home",
    "/index.html": "_get_home",
}

_POST_ROUTE_HANDLERS = {
    "/restart-hub": _post_restart_hub_action,
    "/rename-session": _post_rename_session_action,
    "/settings": _post_settings_action,
    "/pick-workspace": _post_pick_workspace_action,
    "/start-session-draft": _post_start_session_draft_action,
    "/session-messages-changed": "_post_session_messages_changed",
}

class Handler(BaseHTTPRequestHandler):
    _GET_ROUTE_HANDLERS = _GET_ROUTE_HANDLERS
    _POST_ROUTE_HANDLERS = _POST_ROUTE_HANDLERS

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, page):
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

    def _dispatch_route(self, parsed, route_map: dict[str, str]) -> bool:
        handler_name = route_map.get(parsed.path)
        if not handler_name:
            return False
        if callable(handler_name):
            handler_name(self, parsed, _hub_action_context())
            return True
        getattr(self, handler_name)(parsed)
        return True

    def _get_hub_manifest(self, _parsed):
        settings = load_hub_settings()
        palette = resolve_theme_palette(settings)
        bg = str(palette["dark_bg"])
        body = json.dumps({
            "name": APP_DISPLAY_NAME,
            "short_name": APP_DISPLAY_NAME,
            "display": "standalone",
            "background_color": bg,
            "theme_color": bg,
            "start_url": "/hub-launch-shell.html?target=%2F%3Flaunch_shell%3D1",
            "scope": "/",
            "icons": _pwa_icon_entries(),
        }, ensure_ascii=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_hub_launch_shell(self, _parsed):
        settings = load_hub_settings()
        from backend_core.access.settings import normalize_theme_choice, settings_for_hub_render

        variant = request_view_variant(headers=self.headers, query_string=_parsed.query)
        theme_desktop = normalize_theme_choice(settings.get("theme_desktop", "dark"))
        theme_mobile = normalize_theme_choice(settings.get("theme_mobile", "system"))
        page = (
            HUB_LAUNCH_SHELL_HTML
            .replace("__THEME_DESKTOP__", theme_desktop)
            .replace("__THEME_MOBILE__", theme_mobile)
            .replace("__VIEW_VARIANT__", variant)
        )
        page = page.replace(
            "__SYSTEM_LIGHT_FG__",
            str(resolve_theme_palette({"theme": "light"})["light_fg"]),
        )
        render_settings = settings_for_hub_render(settings, variant="desktop")
        page = apply_font_tokens(page, settings=render_settings)
        self._send_html(200, apply_color_tokens(page, settings=render_settings))

    def _get_sessions(self, _parsed):
        query = active_session_records_query(hub)
        active_map = query.records
        warnings = list(query.warnings.values())
        active = []
        for record in active_map.values():
            workspace = str(record.get("workspace") or "").strip()
            chat_port = workspace_chat_port(workspace) if workspace else 0
            active.append({
                "name": record["name"],
                "chat_port": chat_port,
                "latest_message_sender": record["latest_message_sender"],
                "latest_message_preview": record["latest_message_preview"],
                "latest_message_revision": record["latest_message_revision"],
            })
        if query.state == "unhealthy":
            archived = []
        else:
            archived = [
                {
                    "name": record["name"],
                    "chat_port": workspace_chat_port(record["workspace"]) if record.get("workspace") else 0,
                    "latest_message_sender": record["latest_message_sender"],
                    "latest_message_preview": record["latest_message_preview"],
                    "latest_message_revision": record["latest_message_revision"],
                }
                for record in archived_session_records(query.non_archived_names).values()
            ]
        self._send_json(200, {
            "active_sessions": active,
            "archived_sessions": archived,
            "warning_sessions": warnings,
            "tmux_state": query.state,
            "tmux_detail": query.detail,
        })

    def _get_session_messages_events(self, _parsed):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        after_seq = 0
        try:
            while True:
                seq = hub.wait_for_session_messages_changed(after_seq, timeout=15.0)
                if seq is None:
                    self.wfile.write(b": keepalive\n\n")
                else:
                    after_seq = seq
                    self.wfile.write(f"event: messages\ndata: {seq}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            logging.exception("Hub session messages event stream failed")

    def _post_session_messages_changed(self, _parsed):
        client_host = str(self.client_address[0] or "").strip()
        if client_host not in {"127.0.0.1", "::1"}:
            self._send_json(403, {"ok": False, "error": "loopback only"})
            return
        hub.publish_session_messages_changed()
        self.send_response(204)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()



    def _get_home(self, _parsed):
        variant = request_view_variant(headers=self.headers, query_string=_parsed.query)
        settings = load_hub_settings()
        from backend_core.access.settings import normalize_theme_choice, settings_for_hub_render

        page = HUB_HOME_MOBILE_HTML if variant == "mobile" else HUB_HOME_DESKTOP_HTML
        if variant == "desktop":
            theme_desktop = normalize_theme_choice(settings.get("theme_desktop", "dark"))
            page = page.replace("__THEME_DESKTOP__", theme_desktop)
            page = page.replace("__TEXT_SIZE_PX__", f'{int(settings["text_size"])}px')
        render_settings = settings_for_hub_render(settings, variant=variant)
        page = apply_font_tokens(page, settings=render_settings)
        self._send_html(200, apply_color_tokens(page, settings=render_settings))






    def do_GET(self):
        parsed = urlparse(self.path)
        if _serve_pwa_static(self, parsed.path):
            return
        if self._dispatch_route(parsed, self._GET_ROUTE_HANDLERS):
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if self._dispatch_route(parsed, self._POST_ROUTE_HANDLERS):
            return
        self.send_response(404)
        self.end_headers()


def main(argv: list[str] | None = None) -> None:
    global _scheme, hub_server

    initialize_from_argv(argv)

    from backend_core.access.settings import local_bind_host, local_bind_scheme

    cert_file = os.environ.get("AGENT_WINDOW_CERT_FILE", "")
    key_file = os.environ.get("AGENT_WINDOW_KEY_FILE", "")
    _scheme = local_bind_scheme(cert_file=cert_file, key_file=key_file)
    if hub is not None:
        hub.hub_scheme = _scheme
    ThreadingHTTPServer.allow_reuse_address = True
    hub_server = ThreadingHTTPServer((local_bind_host(), port), Handler)
    if _scheme == "https":
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        hub_server.socket = ctx.wrap_socket(hub_server.socket, server_side=True)
    print(f"{_scheme}://127.0.0.1:{port}/", flush=True)
    hub_server.serve_forever()
    if restart_pending:
        # Request-handling threads are daemon threads; once this (the
        # only non-daemon) thread falls off the end of the script, the
        # interpreter kills every remaining daemon thread immediately.
        # A restart in progress needs those threads to finish spawning
        # the replacement and sending this response first -- bounded by
        # launch_hub_restart's own handoff timeout, so no separate timeout
        # here.
        _restart_release_event.wait()


if __name__ == "__main__":
    main()
