from __future__ import annotations

import os
import re
import sys
import unicodedata
from datetime import datetime as dt_datetime
from pathlib import Path
from typing import NamedTuple

from ...agents.names import agent_base_name as _agent_base_name
from ...agents.names import agent_instance_number as _agent_instance_number


def _workspace_slug_variants(path_value: str, *, include_lower: bool = False) -> list[str]:
    raw_slug = str(path_value or "").replace("/", "-").lstrip("-")
    if not raw_slug:
        return []
    variants: list[str] = []
    seen: set[str] = set()
    source_values: list[str] = []
    for candidate in (
        raw_slug,
        unicodedata.normalize("NFC", raw_slug),
        unicodedata.normalize("NFKC", raw_slug),
    ):
        if candidate not in source_values:
            source_values.append(candidate)
    for source in source_values:
        for candidate in (
            source,
            source.replace("_", "-"),
            re.sub(r"[^A-Za-z0-9.-]+", "-", source),
            re.sub(r"[^A-Za-z0-9.-]", "-", source),
            re.sub(r"[^A-Za-z0-9-]+", "-", source),
            re.sub(r"[^A-Za-z0-9-]", "-", source),
        ):
            trimmed = candidate.strip("-")
            compacted = re.sub(r"-+", "-", candidate).strip("-")
            for normalized in (trimmed, compacted):
                if not normalized:
                    continue
                output_candidates = (normalized, normalized.lower()) if include_lower else (normalized,)
                for output in output_candidates:
                    if output and output not in seen:
                        seen.add(output)
                        variants.append(output)
    return variants


def _native_path_claim_key(path: str | Path, *, stat_result: os.stat_result | None = None) -> str:
    """Return a comparison key for native-log paths.

    Path strings can differ while still referring to the same file (symlinks,
    ``/tmp`` vs ``/private/tmp``, case-variant spellings on case-insensitive
    filesystems). Use inode identity when available; otherwise fall back to a
    normalized lexical key.
    """
    raw = str(path or "").strip()
    if not raw:
        return ""
    if stat_result is not None:
        return f"inode:{stat_result.st_dev}:{stat_result.st_ino}"
    candidate = Path(raw).expanduser()
    try:
        st = candidate.stat()
        return f"inode:{st.st_dev}:{st.st_ino}"
    except OSError:
        normalized = str(candidate)
        if sys.platform == "darwin":
            normalized = normalized.lower()
        return f"path:{normalized}"


def _path_within_roots(path: str | Path, roots: list[Path]) -> bool:
    candidate = str(path or "").strip()
    if not candidate or not roots:
        return False
    candidate_real = os.path.realpath(candidate)
    candidate_cmp = candidate_real.lower() if sys.platform == "darwin" else candidate_real
    for root in roots:
        root_real = os.path.realpath(str(root))
        root_cmp = root_real.lower() if sys.platform == "darwin" else root_real
        root_prefix = root_cmp.rstrip(os.sep) + os.sep
        if candidate_cmp == root_cmp or candidate_cmp.startswith(root_prefix):
            return True
    return False


class NativeLogCursor(NamedTuple):
    """Per-agent pointer into a native CLI log file.

    ``path`` is the absolute file path the cursor is bound to; ``offset`` is
    the number of bytes of that file already consumed. A cursor is *bound* to
    a specific file path: when the path changes for an agent (e.g. new CLI
    session or new instance claimed it), the caller must anchor the cursor
    to the new file's current end rather than re-reading from byte 0.
    """

    path: str
    offset: int


class OpenCodeCursor(NamedTuple):
    """OpenCode uses a SQLite DB, so we track session_id + last message id."""

    session_id: str
    last_msg_id: str


def _coerce_native_cursor(raw: object) -> NativeLogCursor | None:
    """Migrate a persisted cursor value to ``NativeLogCursor``.

    The sync-state file stores cursors as JSON. Historic versions stored:
      * a bare ``int`` (offset only; no path binding — unsafe to keep)
      * a 2-element list/tuple ``[path, offset]``

    Bare ints are discarded (returns ``None``) so the syncer will re-anchor
    on the next call instead of reading from a meaningless offset.
    """
    if isinstance(raw, NativeLogCursor):
        return raw
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        path, offset = raw
        if isinstance(path, str) and isinstance(offset, int):
            return NativeLogCursor(path=path, offset=offset)
    return None


def _coerce_opencode_cursor(raw: object) -> OpenCodeCursor | None:
    if isinstance(raw, OpenCodeCursor):
        return raw
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        session_id, msg_id = raw
        if isinstance(session_id, str) and isinstance(msg_id, str):
            return OpenCodeCursor(session_id=session_id, last_msg_id=msg_id)
    return None


def _load_cursor_dict(raw: object) -> dict[str, NativeLogCursor]:
    """Load a per-agent cursor dict from persisted state, discarding invalid entries."""
    result: dict[str, NativeLogCursor] = {}
    if isinstance(raw, dict):
        for agent, value in raw.items():
            if not isinstance(agent, str):
                continue
            cursor = _coerce_native_cursor(value)
            if cursor is not None:
                result[agent] = cursor
    return result


