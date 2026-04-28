from __future__ import annotations

from native_log_sync.refresh.binding_models import binding_for_path
from native_log_sync.io.sync_timing import FIRST_SEEN_GRACE_SECONDS

from .resolve_path import resolve_gemini_native_log


def resolve_native_log_binding(runtime, request):
    workspace_text = str(runtime.workspace or "").strip()
    if not workspace_text:
        return None
    path = resolve_gemini_native_log(
        agent=request.agent,
        workspace_aliases=runtime._workspace_aliases(workspace_text),
        native_log_path=None,
        gemini_cursors=runtime._gemini_cursors,
        should_stick_to_existing_cursor=runtime._should_stick_to_existing_cursor(request.agent),
        first_seen_ts=runtime._first_seen_for_agent(request.agent),
        first_seen_grace_seconds=FIRST_SEEN_GRACE_SECONDS,
        global_claimed_paths=set(runtime._collect_global_native_log_claims().keys()),
    )
    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=path or "",
        source="gemini-chat",
    )
