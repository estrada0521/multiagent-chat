"""Codex: ロールアウト native JSONL のパス解決。"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_codex_rollout_jsonl_path(runtime, agent: str, native_log_path: str | None) -> str:
    resolved = str(Path(native_log_path)) if native_log_path else ""
    if not resolved:
        cursor = runtime._codex_cursors.get(agent)
        if cursor and cursor.path and os.path.exists(cursor.path):
            resolved = cursor.path
        else:
            picked = runtime._pick_codex_rollout_for_agent(agent)
            if picked is None:
                return ""
            resolved = str(picked)
    if runtime._is_globally_claimed_path(resolved):
        return ""
    if not os.path.exists(resolved):
        return ""
    return resolved
