from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from pathlib import Path

from .state_core import resolve_chat_port


def _parse_tmux_environment_output(output: str) -> dict[str, str]:
    env_map: dict[str, str] = {}
    for raw in (output or "").splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key] = value
    return env_map


def _clean_tmux_env_value(value: str) -> str:
    cleaned = (value or "").strip()
    if cleaned == "-":
        return ""
    return cleaned


def session_context_from_env_output(tmux_env_output: str) -> dict[str, str]:
    env_map = _parse_tmux_environment_output(tmux_env_output)
    return {
        "workspace": _clean_tmux_env_value(env_map.get("MULTIAGENT_WORKSPACE", "")),
        "bin_dir": _clean_tmux_env_value(env_map.get("MULTIAGENT_BIN_DIR", "")),
        "tmux_socket": _clean_tmux_env_value(env_map.get("MULTIAGENT_TMUX_SOCKET", "")),
        "log_dir": _clean_tmux_env_value(env_map.get("MULTIAGENT_LOG_DIR", "")),
    }


def chat_server_listener_pids(chat_port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-tiTCP:{int(chat_port)}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    pids: list[int] = []
    for line in (result.stdout or "").splitlines():
        value = line.strip()
        if value.isdigit():
            pids.append(int(value))
    return pids


def _chat_port_open(chat_port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(chat_port)), timeout=0.35):
            return True
    except OSError:
        return False


def _wait_for_chat_port_close(chat_port: int, attempts: int, interval_sec: float) -> bool:
    for _ in range(max(1, int(attempts))):
        if not _chat_port_open(chat_port):
            return True
        time.sleep(max(0.0, float(interval_sec)))
    return not _chat_port_open(chat_port)


def _send_signal(pids: list[int], sig: int) -> None:
    for pid in pids:
        try:
            os.kill(int(pid), sig)
        except (ProcessLookupError, OSError):
            continue


def stop_session_chat_server(
    repo_root: Path | str,
    session_name: str,
    *,
    attempts: int = 15,
    interval_sec: float = 0.1,
) -> tuple[bool, str]:
    name = (session_name or "").strip()
    if not name:
        return False, "session_name is required"
    chat_port = int(resolve_chat_port(repo_root, name))
    pids = chat_server_listener_pids(chat_port)
    if not pids:
        return True, ""
    _send_signal(pids, signal.SIGTERM)
    if _wait_for_chat_port_close(chat_port, attempts, interval_sec):
        return True, ""
    _send_signal(pids, signal.SIGKILL)
    if _wait_for_chat_port_close(chat_port, attempts, interval_sec):
        return True, ""
    return False, f"chat server on port {chat_port} still running after SIGKILL"
