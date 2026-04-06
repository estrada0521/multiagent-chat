from __future__ import annotations

import os
import shutil
import tempfile
import time
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


def _pane_var_for_instance(instance: str) -> str:
    return f"MULTIAGENT_PANE_{instance.upper().replace('-', '_')}"


def build_state_lines(session: str, agents_csv: str, tmux_env_output: str) -> list[str]:
    env_map = _parse_tmux_environment_output(tmux_env_output)
    lines = [
        f"MULTIAGENT_SESSION={session}",
        f"MULTIAGENT_AGENTS={agents_csv}",
    ]
    if agents_csv:
        for instance in [item.strip() for item in agents_csv.split(",") if item.strip()]:
            pane_var = _pane_var_for_instance(instance)
            pane_id = env_map.get(pane_var, "")
            if pane_id:
                lines.append(f"{pane_var}={pane_id}")
    return lines


def write_session_state_file(path: Path | str, session: str, agents_csv: str, tmux_env_output: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = build_state_lines(session, agents_csv, tmux_env_output)
    content = "\n".join(lines) + "\n"

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(target.parent), delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(target)


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
