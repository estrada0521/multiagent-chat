from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import time
import hashlib
import sys
import socket
from pathlib import Path

THEME_PRESETS = {
    "black-hole": {
        "label": "Black Hole",
        "description": "Pure black theme.",
    },
    "soft-light": {
        "label": "Soft Light",
        "description": "Light background theme with dark text.",
    },
}


def available_theme_choices() -> list[tuple[str, str]]:
    return [(key, str(meta.get("label") or key)) for key, meta in THEME_PRESETS.items()]


def theme_description(theme_key: str) -> str:
    meta = THEME_PRESETS.get(str(theme_key or "").strip().lower(), {})
    return str(meta.get("description") or "")


def _base_agent_name(name: str) -> str:
    """Strip instance suffix: 'claude-1' → 'claude', 'gemini' → 'gemini'."""
    return re.sub(r"-\d+$", "", name)


def _coerce_message_limit(raw: dict, fallback: int, cap: int) -> int:
    candidate = raw.get("message_limit")
    try:
        value = int(candidate)
    except Exception:
        value = fallback
    return max(10, min(cap, value))


def _apply_hub_settings(raw: dict, settings: dict, *, message_limit_cap: int, missing_flags_false: bool = False) -> dict:
    if not isinstance(raw, dict):
        return settings

    theme = str(raw.get("theme") or settings["theme"]).strip().lower()
    if theme in THEME_PRESETS:
        settings["theme"] = theme

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
    except Exception:
        message_text_size = int(settings["message_text_size"])
    settings["message_text_size"] = max(11, min(18, message_text_size))

    for key in ("user_message_opacity_blackhole", "agent_message_opacity_blackhole"):
        try:
            value = float(raw.get(key, settings[key]))
        except Exception:
            value = float(settings[key])
        settings[key] = max(0.2, min(1.0, value))

    settings["message_limit"] = _coerce_message_limit(raw, settings["message_limit"], message_limit_cap)

    for key in ("chat_auto_mode", "chat_awake", "chat_sound", "chat_tts", "starfield"):
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
    "user_message_opacity_blackhole": 1.0,
    "agent_message_opacity_blackhole": 1.0,
    "message_limit": 500,
    "chat_auto_mode": False,
    "chat_awake": False,
    "chat_sound": False,
    "chat_tts": False,
    "starfield": True,
}


def central_log_dir(repo_root: Path | str) -> Path:
    return Path(repo_root).resolve() / "logs"


def local_state_dir(repo_root: Path | str) -> Path:
    repo = str(Path(repo_root).resolve())
    repo_hash = hashlib.sha1(repo.encode("utf-8")).hexdigest()[:12]
    mac_root = Path.home() / "Library" / "Application Support" / "multiagent"
    xdg_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "multiagent"
    base = mac_root if sys.platform == "darwin" else xdg_root
    return base / repo_hash


def _thinking_state_lock_path(repo_root: Path | str) -> Path:
    path = local_state_dir(repo_root) / ".thinking-state.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextlib.contextmanager
def _thinking_state_lock(repo_root: Path | str):
    lock_path = _thinking_state_lock_path(repo_root)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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


def chat_ports_path(repo_root: Path | str) -> Path:
    path = local_state_dir(repo_root) / ".chat-ports.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_chat_port_overrides(repo_root: Path | str) -> dict[str, int]:
    raw = _read_json_dict(chat_ports_path(repo_root))
    overrides = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        try:
            port = int(value)
        except Exception:
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


def _collapsed_agent_totals(agent_values: dict) -> dict[str, int]:
    if not isinstance(agent_values, dict):
        return {}
    exact_base_totals: dict[str, int] = {}
    instance_totals: dict[str, int] = {}
    for agent, raw_value in agent_values.items():
        try:
            value = max(0, int(raw_value or 0))
        except Exception:
            value = 0
        if not value:
            continue
        base = _base_agent_name(agent)
        if (agent or "").strip() == base:
            exact_base_totals[base] = max(exact_base_totals.get(base, 0), value)
        else:
            instance_totals[base] = instance_totals.get(base, 0) + value
    collapsed: dict[str, int] = {}
    for base in set(exact_base_totals) | set(instance_totals):
        collapsed[base] = max(exact_base_totals.get(base, 0), instance_totals.get(base, 0))
    return collapsed


