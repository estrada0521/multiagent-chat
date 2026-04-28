"""Background JSONL / native-log sync tick (file lock + claim maintenance) for chat server."""

from __future__ import annotations

import fcntl
import time

from native_log_sync.sync_timing import (
    JSONL_SYNC_ACTIVE_AGENTS_CACHE_SEC,
    JSONL_SYNC_INTERVAL_SEC,
    SYNC_STATE_HEARTBEAT_SEC,
)


def run_periodic_jsonl_sync_loop(runtime) -> None:
    """Match previous server._periodic_jsonl_sync: single long-running thread body."""
    active_agents_cache: list[str] = []
    active_agents_cache_at = 0.0
    time.sleep(1)
    while True:
        try:
            if not runtime.session_is_active:
                time.sleep(JSONL_SYNC_INTERVAL_SEC)
                continue

            lock_fd = None
            try:
                lock_fd = open(runtime.sync_lock_path, "w")
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, IOError):
                if lock_fd:
                    lock_fd.close()
                time.sleep(JSONL_SYNC_INTERVAL_SEC)
                continue

            try:
                try:
                    now = time.monotonic()
                    if now - active_agents_cache_at >= JSONL_SYNC_ACTIVE_AGENTS_CACHE_SEC:
                        active_agents_cache = runtime.active_agents()
                        active_agents_cache_at = now
                    active_agents = list(active_agents_cache)
                except Exception:
                    active_agents = []
                if active_agents:
                    try:
                        for agent in active_agents:
                            runtime._first_seen_for_agent(agent)
                    except Exception:
                        pass
                    try:
                        runtime.prune_sync_claims_to_active_agents(active_agents)
                    except Exception:
                        pass
                    try:
                        runtime.apply_recent_targeted_claim_handoffs(active_agents)
                    except Exception:
                        pass
                try:
                    runtime.maybe_heartbeat_sync_state(interval_seconds=SYNC_STATE_HEARTBEAT_SEC)
                except Exception:
                    pass
            finally:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(JSONL_SYNC_INTERVAL_SEC)
