from __future__ import annotations

HUB_PAGE_HEADER_CSS = """
    :root { --page-side-pad: 14px; }
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
    html, body { font-family: "anthropicSans", "SF Pro Text", "Segoe UI", sans-serif !important; }
    .hub-page-header {
      display: flex; flex-direction: column;
      width: 100%;
      margin: 0;
      position: sticky; top: 0; z-index: 100;
      background: rgba(var(--bg-rgb, 38, 38, 36), 0.42);
      backdrop-filter: blur(28px) saturate(190%);
      -webkit-backdrop-filter: blur(28px) saturate(190%);
      border-bottom: 0.5px solid rgba(255, 255, 255, 0.1);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
    }
    .hub-page-header-top {
      display: flex; align-items: center; justify-content: space-between;
      padding: max(8px, env(safe-area-inset-top)) var(--page-side-pad) 0;
      box-sizing: border-box;
    }
    .hub-page-title {
      display: flex; align-items: center; text-decoration: none; opacity: 1;
      transition: opacity 0.2s ease, transform 0.2s ease;
    }
    .hub-page-title:hover { opacity: 0.8; transform: scale(0.98); }
    .hub-page-env-badge {
      position: relative;
      left: -36px;
      top: -10px;
      font-size: 14px;
      font-weight: 500;
      color: rgba(252,252,252,0.9);
      margin-left: 0;
      margin-top: 0;
      letter-spacing: 0.01em;
      flex: 0 0 auto;
    }
    .hub-page-header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 0 0 auto;
    }
    .hub-page-logo {
      height: 26px; width: auto; display: block; margin-top: 0px;
      filter: invert(1) grayscale(1) brightness(1.04) contrast(1.04);
    }
    .hub-page-menu-item { font-size: 15px !important; padding: 14px 18px !important; }
    .hub-page-menu-btn { width: 48px !important; height: 48px !important; }
    .eyebrow { font-size: 14px !important; }
    h1 { font-size: clamp(34px, 4vw, 48px) !important; }
    .sub { font-size: 17px !important; }
    .toolbar { font-size: 15px !important; }
    .hub-nav a, .hub-nav button { font-size: 15px !important; padding: 8px 14px !important; }
    .stat-card { padding: 16px 18px !important; }
    .stat-label { font-size: 14px !important; }
    .stat-val { font-size: 28px !important; }
    .stat-breakdown-heading { font-size: 13px !important; }
    .stat-breakdown-label { font-size: 15px !important; }
    .stat-breakdown-val { font-size: 15px !important; }
    .mob-row-name { font-size: 26px !important; }
    .mob-row-path { font-size: 15px !important; }
    .mob-row-meta { font-size: 14px !important; }
    .mob-badge { font-size: 12px !important; }
    .mob-kill-link { font-size: 13px !important; }
    .mob-empty { font-size: 17px !important; }
    @keyframes hubPageRestartPulse { 0%, 100% { opacity: 1; filter: drop-shadow(0 0 8px rgba(255,255,255,0.5)); } 50% { opacity: 0.4; filter: drop-shadow(0 0 0 rgba(255,255,255,0)); } }
    .hub-page-menu-btn {
      display: flex; align-items: center; justify-content: center;
      width: 44px; height: 44px; border-radius: 50%;
      background: transparent; border: none; color: rgba(255,255,255,0.96);
      cursor: pointer; font: inherit; font-size: 26px; line-height: 1; -webkit-appearance: none;
      box-shadow: none;
      transition: color 0.2s ease, transform 0.2s ease;
    }
    .hub-page-menu-btn:hover { color: #fff; transform: scale(1.05); }
    .hub-page-menu-btn:active, .hub-page-menu-btn.open { color: #fff; transform: scale(0.95); }
    .hub-page-menu-btn svg { display: block; width: 24px; height: 24px; }
    .hub-page-menu-btn.restarting { animation: hubPageRestartPulse 1.2s ease-in-out infinite; pointer-events: none; border-color: transparent; background: transparent; }
    .hub-page-menu-panel {
      max-height: 0; overflow: hidden;
      transition: max-height 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
      border-top: 0.5px solid transparent;
      background: rgba(var(--bg-rgb, 38, 38, 36), 0.42);
      backdrop-filter: blur(28px) saturate(190%);
      -webkit-backdrop-filter: blur(28px) saturate(190%);
    }
    .hub-page-menu-panel.open { max-height: 400px; border-top-color: rgba(255,255,255,0.05); }
    .hub-page-menu-item {
      display: flex; align-items: center; gap: 12px;
      padding: 16px 20px; font-size: 15px; font-weight: 500; color: rgba(255,255,255,0.88);
      text-decoration: none; cursor: pointer; border: none;
      border-bottom: 0.5px solid rgba(255,255,255,0.05); background: transparent;
      width: 100%; text-align: left; font: inherit; -webkit-appearance: none;
      box-sizing: border-box; max-width: 100%; margin: 0;
      transition: color 0.15s ease, background 0.15s ease, padding-left 0.2s ease;
    }
    .hub-page-menu-item:last-child { border-bottom: none; }
    .hub-page-menu-item:hover { color: #fff; background: rgba(255,255,255,0.03); padding-left: 24px; }
    .hub-page-menu-item:active { color: #fff !important; background: rgba(255,255,255,0.08); }
    html { scrollbar-width: none; -ms-overflow-style: none; }
    html::-webkit-scrollbar { display: none; }
    .hero .eyebrow { display: none; }
    @keyframes hubFadeSlideUp {
      0% { opacity: 0; transform: translateY(16px); }
      100% { opacity: 1; transform: translateY(0); }
    }
    .animate-in { animation: hubFadeSlideUp 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) backwards; }
    .home-card, .form-panel, .panel, .stat-card, .session-card {
      animation: hubFadeSlideUp 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) backwards;
    }
    .home-card:nth-child(1), .form-panel:nth-child(1), .stat-card:nth-child(1), .session-card:nth-child(1) { animation-delay: 0.05s; }
    .home-card:nth-child(2), .form-panel:nth-child(2), .stat-card:nth-child(2), .session-card:nth-child(2) { animation-delay: 0.10s; }
    .home-card:nth-child(3), .form-panel:nth-child(3), .stat-card:nth-child(3), .session-card:nth-child(3) { animation-delay: 0.15s; }
    .home-card:nth-child(4), .form-panel:nth-child(4), .stat-card:nth-child(4), .session-card:nth-child(4) { animation-delay: 0.20s; }
    .home-card:nth-child(5), .form-panel:nth-child(5), .stat-card:nth-child(5), .session-card:nth-child(5) { animation-delay: 0.25s; }
    .home-card:nth-child(n+6), .form-panel:nth-child(n+6), .stat-card:nth-child(n+6), .session-card:nth-child(n+6) { animation-delay: 0.30s; }
    .start-btn { animation: hubFadeSlideUp 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) backwards 0.20s; }
"""

