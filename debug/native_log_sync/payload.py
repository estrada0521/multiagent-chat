"""GET /debug/native-log-sync — kqueue watched paths + cursor state per agent."""

from __future__ import annotations


def build_native_log_resolved_paths_payload(runtime) -> dict:
    active_agents = runtime.active_agents()

    watched: dict[str, str] = runtime.native_log_watched_paths()

    cursor_by_agent = {e["agent"]: e for e in runtime.cursor_status()}

    out: list[dict] = []
    for agent in active_agents:
        cursor = cursor_by_agent.get(agent, {})
        out.append({
            "agent": agent,
            "watched_path": watched.get(agent, ""),
            "offset": cursor.get("offset"),
            "file_size": cursor.get("file_size"),
        })

    return {"ok": True, "agents": out}
