"""Runtime display map for the OpenAI Codex agent.

Codex emits tool calls via custom_tool_call and function_call payloads,
which resolve to the same logical tool names as Claude Code native tools
(exec_command, apply_patch, etc.).

Override TOOL_MAP or QUIET_TOOLS here to customize Codex-specific behavior.
Bash command rules are defined in _bash.py (shared).
"""
from __future__ import annotations

from ._tools import QUIET_TOOLS, TOOL_MAP, ToolEntry

__all__ = ["TOOL_MAP", "QUIET_TOOLS", "ToolEntry"]
