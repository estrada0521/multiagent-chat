from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .agent_registry import (
    ALL_AGENT_NAMES,
    generate_accent_css,
    generate_thinking_glow_css,
    agent_names_js_set,
    agent_names_js_array,
)
from .hub_header_assets import HUB_PAGE_HEADER_CSS, render_hub_page_header

CHAT_HTML = (Path(__file__).resolve().parent / "chat_template.html").read_text()

CHAT_HEADER_ACTIONS_HTML = """
<button type="button" class="hub-page-menu-btn" id="gitBranchMenuBtn" title="Git branch overview" aria-label="Git branch overview">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3v12"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="6" r="3"></circle><circle cx="18" cy="18" r="3"></circle><path d="M9 6h6"></path><path d="M9 18h6"></path><path d="M18 9v6"></path></svg>
</button>
<button type="button" class="hub-page-menu-btn" id="attachedFilesMenuBtn" title="Attached files" aria-label="Attached files">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</button>
<button type="button" class="hub-page-menu-btn" id="hubPageMenuBtn" title="Menu" aria-label="Menu">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="3" y1="8" x2="21" y2="8"/><line x1="6" y1="16" x2="21" y2="16"/></svg>
</button>
"""

CHAT_HEADER_PANELS_HTML = """
<div class="hub-page-menu-panel" id="gitBranchPanel" hidden></div>
<div class="hub-page-menu-panel" id="attachedFilesPanel" hidden></div>
<div class="hub-page-menu-panel" id="hubPageMenuPanel" hidden>
  <div class="hub-main-menu-stack">
    <div class="hub-main-menu-list-view">
      <button type="button" class="hub-page-menu-item" data-forward-action="reloadChat"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 3v6h-6"></path><path d="M20 9a8 8 0 1 0 2 5.3"></path></svg></span><span class="action-label">Reload</span><span class="action-mobile">Reload</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="openTerminal"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg></span><span class="action-label">Terminal</span><span class="action-mobile">Terminal</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="exportBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg></span><span class="action-label">Export</span><span class="action-mobile">Export</span></button>
      <button type="button" class="hub-page-menu-item positive" data-forward-action="addAgent"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="22" y1="11" x2="16" y2="11"></line><line x1="19" y1="8" x2="19" y2="14"></line></svg></span><span class="action-label">Add Agent</span><span class="action-mobile">Add Agent</span></button>
      <button type="button" class="hub-page-menu-item danger" data-forward-action="removeAgent"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="22" y1="11" x2="16" y2="11"></line></svg></span><span class="action-label">Remove Agent</span><span class="action-mobile">Remove</span></button>
    </div>
    <div id="paneViewer" class="pane-viewer">
      <div class="git-commit-detail-body pane-viewer-detail-body">
        <div class="pane-viewer-tabs" id="paneViewerTabs"></div>
        <div class="pane-viewer-carousel" id="paneViewerCarousel"></div>
      </div>
    </div>
  </div>
</div>
"""


CHAT_ANSI_UP_HEAD_TAG = '  <script src="https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js"></script>\n'
CHAT_KATEX_HEAD_TAGS = (
    '  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">\n'
    '  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>\n'
    '  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>\n'
)


_CHAT_APP_SCRIPT_OPEN = "  <script>\n"
_CHAT_APP_SCRIPT_CLOSE = "  </script>\n"
_chat_app_script_start = CHAT_HTML.rfind(_CHAT_APP_SCRIPT_OPEN)
if _chat_app_script_start < 0:
    raise ValueError("chat app script block not found")
_chat_app_script_end = CHAT_HTML.find(_CHAT_APP_SCRIPT_CLOSE, _chat_app_script_start)
if _chat_app_script_end < 0:
    raise ValueError("chat app script close tag not found")
CHAT_APP_SCRIPT_BLOCK = CHAT_HTML[
    _chat_app_script_start:_chat_app_script_end + len(_CHAT_APP_SCRIPT_CLOSE)
]
CHAT_APP_SCRIPT_TEMPLATE = CHAT_HTML[
    _chat_app_script_start + len(_CHAT_APP_SCRIPT_OPEN):_chat_app_script_end
]
CHAT_APP_SCRIPT_ASSET = (
    CHAT_APP_SCRIPT_TEMPLATE
    .replace(
        '    const CHAT_BASE_PATH = "__CHAT_BASE_PATH__";\n',
        '    const CHAT_BOOTSTRAP = window.__CHAT_BOOTSTRAP__ || {};\n'
        '    const CHAT_BASE_PATH = String(CHAT_BOOTSTRAP.basePath || "");\n',
        1,
    )
    .replace(
        '    const AGENT_ICON_NAMES = __AGENT_ICON_NAMES_JS_SET__;\n',
        '    const AGENT_ICON_NAMES = new Set(Array.isArray(CHAT_BOOTSTRAP.agentIconNames) ? CHAT_BOOTSTRAP.agentIconNames : []);\n',
        1,
    )
    .replace(
        '    const ALL_BASE_AGENTS = __ALL_BASE_AGENTS_JS_ARRAY__;\n',
        '    const ALL_BASE_AGENTS = Array.isArray(CHAT_BOOTSTRAP.allBaseAgents) ? CHAT_BOOTSTRAP.allBaseAgents : [];\n',
        1,
    )
    .replace(
        '    let soundEnabled = __CHAT_SOUND_ENABLED__;\n',
        '    let soundEnabled = !!CHAT_BOOTSTRAP.chatSoundEnabled;\n',
        1,
    )
    .replace(
        '    const AGENT_ICON_DATA = __ICON_DATA_URIS__;\n',
        '    const AGENT_ICON_DATA = CHAT_BOOTSTRAP.iconDataUris || {};\n',
        1,
    )
    .replace(
        '    const SERVER_INSTANCE_SEED = "__SERVER_INSTANCE__";\n',
        '    const SERVER_INSTANCE_SEED = String(CHAT_BOOTSTRAP.serverInstance || "");\n',
        1,
    )
    .replace(
        "      return mergeEntriesById(olderEntries, baseEntries).slice(-__MESSAGE_LIMIT__);\n",
        "      return mergeEntriesById(olderEntries, baseEntries).slice(-(Number(CHAT_BOOTSTRAP.messageLimit) || 500));\n",
        1,
    )
    .replace(
        '        window.location.href = `${window.location.protocol}//${hubHost}:__HUB_PORT__/`;\n',
        '        window.location.href = `${window.location.protocol}//${hubHost}:${Number(CHAT_BOOTSTRAP.hubPort) || 0}/`;\n',
        1,
    )
    .replace(
        '    let ttsEnabled = __CHAT_TTS_ENABLED__;\n',
        '    let ttsEnabled = !!CHAT_BOOTSTRAP.chatTtsEnabled;\n',
        1,
    )
)
CHAT_APP_SCRIPT_VERSION = hashlib.sha256(CHAT_APP_SCRIPT_ASSET.encode("utf-8")).hexdigest()[:12]


