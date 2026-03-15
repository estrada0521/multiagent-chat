from __future__ import annotations

import json
import time
from pathlib import Path


HUB_SETTINGS_DEFAULTS = {
    "theme": "default",
    "agent_font_mode": "serif",
    "mobile_message_limit": 50,
    "desktop_message_limit": 500,
    "chat_auto_mode": False,
    "chat_awake": False,
    "chat_sound": False,
    "chat_tts": False,
}


def central_log_dir(repo_root: Path | str) -> Path:
    return Path(repo_root).resolve() / "logs"


def hub_settings_path(repo_root: Path | str) -> Path:
    return central_log_dir(repo_root) / ".hub-settings.json"


def thinking_stats_path(repo_root: Path | str) -> Path:
    return central_log_dir(repo_root) / ".thinking-time.json"


def load_hub_settings(repo_root: Path | str, *, mobile_limit_cap: int = 500, desktop_limit_cap: int = 500):
    settings = dict(HUB_SETTINGS_DEFAULTS)
    path = hub_settings_path(repo_root)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        if isinstance(raw, dict):
            theme = str(raw.get("theme") or settings["theme"]).strip().lower()
            if theme in {"default", "claude", "black-hole"}:
                settings["theme"] = theme
            agent_font_mode = str(raw.get("agent_font_mode") or settings["agent_font_mode"]).strip().lower()
            if agent_font_mode in {"serif", "gothic"}:
                settings["agent_font_mode"] = agent_font_mode
            for key, default, cap in (
                ("mobile_message_limit", 50, mobile_limit_cap),
                ("desktop_message_limit", 500, desktop_limit_cap),
            ):
                try:
                    value = int(raw.get(key, settings[key]))
                except Exception:
                    value = default
                settings[key] = max(10, min(cap, value))
            for key in ("chat_auto_mode", "chat_awake", "chat_sound", "chat_tts"):
                v = raw.get(key, settings[key])
                settings[key] = v in (True, "true", "1", "on") if not isinstance(v, bool) else v
    return settings


def save_hub_settings(repo_root: Path | str, raw, *, mobile_limit_cap: int = 500, desktop_limit_cap: int = 500):
    settings = load_hub_settings(repo_root, mobile_limit_cap=mobile_limit_cap, desktop_limit_cap=desktop_limit_cap)
    theme = str(raw.get("theme") or settings["theme"]).strip().lower()
    if theme in {"default", "claude", "black-hole"}:
        settings["theme"] = theme
    agent_font_mode = str(raw.get("agent_font_mode") or settings["agent_font_mode"]).strip().lower()
    if agent_font_mode in {"serif", "gothic"}:
        settings["agent_font_mode"] = agent_font_mode
    for key, cap in (
        ("mobile_message_limit", mobile_limit_cap),
        ("desktop_message_limit", desktop_limit_cap),
    ):
        try:
            value = int(raw.get(key, settings[key]))
        except Exception:
            value = settings[key]
        settings[key] = max(10, min(cap, value))
    for key in ("chat_auto_mode", "chat_awake", "chat_sound", "chat_tts"):
        v = raw.get(key, settings[key])
        settings[key] = v in (True, "true", "1", "on") if not isinstance(v, bool) else v
    path = hub_settings_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings


def persist_thinking_totals(repo_root: Path | str, session_name: str, workspace: str, totals):
    agents = {}
    for agent in ("claude", "codex", "gemini", "copilot"):
        try:
            value = int(totals.get(agent, 0) or 0)
        except Exception:
            value = 0
        agents[agent] = max(0, value)
    path = thinking_stats_path(repo_root)
    payload = {}
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    sessions = payload.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
    # Compute delta vs previously stored values for this session (for daily tracking)
    prev_agents = {}
    if session_name in sessions and isinstance(sessions[session_name].get("agents"), dict):
        prev_agents = sessions[session_name]["agents"]
    today = time.strftime("%Y-%m-%d")
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        daily = {}
    day_entry = daily.get(today)
    if not isinstance(day_entry, dict):
        day_entry = {}
    for agent in ("claude", "codex", "gemini", "copilot"):
        new_val = agents.get(agent, 0)
        prev_val = max(0, int(prev_agents.get(agent, 0) or 0))
        delta = max(0, new_val - prev_val)
        if delta:
            day_entry[agent] = int(day_entry.get(agent, 0) or 0) + delta
    if day_entry:
        daily[today] = day_entry
    sessions[session_name] = {
        "workspace": workspace,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "agents": agents,
    }
    payload["sessions"] = sessions
    payload["daily"] = daily
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_hub_thinking_totals(repo_root: Path | str):
    totals = {agent: 0 for agent in ("claude", "codex", "gemini", "copilot")}
    session_count = 0
    by_session = {}
    path = thinking_stats_path(repo_root)
    if not path.is_file():
        return {"total_seconds": 0, "by_agent": totals, "by_session": by_session, "session_count": 0}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    sessions = raw.get("sessions") if isinstance(raw, dict) else {}
    if not isinstance(sessions, dict):
        sessions = {}
    for session_name, session_data in sessions.items():
        if not isinstance(session_data, dict):
            continue
        agents = session_data.get("agents")
        if not isinstance(agents, dict):
            continue
        used = False
        session_total = 0
        for agent in totals:
            try:
                value = int(agents.get(agent, 0) or 0)
            except Exception:
                value = 0
            value = max(0, value)
            if value:
                used = True
            totals[agent] += value
            session_total += value
        if used:
            session_count += 1
            by_session[session_name] = {
                "seconds": session_total,
                "workspace": (session_data.get("workspace") or "").strip(),
                "updated_at": (session_data.get("updated_at") or "").strip(),
            }
    daily_raw = raw.get("daily") if isinstance(raw, dict) else {}
    if not isinstance(daily_raw, dict):
        daily_raw = {}
    daily_thinking = {}
    for date_key, day_data in daily_raw.items():
        if not isinstance(day_data, dict):
            continue
        try:
            day_total = sum(max(0, int(day_data.get(a, 0) or 0)) for a in ("claude", "codex", "gemini", "copilot"))
        except Exception:
            continue
        if day_total:
            daily_thinking[date_key] = day_total
    return {
        "total_seconds": sum(totals.values()),
        "by_agent": totals,
        "by_session": by_session,
        "session_count": session_count,
        "daily_thinking": daily_thinking,
    }
