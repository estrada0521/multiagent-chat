"""Dispatch Cursor agent-transcript sync from resolved .jsonl paths (FSEvents / fallback)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from multiagent_chat.chat.runtime_parse import pane_pid_opens_file
from multiagent_chat.chat.sync.cursor import _native_path_claim_key
from multiagent_chat.chat.sync.loop import _pane_field, _pane_id_for_agent


def _cursor_base(agent: str) -> str:
    return (agent or "").lower().split("-")[0]


def _active_cursor_agents(runtime) -> list[str]:
    return [a for a in runtime.active_agents() if _cursor_base(a) == "cursor"]


def _workspace_cursor_project_prefixes(runtime) -> list[str]:
    ws = str(runtime.workspace or "").strip()
    if not ws:
        return []
    prefixes: list[str] = []
    for pv in runtime._workspace_aliases(ws):
        slug = str(pv).replace("/", "-").lstrip("-")
        if not slug:
            continue
        base = Path.home() / ".cursor" / "projects" / slug
        try:
            prefixes.append(str(base.resolve()))
        except OSError:
            prefixes.append(str(base))
    return prefixes


def path_under_workspace_cursor_projects(runtime, path: str) -> bool:
    try:
        rp = os.path.realpath(str(path))
    except OSError:
        return False
    for prefix in _workspace_cursor_project_prefixes(runtime):
        if rp == prefix or rp.startswith(prefix + os.sep):
            return True
    return False


def transcript_jsonl_matches_workspace(runtime, path: str) -> bool:
    try:
        rp = os.path.realpath(str(path))
    except OSError:
        return False
    if not rp.endswith(".jsonl"):
        return False
    return path_under_workspace_cursor_projects(runtime, rp)


def expand_fsevent_paths_to_transcript_jsonl(runtime, paths: set[str]) -> set[str]:
    """FSEvents often reports a parent directory; map those to concrete ``*.jsonl`` transcript files."""
    if not paths:
        return set()
    out: set[str] = set()
    for raw in paths:
        try:
            rp = os.path.realpath(str(raw))
        except OSError:
            continue
        if not path_under_workspace_cursor_projects(runtime, rp):
            continue
        p = Path(rp)
        if p.is_file() and rp.endswith(".jsonl"):
            out.add(rp)
            continue
        if p.is_dir():
            try:
                for jsonl in p.rglob("*.jsonl"):
                    try:
                        if jsonl.is_file():
                            jrp = str(jsonl.resolve())
                            if path_under_workspace_cursor_projects(runtime, jrp):
                                out.add(jrp)
                    except OSError:
                        continue
            except OSError:
                continue
    return out


def _agents_bound_to_transcript(runtime, cursor_agents: list[str], transcript_path: str) -> list[str]:
    key = _native_path_claim_key(transcript_path)
    out: list[str] = []
    for agent in cursor_agents:
        cur = runtime._cursor_cursors.get(agent)
        if cur and cur.path and _native_path_claim_key(cur.path) == key:
            out.append(agent)
    return out


def _agents_whose_pane_opens_transcript(
    runtime, cursor_agents: list[str], transcript_path: str
) -> list[str]:
    out: list[str] = []
    for agent in cursor_agents:
        pane_id = _pane_id_for_agent(runtime, agent)
        if not pane_id:
            continue
        pane_pid = _pane_field(runtime, pane_id, "#{pane_pid}")
        if pane_pid and pane_pid_opens_file(str(pane_pid).strip(), transcript_path):
            out.append(agent)
    return out


def sync_cursor_transcript_paths(runtime, paths: set[str]) -> None:
    """Ingest new assistant lines from transcript paths; *paths* are absolute filesystem paths."""
    cursor_agents = _active_cursor_agents(runtime)
    if not cursor_agents:
        return
    for raw in paths:
        path = os.path.realpath(str(raw))
        if not transcript_jsonl_matches_workspace(runtime, path):
            continue
        bound = _agents_bound_to_transcript(runtime, cursor_agents, path)
        targets = bound if bound else _agents_whose_pane_opens_transcript(runtime, cursor_agents, path)
        if not targets and len(cursor_agents) == 1:
            targets = list(cursor_agents)
        if not targets:
            continue
        for agent in targets:
            try:
                runtime._sync_cursor_assistant_messages(agent, path)
            except Exception as exc:
                logging.error("Cursor transcript sync failed for %s: %s", agent, exc)
