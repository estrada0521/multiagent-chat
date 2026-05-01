from __future__ import annotations

from urllib.parse import parse_qs


def _normalized_view(value: str, *, default: str = "desktop") -> str:
    lowered = str(value or "").strip().lower()
    if lowered == "mobile":
        return "mobile"
    if lowered == "desktop":
        return "desktop"
    return default


def request_view_variant(*, headers, query_string: str = "", default: str = "desktop") -> str:
    qs = parse_qs(query_string or "", keep_blank_values=False)
    query_view = (qs.get("view", [""])[0] or "").strip()
    if query_view:
        return _normalized_view(query_view, default=default)

    header_view = (headers.get("X-Multiagent-View", "") or "").strip()
    if header_view:
        return _normalized_view(header_view, default=default)

    ch_mobile = (headers.get("Sec-CH-UA-Mobile", "") or "").strip().lower()
    if ch_mobile in {"?1", "1", "true"}:
        return "mobile"
    if ch_mobile in {"?0", "0", "false"}:
        return "desktop"

    user_agent = (headers.get("User-Agent", "") or "").lower()
    mobile_tokens = (
        "iphone",
        "ipod",
        "ipad",
        "android",
        "mobile",
        "opera mini",
        "blackberry",
        "iemobile",
        "silk/",
    )
    if any(token in user_agent for token in mobile_tokens):
        return "mobile"
    return default
