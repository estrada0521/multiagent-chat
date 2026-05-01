from __future__ import annotations

import re


def agent_base_name(raw_name: str) -> str:
    return re.sub(r"-\d+$", "", str(raw_name or "").strip().lower())


def agent_instance_number(raw_name: str) -> int | None:
    match = re.fullmatch(r".+-(\d+)$", str(raw_name or "").strip().lower())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None
