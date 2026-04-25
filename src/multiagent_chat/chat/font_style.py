from __future__ import annotations

from ..color_constants import resolve_theme_palette


def font_family_stack(selection: str, role: str) -> str:
    value = str(selection or "").strip()
    sans_stack = '"anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif'
    serif_stack = '"anthropicSerif", "anthropicSerif Fallback", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, "Times New Roman", Times, serif'
    default_stack = sans_stack if role == "user" else serif_stack
    if value == "preset-gothic":
        return sans_stack
    if value == "preset-mincho":
        return serif_stack
    if value.startswith("system:"):
        family = value.split(":", 1)[1].strip()
        if family:
            return f'"{family}", {default_stack}'
    return default_stack


def chat_font_settings_inline_style(
    settings: dict,
    *,
    bold_mode_viewport_max_px: int,
    generate_agent_message_selectors_fn,
    chat_bold_mode_rules_block_fn,
    bh_agent_detail_selectors_fn,
    font_family_stack_fn=font_family_stack,
) -> str:
    user_family = font_family_stack_fn(settings.get("user_message_font", "preset-gothic"), "user")
    agent_family = font_family_stack_fn(settings.get("agent_message_font", "preset-mincho"), "agent")
    agent_font_mode = str(settings.get("agent_font_mode", "serif") or "serif").strip().lower()
    if agent_font_mode == "gothic":
        thinking_body_variation = '"wght" 360, "opsz" 16'
        thinking_keyword_variation = '"wght" 530, "opsz" 16'
        thinking_letter_spacing = "-0.01em"
    else:
        thinking_body_variation = '"wght" 360'
        thinking_keyword_variation = '"wght" 530'
        thinking_letter_spacing = "0"
    try:
        message_text_size = max(11, min(18, int(settings.get("message_text_size", 13))))
    except Exception:
        message_text_size = 13
    message_max_width = 900
    palette = resolve_theme_palette(settings)
    user_color = str(palette["light_fg"])
    agent_color = str(palette["light_fg"])
    bg_channels = str(palette["dark_bg_channels"])
    text_channels = str(palette["light_fg_channels"])
    bright_text = str(palette["light_fg_bright"])

    bold_parts: list[str] = []
    inner = chat_bold_mode_rules_block_fn()
    if settings.get("bold_mode_mobile"):
        bold_parts.append(
            f"@media (max-width: {bold_mode_viewport_max_px}px) {{\n{inner}\n    }}"
        )
    if settings.get("bold_mode_desktop"):
        bold_parts.append(
            f"@media (min-width: {bold_mode_viewport_max_px + 1}px) {{\n{inner}\n    }}"
        )
    bold_style = "\n".join(bold_parts)
    return f"""
    :root {{
      --bg-rgb: {bg_channels};
      --bg: rgb(var(--bg-rgb));
      --text-rgb: {text_channels};
      --text: rgb(var(--text-rgb));
      --fg-bright: {bright_text};
      --message-text-size: {message_text_size}px;
      --message-text-line-height: {message_text_size + 9}px;
      --message-max-width: {message_max_width}px;
      --user-message-font-family: {user_family};
      --agent-message-font-family: {agent_family};
      --user-message-blackhole-color: {user_color};
      --agent-message-blackhole-color: {agent_color};
      --agent-thinking-font-family: {agent_family};
      --agent-thinking-body-variation: {thinking_body_variation};
      --agent-thinking-keyword-variation: {thinking_keyword_variation};
      --agent-thinking-letter-spacing: {thinking_letter_spacing};
    }}
    .shell {{
      max-width: var(--message-max-width);
    }}
    .composer {{
      width: min(var(--composer-overlay-max-width, var(--message-max-width)), calc(100vw - 24px));
      max-width: var(--composer-overlay-max-width, var(--message-max-width));
    }}
    .composer-main-shell {{
      max-width: var(--composer-overlay-max-width, var(--message-max-width));
    }}
    .statusline {{
      width: min(var(--composer-overlay-max-width, var(--message-max-width)), calc(100vw - 16px));
    }}
    .message.user .md-body {{
      font-family: var(--user-message-font-family);
      color: var(--user-message-blackhole-color);
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    .message.user .md-body blockquote {{
      color: var(--user-message-blackhole-color);
    }}
    {generate_agent_message_selectors_fn(" .md-body")} {{
      font-family: var(--agent-message-font-family);
      color: var(--agent-message-blackhole-color);
    }}
    {bh_agent_detail_selectors_fn(prefix="")} {{
      color: var(--agent-message-blackhole-color);
    }}
    {bold_style}
    """