def chat_app_asset_url(chat_base_path: str = "") -> str:
    base_path = chat_base_path.rstrip("/")
    asset_path = f"{base_path}/chat-assets/chat-app.js" if base_path else "/chat-assets/chat-app.js"
    return f"{asset_path}?v={CHAT_APP_SCRIPT_VERSION}"


def render_chat_app_bootstrap_html(*, icon_data_uris, server_instance, hub_port, chat_settings, chat_base_path="") -> str:
    payload = {
        "basePath": chat_base_path.rstrip("/"),
        "iconDataUris": icon_data_uris,
        "serverInstance": server_instance,
        "hubPort": int(hub_port),
        "messageLimit": int(chat_settings["message_limit"]),
        "chatSoundEnabled": bool(chat_settings.get("chat_sound", False)),
        "chatTtsEnabled": bool(chat_settings.get("chat_tts", False)),
        "agentIconNames": list(ALL_AGENT_NAMES),
        "allBaseAgents": list(ALL_AGENT_NAMES),
    }
    payload_json = json.dumps(payload, ensure_ascii=True).replace("</", r"<\/")
    return f"  <script>window.__CHAT_BOOTSTRAP__ = {payload_json};</script>"


def _agent_css_selectors(theme: str = "black-hole") -> dict[str, str]:
    """Generate all agent-specific CSS selector placeholders."""
    names = ALL_AGENT_NAMES
    def _sel(suffix="", prefix=""):
        return ",\n".join(f"    {prefix}.message.{n}{suffix}" for n in names)
    def _row_sel(inner):
        return ",\n".join(f"    .message-row.{n} {inner}" for n in names)
    def _cross(suffixes, prefix=""):
        parts = []
        for n in names:
            for s in suffixes:
                parts.append(f"    {prefix}.message.{n} .md-body {s}")
        return ",\n".join(parts)
    gothic = 'html[data-agent-font-mode="gothic"] '
    return {
        "__AGENT_ACCENT_CSS__": generate_accent_css(theme),
        "__AGENT_MESSAGE_SELECTORS__": _sel(),
        "__AGENT_ROW_MESSAGE_WRAP_SELECTORS__": _row_sel(".message-wrap"),
        "__AGENT_ROW_MESSAGE_SELECTORS__": _row_sel(".message"),
        "__AGENT_ROW_META_SELECTORS__": _row_sel(".meta"),
        "__AGENT_SEL_MD_BODY__": _sel(" .md-body"),
        "__AGENT_SEL_MD_HEADING__": _cross(["p", "li", "h1", "h2", "h3", "h4"]),
        "__AGENT_SEL_MD_BODY_TEXT__": _cross(["p", "li", "blockquote"]),
        "__AGENT_SEL_MD_BODY_LI__": _sel(" .md-body li"),
        "__AGENT_SEL_GOTHIC_MD_BODY__": _sel(" .md-body", prefix=gothic),
        "__AGENT_SEL_GOTHIC_MD_DETAIL__": _cross(["p", "li", "blockquote"], prefix=gothic),
        "__AGENT_SEL_GOTHIC_MD_HEADING__": _cross(["h1", "h2", "h3", "h4"], prefix=gothic),
        "__AGENT_SEL_GOTHIC_MD_LI__": _sel(" .md-body li", prefix=gothic),
        "__AGENT_ICON_NAMES_JS_SET__": agent_names_js_set(),
        "__ALL_BASE_AGENTS_JS_ARRAY__": agent_names_js_array(),
    }


_CHAT_MAIN_STYLE_OPEN = "  <style>\n"
_CHAT_MAIN_STYLE_CLOSE = "  </style>\n"
_chat_main_style_start = CHAT_HTML.find(_CHAT_MAIN_STYLE_OPEN)
if _chat_main_style_start < 0:
    raise ValueError("chat main style block not found")
