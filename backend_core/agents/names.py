from __future__ import annotations

import re


def agent_base_name(raw_name: str) -> str:
    return re.sub(r"-\d+$", "", str(raw_name or "").strip().lower())


def agent_instance_number(raw_name: str) -> int | None:
    match = re.fullmatch(r".+-(\d+)$", str(raw_name or "").strip().lower())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


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
