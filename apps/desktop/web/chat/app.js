__CHAT_INCLUDE:../../../shared/chat/base.js__
    const currentFilePreviewBoldEnabled = () => {
      const isNarrowViewport = (window.innerWidth || 0) <= 480;
      return isNarrowViewport ? !!currentBoldModeMobile : !!currentBoldModeDesktop;
    };
    const normalizeWorkspaceFilePath = (p) => {
      let s = String(p || "").trim();
      if (!s) return "";
      s = s.replace(/\\/g, "/");
      for (let i = 0; i < 8; i += 1) {
        const next = s.replace("/./", "/");
        if (next === s) break;
        s = next;
      }
      for (let i = 0; i < 8; i += 1) {
        const next = s.replace("//", "/");
        if (next === s) break;
        s = next;
      }
      if (s.length > 1 && s.endsWith("/")) {
        s = s.slice(0, -1);
      }
      return s;
    };
    const fileViewHrefForPath = (path, { embed = false } = {}) => {
      const params = new URLSearchParams();
      params.set("path", normalizeWorkspaceFilePath(path) || String(path || "").trim());
      if (embed) { params.set("embed", "1"); params.set("pane", "1"); }
      params.set("agent_font_mode", currentFilePreviewFontMode());
      if (CHAT_BASE_PATH) params.set("base_path", CHAT_BASE_PATH);
      const textSize = currentFilePreviewTextSize();
      if (textSize) params.set("agent_text_size", textSize);
      params.set("message_bold", currentFilePreviewBoldEnabled() ? "1" : "0");
      return withChatBase(`/file-view?${params.toString()}`);
    };
    const buildInlineFileLinkMarkup = (path, label = "") => {
      const normalizedPath = normalizeWorkspaceFilePath(path);
      if (!normalizedPath) return "";
      const visible = String(label || displayAttachmentFilename(normalizedPath) || normalizedPath).trim() || normalizedPath;
      const href = fileViewHrefForPath(normalizedPath);
      return `<a class="inline-file-link" href="${escapeHtml(href)}" data-filepath="${escapeHtml(normalizedPath)}" data-ext="${escapeHtml(extFromPath(normalizedPath))}" title="${escapeHtml(normalizedPath)}"><code>${escapeHtml(visible)}</code></a>`;
    };
    const injectFileCards = (html) => {
      return html
        .replace(/\[Attached:\s*([^\]]+)\]/g, (match, rawPath) => buildInlineFileLinkMarkup(rawPath.trim()))
        .replace(/(^|[\s>(])@((?:[A-Za-z0-9._-]+\/)+[A-Za-z0-9._-]+(?:\.[A-Za-z0-9._-]+)?)/g, (match, prefix, rawPath) => {
          return `${prefix}${buildInlineFileLinkMarkup(rawPath, rawPath)}`;
        });
    };
    const FOCUS_MSG_PARAM = "focus_msg_id";
    const readFocusMsgIdFromUrl = () => (new URLSearchParams(window.location.search).get(FOCUS_MSG_PARAM) || "").trim();
    const _pageParams = new URLSearchParams(window.location.search);
    const followMode = _pageParams.get("follow") === "1";
    const launchShellMode = _pageParams.get("launch_shell") === "1";
    const composerAutoOpenRequested = _pageParams.get("compose") === "1";
    let draftLaunchHintActive = _pageParams.get("draft") === "1";
    let draftTargetHints = (_pageParams.get("draft_targets") || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!draftTargetHints.length) {
      draftLaunchHintActive = false;
    }
    const DESKTOP_FILE_PANE_MIN_VIEWPORT_PX = 961;
    const syncMainAfterHeight = () => {
      const mainEl = document.querySelector("main");
      if (!mainEl) return;
      mainEl.style.removeProperty("--main-after-height");
    };
    const syncAppShellHeight = () => {
      document.documentElement.style.removeProperty("--app-shell-height");
      document.documentElement.style.removeProperty("--mobile-overlay-lock-height");
      syncMainAfterHeight();
    };
    syncAppShellHeight();
    window.addEventListener("pageshow", () => syncAppShellHeight());
    window.addEventListener("resize", () => syncAppShellHeight());
    if (window.visualViewport) {
      let _vvSyncTimer = 0;
      const scheduleSyncFromVV = () => {
        if (_vvSyncTimer) clearTimeout(_vvSyncTimer);
        _vvSyncTimer = setTimeout(() => { _vvSyncTimer = 0; syncAppShellHeight(); }, 200);
      };
      window.visualViewport.addEventListener("resize", scheduleSyncFromVV);
      window.visualViewport.addEventListener("scroll", scheduleSyncFromVV);
    }
    const reconnectingStatusText = "reconnecting...";
    let messageRefreshFailures = 0;
    let reconnectStatusVisible = false;
    let refreshInFlight = false;
    let pendingRefreshOptions = null;
    let reloadInFlight = false;
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const AGENT_ICON_DATA = __ICON_DATA_URIS__;
    const SERVER_INSTANCE_SEED = "__SERVER_INSTANCE__";
    let currentServerInstance = SERVER_INSTANCE_SEED;
    const isPublicChatView = !(() => {
      const host = String(location.hostname || "");
      return host === "127.0.0.1" || host === "localhost" || host === "[::1]" || host.startsWith("192.168.") || host.startsWith("10.") || /^172\\.(1[6-9]|2\\d|3[01])\\./.test(host);
    })();
    const MESSAGE_BATCH = 50;
    const INITIAL_MESSAGE_WINDOW = 50;
    let latestPayloadData = null;
    let pendingFocusMsgId = readFocusMsgIdFromUrl();
    let focusWindowRequestedMsgId = "";
    let olderEntries = [];
    let olderHasMore = false;
    let olderLoading = false;
    let publicFullEntryCache = new Map();
    let publicDeferredLoading = new Set();
    let publicDeferredObserver = null;
    let hasInitialRefreshHydrated = false;
    let launchShellRevealFallbackTimer = 0;
    const timeline = document.getElementById("messages");
    const clearLaunchShellParam = () => {
      const params = new URLSearchParams(window.location.search || "");
      if (!params.has("launch_shell")) return;
      params.delete("launch_shell");
      const nextQuery = params.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}${window.location.hash || ""}`;
      try {
        window.history.replaceState(window.history.state, "", nextUrl);
      } catch (_) {}
    };
    const releaseLaunchShellGate = () => {
      if (document.documentElement.dataset.launchShell !== "1") return;
      document.documentElement.removeAttribute("data-launch-shell");
      if (launchShellRevealFallbackTimer) {
        clearTimeout(launchShellRevealFallbackTimer);
        launchShellRevealFallbackTimer = 0;
      }
      clearLaunchShellParam();
    };
    const armLaunchShellGate = (timeoutMs = 10000) => {
      document.documentElement.dataset.launchShell = "1";
      if (launchShellRevealFallbackTimer) {
        clearTimeout(launchShellRevealFallbackTimer);
      }
      launchShellRevealFallbackTimer = setTimeout(() => {
        releaseLaunchShellGate();
      }, Math.max(1000, Number(timeoutMs) || 10000));
    };
    if (launchShellMode) {
      armLaunchShellGate(10000);
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
        window.parent.postMessage({ type: "multiagent-chat-request-hub-layout" }, "*");
      } catch (_) {}
    };
    const notifyHubComposerOverlayState = (open) => {
      if (!isHubIframeChat()) return;
      try {
        window.parent.postMessage({ type: "multiagent-composer-overlay-state", open: !!open }, "*");
      } catch (_) {}
    };
    const notifyHubChatRenderReady = () => {
      if (!isHubIframeChat()) return;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          try {
            window.parent.postMessage({ type: "multiagent-chat-render-ready" }, "*");
          } catch (_) {}
        });
      });
    };
    if (isHubIframeChat()) {
      document.documentElement.dataset.hubIframeChat = "1";
      _hubChildOriW = window.innerWidth || 0;
      _hubChildOriH = window.innerHeight || 0;
      window.addEventListener("message", (e) => {
        if (!e.data || e.data.type !== "multiagent-hub-layout") return;
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
      window.addEventListener("pagehide", () => notifyHubComposerOverlayState(false));
      let _hubParentScrollSigAt = 0;
      const hubPingParentForSafariChrome = () => {
        const now = Date.now();
        if (now - _hubParentScrollSigAt < 220) return;
        _hubParentScrollSigAt = now;
        try {
          window.parent.postMessage({ type: "multiagent-chat-scroll-signal" }, "*");
        } catch (_) {}
      };
      const hubChildResizeChrome = () => {
        const w = window.innerWidth || 0;
        const h = window.innerHeight || 0;
        if (_hubChildOriW > 0 && _hubChildOriH > 0) {
          const b0 = _hubChildOriH >= _hubChildOriW;
          const b1 = h >= w;
          const diffH = Math.abs(_hubChildOriH - h);
          if (b0 !== b1 && diffH > 150) {
            _hubChromeGapClientMin = Infinity;
          }
        }
        _hubChildOriW = w;
        _hubChildOriH = h;
        bumpHubIframeLayoutLock();
      };
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
    const scrollConversationToBottom = (behavior = "auto") => {
      _programmaticScroll = true;
      timeline.scrollTo({ top: timeline.scrollHeight, behavior });
      requestAnimationFrame(() => { _programmaticScroll = false; });
    };
    const focusMessageInputWithoutScroll = (selectionStart = null, selectionEnd = selectionStart) => {
      if (typeof isComposerOverlayOpen === "function" && typeof openComposerOverlay === "function" && !isComposerOverlayOpen()) {
        openComposerOverlay({ immediateFocus: true });
        if (selectionStart !== null && typeof messageInput.setSelectionRange === "function") {
          requestAnimationFrame(() => {
            try {
              messageInput.setSelectionRange(selectionStart, selectionEnd ?? selectionStart);
            } catch (_) {}
          });
        }
        return;
      }
      try {
        messageInput.focus({ preventScroll: true });
      } catch (_) {
        messageInput.focus();
      }
      if (selectionStart !== null && typeof messageInput.setSelectionRange === "function") {
        try {
          messageInput.setSelectionRange(selectionStart, selectionEnd ?? selectionStart);
        } catch (_) {}
      }
    };
__CHAT_INCLUDE:modals/file-modal.js__
__CHAT_INCLUDE:composer-overlay.js__
    const updateScrollBtnPos = () => {
      const shell = document.querySelector(".shell");
      shell.style.setProperty("--floating-btn-bottom", "160px");
      shell.style.setProperty("--composer-height", "0px");
    };
    const mathRenderOptions = {
      delimiters: [
        {left: '$$', right: '$$', display: true},
        {left: '$', right: '$', display: false},
        {left: '\\[', right: '\\]', display: true}
      ],
      ignoredClasses: ["no-math"],
      throwOnError: false
    };
__CHAT_INCLUDE:transcript/rich-rendering.js__
    let selectedTargets = [];
    let sendLocked = false;
    let lastSubmitAt = 0;
    let sessionActive = true;
    let sessionLaunchPending = draftLaunchHintActive;
    let composerAutoOpenConsumed = false;
    let _sessionLaunching = false;
    const canComposeInSession = () => !!sessionActive;
    const canInteractWithSession = () => !!(sessionActive || sessionLaunchPending);
    let pendingAttachments = [];
    let availableTargets = [];
    let currentSessionName = "";
    let cameraModeStream = null;
    let cameraModeBusy = false;
    let cameraModeOpening = false;
    let cameraModeTarget = "";
    let cameraModeTargetsExpanded = false;
    let cameraModeBackdropFrosted = false;
    let cameraModeTimelinePlaceholder = null;
    let cameraModePrevMainAfterHeight = null;
    let cameraModeMicListening = false;
    let cancelCameraModeMicRecognition = () => {};
    let _renderedIds = new Set();
    const expandedMessageBodies = new Set();
    const isCollapsibleMessageSender = (sender) => {
      const normalized = String(sender || "").trim().toLowerCase();
      return !!normalized && normalized !== "system";
    };
    const isCollapsibleMessageRow = (row) =>
      !!(row && row.classList?.contains("message-row") && isCollapsibleMessageSender(row.dataset?.sender));
    const escapeHtml = (value) => value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
    const emptyConversationHTML = () => {
      return `<div class="conversation-empty" aria-hidden="true"></div>`;
    };
    const stripSenderPrefix = (value) => value.replace(/^\[From:\s*[^\]]+\]\s*/i, "");
    const parseControlShortcut = (value) => {
      const normalized = (value || "").trim().toLowerCase();
      const mapped = {
        "interrupt": { name: "interrupt" },
        "esc": { name: "interrupt" },
        "save": { name: "save" },
        "restart": { name: "restart" },
        "resume": { name: "resume" },
        "ctrl+c": { name: "ctrlc" },
        "ctrlc": { name: "ctrlc" },
        "enter": { name: "enter" },
        "model": { name: "model", keepComposerOpen: true },
      }[normalized];
      if (mapped) return mapped;
      const nav = normalized.match(/^(up|down)(?:\s+(\d+))?$/);
      if (nav) {
        const repeat = Math.max(1, Math.min(parseInt(nav[2] || "1", 10) || 1, 100));
        return { name: nav[1], repeat, keepComposerOpen: true };
      }
      return null;
    };
    const shortcutLabel = (value) => ({
      "interrupt": "Esc",
      "save": "Save",
      "restart": "Restart",
      "resume": "Resume",
      "ctrlc": "Ctrl+C",
      "enter": "Enter",
      "model": "Model",
      "up": "Up",
      "down": "Down",
    }[(value || "").trim().toLowerCase()] || value);
    const rememberDraftTargetHints = (targets = []) => {
      if (!Array.isArray(targets) || !targets.length) return;
      const next = [...new Set(
        targets
          .filter((item) => typeof item === "string" && item.trim())
          .map((item) => item.trim())
      )];
      if (next.length) {
        draftTargetHints = next;
      }
    };
    const effectiveDraftTargets = () => draftLaunchHintActive ? [...draftTargetHints] : [];
    const normalizedSessionTargets = (rawTargets) => {
      const next = Array.isArray(rawTargets)
        ? rawTargets.filter((item) => typeof item === "string" && item.trim()).map((item) => item.trim())
        : [];
      if (next.length) {
        rememberDraftTargetHints(next);
        return next;
      }
      if (sessionLaunchPending || draftLaunchHintActive) {
        return effectiveDraftTargets();
      }
      return [];
    };
    const syncPendingLaunchControls = () => {
      const pendingLaunchControls = document.getElementById("pendingLaunchControls");
      const pendingLaunchBtn = document.getElementById("pendingLaunchBtn");
      const input = document.getElementById("message");
      const sendBtnEl = document.querySelector(".send-btn");
      const micBtnEl = document.getElementById("micBtn");
      const launchMode = !!(sessionLaunchPending && !sessionActive);
      composerOverlay?.classList.toggle("pending-launch-mode", launchMode);
      composerForm?.classList.toggle("pending-launch-mode", launchMode);
      if (input) {
        input.disabled = !sessionActive;
        input.placeholder = launchMode ? "Start the session to send a message" : "Write a message";
      }
      const selectedLaunchAgent = selectedTargets.filter((target) => availableTargets.includes(target))[0] || "";
      if (pendingLaunchBtn) {
        if (_sessionLaunching) {
          pendingLaunchBtn.disabled = true;
          pendingLaunchBtn.textContent = "Starting…";
        } else {
          pendingLaunchBtn.disabled = !selectedLaunchAgent;
          pendingLaunchBtn.textContent = "Start Session";
        }
      }
      if (sessionLaunchPending || !sessionActive) {
        if (sendBtnEl) sendBtnEl.classList.remove("visible");
        if (micBtnEl) micBtnEl.classList.remove("hidden");
        return;
      }
      const hasText = !!(input && input.value.trim().length > 0);
      if (sendBtnEl) sendBtnEl.classList.toggle("visible", hasText);
      if (micBtnEl) micBtnEl.classList.toggle("hidden", hasText);
    };
    const clearDraftLaunchHints = () => {
      draftLaunchHintActive = false;
      draftTargetHints = [];
      try {
        const params = new URLSearchParams(window.location.search);
        let changed = false;
        ["draft", "draft_targets"].forEach((key) => {
          if (params.has(key)) {
            params.delete(key);
            changed = true;
          }
        });
        if (!changed) return;
        const nextQuery = params.toString();
        window.history.replaceState(window.history.state, "", `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`);
      } catch (_) {}
    };
__CHAT_INCLUDE:../../../shared/chat/target-camera.js__
      } catch (_) {}
    }
    const settleScrollLockFrames = (remaining) => {
      if (remaining <= 0) return;
      maybeRestorePollScrollLock();
      requestAnimationFrame(() => settleScrollLockFrames(remaining - 1));
    };
    const isNearBottom = () => {
      return timeline.scrollHeight - timeline.scrollTop - timeline.clientHeight < STICKY_THRESHOLD;
    };
    const updateStickyState = () => {
      if (_programmaticScroll) return;
      _stickyToBottom = isNearBottom();
    };
    const clearPollScrollLock = () => {
      _pollScrollLockTop = null;
      _pollScrollAnchor = null;
    };
    timeline.addEventListener("wheel", clearPollScrollLock, { passive: true });
    timeline.addEventListener("touchstart", clearPollScrollLock, { passive: true });
    timeline.addEventListener("scroll", updateStickyState, { passive: true });
    timeline.addEventListener("scroll", () => {
      if (olderLoading || !olderHasMore) return;
      if (timeline.scrollTop > PUBLIC_OLDER_AUTOLOAD_THRESHOLD) return;
      void loadOlderMessages();
    }, { passive: true });
    const updateScrollBtn = () => {
      if (!hasInitialRefreshHydrated) {
        scrollToBottomBtn.classList.remove("visible");
        composerFabBtn?.classList.remove("visible");
        return;
      }
      const overlayOpen = isComposerOverlayOpen();
      const cameraModeOpen = isCameraModeOpen();
      const emptyPlaceholder = !!document.querySelector("#messages .conversation-empty");
      scrollToBottomBtn.classList.toggle("visible", !_stickyToBottom && !overlayOpen && !cameraModeOpen && !emptyPlaceholder);
      composerFabBtn?.classList.toggle("visible", (_stickyToBottom || emptyPlaceholder) && !overlayOpen && !cameraModeOpen);
    };
    let centeredRowRaf = 0;
    const updateCenteredMessageRow = () => {
      const rows = Array.from(document.querySelectorAll("#messages article.message-row"));
      rows.forEach((row) => row.classList.remove("is-centered"));
      const useCenterHighlight = window.matchMedia("(hover: none), (pointer: coarse)").matches;
      if (!useCenterHighlight || !rows.length) return;
      const timelineRect = timeline.getBoundingClientRect();
      const centerY = timelineRect.top + (timelineRect.height / 2);
      let bestRow = null;
      let bestDistance = Number.POSITIVE_INFINITY;
      rows.forEach((row) => {
        const rect = row.getBoundingClientRect();
        if (rect.bottom <= timelineRect.top || rect.top >= timelineRect.bottom) return;
        const rowCenter = rect.top + (rect.height / 2);
        const distance = Math.abs(rowCenter - centerY);
        if (distance < bestDistance) {
          bestDistance = distance;
          bestRow = row;
        }
      });
      bestRow?.classList.add("is-centered");
    };
    const requestCenteredMessageRowUpdate = () => {
      if (centeredRowRaf) return;
      centeredRowRaf = requestAnimationFrame(() => {
        centeredRowRaf = 0;
        updateCenteredMessageRow();
      });
    };
    const flashHeaderToggle = (targetNode) => {
      const nodes = targetNode ? [targetNode] : document.querySelectorAll("#rightMenuBtn");
      nodes.forEach((node) => {
        if (node.classList.contains("animating")) return;
        node.classList.add("animating");
        setTimeout(() => {
          node.classList.remove("animating");
        }, 500);
      });
    };
    const flashComposerAction = (action) => {
      document.querySelectorAll(`.composer-plus-panel [data-forward-action="${action}"]`).forEach((node) => {
        node.classList.remove("toggle-flash");
        void node.offsetWidth;
        node.classList.add("toggle-flash");
        setTimeout(() => node.classList.remove("toggle-flash"), 120);
      });
    };
    const targetSelectionStorageKey = (session) => `targetSelection:${session || "default"}`;
    const saveTargetSelection = (session, targets) => {
      if (!session) return;
      try {
        localStorage.setItem(targetSelectionStorageKey(session), JSON.stringify(targets || []));
      } catch (_) {}
    };
    const loadTargetSelection = (session, availableTargets = []) => {
      if (!session) return [];
      try {
        const raw = localStorage.getItem(targetSelectionStorageKey(session));
        const parsed = JSON.parse(raw || "[]");
        if (!Array.isArray(parsed)) return [];
        const allowed = new Set(availableTargets);
        return parsed.filter((item) => typeof item === "string" && allowed.has(item));
      } catch (_) {
        return [];
      }
    };
    timeline.addEventListener("scroll", updateScrollBtn, { passive: true });
    timeline.addEventListener("scroll", requestCenteredMessageRowUpdate, { passive: true });
    window.addEventListener("resize", requestCenteredMessageRowUpdate);

    {
      const header = document.querySelector(".hub-page-header");
      if (header) header.classList.remove("header-hidden");
      timeline.addEventListener("scroll", () => {
        if (header?.classList.contains("header-hidden")) {
          header.classList.remove("header-hidden");
        }
      }, { passive: true });
    }

__CHAT_INCLUDE:runtime/sound.js__
__CHAT_INCLUDE:transcript/render.js__
__CHAT_INCLUDE:transcript/actions.js__
__CHAT_INCLUDE:panes/header-menu.js__
__CHAT_INCLUDE:panes/right-pane.js__
__CHAT_INCLUDE:composer/runtime.js__
__CHAT_INCLUDE:attachments/file-runtime.js__
__CHAT_INCLUDE:composer/commands.js__
__CHAT_INCLUDE:runtime/thinking.js__
__CHAT_INCLUDE:runtime/agent-status.js__
__CHAT_INCLUDE:panes/pane-viewer.js__
__CHAT_INCLUDE:../../../../debug/chat/native_log_sync_panel.js__
    let followRefreshTimer = 0;
    const nextFollowRefreshMs = () => {
      if (document.hidden) return 1500;
      return 500;
    };
    const scheduleFollowRefresh = (delay = nextFollowRefreshMs()) => {
      if (followRefreshTimer) clearTimeout(followRefreshTimer);
      if (!followMode) return;
      followRefreshTimer = setTimeout(async () => {
        await refresh();
        scheduleFollowRefresh();
      }, Math.max(250, delay || 0));
    };
    const desktopRightPanel = document.getElementById("desktopRightPanel");
    const desktopRightPanelResizer = document.getElementById("desktopRightPanelResizer");
    const dpSplitPanel = document.getElementById("dpSplitPanel");
    const dpSplitDivider = document.getElementById("dpSplitDivider");
    const dpRepoContent = document.getElementById("dpRepoContent");
    const dpGitContent = document.getElementById("dpGitContent");
    const DP_PANEL_DEFAULT_WIDTH = 356;
    const DP_PANEL_MIN_WIDTH = 220;
    const DP_PANEL_MAX_WIDTH = 560;
    const DP_PANEL_WIDTH_KEY = "multiagent_desktop_right_panel_width_px";
    const DP_PANEL_GAP = 0;
    const hasDesktopRightPanelOverlay = () => (
      document.documentElement.dataset.tauriApp === "1"
      && document.documentElement.dataset.hubIframeChat === "1"
      && document.documentElement.dataset.mobile !== "1"
    );
    let dpPanelOpen = false;
    let dpActivePanelView = "repo";
    let dpRepoBrowserPath = "";
    let dpPanelWidthPx = DP_PANEL_DEFAULT_WIDTH;
    let _desktopRightPanelResizeState = null;
    let _dpSplitDragging = false;
    let _dpSplitGitHeightPx = null;
    const dpDesktopFilePaneWidthPx = () => {
      const raw = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--desktop-file-pane-width"));
      return Number.isFinite(raw) ? Math.max(0, Math.round(raw)) : 0;
    };
    const dpClampPanelWidthPx = (value) => {
      const viewportWidth = Math.max(0, window.innerWidth || 0);
      const filePaneWidth = dpDesktopFilePaneWidthPx();
      const availableWidth = Math.max(0, viewportWidth - filePaneWidth);
      const maxWidth = Math.max(DP_PANEL_MIN_WIDTH, Math.min(DP_PANEL_MAX_WIDTH, availableWidth - 360));
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
            type: "multiagent-desktop-panel-state",
            mode: dpPanelOpen ? "open" : "",
            view: dpActivePanelView,
            width: dpPanelOpen ? dpCurrentPanelWidthPx() : 0,
          }, "*");
        }
      } catch (_) {}
    };
    const setDesktopRightPanelView = (view) => {
      dpActivePanelView = view === "git" ? "git" : "repo";
      return dpActivePanelView;
    };
    const loadDesktopRightPanelView = ({ reset = false } = {}) => {
      if (!dpPanelOpen) return Promise.resolve();
      const gitP = dpLoadGitBranchPage({ reset: true });
      dpLoadRepoDir(dpRepoBrowserPath || "");
      return Promise.resolve(gitP);
    };
    const openDesktopRightPanel = ({ view = null, reset = false } = {}) => {
      if (!hasDesktopRightPanelOverlay() || !desktopRightPanel) return Promise.resolve();
      if (view) setDesktopRightPanelView(view);
      dpPanelOpen = true;
      dpApplyPanelWidth();
      dpSyncPinnedSummaryStrip();
      desktopRightPanel.hidden = false;
      requestAnimationFrame(() => {
        desktopRightPanel.classList.add("open");
        document.body.classList.add("right-panel-open");
      });
      if (fileModal && !fileModal.hidden) {
        updateFileModalViewportMetrics();
        scheduleFileModalViewportMetrics();
      }
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
      const loadP = loadDesktopRightPanelView({ reset });
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
      if (fileModal && !fileModal.hidden) {
        updateFileModalViewportMetrics();
        scheduleFileModalViewportMetrics();
      }
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
      if (fileModal && !fileModal.hidden) updateFileModalViewportMetrics();
      if (needsHeaderViewportMetrics()) updateHeaderMenuViewportMetrics();
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
      return btn;
    };
    const dpRenderRepoPanel = (rawPath, entries, { loading = false, error = "" } = {}) => {
      if (!dpRepoContent) return;
      const path = dpNormalizePath(rawPath);
      dpRepoBrowserPath = path;
      dpRepoContent.innerHTML = "";
      const title = document.createElement("div");
      title.className = "dp-pane-title";
      title.textContent = "Repo";
      dpRepoContent.appendChild(title);
      const stack = document.createElement("div");
      stack.className = "repo-browser-stack";
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
      const rootBtn = document.createElement("button");
      rootBtn.type = "button";
      rootBtn.className = "repo-path-nav-btn";
      rootBtn.innerHTML = wrapFileIcon('<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>');
      rootBtn.title = "ルートへ";
      rootBtn.disabled = !path;
      rootBtn.addEventListener("click", (e) => {
        e.preventDefault(); e.stopPropagation();
        void dpLoadRepoDir("");
      });
      pathRow.append(backIcon, pathText, rootBtn);
      pathWrap.appendChild(pathRow);
      stack.appendChild(pathWrap);
      const scroll = document.createElement("div");
      scroll.className = "repo-browser-scroll";
      const list = document.createElement("div");
      list.className = "repo-browser-list";
      if (loading) {
        const node = document.createElement("div");
        node.className = "repo-browser-empty inline-loading-row";
        node.innerHTML = dpLoadingHtml();
        list.appendChild(node);
      } else if (error) {
        const node = document.createElement("div");
        node.className = "repo-browser-empty";
        node.textContent = error;
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
    const dpLoadRepoDir = async (rawPath) => {
      if (!dpPanelOpen) return;
      const path = dpNormalizePath(rawPath);
      dpRenderRepoPanel(path, [], { loading: true });
      try {
        const entries = await dpFetchRepoDir(path);
        if (!dpPanelOpen) return;
        dpRenderRepoPanel(path, entries);
      } catch (err) {
        if (!dpPanelOpen) return;
        dpRenderRepoPanel(path, [], { error: err?.message || "Failed to load directory" });
      }
    };
    window.addEventListener("message", (event) => {
      if (!event.data) return;
      if (event.data.type === "multiagent-desktop-panel-sync-request") {
        notifyParentPanelState();
        return;
      }
      if (event.data.type !== "multiagent-desktop-panel") return;
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
    let workspaceSyncEventSource = null;
    let workspaceSyncLastSeq = 0;
    let workspaceSyncLastHubSettingsVersion = -1;
    const handleWorkspaceSyncUpdate = (payload = {}) => {
      const nextSeq = Math.max(0, parseInt(payload?.seq) || 0);
      if (nextSeq && nextSeq <= workspaceSyncLastSeq) return;
      if (nextSeq) workspaceSyncLastSeq = nextSeq;
      if (dpPanelOpen && dpActivePanelView === "repo") {
        void dpLoadRepoDir(dpRepoBrowserPath || "");
      }
      if (dpPanelOpen || dpGitSummaryPinned) {
        void dpRefreshGitOverview();
      }
      const nextHubSettingsVersion = parseInt(payload?.hub_settings_version) || 0;
      if (nextHubSettingsVersion > workspaceSyncLastHubSettingsVersion) {
        workspaceSyncLastHubSettingsVersion = nextHubSettingsVersion;
        void syncChatNotificationDefaults();
      }
    };
    const startWorkspaceSyncEvents = () => {
      if (typeof EventSource !== "function") return;
      if (workspaceSyncEventSource) return;
      const base = CHAT_BASE_PATH || "";
      const initialUrl = workspaceSyncLastSeq > 0
        ? `${base}/workspace-sync-events?after=${encodeURIComponent(String(workspaceSyncLastSeq))}`
        : `${base}/workspace-sync-events`;
      const es = new EventSource(initialUrl);
      es.addEventListener("sync", (event) => {
        try {
          handleWorkspaceSyncUpdate(JSON.parse(event.data || "{}"));
        } catch (_) {}
      });
      es.onerror = () => {};
      workspaceSyncEventSource = es;
    };
    startWorkspaceSyncEvents();
    dpOnSessionSummaryPinReload({ force: true });
    dpApplyPanelWidth();
    refresh({ forceScroll: true });
    if (followMode) {
      scheduleFollowRefresh();
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
          void refresh();
          scheduleFollowRefresh(0);
        }
      });
    }
