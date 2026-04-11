from __future__ import annotations

import base64
from pathlib import Path


def hub_header_logo_data_uri(repo_root: Path | str) -> str:
    path = Path(repo_root).resolve() / "hub-header-logo.webp"
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/webp;base64,{b64}"


HUB_PAGE_HEADER_CSS = """
    :root {
      --page-side-pad: 14px;
      --chrome-icon-btn-size: 26px;
      --chrome-icon-size: 16px;
      --chrome-icon-stroke: 1.5;
      --chrome-icon-gap: 2px;
    }
    [hidden] { display: none !important; }
    @font-face {
      font-family: "anthropicSans";
      src: url("/font/anthropic-sans-roman.ttf") format("truetype");
      font-style: normal; font-weight: 300 800; font-display: swap;
    }
    @font-face {
      font-family: "anthropicSans";
      src: url("/font/anthropic-sans-italic.ttf") format("truetype");
      font-style: italic; font-weight: 300 800; font-display: swap;
    }
    html, body { font-family: "anthropicSans", "SF Pro Text", "Segoe UI", sans-serif; }
    .hub-page-header {
      display: flex; flex-direction: column;
      width: 100%;
      margin: 0;
      position: sticky; top: 0; z-index: 100;
      background: linear-gradient(rgba(10, 10, 10, 0.6) 0%, rgba(0, 0, 0, 0) 100%);
      border-bottom: none;
      box-shadow: none;
      transition: opacity 0.3s ease;
    }
    .hub-page-header::after { content: none; }
    .hub-page-header-top { border-bottom: none; box-shadow: none; }
    /* メニュー展開時: パネルとトップ行だけ同色（親全体に blur を付けない＝パネルが透ける事故を避ける） */
    .hub-page-header:has(.hub-page-menu-panel.open) {
      background: transparent;
    }
    .hub-page-header:has(.hub-page-menu-panel.open) .hub-page-header-top {
      position: relative;
      z-index: 1;
      background: rgba(var(--bg-rgb, 38, 38, 36), 0.72);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
    }
    .hub-page-header:has(.hub-page-menu-panel.open) .hub-page-header-shadow {
      opacity: 0;
    }
    .hub-page-header.header-hidden {
      opacity: 0;
      pointer-events: none;
    }
    .hub-page-header-shadow {
      position: absolute;
      top: 0; left: 0; right: 0;
      width: 100%; height: 140px;
      background: linear-gradient(rgba(10, 10, 10, 0.5) 0%, rgba(0, 0, 0, 0) 100%);
      pointer-events: none;
      z-index: -1;
    }
    .header-hidden .hub-page-header-shadow {
      display: none;
    }
    .hub-page-header-top {
      display: flex; align-items: center; justify-content: space-between;
      padding: max(8px, env(safe-area-inset-top)) var(--page-side-pad) 8px;
      box-sizing: border-box;
    }
    .hub-page-title {
      display: inline-flex; align-items: center; justify-content: flex-start; text-decoration: none; opacity: 1;
      min-width: 40px; min-height: 40px;
      gap: 8px;
      transition: opacity 0.2s ease, transform 0.2s ease;
    }
    .hub-page-title:hover { opacity: 0.8; transform: scale(0.98); }
    .hub-page-header-actions {
      display: flex;
      align-items: center;
      gap: var(--chrome-icon-gap);
      flex: 0 0 auto;
    }
    .hub-page-logo {
      height: 20px;
      width: auto;
      display: block;
      filter: invert(1) grayscale(1) brightness(1.04) contrast(1.04);
    }
    .hub-page-menu-btn {
      display: flex; align-items: center; justify-content: center;
      width: var(--chrome-icon-btn-size); height: var(--chrome-icon-btn-size);
      background: transparent !important; border: none !important; color: rgba(255,255,255,0.8);
      cursor: pointer; padding: 0; margin: 0; box-shadow: none !important;
      -webkit-tap-highlight-color: transparent;
      outline: none !important;
    }
    .hub-page-menu-btn:hover { color: #fff; }
    .hub-page-menu-btn:active { color: #fff; }
    .hub-page-menu-btn svg {
      width: var(--chrome-icon-size);
      height: var(--chrome-icon-size);
      stroke-width: var(--chrome-icon-stroke);
    }
    
    .hub-page-menu-btn.restarting { animation: hubPageRestartPulse 1.2s ease-in-out infinite; pointer-events: none; border-color: transparent; background: transparent; }
    .hub-page-menu-panel {
      max-height: 0; overflow: hidden;
      transition: max-height 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
      background: rgba(var(--bg-rgb, 38, 38, 36), 0.72);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
    }
    .hub-page-menu-panel.open { max-height: 400px; }
    .hub-page-menu-item {
      display: flex; align-items: center; gap: 12px;
      padding: 14px 18px; font-size: 16px; font-weight: 400; color: rgba(255,255,255,0.8);
      text-decoration: none; cursor: pointer; border: none;
      border-bottom: 0.5px solid rgba(255,255,255,0.05); background: transparent;
      width: 100%; text-align: left; font-family: inherit; -webkit-appearance: none;
      box-sizing: border-box; max-width: 100%; margin: 0;
      transition: all 0.2s ease;
    }
    @media (min-width: 1024px) {
      .hub-page-menu-item { font-size: 14px; padding: 12px 16px; }
    }
    .hub-page-menu-item:last-child { border-bottom: none; }
    .hub-page-menu-item svg { width: 18px; height: 18px; opacity: 0.7; transition: opacity 0.2s ease; flex-shrink: 0; }
    .hub-page-menu-item:hover { color: #fff; background: rgba(255,255,255,0.04); padding-left: 22px; }
    .hub-page-menu-item:hover svg { opacity: 1; }
    .hub-page-menu-item:active { color: #fff; background: rgba(255,255,255,0.08); }
    @keyframes hubPageRestartPulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.9); }
    }
"""

