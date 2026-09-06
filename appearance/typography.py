from __future__ import annotations

import html

from backend_core.agents.registry import generate_agent_message_selectors


MESSAGE_FONT = '"anthropicSans", "SF Pro Text", "Segoe UI", "Hiragino Sans", "Yu Gothic", Meiryo, "Noto Sans CJK JP", "PingFang TC", "Microsoft JhengHei", "Noto Sans CJK TC", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans CJK KR", sans-serif'
CODE_FONT = '"jetbrainsMono", "SF Pro Text", "Segoe UI", "Hiragino Sans", "Yu Gothic", Meiryo, "Noto Sans CJK JP", "PingFang TC", "Microsoft JhengHei", "Noto Sans CJK TC", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans CJK KR", monospace'
DESKTOP_TEXT_SIZE = 13
MOBILE_TEXT_SIZE = 13
TEXT_SIZE_MIN = 8
TEXT_SIZE_MAX = 16
MESSAGE_MAX_WIDTH = 640
DESKTOP_DARK_BODY_WEIGHT = 300
DESKTOP_DARK_CODE_WEIGHT = 300
DESKTOP_LIGHT_BODY_WEIGHT = 400
DESKTOP_LIGHT_CODE_WEIGHT = 400
MOBILE_LIGHT_BODY_WEIGHT = 430
MOBILE_LIGHT_CODE_WEIGHT = 500
TEXT_LINE_HEIGHT_RATIO = 1.6


def clamp_text_size(value: object) -> int:
    size = int(value)
    return max(TEXT_SIZE_MIN, min(TEXT_SIZE_MAX, size))


def text_line_height_px(text_size: object) -> float:
    return float(text_size) * TEXT_LINE_HEIGHT_RATIO


def apply_font_tokens(text: str) -> str:
    replacements = (
        ("__MESSAGE_FONT_CSS__", MESSAGE_FONT),
        ("__CODE_FONT_CSS__", CODE_FONT),
        ("__MESSAGE_FONT__", html.escape(MESSAGE_FONT)),
        ("__CODE_FONT__", html.escape(CODE_FONT)),
        ("__MESSAGE_FONT_FAMILY__", html.escape(MESSAGE_FONT.split(",", 1)[0].strip().strip('"'))),
        ("__CODE_FONT_FAMILY__", html.escape(CODE_FONT.split(",", 1)[0].strip().strip('"'))),
    )
    resolved = text
    for old, new in replacements:
        resolved = resolved.replace(old, new)
    return resolved


def agent_detail_selectors(prefix: str = "") -> str:
    parts = []
    base = f"    {prefix}.message:not(.user):not(.system) .md-body"
    for suffix in (" p", " li", " h1", " h2", " h3", " h4", " blockquote"):
        parts.append(f"{base}{suffix}")
    return ",\n".join(parts)


def body_typography_css() -> str:
    body_weight_tokens = f"""
    html[data-theme="dark"] {{
      --body-weight: {DESKTOP_DARK_BODY_WEIGHT};
      --code-weight: {DESKTOP_DARK_CODE_WEIGHT};
    }}
    html[data-theme="light"] {{
      --body-weight: {DESKTOP_LIGHT_BODY_WEIGHT};
      --code-weight: {DESKTOP_LIGHT_CODE_WEIGHT};
    }}
    html[data-mobile="1"][data-theme="light"] {{
      --body-weight: {MOBILE_LIGHT_BODY_WEIGHT};
      --code-weight: {MOBILE_LIGHT_CODE_WEIGHT};
    }}"""
    typography_override = """
    .message.user .md-body,
    .message.user .md-body p,
    .message.user .md-body li,
    .message.user .md-body li p,
    .message:not(.user):not(.system) .md-body,
    .message:not(.user):not(.system) .md-body p,
    .message:not(.user):not(.system) .md-body li,
    .message:not(.user):not(.system) .md-body li p,
    .sysmsg-text,
    .md-body,
    .md-body p,
    .md-body li,
    .md-body li p,
    .md-body blockquote,
    .md-body blockquote p {
      font-family: var(--font-main);
      font-weight: var(--body-weight);
      font-optical-sizing: auto;
      font-variation-settings: "opsz" 16;
      font-synthesis: none;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }
    """
    return body_weight_tokens + typography_override


def chat_font_style(*, text_size: object = DESKTOP_TEXT_SIZE) -> str:
    size = clamp_text_size(text_size)
    return f"""
    :root {{
      --text-size: {size}px;
      --text-line-height: {TEXT_LINE_HEIGHT_RATIO:g};
      --message-max-width: {MESSAGE_MAX_WIDTH}px;
      --font-main: {MESSAGE_FONT};
      --font-code: {CODE_FONT};
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
      font-family: var(--font-main);
      color: var(--fg);
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    .message.user .md-body blockquote {{
      color: var(--fg);
    }}
    {generate_agent_message_selectors(" .md-body")} {{
      font-family: var(--font-main);
      color: var(--fg);
    }}
    {agent_detail_selectors()} {{
      font-family: var(--font-main);
      color: var(--fg);
    }}
    {body_typography_css()}
    """
