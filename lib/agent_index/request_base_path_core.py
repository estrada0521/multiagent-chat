from __future__ import annotations

import re
from urllib.parse import parse_qs


_SAFE_BASE_PATH_RE = re.compile(r"^/(?:[A-Za-z0-9._~!$&()*+,;=:@%-]+(?:/[A-Za-z0-9._~!$&()*+,;=:@%-]+)*)?$")


def normalize_request_base_path(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return ""
    if not _SAFE_BASE_PATH_RE.fullmatch(raw):
        return ""
    return raw


def request_base_path(*, headers, query_string: str = "") -> str:
    forwarded = normalize_request_base_path(headers.get("X-Forwarded-Prefix", ""))
    if forwarded:
        return forwarded
    qs = parse_qs(query_string or "", keep_blank_values=False)
    return normalize_request_base_path((qs.get("base_path", [""])[0] or ""))
