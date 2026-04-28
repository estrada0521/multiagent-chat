from __future__ import annotations

import os
import subprocess
import time

_PANE_INFO_CACHE_TTL_SECONDS = 5.0


def _pane_info_cache(runtime) -> dict:
    cache = getattr(runtime, "_sync_pane_info_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(runtime, "_sync_pane_info_cache", cache)
    return cache


def _cached_value(runtime, key: tuple) -> str | None:
    cached = _pane_info_cache(runtime).get(key)
    if not cached:
        return None
    cached_at, value = cached
    if time.monotonic() - float(cached_at) >= _PANE_INFO_CACHE_TTL_SECONDS:
        _pane_info_cache(runtime).pop(key, None)
        return None
    return str(value or "")


def _store_cached_value(runtime, key: tuple, value: str) -> str:
    _pane_info_cache(runtime)[key] = (time.monotonic(), str(value or ""))
    return str(value or "")


def pane_id_for_agent(runtime, agent: str) -> str:
    cache_key = ("pane_id", agent)
    cached = _cached_value(runtime, cache_key)
    if cached is not None:
        return cached
    pane_var = f"MULTIAGENT_PANE_{agent.upper().replace('-', '_')}"
    result = subprocess.run(
        [*runtime.tmux_prefix, "show-environment", "-t", runtime.session_name, pane_var],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    line = result.stdout.strip()
    if result.returncode != 0 or "=" not in line:
        return _store_cached_value(runtime, cache_key, "")
    return _store_cached_value(runtime, cache_key, line.split("=", 1)[1].strip())


def pane_field(runtime, pane_id: str, field: str) -> str:
    if not pane_id:
        return ""
    cache_key = ("pane_field", pane_id, field)
    cached = _cached_value(runtime, cache_key)
    if cached is not None:
        return cached
    value = subprocess.run(
        [*runtime.tmux_prefix, "display-message", "-p", "-t", pane_id, field],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    ).stdout.strip()
    return _store_cached_value(runtime, cache_key, value)


def pids_on_pane_tty(runtime, pane_id: str) -> set[str]:
    """Process IDs sharing the pane's tty (captures Cursor/node helpers not under #{pane_pid}'s child tree)."""
    if not pane_id:
        return set()
    tty_raw = pane_field(runtime, pane_id, "#{pane_tty}")
    tty_raw = str(tty_raw or "").strip()
    if not tty_raw or tty_raw.lower() in ("not a tty", "/dev/not a tty"):
        return set()
    candidates = [tty_raw]
    if not tty_raw.startswith("/dev/"):
        candidates.append("/dev/" + tty_raw.lstrip("/"))
    pids: set[str] = set()
    for dev in candidates:
        proc = subprocess.run(
            ["ps", "-t", dev, "-o", "pid="],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            continue
        for line in proc.stdout.splitlines():
            word = line.strip()
            if word.isdigit():
                pids.add(word)
        if pids:
            return pids
    return set()


def cached_native_log_path(runtime, pane_id: str, pane_pid: str) -> str:
    cached_entry = runtime._pane_native_log_paths.get(pane_id)
    cached_pid = ""
    cached_path = ""
    if isinstance(cached_entry, tuple) and len(cached_entry) == 2:
        cached_pid = str(cached_entry[0] or "")
        cached_path = str(cached_entry[1] or "")
    elif isinstance(cached_entry, str):
        cached_path = cached_entry
    if cached_path and os.path.exists(cached_path) and (not cached_pid or cached_pid == pane_pid):
        return cached_path
    if cached_path and cached_pid and cached_pid != pane_pid:
        runtime._pane_native_log_paths.pop(pane_id, None)
    return ""
