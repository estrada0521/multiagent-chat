from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from multiagent_chat.chat.sync.cursor import _native_path_claim_key

from native_log_sync.core.process_tree import get_process_tree


def resolve_native_log_file(
    pane_pid: str,
    log_pattern: str,
    base_name: str = "",
) -> str | None:
    """ペイン PID ツリーが開いているファイルから *log_pattern* に一致するパスを返す。"""
    pids = get_process_tree(str(pane_pid).strip())
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

    try:
        cmd = ["lsof", "-p", ",".join(pids), "-Fn"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
        ranked_candidates: list[tuple[float, str]] = []
        seen_claim_keys: set[str] = set()
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
        if ranked_candidates:
            ranked_candidates.sort(key=lambda item: item[0], reverse=True)
            return ranked_candidates[0][1]
    except Exception:
        pass
    return None


def pane_pid_opens_file(pane_pid: str, target_path: str) -> bool:
    """*pane_pid* のプロセスツリーが *target_path* を開いているか（realpath 一致）。"""
    try:
        target = os.path.realpath(str(target_path))
    except OSError:
        target = str(target_path)
    pids = get_process_tree(str(pane_pid).strip())
    if not pids:
        return False
    try:
        cmd = ["lsof", "-p", ",".join(pids), "-Fn"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
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
