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
    try:
        _legacy_size = max(8, min(18, int(settings.get("message_text_size", 13))))
    except Exception:
        _legacy_size = 13
    try:
        message_text_size_desktop = max(8, min(18, int(settings.get("message_text_size_desktop") or _legacy_size)))
    except Exception:
        message_text_size_desktop = _legacy_size
    try:
        message_text_size_mobile = max(8, min(18, int(settings.get("message_text_size_mobile") or _legacy_size)))
    except Exception:
        message_text_size_mobile = _legacy_size
    message_max_width = 900

    bold_parts: list[str] = []
    non_tauri_desktop_scope = 'html:not([data-tauri-app="1"][data-hub-iframe-chat="1"])'
    if settings.get("bold_mode_mobile"):
        mobile_inner = chat_bold_mode_rules_block_fn(non_tauri_desktop_scope)
        bold_parts.append(
            f"@media (max-width: {bold_mode_viewport_max_px}px) {{\n{mobile_inner}\n    }}"
        )
    bold_style = "\n".join(bold_parts)
    mobile_text_size_override = ""
    if message_text_size_mobile != message_text_size_desktop:
        non_tauri = 'html:not([data-tauri-app="1"][data-hub-iframe-chat="1"])'
        mobile_text_size_override = f"""
    @media (max-width: {bold_mode_viewport_max_px}px) {{
      {non_tauri} {{
        --message-text-size: {message_text_size_mobile}px;
        --message-text-line-height: {message_text_size_mobile + 9}px;
      }}
    }}"""
    return f"""
    :root {{
      --message-text-size: {message_text_size_desktop}px;
      --message-text-line-height: {message_text_size_desktop + 9}px;
      --message-max-width: {message_max_width}px;
      --user-message-font-family: {user_family};
      --agent-message-font-family: {agent_family};
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
      color: var(--fg);
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    .message.user .md-body blockquote {{
      color: var(--fg);
    }}
    {generate_agent_message_selectors_fn(" .md-body")} {{
      font-family: var(--agent-message-font-family);
      color: var(--fg);
    }}
    {bh_agent_detail_selectors_fn(prefix="")} {{
      color: var(--fg);
    }}
    {bold_style}
    {mobile_text_size_override}
    """