def _thinking_stats_local_path(repo_root: Path | str) -> Path:
    path = local_state_dir(repo_root) / ".thinking-time.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_thinking_stats_payload_unlocked(repo_root: Path | str) -> dict:
    return normalize_thinking_payload(_read_json_dict(_thinking_stats_local_path(repo_root)))


def _thinking_stats_path_unlocked(repo_root: Path | str) -> Path:
    return _thinking_stats_local_path(repo_root)


def thinking_stats_path(repo_root: Path | str) -> Path:
    with _thinking_state_lock(repo_root):
        local_path = _thinking_stats_path_unlocked(repo_root)
        payload = _read_json_dict(local_path)
        normalized = normalize_thinking_payload(payload)
        if normalized != payload:
            try:
                _write_json_atomic(local_path, normalized)
            except Exception:
                pass
        return local_path


def thinking_stats_paths(repo_root: Path | str) -> list[Path]:
    path = _thinking_stats_local_path(repo_root)
    return [path] if path.exists() else []


def normalize_thinking_payload(payload: dict) -> dict:
    normalized = {"sessions": {}, "daily": {}}
    if not isinstance(payload, dict):
        return normalized

    sessions = payload.get("sessions")
    if isinstance(sessions, dict):
        session_items = sessions.items()
    else:
        session_items = [
            (key, value) for key, value in payload.items()
            if key != "daily" and isinstance(value, dict)
        ]

    session_totals = {}
    total_seconds = 0
    for session_key, session_data in session_items:
        if not isinstance(session_data, dict):
            continue
        agents_raw = session_data.get("agents") if "agents" in session_data else session_data
        if not isinstance(agents_raw, dict):
            continue
        session_name = (session_data.get("session_name") or session_key.split("::", 1)[0] or session_key).strip()
        workspace = (session_data.get("workspace") or "").strip()
        canonical_key = _session_storage_key(session_name, workspace)
        updated_at = (session_data.get("updated_at") or "").strip()
        target = normalized["sessions"].setdefault(
            canonical_key,
            {
                "session_name": session_name,
                "workspace": workspace,
                "updated_at": "",
                "agents": {},
            },
        )
        if updated_at > target.get("updated_at", ""):
            target["updated_at"] = updated_at
        session_total = 0
        for base, value in _collapsed_agent_totals(agents_raw).items():
            current = max(target["agents"].get(base, 0), value)
            target["agents"][base] = current
        session_total = sum(max(0, int(v or 0)) for v in target["agents"].values())
        session_totals[canonical_key] = session_total
        total_seconds += session_total

    daily_raw = payload.get("daily")
    daily_sum = 0
    max_day_total = 0
    if isinstance(daily_raw, dict):
        for date_key, day_data in daily_raw.items():
            if not isinstance(day_data, dict):
                continue
            target_day = {}
            day_total = 0
            for base, value in _collapsed_agent_totals(day_data).items():
                target_day[base] = target_day.get(base, 0) + value
                day_total += value
            if target_day:
                normalized["daily"][date_key] = target_day
                daily_sum += day_total
                max_day_total = max(max_day_total, day_total)

    return normalized


def thinking_runtime_path(repo_root: Path | str) -> Path:
    path = local_state_dir(repo_root) / ".thinking-runtime.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json_dict(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def _session_storage_key(session_name: str, workspace: str) -> str:
    workspace_real = str(Path(workspace or "").expanduser().resolve()) if workspace else ""
    return f"{session_name}::{workspace_real}"


def delete_session_thinking_data(repo_root: Path | str, session_name: str, workspace: str) -> None:
    """Remove thinking time data for a session from both stats and runtime files."""
    session_key = _session_storage_key(session_name, workspace)

    with _thinking_state_lock(repo_root):
        for path_fn in (_thinking_stats_path_unlocked, thinking_runtime_path):
            path = path_fn(repo_root)
            payload = _read_json_dict(path)
            sessions = payload.get("sessions")
            if not (isinstance(sessions, dict) and session_key in sessions):
                continue
            del sessions[session_key]
            try:
                _write_json_atomic(path, payload)
            except Exception:
                pass


