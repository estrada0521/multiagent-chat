from __future__ import annotations

from .agent_registry import ALL_AGENT_NAMES


def _agent_markdown_selectors(*suffixes: str, prefix: str = "") -> str:
    """Generate .message.{agent} .md-body selectors for the given suffixes."""
    parts = []
    suffix_list = suffixes or ("",)
    for name in ALL_AGENT_NAMES:
        base = f"    {prefix}.message.{name} .md-body"
        for suffix in suffix_list:
            parts.append(f"{base}{suffix}")
    return ",\n".join(parts)


# Viewport split for bold_mode_mobile (narrow) vs bold_mode_desktop (wide).
# Intentionally below typical tablet width so “mobile” bold applies to phone-sized viewports only.
BOLD_MODE_VIEWPORT_MAX_PX = 480


def _chat_bold_mode_rules_block() -> str:
    """CSS rules that make message / thinking text bold; wrapped in @media by caller."""
    agent_body_selectors = _agent_markdown_selectors("", " p", " li", " li p", " blockquote", " blockquote p")
    agent_heading_selectors = _agent_markdown_selectors(" h1", " h2", " h3", " h4")
    agent_body_selectors_gothic = _agent_markdown_selectors(
        "",
        " p",
        " li",
        " li p",
        " blockquote",
        " blockquote p",
        prefix='html[data-agent-font-mode="gothic"] ',
    )
    agent_heading_selectors_gothic = _agent_markdown_selectors(
        " h1",
        " h2",
        " h3",
        " h4",
        prefix='html[data-agent-font-mode="gothic"] ',
    )
    return f"""
    .message.user .md-body,
    .message.user .md-body p,
    .message.user .md-body li,
    .message.user .md-body li p,
    .message.user .md-body blockquote,
    .message.user .md-body blockquote p,
    {agent_body_selectors},
    {agent_body_selectors_gothic} {{
      font-weight: 620;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4,
    {agent_heading_selectors},
    {agent_heading_selectors_gothic} {{
      font-weight: 700;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    .composer textarea {{
      font-weight: 620;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    .message-thinking-container,
    .message-thinking-container .message-thinking-label,
    .message-thinking-container .message-thinking-label-primary,
    .message-thinking-container .message-thinking-runtime-line,
    .message-thinking-container .message-thinking-label-live,
    .message-thinking-container .message-thinking-label-preview,
    .camera-mode-thinking {{
      font-weight: 620;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    .message-thinking-runtime-keyword {{
      font-weight: 700;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    """


def _bh_agent_detail_selectors(prefix: str = "") -> str:
    """Generate .message.{agent} .md-body {p,li,h1..h4,blockquote} selectors."""
    return _agent_markdown_selectors(
        " p",
        " li",
        " h1",
        " h2",
        " h3",
        " h4",
        " blockquote",
        prefix=prefix,
    )
