from __future__ import annotations

import os
from pathlib import Path

from native_log_sync.agents._shared.resolve_path import path_within_roots, pick_latest_unclaimed_for_agent, workspace_slug_variants


def resolve_claude_session_jsonl_path(runtime, agent: str, native_log_path: str | None, workspace_hint: str | None) -> str:
    workspace_text = str(workspace_hint or runtime.workspace or "").strip()
    if not workspace_text:
        return ""

    roots: list[Path] = []
    seen_roots: set[str] = set()
    for alias in runtime._workspace_aliases(workspace_text):
        for slug in workspace_slug_variants(alias):
            root = Path.home() / ".claude" / "projects" / f"-{slug}"
            if not root.is_dir():
                continue
            key = str(root.resolve())
            if key in seen_roots:
                continue
            seen_roots.add(key)
            roots.append(root)
    if not roots:
        return ""

    resolved = str(Path(native_log_path)) if native_log_path else ""
    if resolved and path_within_roots(resolved, roots) and os.path.exists(resolved):
        return resolved

    cursor = runtime._claude_cursors.get(agent)
    if cursor and cursor.path and path_within_roots(cursor.path, roots) and os.path.exists(cursor.path):
        return cursor.path

    candidates: list[Path] = []
    for root in roots:
        candidates.extend(root.glob("*.jsonl"))
    picked = pick_latest_unclaimed_for_agent(candidates, runtime._claude_cursors, agent)
    return str(picked) if picked and picked.exists() else ""
