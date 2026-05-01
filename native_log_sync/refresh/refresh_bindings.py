from __future__ import annotations

from native_log_sync.agents import resolve_binding
from native_log_sync.refresh.binding_models import NativeLogBinding, PaneBindingRequest


def _watch_roots_for_bindings(bindings_by_agent: dict[str, NativeLogBinding]) -> dict[str, list[str]]:
    watch_roots: dict[str, list[str]] = {}
    for binding in bindings_by_agent.values():
        for root in binding.watch_roots:
            watch_roots.setdefault(root, []).append(binding.agent)
    return watch_roots


def refresh_native_log_bindings(
    runtime,
    pane_requests: list[PaneBindingRequest],
    *,
    replace_all: bool = True,
    reason: str = "",
) -> list[NativeLogBinding]:
    del reason
    bindings: list[NativeLogBinding] = []
    if replace_all:
        next_by_agent: dict[str, NativeLogBinding] = {}
    else:
        next_by_agent = dict(getattr(runtime, "_native_log_bindings_by_agent", {}))

    for request in pane_requests:
        runtime._pane_native_log_paths.pop(request.pane_id, None)
        if not replace_all:
            next_by_agent.pop(request.agent, None)
        binding = resolve_binding(runtime, request)
        if binding is None:
            continue
        bindings.append(binding)
        next_by_agent[binding.agent] = binding

    runtime._native_log_bindings_by_agent = next_by_agent
    runtime._native_log_watch_roots = _watch_roots_for_bindings(next_by_agent)
    runtime._native_log_watch_generation += 1
    runtime._native_log_watch_reconfigure.set()
    return bindings
