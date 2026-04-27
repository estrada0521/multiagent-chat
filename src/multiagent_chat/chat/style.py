from __future__ import annotations


def _agent_markdown_selectors(*suffixes: str, prefix: str = "") -> str:
    """Generate generic agent message markdown selectors."""
    parts = []
    suffix_list = suffixes or ("",)
    base = f"    {prefix}.message:not(.user):not(.system) .md-body"
    for suffix in suffix_list:
        parts.append(f"{base}{suffix}")
    return ",\n".join(parts)


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
    .dp-pane-title,
    .repo-browser-item-name,
    .repo-browser-path,
    .repo-browser-item-size,
    .git-branch-summary-label,
    .git-branch-summary-meta-text,
    .git-branch-summary-count,
    .git-commit-subject,
    .git-commit-meta,
    .git-commit-time,
    .git-commit-file-path,
    .git-commit-file-meta,
    .file-modal-title,
    .file-modal-text,
    .attached-files-sheet-title,
    {agent_body_selectors},
    {agent_body_selectors_gothic} {{
      font-weight: 620 !important;
      font-variation-settings: normal !important;
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
      font-weight: 700 !important;
      font-variation-settings: normal !important;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    .composer textarea {{
      font-weight: 620 !important;
      font-variation-settings: normal !important;
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
    """Generate agent .md-body detail selectors."""
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
