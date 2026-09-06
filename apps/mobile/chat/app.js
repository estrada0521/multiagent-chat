__CHAT_INCLUDE:../../shared/chat/base.js__
    document.documentElement.dataset.mobile = "1";
    const _safariSafeAreaDummy = document.createElement("div");
    _safariSafeAreaDummy.style.cssText = "position:absolute;bottom:0;width:100%;height:env(safe-area-inset-bottom);pointer-events:none;opacity:0;z-index:-1;";
    document.body.appendChild(_safariSafeAreaDummy);
    const applyMobileThemeGradientVars = () => {
      const root = document.documentElement;
      const sheetChannels = getComputedStyle(root).getPropertyValue("--bg-rgb").trim() || (
        root.dataset.theme === "light" ? "249, 249, 247" : "13, 13, 12"
      );
      const topChannels = root.dataset.theme === "light" ? "255, 255, 255" : "0, 0, 0";
      root.style.setProperty("--mobile-top-gradient-rgb", topChannels);
      root.style.setProperty("--mobile-sheet-gradient-rgb", sheetChannels);
    };
    applyMobileThemeGradientVars();
    new MutationObserver((mutations) => {
      if (mutations.some((mutation) => mutation.attributeName === "data-theme")) {
        applyMobileThemeGradientVars();
      }
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const _pageParams = new URLSearchParams(window.location.search || "");
    const launchShellMode = _pageParams.get("launch_shell") === "1";
__CHAT_INCLUDE:../../shared/chat/conversation-state.js__
__CHAT_INCLUDE:../../shared/chat/launch-shell-gate.js__
    if (launchShellMode) {
      armLaunchShellGate();
    }
    const syncMainAfterHeight = () => {
      const mainEl = document.querySelector("main");
      if (!mainEl) return;
      const lockHeight = parseInt(document.documentElement.style.getPropertyValue("--hub-iframe-lock-height"), 10) || 0;
      const baseHeight = lockHeight > 0
        ? lockHeight
        : Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
      if (baseHeight <= 0) return;
      const fixedSpacerHeight = Math.round(baseHeight * 0.4);
      mainEl.style.setProperty("--main-spacer-height", fixedSpacerHeight + "px");
      mainEl.style.removeProperty("--main-after-height");
    };
    let _pollScrollLockTop = null;
    let _pollScrollAnchor = null;
    syncMainAfterHeight();
    window.addEventListener("resize", syncMainAfterHeight, { passive: true });
    if (window.visualViewport) {
      const onVVResize = () => {
        syncMainAfterHeight();
        updateScrollBtnPos();
        if (_stickyToBottom && timeline) {
          _pollScrollLockTop = null;
          _pollScrollAnchor = null;
          timeline.scrollTop = timeline.scrollHeight;
        }
      };
      visualViewport.addEventListener("resize", onVVResize);
      visualViewport.addEventListener("scroll", onVVResize);
    }
    let _hubIframeLayoutMaxH = 0;
    let _hubIframeLayoutFromParent = 0;
    let _hubChromeGapClientMin = Infinity;
    const HUB_KEYBOARD_GAP_THRESHOLD = 150;
    let _hubChildOriW = 0;
    let _hubChildOriH = 0;
    const isEmbeddedHubChat = window.parent !== window;
    const applyHubIframeLockHeight = () => {
      if (!isEmbeddedHubChat) {
        syncMainAfterHeight();
        return;
      }
      const local = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
      _hubIframeLayoutMaxH = Math.max(_hubIframeLayoutMaxH, local);
      const h = Math.max(_hubIframeLayoutMaxH, _hubIframeLayoutFromParent);
      if (h > 0) {
        document.documentElement.style.setProperty("--hub-iframe-lock-height", h + "px");
      }
      syncMainAfterHeight();
    };
    const bumpHubIframeLayoutLock = () => {
      if (!isEmbeddedHubChat) return;
      applyHubIframeLockHeight();
    };
    const requestHubParentLayout = () => {
      if (!isEmbeddedHubChat) return;
      try {
        window.parent.postMessage({ type: "chat-request-hub-layout" }, "*");
      } catch (_) { }
    };
    const requestHubCloseChat = () => {
      if (!isEmbeddedHubChat) return;
      try {
        window.parent.postMessage("hub_close_chat", "*");
      } catch (_) { }
    };
    const notifyHubChatRenderReady = () => {
      if (!isEmbeddedHubChat) return;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          try {
            window.parent.postMessage({ type: "chat-render-ready" }, "*");
          } catch (_) { }
        });
      });
    };
    const notifyHubChatRenderError = (message) => {
      if (!isEmbeddedHubChat) return;
      window.parent.postMessage({ type: "chat-render-error", message: String(message || "render failed") }, "*");
    };
    if (isEmbeddedHubChat) {
      document.documentElement.dataset.hubIframeChat = "1";
      _hubChildOriW = window.innerWidth || 0;
      _hubChildOriH = window.innerHeight || 0;
      window.addEventListener("message", (e) => {
        if (!e.data || e.data.type !== "hub-layout") return;
        if (e.source !== window.parent) return;
        const lh = Number(e.data.layoutHeight) || 0;
        if (lh > 0) {
          _hubIframeLayoutFromParent = lh;
          applyHubIframeLockHeight();
        }
        const pih = Number(e.data.parentInnerHeight);
        const pvh = Number(e.data.parentVvHeight);
        const pvTop = Number(e.data.parentVvOffsetTop);
        const pcg = e.data.parentChromeGap;
        if (pih > 0 && pvh >= 0) {
          const top = Number.isFinite(pvTop) ? pvTop : 0;
          const fallbackRaw = Math.max(0, Math.round(pih - top - pvh));
          const incoming =
            typeof pcg === "number" && Number.isFinite(pcg) && pcg >= 0 ? pcg : fallbackRaw;
          if (incoming < HUB_KEYBOARD_GAP_THRESHOLD) {
            _hubChromeGapClientMin = Math.min(_hubChromeGapClientMin, incoming);
          }
          const effective = incoming >= HUB_KEYBOARD_GAP_THRESHOLD ? incoming : _hubChromeGapClientMin;
          document.documentElement.style.setProperty(
            "--hub-parent-chrome-gap",
            (effective === Infinity ? incoming : effective) + "px",
          );
        }
      });
      __CHAT_INCLUDE:../../shared/chat/hub-safari-chrome.js__
      bumpHubIframeLayoutLock();
      hubPingParentForSafariChrome();
      window.addEventListener("resize", hubChildResizeChrome, { passive: true });
      if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", hubChildResizeChrome);
        window.visualViewport.addEventListener("scroll", () => {
          bumpHubIframeLayoutLock();
          hubPingParentForSafariChrome();
        });
      }
      timeline.addEventListener("scroll", hubPingParentForSafariChrome, { passive: true });
      requestHubParentLayout();
    }
    window.addEventListener("message", (e) => {
      if (!e.data || e.data.type !== "hub-theme-changed") return;
      document.documentElement.dataset.theme = e.data.theme === "light" ? "light" : "dark";
    });
    if (window.parent !== window) {
      const reportObservedSystemTheme = () => {
        try {
          window.parent.postMessage({
            type: "hub-mobile-system-theme-observed",
            theme: window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
          }, "*");
        } catch (_) {}
      };
      try {
        const query = window.matchMedia("(prefers-color-scheme: dark)");
        if (query.addEventListener) query.addEventListener("change", reportObservedSystemTheme);
        else if (query.addListener) query.addListener(reportObservedSystemTheme);
      } catch (_) {}
      window.addEventListener("pageshow", reportObservedSystemTheme);
      window.addEventListener("focus", reportObservedSystemTheme);
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) reportObservedSystemTheme();
      });
    }
