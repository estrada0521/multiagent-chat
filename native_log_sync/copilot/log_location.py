from __future__ import annotations

from native_log_sync.core.native_log_init import cached_native_log_path


def resolve_path(runtime: object, agent: str, pane_id: str, pane_pid: str) -> str:
    path = cached_native_log_path(runtime, pane_id, pane_pid)
    if path:
        return path
    from native_log_sync.core.native_file_resolve import resolve_native_log_file

    found = resolve_native_log_file(
        pane_pid,
        r"events\.jsonl$",
        base_name="copilot",
    ) or ""
    if found:
        runtime._pane_native_log_paths[pane_id] = (pane_pid, found)
    return found
