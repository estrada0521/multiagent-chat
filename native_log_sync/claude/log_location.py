from __future__ import annotations

import os
from pathlib import Path

from native_log_sync.core._08_cursor_state import (
    _pick_latest_unclaimed_for_agent,
    _workspace_slug_variants,
)


def resolve_claude_session_jsonl_path(
    runtime,
    agent: str,
    native_log_path: str | None,
    workspace_hint: str | None,
    *,
    first_seen_grace_seconds: float,
) -> str:
    _FIRST_SEEN_GRACE_SECONDS = float(first_seen_grace_seconds)
    session_path_str = str(Path(native_log_path)) if native_log_path else ""
    if not session_path_str:
        cursor = runtime._claude_cursors.get(agent)
        if (
            cursor
            and cursor.path
            and os.path.exists(cursor.path)
            and runtime._should_stick_to_existing_cursor(agent)
        ):
            session_path_str = cursor.path
        else:
            jsonl_candidates: list[Path] = []
            seen_dirs: set[Path] = set()

            def _add_workspace_candidates(workspace: str | None) -> None:
                ws = str(workspace or "").strip()
                if not ws:
                    return
                candidate_paths = [ws]
                git_root = runtime._workspace_git_root(ws)
                if git_root and git_root != ws:
                    candidate_paths.append(git_root)
                for candidate_path in candidate_paths:
                    for slug in _workspace_slug_variants(candidate_path):
                        workspace_dir = Path.home() / ".claude" / "projects" / f"-{slug}"
                        if workspace_dir in seen_dirs or not workspace_dir.exists():
                            continue
                        seen_dirs.add(workspace_dir)
                        jsonl_candidates.extend(workspace_dir.glob("*.jsonl"))

            hint_workspace = str(workspace_hint or "").strip()
            session_workspace = str(runtime.workspace or "").strip()
            prefer_session_then_hint = False
            if hint_workspace and session_workspace:
                try:
                    hint_resolved = str(Path(hint_workspace).resolve())
                except Exception:
                    hint_resolved = hint_workspace
                try:
                    session_resolved = str(Path(session_workspace).resolve())
                except Exception:
                    session_resolved = session_workspace
                if session_resolved.startswith(hint_resolved.rstrip("/") + "/"):
                    prefer_session_then_hint = True
            if prefer_session_then_hint:
                _add_workspace_candidates(session_workspace)
            else:
                if hint_workspace and session_workspace:
                    if session_workspace == hint_workspace:
                        _add_workspace_candidates(session_workspace)
                    else:
                        _add_workspace_candidates(hint_workspace)
                        _add_workspace_candidates(session_workspace)
                else:
                    _add_workspace_candidates(hint_workspace)
                    _add_workspace_candidates(session_workspace)

            cursor = runtime._claude_cursors.get(agent)
            if cursor and cursor.path:
                cursor_dir = Path(cursor.path).parent
                if cursor_dir not in seen_dirs and cursor_dir.exists():
                    seen_dirs.add(cursor_dir)
                    jsonl_candidates.extend(cursor_dir.glob("*.jsonl"))

            if not jsonl_candidates:
                return ""
            min_mtime = runtime._first_seen_for_agent(agent) - _FIRST_SEEN_GRACE_SECONDS
            session_path = _pick_latest_unclaimed_for_agent(
                jsonl_candidates,
                runtime._claude_cursors,
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
