"""GET /debug/native-log-sync — minimal JSON: paths native_log_sync uses per agent."""

from __future__ import annotations


def build_native_log_resolved_paths_payload(runtime) -> dict:
    """One line per active agent: file path from sync cursor, or OpenCode session id if no file."""
    out: list[dict[str, str]] = []
    for entry in runtime.sync_cursor_status():
        agent = str(entry.get("agent") or "").strip()
        path = entry.get("log_path")
        resolved = str(path).strip() if path else ""
        if not resolved:
            sid = entry.get("session_id")
            if sid:
                resolved = f"(opencode session: {sid})"
        out.append({"agent": agent, "path": resolved})
    return {"ok": True, "agents": out}
