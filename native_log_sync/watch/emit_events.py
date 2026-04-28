from __future__ import annotations

from typing import Literal

from native_log_sync.agents import load_idle_events


def emit_agent_updates(runtime, agent: str, path: str) -> None:
    runtime._first_seen_for_agent(agent)
    base = str(agent or "").split("-", 1)[0]
    sync_method = getattr(runtime, f"_sync_{base}_assistant_messages", None)
    if sync_method is None:
        return
    sync_method(agent, path)


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


def refresh_idle_statuses(runtime) -> dict[str, str]:
    result: dict[str, str] = {}
    for agent in runtime.active_agents():
        runtime_events = load_idle_events(runtime, agent)
        prev_runtime_events = runtime._idle_running_runtime_events.get(agent, [])
        runtime._idle_running_runtime_events[agent] = runtime_events

        last_send = float(runtime._agent_last_send_ts.get(agent) or 0.0)
        last_done = float(runtime._agent_last_turn_done_ts.get(agent) or 0.0)
        result[agent] = idle_running_from_timestamps(last_send, last_done)

        if result[agent] == "running" and runtime._idle_running_last_status.get(agent) != "running":
            runtime._idle_running_display_by_agent.pop(agent, None)
            if prev_runtime_events:
                ev = prev_runtime_events[-1]
                runtime._idle_running_run_start_tail[agent] = (
                    str(ev.get("source_id") or "").strip(),
                    str(ev.get("text") or "").strip(),
                )
            else:
                runtime._idle_running_run_start_tail.pop(agent, None)
        runtime._idle_running_last_status[agent] = result[agent]

        if result[agent] == "running":
            prev_display = runtime._idle_running_display_by_agent.get(agent)
            state = dict(prev_display) if isinstance(prev_display, dict) else {}
            current_event = (
                state.get("current_event") if isinstance(state.get("current_event"), dict) else None
            )
            current_source_id = str((current_event or {}).get("source_id") or "").strip()
            if runtime_events:
                recent_events = runtime_events[-1:]
                combined_text = str(recent_events[-1].get("text") or "").strip()
                latest_event = recent_events[-1]
                source_id = str(latest_event.get("source_id") or "").strip()
                stale_tail = runtime._idle_running_run_start_tail.get(agent)
                if stale_tail is not None and (source_id, combined_text) == stale_tail:
                    current_event = None
                else:
                    if stale_tail is not None:
                        runtime._idle_running_run_start_tail.pop(agent, None)
                    if current_event is None or source_id != current_source_id:
                        runtime._idle_running_event_seq += 1
                        current_event = {
                            "id": f"{agent}:{runtime._idle_running_event_seq}",
                            "text": combined_text,
                            "source_id": source_id,
                        }
                    else:
                        current_event["text"] = combined_text
            if current_event and str(current_event.get("text") or "").strip():
                runtime._idle_running_display_by_agent[agent] = {"current_event": current_event}
        else:
            runtime._idle_running_run_start_tail.pop(agent, None)
    return result
