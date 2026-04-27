"""Cursor 専用: 実ログに出現する tool 名だけ（添付 transcript 集計に基づく）。

他エージェント用のエントリは置かない。未定義ツールは core 側で「Run …」フォールバック。
"""

from __future__ import annotations

from native_log_sync.core.tool_entry import ToolEntry

# 実ログ（c90c7d1b 系 transcript 2本）に出現した名前の小文字化キーのみ。
TOOL_MAP: dict[str, ToolEntry] = {
    "grep": ToolEntry("Search", "search", ["pattern", "q", "query"], ["path", "dir_path"]),
    "strreplace": ToolEntry("Edit", "path", ["path", "file_path"]),
    "write": ToolEntry("Write", "path", ["path", "file_path"]),
    "delete": ToolEntry("Delete", "path", ["path", "file_path"]),
    "websearch": ToolEntry("Search", "query", ["search_term", "query", "q"]),
}

# ログにはあるがランタイムには出さない
QUIET_TOOLS: frozenset[str] = frozenset({"todowrite"})
