from __future__ import annotations

import json
from urllib.parse import parse_qs

from hub_backend.branding import APP_DISPLAY_NAME
from hub_backend.color_constants import apply_color_tokens, resolve_theme_palette
from hub_backend.transport.request_base_path import request_base_path
from hub_backend.transport.request_view import request_view_variant
from .read import _send_bytes


def _get_app_manifest(handler, _parsed, ctx) -> None:
    base_path = request_base_path(headers=handler.headers, query_string=_parsed.query)
    settings = ctx["load_chat_settings_fn"]()
    palette = resolve_theme_palette(settings)
    bg = str(palette["dark_bg"])
    body = json.dumps(
        {
            "name": f"{ctx['session_name']} · {APP_DISPLAY_NAME}" if ctx.get("session_name") else APP_DISPLAY_NAME,
            "short_name": ctx["session_name"],
            "display": "standalone",
            "background_color": bg,
            "theme_color": bg,
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
    settings = ctx["load_chat_settings_fn"]()
    body = apply_color_tokens(ctx["chat_app_script_asset_fn"](variant), settings=settings).encode("utf-8")
    _send_bytes(
        handler,
        200,
        body,
        content_type="application/javascript; charset=utf-8",
        cache_control="no-store",
    )


def _get_chat_app_css(handler, _parsed, ctx) -> None:
    variant = request_view_variant(headers=handler.headers, query_string=_parsed.query)
    settings = ctx["load_chat_settings_fn"]()
    body = apply_color_tokens(ctx["chat_main_style_asset_fn"](variant), settings=settings).encode("utf-8")
    _send_bytes(
        handler,
        200,
        body,
        content_type="text/css; charset=utf-8",
        cache_control="no-store",
    )


def _get_icon_asset(handler, parsed, ctx) -> None:
    name = parsed.path[6:]
    body = ctx["asset_runtime"].icon_bytes(name)
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
    body = ctx["asset_runtime"].font_bytes(name)
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
            or (ctx["public_host"] and request_host_only == ctx["public_host"])
        )
        else ctx["hub_port"]
    )
    body = ctx["render_chat_html_fn"](
        icon_data_uris=ctx["asset_runtime"].icon_data_uris,
        server_instance=ctx["server_instance"],
        hub_port=effective_hub_port,
        chat_settings=chat_settings,
        agent_font_mode_inline_style=ctx["chat_font_settings_inline_style_fn"],
        follow=follow,
        chat_base_path=request_base_path(headers=handler.headers, query_string=parsed.query),
        externalize_app_script=True,
        externalize_main_style=True,
        eager_optional_vendors=False,
        variant=variant,
        session_name=ctx["session_name"],
    ).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="text/html; charset=utf-8")


_GET_ROUTES = {
    "/app.webmanifest": _get_app_manifest,
    "/chat-assets/chat-app.js": _get_chat_app_js,
    "/chat-assets/chat-app.css": _get_chat_app_css,
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
