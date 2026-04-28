from __future__ import annotations

import os
from typing import TYPE_CHECKING

from native_log_sync.core._13_runtime_parsers import parse_qwen_jsonl_for_runtime

if TYPE_CHECKING:
    from multiagent_chat.chat.runtime import ChatRuntime


def load_runtime_events_for_idle_running(runtime: ChatRuntime, agent: str) -> list[dict]:
    if agent not in runtime._qwen_cursors:
        return []
    path = runtime._qwen_cursors[agent].path
    if not path or not os.path.exists(path):
        return []
    return parse_qwen_jsonl_for_runtime(path, limit=12, workspace=runtime.workspace)
