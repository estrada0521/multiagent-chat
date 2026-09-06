from __future__ import annotations

import hashlib
import os
import re
import socket
from pathlib import Path

SESSION_LOG_FILENAME = ".log.jsonl"
NATIVE_LOG_STATE_FILENAME = ".native-log-sync-state.json"
SESSION_NAME_MAX_LENGTH = 64


def sanitize_session_name(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.\-]", "-", str(raw or "")).strip(".-")[:SESSION_NAME_MAX_LENGTH]


def agent_window_root() -> Path:
    return Path.home() / ".agent-window"


def agent_window_state_dir() -> Path:
    override = (os.environ.get("AGENT_WINDOW_STATE_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    return agent_window_root() / "state"


def pwa_https_enabled() -> bool:
    return (agent_window_state_dir() / "pwa" / "enabled").is_file()


def local_bind_scheme(*, cert_file: str = "", key_file: str = "") -> str:
    """PWA on → HTTPS only. PWA off → HTTP."""
    if not pwa_https_enabled():
        return "http"
    if not cert_file or not key_file:
        raise SystemExit("PWA is enabled; HTTPS certificate and key are required")
    if not Path(cert_file).is_file() or not Path(key_file).is_file():
        raise SystemExit("PWA is enabled; HTTPS certificate files are missing")
    return "https"


def local_bind_host() -> str:
    """PWA on → LAN. PWA off → loopback."""
    return "0.0.0.0" if pwa_https_enabled() else "127.0.0.1"


def agent_window_run_dir() -> Path:
    return agent_window_root() / "run"


def agent_window_session_root() -> Path:
    return agent_window_root() / "session"


def session_artifact_dir(session_name: str) -> Path:
    return agent_window_session_root() / str(session_name or "").strip()


def session_log_path(session_name: str) -> Path:
    return session_artifact_dir(session_name) / SESSION_LOG_FILENAME


def session_native_log_state_path(session_name: str) -> Path:
    return session_artifact_dir(session_name) / NATIVE_LOG_STATE_FILENAME


def workspace_agent_window_dir(workspace: Path | str) -> Path:
    return Path(workspace).expanduser() / ".agent-window"


def workspace_log_link_path(workspace: Path | str) -> Path:
    return workspace_agent_window_dir(workspace) / SESSION_LOG_FILENAME


def workspace_native_log_state_link_path(workspace: Path | str) -> Path:
    return workspace_agent_window_dir(workspace) / NATIVE_LOG_STATE_FILENAME


def ensure_session_workspace_mirrors(session_name: str, workspace: Path | str) -> None:
    raw = str(workspace or "").strip()
    if not raw:
        return
    workspace_path = Path(raw).expanduser()
    if not workspace_path.is_dir():
        return
    mirrors = (
        (session_log_path(session_name), workspace_log_link_path(workspace_path)),
        (session_native_log_state_path(session_name), workspace_native_log_state_link_path(workspace_path)),
    )
    for target, link_path in mirrors:
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if link_path.is_symlink():
            if link_path.resolve() == target.resolve():
                continue
            link_path.unlink()
        elif link_path.exists():
            link_path.unlink()
        link_path.symlink_to(target)


def workspace_upload_dir(workspace: Path | str) -> Path:
    return workspace_agent_window_dir(workspace) / "uploads"


def workspace_chat_port(workspace: Path | str) -> int:
    # 30000-48999: wide enough that a real collision with another program
    # is rare, inside the IANA "registered" range so it needs no elevated
    # privileges, clear of both the low end (where nearly every dev tool's
    # conventional default port lives -- 3000, 5432, 6379, 8080, 8888...)
    # and the 49152+ dynamic/ephemeral range OS-assigned ports come from.
    canonical_workspace = str(Path(workspace).expanduser().resolve())
    digest = int(hashlib.md5(canonical_workspace.encode()).hexdigest(), 16)
    return 30000 + (digest % 19000)


def port_is_bindable(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((local_bind_host(), int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()
