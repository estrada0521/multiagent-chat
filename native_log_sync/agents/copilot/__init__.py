from __future__ import annotations

from native_log_sync.refresh.binding_models import binding_for_path

from .resolve_path import resolve_path


def resolve_native_log_binding(runtime, request):
    return binding_for_path(
        agent=request.agent,
        pane_id=request.pane_id,
        pane_pid=request.pane_pid,
        path=resolve_path(runtime, request.agent, request.pane_pid),
        source="copilot-events",
    )


def on_pane_restart(runtime, agent: str) -> None:
    # Path resolves dynamically via lock file on the new PID tree; empty until first message.
    pass


def on_pane_add(runtime, agent: str) -> None:
    pass
