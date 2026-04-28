from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from native_log_sync.io.cursor_state import _native_path_claim_key

_LSOF_PID_CHUNK = 96


def get_process_tree(pid: str) -> set[str]:
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,ppid"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        children_map: dict[str, list[str]] = {}
        for line in out.splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                child, parent = parts[0], parts[1]
                children_map.setdefault(parent, []).append(child)

        pids = {pid}
        queue = [pid]
        while queue:
            current = queue.pop(0)
            for child in children_map.get(current, []):
                if child not in pids:
                    pids.add(child)
                    queue.append(child)
        return pids
    except Exception:
        return {pid}


def enumerate_lsof_paths_matching_pattern_for_pids(
    pids: set[str],
    log_pattern: str,
) -> list[tuple[float, str]]:
    ranked_candidates: list[tuple[float, str]] = []
    seen_claim_keys: set[str] = set()
    pid_list = sorted({str(p).strip() for p in pids if str(p).strip().isdigit()}, key=int)
    if not pid_list:
        return ranked_candidates

    try:
        for start in range(0, len(pid_list), _LSOF_PID_CHUNK):
            chunk = pid_list[start : start + _LSOF_PID_CHUNK]
            out = subprocess.run(
                ["lsof", "-p", ",".join(chunk), "-Fn"],
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout
            for line in out.splitlines():
                if not line.startswith("n"):
                    continue
                path = line[1:]
                if not re.search(log_pattern, path):
                    continue
                stat_result: os.stat_result | None = None
                mtime = -1.0
                try:
                    stat_result = os.stat(path)
                    mtime = stat_result.st_mtime
                except OSError:
                    pass
                claim_key = _native_path_claim_key(path, stat_result=stat_result)
                if claim_key in seen_claim_keys:
                    continue
                seen_claim_keys.add(claim_key)
                ranked_candidates.append((mtime, path))
    except Exception:
        pass
    return ranked_candidates


def enumerate_lsof_paths_matching_pattern(pane_pid: str, log_pattern: str) -> list[tuple[float, str]]:
    root = str(pane_pid).strip()
    pids = set(get_process_tree(root))
    if root:
        pids.add(root)
    return enumerate_lsof_paths_matching_pattern_for_pids(pids, log_pattern)


def pane_pid_opens_file(pane_pid: str, target_path: str) -> bool:
    try:
        target = os.path.realpath(str(target_path))
    except OSError:
        target = str(target_path)
    root = str(pane_pid).strip()
    pids = set(get_process_tree(root))
    if root:
        pids.add(root)
    if not pids:
        return False
    pid_list = sorted(pids, key=int)
    try:
        for start in range(0, len(pid_list), _LSOF_PID_CHUNK):
            chunk = pid_list[start : start + _LSOF_PID_CHUNK]
            out = subprocess.run(
                ["lsof", "-p", ",".join(chunk), "-Fn"],
                capture_output=True,
                text=True,
                timeout=3,
            ).stdout
            for line in out.splitlines():
                if not line.startswith("n"):
                    continue
                path = line[1:]
                try:
                    if os.path.realpath(path) == target:
                        return True
                except OSError:
                    if path == target:
                        return True
    except Exception:
        pass
    return False


def pids_on_tty(tty_raw: str) -> set[str]:
    tty_text = str(tty_raw or "").strip()
    if not tty_text or tty_text.lower() in ("not a tty", "/dev/not a tty"):
        return set()
    candidates = [tty_text]
    if not tty_text.startswith("/dev/"):
        candidates.append("/dev/" + tty_text.lstrip("/"))
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


def copilot_events_jsonl_for_pid_tree(pane_pid: str) -> str:
    root = str(pane_pid).strip()
    pids = set(get_process_tree(root))
    if root:
        pids.add(root)
    if not pids:
        return ""
    state_dir = Path.home() / ".copilot" / "session-state"
    if not state_dir.exists():
        return ""
    for pid in pids:
        for lock_file in state_dir.glob(f"*/inuse.{pid}.lock"):
            log_file = lock_file.parent / "events.jsonl"
            if log_file.exists():
                return str(log_file)
    return ""