_chat_main_style_end = CHAT_HTML.find(_CHAT_MAIN_STYLE_CLOSE, _chat_main_style_start)
if _chat_main_style_end < 0:
    raise ValueError("chat main style close tag not found")
CHAT_MAIN_STYLE_BLOCK = CHAT_HTML[
    _chat_main_style_start:_chat_main_style_end + len(_CHAT_MAIN_STYLE_CLOSE)
]
CHAT_MAIN_STYLE_TEMPLATE = CHAT_HTML[
    _chat_main_style_start + len(_CHAT_MAIN_STYLE_OPEN):_chat_main_style_end
]
CHAT_MAIN_STYLE_ASSET = CHAT_MAIN_STYLE_TEMPLATE
for _font_name in (
    "anthropic-serif-roman.ttf",
    "anthropic-serif-italic.ttf",
    "anthropic-sans-roman.ttf",
    "anthropic-sans-italic.ttf",
    "jetbrains-mono.ttf",
):
    CHAT_MAIN_STYLE_ASSET = CHAT_MAIN_STYLE_ASSET.replace(
        f'"__CHAT_BASE_PATH__/font/{_font_name}"',
        f'"../font/{_font_name}"',
    )
for _placeholder, _value in {
    **_agent_css_selectors(),
    "__HUB_HEADER_CSS__": HUB_PAGE_HEADER_CSS,
}.items():
    CHAT_MAIN_STYLE_ASSET = CHAT_MAIN_STYLE_ASSET.replace(_placeholder, _value)
CHAT_MAIN_STYLE_VERSION = hashlib.sha256(CHAT_MAIN_STYLE_ASSET.encode("utf-8")).hexdigest()[:12]


def chat_style_asset_url(chat_base_path: str = "") -> str:
    base_path = chat_base_path.rstrip("/")
    asset_path = f"{base_path}/chat-assets/chat-app.css" if base_path else "/chat-assets/chat-app.css"
    return f"{asset_path}?v={CHAT_MAIN_STYLE_VERSION}"


def render_chat_html(*, icon_data_uris, logo_data_uri, server_instance, hub_port, chat_settings, agent_font_mode_inline_style, follow, chat_base_path="", externalize_app_script=False, externalize_main_style=False, eager_optional_vendors=True):
    base_path = chat_base_path.rstrip("/")
    if base_path and logo_data_uri == "/hub-logo":
        logo_src = f"{base_path}/hub-logo"
    else:
        logo_src = logo_data_uri
    chat_header_html = render_hub_page_header(
        logo_data_uri=logo_src,
        title_href="/",
        title_id="hubPageTitleLink",
        title_aria_label="Hub",
        title_alt="Hub",
        actions_html=CHAT_HEADER_ACTIONS_HTML,
        panels_html=CHAT_HEADER_PANELS_HTML,
    )
    html = CHAT_HTML
    if not eager_optional_vendors:
        html = html.replace(CHAT_ANSI_UP_HEAD_TAG, "", 1)
        html = html.replace(CHAT_KATEX_HEAD_TAGS, "", 1)
    if externalize_main_style:
        html = html.replace(
            CHAT_MAIN_STYLE_BLOCK,
            '  <link rel="stylesheet" href="__CHAT_STYLE_ASSET_URL__">\n',
            1,
        )
    if externalize_app_script:
        html = html.replace(
            CHAT_APP_SCRIPT_BLOCK,
            "__CHAT_APP_BOOTSTRAP__\n  <script src=\"__CHAT_APP_ASSET_URL__\"></script>\n",
            1,
        )
    # Replace agent-specific CSS/JS placeholders
    current_theme = str(chat_settings.get("theme", "black-hole") or "black-hole")
    for placeholder, value in _agent_css_selectors(current_theme).items():
        html = html.replace(placeholder, value)
    if "__CHAT_HEADER_HTML__" in html:
        html = html.replace("__CHAT_HEADER_HTML__", chat_header_html)
    else:
        html = html.replace('<section class="shell">', f'<section class="shell">{chat_header_html}', 1)
    return (
        html
        .replace("__ICON_DATA_URIS__", json.dumps(icon_data_uris, ensure_ascii=True))
        .replace("__HUB_LOGO_DATA_URI__", logo_src)
        .replace("__CHAT_BASE_PATH__", base_path)
        .replace("__CHAT_STYLE_ASSET_URL__", chat_style_asset_url(base_path) if externalize_main_style else "")
        .replace(
            "__CHAT_APP_BOOTSTRAP__",
            render_chat_app_bootstrap_html(
                icon_data_uris=icon_data_uris,
                server_instance=server_instance,
                hub_port=hub_port,
                chat_settings=chat_settings,
                chat_base_path=base_path,
            ) if externalize_app_script else "",
        )
        .replace("__CHAT_APP_ASSET_URL__", chat_app_asset_url(base_path) if externalize_app_script else "")
        .replace("__SERVER_INSTANCE__", server_instance)
        .replace("__HUB_PORT__", str(hub_port))
        .replace("__CHAT_THEME__", chat_settings["theme"])
        .replace("__STARFIELD_ATTR__", "" if chat_settings.get("starfield", False) else ' data-starfield="off"')
        .replace("__CHAT_SOUND_ENABLED__", "true" if chat_settings.get("chat_sound", False) else "false")
        .replace("__CHAT_TTS_ENABLED__", "true" if chat_settings.get("chat_tts", False) else "false")
        .replace("__AGENT_FONT_MODE__", chat_settings["agent_font_mode"])
        .replace("__AGENT_FONT_MODE_INLINE_STYLE__", agent_font_mode_inline_style(chat_settings))
        .replace("__HUB_HEADER_CSS__", HUB_PAGE_HEADER_CSS)
        .replace("__MESSAGE_LIMIT__", str(chat_settings["message_limit"]))
        .replace("mode: snapshot", f"mode: {'follow' if follow == '1' else 'snapshot'}")
    )


