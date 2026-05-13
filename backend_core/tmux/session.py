from __future__ import annotations

import logging
import subprocess


def active_agents(runtime, *, subprocess_module=subprocess, logging_module=logging) -> list[str]:
    try:
        r = subprocess_module.run(
            [*runtime.tmux_prefix, "show-environment", "-t", runtime.session_name, "MULTIAGENT_AGENTS"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        line = r.stdout.strip()
        if r.returncode == 0 and "=" in line:
            return [a for a in line.split("=", 1)[1].split(",") if a]
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
    return []


def pane_id_for_agent(runtime, agent_name: str, *, subprocess_module=subprocess) -> str:
    pane_var = f"MULTIAGENT_PANE_{agent_name.upper().replace('-', '_')}"
    res = subprocess_module.run(
        [*runtime.tmux_prefix, "show-environment", "-t", runtime.session_name, pane_var],
        capture_output=True,
        text=True,
        check=False,
    )
    return res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""


def pane_field(runtime, pane_id: str, field: str, *, subprocess_module=subprocess) -> str:
    if not pane_id:
        return ""
    result = subprocess_module.run(
        [*runtime.tmux_prefix, "display-message", "-p", "-t", pane_id, field],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    return result.stdout.strip()
