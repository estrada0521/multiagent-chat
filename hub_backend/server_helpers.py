from __future__ import annotations

import html
import json
import os
import re
import subprocess
import threading
from pathlib import Path

from hub_backend.branding import APP_DISPLAY_NAME
from appearance.colors import DARK_BG

_HUB_INCLUDE_RE = re.compile(r"__HUB_INCLUDE:([A-Za-z0-9_./-]+)__")


def _expand_hub_template_includes(text: str, template_dirs: Path | list[Path]) -> str:
    dirs = [template_dirs] if isinstance(template_dirs, Path) else list(template_dirs)
    roots = [d.resolve() for d in dirs]

    def _replace(match: re.Match[str]) -> str:
        rel = match.group(1)
        for root in roots:
            path = (root / rel).resolve()
            if root not in path.parents and path != root:
                continue
            if path.is_file():
                return path.read_text()
        raise FileNotFoundError(f"Hub template include not found in {roots}: {rel}")

    return _HUB_INCLUDE_RE.sub(_replace, text)


def apply_hub_page_branding(html: str, *, page_title: str) -> str:
    return (
        html
        .replace("__APP_DISPLAY_NAME__", APP_DISPLAY_NAME)
        .replace("__PAGE_TITLE__", page_title)
    )


def resolve_external_origin(
    host_header: str,
    local_port: int,
    *,
    host_without_port_fn,
    public_host: str,
    public_hub_port: int,
    hub_port: int,
    scheme: str,
) -> dict[str, object]:
    host = host_without_port_fn(host_header or "127.0.0.1")
    host_lc = host.lower()
    is_public = bool(public_host and host_lc == public_host)
    if is_public and local_port == hub_port:
        external_port = public_hub_port
    else:
        external_port = local_port
    default_port = 443 if scheme == "https" else 80
    authority = host if external_port == default_port else f"{host}:{external_port}"
    return {
        "origin": f"{scheme}://{authority}",
        "host": host,
        "is_public": bool(is_public),
        "external_port": external_port,
    }


def format_external_url(host_header: str, local_port: int, path: str, *, resolve_external_origin_fn) -> str:
    resolved = resolve_external_origin_fn(host_header, local_port)
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{resolved['origin']}{suffix}"


def format_session_chat_url(
    host_header: str,
    session_name: str,
    local_port: int,
    path: str,
    *,
    resolve_external_origin_fn,
    format_external_url_fn,
    url_quote_fn,
) -> str:
    resolved = resolve_external_origin_fn(host_header, local_port)
    if resolved["is_public"]:
        base = f"{resolved['origin']}/session/{url_quote_fn(session_name)}"
        return f"{base}{path}"
    return format_external_url_fn(host_header, local_port, path)


PROCESS_HANDOFF_TIMEOUT_SEC = 8.0


def clean_env() -> dict:
    env = dict(os.environ)
    env["AGENT_WINDOW_AGENT_NAME"] = "user"
    return env


def launch_hub_restart(
    *,
    script_path,
    port: int,
    repo_root,
    clean_env_fn,
    hub_server_getter,
    ready_timeout: float = PROCESS_HANDOFF_TIMEOUT_SEC,
) -> bool:
    """Restart the Hub process and block until agent-index reports ready.

    The actual shutdown/respawn runs on a background daemon thread. This
    is required, not just a style choice: ThreadingHTTPServer's own
    request-handling threads are daemon threads here, so if *this*
    thread (one of them) called server.shutdown() directly, the instant
    serve_forever() returns, main() falls off the end of the script and
    the interpreter kills every remaining daemon thread outright --
    including the one still trying to spawn the replacement or send this
    response. Doing the work on a second daemon thread and just blocking
    this one on an Event sidesteps that; main() additionally holds the
    process open after serve_forever() returns until release_restart_hold()
    confirms the response was actually sent (see hub_server.py).
    """
    done = threading.Event()
    result: dict[str, bool] = {"ok": False}

    def worker() -> None:
        try:
            server = hub_server_getter()
            if server is not None:
                server.shutdown()
                server.server_close()
            env = clean_env_fn()
            env["AGENT_WINDOW_AGENT_NAME"] = "user"
            completed = subprocess.run(
                ["bash", str(script_path), "--hub-port", str(port)],
                cwd=repo_root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=ready_timeout,
            )
            result["ok"] = completed.returncode == 0
        except subprocess.TimeoutExpired:
            result["ok"] = False
        finally:
            done.set()

    threading.Thread(target=worker, daemon=True).start()
    done.wait()
    return result["ok"]