HUB_PAGE_HEADER_HTML_TEMPLATE = """
  <div class="hub-page-header">
    <div class="hub-page-header-top">
      <a href="__TITLE_HREF__" class="hub-page-title" id="__TITLE_ID__" aria-label="__TITLE_ARIA_LABEL__"><img src="__HUB_LOGO_DATA_URI__" alt="__TITLE_ALT__" class="hub-page-logo"><span class="hub-page-env-badge" id="hubPageEnvBadge"></span></a>
      <div class="hub-page-header-actions">__HEADER_ACTIONS__</div>
    </div>
    __HEADER_PANELS__
  </div>
"""

DEFAULT_HUB_HEADER_ACTIONS = """
<button class="hub-page-menu-btn" id="hubPageMenuBtn">
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"><line x1="3" y1="8" x2="21" y2="8"/><line x1="6" y1="16" x2="21" y2="16"/></svg>
</button>
"""

DEFAULT_HUB_HEADER_PANELS = """
<div class="hub-page-menu-panel" id="hubPageMenuPanel">
  <a href="/new-session" class="hub-page-menu-item"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>New Session</a>
  <a href="/stats" class="hub-page-menu-item"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>Statistics</a>
  <a href="/settings" class="hub-page-menu-item"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>Settings</a>
  <button class="hub-page-menu-item" id="hubPageRestartBtn"><svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.62"/></svg>Reload</button>
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

HUB_PAGE_HEADER_JS = """
  (function() {
    var menuBtn = document.getElementById("hubPageMenuBtn");
    var menuPanel = document.getElementById("hubPageMenuPanel");
    var restartBtn = document.getElementById("hubPageRestartBtn");
    var titleLink = document.getElementById("hubPageTitleLink");
    var envBadge = document.getElementById("hubPageEnvBadge");
    if (envBadge) {
      var host = String(location.hostname || "");
      var isLocal = host === "127.0.0.1" || host === "localhost" || host.startsWith("192.168.");
      envBadge.textContent = isLocal ? "Local" : "Public";
    }
    if (titleLink) {
      titleLink.addEventListener("click", function() {
        try { sessionStorage.removeItem("hub_chat_frame"); } catch(_) {}
      });
    }
    if (menuBtn && menuPanel) {
      menuBtn.addEventListener("click", function(e) { e.stopPropagation(); menuPanel.classList.toggle("open"); menuBtn.classList.toggle("open"); });
      document.addEventListener("click", function() { menuPanel.classList.remove("open"); menuBtn.classList.remove("open"); });
      menuPanel.addEventListener("click", function(e) { e.stopPropagation(); });
    }
    if (restartBtn) {
      restartBtn.addEventListener("click", async function() {
        if (restartBtn.classList.contains("restarting")) return;
        restartBtn.classList.add("restarting"); restartBtn.disabled = true;
        try { await fetch("/restart-hub", { method: "POST" }); } catch (_) {}
        var t0 = Date.now();
        var poll = async function() {
          try { var r = await fetch("/sessions?ts=" + Date.now(), { cache: "no-store" }); if (r.ok) { window.location.replace("/"); return; } } catch (_) {}
          if (Date.now() - t0 < 20000) { setTimeout(poll, 500); } else { window.location.reload(); }
        };
        setTimeout(poll, 700);
      });
    }
  })();
"""
