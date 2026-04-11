from __future__ import annotations
import logging

import json
import os
import hashlib
import sys
import socket
from pathlib import Path


def _apply_hub_settings(raw: dict, settings: dict, *, missing_flags_false: bool = False) -> dict:
    if not isinstance(raw, dict):
        return settings

    # Legacy ``bold_mode`` (single toggle): map to mobile + desktop when new keys are absent.
    if (
        "bold_mode" in raw
        and "bold_mode_mobile" not in raw
        and "bold_mode_desktop" not in raw
    ):
        raw = {**raw}
        legacy = raw["bold_mode"]
        both_on = legacy in (True, "true", "1", "on") if not isinstance(legacy, bool) else bool(legacy)
        raw["bold_mode_mobile"] = both_on
        raw["bold_mode_desktop"] = both_on

    settings["theme"] = "black-hole"

    agent_font_mode = str(raw.get("agent_font_mode") or settings["agent_font_mode"]).strip().lower()
    if agent_font_mode in {"serif", "gothic"}:
        settings["agent_font_mode"] = agent_font_mode

    user_message_font = str(raw.get("user_message_font") or settings["user_message_font"]).strip()
    if user_message_font:
        settings["user_message_font"] = user_message_font

    agent_message_font = str(raw.get("agent_message_font") or "").strip()
    if agent_message_font:
        settings["agent_message_font"] = agent_message_font
        if agent_message_font == "preset-gothic":
            settings["agent_font_mode"] = "gothic"
        elif agent_message_font == "preset-mincho":
            settings["agent_font_mode"] = "serif"
    else:
        settings["agent_message_font"] = "preset-gothic" if settings["agent_font_mode"] == "gothic" else "preset-mincho"

    try:
        message_text_size = int(raw.get("message_text_size", settings["message_text_size"]))
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        message_text_size = int(settings["message_text_size"])
    settings["message_text_size"] = max(11, min(18, message_text_size))

    for key in (
        "chat_auto_mode",
        "chat_awake",
        "chat_sound",
        "chat_browser_notifications",
        "bold_mode_mobile",
        "bold_mode_desktop",
    ):
        if missing_flags_false and key not in raw:
            settings[key] = False
            continue
        value = raw.get(key, settings[key])
        settings[key] = value in (True, "true", "1", "on") if not isinstance(value, bool) else value

    return settings


HUB_SETTINGS_DEFAULTS = {
    "theme": "black-hole",
    "agent_font_mode": "serif",
    "user_message_font": "preset-gothic",
    "agent_message_font": "preset-mincho",
    "message_text_size": 13,
    "chat_auto_mode": False,
    "chat_awake": False,
    "chat_sound": False,
    "chat_browser_notifications": False,
    "bold_mode_mobile": False,
    "bold_mode_desktop": False,
}


def local_state_dir(repo_root: Path | str) -> Path:
    repo = str(Path(repo_root).resolve())
    repo_hash = hashlib.sha1(repo.encode("utf-8")).hexdigest()[:12]
    mac_root = Path.home() / "Library" / "Application Support" / "multiagent"
    xdg_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "multiagent"
    base = mac_root if sys.platform == "darwin" else xdg_root
    return base / repo_hash


def local_runtime_log_dir(repo_root: Path | str) -> Path:
    return local_state_dir(repo_root) / "logs"


def local_workspace_log_dir(repo_root: Path | str, workspace: Path | str) -> Path:
    workspace_real = str(Path(workspace).resolve())
    workspace_hash = hashlib.sha1(workspace_real.encode("utf-8")).hexdigest()[:12]
    name = Path(workspace_real).name or "workspace"
    return local_state_dir(repo_root) / "workspaces" / f"{name}-{workspace_hash}"


def default_chat_port(session_name: str) -> int:
    digest = int(hashlib.md5(session_name.encode()).hexdigest(), 16)
    return 8200 + (digest % 700)


def chat_ports_path(repo_root: Path | str, *, create_parent: bool = True) -> Path:
    path = local_state_dir(repo_root) / ".chat-ports.json"
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json_dict(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.error(f"Unexpected error: {exc}", exc_info=True)
        return {}
    return raw if isinstance(raw, dict) else {}


def load_chat_port_overrides(repo_root: Path | str) -> dict[str, int]:
    raw = _read_json_dict(chat_ports_path(repo_root, create_parent=False))
    overrides = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        try:
            port = int(value)
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            continue
        if 1 <= port <= 65535:
            overrides[key] = port
    return overrides


def resolve_chat_port(repo_root: Path | str, session_name: str) -> int:
    return int(load_chat_port_overrides(repo_root).get(session_name) or default_chat_port(session_name))


def save_chat_port_override(repo_root: Path | str, session_name: str, port: int) -> None:
    overrides = load_chat_port_overrides(repo_root)
    overrides[str(session_name)] = int(port)
    chat_ports_path(repo_root).write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")


def port_is_bindable(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def hub_settings_path(repo_root: Path | str) -> Path:
    local_path = local_state_dir(repo_root) / ".hub-settings.json"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    return local_path


def load_hub_settings(repo_root: Path | str) -> dict:
    settings = dict(HUB_SETTINGS_DEFAULTS)
    path = hub_settings_path(repo_root)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.error(f"Unexpected error: {exc}", exc_info=True)
            raw = {}
        settings = _apply_hub_settings(raw, settings)
    return settings


def save_hub_settings(repo_root: Path | str, raw: dict) -> dict:
    settings = load_hub_settings(repo_root)
    settings = _apply_hub_settings(raw, settings, missing_flags_false=True)
    path = hub_settings_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings
