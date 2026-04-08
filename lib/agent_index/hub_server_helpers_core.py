from __future__ import annotations

from pathlib import Path


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
    is_public = (public_host and host_lc == public_host) or host_lc.endswith(".ts.net")
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


def is_public_host(host_header: str, *, resolve_external_origin_fn, hub_port: int) -> bool:
    return bool(resolve_external_origin_fn(host_header, hub_port).get("is_public"))


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


def restarting_page():
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Restarting Hub</title><style>:root{color-scheme:dark}body{margin:0;background:rgb(38,38,36);color:rgb(240,239,235);font-family:'SF Pro Text','Segoe UI',sans-serif;padding:24px}.panel{max-width:680px;margin:0 auto;background:rgb(25,25,24);border:0.5px solid rgba(255,255,255,0.09);border-radius:16px;padding:18px 18px 16px}.eyebrow{color:rgb(156,154,147);font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin:0 0 8px}h1{margin:0 0 10px;font-size:24px}p{margin:0;color:rgb(156,154,147);line-height:1.6}</style></head><body><div class="panel"><div class="eyebrow">multiagent</div><h1>Restarting Hub</h1><p>The Hub server is being replaced. This page will reconnect automatically as soon as the new server is ready.</p></div><script>const started=Date.now();const reconnect=async()=>{try{const res=await fetch(`/sessions?ts=${Date.now()}`,{cache:'no-store'});if(res.ok){window.location.replace('/');return;}}catch(_err){}if(Date.now()-started<15000){window.setTimeout(reconnect,500);}};window.setTimeout(reconnect,700);</script></body></html>"""


def clean_env(*, env_mapping) -> dict:
    env = dict(env_mapping)
    env["MULTIAGENT_AGENT_NAME"] = "user"
    return env


def launch_hub_restart(
    *,
    script_path,
    port: int,
    repo_root,
    clean_env_fn,
    subprocess_module,
    sys_module,
    hub_server_getter,
    threading_module,
    time_module,
) -> bool:
    restart_helper = (
        "import os, socket, subprocess, sys, time\n"
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
        "env = os.environ.copy()\n"
        "env['MULTIAGENT_AGENT_NAME'] = 'user'\n"
        "subprocess.Popen(\n"
        "    ['bash', script_path, '--hub', '--hub-port', str(port), '--no-open'],\n"
        "    cwd=repo_root,\n"
        "    env=env,\n"
        "    stdin=subprocess.DEVNULL,\n"
        "    stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL,\n"
        "    start_new_session=True,\n"
        "    close_fds=True,\n"
        ")\n"
    )
    subprocess_module.Popen(
        [sys_module.executable, "-c", restart_helper, str(script_path), str(port), str(repo_root)],
        cwd=repo_root,
        env=clean_env_fn(),
        stdin=subprocess_module.DEVNULL,
        stdout=subprocess_module.DEVNULL,
        stderr=subprocess_module.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )

    def worker():
        try:
            time_module.sleep(0.15)
            server = hub_server_getter()
            if server is not None:
                server.shutdown()
                server.server_close()
        finally:
            pass

    threading_module.Thread(target=worker, daemon=True).start()
    return True


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


def icon_data_uri(filename: str, *, repo_root: Path, agent_icons_dir: str, base64_module) -> str:
    try:
        icon_file = repo_root / agent_icons_dir / filename
        if not icon_file.is_file():
            if filename == "grok.svg":
                fallback_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 5h9a4 4 0 0 1 4 4v10"/><path d="m6 19 12-14"/><path d="M9 19h9"/></svg>"""
                return "data:image/svg+xml;base64," + base64_module.b64encode(fallback_svg.encode("utf-8")).decode("ascii")
            return ""
        return "data:image/svg+xml;base64," + base64_module.b64encode(icon_file.read_bytes()).decode("ascii")
    except Exception:
        return ""


def pwa_asset_url(path: str, *, base_path: str = "", bust: bool = False, pwa_asset_version_fn) -> str:
    prefix = base_path.rstrip("/")
    target = path if path.startswith("/") else f"/{path}"
    url = f"{prefix}{target}" if prefix else target
    if not bust:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={pwa_asset_version_fn(target)}"


