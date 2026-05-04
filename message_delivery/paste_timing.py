from __future__ import annotations

from collections.abc import Mapping


def delivery_paste_delay_seconds(
    payload: str,
    *,
    env: Mapping[str, str] | None = None,
    session_attached_count: int | None = None,
) -> float:
    environ = env or {}
    raw = str(environ.get("AGENT_SEND_PASTE_DELAY") or "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass

    delay = 0.3
    if session_attached_count == 0:
        delay = max(delay, 0.45)

    text_len = len(str(payload or ""))
    delay += min(0.15, text_len / 4000.0 * 0.15)
    return delay
