from __future__ import annotations

from native_log_sync.claude.runtime_tools import runtime_tool_events
from native_log_sync.core.jsonl_transcript_runtime import parse_transcript_jsonl_for_runtime


def parse_jsonl_for_runtime(filepath: str, limit: int, workspace: str = "") -> list[dict] | None:
    return parse_transcript_jsonl_for_runtime(
        filepath, limit, workspace, tool_events=runtime_tool_events
    )
