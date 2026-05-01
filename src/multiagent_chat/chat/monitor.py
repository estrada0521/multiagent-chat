from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from auto_mode.monitor import set_monitor_active


def apply_saved_monitor_setting(
    runtime,
    *,
    subprocess_module=subprocess,
    os_module=os,
    path_class=Path,
    logging_module=logging,
) -> bool:
    try:
        active = bool(runtime.load_chat_settings().get("chat_auto_mode", False))
    except Exception as exc:
        logging_module.error("Failed to load chat_auto_mode setting: %s", exc, exc_info=True)
        return False
    script_path = path_class(runtime.agent_send_path).resolve().parent.parent / "auto_mode" / "auto-mode"
    return set_monitor_active(
        runtime.tmux_prefix,
        runtime.session_name,
        auto_mode_script=script_path,
        tmux_socket=getattr(runtime, "tmux_socket", ""),
        active=active,
        subprocess_module=subprocess_module,
        os_module=os_module,
        logging_module=logging_module,
    )
