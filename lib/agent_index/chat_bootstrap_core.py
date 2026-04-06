from __future__ import annotations

import json


def build_chat_bootstrap_payload(
    *,
    icon_data_uris: dict,
    server_instance: str,
    hub_port: int,
    chat_settings: dict,
    chat_base_path: str,
    agent_icon_names: list[str],
    all_base_agents: list[str],
) -> dict:
    return {
        "basePath": (chat_base_path or "").rstrip("/"),
        "iconDataUris": icon_data_uris,
        "serverInstance": server_instance,
        "hubPort": int(hub_port),
        "messageLimit": int(chat_settings["message_limit"]),
        "chatSoundEnabled": bool(chat_settings.get("chat_sound", False)),
        "chatBrowserNotificationsEnabled": bool(chat_settings.get("chat_browser_notifications", False)),
        "chatTtsEnabled": bool(chat_settings.get("chat_tts", False)),
        "agentIconNames": list(agent_icon_names or []),
        "allBaseAgents": list(all_base_agents or []),
    }


def encode_chat_bootstrap_payload(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True).replace("</", r"<\/")
