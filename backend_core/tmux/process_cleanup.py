from __future__ import annotations

import os
import signal
import subprocess
import time


def pane_pid_for_target(*, target: str, tmux_prefix: list[str]) -> int | None:
    pane = (target or "").strip()
    if not pane:
        return None
    res = subprocess.run(
        [*tmux_prefix, "display-message", "-p", "-t", pane, "#{pane_pid}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return None
    value = (res.stdout or "").strip()
    if not value.isdigit():
        return None
    return int(value)


def pane_pids_for_target(*, target: str, tmux_prefix: list[str]) -> list[int]:
    tmux_target = (target or "").strip()
    if not tmux_target:
        return []
    res = subprocess.run(
        [*tmux_prefix, "list-panes", "-t", tmux_target, "-F", "#{pane_pid}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        pid = pane_pid_for_target(target=tmux_target, tmux_prefix=tmux_prefix)
        return [pid] if pid else []
    pids: list[int] = []
    seen: set[int] = set()
    for line in (res.stdout or "").splitlines():
        value = line.strip()
        if not value.isdigit():
            continue
        pid = int(value)
        if pid > 1 and pid not in seen:
            seen.add(pid)
            pids.append(pid)
    return pids


def cleanup_process_groups_for_pids(
    pids: list[int],
    *,
    term_timeout_sec: float = 0.45,
    kill_timeout_sec: float = 0.2,
) -> None:
    pgids: list[int] = []
    seen: set[int] = set()
    current_pgrp = os.getpgrp()
    for pid in pids:
        try:
            pgid = os.getpgid(int(pid))
        except (ProcessLookupError, PermissionError, OSError):
            continue
        if pgid <= 1 or pgid == current_pgrp or pgid in seen:
            continue
        seen.add(pgid)
        pgids.append(pgid)

    _signal_process_groups(pgids, signal.SIGTERM)
    _wait_for_process_groups(pgids, term_timeout_sec)
    alive = [pgid for pgid in pgids if _process_group_exists(pgid)]
    if alive:
        _signal_process_groups(alive, signal.SIGKILL)
        _wait_for_process_groups(alive, kill_timeout_sec)


def cleanup_target_process_groups(*, target: str, tmux_prefix: list[str]) -> None:
    cleanup_process_groups_for_pids(pane_pids_for_target(target=target, tmux_prefix=tmux_prefix))


def _signal_process_groups(pgids: list[int], sig: int) -> None:
    for pgid in pgids:
        try:
            os.kill(-pgid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            continue


def _wait_for_process_groups(pgids: list[int], timeout_sec: float) -> None:
    deadline = time.monotonic() + max(0.0, timeout_sec)
    while time.monotonic() < deadline:
        if not any(_process_group_exists(pgid) for pgid in pgids):
            return
        time.sleep(0.05)


def _process_group_exists(pgid: int) -> bool:
    try:
        os.kill(-pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
