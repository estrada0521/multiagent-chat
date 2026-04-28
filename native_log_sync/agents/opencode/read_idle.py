from __future__ import annotations

from typing import TYPE_CHECKING

from native_log_sync.agents.opencode.read_runtime import parse_opencode_runtime

if TYPE_CHECKING:
    from multiagent_chat.chat.runtime import ChatRuntime


def load_runtime_events_for_idle_running(runtime: ChatRuntime, agent: str) -> list[dict]:
    if agent not in runtime._opencode_cursors:
        return []
    return parse_opencode_runtime(runtime, agent, limit=12)
