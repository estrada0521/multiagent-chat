from __future__ import annotations

from native_log_sync.core._01_bindings import NativeLogBinding, PaneBindingRequest
from native_log_sync.registry import resolve_binding


def refresh_native_log_bindings(
    runtime,
    pane_requests: list[PaneBindingRequest],
    *,
    reason: str = "",
) -> list[NativeLogBinding]:
    del reason
    bindings: list[NativeLogBinding] = []
    next_by_agent: dict[str, NativeLogBinding] = {}
    next_watch_roots: dict[str, list[str]] = {}

    for request in pane_requests:
        runtime._pane_native_log_paths.pop(request.pane_id, None)
        binding = resolve_binding(runtime, request)
        if binding is None:
            continue
        bindings.append(binding)
        next_by_agent[binding.agent] = binding
        for root in binding.watch_roots:
            next_watch_roots.setdefault(root, []).append(binding.agent)

    runtime._native_log_bindings_by_agent = next_by_agent
    runtime._native_log_watch_roots = next_watch_roots
    runtime._native_log_watch_generation += 1
    runtime._native_log_watch_reconfigure.set()
    return bindings
