from __future__ import annotations

from native_log_sync.chat_runtime_init import initialize_chat_runtime_native_log_sync
from native_log_sync.idle_running.native_log_idle_running import (
    idle_running_display_for_api,
    refresh_native_log_idle_running_statuses,
)
from native_log_sync.watch import start_binding_watchers


def initialize_runtime(runtime) -> None:
    initialize_chat_runtime_native_log_sync(runtime)


def start_watchers(runtime) -> None:
    runtime.refresh_native_log_bindings(reason="startup")
    start_binding_watchers(runtime)


def refresh_idle_statuses(runtime) -> dict[str, str]:
    return refresh_native_log_idle_running_statuses(runtime)


def idle_display_for_api(payload: dict[str, dict]) -> dict[str, dict]:
    return idle_running_display_for_api(payload)
