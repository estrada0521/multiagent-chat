from __future__ import annotations

import fcntl
import json
import logging
import os
import time

from native_log_sync.agents._shared.path_state import (
    NativeLogCursor,
    _agent_base_name,
    _cursor_dict_to_json,
    _opencode_dict_to_json,
)
from native_log_sync.io.state_paths import (
    canonical_native_log_sync_state_path,
    legacy_agent_index_sync_state_path,
)


def load_sync_state(runtime) -> dict:
    canonical = canonical_native_log_sync_state_path(runtime.index_path.parent)
    legacy = legacy_agent_index_sync_state_path(runtime.index_path.parent)

    if canonical.exists():
        read_path = canonical
    elif legacy.exists():
        read_path = legacy
    else:
        return {}

    try:
        with read_path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            raw = handle.read().strip()
            if not raw:
                return {}
            data = json.loads(raw)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

    if read_path == legacy:
        try:
            legacy.rename(canonical)
        except OSError:
            try:
                canonical.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                legacy.unlink()
            except OSError:
                pass
    elif legacy.exists():
        try:
            legacy.unlink()
        except OSError:
            pass
    return data


def save_sync_state(runtime, *, time_module=time) -> None:
    try:
        state = {
            "codex_cursors": _cursor_dict_to_json(runtime._codex_cursors),
            "cursor_cursors": _cursor_dict_to_json(runtime._cursor_cursors),
            "copilot_cursors": _cursor_dict_to_json(runtime._copilot_cursors),
            "qwen_cursors": _cursor_dict_to_json(runtime._qwen_cursors),
            "claude_cursors": _cursor_dict_to_json(runtime._claude_cursors),
            "gemini_cursors": _cursor_dict_to_json(runtime._gemini_cursors),
            "opencode_cursors": _opencode_dict_to_json(runtime._opencode_cursors),
            "agent_first_seen_ts": dict(runtime._agent_first_seen_ts),
            "synced_msg_ids": sorted(runtime._synced_msg_ids),
            "last_sync": time_module.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with canonical_native_log_sync_state_path(runtime.index_path.parent).open("w", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(state, ensure_ascii=False))
            handle.flush()
            os.fsync(handle.fileno())
    except Exception as exc:
        logging.error("Failed to save sync state: %s", exc)


def sync_cursor_status(runtime, *, os_module=os) -> list[dict]:
    result: list[dict] = []
    cursor_maps: list[tuple[str, dict[str, NativeLogCursor]]] = [
        ("codex", runtime._codex_cursors),
        ("cursor", runtime._cursor_cursors),
        ("copilot", runtime._copilot_cursors),
        ("qwen", runtime._qwen_cursors),
        ("claude", runtime._claude_cursors),
        ("gemini", runtime._gemini_cursors),
    ]
    for agent in runtime.active_agents():
        entry: dict = {
            "agent": agent,
            "type": _agent_base_name(agent),
            "log_path": None,
            "offset": None,
            "file_size": None,
            "session_id": None,
            "last_msg_id": None,
            "first_seen_ts": runtime._first_seen_for_agent(agent),
        }
        for _type, cmap in cursor_maps:
            if agent in cmap:
                cursor = cmap[agent]
                entry["log_path"] = cursor.path
                entry["offset"] = cursor.offset
                try:
                    entry["file_size"] = os_module.path.getsize(cursor.path)
                except OSError:
                    entry["file_size"] = None
                break
        if agent in runtime._opencode_cursors:
            cursor = runtime._opencode_cursors[agent]
            entry["session_id"] = cursor.session_id
            entry["last_msg_id"] = cursor.last_msg_id
        result.append(entry)
    return result
