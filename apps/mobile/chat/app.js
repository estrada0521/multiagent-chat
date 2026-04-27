__CHAT_INCLUDE:../../shared/chat/base.js__
    const fileViewHrefForPath = (path, { embed = false } = {}) => {
      const params = new URLSearchParams();
      params.set("path", String(path || ""));
      if (embed) {
        params.set("embed", "1");
        params.set("progressive", "1");
      }
      params.set("agent_font_mode", currentFilePreviewFontMode());
      if (CHAT_BASE_PATH) params.set("base_path", CHAT_BASE_PATH);
      const textSize = currentFilePreviewTextSize();
      if (textSize) params.set("agent_text_size", textSize);
      return withChatBase(`/file-view?${params.toString()}`);
    };
    const buildInlineFileLinkMarkup = (path, label = "") => {
      const normalizedPath = String(path || "").trim();
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
    const _pageParams = new URLSearchParams(window.location.search || "");
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
    const reconnectingStatusText = "reconnecting...";
    let messageRefreshFailures = 0;
    let reconnectStatusVisible = false;
    let refreshInFlight = false;
    let pendingRefreshOptions = null;
    let sessionStateInFlight = false;
    let pendingSessionStateRefresh = false;
    let autoModeInFlight = false;
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
      } catch (_) { }
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
    const syncMainAfterHeight = () => {
      const mainEl = document.querySelector("main");
      if (!mainEl) return;
      const lockHeight = parseInt(document.documentElement.style.getPropertyValue("--hub-iframe-lock-height"), 10) || 0;
      const baseHeight = lockHeight > 0
        ? lockHeight
        : Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
      if (baseHeight <= 0) return;
      const fixedAfterHeight = Math.round(baseHeight * 0.7);
      mainEl.style.setProperty("--main-after-height", fixedAfterHeight + "px");
    };
    let _pollScrollLockTop = null;
    let _pollScrollAnchor = null;
    let _hubIframeLayoutMaxH = 0;
    let _hubIframeLayoutFromParent = 0;
    let _hubChromeGapClientMin = Infinity;
    let _hubChildOriW = 0;
    let _hubChildOriH = 0;
    const applyHubIframeLockHeight = () => {
      if (!window.frameElement) {
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
      if (!window.frameElement) return;
      applyHubIframeLockHeight();
    };
    const requestHubParentLayout = () => {
      if (!window.frameElement) return;
      try {
        window.parent.postMessage({ type: "multiagent-chat-request-hub-layout" }, "*");
      } catch (_) { }
    };
    const requestHubCloseChat = () => {
      if (!window.frameElement) return;
      try {
        window.parent.postMessage("hub_close_chat", "*");
      } catch (_) { }
    };
    const notifyHubChatRenderReady = () => {
      if (!window.frameElement) return;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          try {
            window.parent.postMessage({ type: "multiagent-chat-render-ready" }, "*");
          } catch (_) { }
        });
      });
    };
    if (window.frameElement) {
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
      let _hubParentScrollSigAt = 0;
      const hubPingParentForSafariChrome = () => {
        const now = Date.now();
        if (now - _hubParentScrollSigAt < 220) return;
        _hubParentScrollSigAt = now;
        try {
          window.parent.postMessage({ type: "multiagent-chat-scroll-signal" }, "*");
        } catch (_) { }
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
      hubPingParentForSafariChrome();
      setTimeout(hubPingParentForSafariChrome, 120);
      setTimeout(hubPingParentForSafariChrome, 400);
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
            } catch (_) { }
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
        } catch (_) { }
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
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\[', right: '\\]', display: true }
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
    let cancelCameraModeMicRecognition = () => { };
    let _renderedIds = new Set();
    const expandedUserMessages = new Set();
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
__CHAT_INCLUDE:../../shared/chat/target-camera.js__
      } catch (_) { }
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
      const nodes = targetNode ? [targetNode] : document.querySelectorAll("#hubPageMenuBtn, #rightMenuBtn");
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
      } catch (_) { }
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
      if (pendingLaunchControls) pendingLaunchControls.hidden = !launchMode;
      if (input) {
        input.disabled = !sessionActive;
        input.placeholder = launchMode ? "Start the session to send a message" : "Write a message";
      }
      const selectedLaunchAgent = selectedTargets.filter((target) => availableTargets.includes(target))[0] || "";
      if (pendingLaunchBtn) {
        pendingLaunchBtn.disabled = !selectedLaunchAgent;
        pendingLaunchBtn.textContent = selectedLaunchAgent ? `Start ${selectedLaunchAgent}` : "Start Session";
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
      } catch (_) { }
    };
    timeline.addEventListener("scroll", updateScrollBtn, { passive: true });
    timeline.addEventListener("scroll", requestCenteredMessageRowUpdate, { passive: true });
    window.addEventListener("resize", requestCenteredMessageRowUpdate);

    {
      const header = document.querySelector(".hub-page-header");
      let prevScrollTop = 0;
      let scrollUpAccum = 0;
      const HIDE_THRESHOLD = 50;
      const SCROLL_UP_REVEAL_PX = 56;
      timeline.addEventListener("scroll", () => {
        const st = timeline.scrollTop;
        const delta = st - prevScrollTop;
        const goingDown = delta > 0;
        const goingUp = delta < 0;
        if (goingUp) scrollUpAccum += -delta;
        else scrollUpAccum = 0;
        const isAtBottom = st + timeline.clientHeight >= timeline.scrollHeight - 30;
        const isComposerFocused = isComposerOverlayOpen() && document.getElementById("composer")?.contains(document.activeElement);
        const isHeaderMenuOpen = !!document.querySelector(".hub-page-header > .hub-page-menu-panel.open");
        const isFileModalOpen = document.body.classList.contains("file-modal-open");

        if (goingDown && st > HIDE_THRESHOLD && !isAtBottom && !isComposerFocused && !isHeaderMenuOpen && !isFileModalOpen) {
          if (header) {
            header.classList.add("header-hidden");
            try { window.parent.postMessage({ type: 'multiagent-hub-scroll-hide', hidden: true }, "*"); } catch (_) {}
          }
        } else if (
          isAtBottom ||
          isComposerFocused ||
          isHeaderMenuOpen ||
          isFileModalOpen ||
          st <= HIDE_THRESHOLD ||
          scrollUpAccum >= SCROLL_UP_REVEAL_PX
        ) {
          if (header) {
            header.classList.remove("header-hidden");
            try { window.parent.postMessage({ type: 'multiagent-hub-scroll-hide', hidden: false }, "*"); } catch (_) {}
            scrollUpAccum = 0;
          }
        }

        prevScrollTop = st;
      }, { passive: true });
    }

