from __future__ import annotations

from native_log_sync.refresh.binding_models import binding_for_path
from native_log_sync.sync_timing import FIRST_SEEN_GRACE_SECONDS

from .resolve_path import resolve_claude_session_jsonl_path


def resolve_native_log_binding(runtime, request):
    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_claude_session_jsonl_path(
            runtime,
            request.agent,
            None,
            None,
            first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
        ),
        source="claude-session",
    )
