from __future__ import annotations

import json
import logging
from collections.abc import Callable

from multiagent_chat.chat.runtime_format import _pane_runtime_with_occurrence_ids

ToolCallIter = Callable[[dict], list[tuple[str, dict]]]
ToolEventsFn = Callable[..., list]


def parse_jsonl_tail_for_runtime(
    filepath: str,
    limit: int,
    workspace: str = "",
    *,
    iter_tool_calls: ToolCallIter,
    tool_events: ToolEventsFn,
    log_label: str = "native JSONL",
    tail_bytes: int = 32_768,
) -> list[dict] | None:
    try:
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
        ws = str(workspace or "")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            for tool_name, inp in iter_tool_calls(entry):
                events.extend(tool_events(tool_name, inp, workspace=ws))

        return _pane_runtime_with_occurrence_ids(events, limit=limit)
    except Exception as e:
        logging.error("Failed to parse %s runtime %s: %s", log_label, filepath, e)
        return None
