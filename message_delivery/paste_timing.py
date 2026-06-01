from __future__ import annotations

from collections.abc import Mapping


def delivery_paste_delay_seconds(
    payload: str,
    *,
    env: Mapping[str, str] | None = None,
    session_attached_count: int | None = None,
) -> float:
    del payload, session_attached_count
    environ = env or {}
    raw = str(environ.get("AGENT_SEND_PASTE_DELAY") or "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return 0.2
