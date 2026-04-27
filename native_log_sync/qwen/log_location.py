"""Qwen Code: ~/.qwen/projects/.../chats のセッション JSONL パスを解決する。"""

from __future__ import annotations

import os
from pathlib import Path

from multiagent_chat.chat.sync.cursor import (
    _path_within_roots,
    _pick_latest_unclaimed_for_agent,
    _workspace_slug_variants,
)


def resolve_qwen_chat_jsonl_path(
    runtime,
    agent: str,
    native_log_path: str | None,
    *,
    first_seen_grace_seconds: float,
) -> str:
    workspace_text = str(runtime.workspace or "").strip()
    if not workspace_text:
        return ""
    qwen_chat_dirs: list[Path] = []
    seen_qwen_dirs: set[Path] = set()

    def _add_qwen_chat_dirs(path_value: str) -> None:
        for slug in _workspace_slug_variants(path_value, include_lower=True):
            chats_dir = Path.home() / ".qwen" / "projects" / f"-{slug}" / "chats"
            if chats_dir.exists() and chats_dir not in seen_qwen_dirs:
                seen_qwen_dirs.add(chats_dir)
                qwen_chat_dirs.append(chats_dir)

    for alias in runtime._workspace_aliases(workspace_text):
        _add_qwen_chat_dirs(alias)
    if not qwen_chat_dirs:
        return ""

    chat_path_str = str(Path(native_log_path)) if native_log_path else ""
    if not chat_path_str:
        cursor = runtime._qwen_cursors.get(agent)
        if (
            cursor
            and cursor.path
            and os.path.exists(cursor.path)
            and runtime._should_stick_to_existing_cursor(agent)
            and _path_within_roots(cursor.path, qwen_chat_dirs)
        ):
            chat_path_str = cursor.path
        else:
            chat_candidates: list[Path] = []
            for qwen_chats_dir in qwen_chat_dirs:
                chat_candidates.extend(qwen_chats_dir.glob("*.jsonl"))
            first_seen_ts = runtime._first_seen_for_agent(agent)
            strict_first_bind = agent not in runtime._qwen_cursors and runtime._should_stick_to_existing_cursor(agent)
            min_mtime = first_seen_ts if strict_first_bind else first_seen_ts - float(first_seen_grace_seconds)
            picked = _pick_latest_unclaimed_for_agent(
                chat_candidates,
                runtime._qwen_cursors,
                agent,
                min_mtime=min_mtime,
                exclude_paths=set(runtime._collect_global_native_log_claims().keys()),
            )
            if picked is None:
                return ""
            chat_path_str = str(picked)
    elif runtime._is_globally_claimed_path(chat_path_str):
        return ""
    if not os.path.exists(chat_path_str):
        return ""
    return chat_path_str
