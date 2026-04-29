from __future__ import annotations

from native_log_sync.refresh.binding_models import binding_for_path

from .resolve_path import resolve_codex_rollout_jsonl_path
from .watch_kqueue import ensure_codex_kqueue_watcher


def resolve_native_log_binding(runtime, request):
    path = resolve_codex_rollout_jsonl_path(request.pane_pid)
    binding = binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=path,
        source="codex-rollout",
    )
    if path:
        ensure_codex_kqueue_watcher(runtime, request.agent, path)
    return binding
