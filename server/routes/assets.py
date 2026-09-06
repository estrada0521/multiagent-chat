from __future__ import annotations

import json
from urllib.parse import parse_qs

from appearance.colors import resolve_theme_palette
from appearance.theme import resolve_server_theme
from appearance.typography import DESKTOP_TEXT_SIZE, MOBILE_TEXT_SIZE, clamp_text_size
from hub_backend.branding import APP_DISPLAY_NAME
from hub_backend.transport.request_base_path import request_base_path
from hub_backend.transport.request_view import request_view_variant
from .read import _send_bytes


def _get_app_manifest(handler, _parsed, ctx) -> None:
    base_path = request_base_path(headers=handler.headers, query_string=_parsed.query)
    palette = resolve_theme_palette()
    bg = str(palette["dark_bg"])
    body = json.dumps(
        {
            "name": f"{ctx['session_name']} · {APP_DISPLAY_NAME}" if ctx.get("session_name") else APP_DISPLAY_NAME,
            "short_name": ctx["session_name"],
            "display": "standalone",
            "background_color": bg,
            "theme_color": bg,
            "start_url": ctx["pwa_asset_url_fn"]("/", base_path),
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


def _send_asset_bytes(handler, reader, name: str, *, content_type: str) -> None:
    try:
        body = reader(name)
    except OSError as exc:
        handler.send_error(500, str(exc))
        return
    if body is None:
        handler.send_response(404)
        handler.end_headers()
        return
    _send_bytes(
        handler,
        200,
        body,
        content_type=content_type,
        cache_control="public, max-age=3600",
    )


def _get_icon_asset(handler, parsed, ctx) -> None:
    _send_asset_bytes(
        handler,
        ctx["asset_runtime"].icon_bytes,
        parsed.path[6:],
        content_type="image/svg+xml",
    )


def _get_font_asset(handler, parsed, ctx) -> None:
    _send_asset_bytes(
        handler,
        ctx["asset_runtime"].font_bytes,
        parsed.path[6:],
        content_type="font/ttf",
    )


def _get_chat_index(handler, parsed, ctx) -> None:
    variant = request_view_variant(headers=handler.headers, query_string=parsed.query)
    query = parse_qs(parsed.query)
    try:
        theme = "dark" if variant == "mobile" else resolve_server_theme(query.get("theme", [""])[0])
        text_size = MOBILE_TEXT_SIZE if variant == "mobile" else clamp_text_size(
            query.get("text_size", [DESKTOP_TEXT_SIZE])[0]
        )
    except (TypeError, ValueError) as exc:
        handler.send_error(400, str(exc))
        return
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
        chat_base_path=request_base_path(headers=handler.headers, query_string=parsed.query),
        eager_optional_vendors=False,
        variant=variant,
        session_name=ctx["session_name"],
        theme=theme,
        text_size=text_size,
    ).encode("utf-8")
    _send_bytes(handler, 200, body, content_type="text/html; charset=utf-8")


_GET_ROUTES = {
    "/app.webmanifest": _get_app_manifest,
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
