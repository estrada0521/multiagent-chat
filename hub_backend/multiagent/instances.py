from __future__ import annotations

import re


def agents_from_tmux_env_output(output: str) -> list[str]:
    agents: list[str] = []
    seen: set[str] = set()
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("MULTIAGENT_PANE_"):
            continue
        key = line.split("=", 1)[0]
        suffix = key[len("MULTIAGENT_PANE_"):]
        if not suffix or suffix == "USER":
            continue
        lower = suffix.lower()
        match = re.fullmatch(r"(.+)_([0-9]+)", lower)
        agent = f"{match.group(1)}-{match.group(2)}" if match else lower
        if agent in seen:
            continue
        seen.add(agent)
        agents.append(agent)
    return agents


def expected_instance_names(base_agents: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for agent in base_agents:
        counts[agent] = counts.get(agent, 0) + 1
    indices: dict[str, int] = {}
    resolved = []
    for agent in base_agents:
        if counts.get(agent, 0) > 1:
            indices[agent] = indices.get(agent, 0) + 1
            resolved.append(f"{agent}-{indices[agent]}")
        else:
            resolved.append(agent)
    return resolved


def resolve_target_agents(target: str, available_agents: list[str]) -> list[str]:
    available = list(available_agents or [])
    available_set = set(available)
    resolved: list[str] = []
    seen: set[str] = set()
    for raw in [item.strip().lower() for item in (target or "").split(",") if item.strip()]:
        if raw in {"user", "others"}:
            candidates = [raw]
        elif raw in available_set:
            candidates = [raw]
        elif re.fullmatch(r".+-\d+", raw):
            candidates = [raw]
        else:
            candidates = [agent for agent in available if agent == raw or agent.startswith(f"{raw}-")]
            if not candidates:
                candidates = [raw]
        for agent in candidates:
            if agent in seen:
                continue
            seen.add(agent)
            resolved.append(agent)
    return resolved
