from __future__ import annotations

import html
import re
from pathlib import Path


def normalized_font_label(name: str) -> str:
    label = re.sub(r"\.(ttf|ttc|otf)$", "", name, flags=re.IGNORECASE)
    label = re.sub(
        r"[-_](Variable|Italic|Italics|Roman|Romans|Regular|Medium|Light|Bold|Heavy|Black|Condensed|Rounded|Mono)\b",
        "",
        label,
        flags=re.IGNORECASE,
    )
    label = re.sub(r"\s+", " ", label).strip(" -_")
    return label


def available_chat_font_choices(*, path_class=Path, normalized_font_label_fn=normalized_font_label):
    seen = set()
    choices = [
        ("preset-gothic", "Default Gothic"),
        ("preset-mincho", "Default Mincho"),
    ]
    curated_families = [
        ("system:Hiragino Sans", "Hiragino Sans"),
        ("system:Hiragino Kaku Gothic ProN", "Hiragino Kaku Gothic ProN"),
        ("system:Hiragino Maru Gothic ProN", "Hiragino Maru Gothic ProN"),
        ("system:Hiragino Mincho ProN", "Hiragino Mincho ProN"),
        ("system:Yu Gothic", "Yu Gothic"),
        ("system:Yu Gothic UI", "Yu Gothic UI"),
        ("system:Yu Mincho", "Yu Mincho"),
        ("system:Meiryo", "Meiryo"),
        ("system:BIZ UDPGothic", "BIZ UDPGothic"),
        ("system:BIZ UDPMincho", "BIZ UDPMincho"),
        ("system:Noto Sans JP", "Noto Sans JP"),
        ("system:Noto Serif JP", "Noto Serif JP"),
        ("system:Zen Kaku Gothic New", "Zen Kaku Gothic New"),
        ("system:Zen Maru Gothic", "Zen Maru Gothic"),
        ("system:Shippori Mincho", "Shippori Mincho"),
        ("system:Sawarabi Gothic", "Sawarabi Gothic"),
        ("system:Sawarabi Mincho", "Sawarabi Mincho"),
    ]
    for value, label in curated_families:
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        choices.append((value, label))
    for root in (
        path_class("/System/Library/Fonts"),
        path_class("/Library/Fonts"),
        path_class.home() / "Library/Fonts",
    ):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".ttf", ".ttc", ".otf"}:
                continue
            label = normalized_font_label_fn(path.name)
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            choices.append((f"system:{label}", label))
            if len(choices) >= 96:
                break
        if len(choices) >= 96:
            break
    return choices


def hub_settings_html(
    *,
    saved: bool,
    load_hub_settings_fn,
    available_chat_font_choices_fn,
    settings_template: str,
    pwa_hub_manifest_url: str,
    pwa_icon_192_url: str,
    pwa_apple_touch_icon_url: str,
    hub_header_css: str,
    hub_header_html: str,
    hub_header_js: str,
    view_variant: str = "desktop",
):
    resolved_view_variant = "mobile" if str(view_variant or "").strip().lower() == "mobile" else "desktop"
    settings = load_hub_settings_fn()
    font_mode = settings["agent_font_mode"]
    user_message_font = settings.get("user_message_font", "preset-gothic")
    agent_message_font = settings.get("agent_message_font", "preset-mincho")
    message_text_size = int(settings.get("message_text_size", 13) or 13)
    chat_auto = settings.get("chat_auto_mode", False)
    chat_awake = settings.get("chat_awake", False)
    chat_sound = settings.get("chat_sound", False)
    chat_browser_notifications = settings.get("chat_browser_notifications", False)
    bold_mode_mobile = settings.get("bold_mode_mobile", False)
    bold_mode_desktop = settings.get("bold_mode_desktop", False)
    font_choices = available_chat_font_choices_fn()
    font_options = lambda selected: "".join(
        f'<option value="{html.escape(value)}"' + (' selected' if value == selected else '') + f'>{html.escape(label)}</option>'
        for value, label in font_choices
    )
    notice = '<div style="margin:0 0 14px;color:rgb(170,190,172);font-size:13px;line-height:1.5;">Saved.</div>' if saved else ""
    page = settings_template
    page = (
        page
        .replace("__HUB_MANIFEST_URL__", pwa_hub_manifest_url)
        .replace("__PWA_ICON_192_URL__", pwa_icon_192_url)
        .replace("__APPLE_TOUCH_ICON_URL__", pwa_apple_touch_icon_url)
        .replace("__NOTICE_HTML__", notice)
        .replace("__USER_MESSAGE_FONT_OPTIONS__", font_options(user_message_font))
        .replace("__AGENT_MESSAGE_FONT_OPTIONS__", font_options(agent_message_font))
        .replace("__FONT_MODE__", font_mode)
        .replace("__MESSAGE_TEXT_SIZE__", str(message_text_size))
        .replace("__CHAT_AUTO_CHECKED__", " checked" if chat_auto else "")
        .replace("__CHAT_AWAKE_CHECKED__", " checked" if chat_awake else "")
        .replace("__CHAT_SOUND_CHECKED__", " checked" if chat_sound else "")
        .replace("__CHAT_BROWSER_NOTIF_CHECKED__", " checked" if chat_browser_notifications else "")
        .replace("__BOLD_MODE_MOBILE_CHECKED__", " checked" if bold_mode_mobile else "")
        .replace("__BOLD_MODE_DESKTOP_CHECKED__", " checked" if bold_mode_desktop else "")
        .replace("__VIEW_VARIANT__", resolved_view_variant)
    )
    return (
        page
        .replace("__HUB_HEADER_CSS__", hub_header_css)
        .replace("__HUB_HEADER_HTML__", hub_header_html)
        .replace("__HUB_HEADER_JS__", hub_header_js)
    )
