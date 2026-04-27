"""Claude / Cursor / Copilot / Qwen 等が共有する JSONL transcript 形状のランタイム抽出。

ツール表示は *tool_events* コールバック（エージェント別 runtime_tools）に委譲する。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from multiagent_chat.chat.runtime_format import _pane_runtime_with_occurrence_ids


def parse_transcript_jsonl_for_runtime(
    filepath: str,
    limit: int,
    workspace: str,
    *,
    tool_events: Callable[..., list],
) -> list[dict] | None:
    try:
        tail_bytes = 32_768
        with open(filepath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - tail_bytes)
            f.seek(start)
            raw = f.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if start > 0 and lines:
            lines = lines[1:]

        events: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") == "assistant":
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                for c in (msg.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        name = c.get("name", "tool")
                        inp = c.get("input") or {}
                        events.extend(tool_events(name, inp, workspace=workspace))

            if entry.get("type") == "tool.execution_start":
                data = entry.get("data") or {}
                name = data.get("toolName", "tool")
                args = data.get("arguments") or {}
                events.extend(tool_events(name, args, workspace=workspace))
            if entry.get("type") == "assistant.message":
                data = entry.get("data") or {}
                for tr in (data.get("toolRequests") or []):
                    if not isinstance(tr, dict):
                        continue
                    name = tr.get("name", "tool")
                    args = tr.get("arguments") or {}
                    events.extend(tool_events(name, args, workspace=workspace))

            if entry.get("role") == "assistant":
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                for c in (msg.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        name = c.get("name", "tool")
                        inp = c.get("input") or {}
                        events.extend(tool_events(name, inp, workspace=workspace))

        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error("Failed to parse transcript JSONL runtime %s: %s", filepath, e)
        return None
