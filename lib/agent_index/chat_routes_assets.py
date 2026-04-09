from __future__ import annotations

import json
import random
from pathlib import Path
from urllib.parse import parse_qs

from .request_view_core import request_view_variant


def _send_bytes(
    handler,
    status: int,
    body: bytes,
    *,
    content_type: str,
    cache_control: str = "no-store",
    extra_headers: dict[str, str] | None = None,
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    if cache_control:
        handler.send_header("Cache-Control", cache_control)
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(key, value)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _chat_notification_sound_filenames(sounds_dir: Path) -> list[str]:
    if not sounds_dir.is_dir():
        return []
    names: list[str] = []
    for path in sorted(sounds_dir.glob("notify_*.ogg")):
        if path.is_file():
            names.append(path.name)
    return names


def _default_session_notify_sound_basename(sounds_dir: Path):
    candidates = _chat_notification_sound_filenames(sounds_dir)
    if candidates:
        return random.choice(candidates)
    return None


def _get_app_manifest(handler, _parsed, ctx) -> None:
    base_path = (handler.headers.get("X-Forwarded-Prefix", "") or "").rstrip("/")
    body = json.dumps(
        {
            "name": f"{ctx['session_name']} chat",
            "short_name": ctx["session_name"],
            "display": "standalone",
            "background_color": "rgb(38, 38, 36)",
            "theme_color": "rgb(38, 38, 36)",
            "start_url": ctx["pwa_asset_url_fn"]("/?follow=1", base_path),
            "scope": ctx["pwa_asset_url_fn"]("/", base_path),
            "icons": ctx["pwa_icon_entries_fn"](base_path),
        },
        ensure_ascii=True,
    ).encode("utf-8")
    _send_bytes(
        handler,
        200,
        body,
        content_type="application/manifest+json; charset=utf-8",
    )


def _get_chat_app_js(handler, _parsed, ctx) -> None:
    variant = request_view_variant(headers=handler.headers, query_string=_parsed.query)
    _send_bytes(
        handler,
        200,
        ctx["chat_app_script_asset_fn"](variant).encode("utf-8"),
        content_type="application/javascript; charset=utf-8",
        cache_control="public, max-age=31536000, immutable",
    )


def _get_chat_app_css(handler, _parsed, ctx) -> None:
    variant = request_view_variant(headers=handler.headers, query_string=_parsed.query)
    _send_bytes(
        handler,
        200,
        ctx["chat_main_style_asset_fn"](variant).encode("utf-8"),
        content_type="text/css; charset=utf-8",
        cache_control="public, max-age=31536000, immutable",
    )


def _get_pane_trace_popup(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    agent = (qs.get("agent", [""])[0] or "").strip()
    agents_str = (qs.get("agents", [""])[0] or "").strip()
    agents = [a.strip() for a in agents_str.split(",") if a.strip()] if agents_str else ([agent] if agent else [])
    bg = (qs.get("bg", [""])[0] or "").strip()
    text = (qs.get("text", [""])[0] or "").strip()
    body = ctx["render_pane_trace_popup_html_fn"](agent=agent, agents=agents, bg=bg, text=text).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="text/html; charset=utf-8")


def _get_icon_asset(handler, parsed, ctx) -> None:
    name = parsed.path[6:]
    body = ctx["export_runtime"].icon_bytes(name)
    if body is None:
        handler.send_response(404)
        handler.end_headers()
        return
    _send_bytes(
        handler,
        200,
        body,
        content_type="image/svg+xml",
        cache_control="public, max-age=3600",
    )


def _get_font_asset(handler, parsed, ctx) -> None:
    name = parsed.path[6:]
    body = ctx["export_runtime"].font_bytes(name)
    if body is None:
        handler.send_response(404)
        handler.end_headers()
        return
    _send_bytes(
        handler,
        200,
        body,
        content_type="font/ttf",
        cache_control="public, max-age=3600",
    )


def _get_notify_sounds(handler, _parsed, ctx) -> None:
    sounds_dir = ctx["repo_root"] / "sounds"
    names = list(_chat_notification_sound_filenames(sounds_dir))
    random.shuffle(names)
    body = json.dumps(names, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_notify_sounds_all(handler, _parsed, ctx) -> None:
    sounds_dir = ctx["repo_root"] / "sounds"
    names = []
    if sounds_dir.is_dir():
        for path in sorted(sounds_dir.glob("*.ogg")):
            if path.is_file():
                names.append(path.name)
    body = json.dumps(names, ensure_ascii=True).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="application/json; charset=utf-8")


def _get_notify_sound(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    name = (qs.get("name", [""])[0] or "").strip()
    sounds_dir = ctx["repo_root"] / "sounds"
    if not name:
        picked = _default_session_notify_sound_basename(sounds_dir)
        if not picked:
            handler.send_response(404)
            handler.end_headers()
            return
        name = picked
    path = (sounds_dir / name).resolve()
    try:
        if path.parent != sounds_dir.resolve() or path.suffix.lower() != ".ogg":
            raise FileNotFoundError
        body = path.read_bytes()
    except Exception:
        handler.send_response(404)
        handler.end_headers()
        return
    _send_bytes(
        handler,
        200,
        body,
        content_type="audio/ogg",
        cache_control="public, max-age=3600",
    )


def _get_chat_index(handler, parsed, ctx) -> None:
    qs = parse_qs(parsed.query)
    follow = "1" if qs.get("follow", ["0"])[0] == "1" else "0"
    variant = request_view_variant(headers=handler.headers, query_string=parsed.query)
    chat_settings = ctx["load_chat_settings_fn"]()
    request_host = (handler.headers.get("Host", "") or "").strip()
    request_host_only = request_host.split(":", 1)[0].rstrip(".").lower()
    forwarded_public_host = (handler.headers.get("X-Forwarded-Public-Host", "") or "").strip()
    effective_hub_port = (
        ctx["public_hub_port"]
        if (
            forwarded_public_host
            or ((ctx["public_host"] and request_host_only == ctx["public_host"]) or request_host_only.endswith(".ts.net"))
        )
        else ctx["hub_port"]
    )
    body = ctx["render_chat_html_fn"](
        icon_data_uris=ctx["export_runtime"].icon_data_uris,
        logo_data_uri=ctx["chat_hub_logo_data_uri"],
        server_instance=ctx["server_instance"],
        hub_port=effective_hub_port,
        chat_settings=chat_settings,
        agent_font_mode_inline_style=ctx["chat_font_settings_inline_style_fn"],
        follow=follow,
        chat_base_path=(handler.headers.get("X-Forwarded-Prefix", "") or "").rstrip("/"),
        externalize_app_script=True,
        externalize_main_style=True,
        eager_optional_vendors=False,
        variant=variant,
    ).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="text/html; charset=utf-8")


_GET_ROUTES = {
    "/app.webmanifest": _get_app_manifest,
    "/chat-assets/chat-app.js": _get_chat_app_js,
    "/chat-assets/chat-app.css": _get_chat_app_css,
    "/pane-trace-popup": _get_pane_trace_popup,
    "/notify-sounds": _get_notify_sounds,
    "/notify-sounds-all": _get_notify_sounds_all,
    "/notify-sound": _get_notify_sound,
    "/": _get_chat_index,
    "/index.html": _get_chat_index,
}


def dispatch_get_assets_route(handler, parsed, ctx) -> bool:
    if ctx["serve_pwa_static_fn"](handler, parsed.path):
        return True
    if parsed.path.startswith("/icon/"):
        _get_icon_asset(handler, parsed, ctx)
        return True
    if parsed.path.startswith("/font/"):
        _get_font_asset(handler, parsed, ctx)
        return True
    route = _GET_ROUTES.get(parsed.path)
    if route is None:
        return False
    route(handler, parsed, ctx)
    return True
