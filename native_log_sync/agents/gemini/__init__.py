from __future__ import annotations

from native_log_sync.refresh.binding_models import binding_for_path
from .resolve_path import resolve_gemini_native_log


def resolve_native_log_binding(runtime, request):
    path = resolve_gemini_native_log(runtime, request.agent, None)
    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=path or "",
        source="gemini-chat",
    )
