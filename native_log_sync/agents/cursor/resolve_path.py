from __future__ import annotations

import os
from pathlib import Path

from native_log_sync.agents._shared.resolve_path import pick_latest_unclaimed_for_agent
from native_log_sync.agents._shared.workspace_paths import cursor_transcript_roots


def resolve_cursor_session_jsonl_path(
    runtime,
    agent: str,
    native_log_path: str | None,
    *,
    first_seen_grace_seconds: float,
) -> str:
    """Resolve Cursor agent-transcripts JSONL like other agents: workspace-scoped glob + claims."""
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    ws = str(runtime.workspace or "").strip()
    if not ws:
        return ""
    session_path_str = str(Path(native_log_path)) if native_log_path else ""
    if not session_path_str:
        cursor = runtime._cursor_cursors.get(agent)
        if (
            cursor
            and cursor.path
            and os.path.exists(cursor.path)
            and runtime._should_stick_to_existing_cursor(agent)
            and transcript_jsonl_matches_workspace(runtime, cursor.path)
        ):
            session_path_str = cursor.path
        else:
            candidates: list[Path] = []
            for root in cursor_transcript_roots(runtime, ws):
                candidates.extend(root.glob("*.jsonl"))
                candidates.extend(root.glob("*/*.jsonl"))
            if not candidates:
                return ""
            min_mtime = runtime._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
            session_path = pick_latest_unclaimed_for_agent(
                candidates,
                runtime._cursor_cursors,
                agent,
                min_mtime=min_mtime,
                exclude_paths=set(runtime._collect_global_native_log_claims().keys()),
            )
            if session_path is None:
                return ""
            session_path_str = str(session_path)
    elif runtime._is_globally_claimed_path(session_path_str):
        return ""
    if not os.path.exists(session_path_str):
        return ""
    return session_path_str


def _workspace_cursor_project_prefixes(runtime) -> list[str]:
    ws = str(runtime.workspace or "").strip()
    if not ws:
        return []
    prefixes: list[str] = []
    seen: set[str] = set()
    for root in cursor_transcript_roots(runtime, ws):
        proj = root.parent
        try:
            s = str(proj.resolve())
        except OSError:
            s = str(proj)
        if s not in seen:
            seen.add(s)
            prefixes.append(s)
    if prefixes:
        return prefixes
    for pv in runtime._workspace_aliases(ws):
        slug = str(pv).replace("/", "-").lstrip("-")
        if not slug:
            continue
        base = Path.home() / ".cursor" / "projects" / slug
        try:
            s = str(base.resolve())
        except OSError:
            s = str(base)
        if s not in seen:
            seen.add(s)
            prefixes.append(s)
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
