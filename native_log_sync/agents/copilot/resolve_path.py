from __future__ import annotations

import subprocess
from pathlib import Path


def _process_tree(pid: str) -> set[str]:
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,ppid"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except Exception:
        return {pid} if pid else set()
    children_map: dict[str, list[str]] = {}
    for line in out.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            child, parent = parts[0], parts[1]
            children_map.setdefault(parent, []).append(child)
    found = {pid} if pid else set()
    queue = [pid] if pid else []
    while queue:
        current = queue.pop(0)
        for child in children_map.get(current, []):
            if child not in found:
                found.add(child)
                queue.append(child)
    return found


def resolve_path(runtime: object, agent: str, pane_pid: str) -> str:
    state_dir = Path.home() / ".copilot" / "session-state"
    if not state_dir.is_dir():
        return ""
    for pid in sorted(_process_tree(str(pane_pid or "").strip())):
        for lock_file in state_dir.glob(f"*/inuse.{pid}.lock"):
            log_file = lock_file.parent / "events.jsonl"
            if log_file.is_file():
                return str(log_file)
    return ""
