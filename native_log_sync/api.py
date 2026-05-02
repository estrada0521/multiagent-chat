from __future__ import annotations

from native_log_sync.watch import start_binding_watchers


def start_watchers(syncer) -> None:
    start_binding_watchers(syncer)
