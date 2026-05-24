from __future__ import annotations


def _agent_markdown_selectors(*suffixes: str, prefix: str = "") -> str:
    parts = []
    suffix_list = suffixes or ("",)
    base = f"    {prefix}.message:not(.user):not(.system) .md-body"
    for suffix in suffix_list:
        parts.append(f"{base}{suffix}")
    return ",\n".join(parts)


BOLD_MODE_VIEWPORT_MAX_PX = 480


def _chat_bold_mode_rules_block(html_scope: str = "") -> str:
    scope = str(html_scope or "").strip()
    selector_prefix = f"{scope} " if scope else ""
    gothic_prefix = f'{scope}[data-agent-font-mode="gothic"] ' if scope else 'html[data-agent-font-mode="gothic"] '

    def scoped(selector: str) -> str:
        return f"{selector_prefix}{selector}"

    agent_body_selectors = _agent_markdown_selectors(
        "", " p", " li", " li p", " blockquote", " blockquote p", prefix=selector_prefix
    )
    agent_heading_selectors = _agent_markdown_selectors(" h1", " h2", " h3", " h4", prefix=selector_prefix)
    agent_body_selectors_gothic = _agent_markdown_selectors(
        "",
        " p",
        " li",
        " li p",
        " blockquote",
        " blockquote p",
        prefix=gothic_prefix,
    )
    agent_heading_selectors_gothic = _agent_markdown_selectors(
        " h1",
        " h2",
        " h3",
        " h4",
        prefix=gothic_prefix,
    )
    return f"""
    {scoped(".message.user .md-body")},
    {scoped(".message.user .md-body p")},
    {scoped(".message.user .md-body li")},
    {scoped(".message.user .md-body li p")},
    {scoped(".message.user .md-body blockquote")},
    {scoped(".message.user .md-body blockquote p")},
    {scoped(".sysmsg-row")},
    {scoped(".sysmsg-text")},
    {scoped(".dp-pane-title")},
    {scoped(".repo-browser-item-name")},
    {scoped(".repo-browser-path")},
    {scoped(".repo-browser-item-size")},
    {scoped(".git-branch-summary-label")},
    {scoped(".git-branch-summary-meta-text")},
    {scoped(".git-branch-summary-count")},
    {scoped(".git-commit-subject")},
    {scoped(".git-commit-meta")},
    {scoped(".git-commit-time")},
    {scoped(".file-modal-title")},
    {scoped(".file-modal-text")},
    {scoped(".attached-files-sheet-title")},
    {agent_body_selectors},
    {agent_body_selectors_gothic} {{
      font-weight: 620;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    {scoped(".message.user .md-body h1")},
    {scoped(".message.user .md-body h2")},
    {scoped(".message.user .md-body h3")},
    {scoped(".message.user .md-body h4")},
    {agent_heading_selectors},
    {agent_heading_selectors_gothic} {{
      font-weight: 700;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    {scoped(".composer textarea")} {{
      font-weight: 620;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    {scoped(".message-thinking-container")},
    {scoped(".message-thinking-container .message-thinking-label")},
    {scoped(".message-thinking-container .message-thinking-label-primary")},
    {scoped(".message-thinking-container .message-thinking-runtime-line")},
    {scoped(".message-thinking-container .message-thinking-label-live")},
    {scoped(".message-thinking-container .message-thinking-label-preview")} {{
      font-weight: 620;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    {scoped(".message-thinking-runtime-keyword")} {{
      font-weight: 700;
      font-variation-settings: normal;
      font-synthesis: weight;
      font-synthesis-weight: auto;
      -webkit-font-smoothing: antialiased;
    }}
    """


def _bh_agent_detail_selectors(prefix: str = "") -> str:
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
