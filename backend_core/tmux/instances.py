from __future__ import annotations

import re


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
