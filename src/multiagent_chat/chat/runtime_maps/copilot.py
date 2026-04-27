"""Runtime display map for the GitHub Copilot agent.

Copilot logs are parsed via the shared JSONL cursor reader.
Override TOOL_MAP or QUIET_TOOLS here to customize Copilot-specific behavior.
Bash command rules are defined in _bash.py (shared).
"""
from __future__ import annotations

from ._tools import QUIET_TOOLS, TOOL_MAP, ToolEntry

__all__ = ["TOOL_MAP", "QUIET_TOOLS", "ToolEntry"]
