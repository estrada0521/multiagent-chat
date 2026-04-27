from __future__ import annotations

from native_log_sync.core.runtime_display import runtime_tool_events as _runtime_tool_events
from native_log_sync.gemini.tools import QUIET_TOOLS, TOOL_MAP


def runtime_tool_events(name: object, arguments: object, *, workspace: str = "") -> list[dict]:
    return _runtime_tool_events(
        name, arguments, workspace=workspace, tool_map=TOOL_MAP, quiet_tools=QUIET_TOOLS
    )