DEFAULT_HUB_HEADER_ACTIONS = """
<button class="hub-page-menu-btn" id="hubPageMenuBtn">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="10" y1="15" x2="20" y2="15"/></svg>
</button>
<select id="hubPageNativeMenuBridge" style="position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;opacity:0.001;pointer-events:auto;appearance:none;-webkit-appearance:none;border:none;outline:none;background:transparent;font-size:13px;z-index:220;cursor:pointer;-webkit-tap-highlight-color:transparent;" aria-hidden="true" tabindex="-1">
  <option value="" disabled selected>Menu</option>
  <option value="new-session">New Session</option>
  <option value="settings">Settings</option>
  <option value="restart-hub">Reload</option>
</select>
"""

DEFAULT_HUB_HEADER_PANELS = """
<div class="hub-page-menu-panel" id="hubPageMenuPanel" hidden>
  <a href="/new-session" class="hub-page-menu-item" data-native-action="new-session"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>New Session</a>
  <a href="/settings" class="hub-page-menu-item" data-native-action="settings"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>Settings</a>
  <button class="hub-page-menu-item" id="hubPageRestartBtn" data-native-action="restart-hub"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"/><path d="M20 12a8 8 0 1 1-2.1-5.3L21 8"/></svg>Reload</button>
</div>
"""

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
<select id="hubPageNativeMenuBridge" style="position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;opacity:0.001;pointer-events:auto;appearance:none;-webkit-appearance:none;border:none;background:transparent;font-size:13px;z-index:220;cursor:pointer" aria-hidden="true" tabindex="-1">
  <option value="" disabled selected>Menu</option>
  <option value="openGitBranchMenu" data-mobile-only="1" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M6 3v12%22/%3E%3Ccircle cx=%2218%22 cy=%226%22 r=%223%22/%3E%3Ccircle cx=%226%22 cy=%2218%22 r=%223%22/%3E%3Cpath d=%22M18 9a9 9 0 0 1-9 9%22/%3E%3C/svg%3E')">Git Branches</option>
  <option value="openAttachedFilesMenu" data-mobile-only="1" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z%22/%3E%3C/svg%3E')">Attached Files</option>
  <option value="reloadChat" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M21 2v6h-6%22/%3E%3Cpath d=%22M20 12a8 8 0 1 1-2.1-5.3L21 8%22/%3E%3C/svg%3E')">Reload</option>
  <option value="openTerminal" data-desktop-only="1" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Crect x=%222%22 y=%223%22 width=%2220%22 height=%2214%22 rx=%222%22/%3E%3Cline x1=%228%22 y1=%2221%22 x2=%2216%22 y2=%2221%22/%3E%3Cline x1=%2212%22 y1=%2217%22 x2=%2212%22 y2=%2221%22/%3E%3C/svg%3E')">Terminal</option>
  <option value="openFinder" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z%22/%3E%3Cpath d=%22M3 10h18%22/%3E%3C/svg%3E')">Finder</option>
  <option value="openCameraMode" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M4 8.5A2.5 2.5 0 0 1 6.5 6H9l1.5-2h3L15 6h2.5A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5z%22/%3E%3Ccircle cx=%2212%22 cy=%2212.5%22 r=%223.5%22/%3E%3C/svg%3E')">Camera</option>
  <option value="openPaneTraceWindow" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M4 5h16%22/%3E%3Cpath d=%22M4 12h16%22/%3E%3Cpath d=%22M4 19h10%22/%3E%3Cpath d=%22M18 17v4%22/%3E%3Cpath d=%22m16 19 2-2 2 2%22/%3E%3C/svg%3E')">Pane Trace</option>
  <option value="exportBtn" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4%22/%3E%3Cpolyline points=%227 10 12 15 17 10%22/%3E%3Cline x1=%2212%22 y1=%2215%22 x2=%2212%22 y2=%223%22/%3E%3C/svg%3E')">Export</option>
  <option value="syncStatus" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M12 20V10%22/%3E%3Cpath d=%22M18 20V4%22/%3E%3Cpath d=%22M6 20v-4%22/%3E%3C/svg%3E')">Sync Status</option>
  <option value="addAgent" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2%22/%3E%3Ccircle cx=%229%22 cy=%227%22 r=%224%22/%3E%3Cline x1=%2222%22 y1=%2211%22 x2=%2216%22 y2=%2211%22/%3E%3Cline x1=%2219%22 y1=%228%22 x2=%2219%22 y2=%2214%22/%3E%3C/svg%3E')">Add Agent</option>
  <option value="removeAgent" style="background-image:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%221.8%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2%22/%3E%3Ccircle cx=%229%22 cy=%227%22 r=%224%22/%3E%3Cline x1=%2222%22 y1=%2211%22 x2=%2216%22 y2=%2211%22/%3E%3C/svg%3E')">Remove Agent</option>
