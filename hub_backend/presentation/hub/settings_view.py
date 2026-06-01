from __future__ import annotations

import html
import re
from pathlib import Path

from hub_backend.branding import APP_DISPLAY_NAME
from hub_backend.color_constants import apply_color_tokens
from hub_backend.server_helpers import apply_hub_page_branding
from backend_core.access.settings import sanitize_hub_external_editor_choice


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
        # English — Serif
        ("system:Georgia", "Georgia"),
        ("system:Baskerville", "Baskerville"),
        ("system:Palatino", "Palatino"),
        ("system:Didot", "Didot"),
        ("system:Big Caslon", "Big Caslon"),
        ("system:American Typewriter", "American Typewriter"),
        ("system:Times New Roman", "Times New Roman"),
        # English — Sans-serif
        ("system:Helvetica Neue", "Helvetica Neue"),
        ("system:Gill Sans", "Gill Sans"),
        ("system:Futura", "Futura"),
        ("system:Optima", "Optima"),
        ("system:Avenir", "Avenir"),
        ("system:Avenir Next", "Avenir Next"),
        ("system:Arial", "Arial"),
        # Japanese
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
            if len(choices) >= 300:
                break
        if len(choices) >= 300:
            break
    return choices


def hub_settings_html(
    *,
    saved: bool,
    load_hub_settings_fn,
    available_chat_font_choices_fn,
    available_external_editor_choices_fn,
    available_markdown_external_editor_choices_fn,
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
    message_text_size_mobile = int(settings.get("message_text_size_mobile") or message_text_size)
    message_text_size_desktop = int(settings.get("message_text_size_desktop") or message_text_size)
    chat_auto = settings.get("chat_auto_mode", False)
    chat_awake = settings.get("chat_awake", False)
    theme = str(settings.get("theme", "dark") or "dark").strip().lower()
    light_mode = theme == "light"
    light_mode_desktop = str(settings.get("theme_desktop", theme) or theme).strip().lower() == "light"
    light_mode_mobile = str(settings.get("theme_mobile", theme) or theme).strip().lower() == "light"
    render_theme = "light" if (light_mode_desktop if resolved_view_variant == "desktop" else light_mode_mobile) else "dark"
    bold_mode_mobile = settings.get("bold_mode_mobile", False)
    open_files_direct_external_editor = settings.get("open_files_direct_external_editor", False)
    external_editor = sanitize_hub_external_editor_choice(
        str(settings.get("external_editor", "vscode") or "vscode").strip(),
        allow_markedit=False,
    )
    external_editor_markdown = sanitize_hub_external_editor_choice(
        str(settings.get("external_editor_markdown", "markedit") or "markedit").strip(),
        allow_markedit=True,
    )
    font_choices = available_chat_font_choices_fn()
    font_options = lambda selected: "".join(
        f'<option value="{html.escape(value)}"' + (' selected' if value == selected else '') + f'>{html.escape(label)}</option>'
        for value, label in font_choices
    )
    def _build_editor_options(choices_fn, selected: str) -> tuple[str, str]:
        raw_choices = choices_fn()
        sanitized: list[tuple[str, str]] = []
        seen_vals: set[str] = set()
        for value, label in raw_choices:
            value_text = str(value or "").strip()
            label_text = str(label or "").strip()
            if not value_text or not label_text or value_text in seen_vals:
                continue
            seen_vals.add(value_text)
            sanitized.append((value_text, label_text))
        resolved = selected
        if not any(value == resolved for value, _ in sanitized):
            if resolved.startswith("app:") and resolved[4:].strip():
                sanitized.append((resolved, resolved[4:].strip()))
            elif resolved == "markedit":
                sanitized.insert(0, ("markedit", "MarkEdit"))
            else:
                resolved = "vscode" if choices_fn is available_external_editor_choices_fn else "markedit"
        if not sanitized:
            sanitized = [
                ("vscode", "VS Code"),
                ("coteditor", "CotEditor"),
                ("system", "System Default"),
            ]
        options_html = "".join(
            f'<option value="{html.escape(value)}"' + (' selected' if value == resolved else '') + f'>{html.escape(label)}</option>'
            for value, label in sanitized
        )
        return options_html, resolved

    external_editor_options, external_editor = _build_editor_options(
        available_external_editor_choices_fn, external_editor
    )
    markdown_editor_options, external_editor_markdown = _build_editor_options(
        available_markdown_external_editor_choices_fn, external_editor_markdown
    )
    notice = ""
    page = settings_template
    page = (
        page
        .replace("__HUB_MANIFEST_URL__", pwa_hub_manifest_url)
        .replace("__PWA_ICON_192_URL__", pwa_icon_192_url)
        .replace("__APPLE_TOUCH_ICON_URL__", pwa_apple_touch_icon_url)
        .replace("__NOTICE_HTML__", notice)
        .replace("__USER_MESSAGE_FONT_OPTIONS__", font_options(user_message_font))
        .replace("__AGENT_MESSAGE_FONT_OPTIONS__", font_options(agent_message_font))
        .replace("__EXTERNAL_EDITOR_OPTIONS__", external_editor_options)
        .replace("__MARKDOWN_EXTERNAL_EDITOR_OPTIONS__", markdown_editor_options)
        .replace("__FONT_MODE__", font_mode)
        .replace("__MESSAGE_TEXT_SIZE__", str(message_text_size))
        .replace("__MESSAGE_TEXT_SIZE_MOBILE__", str(message_text_size_mobile))
        .replace("__MESSAGE_TEXT_SIZE_DESKTOP__", str(message_text_size_desktop))
        .replace("__CHAT_AUTO_CHECKED__", " checked" if chat_auto else "")
        .replace("__CHAT_AWAKE_CHECKED__", " checked" if chat_awake else "")
        .replace("__LIGHT_MODE_CHECKED__", " checked" if light_mode else "")
        .replace("__LIGHT_MODE_DESKTOP_CHECKED__", " checked" if light_mode_desktop else "")
        .replace("__LIGHT_MODE_MOBILE_CHECKED__", " checked" if light_mode_mobile else "")
        .replace("__THEME_MOBILE_HIDDEN__", html.escape("light" if light_mode_mobile else "dark"))
        .replace("__THEME_DESKTOP_HIDDEN__", html.escape("light" if light_mode_desktop else "dark"))
        .replace("__BOLD_MODE_MOBILE_CHECKED__", " checked" if bold_mode_mobile else "")
        .replace("__OPEN_FILES_DIRECT_EXTERNAL_EDITOR_CHECKED__", " checked" if open_files_direct_external_editor else "")
        .replace(
            "__OPEN_FILES_DIRECT_EXTERNAL_EDITOR_HIDDEN__",
            html.escape("on" if open_files_direct_external_editor else ""),
        )
        .replace("__EXTERNAL_EDITOR_MARKDOWN_HIDDEN__", html.escape(external_editor_markdown))
        .replace("__BOLD_MODE_MOBILE_HIDDEN__", html.escape("on" if bold_mode_mobile else ""))
        .replace("__VIEW_VARIANT__", resolved_view_variant)
    )
    page = (
        page
        .replace("__HUB_HEADER_CSS__", hub_header_css)
        .replace("__HUB_HEADER_HTML__", hub_header_html)
        .replace("__HUB_HEADER_JS__", hub_header_js)
    )
    page = apply_hub_page_branding(page, page_title=f"Settings · {APP_DISPLAY_NAME}")
    render_settings = dict(settings, theme=render_theme)
    return apply_color_tokens(page, settings=render_settings)
