from native_log_sync.watch.watch_bindings import start_native_log_fsevents_watcher


def start_binding_watchers(runtime) -> None:
    start_native_log_fsevents_watcher(runtime)


__all__ = [
    "start_binding_watchers",
    "start_native_log_fsevents_watcher",
]
