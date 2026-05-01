from __future__ import annotations

from urllib.parse import parse_qs


def _normalized_client(value: str, *, default: str = "desktop-web") -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"mobile", "mobile-web"}:
        return "mobile-web"
    if lowered in {"desktop-app", "tauri", "tauri-app"}:
        return "desktop-app"
    if lowered in {"desktop", "desktop-web", "web"}:
        return "desktop-web"
    return default


def request_client_variant(
    *,
    headers,
    query_string: str = "",
    view_variant: str = "desktop",
    default: str | None = None,
) -> str:
    normalized_view = "mobile" if str(view_variant or "").strip().lower() == "mobile" else "desktop"
    fallback = default or ("mobile-web" if normalized_view == "mobile" else "desktop-web")
    qs = parse_qs(query_string or "", keep_blank_values=False)

    query_client = (qs.get("client", [""])[0] or "").strip()
    if query_client:
        return _normalized_client(query_client, default=fallback)

    header_client = (headers.get("X-Multiagent-Client", "") or "").strip()
    if header_client:
        return _normalized_client(header_client, default=fallback)

    if normalized_view == "mobile":
        return "mobile-web"

    if (qs.get("tauri", [""])[0] or "").strip() == "1":
        return "desktop-app"

    header_tauri = (headers.get("X-Multiagent-Tauri-App", "") or "").strip().lower()
    if header_tauri in {"1", "true", "yes"}:
        return "desktop-app"

    return fallback
