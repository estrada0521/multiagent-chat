"""Chat server wiring: FSEvents watchers for native CLI logs and Cursor transcripts."""

from __future__ import annotations

from native_log_sync.core.cursor_transcript_fsevents import start_cursor_transcript_fsevents_watcher
from native_log_sync.core.native_log_fsevents import start_native_log_fsevents_watcher


def start_chat_native_log_watchers(runtime) -> None:
    start_cursor_transcript_fsevents_watcher(runtime)
    start_native_log_fsevents_watcher(runtime)
