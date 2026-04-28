from __future__ import annotations

import json
import os
from pathlib import Path

from native_log_sync.agents._shared.resolve_path import pick_latest_unclaimed_for_agent


def resolve_codex_rollout_jsonl_path(runtime, agent: str, native_log_path: str | None) -> str:
    resolved = str(Path(native_log_path)) if native_log_path else ""
    if resolved and os.path.exists(resolved):
        return resolved

    cursor = runtime._codex_cursors.get(agent)
    if cursor and cursor.path and os.path.exists(cursor.path):
        return cursor.path

    workspace_aliases = set(runtime._workspace_aliases(str(runtime.workspace or "").strip()))
    if not workspace_aliases:
        return ""

    sessions_root = Path.home() / ".codex" / "sessions"
    if not sessions_root.is_dir():
        return ""

    candidates: list[Path] = []
    for candidate in sessions_root.glob("*/*/*/rollout-*.jsonl"):
        try:
            with candidate.open("r", encoding="utf-8", errors="replace") as handle:
                first_line = handle.readline().strip()
            if not first_line:
                continue
            payload = json.loads(first_line)
            if payload.get("type") != "session_meta":
                continue
            cwd = str((payload.get("payload") or {}).get("cwd") or "").strip()
            if not cwd:
                continue
            candidate_aliases = {cwd}
            try:
                candidate_aliases.add(str(Path(cwd).resolve()))
            except Exception:
                pass
            if candidate_aliases.isdisjoint(workspace_aliases):
                continue
            candidates.append(candidate)
        except Exception:
            continue

    picked = pick_latest_unclaimed_for_agent(candidates, runtime._codex_cursors, agent)
    return str(picked) if picked and picked.exists() else ""
