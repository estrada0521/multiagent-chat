"""Attach native-log sync mutable state to ChatRuntime (single ownership: this package)."""

from __future__ import annotations

import json

from native_log_sync.core.cursors import (
    _dedup_cursor_claims,
    _load_cursor_dict,
    _load_opencode_dict,
)


def initialize_chat_runtime_native_log_sync(runtime: object) -> None:
    """Populate idle/sync fields previously inlined in ChatRuntime.__init__."""
    runtime._idle_running_runtime_events = {}
    runtime._idle_running_display_by_agent = {}
    runtime._idle_running_run_start_tail = {}
    runtime._idle_running_last_status = {}
    runtime._pane_native_log_paths = {}
    runtime._idle_running_event_seq = 0
    runtime._global_log_claims = {}
    runtime._global_log_claims_fetched_at = 0.0
    runtime._last_sync_state_heartbeat = 0.0
    runtime._workspace_git_root_cache = {}

    runtime._sync_state = runtime.load_sync_state()
    runtime._codex_cursors = _load_cursor_dict(runtime._sync_state.get("codex_cursors"))
    runtime._cursor_cursors = _load_cursor_dict(runtime._sync_state.get("cursor_cursors"))
    runtime._copilot_cursors = _load_cursor_dict(runtime._sync_state.get("copilot_cursors"))
    runtime._qwen_cursors = _load_cursor_dict(runtime._sync_state.get("qwen_cursors"))
    runtime._claude_cursors = _load_cursor_dict(runtime._sync_state.get("claude_cursors"))
    runtime._gemini_cursors = _load_cursor_dict(runtime._sync_state.get("gemini_cursors"))
    runtime._opencode_cursors = _load_opencode_dict(runtime._sync_state.get("opencode_cursors"))
    if not runtime._cursor_cursors:
        runtime._cursor_cursors = _load_cursor_dict(runtime._sync_state.get("cursor_state"))
    if not runtime._opencode_cursors:
        runtime._opencode_cursors = _load_opencode_dict(runtime._sync_state.get("opencode_state"))
    runtime._codex_cursors = _dedup_cursor_claims(runtime._codex_cursors)
    runtime._cursor_cursors = _dedup_cursor_claims(runtime._cursor_cursors)
    runtime._copilot_cursors = _dedup_cursor_claims(runtime._copilot_cursors)
    runtime._qwen_cursors = _dedup_cursor_claims(runtime._qwen_cursors)
    runtime._claude_cursors = _dedup_cursor_claims(runtime._claude_cursors)
    runtime._gemini_cursors = _dedup_cursor_claims(runtime._gemini_cursors)

    runtime._agent_first_seen_ts = {}
    raw_first_seen = runtime._sync_state.get("agent_first_seen_ts")
    if isinstance(raw_first_seen, dict):
        for _k, _v in raw_first_seen.items():
            if isinstance(_k, str) and isinstance(_v, (int, float)):
                runtime._agent_first_seen_ts[_k] = float(_v)

    runtime._synced_msg_ids = set()
    _persisted_ids = runtime._sync_state.get("synced_msg_ids")
    if isinstance(_persisted_ids, list):
        for _mid in _persisted_ids:
            if isinstance(_mid, str) and _mid.strip():
                runtime._synced_msg_ids.add(_mid.strip())

    _preload_prefixes = ("gemini", "codex", "cursor", "claude", "copilot", "qwen", "opencode")
    try:
        if runtime.index_path.exists():
            with open(runtime.index_path, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        _obj = json.loads(_line)
                        _sender = str(_obj.get("sender") or "")
                        _agent = str(_obj.get("agent") or "")
                        if _sender.startswith(_preload_prefixes) or _agent:
                            _mid = str(_obj.get("msg_id") or "").strip()
                            if _mid:
                                runtime._synced_msg_ids.add(_mid)
                    except Exception:
                        pass
    except Exception:
        pass
