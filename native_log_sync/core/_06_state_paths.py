"""
Where native log sync persists per-session state on disk.

This package owns the canonical filenames. Files live next to the session
agent-index JSONL only as a deployment anchor (same directory as the hub index);
the format and lifecycle are defined in native_log_sync (see sync_state.py).

Legacy name ``.agent-index-sync-state.json`` is migrated automatically on load.
"""

from __future__ import annotations

from pathlib import Path

# Canonical (current)
NATIVE_LOG_SYNC_STATE_FILENAME = ".native-log-sync-state.json"
NATIVE_LOG_SYNC_LOCK_FILENAME = ".native-log-sync.lock"

# Historical — migrated on read
LEGACY_AGENT_INDEX_SYNC_STATE_FILENAME = ".agent-index-sync-state.json"
LEGACY_AGENT_INDEX_SYNC_LOCK_FILENAME = ".agent-index-sync.lock"


def session_dir_for_index(index_path: Path) -> Path:
    return Path(index_path).resolve().parent


def canonical_native_log_sync_state_path(session_dir: Path | str) -> Path:
    return Path(session_dir).resolve() / NATIVE_LOG_SYNC_STATE_FILENAME


def legacy_agent_index_sync_state_path(session_dir: Path | str) -> Path:
    return Path(session_dir).resolve() / LEGACY_AGENT_INDEX_SYNC_STATE_FILENAME


def canonical_native_log_sync_lock_path(session_dir: Path | str) -> Path:
    return Path(session_dir).resolve() / NATIVE_LOG_SYNC_LOCK_FILENAME


def legacy_agent_index_sync_lock_path(session_dir: Path | str) -> Path:
    return Path(session_dir).resolve() / LEGACY_AGENT_INDEX_SYNC_LOCK_FILENAME
