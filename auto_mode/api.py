from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path


def auto_mode_status(
    runtime,
    *,
    subprocess_module=subprocess,
    os_module=os,
    path_class=Path,
    logging_module=logging,
) -> dict:
    try:
        result = subprocess_module.run(
            [*runtime.tmux_prefix, "show-environment", "-t", runtime.session_name, "MULTIAGENT_AUTO_MODE"],
            capture_output=True,
            text=True,
            check=False,
        )
        active = result.stdout.strip() == "MULTIAGENT_AUTO_MODE=1"
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
        active = False
    approval_file = f"/tmp/multiagent_auto_approved_{runtime.session_name}"
    try:
        last_approval = os_module.path.getmtime(approval_file)
        last_approval_agent = path_class(approval_file).read_text().strip().lower()
    except OSError:
        last_approval = 0
        last_approval_agent = ""
    return {"active": active, "last_approval": last_approval, "last_approval_agent": last_approval_agent}


def apply_auto_mode_setting(
    runtime,
    *,
    desired_active: bool | None = None,
    subprocess_module=subprocess,
    os_module=os,
    path_class=Path,
    logging_module=logging,
) -> bool:
    if desired_active is None:
        try:
            desired_active = bool(runtime.load_chat_settings().get("chat_auto_mode", False))
        except Exception as exc:
            logging_module.error("Failed to load chat_auto_mode setting: %s", exc, exc_info=True)
            return False
    try:
        has_session = subprocess_module.run(
            [*runtime.tmux_prefix, "has-session", "-t", f"={runtime.session_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        logging_module.error("Failed to check tmux session for auto-mode: %s", exc, exc_info=True)
        return False
    if has_session.returncode != 0:
        return False

    script_path = path_class(runtime.agent_send_path).parent / "multiagent-auto-mode"
    env = os_module.environ.copy()
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    action = "on" if desired_active else "off"
    try:
        result = subprocess_module.run(
            [str(script_path), action, "--session", runtime.session_name],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    except Exception as exc:
        logging_module.error("Failed to apply auto-mode setting: %s", exc, exc_info=True)
        return False
    if result.returncode != 0:
        logging_module.warning(
            "Failed to set auto-mode %s for %s: %s",
            action,
            runtime.session_name,
            (result.stderr or result.stdout or "").strip(),
        )
        return False
    return True
