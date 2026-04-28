from __future__ import annotations

import re
import subprocess
from pathlib import Path

from native_log_sync.agents._shared.workspace_paths import cursor_transcript_roots


_STORE_DB_RE = re.compile(r"/\.cursor/chats/[^/]+/([0-9a-f-]+)/store\.db(?:-wal|-shm)?$")


def _process_tree(pid: str) -> set[str]:
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,ppid"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except Exception:
        return {pid} if pid else set()
    children_map: dict[str, list[str]] = {}
    for line in out.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            child, parent = parts[0], parts[1]
            children_map.setdefault(parent, []).append(child)
    found = {pid} if pid else set()
    queue = [pid] if pid else []
    while queue:
        current = queue.pop(0)
        for child in children_map.get(current, []):
            if child not in found:
                found.add(child)
                queue.append(child)
    return found


def _cursor_store_paths_for_pid_tree(pane_pid: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for pid in sorted(_process_tree(str(pane_pid or "").strip())):
        if not pid:
            continue
        try:
            out = subprocess.run(
                ["lsof", "-p", pid],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        except Exception:
            continue
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            path = " ".join(parts[8:]).strip()
            if not path:
                continue
            if not _STORE_DB_RE.search(path):
                continue
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return paths


def resolve_cursor_session_jsonl_path(runtime, pane_pid: str) -> str:
    workspace_text = str(runtime.workspace or "").strip()
    if not workspace_text:
        return ""
    roots = cursor_transcript_roots(runtime, workspace_text)
    if not roots:
        return ""

    for store_path in _cursor_store_paths_for_pid_tree(pane_pid):
        match = _STORE_DB_RE.search(store_path)
        if not match:
            continue
        session_id = match.group(1)
        for root in roots:
            candidate = root / session_id / f"{session_id}.jsonl"
            if candidate.is_file():
                return str(candidate)
    return ""


def path_under_workspace_cursor_projects(runtime, path: str) -> bool:
    resolved = str(path or "").strip()
    if not resolved:
        return False
    for root in cursor_transcript_roots(runtime, str(runtime.workspace or "").strip()):
        project_root = root.parent
        prefix = str(project_root.resolve())
        if resolved == prefix or resolved.startswith(prefix + "/"):
            return True
    return False


def transcript_jsonl_matches_workspace(runtime, path: str) -> bool:
    resolved = str(path or "").strip()
    return resolved.endswith(".jsonl") and path_under_workspace_cursor_projects(runtime, resolved)
