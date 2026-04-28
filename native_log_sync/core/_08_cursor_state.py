from __future__ import annotations

import os
import sys
from datetime import datetime as dt_datetime
from pathlib import Path
from typing import NamedTuple

from multiagent_chat.agents.names import agent_base_name as _agent_base_name
from multiagent_chat.agents.names import agent_instance_number as _agent_instance_number


def _native_path_claim_key(path: str | Path, *, stat_result: os.stat_result | None = None) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    if stat_result is not None:
        return f"inode:{stat_result.st_dev}:{stat_result.st_ino}"
    candidate = Path(raw).expanduser()
    try:
        st = candidate.stat()
        return f"inode:{st.st_dev}:{st.st_ino}"
    except OSError:
        normalized = str(candidate)
        if sys.platform == "darwin":
            normalized = normalized.lower()
        return f"path:{normalized}"


class NativeLogCursor(NamedTuple):
    path: str
    offset: int


class OpenCodeCursor(NamedTuple):
    session_id: str
    last_msg_id: str


def _coerce_native_cursor(raw: object) -> NativeLogCursor | None:
    if isinstance(raw, NativeLogCursor):
        return raw
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        path, offset = raw
        if isinstance(path, str) and isinstance(offset, int):
            return NativeLogCursor(path=path, offset=offset)
    return None


def _coerce_opencode_cursor(raw: object) -> OpenCodeCursor | None:
    if isinstance(raw, OpenCodeCursor):
        return raw
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        session_id, msg_id = raw
        if isinstance(session_id, str) and isinstance(msg_id, str):
            return OpenCodeCursor(session_id=session_id, last_msg_id=msg_id)
    return None


def _load_cursor_dict(raw: object) -> dict[str, NativeLogCursor]:
    result: dict[str, NativeLogCursor] = {}
    if isinstance(raw, dict):
        for agent, value in raw.items():
            if not isinstance(agent, str):
                continue
            cursor = _coerce_native_cursor(value)
            if cursor is not None:
                result[agent] = cursor
    return result


def _load_opencode_dict(raw: object) -> dict[str, OpenCodeCursor]:
    result: dict[str, OpenCodeCursor] = {}
    if isinstance(raw, dict):
        for agent, value in raw.items():
            if not isinstance(agent, str):
                continue
            cursor = _coerce_opencode_cursor(value)
            if cursor is not None:
                result[agent] = cursor
    return result


def _cursor_dict_to_json(cursors: dict[str, NativeLogCursor]) -> dict[str, list]:
    return {agent: [c.path, c.offset] for agent, c in cursors.items()}


def _opencode_dict_to_json(cursors: dict[str, OpenCodeCursor]) -> dict[str, list]:
    return {agent: [c.session_id, c.last_msg_id] for agent, c in cursors.items()}


def _dedup_cursor_claims(
    cursors: dict[str, NativeLogCursor],
) -> dict[str, NativeLogCursor]:
    path_to_agent: dict[str, str] = {}
    out: dict[str, NativeLogCursor] = {}
    for agent in sorted(cursors):
        cursor = cursors[agent]
        claim_key = _native_path_claim_key(cursor.path)
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
    prev_key = _native_path_claim_key(prev.path) if prev is not None else ""
    current_key = _native_path_claim_key(current_path)
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
        _native_path_claim_key(before.path) != _native_path_claim_key(after.path)
        or before.offset != after.offset
    )
