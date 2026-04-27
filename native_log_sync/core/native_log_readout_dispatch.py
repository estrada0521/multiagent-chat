"""共通: 解決済み native log パスからランタイム用イベントを組み立てる窓口。

ログ1行がツールか・どう表示するかは各エージェントの `log_readout_tools` に任せる（本モジュールは委譲のみ）。
フロント向けの最終形は `multiagent_chat.chat.runtime_format` 側の責務。
"""

from __future__ import annotations

from native_log_sync.claude.log_readout_tools import parse_jsonl_for_runtime as parse_claude_jsonl_for_runtime
from native_log_sync.codex.log_readout_tools import parse_native_codex_log
from native_log_sync.copilot.log_readout_tools import parse_jsonl_for_runtime as parse_copilot_jsonl_for_runtime
from native_log_sync.cursor.log_readout_tools import parse_jsonl_for_runtime as parse_cursor_jsonl_for_runtime
from native_log_sync.gemini.log_readout_tools import parse_native_gemini_log
from native_log_sync.opencode.log_readout_tools import parse_opencode_runtime
from native_log_sync.qwen.log_readout_tools import parse_jsonl_for_runtime as parse_qwen_jsonl_for_runtime

__all__ = [
    "parse_claude_jsonl_for_runtime",
    "parse_copilot_jsonl_for_runtime",
    "parse_cursor_jsonl_for_runtime",
    "parse_native_codex_log",
    "parse_native_gemini_log",
    "parse_opencode_runtime",
    "parse_qwen_jsonl_for_runtime",
]
