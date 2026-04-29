"""Temporary Codex-only backstop for native log sync.

This exception should go away once native_log_sync moves to a lower-level
watching system that reliably observes Codex appends without polling.
"""

from __future__ import annotations

import fcntl
import logging
import os
import threading
import time

from native_log_sync.agents._shared.path_state import _normalized_native_log_path
from native_log_sync.io.state_paths import canonical_native_log_sync_lock_path

_POLL_INTERVAL_SECONDS = 0.25
_SEND_PREFLIGHT_LOCK_ATTEMPTS = 12


def start_codex_running_backstop(runtime, agent: str) -> None:
    """Codex-only exception: poll only while a Codex turn is marked running."""
    if str(agent or "").split("-", 1)[0] != "codex":
        return

    lock = getattr(runtime, "_codex_running_backstop_lock", None)
    if lock is None:
        lock = threading.Lock()
        runtime._codex_running_backstop_lock = lock

    with lock:
        active = getattr(runtime, "_codex_running_backstop_active", None)
        if active is None:
            active = set()
            runtime._codex_running_backstop_active = active
        if agent in active:
            return
        active.add(agent)

    thread = threading.Thread(
        target=_run_codex_running_backstop,
        args=(runtime, agent),
        daemon=True,
        name=f"codex-native-log-backstop:{agent}",
    )
    thread.start()


def flush_codex_pending_before_send(runtime, agent: str) -> None:
    """Flush stale Codex bytes before a new turn is marked running."""
    if str(agent or "").split("-", 1)[0] != "codex":
        return
    binding = getattr(runtime, "_native_log_bindings_by_agent", {}).get(agent)
    path = str(getattr(binding, "path", "") or "").strip() if binding is not None else ""
    if not path or not _codex_log_has_pending_data(runtime, agent, path):
        return
    _sync_codex_under_native_log_lock(
        runtime,
        agent,
        path,
        lock_attempts=_SEND_PREFLIGHT_LOCK_ATTEMPTS,
    )


def _run_codex_running_backstop(runtime, agent: str) -> None:
    try:
        while agent in getattr(runtime, "_agent_running", set()):
            binding = getattr(runtime, "_native_log_bindings_by_agent", {}).get(agent)
            path = str(getattr(binding, "path", "") or "").strip() if binding is not None else ""
            if path and _codex_log_has_pending_data(runtime, agent, path):
                _sync_codex_under_native_log_lock(runtime, agent, path)
            if agent not in getattr(runtime, "_agent_running", set()):
                break
            time.sleep(_POLL_INTERVAL_SECONDS)
    finally:
        lock = getattr(runtime, "_codex_running_backstop_lock", None)
        active = getattr(runtime, "_codex_running_backstop_active", None)
        should_restart = agent in getattr(runtime, "_agent_running", set())
        if lock is not None and isinstance(active, set):
            with lock:
                active.discard(agent)
        if should_restart:
            start_codex_running_backstop(runtime, agent)


def _codex_log_has_pending_data(runtime, agent: str, path: str) -> bool:
    try:
        file_size = os.path.getsize(path)
    except OSError:
        return False

    cursor = getattr(runtime, "_codex_cursors", {}).get(agent)
    if cursor is None:
        return True

    cursor_path = str(getattr(cursor, "path", "") or "")
    if _normalized_native_log_path(cursor_path) != _normalized_native_log_path(path):
        return True

    try:
        return file_size > int(getattr(cursor, "offset", 0) or 0)
    except (TypeError, ValueError):
        return True


def _sync_codex_under_native_log_lock(
    runtime,
    agent: str,
    path: str,
    *,
    lock_attempts: int = 1,
) -> None:
    lock_fd = None
    attempts = max(1, int(lock_attempts))
    for _attempt in range(attempts):
        try:
            lock_fd = open(canonical_native_log_sync_lock_path(runtime.index_path.parent), "w")
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if lock_fd is not None:
                try:
                    lock_fd.close()
                except OSError:
                    pass
                lock_fd = None
            if _attempt + 1 < attempts:
                time.sleep(0.05)
    else:
        return

    try:
        if not _codex_log_has_pending_data(runtime, agent, path):
            return
        sync_method = getattr(runtime, "_sync_codex_native_log", None)
        if sync_method is None:
            return
        sync_method(agent, path)
    except Exception as exc:
        logging.error("Codex native log backstop sync failed for %s: %s", agent, exc)
    finally:
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()
        except OSError:
            pass
