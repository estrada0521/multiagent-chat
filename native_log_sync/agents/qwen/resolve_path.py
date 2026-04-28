from __future__ import annotations

import os
from pathlib import Path

from native_log_sync.agents._shared.resolve_path import path_within_roots, pick_latest_unclaimed_for_agent, workspace_slug_variants


def resolve_qwen_chat_jsonl_path(runtime, agent: str, native_log_path: str | None) -> str:
    workspace_text = str(runtime.workspace or "").strip()
    if not workspace_text:
        return ""

    roots: list[Path] = []
    seen_roots: set[str] = set()
    for alias in runtime._workspace_aliases(workspace_text):
        for slug in workspace_slug_variants(alias, include_lower=True):
            root = Path.home() / ".qwen" / "projects" / f"-{slug}" / "chats"
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

    candidates: list[Path] = []
    for root in roots:
        candidates.extend(root.glob("*.jsonl"))
    picked = pick_latest_unclaimed_for_agent(candidates, runtime._qwen_cursors, agent)
    return str(picked) if picked and picked.exists() else ""