def render_pane_trace_popup_html(*, agent: str, agents: list[str] | None = None, bg: str, text: str, chat_base_path: str = "") -> str:
    base_path = chat_base_path.rstrip("/")
    bg_value = (bg or "").strip() or "rgb(10, 10, 10)"
    text_value = (text or "").strip() or "rgb(252, 252, 252)"
    all_agents = agents or ([agent] if agent else [])
    initial_agent = agent or (all_agents[0] if all_agents else "")
    agents_json = json.dumps(all_agents, ensure_ascii=True)
    initial_agent_json = json.dumps(initial_agent, ensure_ascii=True)
    bg_json = json.dumps(bg_value, ensure_ascii=True)
    text_json = json.dumps(text_value, ensure_ascii=True)
    import re as _re

    bg_effective = "rgb(30, 30, 30)"
    header_overlay_bg = "rgba(30, 30, 30, 0.78)"
    _text_rgb_match = _re.search(r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', text_value)
    if _text_rgb_match:
        tr, tg, tb = int(_text_rgb_match.group(1)), int(_text_rgb_match.group(2)), int(_text_rgb_match.group(3))
        body_fg = f"rgba({tr}, {tg}, {tb}, 0.78)"
        body_dim_fg = f"rgba({tr}, {tg}, {tb}, {0.38 if (tr + tg + tb) >= 384 else 0.42})"
    else:
        body_fg = text_value
        body_dim_fg = text_value
    trace_path_prefix = base_path or ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="{bg_value}">
  <title>Pane Trace</title>
  <script src="https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js"></script>
  <style>
    :root {{
      color-scheme: dark;
      --popup-bg: {bg_value};
      --popup-text: {text_value};
      --pane-trace-body-bg: {bg_effective};
      --pane-trace-body-fg: {body_fg};
      --pane-trace-body-dim-fg: {body_dim_fg};
    }}
    html, body {{
      margin: 0;
      background: var(--pane-trace-body-bg);
      color: var(--popup-text);
      height: 100%;
      font-family: "SF Mono", "SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-weight: 400;
      font-style: normal;
    }}
    body {{
      display: flex;
      flex-direction: column;
      position: relative;
      overflow: hidden;
    }}
    .pane-trace-tabs {{
      position: relative;
      z-index: 10;
      display: flex;
      align-items: flex-end;
      --pane-trace-tab-overlap: 1px;
      --pane-trace-tab-strip-bg: rgb(10,10,10);
      gap: 2px;
      padding: 0 8px;
      height: 35px;
      margin-bottom: calc(-1 * var(--pane-trace-tab-overlap));
      background: linear-gradient(
        to bottom,
        var(--pane-trace-tab-strip-bg) 0 calc(100% - var(--pane-trace-tab-overlap)),
        transparent calc(100% - var(--pane-trace-tab-overlap))
      );
      flex: 0 0 auto;
      overflow-x: auto;
      overflow-y: hidden;
      -webkit-overflow-scrolling: touch;
      -webkit-app-region: drag;
    }}
    .pane-trace-tabs::-webkit-scrollbar {{ display: none; }}
    .pane-trace-tab {{
      position: relative;
      display: flex;
      align-items: center;
      padding: 0 16px;
      height: 34px;
      box-sizing: border-box;
      font: 500 12px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
      color: rgba(255,255,255,0.5);
      background: transparent;
      border: none;
      border-radius: 10px 10px 0 0;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s ease;
      min-width: 0;
      max-width: 200px;
      overflow: visible;
      text-overflow: ellipsis;
      -webkit-app-region: no-drag;
    }}
    .pane-trace-tab:hover {{
      color: rgba(255,255,255,0.9);
      background: rgba(255,255,255,0.1);
    }}
    .pane-trace-tab.active {{
      color: #fff;
      background: {bg_effective};
      box-shadow: none;
      z-index: 2;
      margin-bottom: calc(-1 * var(--pane-trace-tab-overlap));
      border-radius: 10px 10px 0 0;
      overflow: visible;
    }}
    .pane-trace-tab.active::before,
    .pane-trace-tab.active::after {{
      content: "";
      position: absolute;
      bottom: 0;
      width: 10px;
      height: 10px;
      pointer-events: none;
    }}
    .pane-trace-tab.active::before {{
      left: -10px;
      background: radial-gradient(circle at 0 0, transparent 10px, {bg_effective} 10px);
    }}
    .pane-trace-tab.active::after {{
      right: -10px;
      background: radial-gradient(circle at 100% 0, transparent 10px, {bg_effective} 10px);
    }}
    .pane-trace-tab-label {{
      display: inline-flex;
      align-items: baseline;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .pane-trace-thinking-char {{
      color: rgba(252,252,252,0.42);
      animation: thinking-char-pulse 1.5s linear infinite;
    }}
    .pane-trace-tab:not(.pane-trace-tab-thinking) .pane-trace-thinking-char {{
      color: inherit;
      animation: none;
    }}
    .pane-trace-content {{
      position: relative;
      z-index: 1;
      flex: 1 1 auto;
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr;
      grid-template-rows: 1fr;
    }}
    .pane-trace-content.split-h {{ grid-template-columns: 1fr 1fr; }}
    .pane-trace-content.split-v {{ grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3bl {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3bl [data-slot="0"] {{ grid-column: 1; grid-row: 1; }}
    .pane-trace-content.split-3bl [data-slot="1"] {{ grid-column: 2; grid-row: 1 / -1; }}
    .pane-trace-content.split-3bl [data-slot="2"] {{ grid-column: 1; grid-row: 2; }}
    .pane-trace-content.split-3br {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3br [data-slot="0"] {{ grid-column: 1; grid-row: 1 / -1; }}
    .pane-trace-content.split-3br [data-slot="1"] {{ grid-column: 2; grid-row: 1; }}
    .pane-trace-content.split-3br [data-slot="2"] {{ grid-column: 2; grid-row: 2; }}
    .pane-trace-content.split-3span {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3span [data-slot="2"] {{ grid-column: 1 / -1; }}
    .pane-trace-content.split-4 {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-pane {{
      position: relative;
      min-width: 0;
      min-height: 0;
      display: flex;
      flex-direction: column;
      border: 0.5px solid rgba(255,255,255,0.06);
      overflow: hidden;
    }}
    .pane-trace-header-shadow {{
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 40px;
      background: linear-gradient({bg_effective} 0%, transparent 100%);
      pointer-events: none;
      z-index: 2;
    }}
    .pane-trace-pane-badge {{
      position: absolute;
      top: 6px; left: 8px; z-index: 11;
      width: 28px; height: 28px;
      padding: 4px;
      box-sizing: border-box;
      background: none;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: visible;
      transition: background 0.15s;
      user-select: none;
    }}
    .pane-trace-pane-badge-inner {{
      position: relative;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .pane-trace-pane-badge-glow {{
      position: absolute;
      inset: 0;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(250,249,245,0.65) 0%, rgba(250,249,245,0) 70%);
      pointer-events: none;
      animation: thinking-glow-follow 1s ease-in-out infinite;
      animation-delay: var(--agent-pulse-delay, 0s);
    }}
    .pane-trace-pane-badge-icon {{
      width: 100%; height: 100%;
      object-fit: contain;
      display: block;
      position: relative;
      filter: brightness(0) invert(0.92);
    }}
    .pane-trace-pane-badge-thinking .pane-trace-pane-badge-icon {{
      animation: thinking-icon-heartbeat 1s ease-in-out infinite;
      animation-delay: var(--agent-pulse-delay, 0s);
    }}
    .pane-trace-pane-badge:not(.pane-trace-pane-badge-thinking) .pane-trace-pane-badge-glow {{
      display: none;
    }}
    .pane-trace-pane-badge-thinking .pane-trace-pane-badge-glow {{
      display: block;
    }}
    .pane-trace-pane-badge:hover {{ background: rgba(220,40,40,0.7); }}
    .pane-trace-pane-badge:hover .pane-trace-pane-badge-icon {{ filter: brightness(0) invert(1); }}
    @keyframes thinking-glow-follow {{
      0%   {{ transform: scale(0.5); opacity: 0; }}
      50%  {{ transform: scale(1.4); opacity: 0.12; }}
      100% {{ transform: scale(0.5); opacity: 0; }}
    }}
    @keyframes thinking-icon-heartbeat {{
      0%   {{ transform: translateY(0);    filter: brightness(0) invert(0.92); }}
      50%  {{ transform: translateY(-1px); filter: brightness(0) invert(1); }}
      100% {{ transform: translateY(0);    filter: brightness(0) invert(0.92); }}
    }}
    @keyframes thinking-char-pulse {{
      0%   {{ color: rgba(252, 252, 252, 0.62); }}
      10%  {{ color: rgba(252, 252, 252, 0.82); }}
      22%  {{ color: rgba(252, 252, 252, 0.62); }}
      34%  {{ color: rgba(252, 252, 252, 0.42); }}
      88%  {{ color: rgba(252, 252, 252, 0.42); }}
      100% {{ color: rgba(252, 252, 252, 0.62); }}
    }}
    .pane-trace-drop-indicator {{
      position: absolute;
      background: rgba(255,255,255,0.1);
      border: 1.5px solid rgba(255,255,255,0.4);
      border-radius: 4px;
      z-index: 10;
      pointer-events: none;
      display: none;
    }}
    .pane-trace-body {{
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 10px 12px;
      padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
      box-sizing: border-box;
      -webkit-overflow-scrolling: touch;
      font-family: "SF Mono", "SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-weight: 400;
      font-style: normal;
      font-size: 11px;
      line-height: 1.15;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: anywhere;
      color: var(--pane-trace-body-fg);
    }}
    .pane-trace-body .ansi-bright-black-fg {{ color: var(--pane-trace-body-dim-fg); }}
    .trace-dot {{
      font-family: -apple-system, "Helvetica Neue", sans-serif;
      font-variant-emoji: text;
      text-rendering: geometricPrecision;
    }}
    @media (prefers-reduced-motion: reduce) {{
      .pane-trace-pane-badge-thinking .pane-trace-pane-badge-icon {{
        animation: none;
        filter: brightness(0) invert(0.92);
      }}
      .pane-trace-pane-badge-thinking .pane-trace-pane-badge-glow {{
        animation: none;
        display: none;
      }}
      .pane-trace-tab-thinking .pane-trace-thinking-char {{
        animation: none;
        color: rgba(252,252,252,0.6);
      }}
    }}
  </style>
</head>
<body>
  <div class="pane-trace-tabs" id="paneTraceTabs"></div>
  <div class="pane-trace-content" id="paneTraceContent">
    <div class="pane-trace-pane" data-slot="0">
      <span class="pane-trace-pane-badge" data-slot="0"></span>
      <div class="pane-trace-body">Loading...</div>
    </div>
  </div>
  <div class="pane-trace-drop-indicator" id="dropIndicator"></div>
  <script>
    const agents = {agents_json};
    const bg = {bg_json};
    const text = {text_json};
    document.documentElement.style.setProperty("--popup-bg", bg);
    document.documentElement.style.setProperty("--popup-text", text);

    const pollMs = (location.hostname === "127.0.0.1" || location.hostname === "localhost") ? 100 : 1500;
    const tabsEl = document.getElementById("paneTraceTabs");
    const contentEl = document.getElementById("paneTraceContent");
    const dropEl = document.getElementById("dropIndicator");
    const escapeHtml = (value) => String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
    const agentBaseName = (name) => String(name || "").toLowerCase().replace(/-\\d+$/, "");
    const agentPulseOffsets = {{
      claude: 0,
      codex: -0.25,
      gemini: -0.5,
      kimi: -0.625,
      copilot: -0.75,
      cursor: -0.125,
      opencode: -0.625,
      grok: -0.375,
      qwen: -0.875,
      aider: -0.2,
    }};
    const agentPulseOffset = (name) => agentPulseOffsets[agentBaseName(name)] ?? 0;
    const tabLabelHtml = (name) => {{
      const label = String(name || "");
      const offset = agentPulseOffset(name);
      const chars = [...label].map((ch, i) =>
        `<span class="pane-trace-thinking-char" style="animation-delay:${{offset + (i * 0.18)}}s">${{escapeHtml(ch)}}</span>`
      ).join("");
      return `<span class="pane-trace-tab-label">${{chars}}</span>`;
    }};

    /* ── state ── */
    let layout = "single";   /* "single" | "h" | "v" | "3bl" | "3br" | "3span" | "4" */
    let paneAgents = [{initial_agent_json}, null, null, null];
    let extraIntervals = [null, null, null];
    let statusInterval = null;
    let currentStatuses = {{}};
    const slotCount = () => ({{ single: 1, h: 2, v: 2, "3bl": 3, "3br": 3, "3span": 3, "4": 4 }})[layout];

    /* ── ansi / fetch ── */
    let ansiUp = null;
    const traceHtml = (raw) => {{
      const txt = String(raw ?? "No output");
      if (!ansiUp) {{ try {{ if (typeof AnsiUp === "function") ansiUp = new AnsiUp(); }} catch (_) {{}} }}
      let html;
      if (ansiUp) {{ try {{ html = ansiUp.ansi_to_html(txt); }} catch (_) {{}} }}
      if (!html) html = txt.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\\n/g,"<br>");
      return html.replace(/[●⏺]/g, '<span class="trace-dot">●</span>');
    }};
    const _paneBodyAtBottom = (el) => !el || el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    const fetchTo = async (agent, bodyEl, scroll) => {{
      if (!agent || !bodyEl) return;
      if (!scroll && !_paneBodyAtBottom(bodyEl)) return;
      try {{
        const res = await fetch(`{trace_path_prefix}/trace?agent=${{encodeURIComponent(agent)}}&lines=192&ts=${{Date.now()}}`);
        if (!res.ok) return;
        const data = await res.json();
        bodyEl.innerHTML = traceHtml(data.content || "No output");
        if (scroll) bodyEl.scrollTop = bodyEl.scrollHeight;
      }} catch (_) {{}}
    }};

    /* ── icon path helper ── */
    const agentIconUrl = (name) => `{trace_path_prefix}/icon/${{encodeURIComponent(agentBaseName(name))}}`;
    const paneBadgeHtml = (agent) => {{
      const pulse = agentPulseOffset(agent);
      return `<span class="pane-trace-pane-badge-inner" style="--agent-pulse-delay:${{pulse}}s"><span class="pane-trace-pane-badge-glow"></span><img class="pane-trace-pane-badge-icon" src="${{agentIconUrl(agent)}}" alt="${{escapeHtml(agent)}}"></span>`;
    }};
    const applyThinkingState = () => {{
      tabsEl.querySelectorAll(".pane-trace-tab").forEach((tab) => {{
        const agent = tab.dataset.agent || "";
        tab.classList.toggle("pane-trace-tab-thinking", currentStatuses[agent] === "running");
      }});
      contentEl.querySelectorAll(".pane-trace-pane-badge").forEach((badge) => {{
        const slot = Number.parseInt(badge.dataset.slot || "-1", 10);
        const agent = slot >= 0 ? paneAgents[slot] : "";
        badge.classList.toggle("pane-trace-pane-badge-thinking", !!agent && currentStatuses[agent] === "running");
      }});
    }};
    const fetchStatuses = async () => {{
      try {{
        const res = await fetch(`{trace_path_prefix}/session-state?ts=${{Date.now()}}`, {{ cache: "no-store" }});
        if (!res.ok) return;
        const data = await res.json();
        currentStatuses = (data && typeof data.statuses === "object" && data.statuses) ? data.statuses : {{}};
        applyThinkingState();
      }} catch (_) {{}}
    }};

    /* ── make a pane element ── */
    const makePane = (slot, agent) => {{
      const d = document.createElement("div");
      d.className = "pane-trace-pane";
      d.setAttribute("data-slot", slot);
      d.innerHTML = `<div class="pane-trace-header-shadow"></div><span class="pane-trace-pane-badge" data-slot="${{slot}}">${{paneBadgeHtml(agent)}}</span><div class="pane-trace-body">Loading...</div>`;
      d.querySelector(".pane-trace-pane-badge").addEventListener("click", () => closePane(slot));
      return d;
    }};

    /* ── rebuild panes from state ── */
    const rebuildPanes = () => {{
      const n = slotCount();
      contentEl.className = "pane-trace-content" + (layout !== "single" ? ` split-${{layout}}` : "");
      extraIntervals.forEach((iv, i) => {{ if (iv) clearInterval(iv); extraIntervals[i] = null; }});
      contentEl.innerHTML = "";
      const used = new Set();
      for (let i = 0; i < n; i++) {{
        if (!paneAgents[i] || (i > 0 && used.has(paneAgents[i]))) {{
          paneAgents[i] = agents.find(a => !used.has(a)) || agents[0];
        }}
        used.add(paneAgents[i]);
        const pane = makePane(i, paneAgents[i]);
        contentEl.appendChild(pane);
        fetchTo(paneAgents[i], pane.querySelector(".pane-trace-body"), true);
        if (i > 0) {{
          const idx = i;
          extraIntervals[idx - 1] = setInterval(() => {{
            const b = contentEl.querySelector(`[data-slot="${{idx}}"] .pane-trace-body`);
            if (b && paneAgents[idx]) fetchTo(paneAgents[idx], b, false);
          }}, pollMs);
        }}
      }}
      for (let i = n; i < 4; i++) paneAgents[i] = null;
      document.title = layout === "single" ? `${{paneAgents[0]}} Pane Trace` : "Pane Trace";
      applyThinkingState();
    }};

    /* ── close a pane ── */
    const closePane = (slot) => {{
      const n = slotCount();
      if (n <= 1) return;
      paneAgents.splice(slot, 1);
      paneAgents.push(null);
      if (n === 4) {{ layout = "h"; }}
      else if (n === 3) {{ layout = "h"; }}
      else {{ layout = "single"; }}
      buildTabs();
      rebuildPanes();
    }};

    /* ── detect drop zone ── */
    const detectZone = (e) => {{
      const n = slotCount();
      if (n >= 4) {{
        const pane = e.target.closest(".pane-trace-pane");
        return pane ? {{ action: "replace", slot: parseInt(pane.getAttribute("data-slot"), 10) }} : null;
      }}
      const rect = contentEl.getBoundingClientRect();
      const rx = (e.clientX - rect.left) / rect.width;
      const ry = (e.clientY - rect.top) / rect.height;
      if (n === 1) {{
        const dRight = 1 - rx, dBottom = 1 - ry;
        if (dRight < 0.35 && dRight < dBottom) return {{ action: "split", dir: "h", zone: "right", rect }};
        if (dBottom < 0.35) return {{ action: "split", dir: "v", zone: "bottom", rect }};
        return {{ action: "replace", slot: 0 }};
      }}
      if (n === 2 && layout === "h") {{
        /* bottom edge of left or right pane → add 3rd pane */
        const isBottom = ry > 0.65;
        if (isBottom) {{
          /* left half of bottom → 3rd under left column, right half → 3rd under right column */
          /* center region → span full bottom */
          if (rx < 0.35) return {{ action: "expand3", sub: "3bl", rect }};
          if (rx > 0.65) return {{ action: "expand3", sub: "3br", rect }};
          return {{ action: "expand3", sub: "3span", rect }};
        }}
        return {{ action: "replace", slot: rx > 0.5 ? 1 : 0 }};
      }}
      if (n === 2 && layout === "v") {{
        const isRight = rx > 0.65;
        if (isRight) return {{ action: "split_to_h_then_3", rect }};
        return {{ action: "replace", slot: ry > 0.5 ? 1 : 0 }};
      }}
      if (n === 3) {{
        /* 3 panes: bottom edge → go to 4, otherwise replace */
        const isBottom = ry > 0.65;
        if (isBottom && (layout === "3bl" || layout === "3br")) {{
          return {{ action: "expand4", rect }};
        }}
        if (layout === "3span" && ry > 0.5) {{
          /* drop on bottom-span: check left/right to decide expand to 4 */
          if (rx < 0.35 || rx > 0.65) return {{ action: "expand4", rect }};
          return {{ action: "replace", slot: 2 }};
        }}
        const pane = e.target.closest(".pane-trace-pane");
        return pane ? {{ action: "replace", slot: parseInt(pane.getAttribute("data-slot"), 10) }} : null;
      }}
      return null;
    }};

    /* ── drop indicator ── */
    const showIndicator = (e) => {{
      const zone = detectZone(e);
      if (!zone) {{ dropEl.style.display = "none"; return; }}
      const cr = contentEl.getBoundingClientRect();
      dropEl.style.display = "block";
      if (zone.action === "split" && zone.zone === "right") {{
        dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
        dropEl.style.top = cr.top + "px";
        dropEl.style.width = (cr.width * 0.5) + "px";
        dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "split" && zone.zone === "bottom") {{
        dropEl.style.left = cr.left + "px";
        dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
        dropEl.style.width = cr.width + "px";
        dropEl.style.height = (cr.height * 0.5) + "px";
      }} else if (zone.action === "expand3") {{
        if (zone.sub === "3bl") {{
          dropEl.style.left = cr.left + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = (cr.width * 0.5) + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }} else if (zone.sub === "3br") {{
          dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = (cr.width * 0.5) + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }} else {{
          dropEl.style.left = cr.left + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = cr.width + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }}
      }} else if (zone.action === "split_to_h_then_3") {{
        dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
        dropEl.style.top = cr.top + "px";
        dropEl.style.width = (cr.width * 0.5) + "px";
        dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "expand4") {{
        dropEl.style.left = cr.left + "px"; dropEl.style.top = cr.top + "px";
        dropEl.style.width = cr.width + "px"; dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "replace") {{
        const pane = contentEl.querySelector(`[data-slot="${{zone.slot}}"]`);
        if (pane) {{
          const pr = pane.getBoundingClientRect();
          dropEl.style.left = pr.left + "px"; dropEl.style.top = pr.top + "px";
          dropEl.style.width = pr.width + "px"; dropEl.style.height = pr.height + "px";
        }}
      }}
    }};

    /* ── drag events on content ── */
    contentEl.addEventListener("dragover", e => {{ e.preventDefault(); showIndicator(e); }});
    contentEl.addEventListener("dragleave", () => {{ dropEl.style.display = "none"; }});
    contentEl.addEventListener("drop", e => {{
      e.preventDefault();
      dropEl.style.display = "none";
      const agent = e.dataTransfer.getData("text/plain");
      if (!agent || !agents.includes(agent)) return;
      const zone = detectZone(e);
      if (!zone) return;
      if (zone.action === "replace") {{
        paneAgents[zone.slot] = agent;
        const body = contentEl.querySelector(`[data-slot="${{zone.slot}}"] .pane-trace-body`);
        const badge = contentEl.querySelector(`[data-slot="${{zone.slot}}"].pane-trace-pane-badge, .pane-trace-pane[data-slot="${{zone.slot}}"] .pane-trace-pane-badge`);
        if (body) {{ body.innerHTML = "Loading..."; fetchTo(agent, body, true); }}
        if (badge) {{ badge.innerHTML = paneBadgeHtml(agent); }}
        if (zone.slot === 0) buildTabs();
        return;
      }}
      if (zone.action === "split") {{
        layout = zone.dir;
        paneAgents[1] = agent;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "expand3") {{
        /* 2 → 3: add one pane in the chosen sub-layout */
        layout = zone.sub;
        paneAgents[2] = agent;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "split_to_h_then_3") {{
        /* v2 → rearrange as 3bl (top-left, top-right=new, bottom-left=old-slot1) */
        const old1 = paneAgents[1];
        layout = "3span";
        paneAgents[1] = agent;
        paneAgents[2] = old1;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "expand4") {{
        const prevN = slotCount();
        layout = "4";
        if (prevN === 3) {{
          paneAgents[3] = agent;
        }} else {{
          paneAgents[2] = agent;
          paneAgents[3] = agents.find(a => a !== paneAgents[0] && a !== paneAgents[1] && a !== agent) || agents[0];
        }}
        buildTabs();
        rebuildPanes();
      }}
    }});

    /* ── tab bar ── */
    const buildTabs = () => {{
      const n = slotCount();
      const activeSet = new Set(paneAgents.slice(0, n).filter(Boolean));
      tabsEl.innerHTML = agents.map(a =>
        `<button class="pane-trace-tab${{activeSet.has(a) ? " active" : ""}}" data-agent="${{escapeHtml(a)}}" draggable="true">${{tabLabelHtml(a)}}</button>`
      ).join("");
      tabsEl.querySelectorAll(".pane-trace-tab").forEach(tab => {{
        tab.addEventListener("click", () => switchAgent(tab.dataset.agent));
        tab.addEventListener("dragstart", (e) => {{
          e.dataTransfer.setData("text/plain", tab.dataset.agent);
          e.dataTransfer.effectAllowed = "copyMove";
        }});
      }});
      applyThinkingState();
    }};

    /* ── switch main agent (slot 0) ── */
    const switchAgent = (agent) => {{
      if (!agents.includes(agent)) return;
      paneAgents[0] = agent;
      document.title = layout === "single" ? `${{agent}} Pane Trace` : "Pane Trace";
      buildTabs();
      const body = contentEl.querySelector('[data-slot="0"] .pane-trace-body');
      const badge = contentEl.querySelector('.pane-trace-pane[data-slot="0"] .pane-trace-pane-badge');
      if (body) {{ body.innerHTML = "Loading..."; fetchTo(agent, body, true); }}
      if (badge) {{ badge.innerHTML = paneBadgeHtml(agent); }}
    }};

    /* ── postMessage from parent ── */
    window.addEventListener("message", (e) => {{
      if (e.data && e.data.type === "switchAgent" && e.data.agent) switchAgent(e.data.agent);
    }});

    /* ── init ── */
    buildTabs();
    rebuildPanes();
    fetchStatuses();
    statusInterval = setInterval(fetchStatuses, pollMs);
    setInterval(() => {{
      const body = contentEl.querySelector('[data-slot="0"] .pane-trace-body');
      if (body && paneAgents[0]) fetchTo(paneAgents[0], body, false);
    }}, pollMs);
  </script>
</body>
</html>"""
