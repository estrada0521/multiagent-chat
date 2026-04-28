from __future__ import annotations

from native_log_sync.io.process_info import cached_native_log_path, copilot_events_jsonl_for_pid_tree


def resolve_path(runtime: object, agent: str, pane_id: str, pane_pid: str) -> str:
    del agent
    path = cached_native_log_path(runtime, pane_id, pane_pid)
    if path:
        return path
    found = copilot_events_jsonl_for_pid_tree(pane_pid)
    if found:
        runtime._pane_native_log_paths[pane_id] = (pane_pid, found)
    return found
