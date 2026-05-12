from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path


def monitor_status(
    tmux_prefix: list[str],
    session_name: str,
    *,
    subprocess_module=subprocess,
    os_module=os,
    path_class=Path,
    logging_module=logging,
) -> dict:
    try:
        result = subprocess_module.run(
            [*tmux_prefix, "show-environment", "-t", session_name, "MULTIAGENT_AUTO_MODE"],
            capture_output=True,
            text=True,
            check=False,
        )
        active = result.stdout.strip() == "MULTIAGENT_AUTO_MODE=1"
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
        active = False
    approval_file = f"/tmp/auto_mode_approved_{session_name}"
    try:
        last_approval = os_module.path.getmtime(approval_file)
        last_approval_agent = path_class(approval_file).read_text().strip().lower()
    except OSError:
        last_approval = 0
        last_approval_agent = ""
    return {"active": active, "last_approval": last_approval, "last_approval_agent": last_approval_agent}


def set_monitor_active(
    tmux_prefix: list[str],
    session_name: str,
    *,
    auto_mode_script: str | Path,
    tmux_socket: str,
    active: bool,
    subprocess_module=subprocess,
    os_module=os,
    logging_module=logging,
) -> bool:
    try:
        has_session = subprocess_module.run(
            [*tmux_prefix, "has-session", "-t", f"={session_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        logging_module.error("Failed to check tmux session for monitor: %s", exc, exc_info=True)
        return False
    if has_session.returncode != 0:
        return False

    env = os_module.environ.copy()
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    if tmux_socket:
        env["MULTIAGENT_TMUX_SOCKET"] = str(tmux_socket)
    action = "on" if active else "off"
    try:
        result = subprocess_module.run(
            [str(auto_mode_script), action, "--session", session_name],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    except Exception as exc:
        logging_module.error("Failed to set monitor %s: %s", action, exc, exc_info=True)
        return False
    if result.returncode != 0:
        logging_module.warning(
            "Failed to set monitor %s for %s: %s",
            action,
            session_name,
            (result.stderr or result.stdout or "").strip(),
        )
        return False
    return True


def ensure_monitor_running(
    tmux_prefix: list[str],
    session_name: str,
    *,
    auto_mode_script: str | Path,
    tmux_socket: str,
    subprocess_module=subprocess,
    os_module=os,
    logging_module=logging,
) -> bool:
    """Start the auto-mode monitor if AUTO_MODE is on and no monitor is running."""
    env = os_module.environ.copy()
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    if tmux_socket:
        env["MULTIAGENT_TMUX_SOCKET"] = str(tmux_socket)
    try:
        result = subprocess_module.run(
            [str(auto_mode_script), "_ensure", "--session", session_name],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    except Exception as exc:
        logging_module.error("Failed to ensure monitor: %s", exc, exc_info=True)
        return False
    return result.returncode == 0
