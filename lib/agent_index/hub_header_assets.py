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
      background: linear-gradient(rgba(10, 10, 10, 0.6) 0%, rgba(0, 0, 0, 0) 100%);
      border-bottom: none;
      box-shadow: none;
      transition: opacity 0.3s ease;
    }
    .hub-page-header::after { content: none !important; }
    .hub-page-header-top { border-bottom: none !important; box-shadow: none !important; }
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
      min-width: 48px; min-height: 48px;
      gap: 8px;
      transition: opacity 0.2s ease, transform 0.2s ease;
    }
    .hub-page-title:hover { opacity: 0.8; transform: scale(0.98); }
    .hub-page-header-actions {
      display: flex;
      align-items: center;
      gap: 4px;
      flex: 0 0 auto;
    }
    .hub-page-logo {
      height: 26px;
      width: auto;
      display: block;
      filter: invert(1) grayscale(1) brightness(1.04) contrast(1.04);
      flex: 0 0 auto;
    }
    .hub-page-menu-item { font-size: 14px !important; padding: 14px 18px !important; }
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
    @keyframes hubPageRestartPulse { 0%, 100% { opacity: 1; filter: drop-shadow(0 0 8px rgba(255,255,255,0.5)); } 50% { opacity: 0.4; filter: drop-shadow(0 0 0 rgba(255,255,255,0)); } }
    .hub-page-menu-btn {
      display: flex; align-items: center; justify-content: center;
      width: 32px; height: 32px;
      background: transparent; border: none; color: #ffffff;
      cursor: pointer; -webkit-appearance: none;
      box-shadow: none;
      transition: all 0.2s ease;
    }
    .hub-page-menu-btn:hover { color: #fff; }
    .hub-page-menu-btn:active, .hub-page-menu-btn.open {
      color: #fff;
      transform: scale(0.9);
    }
    .hub-page-menu-btn svg { display: block; width: 20px; height: 20px; stroke-width: 1.6; }
    
    /* PC adjustments */
    @media (min-width: 1024px) {
      .hub-page-header-top {
        padding: 10px 18px;
      }
      .hub-page-menu-btn {
        width: 28px; height: 28px;
      }
      .hub-page-menu-btn svg {
        width: 18px; height: 18px;
        stroke-width: 1.5;
      }
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
      padding: 12px 18px; font-size: 13.5px; font-weight: 400; color: rgba(255,255,255,0.8);
      text-decoration: none; cursor: pointer; border: none;
      border-bottom: 0.5px solid rgba(255,255,255,0.05); background: transparent;
      width: 100%; text-align: left; font: inherit; -webkit-appearance: none;
      box-sizing: border-box; max-width: 100%; margin: 0;
      transition: all 0.2s ease;
    }
    .hub-page-menu-item svg { flex-shrink: 0; width: 16px; height: 16px; stroke-width: 1.6; opacity: 0.7; }
    .hub-page-menu-item:last-child { border-bottom: none; }
    .hub-page-menu-item:hover { color: #fff; background: rgba(255,255,255,0.04); padding-left: 22px; }
    .hub-page-menu-item:hover svg { opacity: 1; }
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
    
    @media (max-width: 480px) {
      .hub-page-menu-panel {
        background: rgb(10, 10, 10) !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
      }
    }
"""

HUB_PAGE_HEADER_HTML_TEMPLATE = """
  <div class="hub-page-header">
    <div class="hub-page-header-shadow"></div>
    <div class="hub-page-header-top">
      <a href="__TITLE_HREF__" class="hub-page-title" id="__TITLE_ID__" aria-label="__TITLE_ARIA_LABEL__"><img src="__HUB_LOGO_DATA_URI__" alt="__TITLE_ALT__" class="hub-page-logo"></a>
      <div class="hub-page-header-actions">__HEADER_ACTIONS__</div>
    </div>
    __HEADER_PANELS__
  </div>
"""

DEFAULT_HUB_HEADER_ACTIONS = """
<button class="hub-page-menu-btn" id="hubPageMenuBtn">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/></svg>
</button>
"""

DEFAULT_HUB_HEADER_PANELS = """
<div class="hub-page-menu-panel" id="hubPageMenuPanel">
  <a href="/new-session" class="hub-page-menu-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>New Session</a>
  <a href="/settings" class="hub-page-menu-item"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>Settings</a>
  <button class="hub-page-menu-item" id="hubPageRestartBtn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"/><path d="M20 12a8 8 0 1 1-2.1-5.3L21 8"/></svg>Reload</button>
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
    if (titleLink) {
      titleLink.addEventListener("click", function() {
        try { sessionStorage.removeItem("hub_chat_frame"); } catch(_) {}
      });
    }
    if (menuBtn && menuPanel) {
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
  /* ── Header hide on scroll ── */
  (function() {
    var header = document.querySelector(".hub-page-header");
    if (!header) return;
    var prevY = window.scrollY;
    var HIDE_THRESHOLD = 50;
    window.addEventListener("scroll", function() {
      var y = window.scrollY;
      if (y > prevY && y > HIDE_THRESHOLD) {
        header.classList.add("header-hidden");
      } else if (y < prevY) {
        header.classList.remove("header-hidden");
      }
      prevY = y;
    }, { passive: true });
  })();
"""
