from __future__ import annotations

import base64
from pathlib import Path

# Repo-root webp is often gitignored; fresh clones need an inline fallback for the Hub header <img>.
_HUB_LOGO_FALLBACK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="">'
    '<circle cx="9" cy="11" r="3.5" fill="#d0d0d5"/>'
    '<circle cx="23" cy="11" r="3.5" fill="#d0d0d5"/>'
    '<circle cx="16" cy="20" r="3.5" fill="#d0d0d5"/>'
    "</svg>"
)
HUB_LOGO_FALLBACK_SVG_BYTES = _HUB_LOGO_FALLBACK_SVG.encode("utf-8")
HUB_LOGO_FALLBACK_DATA_URI = (
    "data:image/svg+xml;base64,"
    + base64.b64encode(HUB_LOGO_FALLBACK_SVG_BYTES).decode("ascii")
)

HUB_LOGO_WEBP_NAME = "69b8dae91dba9.webp"


def hub_logo_inline_data_uri(repo_root: Path) -> str:
    """img[src] for Hub header: embed webp when present, else bundled SVG data URI."""
    path = repo_root / HUB_LOGO_WEBP_NAME
    if path.is_file():
        try:
            b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:image/webp;base64,{b64}"
        except OSError:
            pass
    return HUB_LOGO_FALLBACK_DATA_URI


def hub_logo_http_body(repo_root: Path) -> tuple[bytes, str]:
    """Body and Content-Type for GET /hub-logo (SVG fallback if webp missing/unreadable)."""
    path = repo_root / HUB_LOGO_WEBP_NAME
    if path.is_file():
        try:
            return path.read_bytes(), "image/webp"
        except OSError:
            pass
    return HUB_LOGO_FALLBACK_SVG_BYTES, "image/svg+xml"

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
    html[data-theme="soft-light"] .hub-page-header {
      background: linear-gradient(rgba(255, 255, 255, 0.9) 0%, rgba(244, 244, 242, 0) 100%);
    }
    /* メニュー展開時: パネルとトップ行だけ同色（親全体に blur を付けない＝パネルが透ける事故を避ける） */
    .hub-page-header:has(.hub-page-menu-panel.open) {
      background: transparent;
    }
    html[data-theme="soft-light"] .hub-page-header:has(.hub-page-menu-panel.open) {
      background: transparent;
    }
    .hub-page-header:has(.hub-page-menu-panel.open) .hub-page-header-top {
      position: relative;
      z-index: 1;
      background: rgba(var(--bg-rgb, 38, 38, 36), 0.72);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
    }
    html[data-theme="soft-light"] .hub-page-header:has(.hub-page-menu-panel.open) .hub-page-header-top {
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(12px) saturate(120%);
      -webkit-backdrop-filter: blur(12px) saturate(120%);
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
    html[data-theme="soft-light"] .hub-page-header-shadow {
      background: linear-gradient(rgba(255, 255, 255, 0.82) 0%, rgba(244, 244, 242, 0) 100%);
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
    html[data-theme="soft-light"] .hub-page-env-badge {
      color: rgba(26, 30, 36, 0.9);
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
    html[data-theme="soft-light"] .hub-page-logo {
      filter: none;
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
      width: 44px; height: 44px; border-radius: 50%;
      background: transparent; border: none; color: rgba(255,255,255,0.96);
      cursor: pointer; font: inherit; font-size: 26px; line-height: 1; -webkit-appearance: none;
      box-shadow: none;
      transition: color 0.2s ease, transform 0.2s ease;
    }
    html[data-theme="soft-light"] .hub-page-menu-btn {
      color: rgba(26, 30, 36, 0.92);
    }
    .hub-page-menu-btn:hover { color: #fff; transform: scale(1.05); }
    .hub-page-menu-btn:active, .hub-page-menu-btn.open { color: #fff; transform: scale(0.95); }
    .hub-page-menu-btn svg { display: block; width: 24px; height: 24px; }
    .hub-page-menu-btn.restarting { animation: hubPageRestartPulse 1.2s ease-in-out infinite; pointer-events: none; border-color: transparent; background: transparent; }
    .hub-page-menu-panel {
      max-height: 0; overflow: hidden;
      transition: max-height 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
      background: rgba(var(--bg-rgb, 38, 38, 36), 0.72);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
    }
    html[data-theme="soft-light"] .hub-page-menu-panel {
      background: rgba(255, 255, 255, 0.92);
      border-top-color: rgba(15, 20, 30, 0.12);
      backdrop-filter: blur(12px) saturate(120%);
      -webkit-backdrop-filter: blur(12px) saturate(120%);
    }
    .hub-page-menu-panel.open { max-height: 400px; }
    .hub-page-menu-item {
      display: flex; align-items: center; gap: 12px;
      padding: 14px 18px; font-size: 14px; font-weight: 400; color: rgba(255,255,255,0.88);
      text-decoration: none; cursor: pointer; border: none;
      border-bottom: 0.5px solid rgba(255,255,255,0.05); background: transparent;
      width: 100%; text-align: left; font: inherit; -webkit-appearance: none;
      box-sizing: border-box; max-width: 100%; margin: 0;
      transition: color 0.15s ease, background 0.15s ease, padding-left 0.2s ease;
    }
    html[data-theme="soft-light"] .hub-page-menu-item {
      color: rgba(26, 30, 36, 0.9);
      border-bottom-color: rgba(15,20,30,0.08);
    }
    html[data-theme="soft-light"] .hub-page-menu-item:hover {
      color: rgba(8, 10, 12, 0.98);
      background: rgba(15, 20, 30, 0.04);
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
    <div class="hub-page-header-shadow"></div>
    <div class="hub-page-header-top">
      <a href="__TITLE_HREF__" class="hub-page-title" id="__TITLE_ID__" aria-label="__TITLE_ARIA_LABEL__"><img src="__HUB_LOGO_DATA_URI__" alt="__TITLE_ALT__" class="hub-page-logo"><span class="hub-page-env-badge" id="hubPageEnvBadge"></span></a>
      <script>!function(){var b=document.getElementById("hubPageEnvBadge");if(b){var h=location.hostname;b.textContent=(h==="localhost"||h==="127.0.0.1"||h==="[::1]"||h.startsWith("192.168.")||h.startsWith("10.")||/^172\\.(1[6-9]|2\\d|3[01])\\./.test(h))?"Local":"Public"}}()</script>
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
      var isLocal = host === "127.0.0.1" || host === "localhost" || host.startsWith("192.168.") || host.startsWith("10.") || /^172\\.(1[6-9]|2\\d|3[01])\\./.test(host);
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
