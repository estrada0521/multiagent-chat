from __future__ import annotations


HUB_PAGE_HEADER_CSS = """
    :root {
      --page-side-pad: 14px;
      --chrome-icon-btn-size: 26px;
      --chrome-icon-size: 16px;
      --chrome-icon-stroke: 1.5;
      --chrome-icon-gap: 2px;
    }
    [hidden] { display: none; }
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
      transition: opacity 0.18s ease;
    }
    .hub-page-header::after { content: none; }
    .hub-page-header-top { border-bottom: none; box-shadow: none; }
    .hub-page-header.header-hidden {
      opacity: 0;
      pointer-events: none;
    }
    .hub-page-header-shadow {
      position: absolute;
      top: 0; left: 0; right: 0;
      width: 100%; height: 84px;
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
      background: transparent; border: none; color: rgba(255,255,255,0.8);
      cursor: pointer; padding: 0; margin: 0; box-shadow: none;
      appearance: none;
      -webkit-appearance: none;
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
      outline: none;
    }
    .hub-page-menu-btn:hover { color: #fff; background: transparent; }
    .hub-page-menu-btn:active { color: #fff; background: transparent; box-shadow: none; }
    .hub-page-menu-btn svg {
      width: var(--chrome-icon-size);
      height: var(--chrome-icon-size);
      stroke-width: var(--chrome-icon-stroke);
    }
    
"""

DEFAULT_HUB_HEADER_ACTIONS = """
<button class="hub-page-menu-btn" id="hubPageMenuBtn">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="10" y1="15" x2="20" y2="15"/></svg>
</button>
<select id="hubPageNativeMenuBridge" style="position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;opacity:0;pointer-events:auto;appearance:none;-webkit-appearance:none;border:none;outline:none;background:transparent;color:transparent;font-size:13px;z-index:220;cursor:pointer;-webkit-tap-highlight-color:transparent;" aria-hidden="true" tabindex="-1">
  <option value="" disabled selected>Menu</option>
  <option value="new-session">New Session</option>
  <option value="settings">Settings</option>
  <option value="restart-hub">Reload</option>
</select>
"""

DEFAULT_HUB_HEADER_PANELS = """
"""


def render_hub_page_header(
    *,
    title_href: str = "/",
    title_id: str = "hubPageTitleLink",
    title_aria_label: str = "Multiagent Session Hub",
    title_alt: str = "Multiagent Session Hub",
    actions_html: str = DEFAULT_HUB_HEADER_ACTIONS,
    panels_html: str = DEFAULT_HUB_HEADER_PANELS,
) -> str:
    return (
        HUB_PAGE_HEADER_HTML_TEMPLATE.replace("__TITLE_HREF__", title_href)
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
      <a href="/" class="hub-page-title" id="hubPageTitleLink" aria-label="Hub" title="Hub">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" class="hub-page-logo" aria-hidden="true"><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/></svg>
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
    var titleLink = document.getElementById("hubPageTitleLink");
    var bridge = document.getElementById("hubPageNativeMenuBridge");
    var _restarting = false;

    function restartHub() {
      if (_restarting) return;
      _restarting = true;
      fetch("/restart-hub", { method: "POST" })
        .then(function() { setTimeout(function() { location.reload(); }, 1500); })
        .catch(function() { _restarting = false; });
    }

    if (titleLink) {
      titleLink.addEventListener("click", function() {
        try { sessionStorage.removeItem("hub_chat_frame"); } catch(_) {}
      });
    }
    
    if (menuBtn && bridge) {
      var _syncBridge = function() {
        if (!menuBtn || menuBtn.offsetParent === null) return;
        var icon = menuBtn.querySelector("svg");
        var rect = icon ? icon.getBoundingClientRect() : menuBtn.getBoundingClientRect();
        var padX = 9;
        var padY = 10;
        var left = Math.max(0, rect.left - padX);
        var top = Math.max(0, rect.top - padY);
        var width = rect.width + (padX * 2);
        var height = rect.height + (padY * 2);
        var viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
        var viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
        if (viewportWidth > 0 && left + width > viewportWidth) {
          left = Math.max(0, viewportWidth - width);
        }
        if (viewportHeight > 0 && top + height > viewportHeight) {
          top = Math.max(0, viewportHeight - height);
        }
        bridge.style.left = left + "px";
        bridge.style.top = top + "px";
        bridge.style.width = width + "px";
        bridge.style.height = height + "px";
        // opacity:0 so focus ring is invisible; pointer-events:auto keeps it tappable
        bridge.style.opacity = "0";
        bridge.style.pointerEvents = "auto";
        bridge.style.zIndex = "999";
        bridge.style.background = "transparent";
        bridge.style.color = "transparent";
        bridge.style.border = "0";
        bridge.style.outline = "none";
        bridge.style.webkitTapHighlightColor = "transparent";
      };
      _syncBridge();
      window.addEventListener("resize", _syncBridge, { passive: true });
      window.addEventListener("scroll", _syncBridge, { passive: true });
      window.visualViewport && window.visualViewport.addEventListener("resize", _syncBridge, { passive: true });
      window.visualViewport && window.visualViewport.addEventListener("scroll", _syncBridge, { passive: true });
      menuBtn.addEventListener("pointerdown", _syncBridge, { passive: true });

      bridge.addEventListener("change", function(e) {
        var action = e.target.value;
        e.target.value = "";
        if (!action) return;
        if (action === "new-session") {
          location.href = "/new-session";
          return;
        }
        if (action === "settings") {
          location.href = "/settings";
          return;
        }
        if (action === "restart-hub") {
          restartHub();
        }
      });

      menuBtn.addEventListener("click", function(e) {
        _syncBridge();
        // Fallback for browsers without select overlay support
        if (bridge.showPicker) {
          try { bridge.showPicker(); e.preventDefault(); e.stopPropagation(); return; } catch (err) {}
        }
        e.preventDefault();
        e.stopPropagation();
        try { bridge.focus({ preventScroll: true }); } catch (_) { try { bridge.focus(); } catch (_) {} }
        try { bridge.click(); } catch (_) {}
      });
    }
  })();
"""
