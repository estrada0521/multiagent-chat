from __future__ import annotations

from importlib import import_module


def _agent_module_name(agent: str) -> str:
    base = str(agent or "").strip().lower().split("-", 1)[0]
    return f"native_log_sync.{base}"


def resolve_binding(runtime, request):
    module = import_module(_agent_module_name(request.agent))
    resolver = getattr(module, "resolve_native_log_binding", None)
    if resolver is None:
        return None
    return resolver(runtime, request)
