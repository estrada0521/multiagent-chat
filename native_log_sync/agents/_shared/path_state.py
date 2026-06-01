from __future__ import annotations

import os
from datetime import datetime as dt_datetime
from pathlib import Path
from typing import NamedTuple

from backend_core.agents.names import agent_base_name as _agent_base_name
from backend_core.agents.names import agent_instance_number as _agent_instance_number


def _normalized_native_log_path(path: str | Path) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        return os.path.realpath(str(Path(raw).expanduser()))
    except OSError:
        return str(Path(raw).expanduser())


class NativeLogCursor(NamedTuple):
    path: str
    offset: int


def _coerce_native_cursor(raw: object) -> NativeLogCursor | None:
    if isinstance(raw, NativeLogCursor):
        return raw
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        path, offset = raw
        if isinstance(path, str) and isinstance(offset, int):
            return NativeLogCursor(path=path, offset=offset)
    return None


def _load_cursor_dict(raw: object) -> dict[str, NativeLogCursor]:
    result: dict[str, NativeLogCursor] = {}
    if isinstance(raw, dict):
        for agent, value in raw.items():
            if not isinstance(agent, str):
                continue
            cursor = _coerce_native_cursor(value)
            if cursor is not None and Path(cursor.path).is_file():
                result[agent] = cursor
    return result


def _cursor_dict_to_json(cursors: dict[str, NativeLogCursor]) -> dict[str, list]:
    return {agent: [c.path, c.offset] for agent, c in cursors.items()}


def _dedup_cursor_claims(cursors: dict[str, NativeLogCursor]) -> dict[str, NativeLogCursor]:
    path_to_agent: dict[str, str] = {}
    out: dict[str, NativeLogCursor] = {}
    for agent in sorted(cursors):
        cursor = cursors[agent]
        claim_key = _normalized_native_log_path(cursor.path)
        if claim_key in path_to_agent:
            continue
        path_to_agent[claim_key] = agent
        out[agent] = cursor
    return out


def _parse_iso_timestamp_epoch(raw: str) -> float | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return dt_datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _advance_native_cursor(
    cursors: dict[str, NativeLogCursor],
    agent: str,
    current_path: str,
    file_size: int,
) -> int | None:
    prev = cursors.get(agent)
    prev_key = _normalized_native_log_path(prev.path) if prev is not None else ""
    current_key = _normalized_native_log_path(current_path)
    if prev is None or prev_key != current_key:
        cursors[agent] = NativeLogCursor(path=current_path, offset=file_size)
        return None
    if file_size < prev.offset:
        return 0
    if file_size == prev.offset:
        return None
    return prev.offset


def _cursor_binding_changed(
    before: NativeLogCursor | None,
    after: NativeLogCursor | None,
) -> bool:
    if before is None and after is None:
        return False
    if before is None or after is None:
        return True
    return (
        _normalized_native_log_path(before.path) != _normalized_native_log_path(after.path)
        or before.offset != after.offset
    )
