from __future__ import annotations


def push_runtime_display(runtime, agent: str, events: list[dict]) -> None:
    for ev in reversed(events):
        text = str(ev.get("text") or "").strip()
        if not text:
            continue
        runtime._idle_running_event_seq += 1
        runtime._idle_running_display_by_agent[agent] = {
            "current_event": {
                "id": f"{agent}:{runtime._idle_running_event_seq}",
                "text": text,
                "source_id": str(ev.get("source_id") or "").strip(),
            }
        }
        return
