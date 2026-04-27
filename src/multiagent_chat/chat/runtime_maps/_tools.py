"""Named tool → runtime label map (shared across tool-use agents).

Each entry in TOOL_MAP controls what the running indicator shows when an
agent calls a specific tool.

Entry format: tool_name → ToolEntry(label, mode, arg_keys, target_keys?)
  label       – Frontend canonical label: Read / Write / Edit / Search /
                Explore / Run / Delete / Thinking
  mode        – How to extract the detail text shown after the label:
                  "path"   : arg_keys → value displayed as workspace-relative path
                  "query"  : arg_keys → value displayed as-is
                  "search" : arg_keys → pattern; target_keys → optional location
                             displayed as "pattern in location"
  arg_keys    – Ordered list of JSON argument keys to try (first non-empty wins)
  target_keys – (search mode only) Keys for the search location

QUIET_TOOLS lists tools that never produce a runtime event.
"""
from __future__ import annotations

from typing import NamedTuple


class ToolEntry(NamedTuple):
    label: str
    mode: str
    arg_keys: list[str]
    target_keys: list[str] = []


TOOL_MAP: dict[str, ToolEntry] = {
    # ── File I/O ──────────────────────────────────────────────────────────
    "read":           ToolEntry("Read",    "path",   ["file_path", "path", "notebook_path"]),
    "notebookread":   ToolEntry("Read",    "path",   ["file_path", "path", "notebook_path"]),
    "write":          ToolEntry("Write",   "path",   ["file_path", "path"]),
    "edit":           ToolEntry("Edit",    "path",   ["file_path", "path"]),
    "notebookedit":   ToolEntry("Edit",    "path",   ["notebook_path", "path"]),
    # ── Discovery ─────────────────────────────────────────────────────────
    "glob":           ToolEntry("Explore", "query",  ["pattern"]),
    # ── Cursor / IDE-style names (not Claude exec_command) ─────────────────
    "semanticsearch": ToolEntry("Search", "query",  ["query"]),
    "strreplace":     ToolEntry("Edit",    "path",   ["path", "file_path"]),
    "delete":         ToolEntry("Delete",  "path",   ["path", "file_path"]),
    # ── Search ────────────────────────────────────────────────────────────
    "websearch":      ToolEntry("Search",  "query",  ["query", "q"]),
    "web_search":     ToolEntry("Search",  "query",  ["query", "q"]),
    "grep":           ToolEntry("Search",  "search", ["pattern", "q", "query"]),
    "ggrep":          ToolEntry("Search",  "search", ["pattern", "q", "query"]),
    "find":           ToolEntry("Search",  "search", ["pattern", "q", "query"], ["ref_id"]),
    "search_query":   ToolEntry("Search",  "search", ["pattern", "q", "query"], ["ref_id"]),
    # ── Fetch / browse ────────────────────────────────────────────────────
    "webfetch":       ToolEntry("Run",     "query",  ["url", "uri", "prompt"]),
    "web_fetch":      ToolEntry("Run",     "query",  ["url", "uri", "prompt"]),
    # ── Image / media ─────────────────────────────────────────────────────
    "view":           ToolEntry("Read",    "path",   ["path"]),
    "view_image":     ToolEntry("Read",    "path",   ["path"]),
    # ── MCP resources ─────────────────────────────────────────────────────
    "read_mcp_resource":           ToolEntry("Read",    "path",  ["uri", "ref_id", "path"]),
    "open":                        ToolEntry("Read",    "path",  ["uri", "ref_id", "path"]),
    "list_mcp_resources":          ToolEntry("Explore", "query", ["server"]),
    "list_mcp_resource_templates": ToolEntry("Explore", "query", ["server"]),
    # ── Sub-agents ────────────────────────────────────────────────────────
    "agent":          ToolEntry("Run",     "query",  ["description", "prompt"]),
}

QUIET_TOOLS: frozenset[str] = frozenset({"write_stdin", "todowrite", "todoread"})
