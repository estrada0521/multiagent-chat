__CHAT_INCLUDE:../../shared/chat/base.js__
    const _pageParams = new URLSearchParams(window.location.search);
    const launchShellMode = _pageParams.get("launch_shell") === "1";
    const DESKTOP_FILE_PANE_MIN_VIEWPORT_PX = 961;
    let _scrollbarLayoutSyncFrame = 0;
    const syncChatScrollbarLayoutWidth = () => {
      const mainEl = document.querySelector("main");
      if (!mainEl || document.documentElement.dataset.mobile === "1") return;
      const width = Math.max(0, mainEl.offsetWidth - mainEl.clientWidth);
      const next = `${width}px`;
      if (mainEl.style.getPropertyValue("--chat-scrollbar-layout-width") !== next) {
        mainEl.style.setProperty("--chat-scrollbar-layout-width", next);
      }
    };
    const scheduleChatScrollbarLayoutWidthSync = () => {
      if (_scrollbarLayoutSyncFrame) return;
      _scrollbarLayoutSyncFrame = requestAnimationFrame(() => {
        _scrollbarLayoutSyncFrame = 0;
        syncChatScrollbarLayoutWidth();
      });
    };
    const mainScrollbarEl = document.querySelector("main");
    if (mainScrollbarEl && typeof ResizeObserver === "function") {
      new ResizeObserver(scheduleChatScrollbarLayoutWidthSync).observe(mainScrollbarEl);
    }
    const syncMainAfterHeight = () => {
      const mainEl = document.querySelector("main");
      if (!mainEl) return;
      // In "Fit Height to Message" mode the window equals the last message, so
      // the 50vh scroll spacers would just blank the view -- collapse them.
      if (document.documentElement.dataset.autoWindowHeight === "1") {
        mainEl.style.setProperty("--main-spacer-height", "0px");
      } else {
        mainEl.style.removeProperty("--main-spacer-height");
      }
      mainEl.style.removeProperty("--main-after-height");
    };
    const syncAppShellHeight = () => {
      document.documentElement.style.removeProperty("--app-shell-height");
      document.documentElement.style.removeProperty("--mobile-overlay-lock-height");
      syncMainAfterHeight();
    };
    syncAppShellHeight();
    scheduleChatScrollbarLayoutWidthSync();
    window.addEventListener("pageshow", () => syncAppShellHeight());
    window.addEventListener("resize", () => {
      syncAppShellHeight();
      scheduleChatScrollbarLayoutWidthSync();
      // "Fit Height to Message": the window just resized to the last message --
      // pin the transcript to the bottom so that message is what's shown.
      if (document.documentElement.dataset.autoWindowHeight === "1") {
        _stickyToBottom = true;
        requestAnimationFrame(() => scrollConversationToBottom("auto"));
      }
    });
    if (window.visualViewport) {
      let _vvSyncTimer = 0;
      const scheduleSyncFromVV = () => {
        if (_vvSyncTimer) clearTimeout(_vvSyncTimer);
        _vvSyncTimer = setTimeout(() => { _vvSyncTimer = 0; syncAppShellHeight(); }, 200);
      };
      window.visualViewport.addEventListener("resize", scheduleSyncFromVV);
      window.visualViewport.addEventListener("scroll", scheduleSyncFromVV);
    }