def pwa_icon_entries(*, base_path: str = "", pwa_asset_url_fn) -> list[dict[str, str]]:
    return [
        {
            "src": pwa_asset_url_fn("/pwa-icon-192.png", base_path=base_path, bust=True),
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": pwa_asset_url_fn("/pwa-icon-512.png", base_path=base_path, bust=True),
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any",
        },
    ]


def pwa_shortcut_entries(*, base_path: str = "", pwa_asset_url_fn) -> list[dict[str, object]]:
    icon_192 = pwa_asset_url_fn("/pwa-icon-192.png", base_path=base_path, bust=True)
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
            "url": pwa_asset_url_fn("/new-session", base_path=base_path),
            "icons": shortcut_icon,
        },
        {
            "name": "Settings",
            "short_name": "Settings",
            "description": "Open Hub settings and notification controls",
            "url": pwa_asset_url_fn("/settings#app-controls", base_path=base_path),
            "icons": shortcut_icon,
        }
    ]


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
def error_page(message, *, html_escape_fn) -> str:
    text = html_escape_fn(message)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Session Hub</title><style>:root{{color-scheme:dark}}body{{margin:0;background:rgb(38,38,36);color:rgb(240,239,235);font-family:'SF Pro Text','Segoe UI',sans-serif;padding:24px}}.panel{{max-width:680px;margin:0 auto;background:rgb(25,25,24);border:0.5px solid rgba(255,255,255,0.09);border-radius:16px;padding:18px 18px 16px}}a{{color:rgb(240,239,235)}}</style></head><body><div class="panel"><h1 style="margin:0 0 10px;font-size:24px">Session Hub</h1><p style="margin:0 0 14px;color:rgb(156,154,147);line-height:1.6">{text}</p><p style="margin:0"><a href=\"/\">Back</a></p></div></body></html>"""


def build_hub_html_pages(
    *,
    template_dir: Path,
    pwa_hub_manifest_url: str,
    pwa_icon_192_url: str,
    pwa_apple_touch_icon_url: str,
    hub_header_css: str,
    hub_header_html: str,
    hub_header_js: str,
    new_session_max_per_agent: int,
    hub_icon_uris: dict[str, str],
) -> dict[str, str]:
    hub_home_html = (template_dir / "hub_home_template.html").read_text()
    hub_home_html = (
        hub_home_html
        .replace("__HUB_MANIFEST_URL__", pwa_hub_manifest_url)
        .replace("__PWA_ICON_192_URL__", pwa_icon_192_url)
        .replace("__APPLE_TOUCH_ICON_URL__", pwa_apple_touch_icon_url)
        .replace("__HUB_HEADER_CSS__", hub_header_css)
        .replace("__HUB_HEADER_HTML__", hub_header_html)
        .replace("__HUB_HEADER_JS__", hub_header_js)
    )
    hub_new_session_html = (template_dir / "hub_new_session_template.html").read_text()
    hub_new_session_html = (
        hub_new_session_html
        .replace("__HUB_MANIFEST_URL__", pwa_hub_manifest_url)
        .replace("__PWA_ICON_192_URL__", pwa_icon_192_url)
        .replace("__APPLE_TOUCH_ICON_URL__", pwa_apple_touch_icon_url)
        .replace("__HUB_HEADER_CSS__", hub_header_css)
        .replace("__HUB_HEADER_HTML__", hub_header_html)
        .replace("__HUB_HEADER_JS__", hub_header_js)
        .replace("__NEW_SESSION_MAX_PER_AGENT__", str(new_session_max_per_agent))
        .replace("__CLAUDE_ICON__", hub_icon_uris["claude"])
        .replace("__CODEX_ICON__", hub_icon_uris["codex"])
        .replace("__GEMINI_ICON__", hub_icon_uris["gemini"])
        .replace("__KIMI_ICON__", hub_icon_uris["kimi"])
        .replace("__COPILOT_ICON__", hub_icon_uris["copilot"])
        .replace("__CURSOR_ICON__", hub_icon_uris["cursor"])
        .replace("__GROK_ICON__", hub_icon_uris["grok"])
        .replace("__OPENCODE_ICON__", hub_icon_uris["opencode"])
        .replace("__QWEN_ICON__", hub_icon_uris["qwen"])
        .replace("__AIDER_ICON__", hub_icon_uris["aider"])
    )
    return {
        "hub_home_html": hub_home_html,
        "hub_new_session_html": hub_new_session_html,
    }
