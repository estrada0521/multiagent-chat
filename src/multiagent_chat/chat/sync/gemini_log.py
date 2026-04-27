from __future__ import annotations

import os
import time
from pathlib import Path

from .cursor import (
    NativeLogCursor,
    _parse_iso_timestamp_epoch,
    _path_within_roots,
    _pick_latest_unclaimed_for_agent,
    _workspace_slug_variants,
)
from ..thinking_kind import classify_gemini_message_kind


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
    """Resolve the path to the active Gemini native log (events.jsonl)."""
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

            strict_first_bind = (
                agent not in gemini_cursors
                and should_stick_to_existing_cursor
            )
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


def extract_gemini_message(entry: dict, min_event_ts: float | None = None) -> dict | None:
    """Extract a valid message or thought from a Gemini native log entry.

    Returns:
        dict: A dictionary containing 'msg_id', 'display_text', and 'is_thought'.
        None: If the entry is invalid, skipped, or older than min_event_ts.
    """
    if entry.get("type") != "gemini":
        return None
    if min_event_ts is not None:
        event_ts = _parse_iso_timestamp_epoch(str(entry.get("timestamp") or ""))
        if event_ts is None or event_ts < min_event_ts:
            return None
    msg_id = str(entry.get("id") or "")[:12]
    if not msg_id:
        return None

    content = entry.get("content", [])
    texts = []
    has_thought_part = False
    if isinstance(content, str):
        if content.strip():
            texts.append(content)
    elif isinstance(content, list):
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("thought") is True:
                has_thought_part = True
            text_raw = c.get("text")
            if text_raw:
                text = str(text_raw).strip()
                if text:
                    texts.append(text)

    if not texts:
        return None

    kind = classify_gemini_message_kind(texts, has_thought_part=has_thought_part)
    if kind == "agent-thinking":
        return {
            "msg_id": msg_id,
            "display_text": "",
            "is_thought": True,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    display = "\n".join(texts)
    return {
        "msg_id": msg_id,
        "display_text": display,
        "is_thought": False,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
