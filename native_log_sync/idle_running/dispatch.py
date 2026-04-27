from __future__ import annotations

from typing import TYPE_CHECKING

from native_log_sync.core.cursors import _agent_base_name

from native_log_sync.claude.idle_running import load_runtime_events_for_idle_running as _claude_events
from native_log_sync.codex.idle_running import load_runtime_events_for_idle_running as _codex_events
from native_log_sync.copilot.idle_running import load_runtime_events_for_idle_running as _copilot_events
from native_log_sync.cursor.idle_running import load_runtime_events_for_idle_running as _cursor_events
from native_log_sync.gemini.idle_running import load_runtime_events_for_idle_running as _gemini_events
from native_log_sync.opencode.idle_running import load_runtime_events_for_idle_running as _opencode_events
from native_log_sync.qwen.idle_running import load_runtime_events_for_idle_running as _qwen_events

if TYPE_CHECKING:
    from multiagent_chat.chat.runtime import ChatRuntime

_LOADERS = {
    "claude": _claude_events,
    "cursor": _cursor_events,
    "codex": _codex_events,
    "copilot": _copilot_events,
    "gemini": _gemini_events,
    "qwen": _qwen_events,
    "opencode": _opencode_events,
}


def load_runtime_events_for_idle_running(runtime: ChatRuntime, agent: str) -> list[dict]:
    base = _agent_base_name(agent)
    fn = _LOADERS.get(base)
    if fn is None:
        return []
    return fn(runtime, agent)
