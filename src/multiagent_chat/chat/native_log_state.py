from __future__ import annotations

import json
import threading
import time

from native_log_sync.agents._shared.path_state import (
    _dedup_cursor_claims,
    _load_cursor_dict,
    _load_opencode_dict,
)


def initialize_native_log_runtime_state(runtime: object) -> None:
    runtime._idle_running_runtime_events = {}
    runtime._idle_running_display_by_agent = {}
    runtime._idle_running_run_start_tail = {}
    runtime._idle_running_last_status = {}
    runtime._pane_native_log_paths = {}
    runtime._native_log_bindings_by_agent = {}
    runtime._native_log_watch_roots = {}
    runtime._native_log_watch_generation = 0
    runtime._native_log_watch_reconfigure = threading.Event()
    runtime._idle_running_event_seq = 0

    runtime._sync_state = runtime.load_sync_state()
    runtime._codex_cursors = _dedup_cursor_claims(_load_cursor_dict(runtime._sync_state.get("codex_cursors")))
    runtime._cursor_cursors = _dedup_cursor_claims(_load_cursor_dict(runtime._sync_state.get("cursor_cursors")))
    runtime._copilot_cursors = _dedup_cursor_claims(_load_cursor_dict(runtime._sync_state.get("copilot_cursors")))
    runtime._qwen_cursors = _dedup_cursor_claims(_load_cursor_dict(runtime._sync_state.get("qwen_cursors")))
    runtime._claude_cursors = _dedup_cursor_claims(_load_cursor_dict(runtime._sync_state.get("claude_cursors")))
    runtime._gemini_cursors = _dedup_cursor_claims(_load_cursor_dict(runtime._sync_state.get("gemini_cursors")))
    runtime._opencode_cursors = _load_opencode_dict(runtime._sync_state.get("opencode_cursors"))

    runtime._agent_first_seen_ts = {}
    raw_first_seen = runtime._sync_state.get("agent_first_seen_ts")
    if isinstance(raw_first_seen, dict):
        for key, value in raw_first_seen.items():
            if isinstance(key, str) and isinstance(value, (int, float)):
                runtime._agent_first_seen_ts[key] = float(value)

    runtime._synced_msg_ids = set()
    persisted_ids = runtime._sync_state.get("synced_msg_ids")
    if isinstance(persisted_ids, list):
        for msg_id in persisted_ids:
            if isinstance(msg_id, str) and msg_id.strip():
                runtime._synced_msg_ids.add(msg_id.strip())

    preload_prefixes = ("gemini", "codex", "cursor", "claude", "copilot", "qwen", "opencode")
    try:
        if runtime.index_path.exists():
            with open(runtime.index_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    sender = str(obj.get("sender") or "")
                    agent = str(obj.get("agent") or "")
                    if sender.startswith(preload_prefixes) or agent:
                        msg_id = str(obj.get("msg_id") or "").strip()
                        if msg_id:
                            runtime._synced_msg_ids.add(msg_id)
    except Exception:
        pass


def first_seen_for_agent(runtime: object, agent: str, *, time_module=time) -> float:
    ts = runtime._agent_first_seen_ts.get(agent)
    if ts is None:
        ts = time_module.time()
        runtime._agent_first_seen_ts[agent] = ts
    return ts
