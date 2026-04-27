"""Claude 用: ツール名→ランタイム表示（他エージェントとは独立に編集する）。"""

from __future__ import annotations

from native_log_sync.core.tool_entry import ToolEntry

TOOL_MAP: dict[str, ToolEntry] = {
    "read": ToolEntry("Read", "path", ["file_path", "path", "notebook_path"]),
    "read_file": ToolEntry("Read", "path", ["file_path", "path"]),
    "notebookread": ToolEntry("Read", "path", ["file_path", "path", "notebook_path"]),
    "write": ToolEntry("Write", "path", ["file_path", "path"]),
    "write_file": ToolEntry("Write", "path", ["file_path", "path"]),
    "edit": ToolEntry("Edit", "path", ["file_path", "path"]),
    "replace": ToolEntry("Edit", "path", ["file_path", "path"]),
    "notebookedit": ToolEntry("Edit", "path", ["notebook_path", "path"]),
    "glob": ToolEntry("Explore", "query", ["pattern"]),
    "list_directory": ToolEntry("Explore", "path", ["dir_path", "path"]),
    "semanticsearch": ToolEntry("Search", "query", ["query"]),
    "strreplace": ToolEntry("Edit", "path", ["path", "file_path"]),
    "delete": ToolEntry("Delete", "path", ["path", "file_path"]),
    "websearch": ToolEntry("Search", "query", ["query", "q"]),
    "web_search": ToolEntry("Search", "query", ["query", "q"]),
    "google_web_search": ToolEntry("Search", "query", ["query", "q"]),
    "grep": ToolEntry("Search", "search", ["pattern", "q", "query"], ["dir_path", "path"]),
    "grep_search": ToolEntry("Search", "search", ["pattern", "q", "query"], ["dir_path", "path"]),
    "ggrep": ToolEntry("Search", "search", ["pattern", "q", "query"], ["dir_path", "path"]),
    "find": ToolEntry("Search", "search", ["pattern", "q", "query"], ["dir_path", "path", "ref_id"]),
    "search_query": ToolEntry("Search", "search", ["pattern", "q", "query"], ["ref_id", "dir_path", "path"]),
    "webfetch": ToolEntry("Run", "query", ["url", "uri", "prompt"]),
    "web_fetch": ToolEntry("Run", "query", ["url", "uri", "prompt"]),
    "run_shell_command": ToolEntry("Run", "query", ["command", "cmd"]),
    "view": ToolEntry("Read", "path", ["path"]),
    "view_image": ToolEntry("Read", "path", ["path"]),
    "read_mcp_resource": ToolEntry("Read", "path", ["uri", "ref_id", "path"]),
    "open": ToolEntry("Read", "path", ["uri", "ref_id", "path"]),
    "list_mcp_resources": ToolEntry("Explore", "query", ["server"]),
    "list_mcp_resource_templates": ToolEntry("Explore", "query", ["server"]),
    "agent": ToolEntry("Run", "query", ["description", "prompt"]),
}

QUIET_TOOLS: frozenset[str] = frozenset({"write_stdin", "todowrite", "todoread"})
