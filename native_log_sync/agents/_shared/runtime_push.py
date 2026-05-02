from __future__ import annotations


def push_runtime_display(runtime, agent: str, events: list[dict]) -> None:
    for ev in reversed(events):
        text = str(ev.get("text") or "").strip()
        if not text:
            continue
        source_id = str(ev.get("source_id") or "").strip()
        current_payload = runtime._idle_running_display_by_agent.get(agent) or {}
        current_event = (current_payload.get("current_event") or {})
        if (
            str(current_event.get("text") or "").strip() == text
            and str(current_event.get("source_id") or "").strip() == source_id
        ):
            return
        tool_call_count = int(current_payload.get("tool_call_count") or 0) + 1
        runtime._idle_running_event_seq += 1
        runtime._idle_running_display_by_agent[agent] = {
            "current_event": {
                "id": f"{agent}:{runtime._idle_running_event_seq}",
                "text": text,
                "source_id": source_id,
            },
            "tool_call_count": tool_call_count,
        }
        runtime.notify_session_state_changed(["agent_runtime"], reason="agent-runtime")
        return
