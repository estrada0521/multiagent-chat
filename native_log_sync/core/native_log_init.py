"""共通: native log 解決の前準備（tmux pane・PID など）。

具体パス（どの JSONL / DB か）は各エージェントの `log_location` が知る。本モジュールは tmux / プロセス周りの共通部品だけをまとめる。
"""

from __future__ import annotations

from native_log_sync.core.native_file_resolve import pane_pid_opens_file, resolve_native_log_file
from native_log_sync.core.pane_tmux import cached_native_log_path, pane_field, pane_id_for_agent

__all__ = [
    "cached_native_log_path",
    "pane_field",
    "pane_id_for_agent",
    "pane_pid_opens_file",
    "resolve_native_log_file",
]
