from __future__ import annotations

import logging
import os
from pathlib import Path

from native_log_sync.io.process_info import (
    enumerate_lsof_paths_matching_pattern_for_pids,
    get_process_tree,
    pane_pid_opens_file,
    pids_on_tty,
)
from native_log_sync.core._08_cursor_state import _native_path_claim_key

_CURSOR_AGENT_TRANSCRIPT_PATTERN = r"agent-transcripts[/\\].+\.jsonl$"
# Session dir layout: agent-transcripts/<uuid>/store.db + <uuid>.jsonl (jsonl fd often absent from lsof)
_CURSOR_SESSION_STORE_DB_PATTERN = r"agent-transcripts[/\\][^/\\]+[/\\]store\.db$"


def _transcript_jsonl_next_to_store_db(store_db_path: str) -> str:
    """Given .../agent-transcripts/<sessionId>/store.db → .../<sessionId>/<sessionId>.jsonl if present."""
    try:
        p = Path(store_db_path).resolve()
        parent = p.parent
        sid = parent.name
        cand = parent / f"{sid}.jsonl"
        if cand.is_file():
            return str(cand)
    except OSError:
        pass
    return ""


def _cursor_nested_transcript_preference(path: str) -> int:
    """Prefer Cursor layout agent-transcripts/<uuid>/<uuid>.jsonl over flat file names."""
    try:
        p = Path(path)
        if p.suffix != ".jsonl":
            return 0
        if p.stem == p.parent.name:
            return 1
    except Exception:
        pass
    return 0


def resolve_cursor_transcript_open_in_pane(runtime, agent: str) -> str:
    """Resolve transcript jsonl for this pane: prefer active session via store.db, then jsonl fds (lsof)."""
    from native_log_sync.agents.cursor.host_pids import pids_running_cursor_app

    pane_id = runtime.pane_id_for_agent(agent)
    if not pane_id:
        return ""
    pane_pid = runtime.pane_field(pane_id, "#{pane_pid}")
    pid_str = str(pane_pid).strip()
    if not pid_str:
        return ""

    merged_pids = set(get_process_tree(pid_str))
    merged_pids.add(pid_str)
    merged_pids |= pids_on_tty(runtime.pane_field(pane_id, "#{pane_tty}"))
    merged_pids |= pids_running_cursor_app()

    store_rows = enumerate_lsof_paths_matching_pattern_for_pids(
        merged_pids, _CURSOR_SESSION_STORE_DB_PATTERN
    )
    store_rows.sort(key=lambda item: -item[0])
    for _mtime, store_path in store_rows:
        if not path_under_workspace_cursor_projects(runtime, store_path):
            continue
        derived = _transcript_jsonl_next_to_store_db(store_path)
        if derived and transcript_jsonl_matches_workspace(runtime, derived):
            runtime._pane_native_log_paths[pane_id] = (pid_str, derived)
            return derived

    rows = enumerate_lsof_paths_matching_pattern_for_pids(merged_pids, _CURSOR_AGENT_TRANSCRIPT_PATTERN)
    if not rows:
        return ""
    rows.sort(key=lambda item: (-_cursor_nested_transcript_preference(item[1]), -item[0]))
    for _mtime, cand in rows:
        if transcript_jsonl_matches_workspace(runtime, cand):
            runtime._pane_native_log_paths[pane_id] = (pid_str, cand)
            return cand
    return ""


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
        pane_id = runtime.pane_id_for_agent(agent)
        if not pane_id:
            continue
        pane_pid = runtime.pane_field(pane_id, "#{pane_pid}")
        if pane_pid and pane_pid_opens_file(str(pane_pid).strip(), transcript_path):
            out.append(agent)
    return out


def sync_cursor_transcript_paths(runtime, paths: set[str]) -> None:
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
