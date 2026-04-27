from __future__ import annotations


def run_cursor_transcript_sync_from_fs_paths(runtime, raw_paths: set[str]) -> None:
    from native_log_sync.cursor.log_location import (
        expand_fsevent_paths_to_transcript_jsonl,
        sync_cursor_transcript_paths,
    )

    jsonl_paths = expand_fsevent_paths_to_transcript_jsonl(runtime, raw_paths)
    if jsonl_paths:
        sync_cursor_transcript_paths(runtime, jsonl_paths)
