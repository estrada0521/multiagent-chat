from __future__ import annotations

from native_log_sync.refresh.binding_models import binding_for_path

from .resolve_path import resolve_cursor_transcript_open_in_pane


def resolve_native_log_binding(runtime, request):
    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_cursor_transcript_open_in_pane(runtime, request.agent),
        source="cursor-pane",
    )
