from __future__ import annotations


def emit_agent_updates(runtime, agent: str, path: str) -> None:
    runtime._first_seen_for_agent(agent)
    base = str(agent or "").split("-", 1)[0]
    sync_method = getattr(runtime, f"_sync_{base}_native_log", None)
    if sync_method is None:
        return
    sync_method(agent, path)




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


def refresh_idle_statuses(runtime) -> dict[str, str]:
    result: dict[str, str] = {}
    for agent in runtime.active_agents():
        result[agent] = "running" if agent in runtime._agent_running else "idle"
        if result[agent] != "running":
            runtime._idle_running_display_by_agent.pop(agent, None)
    return result
