"""共通: 監視側（FSEvents 等）から渡されたパス集合を、エージェント別の transcript 同期へ届ける。

Cursor 以外の FS→同期は今のところここに無いが、同様の入口を増やすときはこのファイルに集約する。
"""

from __future__ import annotations


def run_cursor_transcript_sync_from_fs_paths(runtime, raw_paths: set[str]) -> None:
    """生パス集合 → ワークスペース配下の transcript JSONL に絞り込み → 各エージェントのメッセージ同期。"""
    from native_log_sync.cursor.log_location import (
        expand_fsevent_paths_to_transcript_jsonl,
        sync_cursor_transcript_paths,
    )

    jsonl_paths = expand_fsevent_paths_to_transcript_jsonl(runtime, raw_paths)
    if jsonl_paths:
        sync_cursor_transcript_paths(runtime, jsonl_paths)
