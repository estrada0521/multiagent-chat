"""Per-agent runtime display maps.

Usage:
    from multiagent_chat.chat.runtime_maps import get_agent_tool_map

    tool_map, quiet_tools = get_agent_tool_map("claude")
"""
from __future__ import annotations

from . import claude, codex, copilot, cursor, gemini, qwen
from ._tools import QUIET_TOOLS, TOOL_MAP, ToolEntry

_AGENT_MODULES = {
    "claude":  claude,
    "codex":   codex,
    "cursor":  cursor,
    "copilot": copilot,
    "qwen":    qwen,
}


def get_agent_tool_map(base_name: str) -> tuple[dict, frozenset]:
    """Return (TOOL_MAP, QUIET_TOOLS) for the given agent base name.

    Falls back to the shared defaults for unknown agents.
    """
    mod = _AGENT_MODULES.get(base_name)
    if mod is None:
        return TOOL_MAP, QUIET_TOOLS
    return mod.TOOL_MAP, mod.QUIET_TOOLS


__all__ = ["get_agent_tool_map", "ToolEntry", "TOOL_MAP", "QUIET_TOOLS", "gemini"]