</select>
"""

CHAT_HEADER_PANELS_HTML = """
<div class="hub-page-menu-panel" id="gitBranchPanel" hidden></div>
<div class="hub-page-menu-panel" id="attachedFilesPanel" hidden></div>
<div class="hub-page-menu-panel" id="hubPageMenuPanel" hidden>
  <div class="hub-main-menu-stack">
    <div class="hub-main-menu-list-view">
      <button type="button" class="hub-page-menu-item" data-forward-action="openGitBranchMenu" data-mobile-only="1"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3v12"></path><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg></span><span class="action-label">Git Branches</span><span class="action-mobile">Branches</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="openAttachedFilesMenu" data-mobile-only="1"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg></span><span class="action-label">Attached Files</span><span class="action-mobile">Files</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="reloadChat"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"></path><path d="M20 12a8 8 0 1 1-2.1-5.3L21 8"></path></svg></span><span class="action-label">Reload</span><span class="action-mobile">Reload</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="openTerminal" data-desktop-only="1"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg></span><span class="action-label">Terminal</span><span class="action-mobile">Terminal</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="openFinder"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z"></path><path d="M3 10h18"></path></svg></span><span class="action-label">Finder</span><span class="action-mobile">Finder</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="openCameraMode"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8.5A2.5 2.5 0 0 1 6.5 6H9l1.5-2h3L15 6h2.5A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5z"></path><circle cx="12" cy="12.5" r="3.5"></circle></svg></span><span class="action-label">Camera</span><span class="action-mobile">Camera</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="openPaneTraceWindow"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16"></path><path d="M4 12h16"></path><path d="M4 19h10"></path><path d="M18 17v4"></path><path d="m16 19 2-2 2 2"></path></svg></span><span class="action-label">Pane Trace</span><span class="action-mobile">Pane Trace</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="exportBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg></span><span class="action-label">Export</span><span class="action-mobile">Export</span></button>
      <button type="button" class="hub-page-menu-item" data-forward-action="syncStatus"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20V10"></path><path d="M18 20V4"></path><path d="M6 20v-4"></path></svg></span><span class="action-label">Sync Status</span><span class="action-mobile">Sync</span></button>
      <button type="button" class="hub-page-menu-item positive" data-forward-action="addAgent"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="22" y1="11" x2="16" y2="11"></line><line x1="19" y1="8" x2="19" y2="14"></line></svg></span><span class="action-label">Add Agent</span><span class="action-mobile">Add Agent</span></button>
      <button type="button" class="hub-page-menu-item danger" data-forward-action="removeAgent"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="22" y1="11" x2="16" y2="11"></line></svg></span><span class="action-label">Remove Agent</span><span class="action-mobile">Remove</span></button>
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


