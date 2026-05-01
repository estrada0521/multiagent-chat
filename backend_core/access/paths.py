from __future__ import annotations

import hashlib
import os
from pathlib import Path


def default_tmux_socket_name(repo_root: Path | str) -> str:
    root = os.path.realpath(str(repo_root))
    digest = hashlib.sha1(root.encode("utf-8")).hexdigest()[:12]
    return f"multiagent-{digest}"


def _safe_session_name(session_name: str) -> str:
    return (session_name or "default").replace("/", "_")


def multiagent_panes_state_path(tmux_socket: str, session_name: str) -> Path:
    safe_session = _safe_session_name(session_name)
    socket_name = tmux_socket or "default"
    if socket_name.startswith("/"):
        digest = hashlib.sha1(f"{socket_name}|{safe_session}".encode("utf-8")).hexdigest()[:20]
        return Path(f"/tmp/multiagent_sock_{digest}_panes")
    return Path(f"/tmp/multiagent_{socket_name}_{safe_session}_panes")


def session_topology_lock_path(tmux_socket: str, session_name: str) -> Path:
    safe_session = _safe_session_name(session_name)
    socket_name = tmux_socket or "default"
    if socket_name.startswith("/"):
        digest = hashlib.sha1(f"{socket_name}|{safe_session}".encode("utf-8")).hexdigest()[:20]
        return Path(f"/tmp/multiagent_sock_{digest}_topology.lock")
    return Path(f"/tmp/multiagent_{socket_name}_{safe_session}_topology.lock")
