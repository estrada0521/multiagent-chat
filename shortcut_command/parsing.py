from __future__ import annotations

import re


def parse_pane_direct_command(message: str) -> dict | None:
    normalized = (message or "").strip().lower()
    match = re.fullmatch(r"(up|down)(?:\s+(\d+))?", normalized)
    if not match:
        return None
    repeat = max(1, min(int(match.group(2) or "1"), 100))
    return {"name": match.group(1), "repeat": repeat}
