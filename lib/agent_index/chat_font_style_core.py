from __future__ import annotations


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
    theme = str(settings.get("theme", "black-hole") or "black-hole").strip().lower()
    try:
        message_text_size = max(11, min(18, int(settings.get("message_text_size", 13))))
    except Exception:
        message_text_size = 13
    try:
        message_max_width = max(400, min(2000, int(settings.get("message_max_width", 900))))
    except Exception:
        message_max_width = 900
    try:
        user_opacity = max(0.2, min(1.0, float(settings.get("user_message_opacity_blackhole", 1.0))))
    except Exception:
        user_opacity = 1.0
    try:
        agent_opacity = max(0.2, min(1.0, float(settings.get("agent_message_opacity_blackhole", 1.0))))
    except Exception:
        agent_opacity = 1.0
    if theme == "black-hole":
        user_color = f"rgba(252, 252, 252, {user_opacity:.2f})"
        agent_color = f"rgba(252, 252, 252, {agent_opacity:.2f})"
    else:
        # Light themes should inherit dark foreground tones.
        user_color = f"rgba(26, 30, 36, {user_opacity:.2f})"
        agent_color = f"rgba(26, 30, 36, {agent_opacity:.2f})"

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
      --message-text-size: {message_text_size}px;
      --message-text-line-height: {message_text_size + 9}px;
      --message-max-width: {message_max_width}px;
      --user-message-blackhole-color: {user_color};
      --agent-message-blackhole-color: {agent_color};
      --agent-thinking-font-family: {agent_family};
      --agent-thinking-body-variation: {thinking_body_variation};
      --agent-thinking-keyword-variation: {thinking_keyword_variation};
      --agent-thinking-letter-spacing: {thinking_letter_spacing};
    }}
    .shell {{
      max-width: var(--message-max-width) !important;
    }}
    .composer {{
      width: min(var(--message-max-width), calc(100vw - 24px)) !important;
      max-width: var(--message-max-width) !important;
    }}
    .composer-main-shell {{
      max-width: var(--message-max-width) !important;
    }}
    .statusline {{
      width: min(var(--message-max-width), calc(100vw - 16px)) !important;
    }}
    .brief-editor-panel {{
      width: min(92vw, var(--message-max-width)) !important;
      max-width: var(--message-max-width) !important;
    }}
    .message.user .md-body {{
      font-family: {user_family} !important;
      color: var(--user-message-blackhole-color) !important;
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    .message.user .md-body blockquote {{
      color: var(--user-message-blackhole-color) !important;
    }}
    {generate_agent_message_selectors_fn(" .md-body")} {{
      font-family: {agent_family} !important;
      color: var(--agent-message-blackhole-color) !important;
    }}
    {bh_agent_detail_selectors_fn(prefix="")} {{
      color: var(--agent-message-blackhole-color) !important;
    }}
    {bold_style}
    """
