from __future__ import annotations

import hashlib
from dataclasses import dataclass


CHAT_HEADER_ACTIONS_HTML = """
<button type="button" class="hub-page-menu-btn" id="gitBranchMenuBtn" title="Git branch overview" aria-label="Git branch overview">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3v12"></path><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>
</button>
<button type="button" class="hub-page-menu-btn" id="attachedFilesMenuBtn" title="Attached files" aria-label="Attached files">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</button>
<button type="button" class="hub-page-menu-btn" id="hubPageMenuBtn" title="Menu" aria-label="Menu">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="10" y1="15" x2="20" y2="15"/></svg>
</button>
<select id="hubPageNativeMenuBridge" style="position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;opacity:0.001;pointer-events:auto;appearance:none;-webkit-appearance:none;border:none;outline:none;background:transparent;font-size:13px;z-index:220;cursor:pointer;-webkit-tap-highlight-color:transparent;" aria-hidden="true">
  <option value="" disabled selected>Menu</option>
  <option value="openGitBranchMenu" data-mobile-only="1" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M6 3v12%22/%3E%3Ccircle cx=%2218%22 cy=%226%22 r=%223%22/%3E%3Ccircle cx=%226%22 cy=%2218%22 r=%223%22/%3E%3Cpath d=%22M18 9a9 9 0 0 1-9 9%22/%3E%3C/svg%3E')">Git Branches</option>
  <option value="openAttachedFilesMenu" data-mobile-only="1" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z%22/%3E%3C/svg%3E')">Attached Files</option>
  <option value="reloadChat" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M21 2v6h-6%22/%3E%3Cpath d=%22M20 12a8 8 0 1 1-2.1-5.3L21 8%22/%3E%3C/svg%3E')">Reload</option>
  <option value="openTerminal" data-desktop-only="1" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Crect x=%222%22 y=%223%22 width=%2220%22 height=%2214%22 rx=%222%22/%3E%3Cline x1=%228%22 y1=%2221%22 x2=%2216%22 y2=%2221%22/%3E%3Cline x1=%2212%22 y1=%2217%22 x2=%2212%22 y2=%2221%22/%3E%3C/svg%3E')">Terminal</option>
  <option value="openFinder" data-desktop-only="1" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z%22/%3E%3Cpath d=%22M3 10h18%22/%3E%3C/svg%3E')">Finder</option>
  <option value="openCameraMode" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M4 8.5A2.5 2.5 0 0 1 6.5 6H9l1.5-2h3L15 6h2.5A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5z%22/%3E%3Ccircle cx=%2212%22 cy=%2212.5%22 r=%223.5%22/%3E%3C/svg%3E')">Camera</option>
  <option value="openPaneTraceWindow" data-mobile-only="1" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M4 5h16%22/%3E%3Cpath d=%22M4 12h16%22/%3E%3Cpath d=%22M4 19h10%22/%3E%3Cpath d=%22M18 17v4%22/%3E%3Cpath d=%22m16 19 2-2 2 2%22/%3E%3C/svg%3E')">Pane Trace</option>
  <option value="exportBtn" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4%22/%3E%3Cpolyline points=%227 10 12 15 17 10%22/%3E%3Cline x1=%2212%22 y1=%2215%22 x2=%2212%22 y2=%223%22/%3E%3C/svg%3E')">Export</option>
  <option value="syncStatus" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M12 20V10%22/%3E%3Cpath d=%22M18 20V4%22/%3E%3Cpath d=%22M6 20v-4%22/%3E%3C/svg%3E')">Sync Status</option>
  <option value="addAgent" style="background-image:url('data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27%23888%27%20stroke-width%3D%271.8%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Crect%20x%3D%273.5%27%20y%3D%274.5%27%20width%3D%2711%27%20height%3D%2712%27%20rx%3D%272.6%27%2F%3E%3Ccircle%20cx%3D%277.5%27%20cy%3D%279.5%27%20r%3D%270.85%27%2F%3E%3Ccircle%20cx%3D%2710.5%27%20cy%3D%279.5%27%20r%3D%270.85%27%2F%3E%3Cpath%20d%3D%27M7%2012.7h4%27%2F%3E%3Cpath%20d%3D%27M9%204.5V3%27%2F%3E%3Cline%20x1%3D%2721%27%20y1%3D%2710.5%27%20x2%3D%2716.5%27%20y2%3D%2710.5%27%2F%3E%3Cline%20x1%3D%2718.75%27%20y1%3D%278.25%27%20x2%3D%2718.75%27%20y2%3D%2712.75%27%2F%3E%3C%2Fsvg%3E')">Add Agent</option>
  <option value="removeAgent" style="background-image:url('data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27%23888%27%20stroke-width%3D%271.8%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Crect%20x%3D%273.5%27%20y%3D%274.5%27%20width%3D%2711%27%20height%3D%2712%27%20rx%3D%272.6%27%2F%3E%3Ccircle%20cx%3D%277.5%27%20cy%3D%279.5%27%20r%3D%270.85%27%2F%3E%3Ccircle%20cx%3D%2710.5%27%20cy%3D%279.5%27%20r%3D%270.85%27%2F%3E%3Cpath%20d%3D%27M7%2012.7h4%27%2F%3E%3Cpath%20d%3D%27M9%204.5V3%27%2F%3E%3Cline%20x1%3D%2721%27%20y1%3D%2710.5%27%20x2%3D%2716.5%27%20y2%3D%2710.5%27%2F%3E%3C%2Fsvg%3E')">Remove Agent</option>
</select>
"""
CHAT_HEADER_PANELS_HTML = """
<div class="hub-page-menu-panel" id="gitBranchPanel" hidden></div>
<div class="hub-page-menu-panel" id="attachedFilesPanel" hidden></div>
<div class="hub-page-menu-panel" id="paneTracePanel" hidden>
  <div class="hub-main-menu-stack">
    <div id="paneViewer" class="pane-viewer">
      <div class="git-commit-detail-body pane-viewer-detail-body">
        <div class="pane-viewer-tabs" id="paneViewerTabs"></div>
        <div class="pane-viewer-carousel" id="paneViewerCarousel"></div>
      </div>
    </div>
  </div>
</div>
<div class="hub-page-menu-panel" id="hubPageMenuPanel" hidden>
  <div class="hub-main-menu-stack">
    <div class="hub-main-menu-list-view">
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


@dataclass(frozen=True)
class ChatAppScriptAssets:
    block: str
    template: str
    asset: str
    version: str


def build_chat_app_script_assets(chat_html: str) -> ChatAppScriptAssets:
    script_open = "  <script>\n"
    script_close = "  </script>\n"
    script_start = chat_html.rfind(script_open)
    if script_start < 0:
        raise ValueError("chat app script block not found")
    script_end = chat_html.find(script_close, script_start)
    if script_end < 0:
        raise ValueError("chat app script close tag not found")
    block = chat_html[script_start:script_end + len(script_close)]
    template = chat_html[script_start + len(script_open):script_end]
    asset = (
        template
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
            '      const hubUrl = `${window.location.protocol}//${hubHost}:__HUB_PORT__${normalizedPath}`;\n',
            '      const hubUrl = `${window.location.protocol}//${hubHost}:${Number(CHAT_BOOTSTRAP.hubPort) || 0}${normalizedPath}`;\n',
            1,
        )
        .replace(
            '    let browserNotificationsEnabled = __CHAT_BROWSER_NOTIFICATIONS_ENABLED__;\n',
            '    let browserNotificationsEnabled = !!CHAT_BOOTSTRAP.chatBrowserNotificationsEnabled;\n',
            1,
        )
    )
    version = hashlib.sha256(asset.encode("utf-8")).hexdigest()[:12]
    return ChatAppScriptAssets(block=block, template=template, asset=asset, version=version)