def load_session_thinking_totals(repo_root: Path | str, session_name: str, workspace: str) -> dict[str, int]:
    session_key = _session_storage_key(session_name, workspace)
    with _thinking_state_lock(repo_root):
        payload = _load_thinking_stats_payload_unlocked(repo_root)
    sessions = payload.get("sessions")
    if not isinstance(sessions, dict):
        return {}
    session_data = sessions.get(session_key)
    if not isinstance(session_data, dict):
        return {}
    agents = session_data.get("agents")
    if not isinstance(agents, dict):
        return {}
    totals = {}
    for agent, raw_value in agents.items():
        try:
            value = max(0, int(raw_value or 0))
        except Exception:
            value = 0
        if value:
            totals[_base_agent_name(agent)] = value
    return totals


def update_thinking_totals_from_statuses(
    repo_root: Path | str,
    session_name: str,
    workspace: str,
    statuses: dict[str, str],
    *,
    now: float | None = None,
):
    if not session_name:
        return
    with _thinking_state_lock(repo_root):
        now_ts = float(now if now is not None else time.time())
        today = time.strftime("%Y-%m-%d", time.localtime(now_ts))
        session_key = _session_storage_key(session_name, workspace)

        runtime_path = thinking_runtime_path(repo_root)
        runtime_payload = _read_json_dict(runtime_path)
        runtime_sessions = runtime_payload.get("sessions")
        if not isinstance(runtime_sessions, dict):
            runtime_sessions = {}

        runtime_entry = runtime_sessions.get(session_key)
        if not isinstance(runtime_entry, dict):
            runtime_entry = {
                "session_name": session_name,
                "workspace": workspace,
                "running_agents": {},
            }
        running_agents = runtime_entry.get("running_agents")
        if not isinstance(running_agents, dict):
            running_agents = {}

        stats_path = _thinking_stats_path_unlocked(repo_root)
        stats_payload = _read_json_dict(stats_path)
        sessions = stats_payload.get("sessions")
        if not isinstance(sessions, dict):
            sessions = {}
        daily = stats_payload.get("daily")
        if not isinstance(daily, dict):
            daily = {}
        day_entry = daily.get(today)
        if not isinstance(day_entry, dict):
            day_entry = {}

        session_entry = sessions.get(session_key)
        if not isinstance(session_entry, dict):
            session_entry = {
                "session_name": session_name,
                "workspace": workspace,
                "updated_at": "",
                "agents": {},
            }
        agent_totals = session_entry.get("agents")
        if not isinstance(agent_totals, dict):
            agent_totals = {}

        changed = False

        def flush_agent(agent_name: str, last_tick: float):
            nonlocal changed
            delta = int(max(0, now_ts - float(last_tick or now_ts)))
            if delta <= 0:
                return
            base = _base_agent_name(agent_name)
            agent_totals[base] = max(0, int(agent_totals.get(base, 0) or 0)) + delta
            day_entry[base] = max(0, int(day_entry.get(base, 0) or 0)) + delta
            changed = True

        tracked_agents = list(running_agents.keys())
        for agent_name in tracked_agents:
            status = str(statuses.get(agent_name) or "").strip().lower()
            meta = running_agents.get(agent_name)
            if not isinstance(meta, dict):
                meta = {}
            last_tick = float(meta.get("last_tick") or now_ts)
            flush_agent(agent_name, last_tick)
            if status == "running":
                running_agents[agent_name] = {"last_tick": now_ts}
            else:
                running_agents.pop(agent_name, None)
                changed = True

        for agent_name, status in statuses.items():
            if str(status).strip().lower() != "running":
                continue
            if agent_name not in running_agents:
                running_agents[agent_name] = {"last_tick": now_ts}
                changed = True

        runtime_entry["session_name"] = session_name
        runtime_entry["workspace"] = workspace
        runtime_entry["running_agents"] = running_agents
        runtime_sessions[session_key] = runtime_entry
        runtime_payload["sessions"] = runtime_sessions
        _write_json_atomic(runtime_path, runtime_payload)

        if changed:
            session_entry["session_name"] = session_name
            session_entry["workspace"] = workspace
            session_entry["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts))
            session_entry["agents"] = agent_totals
            sessions[session_key] = session_entry
            if day_entry:
                daily[today] = day_entry
            stats_payload["sessions"] = sessions
            stats_payload["daily"] = daily
            _write_json_atomic(stats_path, stats_payload)


def load_hub_settings(repo_root: Path | str, *, message_limit_cap: int = 500):
    settings = dict(HUB_SETTINGS_DEFAULTS)
    path = hub_settings_path(repo_root)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        settings = _apply_hub_settings(raw, settings, message_limit_cap=message_limit_cap)
    return settings


def save_hub_settings(repo_root: Path | str, raw, *, message_limit_cap: int = 500):
    settings = load_hub_settings(repo_root, message_limit_cap=message_limit_cap)
    settings = _apply_hub_settings(raw, settings, message_limit_cap=message_limit_cap, missing_flags_false=True)
    path = hub_settings_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings

def load_hub_thinking_totals(repo_root: Path | str):
    totals = {}
    by_session = {}
    daily_thinking = {}
    session_agents = {}
    session_meta = {}
    with _thinking_state_lock(repo_root):
        raw = _load_thinking_stats_payload_unlocked(repo_root)
    if not isinstance(raw, dict):
        raw = {}
    sessions = raw.get("sessions")
    if isinstance(sessions, dict):
        session_items = sessions.items()
    else:
        # Legacy format: top-level keys are session names, values are agent→seconds maps.
        session_items = [
            (key, value) for key, value in raw.items()
            if key != "daily" and isinstance(value, dict)
        ]
    for session_key, session_data in session_items:
        if not isinstance(session_data, dict):
            continue
        agents = session_data.get("agents") if "agents" in session_data else session_data
        if not isinstance(agents, dict):
            continue
        display_name = (session_data.get("session_name") or session_key.split("::", 1)[0] or session_key).strip()
        workspace = (session_data.get("workspace") or "").strip()
        updated_at = (session_data.get("updated_at") or "").strip()
        if display_name not in session_agents:
            session_agents[display_name] = {}
            session_meta[display_name] = {"workspace": workspace, "updated_at": updated_at}
        else:
            if workspace and not session_meta[display_name].get("workspace"):
                session_meta[display_name]["workspace"] = workspace
            if updated_at and updated_at > session_meta[display_name].get("updated_at", ""):
                session_meta[display_name]["updated_at"] = updated_at
        for agent, raw_value in agents.items():
            try:
                value = int(raw_value or 0)
            except Exception:
                value = 0
            value = max(0, value)
            base = _base_agent_name(agent)
            session_agents[display_name][base] = max(session_agents[display_name].get(base, 0), value)
    daily_raw = raw.get("daily")
    if not isinstance(daily_raw, dict):
        daily_raw = {}
    for date_key, day_data in daily_raw.items():
        if not isinstance(day_data, dict):
            continue
        try:
            day_total = sum(max(0, int(v or 0)) for v in day_data.values())
        except Exception:
            continue
        if day_total:
            daily_thinking[date_key] = max(daily_thinking.get(date_key, 0), day_total)
    session_count = 0
    for display_name, agents in session_agents.items():
        session_total = 0
        used = False
        for agent, value in agents.items():
            value = max(0, int(value or 0))
            if value:
                used = True
            totals[agent] = totals.get(agent, 0) + value
            session_total += value
        if used:
            session_count += 1
            meta = session_meta.get(display_name, {})
            by_session[display_name] = {
                "seconds": session_total,
                "workspace": (meta.get("workspace") or "").strip(),
                "updated_at": (meta.get("updated_at") or "").strip(),
            }
    return {
        "total_seconds": sum(totals.values()),
        "by_agent": totals,
        "by_session": by_session,
        "session_count": session_count,
        "daily_thinking": daily_thinking,
    }
