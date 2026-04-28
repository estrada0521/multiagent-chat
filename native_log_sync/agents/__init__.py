from __future__ import annotations

from importlib import import_module


def _agent_module(agent: str):
    base = str(agent or "").strip().lower().split("-", 1)[0]
    return import_module(f"native_log_sync.agents.{base}")


def resolve_binding(runtime, request):
    resolver = getattr(_agent_module(request.agent), "resolve_native_log_binding", None)
    if resolver is None:
        return None
    return resolver(runtime, request)


def load_idle_events(runtime, agent: str) -> list[dict]:
    reader = getattr(_agent_module(agent), "load_runtime_events_for_idle_running", None)
    if reader is None:
        return []
    return reader(runtime, agent)