__CHAT_INCLUDE:../../shared/chat/conversation-state.js__
__CHAT_INCLUDE:../../shared/chat/launch-shell-gate.js__
    if (launchShellMode) {
      armLaunchShellGate();
    }
    let _pollScrollLockTop = null;
    let _pollScrollAnchor = null;
    let _hubIframeLayoutMaxH = 0;
    let _hubIframeLayoutFromParent = 0;
    let _hubChromeGapClientMin = Infinity;
    let _hubChildOriW = 0;
    let _hubChildOriH = 0;
    const isHubIframeChat = () =>
      document.documentElement.dataset.hubIframeChat === "1" ||
      document.documentElement.dataset.hubShell === "1" ||
      !!window.frameElement;
    const applyHubIframeLockHeight = () => {
      if (!isHubIframeChat()) return;
      const local = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
      _hubIframeLayoutMaxH = Math.max(_hubIframeLayoutMaxH, local);
      const h = Math.max(_hubIframeLayoutMaxH, _hubIframeLayoutFromParent);
      if (h > 0) {
        document.documentElement.style.setProperty("--hub-iframe-lock-height", h + "px");
      }
    };
    const bumpHubIframeLayoutLock = () => {
      if (!isHubIframeChat()) return;
      applyHubIframeLockHeight();
    };
    const requestHubParentLayout = () => {
      if (!isHubIframeChat()) return;
      try {
        window.parent.postMessage({ type: "chat-request-hub-layout" }, "*");
      } catch (_) {}
    };
    const notifyHubChatRenderReady = () => {
      if (!isHubIframeChat()) return;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          try {
            window.parent.postMessage({ type: "chat-render-ready" }, "*");
          } catch (_) {}
        });
      });
    };
    const notifyHubChatRenderError = (message) => {
      if (!isHubIframeChat()) return;
      window.parent.postMessage({ type: "chat-render-error", message: String(message || "render failed") }, "*");
    };
    if (isHubIframeChat()) {
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
          if (incoming < 150) {
            _hubChromeGapClientMin = Math.min(_hubChromeGapClientMin, incoming);
          }
          const effective = incoming >= 150 ? incoming : _hubChromeGapClientMin;
          document.documentElement.style.setProperty(
            "--hub-parent-chrome-gap",
            (effective === Infinity ? incoming : effective) + "px",
          );
        }
      });
      __CHAT_INCLUDE:../../shared/chat/hub-safari-chrome.js__
      bumpHubIframeLayoutLock();
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

    // "Fit Height to Message": after a message settles, report the transcript's
    // rendered content extent so the hub can size the window to it. Measured as
    // (last row bottom - first row top) in viewport px -- scroll-position
    // independent, and it ignores main::before / main::after (the 50vh scroll
    // spacers, which is why scrollHeight is useless here). Debounced for bursts.
    let _fitHeightTimer = 0;
    let _closeRefitTimer = 0;
    // Breathing room above the composer field when the window is sized to it.
    const COMPOSER_FIT_SLACK = 20;
    // The composer textarea stops growing at this height (composer-input.css
    // max-height). When the composer opens we size the window for this maximum
    // once, so typing never has to resize the window afterwards.
    const COMPOSER_MAX_FIELD = 200;
    const reportFitHeight = ({ fromComposer = false } = {}) => {
      if (!isHubIframeChat() || document.documentElement.dataset.autoWindowHeight !== "1") return;
      const scroller = timeline || document.getElementById("messages");
      const rows = scroller
        ? scroller.querySelectorAll(":scope > article.message-row, :scope > .sysmsg-row")
        : null;
      if (!rows || !rows.length) return;
      // The last message row, plus the running/thinking indicator below it when
      // one is up (so sending doesn't push the message off the top).
      const lastRow = rows[rows.length - 1];
      const thinkEl = scroller.querySelector(":scope > .message-thinking-container");
      const topPx = lastRow.getBoundingClientRect().top;
      const bottomPx = (thinkEl || lastRow).getBoundingClientRect().bottom;
      let contentHeight = Math.ceil(bottomPx - topPx);
      // While the composer overlay is open, always size the window for a
      // fully-grown composer (field at its max-height) -- even if the window is
      // currently taller. The input then always lands at the same place, and
      // typing never resizes the window.
      // Measure with offsetHeight, not getBoundingClientRect -- the composer
      // animates in with a transform and rects are distorted during it, whereas
      // offset metrics are the settled layout box. #composer's own box stays at
      // the one-line height (the field grows upward out of an absolutely-
      // positioned anchor), so add the field's max overflow above it.
      if (isComposerOverlayOpen()) {
        const box = document.getElementById("composer");
        if (box) {
          const FIELD_BASE = 52;
          contentHeight = Math.ceil(box.offsetHeight + (COMPOSER_MAX_FIELD - FIELD_BASE)) + COMPOSER_FIT_SLACK;
        }
      }
      if (contentHeight > 0) {
        if (!fromComposer) {
          _stickyToBottom = true;
          scrollConversationToBottom("auto");
        }
        try {
          window.parent.postMessage({ type: "fit-window-height", contentHeight }, "*");
        } catch (_) {}
      }
    };
    const scheduleFitHeight = () => {
      // Fire immediately (message just entered the DOM -> resize in step), then
      // a short follow-up to catch late layout: code blocks, KaTeX, image loads.
      reportFitHeight();
      clearTimeout(_fitHeightTimer);
      _fitHeightTimer = setTimeout(reportFitHeight, 120);
      // A real transcript update supersedes whatever the composer-close refit
      // below was about to (re)measure -- drop it so it doesn't fire a moment
      // later and redundantly resize to the same value it's already at.
      clearTimeout(_closeRefitTimer);
    };
    document.addEventListener("chat-transcript-settled", scheduleFitHeight);
    // Composer open: size the window once for a fully-grown composer. Typing
    // grows the field inside that already-large-enough window -- no per-keystroke
    // resize. Close: re-fit to the transcript.
    document.addEventListener("composer-overlay-open", () => {
      if (document.documentElement.dataset.autoWindowHeight !== "1") return;
      requestAnimationFrame(() => reportFitHeight({ fromComposer: true }));
    });
    document.addEventListener("composer-overlay-close-start", () => {
      clearTimeout(_closeRefitTimer);
      if (document.documentElement.dataset.sendInFlight === "1") {
        // Closing on send fires this before the just-sent message has
        // actually rendered (that happens after the /send round trip
        // resolves), so an immediate refit here would measure the *previous*
        // last message and snap the window to that size for a moment before
        // "chat-transcript-settled" (for the new message) corrects it right
        // after -- a visible flash. Give the round trip a head start instead;
        // scheduleFitHeight cancels this if the real message settles first.
        _closeRefitTimer = setTimeout(reportFitHeight, 200);
        return;
      }
      // Plain close (Escape / click-outside, nothing being sent): no new
      // message is coming, so refit immediately -- no reason to wait.
      requestAnimationFrame(() => reportFitHeight());
    });
__CHAT_INCLUDE:../../shared/chat/scroll-focus.js__
__CHAT_INCLUDE:attachments/file-open.js__
__CHAT_INCLUDE:../../shared/chat/composer-overlay.js__
__CHAT_INCLUDE:../../shared/chat/rich-rendering-setup.js__
__CHAT_INCLUDE:../../shared/chat/transcript/rich-rendering.js__
__CHAT_INCLUDE:../../shared/chat/message-collapse.js__
__CHAT_INCLUDE:../../shared/chat/target-picker.js__
__CHAT_INCLUDE:../../shared/chat/target-selection.js__
__CHAT_INCLUDE:../../shared/chat/composer-draft.js__
__CHAT_INCLUDE:../../shared/chat/scroll-lock.js__
    let _pinStickyThroughWidthChange = false;
    const updateStickyState = () => {
      if (_programmaticScroll || _pinStickyThroughWidthChange) return;
      _stickyToBottom = isNearBottom();
    };
