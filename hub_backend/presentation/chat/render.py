from __future__ import annotations

import json

from hub_backend.branding import APP_DISPLAY_NAME


def build_chat_template_replacements(
    *,
    icon_data_uris: dict,
    base_path: str,
    chat_manifest_url: str,
    chat_pwa_icon_192_url: str,
    chat_apple_touch_icon_url: str,
    chat_service_worker_html: str,
    server_instance: str,
    hub_port: int,
    text_size_default: int,
    chat_font_settings_inline_style: str,
    hub_header_css: str,
    chat_document_title: str = APP_DISPLAY_NAME,
) -> dict[str, str]:
    return {
        "__ICON_DATA_URIS__": json.dumps(icon_data_uris, ensure_ascii=True),
        "__CHAT_BASE_PATH__": base_path,
        "__CHAT_MANIFEST_URL__": chat_manifest_url,
        "__CHAT_PWA_ICON_192_URL__": chat_pwa_icon_192_url,
        "__CHAT_APPLE_TOUCH_ICON_URL__": chat_apple_touch_icon_url,
        "__CHAT_SERVICE_WORKER_HTML__": chat_service_worker_html,
        "__SERVER_INSTANCE__": server_instance,
        "__HUB_PORT__": str(hub_port),
        "__TEXT_SIZE_DEFAULT__": str(text_size_default),
        "__CHAT_FONT_SETTINGS_INLINE_STYLE__": chat_font_settings_inline_style,
        "__HUB_HEADER_CSS__": hub_header_css,
        "__APP_DISPLAY_NAME__": APP_DISPLAY_NAME,
        "__CHAT_DOCUMENT_TITLE__": chat_document_title,
    }


def apply_chat_template_replacements(template: str, replacements: dict[str, str]) -> str:
    html = template
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html
