from __future__ import annotations

import json


def _js_bool(value: object) -> str:
    return "true" if bool(value) else "false"


def build_chat_template_replacements(
    *,
    icon_data_uris: dict,
    logo_src: str,
    base_path: str,
    chat_manifest_url: str,
    chat_pwa_icon_192_url: str,
    chat_apple_touch_icon_url: str,
    chat_style_asset_url: str,
    chat_app_bootstrap_html: str,
    chat_app_asset_url: str,
    server_instance: str,
    hub_port: int,
    chat_settings: dict,
    agent_font_mode_inline_style: str,
    hub_header_css: str,
) -> dict[str, str]:
    return {
        "__ICON_DATA_URIS__": json.dumps(icon_data_uris, ensure_ascii=True),
        "__HUB_LOGO_DATA_URI__": logo_src,
        "__CHAT_BASE_PATH__": base_path,
        "__CHAT_MANIFEST_URL__": chat_manifest_url,
        "__CHAT_PWA_ICON_192_URL__": chat_pwa_icon_192_url,
        "__CHAT_APPLE_TOUCH_ICON_URL__": chat_apple_touch_icon_url,
        "__CHAT_STYLE_ASSET_URL__": chat_style_asset_url,
        "__CHAT_APP_BOOTSTRAP__": chat_app_bootstrap_html,
        "__CHAT_APP_ASSET_URL__": chat_app_asset_url,
        "__SERVER_INSTANCE__": server_instance,
        "__HUB_PORT__": str(hub_port),
        "__CHAT_SOUND_ENABLED__": _js_bool(chat_settings.get("chat_sound", False)),
        "__CHAT_BROWSER_NOTIFICATIONS_ENABLED__": _js_bool(chat_settings.get("chat_browser_notifications", False)),
        "__AGENT_FONT_MODE__": str(chat_settings["agent_font_mode"]),
        "__AGENT_FONT_MODE_INLINE_STYLE__": agent_font_mode_inline_style,
        "__HUB_HEADER_CSS__": hub_header_css,
    }


def apply_chat_template_replacements(template: str, replacements: dict[str, str]) -> str:
    html = template
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html
