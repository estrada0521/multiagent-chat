    const _chatOverlay = document.getElementById("chatOverlay");
    const _chatFrame = document.getElementById("chatFrame");
    const _launchShell = document.getElementById("launchShell");
    let _hubChatParentLayoutMax = 0;
    let _hubMinParentChromeGap = Infinity;
    let _hubLayoutRefW = 0;
    let _hubLayoutRefH = 0;
    let _hubVVBridgeHandler = null;
    let _hubPreOverlayScrollY = 0;
    let _currentChatSessionName = "";
    let _currentChatUrl = "";
    let _chatFrameRenderReady = false;
    let _hubLaunchShellPending = false;
    let _awaitingChatRenderReady = false;
    let _hubReadyTimeoutTimer = 0;
    let _chatOverlayCloseTimer = 0;
    let refreshMobSessions = null;
    const HUB_CHAT_FRAME_KEY = "hub_chat_frame";
    const HUB_LAST_SESSION_KEY = "agent_window_hub_last_session_name";
    const HUB_PENDING_ERROR_KEY = "agent_window_hub_pending_error";
    const HUB_CHAT_URL_CACHE_TTL_MS = 180000;
    const HUB_CHAT_URL_CACHE_LIMIT = 3;
    const HUB_LAUNCH_SHELL_PARAM = "launch_shell";
    const hubChatUrls = createHubChatUrlResolver({
      cacheLimit: HUB_CHAT_URL_CACHE_LIMIT,
      ttlMs: HUB_CHAT_URL_CACHE_TTL_MS,
      cacheKey: (openHref, name) => String(name || "").trim() || String(openHref || "").trim(),
      wrapUrl: (url) => hubFrameChatUrl(url),
      errorMessage: "open session failed",
    });
    const applyMobThemeGradientVars = () => {
      const root = document.documentElement;
      const channels = getComputedStyle(root).getPropertyValue("--bg-rgb").trim();
      if (channels) root.style.setProperty("--mob-top-gradient-rgb", channels);
    };
    applyMobThemeGradientVars();
    new MutationObserver((mutations) => {
      if (mutations.some((mutation) => mutation.attributeName === "data-theme")) {
        applyMobThemeGradientVars();
      }
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const resolveMobileTheme = () => {
      const setting = document.documentElement.dataset.themeMobileSetting;
      if (setting === "light" || setting === "dark") return setting;
      try { return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; } catch (_) { return "dark"; }
    };
    const publishMobileTheme = (observedTheme = "") => {
      const theme = observedTheme === "light" || observedTheme === "dark"
        ? observedTheme
        : resolveMobileTheme();
      const root = document.documentElement;
      root.dataset.theme = theme;
      // Do this synchronously as well as through the CSS selector.  Safari's
      // PWA renderer can otherwise keep the fixed Hub gradient in its old
      // compositing layer for a frame after an appearance change.
      root.style.colorScheme = theme;
      applyMobThemeGradientVars();
      try { _chatFrame.contentDocument.documentElement.dataset.theme = theme; } catch (_) {}
      try { _chatFrame?.contentWindow?.postMessage({ type: "hub-theme-changed", theme }, "*"); } catch (_) {}
      return theme;
    };
    publishMobileTheme();
    const refreshSystemMobileTheme = () => publishMobileTheme();
    try {
      const systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
      if (systemThemeQuery.addEventListener) systemThemeQuery.addEventListener("change", refreshSystemMobileTheme);
      else if (systemThemeQuery.addListener) systemThemeQuery.addListener(refreshSystemMobileTheme);
    } catch (_) {}
    // iOS may defer a media-query change while an installed PWA is in the
    // background.  Reconcile on every return to the Hub, but only in System.
    window.addEventListener("pageshow", refreshSystemMobileTheme);
    window.addEventListener("focus", refreshSystemMobileTheme);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) refreshSystemMobileTheme();
    });
    const HUB_READY_TIMEOUT_MS = 5000;
    const CHAT_OVERLAY_CLOSE_MS = 300;
    function resetChatOverlayMotionStyles() {
      _chatOverlay.style.transform = "";
      _chatOverlay.style.transition = "";
      _chatOverlay.style.opacity = "";
    }
    // The overlay's edge line must vanish when the slide *looks* seated, which
    // the hard-decelerating ease reaches well before the transition's nominal
    // end. Fire .overlay-settled on a lead-time timer, with transitionend as a
    // backstop.
    const CHAT_OVERLAY_SLIDE_MS = 440;        // matches #chatOverlay transform transition
    const CHAT_OVERLAY_SETTLE_LEAD_MS = 130;
    let _overlaySettleHandler = null;
    let _overlaySettleTimer = 0;
    function clearOverlaySettle() {
      if (_overlaySettleHandler) {
        _chatOverlay.removeEventListener("transitionend", _overlaySettleHandler);
        _overlaySettleHandler = null;
      }
      if (_overlaySettleTimer) {
        clearTimeout(_overlaySettleTimer);
        _overlaySettleTimer = 0;
      }
      _chatOverlay.classList.remove("overlay-settled");
    }
    function armOverlaySettle() {
      clearOverlaySettle();
      const settle = () => {
        clearOverlaySettle();
        if (_chatOverlay.classList.contains("overlay-visible")) {
          _chatOverlay.classList.add("overlay-settled");
        }
      };
      _overlaySettleHandler = (event) => {
        if (event.target !== _chatOverlay || event.propertyName !== "transform") return;
        settle();
      };
      _chatOverlay.addEventListener("transitionend", _overlaySettleHandler);
      _overlaySettleTimer = setTimeout(settle, Math.max(0, CHAT_OVERLAY_SLIDE_MS - CHAT_OVERLAY_SETTLE_LEAD_MS));
    }
    function showLaunchShell() {
      if (!_launchShell) return;
      _launchShell.hidden = false;
      _launchShell.classList.add("visible");
    }
    function resetLaunchShellCard() {
      const card = _launchShell?.querySelector(".launch-shell-card");
      if (!card) return;
      card.setAttribute("aria-hidden", "true");
      card.innerHTML = '<span class="launch-shell-title">Agent Window</span>';
    }
    function hideLaunchShell() {
      if (!_launchShell) return;
      _launchShell.classList.remove("visible");
      _launchShell.hidden = true;
    }
    function clearHubReadyTimeout() {
      if (!_hubReadyTimeoutTimer) return;
      clearTimeout(_hubReadyTimeoutTimer);
      _hubReadyTimeoutTimer = 0;
    }
    function failHubReadyWait(message) {
      _hubLaunchShellPending = false;
      _awaitingChatRenderReady = false;
      clearHubReadyTimeout();
      clearLaunchShellQueryFlag();
      hideLaunchShell();
    }
    function startHubReadyTimeout() {
      if (_hubReadyTimeoutTimer) return;
      resetLaunchShellCard();
      _hubReadyTimeoutTimer = setTimeout(() => {
        failHubReadyWait("timeout");
      }, HUB_READY_TIMEOUT_MS);
    }
    function finishHubReadyWaitIfComplete() {
      if (_hubLaunchShellPending || _awaitingChatRenderReady) return;
      clearHubReadyTimeout();
      hideLaunchShell();
    }
    function clearLaunchShellQueryFlag() {
      const params = new URLSearchParams(window.location.search || "");
      if (!params.has(HUB_LAUNCH_SHELL_PARAM)) return;
      params.delete(HUB_LAUNCH_SHELL_PARAM);
      const nextQuery = params.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}${window.location.hash || ""}`;
      try {
        window.history.replaceState(window.history.state, "", nextUrl);
      } catch (_) { }
    }
    function releaseHubLaunchShellAfterRender() {
      if (!_hubLaunchShellPending) return;
      _hubLaunchShellPending = false;
      clearLaunchShellQueryFlag();
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          finishHubReadyWaitIfComplete();
        });
      });
    }
    function startChatRenderWait() {
      _awaitingChatRenderReady = true;
      startHubReadyTimeout();
    }
    function finishChatRenderWait() {
      if (!_awaitingChatRenderReady) return;
      _awaitingChatRenderReady = false;
      finishHubReadyWaitIfComplete();
    }
    function cancelChatRenderWait() {
      _awaitingChatRenderReady = false;
      finishHubReadyWaitIfComplete();
    }
    const _launchShellParams = new URLSearchParams(window.location.search || "");
    _hubLaunchShellPending = _launchShellParams.get(HUB_LAUNCH_SHELL_PARAM) === "1";
    if (_hubLaunchShellPending) {
      showLaunchShell();
      startHubReadyTimeout();
    }
    function rememberLastSession(name) {
      const normalized = String(name || "").trim();
      if (!normalized) return;
      try { sessionStorage.setItem(HUB_LAST_SESSION_KEY, normalized); } catch (_) { }
    }
    function lastRememberedSession() {
      try { return (sessionStorage.getItem(HUB_LAST_SESSION_KEY) || "").trim(); } catch (_) { return ""; }
    }
    function syncMobileSelectedSessionRows() {
      const selectedName = String(_currentChatSessionName || lastRememberedSession() || "").trim();
      document.querySelectorAll("#mobListWrap .mob-session-row[data-session-name]").forEach((row) => {
        const isSelected = !!selectedName && row.dataset.sessionName === selectedName;
        row.classList.toggle("is-selected", isSelected);
        if (isSelected) row.setAttribute("aria-current", "page");
        else row.removeAttribute("aria-current");
      });
    }
    function persistChatFrameState(url, name) {
      const normalizedUrl = String(url || "").trim();
      if (!normalizedUrl) return;
      const normalizedName = String(name || "").trim();
      try { sessionStorage.setItem(HUB_CHAT_FRAME_KEY, JSON.stringify({ url: normalizedUrl, name: normalizedName })); } catch (_) { }
    }
    function clearPersistedChatFrameState() {
      try { sessionStorage.removeItem(HUB_CHAT_FRAME_KEY); } catch (_) { }
    }
    function consumePendingHubErrorMessage() {
      let message = "";
      try {
        message = String(sessionStorage.getItem(HUB_PENDING_ERROR_KEY) || "");
        if (message) sessionStorage.removeItem(HUB_PENDING_ERROR_KEY);
      } catch (_) {
        message = "";
      }
      return message;
    }
    function hubFrameChatUrl(chatUrl) {
      const raw = String(chatUrl || "").trim();
      if (!raw) return raw;
      try {
        const next = new URL(raw, window.location.href);
        // Direct (non-proxied) access points the iframe at the session's own
        // chat_port, a different port on this same host, not the same
        // origin as the Hub -- only reject truly foreign hosts here.
        if (next.hostname !== window.location.hostname) return raw;
        // This page only ever runs as the mobile Hub, so it already knows
        // the answer the framed chat page would otherwise have to guess
        // from headers alone -- guessing is what fails for iPad Safari.
        next.searchParams.set("view", "mobile");
        return next.origin === window.location.origin
          ? next.pathname + next.search + next.hash
          : next.toString();
      } catch (_) {}
      return raw;
    }
    function hubFrameSrcMatches(url) {
      const current = normalizeComparableUrl(_chatFrame.src);
      const next = normalizeComparableUrl(url);
      return !!current && !!next && current === next;
    }
    function cacheChatUrl(name, url) {
      hubChatUrls.write(name, url);
    }
    function _bumpHubChatParentLayoutMax() {
      if (_chatOverlay.hidden) return;
      const ih = window.innerHeight || 0;
      const ch = document.documentElement.clientHeight || 0;
      _hubChatParentLayoutMax = Math.max(_hubChatParentLayoutMax, ih, ch);
      _postHubLayoutToChat();
    }
    function _postHubLayoutToChat() {
      const w = _chatFrame.contentWindow;
      if (!w || _chatOverlay.hidden) return;
      const iw = window.innerWidth || 0;
      const ih = window.innerHeight || 0;
      if (_hubLayoutRefW > 0 && _hubLayoutRefH > 0) {
        const b0 = _hubLayoutRefH >= _hubLayoutRefW;
        const b1 = ih >= iw;
        const diffH = Math.abs(_hubLayoutRefH - ih);
        if (b0 !== b1 && diffH > 150) {
          _hubMinParentChromeGap = Infinity;
        }
      }
      _hubLayoutRefW = iw;
      _hubLayoutRefH = ih;
      const vv = window.visualViewport;
      const vvH = vv ? vv.height : ih;
      const vvTop = vv ? vv.offsetTop : 0;
      const raw = Math.max(0, Math.round(ih - vvTop - vvH));
      if (raw < 150) {
        _hubMinParentChromeGap = Math.min(_hubMinParentChromeGap, raw);
      }
      const effectiveGap = raw >= 150 ? raw : _hubMinParentChromeGap;
      try {
        w.postMessage(
          {
            type: "hub-layout",
            layoutHeight: _hubChatParentLayoutMax,
            parentInnerHeight: ih,
            parentVvHeight: vvH,
            parentVvOffsetTop: vvTop,
            parentChromeGap: effectiveGap === Infinity ? raw : effectiveGap,
          },
          "*"
        );
      } catch (_) { }
    }
    function _attachHubViewportBridge() {
      if (_hubVVBridgeHandler) return;
      _hubVVBridgeHandler = () => { _bumpHubChatParentLayoutMax(); };
      window.addEventListener("resize", _hubVVBridgeHandler, { passive: true });
      if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", _hubVVBridgeHandler);
        window.visualViewport.addEventListener("scroll", _hubVVBridgeHandler);
      }
    }
    function _detachHubViewportBridge() {
      if (!_hubVVBridgeHandler) return;
      window.removeEventListener("resize", _hubVVBridgeHandler);
      if (window.visualViewport) {
        window.visualViewport.removeEventListener("resize", _hubVVBridgeHandler);
        window.visualViewport.removeEventListener("scroll", _hubVVBridgeHandler);
      }
      _hubVVBridgeHandler = null;
    }
    function _fitChatOverlay() {
      if (_chatOverlay.hidden) return;
      _chatOverlay.style.top = "";
      _chatOverlay.style.height = "";
    }
    function updateMenuContext(isChat) {
      const bridge = document.getElementById("pageNativeMenuBridge");
      if (!bridge) return;
      if (isChat) {
        bridge.innerHTML = `
          <option value="" disabled selected>Menu</option>
          <option value="close-session">Close Session</option>
          <option value="restart-hub">Reload</option>
        `;
      } else {
        bridge.innerHTML = `
          <option value="" disabled selected>Menu</option>
          <option value="restart-hub">Reload</option>
        `;
      }
    }
    updateMenuContext(false);
    function openChatInFrame(url, name) {
      if (_chatOverlayCloseTimer) {
        clearTimeout(_chatOverlayCloseTimer);
        _chatOverlayCloseTimer = 0;
      }
      rememberLastSession(name);
      if (_hubLaunchShellPending) showLaunchShell();
      startChatRenderWait();
      const normalizedName = String(name || "").trim();
      const normalizedUrl = hubFrameChatUrl(url, normalizedName);
      cacheChatUrl(normalizedName, normalizedUrl);
      clearPersistedChatFrameState();
      _currentChatUrl = normalizedUrl;
      _hubMinParentChromeGap = Infinity;
      _hubLayoutRefW = window.innerWidth || 0;
      _hubLayoutRefH = window.innerHeight || 0;
      _hubChatParentLayoutMax = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
      const onChatReady = function () {
        _chatFrame.style.transition = "opacity 140ms ease";
        _chatFrame.style.opacity = "1";
        _bumpHubChatParentLayoutMax();
        _postHubLayoutToChat();
        publishMobileTheme();
        if (_chatFrameRenderReady) {
          persistChatFrameState(normalizedUrl, normalizedName);
          finishChatRenderWait();
        }
      };
      // chat -> hub -> same chat: the frame still holds that rendered
      // session, so re-show it as-is instead of blanking and reloading --
      // the session should feel continuous, not rebuilt. (A stale ts in the
      // resolved URL past the cache TTL falls through to a fresh load.)
      const reuseLoadedFrame =
        !!normalizedName && _chatFrameRenderReady && hubFrameSrcMatches(normalizedUrl);
      _chatFrame.style.transition = "none";
      _chatFrame.style.opacity = reuseLoadedFrame ? "1" : "0";
      _chatFrame.onload = onChatReady;
      _attachHubViewportBridge();
      updateMenuContext(true);
      _hubPreOverlayScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.documentElement.classList.add("hub-chat-overlay-active");
      document.body.classList.add("hub-chat-overlay-active");
      const _wasPeeking = _chatOverlay.classList.contains("overlay-peeking");
      document.documentElement.classList.remove("hub-chat-peeking");
      _chatOverlay.classList.remove("overlay-visible", "overlay-closing", "overlay-peeking");
      clearOverlaySettle();
      resetChatOverlayMotionStyles();
      _chatOverlay.hidden = false;
      if (_wasPeeking) {
        _chatOverlay.classList.add("overlay-visible");
        armOverlaySettle();
        document.documentElement.classList.add("hub-chat-ui-active");
      } else {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            if (_chatOverlay.hidden) return;
            _chatOverlay.classList.add("overlay-visible");
            armOverlaySettle();
            document.documentElement.classList.add("hub-chat-ui-active");
          });
        });
      }
      _currentChatSessionName = normalizedName;
      syncMobileSelectedSessionRows();
      if (reuseLoadedFrame) {
        requestAnimationFrame(onChatReady);
      } else {
        _chatFrameRenderReady = false;
        if (hubFrameSrcMatches(normalizedUrl)) {
          _chatFrame.src = "about:blank";
        }
        _chatFrame.src = normalizedUrl;
      }
      _fitChatOverlay();
    }
    function closeChatFrame() {
      cancelChatRenderWait();
      if (!_hubLaunchShellPending) hideLaunchShell();
      _detachHubViewportBridge();
      _chatFrame.style.transition = "";
      _chatFrame.style.opacity = "1";
      try {
        window.scrollTo(0, _hubPreOverlayScrollY);
      } catch (_) { }
      _chatFrame.onload = null;
      _chatOverlay.classList.remove("overlay-visible");
      clearOverlaySettle();
      document.documentElement.classList.remove("hub-chat-ui-active");
      resetChatOverlayMotionStyles();
      updateMenuContext(false);
      _chatOverlay.classList.add("overlay-closing");
      document.documentElement.classList.add("hub-chat-peeking");
      if (_chatOverlayCloseTimer) clearTimeout(_chatOverlayCloseTimer);
      _chatOverlayCloseTimer = setTimeout(() => {
        _chatOverlayCloseTimer = 0;
        document.documentElement.classList.remove("hub-chat-overlay-active");
        document.body.classList.remove("hub-chat-overlay-active");
        _chatOverlay.classList.remove("overlay-closing");
        resetChatOverlayMotionStyles();
        _chatOverlay.classList.add("overlay-peeking");
        _chatOverlay.style.top = "";
        _chatOverlay.style.height = "";
        _currentChatUrl = "";
        clearPersistedChatFrameState();
      }, CHAT_OVERLAY_CLOSE_MS);
    }
    function openSessionFrame(openHref, name) {
      rememberLastSession(name);
      resetLaunchShellCard();
      const needsReviveTransition = /^\/revive-session(?:[/?]|$)/.test(String(openHref || ""));
      if (needsReviveTransition) showLaunchShell();
      hubChatUrls.resolve(openHref, name, { force: needsReviveTransition })
        .then((chatUrl) => {
          openChatInFrame(chatUrl, name);
          if (needsReviveTransition) {
            if (refreshMobSessions) void refreshMobSessions(true);
          }
        })
        .catch((err) => {
          failHubReadyWait(err?.message || "open session failed");
        });
    }
    window.addEventListener("message", function (e) {
      if (e.data && e.data.type === "chat-render-error" && e.source === _chatFrame.contentWindow) {
        _chatFrameRenderReady = false;
        if (!_awaitingChatRenderReady) {
          return;
        }
        failHubReadyWait(e.data.message || "render failed");
        return;
      }
      if (e.data && e.data.type === "chat-render-ready" && e.source === _chatFrame.contentWindow) {
        _chatFrameRenderReady = true;
        if (!_chatOverlay.hidden) {
          _chatFrame.style.transition = "opacity 140ms ease";
          _chatFrame.style.opacity = "1";
          if (_currentChatUrl) {
            persistChatFrameState(_currentChatUrl, _currentChatSessionName || "");
          }
          finishChatRenderWait();
        }
        return;
      }
      if (e.data === "hub_close_chat") closeChatFrame();
      if (e.data && e.data.type === "toggle-hub-sidebar") {
        closeChatFrame();
        return;
      }
      if (e.data && e.data.type === "open-hub-path") {
        const nextUrl = typeof e.data.url === "string" ? e.data.url : "";
        if (nextUrl) {
          closeChatFrame();
          let sameHubRoot = false;
          try {
            const target = new URL(nextUrl, window.location.href);
            sameHubRoot = target.origin === window.location.origin && target.pathname === "/" && window.location.pathname === "/";
          } catch (_) { }
          if (!sameHubRoot) {
            setTimeout(() => {
              window.location.href = nextUrl;
            }, e.data.reveal ? CHAT_OVERLAY_CLOSE_MS : 0);
          }
        }
        return;
      }
      if (e.data && e.data.type === "chat-scroll-signal" && e.source === _chatFrame.contentWindow) {
        if (_chatOverlay.hidden) return;
        const y = window.scrollY || document.documentElement.scrollTop || 0;
        try {
          window.scrollTo(0, y + 1);
          window.scrollTo(0, y);
        } catch (_) { }
        return;
      }
      if (e.data && e.data.type === "chat-request-hub-layout" && e.source === _chatFrame.contentWindow) {
        _bumpHubChatParentLayoutMax();
        _postHubLayoutToChat();
        return;
      }
      if (e.data && e.data.type === "hub-mobile-system-theme-observed") {
        // Only a live OS-preference change, relayed from the chat iframe's
        // own matchMedia listener -- irrelevant once theme_mobile pins an
        // explicit choice, since publishMobileTheme/resolveMobileTheme
        // would just override it back to that choice regardless.
        const setting = document.documentElement.dataset.themeMobileSetting;
        if (setting === "light" || setting === "dark") return;
        const theme = e.data.theme === "light" ? "light" : (e.data.theme === "dark" ? "dark" : "");
        if (theme) publishMobileTheme(theme);
        return;
      }
      if (e.data && e.data.type === "hub-theme-changed") {
        if (e.data.theme !== "light" && e.data.theme !== "dark") return;
        const theme = e.data.theme;
        document.documentElement.dataset.theme = theme;
        try { _chatFrame.contentDocument.documentElement.dataset.theme = theme; } catch (_) {}
        try { _chatFrame?.contentWindow?.postMessage({ type: "hub-theme-changed", theme }, "*"); } catch (_) {}
        return;
      }
    });
    const pendingHubErrorMessage = consumePendingHubErrorMessage();
    if (pendingHubErrorMessage) {
      clearPersistedChatFrameState();
      failHubReadyWait(pendingHubErrorMessage);
    }
    try {
      const saved = sessionStorage.getItem(HUB_CHAT_FRAME_KEY);
      if (saved && !pendingHubErrorMessage) {
        const { url, name } = JSON.parse(saved);
        if (url) openChatInFrame(url, name);
      }
    } catch (_) { }

    (function () {
      const wrap = document.getElementById("mobListWrap");
      if (!wrap) return;
      let _mobSessionsCache = { active: [], archived: [] };
      let _mobSessionsRequestSeq = 0;
      let _mobSessionsRenderedOnce = false;

      const esc = (v) => String(v || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

      const SNAP_W = 84;
      const THRESH = 48;
      const trashSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>`;
      const killSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>`;
      const reviveSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>`;
      const SWIPE_ACTIONS = {
        kill: { svg: killSvg, label: "Archive" },
        "delete-archived": { svg: trashSvg, label: "Delete" },
        revive: { svg: reviveSvg, label: "Revive" },
      };
      let anyOpen = null;
      const removeSwipeActs = (sr) => {
        sr.querySelectorAll(".swipe-act").forEach((n) => n.remove());
      };
      const closeRow = (sr, animate) => {
        const el = sr && sr.querySelector(".mob-session-row");
        if (!el) return;
        el.style.transition = animate ? "transform 220ms cubic-bezier(.25,.46,.45,.94)" : "none";
        el.style.transform = "";
        sr._snap = 0;
        if (animate) {
          el.addEventListener("transitionend", () => removeSwipeActs(sr), { once: true });
        } else {
          removeSwipeActs(sr);
        }
      };
      const initSwipeRow = (sr) => {
        const inner = sr.querySelector(".mob-session-row");
        if (!inner) return;
        const rightAction = sr.dataset.swipeRight || "";
        const leftAction = sr.dataset.swipeLeft || "";
        const actRDef = SWIPE_ACTIONS[rightAction];
        const actLDef = SWIPE_ACTIONS[leftAction];
        sr._snap = 0;
        let sx = 0, sy = 0, dx = 0, axis = null, active = false, didSwipe = false;
        const minX = actRDef ? -SNAP_W : 0;
        const maxX = actLDef ? SNAP_W : 0;
        const onActClick = (e) => {
          e.stopPropagation();
          const action = e.currentTarget.dataset.action;
          const n = sr.dataset.sessionName;
          if (action === "revive") {
            if (n) openSessionFrame(`/revive-session?session=${encodeURIComponent(n)}`, n);
            return;
          }
          if (action === "delete-archived") {
            if (confirm("Delete archived logs for " + n + "? This cannot be undone.")) {
              window.location.href = `/delete-archived-session?session=${encodeURIComponent(n)}`;
            }
            return;
          }
          if (confirm("Archive " + n + "?")) window.location.href = `/kill-session?session=${encodeURIComponent(n)}`;
        };
        const ensureActs = () => {
          if (actRDef && !sr.querySelector(".swipe-act-right")) {
            const el = document.createElement("div");
            el.className = "swipe-act swipe-act-right";
            el.dataset.action = rightAction;
            el.innerHTML = `${actRDef.svg}<span>${actRDef.label}</span>`;
            el.addEventListener("click", onActClick);
            sr.insertBefore(el, inner);
          }
          if (actLDef && !sr.querySelector(".swipe-act-left")) {
            const el = document.createElement("div");
            el.className = "swipe-act swipe-act-left";
            el.dataset.action = leftAction;
            el.innerHTML = `${actLDef.svg}<span>${actLDef.label}</span>`;
            el.addEventListener("click", onActClick);
            sr.insertBefore(el, inner);
          }
        };
        const startDrag = (clientX, clientY) => {
          if (anyOpen && anyOpen !== sr) { closeRow(anyOpen, true); anyOpen = null; }
          sx = clientX; sy = clientY;
          dx = 0; axis = null; active = true; didSwipe = false;
          inner.style.transition = "none";
        };
        const moveDrag = (clientX, clientY, preventDefault) => {
          if (!active) return;
          const cx = clientX - sx, cy = clientY - sy;
          if (!axis) {
            if (Math.abs(cy) > Math.abs(cx) + 4) { axis = "y"; return; }
            if (Math.abs(cx) > 6) { axis = "x"; ensureActs(); }
          }
          if (axis !== "x") return;
          if (preventDefault) preventDefault();
          didSwipe = true;
          dx = cx;
          const base = (sr._snap || 0) * SNAP_W;
          const x = Math.max(minX, Math.min(maxX, base + dx));
          inner.style.transform = x ? `translateX(${x}px)` : "";
        };
        const endDrag = () => {
          if (!active || axis !== "x") { active = false; return; }
          active = false;
          const base = (sr._snap || 0) * SNAP_W;
          const fx = base + dx;
          const ease = "transform 220ms cubic-bezier(.25,.46,.45,.94)";
          if (fx < -THRESH && actRDef) {
            inner.style.transition = ease; inner.style.transform = `translateX(${-SNAP_W}px)`;
            sr._snap = -1; anyOpen = sr;
          } else if (fx > THRESH && actLDef) {
            inner.style.transition = ease; inner.style.transform = `translateX(${SNAP_W}px)`;
            sr._snap = 1; anyOpen = sr;
          } else {
            inner.style.transition = ease; inner.style.transform = "";
            sr._snap = 0; if (anyOpen === sr) anyOpen = null;
          }
          dx = 0;
          inner.addEventListener("transitionend", () => { if (!sr._snap) removeSwipeActs(sr); }, { once: true });
        };
        inner.addEventListener("touchstart", (e) => startDrag(e.touches[0].clientX, e.touches[0].clientY), { passive: true });
        inner.addEventListener("touchmove", (e) => moveDrag(e.touches[0].clientX, e.touches[0].clientY, () => e.preventDefault()), { passive: false });
        inner.addEventListener("touchend", endDrag, { passive: true });
        inner.addEventListener("mousedown", (e) => {
          if (e.target.closest("a, button")) return;
          e.preventDefault();
          startDrag(e.clientX, e.clientY);
          const onMove = (me) => moveDrag(me.clientX, me.clientY, () => me.preventDefault());
          const onUp = () => { endDrag(); document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); };
          document.addEventListener("mousemove", onMove);
          document.addEventListener("mouseup", onUp);
        });
        inner.addEventListener("click", (e) => {
          if (didSwipe) { didSwipe = false; e.stopPropagation(); return; }
          if (sr._snap !== 0) { closeRow(sr, true); anyOpen = null; e.stopPropagation(); return; }
          if (e.target.closest(".swipe-act")) return;
          const href = inner.dataset.openHref;
          if (href) openSessionFrame(href, sr.dataset.sessionName || "");
        });
      };

      const renderRows = (active, archived) => {
        let html = "";
        if (active.length) {
          html += `<div class="mob-section-label">Active</div>`;
          html += active.map((s) => {
            const preview = s.latest_message_preview ? `<div class="mob-row-preview"><span class="sender">${esc(s.latest_message_sender || "latest")}</span> ${esc(s.latest_message_preview)}</div>` : "";
            return `<div class="swipe-row" data-session-name="${esc(s.name)}" data-swipe-right="kill">` +
              `<div class="mob-session-row" data-session-name="${esc(s.name)}" data-open-href="/open-session?session=${encodeURIComponent(s.name)}" role="link" tabindex="0">` +
              `<div class="mob-row-head">` +
              `<div class="mob-row-name">${esc(s.name)}</div>` +
              `</div>` +
              preview +
              `</div></div>`;
          }).join("");
        }
        if (archived.length) {
          html += `<div class="mob-section-label">Archived</div>`;
          html += archived.map((s) => {
            const preview = s.latest_message_preview ? `<div class="mob-row-preview"><span class="sender">${esc(s.latest_message_sender || "latest")}</span> ${esc(s.latest_message_preview)}</div>` : "";
            return `<div class="swipe-row" data-session-name="${esc(s.name)}" data-swipe-left="revive" data-swipe-right="delete-archived">` +
              `<div class="mob-session-row archived-row" data-session-name="${esc(s.name)}" data-open-href="/open-session?session=${encodeURIComponent(s.name)}" role="link" tabindex="0">` +
              `<div class="mob-row-head">` +
              `<div class="mob-row-name">${esc(s.name)}</div>` +
              `</div>` +
              preview +
              `</div></div>`;
          }).join("");
        }
        if (!active.length && !archived.length) {
          html += `<div class="mob-empty">No sessions found</div>`;
        }
        wrap.innerHTML = html;
        syncMobileSelectedSessionRows();
        wrap.querySelectorAll(".swipe-row").forEach(initSwipeRow);
      };
      const refresh = async (force) => {
        const requestSeq = ++_mobSessionsRequestSeq;
        try {
          const res = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
          if (!res.ok) throw new Error("failed");
          const data = await res.json();
          if (requestSeq !== _mobSessionsRequestSeq) return;
          const activeSessions = data.active_sessions;
          const archivedSessions = data.archived_sessions;
          _mobSessionsCache = { active: activeSessions, archived: archivedSessions };

          const sig = JSON.stringify({
            active: activeSessions,
            archived: archivedSessions,
          });
          if (!force && window._lastMobRenderSig === sig) {
            _mobSessionsRenderedOnce = true;
            releaseHubLaunchShellAfterRender();
            return;
          }
          window._lastMobRenderSig = sig;

          renderRows(activeSessions, archivedSessions);
          _mobSessionsRenderedOnce = true;
          releaseHubLaunchShellAfterRender();
        } catch (_) {
          if (requestSeq !== _mobSessionsRequestSeq) return;
          if (_mobSessionsRenderedOnce || _mobSessionsCache.active.length || _mobSessionsCache.archived.length) return;
          wrap.innerHTML = `<div class="mob-empty">Failed to load sessions</div>`;
          if (_hubLaunchShellPending) failHubReadyWait("Failed to load sessions");
        }
      };
      refreshMobSessions = refresh;
      startHubSessionMessagesEvents(() => refresh(true));
      refresh();
    })();

    (function () {
      var bridge = document.getElementById("pageNativeMenuBridge");
      if (bridge) {
        bridge.addEventListener("change", function (e) {
          var val = bridge.value;
          if (!val) return;
          if (val === "close-session" || val === "hub") {
            e.stopImmediatePropagation();
            bridge.value = "";
            closeChatFrame();
          }
        });
      }
    })();


    __HUB_HEADER_JS__
