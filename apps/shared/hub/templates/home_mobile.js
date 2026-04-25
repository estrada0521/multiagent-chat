    // ── Chat iframe overlay ──
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
    let _prewarmedSessionName = "";
    let _prewarmedChatUrl = "";
    let _prewarmedFrameReady = false;
    let _prewarmedFrameRenderReady = false;
    let _prewarmToken = 0;
    let _hubLaunchShellPending = false;
    let _hubLaunchShellFallbackTimer = 0;
    let _awaitingChatRenderReady = false;
    let _chatRenderReadyFallbackTimer = 0;
    let _chatOverlayCloseTimer = 0;
    const _chatUrlCache = new Map();
    const _chatUrlInflight = new Map();
    const HUB_CHAT_FRAME_KEY = "hub_chat_frame";
    const HUB_LAST_SESSION_KEY = "multiagent_hub_last_session_name";
    const HUB_PENDING_ERROR_KEY = "multiagent_hub_pending_error";
    const HUB_CHAT_URL_CACHE_TTL_MS = 180000;
    const HUB_CHAT_URL_CACHE_LIMIT = 3;
    const HUB_ACTIVE_PREWARM_LIMIT = 3;
    const HUB_LAUNCH_SHELL_PARAM = "launch_shell";
    const HUB_LAUNCH_SHELL_FALLBACK_MS = 5000;
    const CHAT_RENDER_READY_FALLBACK_MS = 2600;
    const CHAT_OVERLAY_CLOSE_MS = 340;
    function resetChatOverlayMotionStyles() {
      _chatOverlay.style.transform = "";
      _chatOverlay.style.transition = "";
      _chatOverlay.style.opacity = "";
    }
    function showLaunchShell() {
      if (!_launchShell) return;
      _launchShell.hidden = false;
      _launchShell.classList.add("visible");
    }
    function hideLaunchShell() {
      if (!_launchShell) return;
      _launchShell.classList.remove("visible");
      _launchShell.hidden = true;
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
      if (_hubLaunchShellFallbackTimer) {
        clearTimeout(_hubLaunchShellFallbackTimer);
        _hubLaunchShellFallbackTimer = 0;
      }
      clearLaunchShellQueryFlag();
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (!_awaitingChatRenderReady) hideLaunchShell();
        });
      });
    }
    function startChatRenderWait() {
      _awaitingChatRenderReady = true;
      if (_chatRenderReadyFallbackTimer) clearTimeout(_chatRenderReadyFallbackTimer);
      _chatRenderReadyFallbackTimer = setTimeout(() => {
        _awaitingChatRenderReady = false;
        _chatRenderReadyFallbackTimer = 0;
        if (!_hubLaunchShellPending) hideLaunchShell();
      }, CHAT_RENDER_READY_FALLBACK_MS);
    }
    function finishChatRenderWait() {
      if (!_awaitingChatRenderReady) return;
      _awaitingChatRenderReady = false;
      if (_chatRenderReadyFallbackTimer) {
        clearTimeout(_chatRenderReadyFallbackTimer);
        _chatRenderReadyFallbackTimer = 0;
      }
      if (!_hubLaunchShellPending) hideLaunchShell();
    }
    function cancelChatRenderWait() {
      _awaitingChatRenderReady = false;
      if (_chatRenderReadyFallbackTimer) {
        clearTimeout(_chatRenderReadyFallbackTimer);
        _chatRenderReadyFallbackTimer = 0;
      }
    }
    const _launchShellParams = new URLSearchParams(window.location.search || "");
    _hubLaunchShellPending = _launchShellParams.get(HUB_LAUNCH_SHELL_PARAM) === "1";
    if (_hubLaunchShellPending) {
      showLaunchShell();
      _hubLaunchShellFallbackTimer = setTimeout(() => {
        if (!_hubLaunchShellPending || _awaitingChatRenderReady) return;
        _hubLaunchShellPending = false;
        _hubLaunchShellFallbackTimer = 0;
        clearLaunchShellQueryFlag();
        hideLaunchShell();
      }, HUB_LAUNCH_SHELL_FALLBACK_MS);
    }
    function rememberLastSession(name) {
      const normalized = String(name || "").trim();
      if (!normalized) return;
      try { sessionStorage.setItem(HUB_LAST_SESSION_KEY, normalized); } catch (_) { }
    }
    function lastRememberedSession() {
      try { return (sessionStorage.getItem(HUB_LAST_SESSION_KEY) || "").trim(); } catch (_) { return ""; }
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
    function chatUrlCacheKey(openHref, name) {
      const normalizedName = String(name || "").trim();
      if (normalizedName) return normalizedName;
      return String(openHref || "").trim();
    }
    function cacheChatUrl(name, url) {
      const normalizedName = String(name || "").trim();
      const normalizedUrl = String(url || "").trim();
      if (!normalizedName || !normalizedUrl) return;
      if (_chatUrlCache.has(normalizedName)) _chatUrlCache.delete(normalizedName);
      _chatUrlCache.set(normalizedName, { url: normalizedUrl, ts: Date.now() });
      while (_chatUrlCache.size > HUB_CHAT_URL_CACHE_LIMIT) {
        const oldest = _chatUrlCache.keys().next();
        if (oldest && !oldest.done) _chatUrlCache.delete(oldest.value);
        else break;
      }
    }
    function cachedChatUrl(name) {
      const normalizedName = String(name || "").trim();
      if (!normalizedName) return "";
      const item = _chatUrlCache.get(normalizedName);
      if (!item) return "";
      if ((Date.now() - Number(item.ts || 0)) > HUB_CHAT_URL_CACHE_TTL_MS) {
        _chatUrlCache.delete(normalizedName);
        return "";
      }
      const cachedUrl = String(item.url || "").trim();
      if (cachedUrl) cacheChatUrl(normalizedName, cachedUrl);
      return cachedUrl;
    }
    function setPrewarmingOverlayActive(active) {
      _chatOverlay.classList.toggle("prewarming", !!active);
      if (active) {
        _chatOverlay.classList.remove("overlay-visible", "overlay-closing");
        resetChatOverlayMotionStyles();
        _chatOverlay.hidden = false;
      } else {
        _chatOverlay.classList.remove("prewarming", "overlay-closing");
        resetChatOverlayMotionStyles();
      }
    }
    function primeChatFrame(sessionName, chatUrl) {
      if (!shouldUseChatOverlay()) return;
      const normalizedName = String(sessionName || "").trim();
      const normalizedUrl = String(chatUrl || "").trim();
      if (!normalizedName || !normalizedUrl) return;
      const reusingSameSrc = _chatFrame.src === normalizedUrl;
      _prewarmedSessionName = normalizedName;
      _prewarmedChatUrl = normalizedUrl;
      if (!reusingSameSrc) {
        _prewarmedFrameReady = false;
        _prewarmedFrameRenderReady = false;
      }
      setPrewarmingOverlayActive(true);
      _chatFrame.onload = function () {
        _prewarmedFrameReady = true;
      };
      if (!reusingSameSrc) {
        _chatFrame.style.transition = "none";
        _chatFrame.style.opacity = "0";
        _chatFrame.src = normalizedUrl;
      } else {
        _prewarmedFrameReady = true;
      }
    }
    async function resolveChatUrl(openHref, name, { force = false, prewarm = false } = {}) {
      const normalizedName = String(name || "").trim();
      const cacheKey = chatUrlCacheKey(openHref, normalizedName);
      if (!force && normalizedName) {
        const cached = cachedChatUrl(normalizedName);
        if (cached) {
          if (prewarm) primeChatFrame(normalizedName, cached);
          return cached;
        }
      }
      const inflight = !force && cacheKey ? _chatUrlInflight.get(cacheKey) : null;
      if (inflight) {
        return inflight.then((chatUrl) => {
          if (prewarm && chatUrl && normalizedName) primeChatFrame(normalizedName, chatUrl);
          return chatUrl;
        });
      }
      const url = openHref + (openHref.includes("?") ? "&" : "?") + "format=json";
      const request = fetch(url, { cache: "no-store" })
        .then(async (res) => {
          const data = await res.json();
          const chatUrl = String((data && data.chat_url) || "").trim();
          if (chatUrl && normalizedName) {
            cacheChatUrl(normalizedName, chatUrl);
          }
          return chatUrl;
        })
        .finally(() => {
          if (cacheKey) _chatUrlInflight.delete(cacheKey);
        });
      if (!force && cacheKey) {
        _chatUrlInflight.set(cacheKey, request);
      }
      return request.then((chatUrl) => {
        if (prewarm && chatUrl && normalizedName) primeChatFrame(normalizedName, chatUrl);
        return chatUrl;
      });
    }
    function activeWarmCandidates(activeSessions) {
      return (activeSessions || [])
        .filter((session) => String(session?.status || "").toLowerCase() !== "pending")
        .filter((session) => String(session?.name || "").trim());
    }
    function choosePrewarmSession(activeSessions) {
      const active = activeWarmCandidates(activeSessions);
      if (!active.length) return null;
      const remembered = lastRememberedSession();
      return active.find((session) => String(session?.name || "") === remembered) || active[0];
    }
    function scheduleActiveSessionPrewarm(activeSessions) {
      if (_chatOverlay && !_chatOverlay.hidden && !_chatOverlay.classList.contains("prewarming")) return;
      const token = ++_prewarmToken;
      const active = activeWarmCandidates(activeSessions).slice(0, HUB_ACTIVE_PREWARM_LIMIT);
      if (!active.length) return;
      const primary = choosePrewarmSession(active) || active[0];
      const primaryName = String(primary?.name || "").trim();
      const orderedActive = [
        primary,
        ...active.filter((session) => String(session?.name || "").trim() !== primaryName),
      ];
      orderedActive.forEach((session, index) => {
        const sessionName = String(session?.name || "").trim();
        if (!sessionName) return;
        const openHref = `/open-session?session=${encodeURIComponent(sessionName)}`;
        const shouldPrimeFrame = index === 0;
        const runWarm = () => {
          if (token !== _prewarmToken) return;
          resolveChatUrl(openHref, sessionName, { prewarm: shouldPrimeFrame }).catch(() => {
            if (token !== _prewarmToken) return;
          });
        };
        const delayMs = shouldPrimeFrame ? 0 : Math.min(2500, index * 180);
        if (delayMs <= 0) runWarm();
        else setTimeout(runWarm, delayMs);
      });
    }
    function kickstartRememberedSessionPrewarm() {
      if (_chatOverlay && !_chatOverlay.hidden && !_chatOverlay.classList.contains("prewarming")) return;
      const sessionName = lastRememberedSession();
      if (!sessionName) return;
      const token = ++_prewarmToken;
      const openHref = `/open-session?session=${encodeURIComponent(sessionName)}`;
      resolveChatUrl(openHref, sessionName, { prewarm: true }).catch(() => {
        if (token !== _prewarmToken) return;
      });
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
            type: "multiagent-hub-layout",
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
      // 以前は visualViewport に合わせて #chatOverlay の top/height を縮めていた。
      // その結果 iframe 内の window.innerHeight / 100vh も「キーボード上の帯」だけになり、
      // チャットの .composer-overlay（flex 中央）が「画面全体の中央」ではなく
      // 「押し上げ後の領域の中央」に寄る。Public（トップレベル）との差の主因だった。
      // オーバーレイは CSS の position:fixed; inset:0 のままフルレイアウト高さを維持する。
      _chatOverlay.style.top = "";
      _chatOverlay.style.height = "";
    }
    function shouldUseChatOverlay() {
      return true;
    }
    function ensureChatLaunchShellFlag(rawUrl) {
      const target = String(rawUrl || "").trim();
      if (!target) return "";
      try {
        const next = new URL(target, window.location.origin);
        if (next.origin !== window.location.origin) return target;
        if (!next.searchParams.has("launch_shell")) next.searchParams.set("launch_shell", "1");
        return next.pathname + next.search + next.hash;
      } catch (_) {
        return target;
      }
    }
    function navigateWithLaunchShell(url) {
      const target = ensureChatLaunchShellFlag(url);
      if (!target) return;
      showLaunchShell();
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          window.location.href = target;
        });
      });
    }
    function updateMenuContext(isChat) {
      const bridge = document.getElementById("hubPageNativeMenuBridge");
      if (!bridge) return;
      if (isChat) {
        bridge.innerHTML = `
          <option value="" disabled selected>Menu</option>
          <option value="close-session">Close Session</option>
          <option value="settings">Settings</option>
          <option value="restart-hub">Reload</option>
        `;
      } else {
        bridge.innerHTML = `
          <option value="" disabled selected>Menu</option>
          <option value="new-session">New Session</option>
          <option value="settings">Settings</option>
          <option value="restart-hub">Reload</option>
        `;
      }
    }
    function openChatInFrame(url, name) {
      if (_chatOverlayCloseTimer) {
        clearTimeout(_chatOverlayCloseTimer);
        _chatOverlayCloseTimer = 0;
      }
      rememberLastSession(name);
      const useOverlay = shouldUseChatOverlay();
      if (!useOverlay) {
        showLaunchShell();
        startChatRenderWait();
        navigateWithLaunchShell(url);
        return;
      }
      if (_hubLaunchShellPending) showLaunchShell();
      startChatRenderWait();
      const normalizedName = String(name || "").trim();
      const normalizedUrl = String(url || "").trim();
      cacheChatUrl(normalizedName, normalizedUrl);
      clearPersistedChatFrameState();
      _currentChatUrl = normalizedUrl;
      _hubMinParentChromeGap = Infinity;
      _hubLayoutRefW = window.innerWidth || 0;
      _hubLayoutRefH = window.innerHeight || 0;
      _hubChatParentLayoutMax = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
      const onChatReady = function () {
        _prewarmedSessionName = normalizedName;
        _prewarmedChatUrl = normalizedUrl;
        _prewarmedFrameReady = true;
        _chatFrame.style.transition = "opacity 140ms ease";
        _chatFrame.style.opacity = "1";
        _bumpHubChatParentLayoutMax();
        _postHubLayoutToChat();
        if (_prewarmedFrameRenderReady) {
          persistChatFrameState(normalizedUrl, normalizedName);
          finishChatRenderWait();
        }
      };
      const canReusePrewarm =
        normalizedName &&
        _prewarmedSessionName === normalizedName &&
        _prewarmedChatUrl === normalizedUrl &&
        _chatFrame.src === normalizedUrl;
      if (!canReusePrewarm) {
        _chatFrame.style.transition = "none";
        _chatFrame.style.opacity = "0";
      } else {
        _chatFrame.style.opacity = "1";
      }
      _chatFrame.onload = onChatReady;
      _attachHubViewportBridge();
      updateMenuContext(true);
      _hubPreOverlayScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.documentElement.classList.add("hub-chat-overlay-active");
      document.body.classList.add("hub-chat-overlay-active");
      setPrewarmingOverlayActive(false);
      _chatOverlay.classList.remove("overlay-visible", "overlay-closing");
      resetChatOverlayMotionStyles();
      _chatOverlay.hidden = false;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (_chatOverlay.hidden || _chatOverlay.classList.contains("prewarming")) return;
          _chatOverlay.classList.add("overlay-visible");
          document.documentElement.classList.add("hub-chat-ui-active");
        });
      });
      _currentChatSessionName = normalizedName;
      if (!canReusePrewarm) {
        _prewarmedFrameReady = false;
        _prewarmedFrameRenderReady = false;
        _chatFrame.src = normalizedUrl;
      } else if (_prewarmedFrameReady) {
        requestAnimationFrame(onChatReady);
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
      document.documentElement.classList.remove("hub-chat-ui-active");
      resetChatOverlayMotionStyles();
      updateMenuContext(false);
      _chatOverlay.classList.add("overlay-closing");
      if (_chatOverlayCloseTimer) clearTimeout(_chatOverlayCloseTimer);
      _chatOverlayCloseTimer = setTimeout(() => {
        _chatOverlayCloseTimer = 0;
        document.documentElement.classList.remove("hub-chat-overlay-active");
        document.body.classList.remove("hub-chat-overlay-active");
        _chatOverlay.classList.remove("overlay-closing");
        resetChatOverlayMotionStyles();
        if (shouldUseChatOverlay() && _currentChatSessionName && _prewarmedChatUrl && _chatFrame.src === _prewarmedChatUrl) {
          setPrewarmingOverlayActive(true);
        } else {
          _chatOverlay.hidden = true;
          _chatFrame.src = "about:blank";
        }
        _chatOverlay.style.top = "";
        _chatOverlay.style.height = "";
        _currentChatUrl = "";
        clearPersistedChatFrameState();
      }, CHAT_OVERLAY_CLOSE_MS);
    }
    // ── Hub Logo Click Handler ──
    const hubLogoBtn = document.getElementById("hubPageTitleLink");
    function openRememberedSessionFromHub() {
      const remembered = lastRememberedSession();
      if (!remembered) return false;
      openSessionFrame(`/open-session?session=${encodeURIComponent(remembered)}`, remembered);
      return true;
    }
    if (hubLogoBtn) {
      hubLogoBtn.addEventListener("click", (event) => {
        if (document.documentElement.classList.contains("hub-chat-ui-active")) {
          event.preventDefault();
          closeChatFrame();
          return;
        }
        if (openRememberedSessionFromHub()) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      });
    }

    function openSessionFrame(openHref, name, options = {}) {
      rememberLastSession(name);
      const shouldShowTransition = !!options.showTransition || /^\/revive-session(?:[/?]|$)/.test(String(openHref || ""));
      if (shouldShowTransition) showLaunchShell();
      if (!shouldUseChatOverlay()) {
        showLaunchShell();
        const cached = cachedChatUrl(name);
        if (cached) {
          navigateWithLaunchShell(cached);
          return;
        }
        resolveChatUrl(openHref, name)
          .then((chatUrl) => {
            if (chatUrl) navigateWithLaunchShell(chatUrl);
            else if (name && openHref.startsWith("/open-session")) navigateWithLaunchShell(`/session/${encodeURIComponent(name)}/?follow=1&ts=${Date.now()}`);
            else navigateWithLaunchShell(openHref);
          })
          .catch(() => {
            if (name && openHref.startsWith("/open-session")) navigateWithLaunchShell(`/session/${encodeURIComponent(name)}/?follow=1&ts=${Date.now()}`);
            else navigateWithLaunchShell(openHref);
          });
        return;
      }
      resolveChatUrl(openHref, name)
        .then((chatUrl) => {
          if (chatUrl) {
            openChatInFrame(chatUrl, name);
            return;
          }
          if (shouldShowTransition) {
            navigateWithLaunchShell(openHref);
          } else {
            window.location.href = openHref;
          }
        })
        .catch(() => {
          if (shouldShowTransition) {
            navigateWithLaunchShell(openHref);
          } else {
            window.location.href = openHref;
          }
        });
    }
    window.addEventListener("message", function (e) {
      if (e.data && e.data.type === "multiagent-chat-render-ready" && e.source === _chatFrame.contentWindow) {
        _prewarmedFrameRenderReady = true;
        if (!_chatOverlay.hidden && !_chatOverlay.classList.contains("prewarming")) {
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
      if (e.data && e.data.type === "multiagent-toggle-hub-sidebar") {
        closeChatFrame();
        return;
      }
      if (e.data && e.data.type === "multiagent-open-hub-path") {
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
      if (e.data && e.data.type === "multiagent-chat-scroll-signal" && e.source === _chatFrame.contentWindow) {
        if (_chatOverlay.hidden) return;
        const y = window.scrollY || document.documentElement.scrollTop || 0;
        try {
          window.scrollTo(0, y + 1);
          window.scrollTo(0, y);
        } catch (_) { }
        return;
      }
      if (e.data && e.data.type === "multiagent-chat-request-hub-layout" && e.source === _chatFrame.contentWindow) {
        _bumpHubChatParentLayoutMax();
        _postHubLayoutToChat();
      }
    });
    // Restore active chat on PWA re-launch
    const pendingHubErrorMessage = consumePendingHubErrorMessage();
    if (pendingHubErrorMessage) {
      clearPersistedChatFrameState();
    }
    try {
      const saved = sessionStorage.getItem(HUB_CHAT_FRAME_KEY);
      if (!shouldUseChatOverlay()) {
        sessionStorage.removeItem(HUB_CHAT_FRAME_KEY);
      } else if (saved) {
        const { url, name } = JSON.parse(saved);
        if (url) openChatInFrame(url, name);
      }
    } catch (_) { }

    // --- Mobile session list ---
    (function () {
      const wrap = document.getElementById("mobListWrap");
      if (!wrap) return;
      let _mobSessionsCache = { active: [], archived: [] };
      let _mobSessionsRequestSeq = 0;
      let _mobSessionsRenderedOnce = false;
      let _mobSessionsColdFailures = 0;

      const esc = (v) => String(v || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

      // ── Swipe logic ──
      const SNAP_W = 84;
      const THRESH = 48;
      let anyOpen = null;
      const closeRow = (sr, animate) => {
        const el = sr && sr.querySelector(".mob-session-row");
        if (!el) return;
        el.style.transition = animate ? "transform 220ms cubic-bezier(.25,.46,.45,.94)" : "none";
        el.style.transform = "";
        sr._snap = 0;
      };
      const initSwipeRow = (sr) => {
        const inner = sr.querySelector(".mob-session-row");
        const actR = sr.querySelector(".swipe-act-right");
        if (!inner) return;
        sr._snap = 0;
        let sx = 0, sy = 0, dx = 0, axis = null, active = false, didSwipe = false;
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
            if (Math.abs(cx) > 6) axis = "x";
          }
          if (axis !== "x") return;
          if (preventDefault) preventDefault();
          didSwipe = true;
          dx = cx;
          const base = (sr._snap || 0) * SNAP_W;
          let x = Math.max(-SNAP_W, Math.min(0, base + dx));
          if (!actR && x < 0) x = 0;
          inner.style.transform = x ? `translateX(${x}px)` : "";
        };
        const endDrag = () => {
          if (!active || axis !== "x") { active = false; return; }
          active = false;
          const base = (sr._snap || 0) * SNAP_W;
          const fx = base + dx;
          const ease = "transform 220ms cubic-bezier(.25,.46,.45,.94)";
          if (fx < -THRESH && actR) {
            inner.style.transition = ease; inner.style.transform = `translateX(${-SNAP_W}px)`;
            sr._snap = -1; anyOpen = sr;
          } else {
            inner.style.transition = ease; inner.style.transform = "";
            sr._snap = 0; if (anyOpen === sr) anyOpen = null;
          }
          dx = 0;
        };
        // Touch events
        inner.addEventListener("touchstart", (e) => startDrag(e.touches[0].clientX, e.touches[0].clientY), { passive: true });
        inner.addEventListener("touchmove", (e) => moveDrag(e.touches[0].clientX, e.touches[0].clientY, () => e.preventDefault()), { passive: false });
        inner.addEventListener("touchend", endDrag, { passive: true });
        // Mouse events (PC swipe)
        inner.addEventListener("mousedown", (e) => {
          if (e.target.closest("a, button")) return;
          e.preventDefault();
          startDrag(e.clientX, e.clientY);
          const onMove = (me) => moveDrag(me.clientX, me.clientY, () => me.preventDefault());
          const onUp = () => { endDrag(); document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); };
          document.addEventListener("mousemove", onMove);
          document.addEventListener("mouseup", onUp);
        });
        if (actR) actR.addEventListener("click", (e) => {
          e.stopPropagation();
          const n = sr.dataset.sessionName;
          const action = actR.dataset.action;
          if (action === "delete-archived") {
            if (confirm("Delete archived logs for " + n + "? This cannot be undone.")) {
              window.location.href = `/delete-archived-session?session=${encodeURIComponent(n)}`;
            }
            return;
          }
          if (confirm("Kill " + n + "?")) window.location.href = `/kill-session?session=${encodeURIComponent(n)}`;
        });
        // tap/click on row body navigates (unless swipe was happening)
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
        const trashSvg = `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>`;
        if (active.length) {
          html += `<div class="mob-section-label">Active</div>`;
          html += active.map((s) => {
            const preview = s.latest_message_preview ? `<div class="mob-row-preview"><span class="sender">${esc(s.latest_message_sender || "latest")}</span> ${esc(s.latest_message_preview)}</div>` : "";
            return `<div class="swipe-row" data-session-name="${esc(s.name)}">` +
              `<div class="swipe-act swipe-act-right" data-action="kill">${trashSvg}<span>Kill</span></div>` +
              `<div class="mob-session-row" data-open-href="/open-session?session=${encodeURIComponent(s.name)}" role="link" tabindex="0">` +
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
            return `<div class="swipe-row" data-session-name="${esc(s.name)}">` +
              `<div class="swipe-act swipe-act-right" data-action="delete-archived">${trashSvg}<span>Delete</span></div>` +
              `<div class="mob-session-row archived-row" data-open-href="/revive-session?session=${encodeURIComponent(s.name)}" role="link" tabindex="0">` +
              `<div class="mob-row-head">` +
              `<div class="mob-row-name">${esc(s.name)}</div>` +
              `</div>` +
              preview +
              `</div></div>`;
          }).join("");
        }
        if (!active.length && !archived.length) {
          html = `<div class="mob-empty">No sessions found</div>`;
        }
        wrap.innerHTML = html;
        wrap.querySelectorAll(".swipe-row").forEach(initSwipeRow);
      };
      const refresh = async (force) => {
        const requestSeq = ++_mobSessionsRequestSeq;
        try {
          const res = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
          if (!res.ok) throw new Error("failed");
          const data = await res.json();
          if (requestSeq !== _mobSessionsRequestSeq) return;
          const activeSessions = data.active_sessions || data.sessions || [];
          const archivedSessions = data.archived_sessions || [];
          _mobSessionsCache = { active: activeSessions, archived: archivedSessions };
          _mobSessionsColdFailures = 0;

          // Prevent layout thrashing and animation re-triggering if data hasn't changed
          const sig = JSON.stringify({
            active: activeSessions,
            archived: archivedSessions,
          });
          if (!force && window._lastMobRenderSig === sig) {
            _mobSessionsRenderedOnce = true;
            scheduleActiveSessionPrewarm(activeSessions);
            releaseHubLaunchShellAfterRender();
            return;
          }
          window._lastMobRenderSig = sig;

          renderRows(activeSessions, archivedSessions);
          _mobSessionsRenderedOnce = true;
          scheduleActiveSessionPrewarm(activeSessions);
          releaseHubLaunchShellAfterRender();
        } catch (_) {
          if (requestSeq !== _mobSessionsRequestSeq) return;
          if (_mobSessionsRenderedOnce || _mobSessionsCache.active.length || _mobSessionsCache.archived.length) return;
          _mobSessionsColdFailures += 1;
          if (_mobSessionsColdFailures < 2) return;
          wrap.innerHTML = `<div class="mob-empty">Failed to load sessions</div>`;
        }
      };
      kickstartRememberedSessionPrewarm();
      window._mobRefresh = refresh;
      refresh();
      setInterval(refresh, 5000);
    })();

    // ── Bottom sheet (New Session / Settings) ──
    (function () {
      var sheet = document.getElementById("mobSheet");
      var sheetFrame = document.getElementById("mobSheetFrame");
      var sheetPanel = document.getElementById("mobSheetPanel");
      var sheetNav = document.getElementById("mobSheetNav");
      var sheetTitle = document.getElementById("mobSheetTitle");
      var sheetClose = document.getElementById("mobSheetClose");
      if (!sheet || !sheetFrame || !sheetPanel) return;

      var _sheetCloseTimer = 0;
      var _sheetIsNewSession = false;
      var _sheetFrameLoadToken = 0;
      var _sheetOpeningChat = false;
      var _sheetScrollY = 0;
      var _sheetScrollLocked = false;
      // Color constant
      var DARK_BG = "__DARK_BG__";
      var _sheetBlankDoc = `<!doctype html><html><head><meta name='color-scheme' content='dark'><style>html,body{margin:0;min-height:100%;background:${DARK_BG};color-scheme:dark}</style></head><body></body></html>`;

      function lockSheetScroll() {
        if (_sheetScrollLocked) return;
        _sheetScrollLocked = true;
        _sheetScrollY = window.scrollY || document.documentElement.scrollTop || 0;
        document.documentElement.classList.add("mob-sheet-active");
        document.body.classList.add("mob-sheet-active");
        document.body.style.top = "-" + _sheetScrollY + "px";
      }

      function unlockSheetScroll() {
        if (!_sheetScrollLocked) return;
        _sheetScrollLocked = false;
        document.documentElement.classList.remove("mob-sheet-active");
        document.body.classList.remove("mob-sheet-active");
        document.body.style.top = "";
        try { window.scrollTo(0, _sheetScrollY || 0); } catch (_) { }
      }

      function openSheet(url, isNewSession, title) {
        _sheetIsNewSession = !!isNewSession;
        if (sheetTitle) sheetTitle.textContent = title || "";
        if (_sheetCloseTimer) { clearTimeout(_sheetCloseTimer); _sheetCloseTimer = 0; }
        var loadToken = ++_sheetFrameLoadToken;
        sheetFrame.classList.remove("sheet-frame-ready");
        sheetFrame.onload = function () {
          if (loadToken !== _sheetFrameLoadToken) return;
          requestAnimationFrame(function () {
            if (loadToken === _sheetFrameLoadToken) sheetFrame.classList.add("sheet-frame-ready");
          });
        };
        sheetFrame.removeAttribute("srcdoc");
        sheetFrame.src = url;
        lockSheetScroll();
        sheet.hidden = false;
        sheet.classList.remove("sheet-closing");
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            sheet.classList.add("sheet-open");
          });
        });
      }

      function finishSheetClose(refreshSessionList) {
        var wasNewSession = _sheetIsNewSession;
        _sheetIsNewSession = false;
        sheet.classList.remove("sheet-closing");
        sheet.hidden = true;
        _sheetFrameLoadToken++;
        sheetFrame.onload = null;
        sheetFrame.classList.remove("sheet-frame-ready");
        sheetFrame.removeAttribute("src");
        sheetFrame.srcdoc = _sheetBlankDoc;
        unlockSheetScroll();
        if (wasNewSession && refreshSessionList !== false && window._mobRefresh) {
          window._lastMobRenderSig = null;
          window._mobRefresh(true);
        }
      }

      function closeSheet(options) {
        options = options || {};
        const immediate = options.immediate === true;
        const refreshSessionList = options.refreshSessionList !== false;
        if (_sheetCloseTimer) {
          clearTimeout(_sheetCloseTimer);
          _sheetCloseTimer = 0;
        }
        if (immediate) {
          sheet.classList.remove("sheet-open", "sheet-closing");
          finishSheetClose(refreshSessionList);
          return;
        }
        sheet.classList.remove("sheet-open");
        sheet.classList.add("sheet-closing");
        _sheetCloseTimer = setTimeout(function () {
          _sheetCloseTimer = 0;
          finishSheetClose(refreshSessionList);
        }, 300);
      }

      window._openMobSheet = openSheet;
      window._closeMobSheet = closeSheet;

      // Backdrop tap closes sheet
      sheet.addEventListener("click", function (e) {
        if (e.target === sheet) closeSheet();
      });

      // ✕ button closes sheet
      if (sheetClose) sheetClose.addEventListener("click", closeSheet);

      // Drag on nav bar to dismiss
      if (sheetNav) {
        var _startY = 0, _dy = 0, _dragging = false;
        sheetNav.addEventListener("touchstart", function (e) {
          _startY = e.touches[0].clientY; _dy = 0; _dragging = true;
          sheetPanel.style.transition = "none";
        }, { passive: true });
        sheetNav.addEventListener("touchmove", function (e) {
          if (!_dragging) return;
          _dy = Math.max(0, e.touches[0].clientY - _startY);
          sheetPanel.style.transform = "translateY(" + _dy + "px)";
        }, { passive: true });
        sheetNav.addEventListener("touchend", function () {
          if (!_dragging) return;
          _dragging = false;
          sheetPanel.style.transition = "";
          sheetPanel.style.transform = "";
          if (_dy > 80) closeSheet();
        }, { passive: true });
      }

      // postMessage from iframe
      window.addEventListener("message", function (e) {
        if (!sheetFrame || e.source !== sheetFrame.contentWindow) return;
        if (e.data && e.data.type === "multiagent-hub-close-sidebar-page") closeSheet();
        if (e.data === "hub_close_chat") closeSheet();
        if (e.data && e.data.type === "multiagent-hub-open-chat-session") {
          if (_sheetOpeningChat) return;
          _sheetOpeningChat = true;
          var chatUrl = typeof e.data.chatUrl === "string" ? e.data.chatUrl : "";
          var sessionName = typeof e.data.sessionName === "string" ? e.data.sessionName : "";
          closeSheet({ immediate: true, refreshSessionList: false });
          if (chatUrl) {
            requestAnimationFrame(function () {
              _sheetOpeningChat = false;
              openChatInFrame(chatUrl, sessionName);
            });
          } else {
            _sheetOpeningChat = false;
          }
        }
      });

      // Intercept native bridge: new-session / settings → bottom sheet
      var bridge = document.getElementById("hubPageNativeMenuBridge");
      if (bridge) {
        bridge.addEventListener("change", function (e) {
          var val = bridge.value;
          if (!val) return;
          if (val === "new-session") {
            e.stopImmediatePropagation();
            bridge.value = "";
            openSheet("/new-session?embed=1&view=mobile", true, "New Session");
          } else if (val === "settings") {
            e.stopImmediatePropagation();
            bridge.value = "";
            openSheet("/settings?embed=1&view=mobile", false, "Settings");
          } else if (val === "close-session" || val === "hub") {
            e.stopImmediatePropagation();
            bridge.value = "";
            closeChatFrame();
          }
        });
      }
    })();

    // ── Hub scroll-to-hide logic ──
    (function () {
      const header = document.querySelector(".hub-page-header");
      let prevScrollTop = 0;
      let scrollUpAccum = 0;
      const HIDE_THRESHOLD = 50;
      const SCROLL_UP_REVEAL_PX = 56;

      window.addEventListener("scroll", () => {
        // Skip if a sheet or chat overlay is open
        if (document.documentElement.classList.contains("mob-sheet-active")) return;
        if (!_chatOverlay.hidden && !_chatOverlay.classList.contains("prewarming")) return;

        const st = window.scrollY || document.documentElement.scrollTop || 0;
        const delta = st - prevScrollTop;
        const goingDown = delta > 0;
        const goingUp = delta < 0;

        if (goingUp) scrollUpAccum += -delta;
        else scrollUpAccum = 0;

        const isAtTop = st <= HIDE_THRESHOLD;

        if (goingDown && st > HIDE_THRESHOLD) {
          if (header) header.classList.add("header-hidden");
        } else if (isAtTop || scrollUpAccum >= SCROLL_UP_REVEAL_PX) {
          if (header) {
            header.classList.remove("header-hidden");
            scrollUpAccum = 0;
          }
        }
        prevScrollTop = st;
      }, { passive: true });
    })();

    __HUB_HEADER_JS__
