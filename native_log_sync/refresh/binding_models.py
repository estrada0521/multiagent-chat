from __future__ import annotations

import os
from dataclasses import dataclass

from multiagent_chat.agents.names import agent_base_name


@dataclass(frozen=True)
class PaneBindingRequest:
    agent: str
    pane_id: str
    pane_pid: str


@dataclass(frozen=True)
class NativeLogBinding:
    agent: str
    base: str
    pane_id: str
    pane_pid: str
    path: str
    watch_roots: tuple[str, ...]
    source: str = ""


def binding_base(agent: str) -> str:
    return agent_base_name(str(agent or "").strip())


def normalize_watch_roots(path: str) -> tuple[str, ...]:
    raw = str(path or "").strip()
    if not raw:
        return ()
    try:
        real = os.path.realpath(raw)
    except OSError:
        real = raw
    root = real if os.path.isdir(real) else os.path.dirname(real)
    if not root:
        return ()
    return (root,)


def binding_for_path(
    *,
    agent: str,
    pane_id: str,
    pane_pid: str,
    path: str,
    source: str = "",
) -> NativeLogBinding | None:
    resolved = str(path or "").strip()
    if not resolved:
        return None
    return NativeLogBinding(
        agent=agent,
        base=binding_base(agent),
        pane_id=str(pane_id or "").strip(),
        pane_pid=str(pane_pid or "").strip(),
        path=resolved,
        watch_roots=normalize_watch_roots(resolved),
        source=source,
    )
