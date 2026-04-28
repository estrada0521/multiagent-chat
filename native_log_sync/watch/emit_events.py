from __future__ import annotations


def emit_agent_updates(runtime, agent: str, path: str) -> None:
    runtime._first_seen_for_agent(agent)
    base = str(agent or "").split("-", 1)[0]
    sync_method = getattr(runtime, f"_sync_{base}_assistant_messages", None)
    if sync_method is None:
        return
    sync_method(agent, path)
