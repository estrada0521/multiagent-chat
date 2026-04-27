from __future__ import annotations

from typing import Literal


def send_turn_is_complete(last_send_ts: float, last_done_ts: float) -> bool:
    if last_send_ts == 0.0:
        return True
    return last_done_ts >= last_send_ts


def idle_running_from_timestamps(last_send_ts: float, last_done_ts: float) -> Literal["idle", "running"]:
    if last_send_ts > 0.0 and last_done_ts < last_send_ts:
        return "running"
    return "idle"


def idle_running_display_for_api(display_by_agent: dict[str, dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for agent, payload in display_by_agent.items():
        if not isinstance(payload, dict):
            continue
        raw_event = payload.get("current_event")
        if not isinstance(raw_event, dict):
            continue
        event_id = str(raw_event.get("id") or "").strip()
        text = str(raw_event.get("text") or "").rstrip()
        if not event_id or not text:
            continue
        result[agent] = {"current_event": {"id": event_id, "text": text}}
    return result