def _load_opencode_dict(raw: object) -> dict[str, OpenCodeCursor]:
    result: dict[str, OpenCodeCursor] = {}
    if isinstance(raw, dict):
        for agent, value in raw.items():
            if not isinstance(agent, str):
                continue
            cursor = _coerce_opencode_cursor(value)
            if cursor is not None:
                result[agent] = cursor
    return result


def _cursor_dict_to_json(cursors: dict[str, NativeLogCursor]) -> dict[str, list]:
    return {agent: [c.path, c.offset] for agent, c in cursors.items()}


def _opencode_dict_to_json(cursors: dict[str, OpenCodeCursor]) -> dict[str, list]:
    return {agent: [c.session_id, c.last_msg_id] for agent, c in cursors.items()}


def _dedup_cursor_claims(
    cursors: dict[str, NativeLogCursor],
) -> dict[str, NativeLogCursor]:
    """Remove duplicate path claims, keeping the alphabetically-first agent per path.

    When stale state or bugs cause two agents to point at the same file,
    messages from that file get attributed to whichever agent syncs first —
    causing the "qwen-1 messages show as qwen-2" bug. This helper runs at
    load time and evicts the later-named duplicates so the displaced agents
    re-discover their own files on the next sync tick.
    """
    path_to_agent: dict[str, str] = {}
    out: dict[str, NativeLogCursor] = {}
    for agent in sorted(cursors):
        cursor = cursors[agent]
        claim_key = _native_path_claim_key(cursor.path)
        if claim_key in path_to_agent:
            continue
        path_to_agent[claim_key] = agent
        out[agent] = cursor
    return out


def _parse_iso_timestamp_epoch(raw: str) -> float | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return dt_datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _pick_latest_unclaimed(
    candidates: list[Path],
    cursors: dict[str, NativeLogCursor],
    agent: str,
    min_mtime: float = 0.0,
    *,
    exclude_paths: set[str] | None = None,
) -> Path | None:
    """Return the most-recently-modified candidate not claimed by another agent.

    ``cursors`` maps agent name -> NativeLogCursor (may include the caller).
    Files already claimed by *other* agents in the same dict are skipped.
    ``min_mtime``: candidates with ``st_mtime < min_mtime`` are excluded.
    Pass the agent's ``first_seen_ts`` here so that pre-existing files
    (which may belong to some other CLI instance) don't get silently
    claimed before we can prove the agent actually wrote to them.

    Returns ``None`` when nothing qualifies. Callers should *not* retry
    with a relaxed filter — the right behavior in that case is to wait
    for the agent's CLI to touch a file, whose mtime will then exceed
    ``min_mtime`` and make it eligible on the next poll.
    """
    if not candidates:
        return None
    claimed: set[str] = set()
    if exclude_paths:
        normalize_exclude = {_native_path_claim_key(p) for p in exclude_paths}
    else:
        normalize_exclude = set()
    for other_agent, cursor in cursors.items():
        if other_agent == agent:
            continue
        claimed.add(_native_path_claim_key(cursor.path))
    eligible: list[tuple[float, Path]] = []
    seen_candidate_keys: set[str] = set()
    for candidate in candidates:
        try:
            st = candidate.stat()
            mtime = st.st_mtime
        except OSError:
            continue
        if mtime < min_mtime:
            continue
        candidate_key = _native_path_claim_key(candidate, stat_result=st)
        if candidate_key in claimed or candidate_key in normalize_exclude:
            continue
        if candidate_key in seen_candidate_keys:
            continue
        seen_candidate_keys.add(candidate_key)
        eligible.append((mtime, candidate))
    if not eligible:
        return None
    eligible.sort(key=lambda item: item[0], reverse=True)
    return eligible[0][1]


def _pick_latest_unclaimed_for_agent(
    candidates: list[Path],
    cursors: dict[str, NativeLogCursor],
    agent: str,
    min_mtime: float,
    *,
    exclude_paths: set[str] | None = None,
) -> Path | None:
    return _pick_latest_unclaimed(
        candidates,
        cursors,
        agent,
        min_mtime=min_mtime,
        exclude_paths=exclude_paths,
    )


def _advance_native_cursor(
    cursors: dict[str, NativeLogCursor],
    agent: str,
    current_path: str,
    file_size: int,
) -> int | None:
    """Decide whether to read from ``current_path`` and return the start offset.

    Returns ``None`` when no processing is needed (first sight of this path,
    or no new bytes since last sync). Returns ``0`` on detected truncation.
    When a non-None offset is returned, the *caller* must persist the new
    cursor ``(current_path, file_size)`` after it finishes reading — this
    keeps cursor advance and the actual read coupled in the caller.
    """
    prev = cursors.get(agent)
    prev_key = _native_path_claim_key(prev.path) if prev is not None else ""
    current_key = _native_path_claim_key(current_path)
    if prev is None or prev_key != current_key:
        cursors[agent] = NativeLogCursor(path=current_path, offset=file_size)
        return None
    if file_size < prev.offset:
        return 0
    if file_size == prev.offset:
        return None
    return prev.offset


def _cursor_binding_changed(
    before: NativeLogCursor | None,
    after: NativeLogCursor | None,
) -> bool:
    if before is None and after is None:
        return False
    if before is None or after is None:
        return True
    return (
        _native_path_claim_key(before.path) != _native_path_claim_key(after.path)
        or before.offset != after.offset
    )
