from __future__ import annotations


ANSI_UP_VERSION = "5.1.0"
MARKED_VERSION = "12"
KATEX_VERSION = "0.16.11"

ANSI_UP_CDN_SRC = f"https://cdn.jsdelivr.net/npm/ansi_up@{ANSI_UP_VERSION}/ansi_up.min.js"
MARKED_CDN_SRC = f"https://cdn.jsdelivr.net/npm/marked@{MARKED_VERSION}/marked.min.js"
KATEX_CDN_CSS_HREF = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.css"
KATEX_CDN_JS_SRC = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.js"
KATEX_CDN_AUTO_RENDER_SRC = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/contrib/auto-render.min.js"

CHAT_HEADER_MENU_BUTTON_HTML = """
<button type="button" class="page-menu-btn" id="pageMenuBtn" title="Menu" aria-label="Menu">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="10" y1="15" x2="20" y2="15"/></svg>
</button>
"""
CHAT_HEADER_ACTIONS_HTML_MOBILE = CHAT_HEADER_MENU_BUTTON_HTML
CHAT_HEADER_ACTIONS_HTML = CHAT_HEADER_MENU_BUTTON_HTML + """
<select id="pageNativeMenuBridge" style="position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;opacity:0.001;pointer-events:auto;appearance:none;-webkit-appearance:none;border:none;outline:none;background:transparent;font-size:13px;z-index:220;cursor:pointer;-webkit-tap-highlight-color:transparent;" aria-hidden="true">
  <option value="" disabled selected>Menu</option>
  <option value="openShell">Terminal</option>
  <option value="openTerminal">tmux window</option>
  <option value="openFinder">Finder</option>
  <option value="addAgent">Add Agent</option>
  <option value="removeAgent">Remove Agent</option>
</select>
"""
CHAT_SHEET_PANELS_HTML = """
<div class="page-menu-panel mobile-sheet-overlay" id="gitPanel" hidden></div>
<div class="page-menu-panel mobile-sheet-overlay" id="repoPanel" hidden></div>
<div class="page-menu-panel mobile-sheet-overlay" id="paneTracePanel" hidden>
  <div class="hub-main-menu-stack">
    <div id="paneViewer" class="pane-viewer" hidden>
      <div class="git-commit-detail-body pane-viewer-detail-body">
        <div class="pane-viewer-tabs" id="paneViewerTabs"></div>
        <div class="pane-viewer-carousel" id="paneViewerCarousel"></div>
      </div>
    </div>
  </div>
</div>
"""
CHAT_ANSI_UP_HEAD_TAG = f'  <script src="{ANSI_UP_CDN_SRC}"></script>\n'
CHAT_KATEX_HEAD_TAGS = (
    f'  <link rel="stylesheet" href="{KATEX_CDN_CSS_HREF}">\n'
    f'  <script src="{KATEX_CDN_JS_SRC}"></script>\n'
    f'  <script src="{KATEX_CDN_AUTO_RENDER_SRC}"></script>\n'
)
