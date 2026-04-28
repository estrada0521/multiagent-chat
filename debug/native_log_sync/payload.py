"""GET /debug/native-log-sync — minimal JSON: resolved native paths per agent."""

from __future__ import annotations

from multiagent_chat.agents.names import agent_base_name


def build_native_log_resolved_paths_payload(runtime) -> dict:
    """Paths from explicit pane-scoped bindings when available."""
    out: list[dict[str, str]] = []
    active_agents = runtime.active_agents()
    runtime.refresh_native_log_bindings(active_agents, reason="debug-panel")
    for agent in active_agents:
        binding = runtime._native_log_bindings_by_agent.get(agent)
        resolved = binding.path if binding else ""
        if not resolved and agent_base_name(agent) == "opencode":
            sid = runtime.sync_cursor_status()
            for entry in sid:
                if str(entry.get("agent") or "").strip() == agent and entry.get("session_id"):
                    resolved = f"(opencode session: {entry['session_id']})"
                    break
        out.append({"agent": agent, "path": resolved})
    return {"ok": True, "agents": out}
