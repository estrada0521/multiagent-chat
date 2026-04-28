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


def agents_from_pane_env(
    runtime,
    *,
    subprocess_module=subprocess,
    logging_module=logging,
    agents_from_tmux_env_output_fn,
) -> list[str]:
    try:
        r = subprocess_module.run(
            [*runtime.tmux_prefix, "show-environment", "-t", runtime.session_name],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception as exc:
        logging_module.error(f"Unexpected error: {exc}", exc_info=True)
        return []
    if r.returncode != 0:
        return []
    return agents_from_tmux_env_output_fn(r.stdout)


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
        pass
    pane_agents = runtime._agents_from_pane_env()
    if pane_agents:
        return pane_agents
    return list(runtime.targets) if runtime.targets else []


def resolve_target_agents(runtime, target: str, *, resolve_target_agent_names_fn) -> list[str]:
    return resolve_target_agent_names_fn(target, runtime.active_agents())


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
