from __future__ import annotations

import threading
import time
from collections import deque

SESSION_STATE_PROJECTIONS = (
    "base",
    "targets",
    "statuses",
    "messages",
    "agent_runtime",
    "provider_runtime",
)
_SESSION_STATE_PROJECTION_SET = frozenset(SESSION_STATE_PROJECTIONS)
_SESSION_STATE_HISTORY_LIMIT = 128


def _ordered_projection_list(values: set[str]) -> list[str]:
    return [name for name in SESSION_STATE_PROJECTIONS if name in values]


def normalize_session_state_projections(
    projections: str | list[str] | tuple[str, ...] | set[str] | None,
    *,
    default_all: bool = True,
) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    raw_items: list[str] = []
    if projections is None:
        raw_items = []
    elif isinstance(projections, str):
        raw_items = projections.split(",")
    else:
        for item in projections:
            raw_items.extend(str(item or "").split(","))
    for raw in raw_items:
        name = str(raw or "").strip().lower()
        if not name:
            continue
        if name == "all":
            for full in SESSION_STATE_PROJECTIONS:
                if full not in seen:
                    selected.append(full)
                    seen.add(full)
            continue
        if name not in _SESSION_STATE_PROJECTION_SET or name in seen:
            continue
        selected.append(name)
        seen.add(name)
    if not selected and default_all:
        return SESSION_STATE_PROJECTIONS
    return tuple(selected)


def initialize_session_state_bus(runtime) -> None:
    runtime._session_state_condition = threading.Condition()
    runtime._session_state_seq = 0
    runtime._session_state_event_history = deque(maxlen=_SESSION_STATE_HISTORY_LIMIT)


def publish_session_state_change(
    runtime,
    projections: str | list[str] | tuple[str, ...] | set[str] | None = None,
    *,
    reason: str = "",
) -> None:
    selected = normalize_session_state_projections(projections, default_all=True)
    with runtime._session_state_condition:
        runtime._session_state_seq += 1
        runtime._session_state_event_history.append(
            {
                "seq": runtime._session_state_seq,
                "projections": list(selected),
                "reason": str(reason or "").strip(),
            }
        )
        runtime._session_state_condition.notify_all()


def wait_for_session_state_change(runtime, after_seq: int, timeout: float = 15.0) -> dict | None:
    deadline = time.monotonic() + max(0.1, float(timeout))
    with runtime._session_state_condition:
        while runtime._session_state_seq <= after_seq:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            runtime._session_state_condition.wait(timeout=remaining)
        latest_seq = runtime._session_state_seq
        history = list(runtime._session_state_event_history)
    relevant = [event for event in history if int(event.get("seq") or 0) > after_seq]
    if not relevant:
        projections = list(SESSION_STATE_PROJECTIONS)
        reason = "resync"
    else:
        missed_history = int(relevant[0].get("seq") or 0) > after_seq + 1
        if missed_history:
            projections = list(SESSION_STATE_PROJECTIONS)
            reason = "resync"
        else:
            projection_set: set[str] = set()
            for event in relevant:
                projection_set.update(normalize_session_state_projections(event.get("projections"), default_all=False))
            projections = _ordered_projection_list(projection_set) or list(SESSION_STATE_PROJECTIONS)
            reason = str(relevant[-1].get("reason") or "").strip()
    return {
        "seq": latest_seq,
        "projections": projections,
        "reason": reason,
    }


def build_session_state_payload(
    runtime,
    *,
    server_instance: str,
    session_name: str,
    projections: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict:
    selected = set(normalize_session_state_projections(projections, default_all=True))
    payload: dict = {}
    if "base" in selected:
        payload.update(
            {
                "server_instance": server_instance,
                "session": session_name,
                "active": bool(runtime.session_is_active),
                "launch_pending": bool(runtime.launch_pending()),
            }
        )
    if "targets" in selected:
        active = runtime.active_agents()
        if not active and runtime.session_is_active and runtime.targets:
            active = list(runtime.targets)
        payload["targets"] = active
    if "statuses" in selected:
        payload["statuses"] = runtime.agent_statuses()
    if "agent_runtime" in selected:
        payload["agent_runtime"] = runtime.agent_runtime_state()
    if "provider_runtime" in selected:
        payload["provider_runtime"] = runtime.provider_runtime_state()
    return payload
