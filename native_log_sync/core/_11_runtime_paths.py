from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlparse


def workspace_roots(workspace: str = "") -> list[str]:
    roots: list[str] = []
    for raw_root in (workspace, os.getcwd()):
        root = str(raw_root or "").strip()
        if not root:
            continue
        normalized = os.path.realpath(root)
        if normalized not in roots:
            roots.append(normalized)
    return roots


def display_path(value: object, *, workspace: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.match(r"^[a-z][a-z0-9+.-]*://", text, re.IGNORECASE):
        if not text.lower().startswith("file://"):
            return text
        try:
            parsed = urlparse(text)
            text = unquote(parsed.path or "").strip()
        except Exception:
            return text
    if not text:
        return ""
    normalized = os.path.normpath(text)
    if not os.path.isabs(normalized):
        return normalized.replace(os.sep, "/")
    normalized_real = os.path.realpath(normalized)
    for root in workspace_roots(workspace):
        try:
            rel = os.path.relpath(normalized_real, root)
        except Exception:
            continue
        if rel == ".":
            return "."
        if rel != ".." and not rel.startswith(f"..{os.sep}"):
            return rel.replace(os.sep, "/")
    return normalized_real.replace(os.sep, "/")
