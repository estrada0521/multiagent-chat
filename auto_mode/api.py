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
