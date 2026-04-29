"""GET /debug/native-log-sync — kqueue watched paths + cursor state per agent."""

from __future__ import annotations

from native_log_sync.io.sync_state import sync_cursor_status


def build_native_log_resolved_paths_payload(runtime) -> dict:
    active_agents = runtime.active_agents()

    watcher = getattr(runtime, "_native_log_vnode_watcher", None)
    watched: dict[str, str] = watcher.get_watched_paths() if watcher else {}

    cursor_by_agent = {e["agent"]: e for e in sync_cursor_status(runtime)}

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