__CHAT_INCLUDE:../../shared/chat/scroll-focus.js__
__CHAT_INCLUDE:modals/file-modal.js__
__CHAT_INCLUDE:../../shared/chat/composer-overlay.js__
__CHAT_INCLUDE:../../shared/chat/rich-rendering-setup.js__
__CHAT_INCLUDE:../../shared/chat/transcript/rich-rendering.js__
__CHAT_INCLUDE:../../shared/chat/message-collapse.js__
__CHAT_INCLUDE:../../shared/chat/target-picker.js__
__CHAT_INCLUDE:../../shared/chat/target-selection.js__
__CHAT_INCLUDE:../../shared/chat/composer-draft.js__
__CHAT_INCLUDE:../../shared/chat/scroll-lock.js__
    const updateStickyState = () => {
      if (_programmaticScroll) return;
      _stickyToBottom = isNearBottom();
    };
__CHAT_INCLUDE:../../shared/chat/scroll-btn.js__

__CHAT_INCLUDE:../../shared/chat/runtime/messages.js__
__CHAT_INCLUDE:../../shared/chat/transcript/render.js__
__CHAT_INCLUDE:../../shared/chat/transcript/actions.js__
__CHAT_INCLUDE:runtime/hub-navigation.js__
__CHAT_INCLUDE:panes/header-menu.js__
__CHAT_INCLUDE:panes/sheets.js__
__CHAT_INCLUDE:../../shared/chat/composer/runtime.js__
__CHAT_INCLUDE:../../shared/chat/attachments/file-runtime.js__
__CHAT_INCLUDE:../../shared/chat/composer/commands.js__
__CHAT_INCLUDE:../../shared/chat/thinking.js__
__CHAT_INCLUDE:../../shared/chat/runtime/agent-status.js__
__CHAT_INCLUDE:../../shared/chat/pointer-capability.js__
__CHAT_INCLUDE:panes/pane-viewer.js__
    let workspaceSyncEventSource = null;
    let workspaceSyncLastSeq = 0;
    let workspaceSyncLastGitVersion = 0;
    let workspaceSyncLastFileVersion = 0;
    const handleWorkspaceSyncUpdate = (payload = {}) => {
      const nextSeq = Math.max(0, parseInt(payload?.seq) || 0);
      if (nextSeq && nextSeq <= workspaceSyncLastSeq) return;
      if (nextSeq) workspaceSyncLastSeq = nextSeq;
      const nextGitVersion = parseInt(payload?.git_version);
      const gitChanged = Number.isFinite(nextGitVersion) && nextGitVersion !== workspaceSyncLastGitVersion;
      if (Number.isFinite(nextGitVersion)) workspaceSyncLastGitVersion = nextGitVersion;
      const nextFileVersion = parseInt(payload?.file_version);
      const fileChanged = Number.isFinite(nextFileVersion) && nextFileVersion !== workspaceSyncLastFileVersion;
      if (Number.isFinite(nextFileVersion)) workspaceSyncLastFileVersion = nextFileVersion;
      const repoPanelOpen = !!(repoPanel && repoPanel.classList.contains("open") && !repoPanel.hidden);
      if (fileChanged && repoPanelOpen && typeof repoPanel._syncCategoryUi === "function") {
        repoPanel._syncCategoryUi();
      }
      const gitPanelOpen = !!(gitPanel && gitPanel.classList.contains("open") && !gitPanel.hidden);
      if (gitChanged && gitPanelOpen) {
        void updateGitPanel().catch(() => {});
      }
    };
    __CHAT_INCLUDE:../../shared/chat/workspace-sync-events.js__
    refresh({ forceScroll: true });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        void refresh();
      }
    });
