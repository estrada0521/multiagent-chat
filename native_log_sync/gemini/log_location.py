from __future__ import annotations

import os
from pathlib import Path

from multiagent_chat.chat.sync.cursor import (
    NativeLogCursor,
    _path_within_roots,
    _pick_latest_unclaimed_for_agent,
    _workspace_slug_variants,
)


def resolve_gemini_native_log(
    agent: str,
    workspace_aliases: list[str],
    native_log_path: str | None,
    gemini_cursors: dict[str, NativeLogCursor],
    should_stick_to_existing_cursor: bool,
    first_seen_ts: float,
    first_seen_grace_seconds: float,
    global_claimed_paths: set[str],
) -> str | None:
    gemini_chat_dirs: list[Path] = []
    seen_gemini_dirs: set[Path] = set()

    for alias in workspace_aliases:
        workspace_name = Path(str(alias or "")).name.strip()
        if not workspace_name:
            continue
        for variant in _workspace_slug_variants(workspace_name, include_lower=True):
            chats_dir = Path.home() / ".gemini" / "tmp" / variant / "chats"
            if chats_dir.exists() and chats_dir not in seen_gemini_dirs:
                seen_gemini_dirs.add(chats_dir)
                gemini_chat_dirs.append(chats_dir)

    if not gemini_chat_dirs:
        return None

    session_path_str = str(Path(native_log_path)) if native_log_path else ""
    if not session_path_str:
        cursor = gemini_cursors.get(agent)
        if (
            cursor
            and cursor.path
            and os.path.exists(cursor.path)
            and should_stick_to_existing_cursor
            and _path_within_roots(cursor.path, gemini_chat_dirs)
        ):
            session_path_str = cursor.path
        else:
            candidates: list[Path] = []
            for chats_dir in gemini_chat_dirs:
                candidates.extend(chats_dir.glob("*.jsonl"))

            strict_first_bind = agent not in gemini_cursors and should_stick_to_existing_cursor
            min_mtime = first_seen_ts if strict_first_bind else first_seen_ts - first_seen_grace_seconds

            picked = _pick_latest_unclaimed_for_agent(
                candidates,
                gemini_cursors,
                agent,
                min_mtime=min_mtime,
                exclude_paths=global_claimed_paths,
            )
            if picked is None:
                return None
            session_path_str = str(picked)
    elif session_path_str in global_claimed_paths:
        return None

    if not os.path.exists(session_path_str):
        return None

    return session_path_str
