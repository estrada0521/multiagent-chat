from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

from native_log_sync.agents._shared.path_state import _agent_base_name
from .monitor import apply_saved_monitor_setting
from backend_core.session.launch import launch_session


def _update_running_env(runtime, agent: str, running: bool) -> None:
    upper = agent.upper().replace("-", "_")
    var = f"MULTIAGENT_RUNNING_{upper}"
    try:
        if running:
            subprocess.run(
                [*runtime.tmux_prefix, "set-environment", "-t", runtime.session_name, var, "1"],
                capture_output=True, check=False, timeout=1,
            )
        else:
            subprocess.run(
                [*runtime.tmux_prefix, "set-environment", "-u", "-t", runtime.session_name, var],
                capture_output=True, check=False, timeout=1,
            )
    except Exception:
        pass


def mark_agent_sent(self, agent_name: str) -> None:
    base = _agent_base_name(agent_name)
    if base in {"claude", "cursor", "codex", "copilot", "gemini"}:
        self._agent_last_send_ts[agent_name] = time.time()
        self._mark_running(agent_name)


def launch_pending_session(self, requested_targets: list[str] | tuple[str, ...] | str) -> tuple[int, dict]:
    if not self.launch_pending():
        return 400, {"ok": False, "error": "session is already active"}
    if isinstance(requested_targets, str):
        raw_targets = [item.strip() for item in requested_targets.split(",") if item.strip()]
    else:
        raw_targets = [str(item).strip() for item in (requested_targets or []) if str(item).strip()]
    if not raw_targets:
        return 400, {"ok": False, "error": "agent required"}
    delivery_targets: list[str] = []
    seen_targets: set[str] = set()
    for raw_target in raw_targets:
        if raw_target in {"user", "others"}:
            return 400, {"ok": False, "error": "select an initial agent"}
        for resolved in self.resolve_target_agents(raw_target):
            if resolved in {"user", "others"} or resolved in seen_targets:
                continue
            seen_targets.add(resolved)
            delivery_targets.append(resolved)
    if len(delivery_targets) != 1:
        return 400, {"ok": False, "error": "select exactly one initial agent"}
    activated, payload = launch_session(self, delivery_targets)
    if not activated:
        return 400, payload
    apply_saved_monitor_setting(
        self,
        subprocess_module=subprocess,
        os_module=os,
        path_class=Path,
        logging_module=logging,
    )
    return 200, {
        **payload,
        "selected_agent": delivery_targets[0],
        "targets": self.active_agents(),
    }


