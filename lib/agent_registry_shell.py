#!/usr/bin/env python3
"""Emit bash-safe shell assignments derived from agent_registry."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

# Ensure lib/ is on sys.path so agent_index can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_index.agent_registry import AGENTS, AGENT_ICONS_DIR, ALL_AGENT_NAMES


def q(value: object) -> str:
    return shlex.quote("" if value is None else str(value))


def emit(line: str) -> None:
    print(line)


def emit_scalar(name: str, value: object) -> None:
    emit(f"{name}={q(value)}")


def emit_array(name: str, values: list[str]) -> None:
    if values:
        emit(f"{name}=({' '.join(q(v) for v in values)})")
    else:
        emit(f"{name}=()")


def main() -> None:
    emit("# shellcheck shell=bash")
    emit_array("ALL_AGENTS", ALL_AGENT_NAMES)
    emit_scalar("ALL_AGENTS_CSV", ",".join(ALL_AGENT_NAMES))
    emit_scalar("ALL_AGENTS_DISPLAY", ", ".join(ALL_AGENT_NAMES))
    emit_scalar("AGENT_ICONS_DIR", AGENT_ICONS_DIR)

    for name, agent in AGENTS.items():
        emit_scalar(f"AGENT_EXECUTABLE_{name}", agent.exe)
        emit_scalar(f"AGENT_DISPLAY_NAME_{name}", agent.display_name)
        emit_scalar(f"AGENT_ICON_FILE_{name}", agent.icon_file)
        emit_scalar(f"AGENT_READY_PATTERN_{name}", agent.ready_pattern)
        emit_scalar(f"AGENT_LAUNCH_EXTRA_{name}", agent.launch_extra)
        emit_scalar(f"AGENT_LAUNCH_FLAGS_{name}", agent.launch_flags)
        emit_scalar(f"AGENT_LAUNCH_ENV_{name}", agent.launch_env)
        emit_scalar(f"AGENT_RESUME_FLAG_{name}", agent.resume_flag)
        emit_scalar(f"AGENT_RESUME_EXTRA_FLAGS_{name}", agent.resume_extra_flags)
        emit_scalar(f"AGENT_STARTUP_PRIORITY_{name}", agent.startup_priority)
        if agent.number_alias:
            emit_scalar(f"AGENT_NUMBER_ALIAS_{agent.number_alias}", name)


if __name__ == "__main__":
    main()
