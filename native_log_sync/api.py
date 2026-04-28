from __future__ import annotations

from native_log_sync.watch import start_binding_watchers
from native_log_sync.watch.emit_events import (
    idle_running_display_for_api,
    refresh_idle_statuses as _refresh_idle_statuses_impl,
)


def start_watchers(runtime) -> None:
    runtime.refresh_native_log_bindings(reason="startup")
    start_binding_watchers(runtime)


def refresh_idle_statuses(runtime) -> dict[str, str]:
    return _refresh_idle_statuses_impl(runtime)


def idle_display_for_api(payload: dict[str, dict]) -> dict[str, dict]:
    return idle_running_display_for_api(payload)
