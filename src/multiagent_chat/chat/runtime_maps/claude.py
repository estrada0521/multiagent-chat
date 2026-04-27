"""Runtime display map for the Claude Code agent.

Tool → label mapping is defined in _tools.py (shared with other agents).
Override TOOL_MAP or QUIET_TOOLS here to customize Claude-specific behavior.

Bash command rules are defined in _bash.py (also shared).
"""
from __future__ import annotations

from ._tools import QUIET_TOOLS, TOOL_MAP, ToolEntry

__all__ = ["TOOL_MAP", "QUIET_TOOLS", "ToolEntry"]
