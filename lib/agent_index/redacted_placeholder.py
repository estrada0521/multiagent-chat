"""Cursor transcript lines may contain the literal placeholder ``[REDACTED]``.

Sync skips rows that are only that token; trailing ``[REDACTED]`` is stripped.
This module centralizes that logic for chat index JSONL compaction and filtering.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path

REDACTED_TOKEN = "[REDACTED]"


def split_message_from_prefix(message: str) -> tuple[str, str]:
    """Split ``[From: name]\\nbody`` into ``(prefix_including_bracket_newline, body)``."""
    m = str(message or "")
    if not m.startswith("[From:"):
        return "", m
    idx = m.find("]\n")
    if idx == -1:
        return "", m
    return m[: idx + 2], m[idx + 2 :]


def normalize_cursor_plaintext_for_index(display: str) -> str | None:
    """Return text safe to store in the chat index, or None if the row should be skipped."""
    t = (display or "").strip()
    if not t:
        return None
    if t == REDACTED_TOKEN:
        return None
    if t.endswith(REDACTED_TOKEN):
        t = t[: -len(REDACTED_TOKEN)].rstrip()
    if not t:
        return None
    return t


def agent_index_entry_omit_for_redacted(message: str) -> bool:
    """True if the chat jsonl row is only a redacted placeholder (after ``[From:]`` body)."""
    _, body = split_message_from_prefix(message)
    b = (body or "").strip()
    if not b:
        return False
    return normalize_cursor_plaintext_for_index(b) is None


def rewrite_agent_index_message_strip_trailing_redacted(message: str) -> str | None:
    """Return message with trailing ``[REDACTED]`` removed from the body, or None if unchanged."""
    prefix, body = split_message_from_prefix(message)
    b = (body or "").rstrip()
    if not b.endswith(REDACTED_TOKEN):
        return None
    new_body = b[: -len(REDACTED_TOKEN)].rstrip()
    if not new_body:
        return None
    if prefix:
        return prefix + new_body
    return new_body


def compact_agent_index_jsonl(path: Path | str) -> tuple[int, int, int]:
    """Rewrite *path*: drop redacted-only lines; strip trailing ``[REDACTED]`` on others.

    Returns ``(lines_kept, lines_removed, lines_rewritten)``. No-op if nothing changes.
    Uses a lock compatible with :func:`jsonl_append.append_jsonl_entry`.
    """
    target = Path(path)
    if not target.is_file():
        return (0, 0, 0)

    out_lines: list[str] = []
    removed = 0
    rewritten = 0
    with target.open("r+", encoding="utf-8", errors="replace") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            for line in handle:
                if not line.strip():
                    continue
                raw = line.rstrip("\n\r")
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    out_lines.append(line if line.endswith("\n") else line + "\n")
                    continue
                if not isinstance(entry, dict):
                    out_lines.append(line if line.endswith("\n") else line + "\n")
                    continue
                msg = entry.get("message", "")
                if agent_index_entry_omit_for_redacted(str(msg)):
                    removed += 1
                    continue
                new_msg = rewrite_agent_index_message_strip_trailing_redacted(str(msg))
                if new_msg is not None:
                    entry["message"] = new_msg
                    rewritten += 1
                    out_lines.append(json.dumps(entry, ensure_ascii=False) + "\n")
                else:
                    out_lines.append(line if line.endswith("\n") else line + "\n")

            kept = len(out_lines)
            if removed == 0 and rewritten == 0:
                return (kept, 0, 0)

            handle.seek(0)
            handle.truncate()
            handle.writelines(out_lines)
            handle.flush()
            os.fsync(handle.fileno())
            return (kept, removed, rewritten)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
