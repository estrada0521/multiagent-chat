from __future__ import annotations

import os
from pathlib import Path

from native_log_sync.agents._shared.path_state import _native_path_claim_key
from native_log_sync.agents._shared.resolve_path import path_within_roots, pick_latest_unclaimed_for_agent
from native_log_sync.agents._shared.workspace_paths import cursor_transcript_roots


def resolve_cursor_session_jsonl_path(runtime, agent: str, native_log_path: str | None) -> str:
    workspace_text = str(runtime.workspace or "").strip()
    if not workspace_text:
        return ""

    roots = cursor_transcript_roots(runtime, workspace_text)
    if not roots:
        return ""

    resolved = str(Path(native_log_path)) if native_log_path else ""
    if resolved and path_within_roots(resolved, roots) and os.path.exists(resolved):
        return resolved

    cursor = runtime._cursor_cursors.get(agent)
    if cursor and cursor.path and path_within_roots(cursor.path, roots) and os.path.exists(cursor.path):
        return cursor.path

    candidates: list[Path] = []
    for root in roots:
        candidates.extend(root.glob("*.jsonl"))
        candidates.extend(root.glob("*/*.jsonl"))
    picked = pick_latest_unclaimed_for_agent(candidates, runtime._cursor_cursors, agent)
    return str(picked) if picked and picked.exists() else ""


def _workspace_cursor_project_prefixes(runtime) -> list[str]:
    workspace_text = str(runtime.workspace or "").strip()
    if not workspace_text:
        return []
    prefixes: list[str] = []
    seen: set[str] = set()
    for root in cursor_transcript_roots(runtime, workspace_text):
        proj = root.parent
        key = str(proj.resolve())
        if key not in seen:
            seen.add(key)
            prefixes.append(key)
    return prefixes


def path_under_workspace_cursor_projects(runtime, path: str) -> bool:
    try:
        resolved = os.path.realpath(str(path))
    except OSError:
        return False
    for prefix in _workspace_cursor_project_prefixes(runtime):
        if resolved == prefix or resolved.startswith(prefix + os.sep):
            return True
    return False


def transcript_jsonl_matches_workspace(runtime, path: str) -> bool:
    try:
        resolved = os.path.realpath(str(path))
    except OSError:
        return False
    return resolved.endswith(".jsonl") and path_under_workspace_cursor_projects(runtime, resolved)


def expand_fsevent_paths_to_transcript_jsonl(runtime, raw_paths: set[str]) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    for raw_path in raw_paths:
        try:
            resolved = os.path.realpath(raw_path)
        except OSError:
            continue
        candidates: list[str] = []
        if os.path.isfile(resolved) and resolved.endswith(".jsonl"):
            candidates.append(resolved)
        elif os.path.isdir(resolved):
            for path in Path(resolved).glob("*.jsonl"):
                candidates.append(str(path))
            for path in Path(resolved).glob("*/*.jsonl"):
                candidates.append(str(path))
        else:
            parent = Path(resolved).parent
            if parent.is_dir():
                for path in parent.glob("*.jsonl"):
                    candidates.append(str(path))
        for candidate in candidates:
            if candidate in seen or not transcript_jsonl_matches_workspace(runtime, candidate):
                continue
            seen.add(candidate)
            matched.append(candidate)
    return matched


def sync_cursor_transcript_paths(runtime, jsonl_paths: list[str]) -> None:
    claim_keys = {_native_path_claim_key(path) for path in jsonl_paths if path}
    if not claim_keys:
        return
    for agent, binding in getattr(runtime, "_native_log_bindings_by_agent", {}).items():
        if getattr(binding, "base", "") != "cursor":
            continue
        if _native_path_claim_key(binding.path) not in claim_keys:
            continue
        runtime._sync_cursor_assistant_messages(agent, binding.path)
