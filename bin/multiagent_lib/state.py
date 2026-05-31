from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path


def _parse_tmux_environment_output(output: str) -> dict[str, str]:
    env_map: dict[str, str] = {}
    for raw in (output or "").splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key] = value
    return env_map


def _parse_agents_csv(agents_csv: str) -> list[str]:
    return [item.strip() for item in (agents_csv or "").split(",") if item.strip()]


def write_session_meta_file(session: str, agents_csv: str, tmux_env_output: str) -> None:
    env_map = _parse_tmux_environment_output(tmux_env_output)
    index_path_raw = str(env_map.get("MULTIAGENT_INDEX_PATH") or "").strip()
    if not index_path_raw:
        return

    meta_path = Path(index_path_raw).expanduser().resolve().parent / ".meta"
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta: dict[str, object] = {}
    if meta_path.is_file():
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                meta = raw
        except Exception:
            meta = {}

    created_at = str(meta.get("created_at") or "").strip() or updated_at
    workspace = str(
        env_map.get("MULTIAGENT_WORKSPACE")
        or meta.get("workspace")
        or ""
    ).strip()

    meta["session"] = session
    meta["workspace"] = workspace
    meta["agents"] = _parse_agents_csv(agents_csv)
    meta["created_at"] = created_at
    meta["updated_at"] = updated_at
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


def _read_lock_pid(lock_dir: Path) -> int:
    pid_file = lock_dir / "pid"
    if not pid_file.is_file():
        return 0
    try:
        raw = pid_file.read_text(encoding="utf-8").strip()
        return int(raw)
    except Exception:
        return 0


def acquire_topology_lock(
    lock_dir: Path | str,
    holder_pid: int,
    *,
    max_attempts: int = 400,
    sleep_seconds: float = 0.05,
) -> bool:
    lock_path = Path(lock_dir)
    attempts = 0
    while True:
        try:
            lock_path.mkdir()
            (lock_path / "pid").write_text(str(holder_pid), encoding="utf-8")
            return True
        except FileExistsError:
            existing_pid = _read_lock_pid(lock_path)
            if existing_pid and not _pid_alive(existing_pid):
                shutil.rmtree(lock_path, ignore_errors=True)
                continue
            attempts += 1
            if attempts >= max_attempts:
                return False
            time.sleep(max(0.0, sleep_seconds))


def release_topology_lock(lock_dir: Path | str) -> None:
    shutil.rmtree(Path(lock_dir), ignore_errors=True)