def pwa_asset_version(
    path: str,
    *,
    pwa_asset_version_overrides: dict[str, str],
    pwa_static_routes: dict[str, tuple[str, str, str]],
    pwa_static_dir: Path,
    fallback_file: str,
) -> str:
    if path in pwa_asset_version_overrides:
        return pwa_asset_version_overrides[path]
    route = pwa_static_routes.get(path)
    if not route:
        return str(int(Path(fallback_file).stat().st_mtime_ns))
    filename = route[0]
    try:
        return str(int((pwa_static_dir / filename).stat().st_mtime_ns))
    except OSError:
        return str(int(Path(fallback_file).stat().st_mtime_ns))


def pwa_asset_url(path: str, *, base_path: str = "", bust: bool = False, pwa_asset_version_fn) -> str:
    prefix = base_path.rstrip("/")
    target = path if path.startswith("/") else f"/{path}"
    url = f"{prefix}{target}" if prefix else target
    if not bust:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={pwa_asset_version_fn(target)}"


def serve_pwa_static(handler, path: str, *, pwa_static_routes, pwa_static_dir: Path) -> bool:
    route = pwa_static_routes.get(path)
    if not route:
        return False
    filename, content_type, cache_control = route
    asset_path = pwa_static_dir / filename
    if not asset_path.exists():
        handler.send_response(404)
        handler.end_headers()
        return True
    body = asset_path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", cache_control)
    handler.end_headers()
    handler.wfile.write(body)
    return True


def error_page(message) -> str:
    text = str(message or "").strip()
    escaped = html.escape(text)
    payload = json.dumps(text)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Hub</title><style>:root{{color-scheme:dark;--fg:rgb(180, 180, 180);--muted:rgb(128, 128, 128)}}html,body{{margin:0;min-height:100%;background:{DARK_BG};color:var(--fg);font-family:var(--font-main)}}body{{display:grid;place-items:center;padding:24px}}.note{{font-size:13px;line-height:1.5;color:var(--muted)}}</style></head><body><div class="note">{escaped}</div><p><a href="/">Back to Hub</a></p><script>(()=>{{const message={payload};if(window.parent!==window){{try{{window.parent.postMessage({{type:"hub-session-error",message}},window.location.origin);}}catch(_err){{}}return;}}try{{sessionStorage.setItem("agent_window_hub_pending_error",message);}}catch(_err){{}}window.location.replace("/");}})();</script><noscript><p><a href="/">Back to Hub</a></p></noscript></body></html>"""


def build_hub_html_pages(
    *,
    desktop_template_dir: Path,
    mobile_template_dir: Path,
    shared_template_dir: Path,
    pwa_hub_manifest_url: str,
    pwa_icon_192_url: str,
    pwa_apple_touch_icon_url: str,
    hub_header_css: str,
    hub_header_html: str,
    hub_header_html_mobile: str,
    hub_header_js: str,
) -> dict[str, str]:
    def _render_hub_home_html(own_dir: Path, *, header_html: str) -> str:
        template_path = own_dir / "home.html"
        if not template_path.is_file():
            raise FileNotFoundError(f"Hub home template not found: {template_path}")
        html = _expand_hub_template_includes(template_path.read_text(), [own_dir, shared_template_dir])
        html = (
            html
            .replace("__HUB_MANIFEST_URL__", pwa_hub_manifest_url)
            .replace("__PWA_ICON_192_URL__", pwa_icon_192_url)
            .replace("__APPLE_TOUCH_ICON_URL__", pwa_apple_touch_icon_url)
            .replace("__HUB_HEADER_CSS__", hub_header_css)
            .replace("__HUB_HEADER_HTML__", header_html)
            .replace("__HUB_HEADER_JS__", hub_header_js)
        )
        return apply_hub_page_branding(html, page_title=APP_DISPLAY_NAME)

    hub_home_desktop_html = _render_hub_home_html(desktop_template_dir, header_html=hub_header_html)
    hub_home_mobile_html = _render_hub_home_html(mobile_template_dir, header_html=hub_header_html_mobile)
    return {
        "hub_home_html_desktop": hub_home_desktop_html,
        "hub_home_html_mobile": hub_home_mobile_html,
    }