__CHAT_INCLUDE:runtime/sound.js__
__CHAT_INCLUDE:transcript/render.js__
__CHAT_INCLUDE:transcript/actions.js__
__CHAT_INCLUDE:panes/header-menu.js__
__CHAT_INCLUDE:panes/right-pane.js__
__CHAT_INCLUDE:composer/runtime.js__
__CHAT_INCLUDE:runtime/thinking-touch.js__
__CHAT_INCLUDE:attachments/file-runtime.js__
__CHAT_INCLUDE:composer/commands.js__
__CHAT_INCLUDE:runtime/thinking.js__
__CHAT_INCLUDE:runtime/agent-status.js__
__CHAT_INCLUDE:panes/pane-viewer.js__
    let lastApprovalTs = 0;
    const showAutoApprovalNotice = (agent) => {
      const chip = agent
        ? document.querySelector(`.target-chip[data-target="${CSS.escape(agent)}"]`)
        : null;
      if (!chip) return;
      document.querySelectorAll(".target-chip.auto-approval-notice").forEach((node) => {
        if (node._autoApprovalNoticeHideTimer) clearTimeout(node._autoApprovalNoticeHideTimer);
        if (node._autoApprovalNoticeCleanupTimer) clearTimeout(node._autoApprovalNoticeCleanupTimer);
        node.classList.remove("auto-approval-notice-visible");
        node.classList.remove("auto-approval-notice");
      });
      chip.classList.add("auto-approval-notice");
      void chip.offsetWidth;
      chip.classList.add("auto-approval-notice-visible");
      chip._autoApprovalNoticeHideTimer = setTimeout(() => {
        chip.classList.remove("auto-approval-notice-visible");
        chip._autoApprovalNoticeCleanupTimer = setTimeout(() => {
          chip.classList.remove("auto-approval-notice");
          chip._autoApprovalNoticeCleanupTimer = null;
          chip._autoApprovalNoticeHideTimer = null;
        }, 220);
      }, 1600);
    };
    const refreshAutoMode = async () => {
      if (autoModeInFlight) return;
      autoModeInFlight = true;
      try {
        const res = await fetchWithTimeout("/auto-mode", {}, 4000);
        if (!res.ok) return;
        const d = await res.json();
        if (d.last_approval && d.last_approval !== lastApprovalTs) {
          if (lastApprovalTs !== 0) showAutoApprovalNotice(d.last_approval_agent || "");
          lastApprovalTs = d.last_approval;
        }
      } catch (_) {
      } finally {
        autoModeInFlight = false;
      }
    };
    refreshAutoMode();
    setInterval(refreshAutoMode, 3000);
    refresh({ forceScroll: true });
    if (followMode) {
      setInterval(refresh, 500);
    }