def render_hub_page_header(
    *,
    logo_data_uri: str,
    title_href: str = "/",
    title_id: str = "hubPageTitleLink",
    title_aria_label: str = "Multiagent Session Hub",
    title_alt: str = "Multiagent Session Hub",
    actions_html: str = DEFAULT_HUB_HEADER_ACTIONS,
    panels_html: str = DEFAULT_HUB_HEADER_PANELS,
) -> str:
    return (
        HUB_PAGE_HEADER_HTML_TEMPLATE
        .replace("__HUB_LOGO_DATA_URI__", logo_data_uri)
        .replace("__TITLE_HREF__", title_href)
        .replace("__TITLE_ID__", title_id)
        .replace("__TITLE_ARIA_LABEL__", title_aria_label)
        .replace("__TITLE_ALT__", title_alt)
        .replace("__HEADER_ACTIONS__", actions_html.strip())
        .replace("__HEADER_PANELS__", panels_html.strip())
    )


HUB_PAGE_HEADER_HTML_TEMPLATE = """
  <div class="hub-page-header">
    <div class="hub-page-header-shadow"></div>
    <div class="hub-page-header-top">
      <a href="__TITLE_HREF__" class="hub-page-title" id="__TITLE_ID__" aria-label="__TITLE_ARIA_LABEL__">
        <img src="__HUB_LOGO_DATA_URI__" class="hub-page-logo" alt="__TITLE_ALT__">
      </a>
      <div class="hub-page-header-actions">
        __HEADER_ACTIONS__
      </div>
    </div>
    __HEADER_PANELS__
  </div>
"""

HUB_PAGE_HEADER_JS = """
  (function() {
    var menuBtn = document.getElementById("hubPageMenuBtn");
    var menuPanel = document.getElementById("hubPageMenuPanel");
    var restartBtn = document.getElementById("hubPageRestartBtn");
    var titleLink = document.getElementById("hubPageTitleLink");
    var bridge = document.getElementById("hubPageNativeMenuBridge");

    if (titleLink) {
      titleLink.addEventListener("click", function() {
        try { sessionStorage.removeItem("hub_chat_frame"); } catch(_) {}
      });
    }
    
    if (menuBtn && bridge) {
      var _syncBridge = function() {
        if (!menuBtn || menuBtn.offsetParent === null) return;
        var rect = menuBtn.getBoundingClientRect();
        bridge.style.left = rect.left + "px";
        bridge.style.top = rect.top + "px";
        bridge.style.width = rect.width + "px";
        bridge.style.height = rect.height + "px";
        // opacity:0 so focus ring is invisible; pointer-events:auto keeps it tappable
        bridge.style.opacity = "0";
        bridge.style.pointerEvents = "auto";
        bridge.style.zIndex = "999";
        bridge.style.outline = "none";
        bridge.style.webkitTapHighlightColor = "transparent";
      };
      _syncBridge();
      window.addEventListener("resize", _syncBridge, { passive: true });
      window.visualViewport && window.visualViewport.addEventListener("resize", _syncBridge, { passive: true });

      bridge.addEventListener("change", function(e) {
        var action = e.target.value;
        e.target.value = "";
        if (!action) return;
        var item = document.querySelector('[data-native-action="' + action + '"]') ||
                   document.querySelector('[data-forward-action="' + action + '"]');
        if (item) item.click();
      });

      menuBtn.addEventListener("click", function(e) {
        // Fallback for browsers without select overlay support
        if (bridge.showPicker) {
          try { bridge.showPicker(); e.preventDefault(); e.stopPropagation(); return; } catch (err) {}
        }
        if (menuPanel) {
          e.preventDefault();
          e.stopPropagation();
          menuPanel.classList.toggle("open");
          menuBtn.classList.toggle("open");
        }
      });
    } else if (menuBtn && menuPanel) {
      menuBtn.addEventListener("click", function(e) {
        e.stopPropagation();
        menuPanel.classList.toggle("open");
        menuBtn.classList.toggle("open");
      });
      document.addEventListener("click", function() {
        menuPanel.classList.remove("open");
        menuBtn.classList.remove("open");
      });
      menuPanel.addEventListener("click", function(e) { e.stopPropagation(); });
    }
    if (restartBtn) {
      restartBtn.addEventListener("click", function(e) {
        e.preventDefault();
        if (restartBtn.classList.contains("restarting")) return;
        restartBtn.classList.add("restarting");
        var form = restartBtn.closest("form") || { action: "/restart-hub", method: "POST" };
        fetch(form.action, { method: form.method || "POST" })
          .then(function() { setTimeout(function() { location.reload(); }, 1500); })
          .catch(function() { restartBtn.classList.remove("restarting"); });
      });
    }
    window.addEventListener("message", function(e) {
      if (e.data === "hub_close_chat") {
        if (menuPanel) menuPanel.classList.remove("open");
        if (menuBtn) menuBtn.classList.remove("open");
      }
    });
  })();
"""