__CHAT_INCLUDE:../../shared/chat/scroll-btn.js__
    let _timelineLayoutWidth = timeline.clientWidth;
    let _timelineMaxScroll = Math.max(0, timeline.scrollHeight - timeline.clientHeight);
    new ResizeObserver(() => {
      const width = timeline.clientWidth;
      const maxScroll = Math.max(0, timeline.scrollHeight - timeline.clientHeight);
      const prevWidth = _timelineLayoutWidth;
      const prevMaxScroll = _timelineMaxScroll;
      _timelineLayoutWidth = width;
      _timelineMaxScroll = maxScroll;
      if (width === prevWidth) return;
      const wasSticky = _stickyToBottom || (prevMaxScroll - timeline.scrollTop < STICKY_THRESHOLD);
      if (!wasSticky) return;
      _pinStickyThroughWidthChange = true;
      scrollConversationToBottom("auto");
      _stickyToBottom = true;
      requestAnimationFrame(() => {
        scrollConversationToBottom("auto");
        _stickyToBottom = true;
        requestAnimationFrame(() => {
          scrollConversationToBottom("auto");
          _stickyToBottom = true;
          _pinStickyThroughWidthChange = false;
          _timelineMaxScroll = Math.max(0, timeline.scrollHeight - timeline.clientHeight);
          updateScrollBtn();
        });
      });
    }).observe(timeline);

    {
      const header = document.querySelector(".page-header");
      if (header) header.classList.remove("header-hidden");
      timeline.addEventListener("scroll", () => {
        if (header?.classList.contains("header-hidden")) {
          header.classList.remove("header-hidden");
        }
      }, { passive: true });
    }

__CHAT_INCLUDE:../../shared/chat/runtime/messages.js__
__CHAT_INCLUDE:../../shared/chat/transcript/render.js__
__CHAT_INCLUDE:../../shared/chat/transcript/actions.js__
__CHAT_INCLUDE:runtime/hub-navigation.js__
__CHAT_INCLUDE:panes/header-menu.js__
__CHAT_INCLUDE:panes/header-actions.js__
__CHAT_INCLUDE:../../shared/chat/composer/runtime.js__
__CHAT_INCLUDE:../../shared/chat/attachments/file-runtime.js__
__CHAT_INCLUDE:../../shared/chat/composer/commands.js__
__CHAT_INCLUDE:../../shared/chat/thinking.js__
__CHAT_INCLUDE:../../shared/chat/runtime/agent-status.js__
    window.addEventListener("message", (event) => {
      if (event.source !== window.parent || event.data?.type !== "refresh-session-state") return;
      void refreshSessionState(event.data.projections);
    });
__CHAT_INCLUDE:../../shared/chat/pointer-capability.js__
__CHAT_INCLUDE:../../shared/chat/runtime/settings-sync.js__
    const desktopRightPanel = document.getElementById("desktopRightPanel");
    const desktopRightPanelResizer = document.getElementById("desktopRightPanelResizer");
    const dpSplitPanel = document.getElementById("dpSplitPanel");
    const dpSplitDivider = document.getElementById("dpSplitDivider");
    const dpRepoContent = document.getElementById("dpRepoContent");
    const dpGitContent = document.getElementById("dpGitContent");
    const DP_PANEL_DEFAULT_WIDTH = 220;
    const DP_PANEL_MIN_WIDTH = 220;
    const DP_PANEL_MAX_WIDTH = 560;
    const DP_CHAT_MIN_WIDTH = 360;
    const DP_PANEL_WIDTH_KEY = "agent_window_desktop_right_panel_width_px";
    const DP_PANEL_GAP = 0;
    const hasDesktopRightPanelOverlay = () => (
      document.documentElement.dataset.tauriApp === "1"
      && document.documentElement.dataset.hubIframeChat === "1"
      && document.documentElement.dataset.mobile !== "1"
    );
    let dpPanelOpen = false;
    let dpActivePanelView = "repo";
    let dpRepoBrowserPath = "";
    let dpRepoBrowserNavDirection = "forward";
    let dpPanelWidthPx = DP_PANEL_DEFAULT_WIDTH;
    let _desktopRightPanelResizeState = null;
    let _dpSplitDragging = false;
    let _dpSplitGitHeightPx = null;
    const dpClampPanelWidthPx = (value) => {
      const viewportWidth = Math.max(0, window.innerWidth || 0);
      const availableWidth = viewportWidth;
      const maxWidth = Math.max(DP_PANEL_MIN_WIDTH, Math.min(DP_PANEL_MAX_WIDTH, availableWidth - DP_CHAT_MIN_WIDTH));
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return Math.max(DP_PANEL_MIN_WIDTH, Math.min(DP_PANEL_DEFAULT_WIDTH, maxWidth));
      }
      return Math.max(DP_PANEL_MIN_WIDTH, Math.min(maxWidth, Math.round(numeric)));
    };
    try {
      const storedPanelWidth = Number.parseInt(window.localStorage?.getItem(DP_PANEL_WIDTH_KEY) || "", 10);
      if (Number.isFinite(storedPanelWidth) && storedPanelWidth > 0) {
        dpPanelWidthPx = storedPanelWidth;
      }
    } catch (_) {}
    const dpOutwardPanelWidthPx = () => {
      if (dpPanelOpen) return dpCurrentPanelWidthPx();
      const viewportWidth = Math.max(0, window.innerWidth || 0);
      if (viewportWidth < DP_CHAT_MIN_WIDTH) return DP_PANEL_MIN_WIDTH;
      const numeric = Number(dpPanelWidthPx);
      if (!Number.isFinite(numeric)) return DP_PANEL_DEFAULT_WIDTH;
      return Math.max(DP_PANEL_MIN_WIDTH, Math.min(DP_PANEL_MAX_WIDTH, Math.round(numeric)));
    };
    const dpPersistPanelWidthPx = () => {
      try {
        if (dpPanelWidthPx > 0) {
          window.localStorage?.setItem(DP_PANEL_WIDTH_KEY, String(dpPanelWidthPx));
        }
      } catch (_) {}
    };
    const dpCurrentPanelWidthPx = () => dpClampPanelWidthPx(dpPanelWidthPx || DP_PANEL_DEFAULT_WIDTH);
    const dpApplyPanelWidth = () => {
      dpPanelWidthPx = dpCurrentPanelWidthPx();
      const panelWidth = hasDesktopRightPanelOverlay() && dpPanelOpen ? dpPanelWidthPx : 0;
      document.documentElement.style.setProperty("--desktop-right-panel-width", `${panelWidth}px`);
      document.documentElement.style.setProperty("--desktop-right-panel-reserved-width", `${panelWidth > 0 ? panelWidth + DP_PANEL_GAP : 0}px`);
    };
