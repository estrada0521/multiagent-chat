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

from multiagent_chat.agent_registry import (
    AGENT_ICONS_DIR,
    ALL_AGENT_NAMES,
    icon_filename_map as _icon_filename_map,
)
from multiagent_chat.hub_core import HubRuntime
from multiagent_chat.ensure_agent_clis import agent_launch_readiness
from multiagent_chat.hub_header_assets import (
    DEFAULT_HUB_HEADER_ACTIONS,
    DEFAULT_HUB_HEADER_PANELS,
    HUB_PAGE_HEADER_CSS,
    HUB_PAGE_HEADER_JS,
    render_hub_page_header,
)
from multiagent_chat.state_core import (
    local_runtime_log_dir,
    load_hub_settings,
    port_is_bindable,
    save_chat_port_override,
    save_hub_settings,
)
from multiagent_chat.hub_settings_view_core import (
    available_chat_font_choices as _available_chat_font_choices_impl,
    hub_settings_html as _hub_settings_html_impl,
    normalized_font_label as _normalized_font_label_impl,
)
from multiagent_chat.color_constants import apply_color_tokens, resolve_theme_palette
from multiagent_chat.hub_server_post_routes_core import (
    post_start_session as _post_start_session_impl,
)
from multiagent_chat.hub_server_helpers_core import (
    build_hub_html_pages as _build_hub_html_pages_impl,
    clean_env as _clean_env_impl,
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
from multiagent_chat.request_view_core import request_view_variant

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
    global archived_session_records, ensure_chat_server
    global wait_for_session_instances, revive_archived_session, kill_repo_session
    global delete_archived_session, host_without_port, PUBLIC_HOST, PUBLIC_HUB_PORT
    global restart_pending, hub_server, _PWA_STATIC_DIR

    if _initialized:
        return

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 4:
        raise SystemExit(
            "usage: python -m multiagent_chat.hub_server <repo_root> <script_path> <port> <tmux_socket>"
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
    _PWA_STATIC_DIR = repo_root / "src" / "multiagent_chat" / "static" / "pwa"

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
_HUB_PAGE_HEADER_CSS = HUB_PAGE_HEADER_CSS
_HUB_PAGE_HEADER_HTML = render_hub_page_header()
_HUB_PAGE_HEADER_JS = HUB_PAGE_HEADER_JS
_HUB_LAUNCH_SHELL_BODY_HTML = (
    '<div class="launch-shell-card">'
    '<span class="launch-shell-spinner" aria-hidden="true"></span>'
    "</div>"
)
HUB_LAUNCH_SHELL_HTML = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="__DARK_BG__">
  <title>Session Hub</title>
  <style>
    :root {{ color-scheme: dark; }}
    html, body {{
      margin: 0;
      min-height: 100%;
      background: __DARK_BG__;
      color: rgb(245, 245, 245);
    }}
    body {{
      display: grid;
      place-items: center;
      padding: 24px;
      font-family: "SF Pro Text", "Segoe UI", sans-serif;
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
      width: 18px;
      height: 18px;
      border-radius: 0;
      background: transparent;
      border: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      box-shadow: none;
    }}
    .launch-shell-spinner {{
      width: 18px;
      height: 18px;
      border-radius: 999px;
      border: 2px solid rgba(255, 255, 255, 0.24);
      border-top-color: rgba(255, 255, 255, 0.92);
      box-sizing: border-box;
      animation: launch-shell-spin 800ms linear infinite;
    }}
    @keyframes launch-shell-spin {{
      to {{ transform: rotate(360deg); }}
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
        if (!requestedRestart || restartRequested) return;
        restartRequested = true;
        try {{
          await fetch("/restart-hub", {{ method: "POST" }});
        }} catch (_err) {{}}
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
      const load = async () => {{
        if (requestedRestart && !restartRequested) {{
          await requestHubRestart();
          await new Promise((resolve) => window.setTimeout(resolve, 120));
        }}
        try {{
          const response = await fetch(target, {{ cache: "no-store" }});
          if (!response.ok) throw new Error(`load failed: ${{response.status}}`);
          const html = await response.text();
          document.open();
          document.write(html);
          document.close();
        }} catch (_err) {{
          window.setTimeout(load, requestedRestart ? 520 : 700);
        }}
      }};
      load();
    }})();
  </script>
</body>
</html>"""

_HUB_SETTINGS_TEMPLATE = (Path(__file__).resolve().parent / "hub_settings_template.html").read_text()
_hub_pages = _build_hub_html_pages_impl(
    template_dir=Path(__file__).resolve().parent,
    pwa_hub_manifest_url=_PWA_HUB_MANIFEST_URL,
    pwa_icon_192_url=_PWA_ICON_192_URL,
    pwa_apple_touch_icon_url=_PWA_APPLE_TOUCH_ICON_URL,
    hub_header_css=_HUB_PAGE_HEADER_CSS,
    hub_header_html=_HUB_PAGE_HEADER_HTML,
    hub_header_js=_HUB_PAGE_HEADER_JS,
    new_session_max_per_agent=NEW_SESSION_MAX_PER_AGENT,
    hub_icon_uris=_HUB_ICON_URIS,
)
HUB_HOME_HTML = _hub_pages["hub_home_html"]
HUB_HOME_DESKTOP_HTML = _hub_pages["hub_home_html_desktop"]
HUB_HOME_MOBILE_HTML = _hub_pages["hub_home_html_mobile"]
HUB_NEW_SESSION_HTML = _hub_pages["hub_new_session_html"]


def _normalized_font_label(name: str) -> str:
    return _normalized_font_label_impl(name)


def available_chat_font_choices():
    return _available_chat_font_choices_impl(
        path_class=Path,
        normalized_font_label_fn=_normalized_font_label,
    )


def _macos_app_exists(app_name: str) -> bool:
    if sys.platform != "darwin" or not shutil.which("osascript"):
        return False
    try:
        result = subprocess.run(
            ["osascript", "-e", f'id of application "{app_name}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def available_external_editor_choices():
    choices: list[tuple[str, str]] = []

    def _append(value: str, label: str) -> None:
        if any(existing == value for existing, _ in choices):
            return
        choices.append((value, label))

    if shutil.which("code") or _macos_app_exists("Visual Studio Code"):
        _append("vscode", "VS Code")
    else:
        _append("vscode", "VS Code")

    if _macos_app_exists("CotEditor"):
        _append("coteditor", "CotEditor")
    else:
        _append("coteditor", "CotEditor")

    if sys.platform == "darwin":
        app_candidates = (
            ("app:Antigravity", "Antigravity", ("Antigravity", "Antigravity Editor")),
            ("app:Cursor", "Cursor", ("Cursor",)),
            ("app:Windsurf", "Windsurf", ("Windsurf",)),
            ("app:Zed", "Zed", ("Zed",)),
            ("app:Sublime Text", "Sublime Text", ("Sublime Text",)),
            ("app:TextMate", "TextMate", ("TextMate",)),
            ("app:BBEdit", "BBEdit", ("BBEdit",)),
            ("app:Nova", "Nova", ("Nova",)),
        )
        for value, label, app_names in app_candidates:
            if any(_macos_app_exists(app_name) for app_name in app_names):
                _append(value, label)

    _append("system", "System Default")
    return choices


def available_markdown_external_editor_choices():
    """Like external editors, plus MarkEdit first when installed (markdown default)."""
    seen: set[str] = set()
    choices: list[tuple[str, str]] = []
    if sys.platform == "darwin" and _macos_app_exists("MarkEdit"):
        choices.append(("markedit", "MarkEdit"))
        seen.add("markedit")
    for value, label in available_external_editor_choices():
        if value in seen:
            continue
        choices.append((value, label))
        seen.add(value)
    return choices


def hub_settings_html(saved=False, variant="desktop"):
    header_html = render_hub_page_header(
        title_href="/",
        title_id="hubPageTitleLink",
        title_aria_label="Hub",
        title_alt="Hub",
        actions_html=DEFAULT_HUB_HEADER_ACTIONS,
        panels_html=DEFAULT_HUB_HEADER_PANELS,
    )
    return _hub_settings_html_impl(
        saved=bool(saved),
        load_hub_settings_fn=hub.load_hub_settings,
        available_chat_font_choices_fn=available_chat_font_choices,
        available_external_editor_choices_fn=available_external_editor_choices,
        available_markdown_external_editor_choices_fn=available_markdown_external_editor_choices,
        settings_template=_HUB_SETTINGS_TEMPLATE,
        pwa_hub_manifest_url=_PWA_HUB_MANIFEST_URL,
        pwa_icon_192_url=_PWA_ICON_192_URL,
        pwa_apple_touch_icon_url=_PWA_APPLE_TOUCH_ICON_URL,
        hub_header_css=_HUB_PAGE_HEADER_CSS,
        hub_header_html=header_html,
        hub_header_js=_HUB_PAGE_HEADER_JS,
        view_variant=variant,
    )

def hub_new_session_html(variant="desktop"):
    is_mobile = (variant == "mobile")
    try:
        current_settings = hub.load_hub_settings()
    except Exception:
        current_settings = {}
    try:
        message_text_size = int(current_settings.get("message_text_size", 13) or 13)
    except Exception:
        message_text_size = 13
    header_html = render_hub_page_header(
        title_href="/",
        title_id="hubPageTitleLink",
        title_aria_label="Hub",
        title_alt="Hub",
        actions_html=DEFAULT_HUB_HEADER_ACTIONS,
        panels_html=DEFAULT_HUB_HEADER_PANELS,
    )
    page = (
        _hub_pages["hub_new_session_html"]
        .replace("__HUB_HEADER_CSS__", _HUB_PAGE_HEADER_CSS)
        .replace("__HUB_HEADER_HTML__", header_html)
        .replace("__HUB_HEADER_JS__", _HUB_PAGE_HEADER_JS)
        .replace("__VIEW_VARIANT__", "mobile" if is_mobile else "desktop")
        .replace("__MESSAGE_TEXT_SIZE__", str(message_text_size))
    )
    return apply_color_tokens(page, settings=current_settings)

_PENDING_LAUNCH_FILE = ".pending-launch.json"

def error_page(message):
    try:
        settings = load_hub_settings()
    except Exception:
        settings = {}
    return apply_color_tokens(_error_page_impl(message, html_escape_fn=html.escape), settings=settings)


def _session_logs_dir(session_name: str) -> Path:
    return local_runtime_log_dir(repo_root) / str(session_name or "").strip()


def _pending_launch_path(session_name: str) -> Path:
    return _session_logs_dir(session_name) / _PENDING_LAUNCH_FILE


def _read_json_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_pending_launch(session_name: str) -> dict:
    path = _pending_launch_path(session_name)
    if not path.is_file():
        return {}
    data = _read_json_file(path)
    if not data:
        return {}
    pending_session = str(data.get("session") or "").strip()
    if pending_session and pending_session != session_name:
        return {}
    return data


def _is_pending_launch_session(session_name: str) -> bool:
    return bool(_read_pending_launch(session_name))


def _pending_session_record(session_name: str) -> dict | None:
    pending_cfg = _read_pending_launch(session_name)
    if not pending_cfg:
        return None
    workspace = str(pending_cfg.get("workspace") or "").strip()
    if not workspace:
        return None
    targets = [
        str(item).strip()
        for item in (pending_cfg.get("available_agents") or ALL_AGENT_NAMES)
        if str(item).strip()
    ]
    return _build_pending_session_record(
        session_name,
        workspace,
        targets,
        created_at=str(pending_cfg.get("created_at") or ""),
        updated_at=str(pending_cfg.get("updated_at") or ""),
    )


def _resolve_session_chat_target(session_name: str) -> dict:
    query = active_session_records_query()
    if session_name in query.records:
        ok, chat_port, detail = ensure_chat_server(session_name)
        if not ok:
            return {"status": "error", "detail": detail}
        return {
            "status": "ok",
            "chat_port": chat_port,
            "session_record": query.records.get(session_name, {}),
        }

    pending_record = _pending_session_record(session_name)
    if pending_record is not None:
        workspace = str(pending_record.get("workspace") or "").strip()
        targets = [str(item).strip() for item in (pending_record.get("agents") or []) if str(item).strip()]
        ok, chat_port, detail = _ensure_pending_chat_server(session_name, workspace, targets)
        if not ok:
            return {"status": "error", "detail": detail}
        return {
            "status": "ok",
            "chat_port": chat_port,
            "session_record": pending_record,
        }

    if query.state == "unhealthy":
        return {"status": "unhealthy", "detail": query.detail}
    return {"status": "missing"}


def _format_session_timestamp(epoch: int | None = None) -> str:
    ts = int(epoch or time.time())
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def _unique_session_name_for_workspace(workspace: str) -> str:
    raw_name = Path(workspace).name or "session"
    base = re.sub(r"[^a-zA-Z0-9_.\-]", "-", raw_name).strip(".-")[:64] or "session"
    query = active_session_records_query()
    existing = set(query.records.keys())
    try:
        existing.update(archived_session_records(existing).keys())
    except Exception:
        pass
    candidate = base
    suffix = 2
    while candidate in existing or _session_logs_dir(candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base[:max(1, 64 - len(suffix_text))]}{suffix_text}"
        suffix += 1
    return candidate


def _write_pending_session_files(session_name: str, workspace: str, agents: list[str]) -> dict:
    session_dir = _session_logs_dir(session_name)
    session_dir.mkdir(parents=True, exist_ok=True)
    index_path = session_dir / ".agent-index.jsonl"
    index_path.touch(exist_ok=True)
    meta_path = session_dir / ".meta"
    existing_meta = _read_json_file(meta_path) if meta_path.is_file() else {}
    created_at = str(existing_meta.get("created_at") or "").strip() or _format_session_timestamp()
    updated_at = _format_session_timestamp()
    meta_payload = {
        "session": session_name,
        "workspace": workspace,
        "agents": list(agents or []),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending_payload = {
        "session": session_name,
        "workspace": workspace,
        "available_agents": list(agents or []),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    _pending_launch_path(session_name).write_text(
        json.dumps(pending_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "session_dir": session_dir,
        "index_path": index_path,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _build_pending_session_record(session_name: str, workspace: str, agents: list[str], *, created_at: str = "", updated_at: str = "") -> dict:
    session_dir = _session_logs_dir(session_name)
    index_path = session_dir / ".agent-index.jsonl"
    now_epoch = int(time.time())
    record = hub._build_session_record(
        name=session_name,
        workspace=workspace,
        agents=list(agents or []),
        status="pending",
        attached=0,
        dead_panes=0,
        created_epoch=now_epoch,
        created_at=created_at or _format_session_timestamp(now_epoch),
        updated_epoch=now_epoch,
        updated_at=updated_at or _format_session_timestamp(now_epoch),
        preferred_index_path=index_path,
    )
    record["launch_pending"] = True
    record["running_agents"] = []
    record["is_running"] = False
    return record


def _pending_chat_server_matches(session_name: str, chat_port: int) -> bool:
    state = hub.chat_server_state(chat_port)
    if not state:
        return False
    return str(state.get("session") or "").strip() == session_name


def _running_agents_from_session_state(session_state: dict | None) -> list[str]:
    if not isinstance(session_state, dict):
        return []
    statuses = session_state.get("statuses")
    if not isinstance(statuses, dict):
        return []
    running: list[str] = []
    for agent, status in statuses.items():
        agent_name = str(agent or "").strip()
        if not agent_name:
            continue
        if str(status or "").strip().lower() == "running":
            running.append(agent_name)
    return running


def _ensure_pending_chat_server(session_name: str, workspace: str, targets: list[str]) -> tuple[bool, int, str]:
    lock = hub._get_launch_lock(session_name)
    with lock:
        chat_port = hub.chat_port_for_session(session_name)
        if hub.chat_ready(chat_port) and _pending_chat_server_matches(session_name, chat_port):
            return True, chat_port, ""
        if hub.chat_ready(chat_port):
            stop_ok, stop_detail = hub.stop_chat_server(session_name)
            if not stop_ok:
                return False, chat_port, stop_detail
        if not port_is_bindable(chat_port):
            for candidate in range(chat_port, chat_port + 10):
                if hub.chat_ready(candidate) and _pending_chat_server_matches(session_name, candidate):
                    save_chat_port_override(repo_root, session_name, candidate)
                    return True, candidate, ""
                if port_is_bindable(candidate):
                    save_chat_port_override(repo_root, session_name, candidate)
                    chat_port = candidate
                    break
        session_dir = hub._chat_launch_session_dir(session_name, workspace, "")
        index_path = session_dir / ".agent-index.jsonl"
        index_path.touch(exist_ok=True)
        env = hub._chat_launch_env()
        env["MULTIAGENT_INDEX_PATH"] = str(index_path)
        env["SESSION_IS_ACTIVE"] = "0"
        try:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "multiagent_chat.chat_server",
                    str(index_path),
                    "2000",
                    "",
                    session_name,
                    "1",
                    str(chat_port),
                    str(hub.agent_send_path),
                    workspace,
                    str(session_dir.parent),
                    ",".join(targets or []),
                    hub.tmux_socket,
                    str(port),
                ],
                cwd=workspace or str(repo_root),
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            return False, chat_port, str(exc)
        for _ in range(80):
            if hub.chat_ready(chat_port) and _pending_chat_server_matches(session_name, chat_port):
                return True, chat_port, ""
            time.sleep(0.05)
        return False, chat_port, "pending chat server did not become ready"


def _delete_pending_draft_session(session_name: str) -> tuple[bool, str]:
    try:
        stop_ok, stop_detail = hub.stop_chat_server(session_name)
    except Exception as exc:
        stop_ok, stop_detail = False, str(exc)
    if not stop_ok:
        chat_port = hub.chat_port_for_session(session_name)
        if hub.chat_ready(chat_port):
            return False, stop_detail or "pending chat server cleanup failed"
    ok, detail = delete_archived_session(session_name)
    if not ok:
        return False, detail
    return True, ""

_GET_ROUTE_HANDLERS = {
    "/hub.webmanifest": "_get_hub_manifest",
    "/hub-launch-shell.html": "_get_hub_launch_shell",
    "/sessions": "_get_sessions",
    "/notify-sound": "_get_notify_sound",
    "/open-session": "_get_open_session",
    "/revive-session": "_get_revive_session",
    "/kill-session": "_get_kill_session",
    "/delete-archived-session": "_get_delete_archived_session",
    "/": "_get_home",
    "/index.html": "_get_home",
    "/settings": "_get_settings",
    "/new-session": "_get_new_session",
    "/check-session-name": "_get_check_session_name",
    "/dirs": "_get_dirs",
}

_POST_ROUTE_HANDLERS = {
    "/restart-hub": "_post_restart_hub",
    "/settings": "_post_settings",
    "/pick-workspace": "_post_pick_workspace",
    "/mkdir": "_post_mkdir",
    "/start-session-draft": "_post_start_session_draft",
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
        getattr(self, handler_name)(parsed)
        return True

    def _get_hub_manifest(self, _parsed):
        try:
            settings = load_hub_settings()
        except Exception:
            settings = {}
        palette = resolve_theme_palette(settings)
        bg = str(palette["dark_bg"])
        body = json.dumps({
            "name": "Session Hub",
            "short_name": "Hub",
            "display": "standalone",
            "background_color": bg,
            "theme_color": bg,
            "start_url": "/hub-launch-shell.html?target=%2F%3Flaunch_shell%3D1",
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

    def _get_hub_launch_shell(self, _parsed):
        try:
            settings = load_hub_settings()
        except Exception:
            settings = {}
        self._send_html(200, apply_color_tokens(HUB_LAUNCH_SHELL_HTML, settings=settings))

    def _get_sessions(self, _parsed):
        query = active_session_records_query()
        active_map = query.records
        active = []
        for record in active_map.values():
            session_record = dict(record)
            running_agents: list[str] = []
            try:
                chat_port = int(session_record.get("chat_port") or 0)
            except Exception:
                chat_port = 0
            if chat_port > 0 and hub.chat_ready(chat_port):
                running_agents = _running_agents_from_session_state(hub.chat_server_state(chat_port))
            session_record["running_agents"] = running_agents
            session_record["is_running"] = bool(running_agents)
            active.append(session_record)
        if query.state == "unhealthy":
            # Suppress archived to avoid duplicates from partial scan
            archived = []
        else:
            archived = list(archived_session_records(active_map.keys()).values())
        pending_active = []
        remaining_archived = []
        for record in archived:
            session_name = str(record.get("name") or "").strip()
            if session_name and _is_pending_launch_session(session_name):
                pending_record = dict(record)
                pending_record["launch_pending"] = True
                pending_record["status"] = "pending"
                pending_record["running_agents"] = []
                pending_record["is_running"] = False
                pending_active.append(pending_record)
            else:
                remaining_archived.append(record)
        if pending_active:
            active = pending_active + active
        archived = remaining_archived
        try:
            hub_settings = load_hub_settings()
        except Exception:
            hub_settings = {}
        bold_mode_desktop = bool(hub_settings.get("bold_mode_desktop", False))
        self._send_json(200, {
            "sessions": active,
            "active_sessions": active,
            "archived_sessions": archived,
            "tmux_state": query.state,
            "tmux_detail": query.detail,
            "bold_mode_desktop": bold_mode_desktop,
        })

    def _get_notify_sound(self, parsed):
        qs = parse_qs(parsed.query)
        name = (qs.get("name", [""])[0] or "").strip()
        if not name:
            name = "mictest.ogg"
        sounds_dir = repo_root / "assets" / "sounds"
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
        if not session_name:
            if fmt == "json":
                self._send_json(404, {"ok": False, "error": "Session not found"})
            else:
                self._send_html(404, error_page("That session is not available in this repo."))
            return
        resolved = _resolve_session_chat_target(session_name)
        if resolved["status"] == "unhealthy":
            self._send_unhealthy(fmt, resolved.get("detail", ""))
            return
        if resolved["status"] == "missing":
            if fmt == "json":
                self._send_json(404, {"ok": False, "error": "Session not found"})
            else:
                self._send_html(404, error_page("That session is not available in this repo."))
            return
        if resolved["status"] != "ok":
            detail = str(resolved.get("detail") or "")
            if fmt == "json":
                self._send_json(500, {"ok": False, "error": detail})
            else:
                self._send_html(500, error_page(f"Failed to start chat for {session_name}: {detail}"))
            return
        chat_port = int(resolved.get("chat_port") or 0)
        location = format_session_chat_url(
            self.headers.get("Host", "127.0.0.1"),
            session_name,
            chat_port,
            f"/?follow=1&ts={int(time.time() * 1000)}",
        )
        if fmt == "json":
            self._send_json(200, {"ok": True, "chat_url": location, "session_record": resolved.get("session_record", {})})
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
        fmt = qs.get("format", [""])[0]
        if not session_name:
            if fmt == "json":
                self._send_json(404, {"ok": False, "error": "Session not found"})
            else:
                self._send_html(404, error_page("That active session is not available in this repo."))
            return
        if _is_pending_launch_session(session_name):
            ok, detail = _delete_pending_draft_session(session_name)
            if not ok:
                if fmt == "json":
                    self._send_json(500, {"ok": False, "error": detail or f"Failed to delete draft session {session_name}"})
                else:
                    self._send_html(500, error_page(f"Failed to delete draft session {session_name}: {detail}"))
                return
            if fmt == "json":
                self._send_json(200, {"ok": True, "session": session_name, "action": "deleted", "pending": True})
            else:
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
            return
        ok, detail = kill_repo_session(session_name)
        if not ok:
            if fmt == "json":
                self._send_json(500, {"ok": False, "error": detail or f"Failed to kill {session_name}"})
            else:
                self._send_html(500, error_page(f"Failed to kill {session_name}: {detail}"))
            return
        if detail:
            logging.warning("Session %s terminated but cleanup incomplete: %s", session_name, detail)
        if fmt == "json":
            self._send_json(200, {"ok": True, "session": session_name, "action": "killed"})
        else:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def _get_delete_archived_session(self, parsed):
        qs = parse_qs(parsed.query)
        session_name = (qs.get("session", [""])[0] or "").strip()
        fmt = qs.get("format", [""])[0]
        if not session_name:
            if fmt == "json":
                self._send_json(404, {"ok": False, "error": "Session not found"})
            else:
                self._send_html(404, error_page("That archived session is not available in this repo."))
            return
        if _is_pending_launch_session(session_name):
            ok, detail = _delete_pending_draft_session(session_name)
            if not ok:
                if fmt == "json":
                    self._send_json(500, {"ok": False, "error": detail or f"Failed to delete draft session {session_name}"})
                else:
                    self._send_html(500, error_page(f"Failed to delete draft session {session_name}: {detail}"))
                return
            if fmt == "json":
                self._send_json(200, {"ok": True, "session": session_name, "action": "deleted", "pending": True})
            else:
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
            return
        ok, detail = delete_archived_session(session_name)
        if not ok:
            if fmt == "json":
                self._send_json(500, {"ok": False, "error": detail or f"Failed to delete archived session {session_name}"})
            else:
                self._send_html(500, error_page(f"Failed to delete archived session {session_name}: {detail}"))
            return
        if fmt == "json":
            self._send_json(200, {"ok": True, "session": session_name, "action": "deleted"})
        else:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def _get_home(self, _parsed):
        variant = request_view_variant(headers=self.headers, query_string=_parsed.query)
        try:
            settings = load_hub_settings()
        except Exception:
            settings = {}
        page = HUB_HOME_MOBILE_HTML if variant == "mobile" else HUB_HOME_DESKTOP_HTML
        self._send_html(200, apply_color_tokens(page, settings=settings))

    def _get_settings(self, parsed):
        variant = request_view_variant(headers=self.headers, query_string=parsed.query)
        saved = (parse_qs(parsed.query).get("saved", ["0"])[0] == "1")
        self._send_html(200, hub_settings_html(saved=saved, variant=variant))

    def _get_new_session(self, parsed):
        variant = request_view_variant(headers=self.headers, query_string=parsed.query)
        self._send_html(200, hub_new_session_html(variant=variant))

    def _get_check_session_name(self, parsed):
        qs = parse_qs(parsed.query)
        workspace = (qs.get("workspace", [""])[0] or "").strip()
        if not workspace:
            self._send_json(400, {"ok": False, "error": "workspace required"})
            return
        try:
            resolved = str(Path(workspace).expanduser().resolve())
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        original = re.sub(r"[^a-zA-Z0-9_.\-]", "-", Path(resolved).name or "session").strip(".-")[:64] or "session"
        proposed = _unique_session_name_for_workspace(resolved)
        self._send_json(200, {"ok": True, "name": proposed, "original": original, "conflict": proposed != original})

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

    def _post_restart_hub(self, _parsed):
        queue_hub_restart()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def _post_settings(self, parsed):
        data = self._read_form()
        save_hub_settings(data)
        qs = parse_qs(parsed.query)
        if qs.get("embed", ["0"])[0] == "1":
            self._redirect("/settings?embed=1&saved=1")
            return
        self._redirect("/settings?saved=1")

    def _post_pick_workspace(self, _parsed):
        if sys.platform != "darwin" or not shutil.which("osascript"):
            self._send_json(501, {"ok": False, "error": "native workspace picker is unavailable on this device"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length)
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
            self._send_json(504, {"ok": False, "error": "workspace picker timed out"})
            return
        stderr_text = str(proc.stderr or "").strip()
        if proc.returncode != 0:
            if "-128" in stderr_text or "User canceled" in stderr_text:
                self._send_json(200, {"ok": False, "canceled": True})
                return
            self._send_json(500, {"ok": False, "error": stderr_text or "workspace picker failed"})
            return
        chosen = str(proc.stdout or "").strip()
        if not chosen:
            self._send_json(500, {"ok": False, "error": "workspace picker returned an empty path"})
            return
        try:
            resolved = Path(chosen).expanduser().resolve()
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
            return
        if not resolved.is_dir():
            self._send_json(400, {"ok": False, "error": f"Invalid workspace: {resolved}"})
            return
        self._send_json(200, {"ok": True, "path": str(resolved)})

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

    def _post_start_session_draft(self, _parsed):
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
        workspace = str(data.get("workspace") or "").strip()
        if not workspace:
            self._send_json(400, {"ok": False, "error": "workspace required"})
            return
        try:
            resolved_workspace = str(Path(workspace).expanduser().resolve())
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        if not Path(resolved_workspace).is_dir():
            self._send_json(400, {"ok": False, "error": f"Invalid workspace: {resolved_workspace}"})
            return
        override_name = re.sub(r"[^a-zA-Z0-9_.\-]", "-", str(data.get("session_name") or "")).strip(".-")[:64]
        if override_name:
            query = active_session_records_query()
            existing = set(query.records.keys())
            try:
                existing.update(archived_session_records(existing).keys())
            except Exception:
                pass
            if override_name in existing or _session_logs_dir(override_name).exists():
                self._send_json(409, {"ok": False, "error": f"セッション名 '{override_name}' は既に使用されています"})
                return
            session_name = override_name
        else:
            session_name = _unique_session_name_for_workspace(resolved_workspace)
        try:
            session_state = _write_pending_session_files(session_name, resolved_workspace, ALL_AGENT_NAMES)
            ok, chat_port, detail = _ensure_pending_chat_server(session_name, resolved_workspace, ALL_AGENT_NAMES)
            if not ok:
                self._send_json(500, {"ok": False, "error": detail})
                return
            record = _build_pending_session_record(
                session_name,
                resolved_workspace,
                ALL_AGENT_NAMES,
                created_at=session_state.get("created_at", ""),
                updated_at=session_state.get("updated_at", ""),
            )
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
            return
        draft_query = f"follow=1&compose=1&ts={int(time.time() * 1000)}"
        draft_chat_url = f"/session/{url_quote(session_name, safe='')}/?{draft_query}"
        self._send_json(
            200,
            {
                "ok": True,
                "session": session_name,
                "chat_url": draft_chat_url,
                "session_record": record,
            },
        )

    def _post_start_session(self, _parsed):
        try:
            _post_start_session_impl(
                self,
                all_agent_names=ALL_AGENT_NAMES,
                new_session_max_per_agent=NEW_SESSION_MAX_PER_AGENT,
                script_path=script_path,
                wait_for_session_instances_fn=wait_for_session_instances,
                ensure_chat_server_fn=ensure_chat_server,
                active_session_records_query_fn=active_session_records_query,
                agent_launch_readiness_fn=agent_launch_readiness,
            )
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})

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
        resolved = _resolve_session_chat_target(session_name)
        if resolved["status"] == "unhealthy":
            self._send_unhealthy("plain", str(resolved.get("detail") or ""))
            return
        if resolved["status"] == "missing":
            self._send_html(404, error_page("That session is not available in this repo."))
            return
        if resolved["status"] != "ok":
            detail = str(resolved.get("detail") or "")
            self._send_html(500, error_page(f"Failed to start chat for {session_name}: {detail}"))
            return
        chat_port = int(resolved.get("chat_port") or 0)
        body = None
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            body = self.rfile.read(length)
        query = f"?{parsed.query}" if parsed.query else ""
        chat_scheme = _scheme or "http"
        upstream = f"{chat_scheme}://127.0.0.1:{chat_port}{suffix}{query}"
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
        ctx = ssl._create_unverified_context() if chat_scheme == "https" else None
        try:
            # multiagent-public-edge のプロキシと同様 30s（セッション・リロード時の並列転送向け）
            resp = urlopen(req, context=ctx, timeout=30) if ctx is not None else urlopen(req, timeout=30)
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
