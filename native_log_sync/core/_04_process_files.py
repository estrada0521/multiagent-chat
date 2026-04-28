from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from native_log_sync.core._08_cursor_state import _native_path_claim_key

from native_log_sync.core._03_process_tree import get_process_tree

_LSOF_PID_CHUNK = 96


def enumerate_lsof_paths_matching_pattern_for_pids(pids: set[str], log_pattern: str) -> list[tuple[float, str]]:
    """lsof union over many PIDs (dedupe paths by inode); used when pane tty adds processes outside child tree."""
    ranked_candidates: list[tuple[float, str]] = []
    seen_claim_keys: set[str] = set()
    pid_list = sorted({str(p).strip() for p in pids if str(p).strip().isdigit()}, key=int)
    if not pid_list:
        return ranked_candidates

    try:
        for start in range(0, len(pid_list), _LSOF_PID_CHUNK):
            chunk = pid_list[start : start + _LSOF_PID_CHUNK]
            cmd = ["lsof", "-p", ",".join(chunk), "-Fn"]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
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
    """Paths open under #{pane_pid}'s descendant process tree (plus that PID)."""
    root = str(pane_pid).strip()
    pids = set(get_process_tree(root))
    if root:
        pids.add(root)
    return enumerate_lsof_paths_matching_pattern_for_pids(pids, log_pattern)


def resolve_native_log_file(
    pane_pid: str,
    log_pattern: str,
    base_name: str = "",
) -> str | None:
    root = str(pane_pid).strip()
    pids = set(get_process_tree(root))
    if root:
        pids.add(root)
    if not pids:
        return None

    if base_name == "copilot":
        for pid in pids:
            state_dir = Path.home() / ".copilot" / "session-state"
            if not state_dir.exists():
                continue
            for lock_file in state_dir.glob(f"*/inuse.{pid}.lock"):
                session_dir = lock_file.parent
                log_file = session_dir / "events.jsonl"
                if log_file.exists():
                    return str(log_file)

    ranked_candidates = enumerate_lsof_paths_matching_pattern_for_pids(pids, log_pattern)
    if ranked_candidates:
        ranked_candidates.sort(key=lambda item: item[0], reverse=True)
        return ranked_candidates[0][1]
    return None


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
            cmd = ["lsof", "-p", ",".join(chunk), "-Fn"]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
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
