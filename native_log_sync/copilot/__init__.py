from __future__ import annotations

from native_log_sync.core._01_bindings import binding_for_path

from .log_location import resolve_path


def resolve_native_log_binding(runtime, request):
    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_path(runtime, request.agent, request.pane_id, request.pane_pid),
        source="copilot-events",
    )
