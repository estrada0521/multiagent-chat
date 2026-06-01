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
            raw = line.split("=", 1)[1].strip()
            if not raw or raw == "-":
                return []
            return [a for a in raw.split(",") if a and a != "-"]
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
    return []


def running_agents_from_env(runtime, agents: list[str], *, subprocess_module=subprocess, logging_module=logging) -> set[str]:
    running: set[str] = set()
    for agent in agents or []:
        name = str(agent or "").strip()
        if not name:
            continue
        upper = name.upper().replace("-", "_")
        var = f"MULTIAGENT_RUNNING_{upper}"
        try:
            result = subprocess_module.run(
                [*runtime.tmux_prefix, "show-environment", "-t", runtime.session_name, var],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
        except Exception as exc:
            logging_module.error(f"Unexpected error: {exc}", exc_info=True)
            continue
        line = result.stdout.strip()
        if result.returncode == 0 and "=" in line and line.split("=", 1)[1].strip() == "1":
            running.add(name)
    return running


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
