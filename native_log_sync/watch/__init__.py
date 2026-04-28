from native_log_sync.watch.watch_bindings import (
    start_cursor_transcript_fsevents_watcher,
    start_native_log_fsevents_watcher,
)


def start_binding_watchers(runtime) -> None:
    start_cursor_transcript_fsevents_watcher(runtime)
    start_native_log_fsevents_watcher(runtime)


__all__ = [
    "start_binding_watchers",
    "start_cursor_transcript_fsevents_watcher",
    "start_native_log_fsevents_watcher",
]
