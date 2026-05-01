from __future__ import annotations

import subprocess
import time

from native_log_sync.agents._shared.path_state import _agent_base_name


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