__CHAT_INCLUDE:features/git-panel/panel.js__
    const notifyParentPanelState = () => {
      try {
        if (window.parent && window.parent !== window) {
          window.parent.postMessage({
            type: "desktop-panel-state",
            mode: dpPanelOpen ? "open" : "",
            view: dpActivePanelView,
            width: dpOutwardPanelWidthPx(),
          }, "*");
        }
      } catch (_) {}
    };
    const setDesktopRightPanelView = (view) => {
      dpActivePanelView = view === "git" ? "git" : "repo";
      return dpActivePanelView;
    };
    const loadDesktopRightPanelView = ({ reset = false, animateRepo = true } = {}) => {
      if (!dpPanelOpen) return Promise.resolve();
      const gitP = dpLoadGitPage({ reset: true });
      dpLoadRepoDir(dpRepoBrowserPath || "", { animate: animateRepo });
      return Promise.resolve(gitP);
    };
    const openDesktopRightPanel = ({ view = null, reset = false } = {}) => {
      if (!hasDesktopRightPanelOverlay() || !desktopRightPanel) return Promise.resolve();
      if (view) setDesktopRightPanelView(view);
      dpPanelOpen = true;
      dpApplyPanelWidth();
      dpSyncPinnedSummaryStrip();
      desktopRightPanel.hidden = false;
      desktopRightPanel.classList.add("open");
      document.body.classList.add("right-panel-open");
      if (dpGitContent && dpSplitPanel && !_dpSplitGitHeightPx) {
        requestAnimationFrame(() => {
          const panelH = dpSplitPanel.getBoundingClientRect().height;
          if (panelH > 0 && !_dpSplitGitHeightPx) {
            const initH = Math.max(80, Math.floor(panelH * 0.5));
            dpGitContent.style.height = `${initH}px`;
            _dpSplitGitHeightPx = initH;
          }
        });
      }
      const loadP = loadDesktopRightPanelView({ reset, animateRepo: false });
      notifyParentPanelState();
      return loadP;
    };
    const closeDesktopRightPanel = () => {
      if (!desktopRightPanel) return;
      dpStopPanelResize();
      dpPanelOpen = false;
      desktopRightPanel.classList.remove("open");
      desktopRightPanel.hidden = true;
      document.body.classList.remove("right-panel-open");
      dpDisconnectGitObserver();
      dpSyncPinnedSummaryStrip();
      notifyParentPanelState();
    };
    const toggleDesktopRightPanel = () => {
      if (dpPanelOpen) closeDesktopRightPanel();
      else openDesktopRightPanel();
    };
    const dpStopPanelResize = ({ persist = false } = {}) => {
      if (!_desktopRightPanelResizeState) return;
      _desktopRightPanelResizeState = null;
      document.body.classList.remove("desktop-right-panel-resizing");
      if (persist) dpPersistPanelWidthPx();
    };
    const dpHandlePanelResizeMove = (event) => {
      if (!_desktopRightPanelResizeState || !dpPanelOpen) return;
      const nextWidth = _desktopRightPanelResizeState.startWidth + (_desktopRightPanelResizeState.startX - event.clientX);
      dpPanelWidthPx = dpClampPanelWidthPx(nextWidth);
      dpApplyPanelWidth();
      notifyParentPanelState();
    };
    dpSplitDivider?.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      _dpSplitDragging = true;
      dpSplitDivider.classList.add("dragging");
      dpSplitDivider.setPointerCapture(e.pointerId);
      document.body.classList.add("dp-split-resizing");
    });
    dpSplitDivider?.addEventListener("pointermove", (e) => {
      if (!_dpSplitDragging || !dpGitContent || !dpSplitPanel) return;
      const rect = dpSplitPanel.getBoundingClientRect();
      let newH = e.clientY - rect.top - 3;
      newH = Math.max(80, Math.min(rect.height - 66, newH));
      dpGitContent.style.height = `${newH}px`;
      _dpSplitGitHeightPx = newH;
    });
    dpSplitDivider?.addEventListener("pointerup", () => {
      _dpSplitDragging = false;
      dpSplitDivider.classList.remove("dragging");
      document.body.classList.remove("dp-split-resizing");
    });
    dpSplitDivider?.addEventListener("pointercancel", () => {
      _dpSplitDragging = false;
      dpSplitDivider.classList.remove("dragging");
      document.body.classList.remove("dp-split-resizing");
    });
    desktopRightPanelResizer?.addEventListener("pointerdown", (event) => {
      if (!dpPanelOpen) return;
      event.preventDefault();
      event.stopPropagation();
      _desktopRightPanelResizeState = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startWidth: dpCurrentPanelWidthPx(),
      };
      document.body.classList.add("desktop-right-panel-resizing");
      try {
        desktopRightPanelResizer.setPointerCapture(event.pointerId);
      } catch (_) {}
    });
    desktopRightPanelResizer?.addEventListener("pointermove", (event) => {
      if (!_desktopRightPanelResizeState || _desktopRightPanelResizeState.pointerId !== event.pointerId) return;
      dpHandlePanelResizeMove(event);
    });
    desktopRightPanelResizer?.addEventListener("pointerup", (event) => {
      if (!_desktopRightPanelResizeState || _desktopRightPanelResizeState.pointerId !== event.pointerId) return;
      dpStopPanelResize({ persist: true });
    });
    desktopRightPanelResizer?.addEventListener("pointercancel", () => {
      dpStopPanelResize({ persist: true });
    });
    const dpNormalizePath = (value) => String(value || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
    let dpFileContextPath = "";
    let dpFileContextRequestSeq = 0;
    let dpWorkspaceRoot = "";
    const dpShowFileActionStatus = (message, error = false) => {
      setStatus(message, error);
      setTimeout(() => setStatus(""), STATUS_TOAST_MS);
    };
    const dpOpenFileContextMenu = async (rawPath, event) => {
      const path = dpNormalizePath(rawPath);
      if (!path) return;
      event.preventDefault();
      event.stopPropagation();
      const requestSeq = ++dpFileContextRequestSeq;
      let revealEnabled = false;
      try {
        const response = await fetchWithTimeout("/files-exist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paths: [path] }),
        }, 4000);
        if (!response.ok) throw new Error("Failed to inspect file path.");
        const result = await response.json();
        revealEnabled = result?.[path] === true;
      } catch (err) {
        dpShowFileActionStatus(err?.message || "Failed to inspect file path.", true);
      }
      if (requestSeq !== dpFileContextRequestSeq) return;
      dpFileContextPath = path;
      window.parent?.postMessage({
        type: "show-file-context-menu",
        payload: {
          x: Math.round(Number(event.clientX) || 0),
          y: Math.round(Number(event.clientY) || 0),
          revealEnabled,
        },
      }, "*");
    };
    const dpCopyFilePath = async (path, absolute) => {
      let text = path;
      if (absolute) {
        if (!dpWorkspaceRoot) {
          const response = await fetchWithTimeout("/session-state?projections=base", {}, 4000);
          if (!response.ok) throw new Error("Failed to read workspace path.");
          const state = await response.json();
          dpWorkspaceRoot = String(state?.workspace || "").replace(/\/+$/, "");
          if (!dpWorkspaceRoot) throw new Error("Workspace path is unavailable.");
        }
        text = `${dpWorkspaceRoot}/${path}`;
      }
      await doCopyText(text);
      dpShowFileActionStatus(absolute ? "Copied absolute path" : "Copied relative path");
    };
    const dpRevealFileInFinder = async (path) => {
      const response = await fetchWithTimeout("/reveal-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      }, 12000);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data?.error || "Failed to reveal file in Finder.");
      }
      dpShowFileActionStatus(`Revealed ${path}`);
    };
    function handleDesktopFileContextMenuAction(payload) {
      const action = String(payload?.action || "");
      if (!["revealFileInFinder", "copyAbsoluteFilePath", "copyRelativeFilePath"].includes(action)) return false;
      const path = dpFileContextPath;
      if (!path) return true;
      const operation = action === "revealFileInFinder"
        ? dpRevealFileInFinder(path)
        : dpCopyFilePath(path, action === "copyAbsoluteFilePath");
      void operation.catch((err) => {
        dpShowFileActionStatus(err?.message || "File action failed.", true);
      });
      return true;
    }
    const dpFolderIcon = wrapFileIcon('<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h5.1a1.5 1.5 0 0 1 1.06.44l1.9 1.9a1.5 1.5 0 0 0 1.06.44H19.5A1.5 1.5 0 0 1 21 9.28V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>');
    const dpChevronIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 6 15 12 9 18"/></svg>';
    const dpBackIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 6 9 12 15 18"/></svg>';
    const dpFetchRepoDir = async (rawPath) => {
      const path = dpNormalizePath(rawPath);
      const res = await fetchWithTimeout(`/files-dir?path=${encodeURIComponent(path)}`, {}, 12000);
      if (!res.ok) throw new Error(res.status === 404 ? "Directory not found" : "Failed to load directory");
      const payload = await res.json().catch(() => ({}));
      const rawEntries = Array.isArray(payload?.entries) ? payload.entries : [];
      return rawEntries
        .filter((item) => item && typeof item.path === "string")
        .map((item) => {
          const entryPath = dpNormalizePath(item.path);
          const rawSize = Number(item.size);
          return {
            name: String(item.name || entryPath.split("/").pop() || entryPath),
            path: entryPath,
            kind: item.kind === "dir" ? "dir" : "file",
            size: item.kind === "dir" || !Number.isFinite(rawSize) || rawSize < 0 ? null : rawSize,
          };
        })
        .sort((a, b) => {
          if (a.kind !== b.kind) return a.kind === "dir" ? -1 : 1;
          return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
        });
    };
    const dpBuildRepoEntryItem = (entry) => {
      const isDir = entry.kind === "dir";
      const btn = document.createElement("button");
      btn.type = "button";
      const displayName = isDir ? entry.name : displayAttachmentFilename(entry.path);
      btn.className = `repo-browser-item ${isDir ? "repo-browser-dir" : "repo-browser-file"}${displayName.startsWith(".") ? " repo-browser-item-dimmed" : ""}`;
      btn.title = entry.path;
      const iconEl = document.createElement("span");
      iconEl.className = "repo-browser-item-icon";
      iconEl.innerHTML = isDir ? dpFolderIcon : (FILE_ICONS[fileExtForPath(entry.path)] || FILE_SVG_ICONS.file);
      const nameEl = document.createElement("span");
      nameEl.className = "repo-browser-item-name";
      nameEl.textContent = displayName;
      btn.append(iconEl, nameEl);
      if (isDir) {
        const chevronEl = document.createElement("span");
        chevronEl.className = "repo-browser-item-chevron";
        chevronEl.innerHTML = dpChevronIcon;
        btn.appendChild(chevronEl);
        btn.addEventListener("click", (e) => {
          e.preventDefault(); e.stopPropagation();
          void dpLoadRepoDir(entry.path);
        });
      } else {
        const sizeLabel = formatFileSize(entry.size);
        if (sizeLabel) {
          const sizeEl = document.createElement("span");
          sizeEl.className = "repo-browser-item-size";
          sizeEl.textContent = sizeLabel;
          btn.appendChild(sizeEl);
        }
        btn.addEventListener("click", async (e) => {
          e.preventDefault(); e.stopPropagation();
          await openFileSurface(entry.path, fileExtForPath(entry.path), btn, e);
        });
      }
      btn.addEventListener("contextmenu", (e) => {
        void dpOpenFileContextMenu(entry.path, e);
      });
      return btn;
    };
    const dpRepoEntriesStructureSignature = (entries) =>
      (entries || []).map((entry) => `${entry.kind}:${entry.path}`).join("\n");
    const dpRenderRepoPanel = (rawPath, entries, { loading = false, error = "", direction = "forward" } = {}) => {
      if (!dpRepoContent) return;
      const path = dpNormalizePath(rawPath);
      dpRepoBrowserPath = path;
      dpRepoContent.innerHTML = "";
      const stack = document.createElement("div");
      stack.className = `repo-browser-stack repo-browser-nav-${direction}`;
      const pathWrap = document.createElement("div");
      pathWrap.className = "repo-path-wrap";
      const pathRow = document.createElement("div");
      pathRow.className = `repo-path-back-btn${path ? " clickable" : ""}`;
      pathRow.setAttribute("role", "button");
      pathRow.setAttribute("aria-disabled", path ? "false" : "true");
      pathRow.tabIndex = path ? 0 : -1;
      pathRow.title = path ? "親ディレクトリへ" : "Root";
      pathRow.addEventListener("click", (e) => {
        e.preventDefault(); e.stopPropagation();
        if (!path) return;
        const parts = path.split("/").filter(Boolean);
        parts.pop();
        void dpLoadRepoDir(parts.join("/"));
      });
      pathRow.addEventListener("keydown", (e) => {
        if (e.target?.closest?.(".repo-path-nav-btn:not(.repo-path-back-icon-slot)")) return;
        if (!path || (e.key !== "Enter" && e.key !== " ")) return;
        e.preventDefault(); e.stopPropagation();
        const parts = path.split("/").filter(Boolean);
        parts.pop();
        void dpLoadRepoDir(parts.join("/"));
      });
      const backIcon = document.createElement("span");
      backIcon.className = "repo-path-nav-btn repo-path-back-icon-slot";
      backIcon.innerHTML = dpBackIcon;
      const pathText = document.createElement("span");
      pathText.className = "repo-path-label";
      pathText.textContent = path ? `/ ${path}` : "/";
      pathRow.append(backIcon, pathText);
      pathWrap.appendChild(pathRow);
      stack.appendChild(pathWrap);
      const scroll = document.createElement("div");
      scroll.className = "repo-browser-scroll";
      const list = document.createElement("div");
      list.className = "repo-browser-list";
      if (loading) {
        const node = document.createElement("div");
        node.className = "repo-browser-empty inline-loading-row";
        node.textContent = "";
        list.appendChild(node);
      } else if (error) {
        const node = document.createElement("button");
        node.type = "button";
        node.className = "repo-browser-empty error";
        node.textContent = error;
        node.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          void dpLoadRepoDir(path);
        });
        list.appendChild(node);
      } else {
        const dirs = (entries || []).filter(e => e.kind === "dir");
        const files = (entries || []).filter(e => e.kind !== "dir");
        if (!dirs.length && !files.length) {
          const node = document.createElement("div");
          node.className = "repo-browser-empty";
          node.textContent = "Empty directory";
          list.appendChild(node);
        } else {
          dirs.forEach(e => list.appendChild(dpBuildRepoEntryItem(e)));
          files.forEach(e => list.appendChild(dpBuildRepoEntryItem(e)));
        }
      }
      scroll.appendChild(list);
      stack.appendChild(scroll);
      dpRepoContent.appendChild(stack);
    };
    const dpLoadRepoDir = async (rawPath, { animate = true } = {}) => {
      if (!dpPanelOpen) return;
      const path = dpNormalizePath(rawPath);
      const currentDepth = dpRepoBrowserPath.split("/").filter(Boolean).length;
      const newDepth = path.split("/").filter(Boolean).length;
      const direction = animate && newDepth > currentDepth ? "forward" : (animate ? "back" : "none");
      dpRepoBrowserNavDirection = direction;
      dpRenderRepoPanel(path, [], { loading: true, direction });
      try {
        const entries = await dpFetchRepoDir(path);
        if (!dpPanelOpen) return;
        dpRenderRepoPanel(path, entries, { direction });
      } catch (err) {
        if (!dpPanelOpen) return;
        dpRenderRepoPanel(path, [], { error: err?.message || "Failed to load directory", direction });
      }
    };
    const dpRefreshRepoDir = async (rawPath) => {
      if (!dpPanelOpen || !dpRepoContent?.querySelector(".repo-browser-stack")) return;
      const path = dpNormalizePath(rawPath);
      try {
        const entries = await dpFetchRepoDir(path);
        if (!dpPanelOpen || dpActivePanelView !== "repo" || dpNormalizePath(dpRepoBrowserPath) !== path) return;
        const currentEntries = Array.from(dpRepoContent.querySelectorAll(".repo-browser-item")).map((item) => ({
          kind: item.classList.contains("repo-browser-dir") ? "dir" : "file",
          path: dpNormalizePath(item.title || ""),
        }));
        if (dpRepoEntriesStructureSignature(currentEntries) === dpRepoEntriesStructureSignature(entries)) return;
        const scrollEl = dpRepoContent.querySelector(".repo-browser-scroll");
        const scrollTop = scrollEl ? scrollEl.scrollTop : 0;
        dpRenderRepoPanel(path, entries, { direction: "none" });
        const nextScroll = dpRepoContent.querySelector(".repo-browser-scroll");
        if (nextScroll) nextScroll.scrollTop = scrollTop;
      } catch (_) {}
    };
    window.addEventListener("message", (event) => {
      if (!event.data) return;
      if (event.data.type === "hub-theme-changed") {
        const chatTheme = event.data.chatTheme || event.data.theme;
        document.documentElement.dataset.theme = chatTheme === "light" ? "light" : "dark";
        const themeDesktop = event.data.themeDesktop;
        if (themeDesktop) {
          document.documentElement.dataset.themeDesktop = themeDesktop;
        } else {
          delete document.documentElement.dataset.themeDesktop;
        }
        return;
      }
      if (event.data.type === "hub-text-size-changed") {
        const px = Number(event.data.textSize);
        if (Number.isFinite(px)) document.documentElement.style.setProperty("--text-size", `${px}px`);
        return;
      }
      if (event.data.type === "hub-auto-window-height") {
        document.documentElement.dataset.autoWindowHeight = event.data.on ? "1" : "0";
        syncMainAfterHeight();
        if (event.data.on) {
          // Entering the mode: the window gets short, so drop the pinned git
          // summary. Only here — a later explicit re-pin by the user stands.
          if (dpGitSummaryPinned) dpToggleGitSummaryPinned();
          requestAnimationFrame(reportFitHeight);
        } else {
          // The 50vh spacers just came back; the old scrollTop now points
          // mid-transcript. Snap to the bottom.
          _stickyToBottom = true;
          requestAnimationFrame(() => scrollConversationToBottom("auto"));
        }
        return;
      }
      if (event.data.type === "desktop-panel-sync-request") {
        notifyParentPanelState();
        return;
      }
      if (event.data.type === "file-context-menu-error") {
        dpShowFileActionStatus(String(event.data.message || "Failed to open file menu."), true);
        return;
      }
      // Fit Height mode: the hub asks for the uncommitted-file list to build a
      // native menu (the DOM panel can't fit the tiny window).
      if (event.data.type === "desk-git-changes-request") {
        (async () => {
          let files = [];
          let error = false;
          try {
            const loaded = await loadGitDiffFileStats({});
            const byPath = new Map();
            for (const f of (Array.isArray(loaded?.files) ? loaded.files : [])) {
              const p = String(f?.path || "").trim();
              if (!p) continue;
              const cur = byPath.get(p) || { path: p, ins: 0, dels: 0, untracked: !!f?.untracked };
              cur.ins += Number(f?.ins) || 0;
              cur.dels += Number(f?.dels) || 0;
              cur.untracked = cur.untracked || !!f?.untracked;
              byPath.set(p, cur);
            }
            files = Array.from(byPath.values());
          } catch (_) { error = true; }
          try { window.parent?.postMessage({ type: "desk-git-changes", files, error }, "*"); } catch (_) {}
        })();
        return;
      }
      if (event.data.type === "desk-open-git-file") {
        const p = String(event.data.path || "").trim();
        if (p) {
          if (event.data.untracked) void dpPostOpenFile(p);
          else void dpPostOpenDiff(p);
        }
        return;
      }
      if (event.data.type === "desktop-chat-reset") {
        closeDesktopRightPanel();
        // Reset / Compact Window restore the default layout, which includes the
        // pinned git summary (Fit Height mode drops it and doesn't put it back).
        if (!dpGitSummaryPinned) dpToggleGitSummaryPinned();
        _pollScrollLockTop = null;
        _pollScrollAnchor = null;
        _stickyToBottom = true;
        // The hub sends this only after the window geometry change has landed,
        // but the webview's own relayout (grid columns, iframe size) still
        // trails it by a frame or two -- re-assert the bottom across a few
        // frames so scrollHeight is measured once it has settled.
        let frames = 6;
        const settleToBottom = () => {
          scrollConversationToBottom("auto");
          _stickyToBottom = true;
          if (--frames > 0) requestAnimationFrame(settleToBottom);
        };
        settleToBottom();
        return;
      }
      if (event.data.type !== "desktop-panel") return;
      if (!hasDesktopRightPanelOverlay()) return;
      const mode = String(event.data.mode || "");
      if (mode === "close") {
        closeDesktopRightPanel();
      } else if (mode === "open") {
        toggleDesktopRightPanel();
      } else if (mode === "git") {
        openDesktopRightPanel({ view: "git", reset: true });
      } else if (mode === "repo") {
        openDesktopRightPanel({ view: "repo" });
      } else {
        toggleDesktopRightPanel();
      }
    });
    (() => {
      // Text size has exactly one writer: the Hub (home.js). This frame only
      // forwards the key intent and waits for the authoritative new value to
      // come back over "hub-text-size-changed" (handled above). It must NOT
      // compute-and-persist its own value here -- two independent writers
      // (this frame and the Hub) racing to read-modify-write the same
      // setting is exactly what caused the size to end up wrong on disk.
      window.addEventListener("keydown", (event) => {
        if (event.metaKey && event.altKey) {
          if (event.code === "KeyB") {
            event.preventDefault();
            window.parent?.postMessage({ type: "toggle-hub-sidebar-outward" }, "*");
            return;
          }
          if (event.code === "KeyE") {
            event.preventDefault();
            window.parent?.postMessage({ type: "toggle-desktop-panel-outward" }, "*");
            return;
          }
          if (event.code === "KeyT") {
            event.preventDefault();
            window.parent?.postMessage({ type: "desktop-menu-shortcut", action: "openTerminal" }, "*");
            return;
          }
          if (event.code === "KeyR") {
            event.preventDefault();
            window.parent?.postMessage({ type: "desktop-menu-shortcut", action: "openFinder" }, "*");
            return;
          }
          if (event.code === "KeyP") {
            event.preventDefault();
            window.parent?.postMessage({ type: "always-on-top-shortcut" }, "*");
            return;
          }
          if (event.code === "KeyH") {
            event.preventDefault();
            window.parent?.postMessage({ type: "auto-window-height-shortcut" }, "*");
            return;
          }
          if (event.code === "Digit0" || event.key === "0") {
            event.preventDefault();
            window.parent?.postMessage({ type: "reset-window-shortcut" }, "*");
            return;
          }
          if (event.code === "Digit9" || event.key === "9") {
            event.preventDefault();
            window.parent?.postMessage({ type: "compact-window-shortcut" }, "*");
            return;
          }
          if (event.code === "ArrowUp") {
            event.preventDefault();
            window.parent?.postMessage({ type: "move-window-shortcut", command: "move_window_top" }, "*");
            return;
          }
          if (event.code === "ArrowLeft") {
            event.preventDefault();
            window.parent?.postMessage({ type: "move-window-shortcut", command: "move_window_top_left" }, "*");
            return;
          }
          if (event.code === "ArrowRight") {
            event.preventDefault();
            window.parent?.postMessage({ type: "move-window-shortcut", command: "move_window_top_right" }, "*");
            return;
          }
          if (event.code === "ArrowDown") {
            event.preventDefault();
            window.parent?.postMessage({ type: "move-window-shortcut", command: "move_window_center" }, "*");
            return;
          }
        }
        if (event.metaKey && event.code === "Comma") {
          event.preventDefault();
          window.parent?.postMessage({ type: "desktop-menu-shortcut", action: "openSettingsFile" }, "*");
          return;
        }
        // In-app view toggles: plain ⌘ (like ⌘, and the text-size chords),
        // not the ⌥⌘ family that resizes/moves the window.
        if (event.metaKey && !event.altKey && event.code === "KeyB") {
          event.preventDefault();
          // Nothing to toggle while Fit Height has the sidebar collapsed to
          // native menus.
          if (document.documentElement.dataset.autoWindowHeight !== "1") {
            window.parent?.postMessage({ type: "toggle-hub-sidebar" }, "*");
          }
          return;
        }
        if (event.metaKey && !event.altKey && event.code === "KeyE") {
          event.preventDefault();
          // toggleDesktopRightPanel no-ops when the overlay is unavailable
          // (Fit Height).
          toggleDesktopRightPanel();
          return;
        }
        if (event.metaKey && !event.altKey && !event.shiftKey && !event.ctrlKey && event.code === "KeyT") {
          event.preventDefault();
          window.parent?.postMessage({ type: "desktop-menu-shortcut", action: "openShell" }, "*");
          return;
        }
        if (event.metaKey && !event.altKey && !event.ctrlKey && event.code === "KeyR") {
          event.preventDefault();
          window.parent?.postMessage({ type: "reload-shortcut", scope: event.shiftKey ? "hub" : "chat" }, "*");
          return;
        }
        if (event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey && event.code === "KeyN") {
          event.preventDefault();
          window.parent?.postMessage({ type: "new-session-shortcut" }, "*");
          return;
        }
        if (event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey && /^Digit[1-9]$/.test(event.code || "")) {
          event.preventDefault();
          window.parent?.postMessage({ type: "switch-session-shortcut", index: Number(event.code.slice(5)) - 1 }, "*");
          return;
        }
        if (!(event.metaKey || event.ctrlKey)) return;
        // event.code (physical key) instead of event.key: with metaKey held,
        // some WebViews don't reliably report the shift-modified character
        // for "=" (i.e. "+"), so matching on .key alone silently misses ⌘+.
        // Also accept "Semicolon": on JIS keyboards the physical key that
        // types "+" reports code "Semicolon", not "Equal" (confirmed via
        // live testing).
        if (event.code === "Equal" || event.code === "Semicolon" || event.key === "=" || event.key === "+") {
          event.preventDefault();
          window.parent?.postMessage({ type: "text-size-shortcut", delta: 1 }, "*");
        } else if (event.code === "Minus" || event.key === "-" || event.key === "_") {
          event.preventDefault();
          window.parent?.postMessage({ type: "text-size-shortcut", delta: -1 }, "*");
        } else if (event.code === "Digit0" || event.key === "0") {
          event.preventDefault();
          window.parent?.postMessage({ type: "text-size-shortcut", reset: true }, "*");
        }
      }, true);
    })();
    let workspaceSyncEventSource = null;
    let workspaceSyncLastSeq = 0;
    let workspaceSyncLastGitVersion = 0;
    let workspaceSyncLastFileVersion = 0;
    let workspaceSyncLastHubSettingsVersion = -1;
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
      if (gitChanged) gitSession.invalidateFingerprint();
      if (fileChanged && dpPanelOpen && dpActivePanelView === "repo") {
        void dpRefreshRepoDir(dpRepoBrowserPath || "");
      }
      if ((gitChanged || fileChanged) && (dpPanelOpen || dpGitSummaryPinned)) {
        if (dpPanelOpen && !gitSession.hasShell()) {
          void dpLoadGitPage({ reset: true });
        } else {
          void dpRefreshGitOverview();
        }
      }
      const nextHubSettingsVersion = parseInt(payload?.hub_settings_version) || 0;
      if (nextHubSettingsVersion > workspaceSyncLastHubSettingsVersion) {
        workspaceSyncLastHubSettingsVersion = nextHubSettingsVersion;
        void syncChatSettingsDefaults();
      }
    };
    __CHAT_INCLUDE:../../shared/chat/workspace-sync-events.js__
    dpOnSessionSummaryPinReload({ force: true });
    dpApplyPanelWidth();
    refresh({ forceScroll: true });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        void refresh();
      }
    });
