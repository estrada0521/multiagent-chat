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


def resolve_codex_rollout_jsonl_path(pane_pid: str) -> str:
    sessions_root = str((Path.home() / ".codex" / "sessions").resolve())
    for pid in sorted(_process_tree(str(pane_pid or "").strip())):
        if not pid:
            continue
        try:
            out = subprocess.run(
                ["lsof", "-p", pid],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        except Exception:
            continue
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            path = " ".join(parts[8:]).strip()
            if not path.endswith(".jsonl"):
                continue
            if "/rollout-" not in path:
                continue
            try:
                resolved = str(Path(path).resolve())
            except OSError:
                resolved = path
            if resolved.startswith(sessions_root + "/") and Path(resolved).is_file():
                return resolved
    return ""
