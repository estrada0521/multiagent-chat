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
      try {
        const res = await fetch("/auto-mode", { cache: "no-store" });
        if (!res.ok) return;
        const d = await res.json();
        if (d.last_approval && d.last_approval !== lastApprovalTs) {
          if (lastApprovalTs !== 0) showAutoApprovalNotice(d.last_approval_agent || "");
          lastApprovalTs = d.last_approval;
        }
      } catch (_) {}
    };
    refreshAutoMode();
    setInterval(refreshAutoMode, 3000);
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
    const DP_GIT_BATCH = 50;
    const DP_GIT_POLL_INTERVAL_MS = 3000;
    const hasDesktopRightPanelOverlay = () => (
      document.documentElement.dataset.tauriApp === "1"
      && document.documentElement.dataset.hubIframeChat === "1"
      && document.documentElement.dataset.mobile !== "1"
    );
    let dpPanelOpen = false;
    const dpGitSummaryPinnedStorageKey = () => `multiagent_git_summary_pinned:${String(currentSessionName || "").trim() || "__none"}`;
    let dpGitSummaryPinned = false;
    let _dpGitSummaryPinnedLoadedForKey = "";
    const dpReadGitSummaryPinnedFromStorage = () => {
      try {
        dpGitSummaryPinned = window.localStorage?.getItem(dpGitSummaryPinnedStorageKey()) === "1";
      } catch (_) {
        dpGitSummaryPinned = false;
      }
    };
    const dpApplySummaryPinButtonPressed = (root) => {
      if (!root) return;
      root.querySelectorAll(".git-branch-summary-pin").forEach((btn) => {
        btn.setAttribute("aria-pressed", dpGitSummaryPinned ? "true" : "false");
        btn.classList.toggle("is-pinned", dpGitSummaryPinned);
        btn.title = dpGitSummaryPinned ? "ピンを外して右端の表示を消す" : "右ペインを閉じても右端にこの概要を表示";
      });
    };
    let _dpGitGlowClearTimer = null;
    const dpCancelWorktreeSummaryGlow = () => {
      if (_dpGitGlowClearTimer) {
        clearTimeout(_dpGitGlowClearTimer);
        _dpGitGlowClearTimer = null;
      }
      [dpGitContent?.querySelector(".git-branch-summary-wrap"), document.getElementById("gitPinnedSummaryInner")]
        .filter(Boolean)
        .forEach((root) => {
          root.querySelector(".git-branch-summary-row")?.classList.remove("git-worktree-glow");
        });
    };
    const dpKickWorktreeSummaryGlow = () => {
      const panelWrap = dpGitContent?.querySelector(".git-branch-summary-wrap");
      const pinnedInner = document.getElementById("gitPinnedSummaryInner");
      const stripShown = dpGitSummaryPinned && !dpPanelOpen;
      const rootEl = (dpPanelOpen && panelWrap)
        ? panelWrap
        : (stripShown && pinnedInner ? pinnedInner : (panelWrap || pinnedInner));
      if (!rootEl) return;
      const row = rootEl.querySelector(".git-branch-summary-row");
      if (!row) return;
      if (_dpGitGlowClearTimer) {
        clearTimeout(_dpGitGlowClearTimer);
        _dpGitGlowClearTimer = null;
      }
      row.classList.remove("git-worktree-glow");
      void row.offsetWidth;
      row.classList.add("git-worktree-glow");
      _dpGitGlowClearTimer = setTimeout(() => {
        row.classList.remove("git-worktree-glow");
        _dpGitGlowClearTimer = null;
      }, 950);
    };
    let dpActivePanelView = "repo";
    let dpRepoBrowserPath = "";
    let dpRepoDirCache = new Map();
    let dpRepoDirInFlight = new Map();
    let dpGitLoadedFor = "";
    let dpGitCommits = [];
    let dpGitNextOffset = 0;
    let dpGitTotalCommits = 0;
    let dpGitHasMore = false;
    let dpGitPageLoading = false;
    let dpGitLoadError = "";
    let dpGitLoadSeq = 0;
    let dpGitDetailContext = null;
    let dpGitDetailNeedsRefresh = false;
    let dpGitObserver = null;
    let dpGitHeaderSummaryState = null;
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
    const dpApplyGitOverviewHeader = () => {
      dpCancelWorktreeSummaryGlow();
      const rowHtml = dpGitHeaderSummaryState?.rowHtml || "";
      const panelWrap = dpGitContent?.querySelector(".git-branch-summary-wrap");
      const aside = document.getElementById("gitPinnedSummaryAside");
      const inner = document.getElementById("gitPinnedSummaryInner");
      const overlay = hasDesktopRightPanelOverlay();
      const stripShown = !!dpGitSummaryPinned && !dpPanelOpen;

      if (overlay && aside && inner) {
        aside.hidden = !stripShown;
      }

      if (stripShown && inner && overlay) {
        inner.innerHTML = rowHtml;
        dpApplySummaryPinButtonPressed(inner);
      } else if (dpPanelOpen && panelWrap) {
        panelWrap.innerHTML = rowHtml;
        dpApplySummaryPinButtonPressed(panelWrap);
      } else if (panelWrap) {
        panelWrap.innerHTML = rowHtml;
        dpApplySummaryPinButtonPressed(panelWrap);
      }

      if (overlay && aside && inner) dpApplyPanelWidth();
    };
    const dpSyncPinnedSummaryStrip = () => {
      dpApplyGitOverviewHeader();
    };
    const dpSetPanelMeta = () => {};
    const dpSyncPanelMeta = () => {};
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
    const syncDesktopRightPanelView = () => {};
    const setDesktopRightPanelView = (view) => {
      dpActivePanelView = view === "git" ? "git" : "repo";
      return dpActivePanelView;
    };
    const loadDesktopRightPanelView = ({ reset = false } = {}) => {
      if (!dpPanelOpen) return Promise.resolve();
      const gitP = dpLoadGitBranchPage({ reset: reset || dpGitLoadedFor !== (currentSessionName || "") });
      dpLoadRepoDir(dpRepoBrowserPath || "");
      return Promise.resolve(gitP);
    };
    let _dpGitPollTimer = null;
    let _dpGitPollFingerprint = null;
    let _dpGitPollInFlight = false;
    const dpGitStatusLinesDigest = (data) => {
      const lines = Array.isArray(data?.status_lines) ? data.status_lines : [];
      return lines.map((s) => String(s || "")).sort().join("\n");
    };
    const dpGitFingerprint = (data) => [
      data?.worktree_changed_paths ?? "",
      data?.worktree_added ?? "",
      data?.worktree_deleted ?? "",
      data?.worktree_fingerprint ?? "",
      data?.total_commits ?? "",
      (data?.recent_commits || []).slice(0, 5).map(c => c.hash).join(","),
      dpGitStatusLinesDigest(data),
    ].join("|");
    const dpSilentRefreshGit = async () => {
      if (dpGitPageLoading) return;
      if (!dpPanelOpen && !dpGitSummaryPinned) return;
      if (_dpGitPollInFlight) return;
      _dpGitPollInFlight = true;
      try {
        const params = new URLSearchParams({ offset: "0", limit: String(DP_GIT_BATCH), refresh: "1" });
        const res = await fetchWithTimeout(`/git-branch-overview?${params}`, {}, 5000);
        if (!res.ok) return;
        const data = await res.json();
        const fp = dpGitFingerprint(data);
        if (fp === _dpGitPollFingerprint) return;
        const isFirstPoll = _dpGitPollFingerprint === null;
        _dpGitPollFingerprint = fp;

        if (!dpPanelOpen && dpGitSummaryPinned) {
          dpGitHeaderSummaryState = dpBuildSummaryState(data);
          dpApplyGitOverviewHeader();
          if (!isFirstPoll && !dpGitDetailContext) dpKickWorktreeSummaryGlow();
          return;
        }

        let newHashes = null;
        if (!isFirstPoll && Array.isArray(data?.recent_commits) && dpGitCommits.length > 0) {
          const oldHashes = new Set(dpGitCommits.map(c => c.hash));
          newHashes = new Set();
          for (const c of data.recent_commits) {
            if (!oldHashes.has(c.hash)) newHashes.add(c.hash);
          }
          if (newHashes.size === 0) newHashes = null;
        }

        dpGitHeaderSummaryState = dpBuildSummaryState(data);
        dpSyncSummaryWrap({ flash: !isFirstPoll && !dpGitDetailContext });
        dpSyncPanelMeta();
        if (!dpGitDetailContext) {
          dpGitCommits = Array.isArray(data?.recent_commits) ? data.recent_commits.slice() : [];
          dpGitTotalCommits = Math.max(0, parseInt(data?.total_commits) || 0);
          dpGitNextOffset = Math.max(0, parseInt(data?.next_offset) || dpGitCommits.length);
          dpGitHasMore = !!data?.has_more;
          dpGitLoadedFor = currentSessionName || "";
          dpRenderCommitRows(dpGitCommits, { append: false, newHashes });
          dpUpdateLoadMoreUi();
          dpEnsureGitObserver();
        } else if (dpGitDetailContext.kind === "worktree" && dpGitDetailContext.wrapEl) {
          void dpRenderFileStatsInto(dpGitDetailContext.wrapEl, "", { allowUndo: true })
            .then(() => {
              if (dpGitDetailContext?.wrapEl && !dpGitDetailContext.wrapEl.querySelector(".git-commit-file-row")) {
                dpCloseGitDetail({ refreshList: true });
              }
            }).catch(() => {});
        }
      } catch (_) {
      } finally {
        _dpGitPollInFlight = false;
      }
    };
    const dpStopGitPoll = () => { if (_dpGitPollTimer) { clearInterval(_dpGitPollTimer); _dpGitPollTimer = null; } };
    const dpStartGitPoll = () => {
      dpStopGitPoll();
      _dpGitPollTimer = setInterval(() => { void dpSilentRefreshGit(); }, DP_GIT_POLL_INTERVAL_MS);
    };
    const dpToggleGitSummaryPinned = () => {
      dpGitSummaryPinned = !dpGitSummaryPinned;
      try {
        window.localStorage?.setItem(dpGitSummaryPinnedStorageKey(), dpGitSummaryPinned ? "1" : "0");
      } catch (_) {}
      if (dpGitSummaryPinned) {
        dpStartGitPoll();
        if (!dpGitHeaderSummaryState?.rowHtml) void dpBootstrapPinnedGitSummary();
        else dpSyncPinnedSummaryStrip();
      } else {
        if (!dpPanelOpen) dpStopGitPoll();
        dpSyncPinnedSummaryStrip();
      }
    };
    const dpBootstrapPinnedGitSummary = async () => {
      if (!hasDesktopRightPanelOverlay() || !dpGitSummaryPinned) return;
      try {
        const params = new URLSearchParams({ offset: "0", limit: String(DP_GIT_BATCH), refresh: "1" });
        const res = await fetchWithTimeout(`/git-branch-overview?${params}`, {}, 5000);
        if (!res.ok) return;
        const data = await res.json();
        dpGitHeaderSummaryState = dpBuildSummaryState(data);
        dpApplyGitOverviewHeader();
        _dpGitPollFingerprint = dpGitFingerprint(data);
      } catch (_) {}
    };
    const dpOnSessionSummaryPinReload = ({ force = false } = {}) => {
      const storageKey = dpGitSummaryPinnedStorageKey();
      if (!force && _dpGitSummaryPinnedLoadedForKey === storageKey) return;
      _dpGitSummaryPinnedLoadedForKey = storageKey;
      dpReadGitSummaryPinnedFromStorage();
      _dpGitPollFingerprint = null;
      if (dpGitSummaryPinned) {
        void dpBootstrapPinnedGitSummary();
        dpStartGitPoll();
      } else if (!dpPanelOpen) {
        dpStopGitPoll();
      }
      dpSyncPinnedSummaryStrip();
      dpApplyPanelWidth();
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
      dpStartGitPoll();
      notifyParentPanelState();
      return loadP;
    };
    const closeDesktopRightPanel = () => {
      if (!desktopRightPanel) return;
      dpStopPanelResize();
      if (!dpGitSummaryPinned) dpStopGitPoll();
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
    const dpGitCountsHtml = (ins, dels) => {
      const safeIns = Math.max(0, parseInt(ins) || 0);
      const safeDels = Math.max(0, parseInt(dels) || 0);
      const cleanClass = (safeIns || safeDels) ? "" : " clean";
      return `<span class="git-branch-summary-counts${cleanClass}"><span class="git-branch-summary-count ins">+${safeIns}</span><span class="git-branch-summary-count del">-${safeDels}</span></span>`;
    };
    const dpGitPathCountText = (count) => {
      const safeCount = Math.max(0, parseInt(count) || 0);
      return `${safeCount} ${safeCount === 1 ? "path" : "paths"}`;
    };
    const dpLoadingHtml = () => '<span class="inline-loading"><span class="inline-loading-spinner" aria-hidden="true"></span></span>';
    const DP_GIT_SUMMARY_PIN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-6-4.35-6-10a6 6 0 1 1 12 0c0 5.65-6 10-6 10Z"/><circle cx="12" cy="11" r="2.25"/></svg>';
    const dpBuildSummaryHtml = (data) => {
      const changedPaths = parseInt(data?.worktree_changed_paths) || 0;
      const worktreeAdded = parseInt(data?.worktree_added) || 0;
      const worktreeDeleted = parseInt(data?.worktree_deleted) || 0;
      const worktreeClickable = !!data?.worktree_has_diff;
      const worktreeLabel = changedPaths ? "Uncommitted changes" : "Working tree clean";
      const worktreeMeta = changedPaths
        ? `<span class="git-branch-summary-meta-text">${dpGitPathCountText(changedPaths)}</span>`
        : `<span class="git-branch-summary-meta-text">No changes</span>`;
      const worktreeCounts = dpGitCountsHtml(worktreeAdded, worktreeDeleted);
      const icon = '<span class="git-branch-summary-icon-wrap"><svg class="git-branch-summary-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M9 10h6"/><path d="M12 7v6"/><path d="M9 17h6"/></svg></span>';
      const chevron = worktreeClickable
        ? '<svg class="git-commit-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>'
        : "";
      const pinBtn = `<button type="button" class="git-branch-summary-pin" aria-pressed="false" aria-label="未コミット概要をチャット右端に固定表示" title="右ペインを閉じても右端にこの概要を表示">${DP_GIT_SUMMARY_PIN_SVG}</button>`;
      return `<div class="git-branch-summary-row${worktreeClickable ? " clickable" : ""}"${worktreeClickable ? ' data-diff-kind="worktree"' : ""}>${icon}<div class="git-commit-info"><div class="git-branch-summary-label">${escapeHtml(worktreeLabel)}</div><div class="git-commit-meta">${worktreeMeta}${worktreeCounts}</div></div>${pinBtn}${chevron}</div>`;
    };
    const dpBuildSummaryState = (data) => {
      const changedPaths = Math.max(0, parseInt(data?.worktree_changed_paths) || 0);
      const worktreeAdded = Math.max(0, parseInt(data?.worktree_added) || 0);
      const worktreeDeleted = Math.max(0, parseInt(data?.worktree_deleted) || 0);
      const summaryBits = changedPaths
        ? ["Uncommitted changes", dpGitPathCountText(changedPaths), `+${worktreeAdded}`, `-${worktreeDeleted}`]
        : ["Working tree clean"];
      return {
        text: summaryBits.join(" · "),
        subject: changedPaths ? "Uncommitted changes" : "Working tree clean",
        clickable: !!data?.worktree_has_diff,
        rowHtml: dpBuildSummaryHtml(data),
      };
    };
    const dpBuildCommitRowHtml = (commit, { animate = false } = {}) => {
      const agent = commit?.agent || "";
      let iconInner;
      if (agent && AGENT_ICON_NAMES.has(agentBaseName(agent))) {
        const sub = agentIconInstanceSubHtml(agent);
        iconInner = `<span class="agent-icon-slot"><img class="git-commit-icon" src="${escapeHtml(agentIconSrc(agent))}" alt="${escapeHtml(agent)}">${sub}</span>`;
      } else {
        iconInner = '<span class="git-commit-icon-placeholder"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg></span>';
      }
      const timeHtml = `<span class="git-commit-time">${escapeHtml(commit?.time || "")}</span>`;
      const subjHtml = `<div class="git-commit-subject">${escapeHtml(commit?.subject || "")}</div>`;
      const ins = Math.max(0, parseInt(commit?.ins) || 0);
      const dels = Math.max(0, parseInt(commit?.dels) || 0);
      const changedPaths = Math.max(0, parseInt(commit?.changed_paths) || 0);
      const pathMeta = `<span class="git-branch-summary-meta-text">${dpGitPathCountText(changedPaths)}</span>`;
      const statHtml = dpGitCountsHtml(ins, dels);
      const chevron = '<svg class="git-commit-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>';
      const animClass = animate ? " new-commit-slide" : "";
      return `<div class="git-commit-row${animClass}" data-hash="${escapeHtml(commit?.hash || "")}"><span class="git-commit-icon-wrap">${iconInner}</span><div class="git-commit-info">${subjHtml}<div class="git-commit-meta">${timeHtml}${pathMeta}${statHtml}</div></div>${chevron}</div>`;
    };
    const dpBuildFileRowHtml = (entry, { allowUndo = false } = {}) => {
      const path = String(entry?.path || "").trim();
      const ins = Math.max(0, parseInt(entry?.ins) || 0);
      const dels = Math.max(0, parseInt(entry?.dels) || 0);
      const changed = Math.max(0, parseInt(entry?.changed) || (ins + dels));
      const binary = !!entry?.binary;
      const lineMeta = binary ? "binary" : `${changed} ${changed === 1 ? "line" : "lines"}`;
      const undoHtml = allowUndo
        ? `<button type="button" class="git-commit-file-undo" data-path="${escapeHtml(path)}" aria-label="Undo ${escapeHtml(path)}" title="Undo"><svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14H6L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4h6v2"></path></svg></button>`
        : "";
      const slashIdx = path.lastIndexOf("/");
      const fileName = slashIdx >= 0 ? path.slice(slashIdx + 1) : path;
      const dirPath = slashIdx >= 0 ? path.slice(0, slashIdx) : "";
      const pathInner = dirPath
        ? `<span class="git-commit-file-name">${escapeHtml(fileName)}</span><span class="git-commit-file-dir">${escapeHtml(dirPath)}</span>`
        : `<span class="git-commit-file-name">${escapeHtml(fileName)}</span>`;
      const ext = extFromPath(path);
      const iconSvg = FILE_ICONS[ext] || FILE_SVG_ICONS.file;
      const iconHtml = `<span class="git-commit-file-icon">${iconSvg}</span>`;
      const undoClass = allowUndo ? " has-undo" : "";
      return `<div class="git-commit-file-row clickable${undoClass}" data-path="${escapeHtml(path)}"><div class="git-commit-file-header">${iconHtml}<div class="git-commit-file-top"><div class="git-commit-file-path" title="${escapeHtml(path)}">${pathInner}</div></div><div class="git-commit-file-meta"><span class="git-branch-summary-meta-text">${escapeHtml(lineMeta)}</span>${dpGitCountsHtml(ins, dels)}</div>${undoHtml}</div></div>`;
    };
    const dpDisconnectGitObserver = () => {
      if (!dpGitObserver) return;
      try { dpGitObserver.disconnect(); } catch (_) {}
      dpGitObserver = null;
    };
    const dpGitCommitListEl = () => dpGitContent?.querySelector(".git-branch-commit-list");
    const dpGitLoadMoreEl = () => dpGitContent?.querySelector(".git-branch-load-more");
    const dpRenderCommitRows = (commits, { append = false, newHashes = null } = {}) => {
      const listEl = dpGitCommitListEl();
      if (!listEl) return;
      if (!append) {
        if (!commits.length) {
          listEl.innerHTML = '<div class="dp-empty-state" data-git-branch-empty="1">No commits</div>';
          return;
        }
        listEl.innerHTML = commits.map(c => {
          const isNew = newHashes && newHashes.has(c.hash);
          return dpBuildCommitRowHtml(c, { animate: isNew });
        }).join("");
        return;
      }
      if (!commits.length) return;
      listEl.querySelector("[data-git-branch-empty]")?.remove();
      listEl.insertAdjacentHTML("beforeend", commits.map(c => dpBuildCommitRowHtml(c)).join(""));
    };
    const dpUpdateLoadMoreUi = () => {
      const btn = dpGitLoadMoreEl();
      if (!btn) return;
      if (!dpGitHasMore && !dpGitLoadError) {
        btn.hidden = true;
        btn.disabled = true;
        btn.textContent = "";
        return;
      }
      btn.hidden = false;
      btn.disabled = dpGitPageLoading;
      if (dpGitLoadError) {
        btn.innerHTML = "Retry loading commits";
      } else if (dpGitPageLoading) {
        btn.innerHTML = dpLoadingHtml();
      } else if (dpGitTotalCommits > 0) {
        btn.textContent = `Load more (${dpGitCommits.length}/${dpGitTotalCommits})`;
      } else {
        btn.textContent = "Load more commits";
      }
    };
    const dpEnsureGitObserver = () => {
      dpDisconnectGitObserver();
      const btn = dpGitLoadMoreEl();
      if (!btn || !dpGitHasMore || dpGitPageLoading || dpGitLoadError || typeof IntersectionObserver !== "function") return;
      dpGitObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) void dpLoadGitBranchPage();
        });
      }, { root: dpGitContent?.querySelector(".git-branch-commit-scroll") ?? dpGitContent, rootMargin: "220px 0px", threshold: 0.01 });
      dpGitObserver.observe(btn);
    };
    const dpRenderGitShell = (data) => {
      if (!dpGitContent) return;
      dpGitContent.innerHTML = `
        <div class="dp-pane-title">Git</div>
        <div class="git-branch-stack">
          <div class="git-branch-list-view">
            <div class="git-branch-summary-wrap"></div>
            <div class="git-branch-commit-scroll">
              <div class="git-branch-commit-list"></div>
              <button type="button" class="git-branch-load-more" hidden></button>
            </div>
          </div>
          <div class="git-branch-detail-view">
            <button type="button" class="git-commit-detail-head" aria-label="Back"></button>
            <div class="git-commit-detail-body"></div>
          </div>
        </div>`;
    };
    const dpSyncSummaryWrap = ({ flash = false } = {}) => {
      dpApplyGitOverviewHeader();
      if (flash) dpKickWorktreeSummaryGlow();
    };
    const dpApplyGitPage = (data, { reset = false, newHashes = null } = {}) => {
      const commits = Array.isArray(data?.recent_commits) ? data.recent_commits : [];
      if (reset) {
        dpRenderGitShell(data || {});
        dpGitCommits = [];
      }
      dpGitHeaderSummaryState = dpBuildSummaryState(data || {});
      _dpGitPollFingerprint = dpGitFingerprint(data || {});
      dpSyncSummaryWrap();
      dpSyncPanelMeta();
      if (commits.length) {
        dpGitCommits = reset ? commits.slice() : dpGitCommits.concat(commits);
      } else if (reset) {
        dpGitCommits = [];
      }
      dpGitTotalCommits = Math.max(0, parseInt(data?.total_commits) || 0);
      dpGitNextOffset = Math.max(0, parseInt(data?.next_offset) || dpGitCommits.length);
      dpGitHasMore = !!data?.has_more;
      if (reset) {
        dpRenderCommitRows(dpGitCommits, { append: false, newHashes });
      } else if (commits.length) {
        dpRenderCommitRows(commits, { append: true });
      }
      dpUpdateLoadMoreUi();
      dpEnsureGitObserver();
    };
    const dpPostOpenFileInEditor = async (rawPath, line = 0, { diff = false, commitHash = "" } = {}) => {
      const normalizedPath = normalizeWorkspaceFilePath(rawPath);
      if (!normalizedPath) return;
      const normalizedLine = Number.isFinite(line) && line > 0 ? Math.floor(line) : 0;
      const payload = { path: normalizedPath, line: normalizedLine };
      if (diff) {
        payload.diff = true;
        payload.commit_hash = String(commitHash || "").trim();
      }
      const tryPost = () => fetch("/open-file-in-editor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const okMsg = diff ? `Diff opened: ${normalizedPath}` : `Opened ${normalizedPath}`;
      const errMsg = diff ? "Failed to open diff in editor." : "Failed to open file in editor.";
      try {
        let res = await tryPost();
        if (!res.ok && (res.status >= 500 || res.status === 429)) {
          await sleep(220);
          res = await tryPost();
        }
        if (!res.ok) {
          let detail = errMsg;
          try {
            const data = await res.json();
            if (data?.error) detail = data.error;
          } catch (_) {}
          throw new Error(detail);
        }
        setStatus(okMsg);
        setTimeout(() => setStatus(""), 1800);
      } catch (err) {
        setStatus(err?.message || errMsg, true);
        setTimeout(() => setStatus(""), 2600);
      }
    };
    const dpRenderFileStatsInto = async (wrapEl, hash, { allowUndo = false } = {}) => {
      if (!wrapEl) return null;
      wrapEl.innerHTML = `<div class="git-commit-file-empty inline-loading-row">${dpLoadingHtml()}</div>`;
      const res = await fetchWithTimeout(`/git-diff-files?hash=${encodeURIComponent(hash || "")}`, {}, 5000);
      const data = await res.json();
      const files = Array.isArray(data?.files) ? data.files : [];
      if (!files.length) {
        wrapEl.innerHTML = '<div class="git-commit-file-empty">No changed files</div>';
        return data;
      }
      wrapEl.innerHTML = `<div class="git-commit-file-list">${files.map((entry) => dpBuildFileRowHtml(entry, { allowUndo })).join("")}</div>`;
      return data;
    };
    const dpCloseGitDetail = ({ refreshList = false } = {}) => {
      if (!dpGitContent) return;
      const stack = dpGitContent.querySelector(".git-branch-stack");
      stack?.classList.remove("git-branch-transitioning", "git-branch-mode-detail");
      const body = dpGitContent.querySelector(".git-commit-detail-body");
      const head = dpGitContent.querySelector(".git-commit-detail-head");
      if (body) body.innerHTML = "";
      if (head) head.innerHTML = "";
      dpGitDetailContext = null;
      dpSyncPanelMeta();
      dpUpdateLoadMoreUi();
      dpEnsureGitObserver();
      const shouldRefresh = !!refreshList;
      dpGitDetailNeedsRefresh = false;
      if (shouldRefresh) void dpLoadGitBranchPage({ reset: true });
    };
    const dpLoadGitBranchPage = async ({ reset = false } = {}) => {
      if ((!dpPanelOpen && !dpGitSummaryPinned) || !dpGitContent) return;
      if (dpGitPageLoading) return;
      if (!reset && !dpGitHasMore && !dpGitLoadError) return;
      const loadSeq = ++dpGitLoadSeq;
      dpGitPageLoading = true;
      dpGitLoadError = "";
      dpDisconnectGitObserver();
      if (reset) {
        dpCloseGitDetail();
        dpGitHasMore = false;
        dpGitNextOffset = 0;
        dpGitTotalCommits = 0;
        dpGitCommits = [];
        dpGitContent.innerHTML = `<div class="dp-pane-title">Git</div><div class="dp-empty-state inline-loading-row">${dpLoadingHtml()}</div>`;
      } else {
        dpUpdateLoadMoreUi();
      }
      try {
        const params = new URLSearchParams({ offset: String(reset ? 0 : dpGitNextOffset), limit: String(DP_GIT_BATCH) });
        if (reset) params.set("refresh", "1");
        const res = await fetchWithTimeout(`/git-branch-overview?${params.toString()}`, {}, 5000);
        if (!res.ok) throw new Error("Failed to load branch overview");
        const data = await res.json();
        if (loadSeq !== dpGitLoadSeq) return;
        dpApplyGitPage(data, { reset });
        dpGitLoadedFor = currentSessionName || "";
      } catch (err) {
        if (loadSeq !== dpGitLoadSeq) return;
        if (reset) {
          dpGitLoadedFor = "";
          dpGitContent.innerHTML = `<div class="dp-pane-title">Git</div><div class="dp-empty-state">${escapeHtml(err?.message || "Load failed")}</div>`;
        } else {
          dpGitLoadError = err?.message || "Load failed";
        }
      } finally {
        if (loadSeq !== dpGitLoadSeq) return;
        dpGitPageLoading = false;
        dpUpdateLoadMoreUi();
        dpEnsureGitObserver();
      }
    };
    const dpOpenGitDetail = async ({ diffKind = "", hash = "", rowHtml = "", subject = "" } = {}) => {
      if (!dpGitContent) return;
      const stack = dpGitContent.querySelector(".git-branch-stack");
      if (!stack) return;
      dpCloseGitDetail();
      dpDisconnectGitObserver();
      dpGitDetailNeedsRefresh = false;
      stack.classList.add("git-branch-transitioning");
      const headEl = dpGitContent.querySelector(".git-commit-detail-head");
      const bodyEl = dpGitContent.querySelector(".git-commit-detail-body");
      if (headEl) {
        headEl.title = subject;
        headEl.innerHTML = rowHtml;
      }
      if (!bodyEl) return;
      const wrapEl = document.createElement("div");
      wrapEl.className = "git-commit-file-wrap";
      bodyEl.appendChild(wrapEl);
      stack.classList.add("git-branch-mode-detail");
      dpGitDetailContext = {
        kind: diffKind === "worktree" ? "worktree" : "commit",
        hash: diffKind === "worktree" ? "" : hash,
        wrapEl,
      };
      dpSyncPanelMeta();
      dpGitContent.scrollTop = 0;
      requestAnimationFrame(() => stack.classList.remove("git-branch-transitioning"));
      try {
        await dpRenderFileStatsInto(wrapEl, diffKind === "worktree" ? "" : hash, { allowUndo: diffKind === "worktree" });
      } catch (_) {
        wrapEl.innerHTML = '<div class="git-commit-file-empty">Failed to load file stats</div>';
      }
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
    dpGitContent?.addEventListener("click", async (event) => {
      if (event.target.closest(".git-branch-summary-pin")) {
        event.preventDefault();
        event.stopPropagation();
        dpToggleGitSummaryPinned();
        return;
      }
      if (!dpPanelOpen) return;
      const loadMoreBtn = event.target.closest(".git-branch-load-more");
      if (loadMoreBtn) {
        event.preventDefault();
        event.stopPropagation();
        await dpLoadGitBranchPage();
        return;
      }
      const fileRow = event.target.closest(".git-commit-file-row");
      if (fileRow && !event.target.closest(".git-commit-file-undo")) {
        event.preventDefault();
        const p = String(fileRow.dataset.path || "").trim();
        if (p) {
          await dpPostOpenFileInEditor(p, 0, {
            diff: true,
            commitHash: dpGitDetailContext?.hash || "",
          });
        }
        return;
      }
      const undoBtn = event.target.closest(".git-commit-file-undo");
      if (undoBtn) {
        event.preventDefault();
        event.stopPropagation();
        const filePath = String(undoBtn.dataset.path || "").trim();
        if (!filePath || undoBtn.dataset.busy === "1") return;
        undoBtn.dataset.busy = "1";
        undoBtn.disabled = true;
        setStatus(`undoing ${filePath}...`);
        try {
          const response = await fetch("/git-restore-file", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: filePath }),
          });
          const payload = await response.json().catch(() => ({}));
          if (!response.ok || !payload?.ok) throw new Error(payload?.error || "undo failed");
          setStatus(`restored ${filePath}`);
          setTimeout(() => setStatus(""), 1800);
          dpGitDetailNeedsRefresh = true;
          if (dpGitDetailContext?.kind === "worktree" && dpGitDetailContext?.wrapEl) {
            await dpRenderFileStatsInto(dpGitDetailContext.wrapEl, "", { allowUndo: true });
            if (!dpGitDetailContext.wrapEl.querySelector(".git-commit-file-row")) {
              dpCloseGitDetail({ refreshList: true });
            }
          }
        } catch (err) {
          setStatus(err?.message || "undo failed", true);
        } finally {
          delete undoBtn.dataset.busy;
          undoBtn.disabled = false;
        }
        return;
      }
      if (event.target.closest(".git-commit-detail-head")) {
        event.preventDefault();
        event.stopPropagation();
        dpCloseGitDetail({ refreshList: dpGitDetailNeedsRefresh });
        return;
      }
      const stack = dpGitContent.querySelector(".git-branch-stack");
      if (stack?.classList.contains("git-branch-mode-detail")) return;
      const row = event.target.closest(".git-commit-row, .git-branch-summary-row");
      if (!row) return;
      const diffKind = row.dataset.diffKind || "";
      const hash = String(row.dataset.hash || "");
      if (!hash && !diffKind) return;
      event.preventDefault();
      event.stopPropagation();
      const subject = diffKind === "worktree"
        ? (row.querySelector(".git-branch-summary-label")?.textContent?.trim() || "Uncommitted changes")
        : (row.querySelector(".git-commit-subject")?.textContent?.trim() || hash.slice(0, 7));
      await dpOpenGitDetail({ diffKind, hash, rowHtml: row.outerHTML, subject });
    });
    document.getElementById("gitPinnedSummaryAside")?.addEventListener("click", async (event) => {
      if (event.target.closest(".git-branch-summary-pin")) {
        event.preventDefault();
        event.stopPropagation();
        dpToggleGitSummaryPinned();
        return;
      }
      const row = event.target.closest('.git-branch-summary-row[data-diff-kind="worktree"]');
      if (!row || !dpGitContent) return;
      event.preventDefault();
      event.stopPropagation();
      const needReset = !dpGitContent.querySelector(".git-branch-stack")
        || dpGitLoadedFor !== (currentSessionName || "");
      await openDesktopRightPanel({ view: "git", reset: needReset });
      await dpOpenGitDetail({
        diffKind: "worktree",
        hash: "",
        rowHtml: row.outerHTML,
        subject: row.querySelector(".git-branch-summary-label")?.textContent?.trim() || "Uncommitted changes",
      });
    });
    const dpNormalizePath = (value) => String(value || "").replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
    const dpFolderIcon = wrapFileIcon('<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h5.1a1.5 1.5 0 0 1 1.06.44l1.9 1.9a1.5 1.5 0 0 0 1.06.44H19.5A1.5 1.5 0 0 1 21 9.28V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>');
    const dpChevronIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 6 15 12 9 18"/></svg>';
    const dpBackIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 6 9 12 15 18"/></svg>';
    const dpFetchRepoDir = async (rawPath) => {
      const path = dpNormalizePath(rawPath);
      if (dpRepoDirCache.has(path)) return dpRepoDirCache.get(path);
      if (dpRepoDirInFlight.has(path)) return dpRepoDirInFlight.get(path);
      const loadPromise = (async () => {
        const res = await fetchWithTimeout(`/files-dir?path=${encodeURIComponent(path)}`, {}, 12000);
        if (!res.ok) throw new Error(res.status === 404 ? "Directory not found" : "Failed to load directory");
        const payload = await res.json().catch(() => ({}));
        const rawEntries = Array.isArray(payload?.entries) ? payload.entries : [];
        const entries = rawEntries
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
        dpRepoDirCache.set(path, entries);
        return entries;
      })().finally(() => dpRepoDirInFlight.delete(path));
      dpRepoDirInFlight.set(path, loadPromise);
      return loadPromise;
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
      dpSyncPanelMeta();
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
    dpOnSessionSummaryPinReload({ force: true });
    dpApplyPanelWidth();
    syncDesktopRightPanelView();
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
