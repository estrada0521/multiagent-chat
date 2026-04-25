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
      hubPingParentForSafariChrome(); // initial tickle
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
        /* immediateFocus: mobile OSes need focus in the same user-gesture turn; deferring with rAF often skips the keyboard. */
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
    const fileModal = document.getElementById("fileModal");
    const fileModalFrame = document.getElementById("fileModalFrame");
    const fileModalTitle = document.getElementById("fileModalTitle");
    const fileModalBackBtn = document.getElementById("fileModalBackBtn");
    const fileModalCloseBtn = document.getElementById("fileModalCloseBtn");
    const fileModalThemeToggleBtn = document.getElementById("fileModalThemeToggleBtn");
    const fileModalThemeToggleIcon = document.getElementById("fileModalThemeToggleIcon");
    const fileModalHtmlModeBtn = document.getElementById("fileModalHtmlModeBtn");
    const fileModalHtmlModeIcon = document.getElementById("fileModalHtmlModeIcon");
    const fileModalOpenEditorBtn = document.getElementById("fileModalOpenEditorBtn");
    const cameraMode = document.getElementById("cameraMode");
    const cameraModeShell = document.getElementById("cameraModeShell");
    const cameraModeVideo = document.getElementById("cameraModeVideo");
    const cameraModeCloseBtn = document.getElementById("cameraModeCloseBtn");
    const cameraModeTargetRail = document.getElementById("cameraModeTargetRail");
    const cameraModeTargetToggleBtn = document.getElementById("cameraModeTargetToggleBtn");
    const cameraModeTargets = document.getElementById("cameraModeTargets");
    const cameraModeReplies = document.getElementById("cameraModeReplies");
    const cameraModeRepliesInner = document.getElementById("cameraModeRepliesInner");
    const cameraModeThinking = document.getElementById("cameraModeThinking");
    const cameraModeHint = document.getElementById("cameraModeHint");
    const cameraModeEmpty = document.getElementById("cameraModeEmpty");
    const cameraModeEmptyCopy = document.getElementById("cameraModeEmptyCopy");
    const cameraModeMicBtn = document.getElementById("cameraModeMicBtn");
    const cameraModeShutterBtn = document.getElementById("cameraModeShutterBtn");
    const cameraModeBackdropBtn = document.getElementById("cameraModeBackdropBtn");
    let fileModalCurrentPath = "";
    let fileModalCurrentExt = "";
    let fileModalPreviewTheme = "dark";
    let fileModalHtmlPreviewMode = "text";
    let _fileModalScrollBridgeCleanup = null;
    let lastFocusedElement = null;
    const _fileExistenceCache = new Map();
    const FILE_MODAL_THEME_ICONS = {
      dark: '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>',
      light: '<path d="M21 12.79A9 9 0 1 1 11.21 3c0 0 0 0 0 0A7 7 0 0 0 21 12.79z"></path>',
    };
    const FILE_MODAL_HTML_MODE_ICONS = {
      web: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"></rect><path d="M3.5 9.5h17"></path><circle cx="7.5" cy="7" r="0.8" fill="currentColor" stroke="none"></circle><circle cx="10.5" cy="7" r="0.8" fill="currentColor" stroke="none"></circle><path d="M9.5 13.5h6"></path><path d="M9.5 16.5h4"></path>',
      text: '<path d="M14 3.5H7.5A2.5 2.5 0 0 0 5 6v12a2.5 2.5 0 0 0 2.5 2.5h9A2.5 2.5 0 0 0 19 18V8.5z"></path><path d="M14 3.5V8.5H19"></path><path d="M9 12.5h6"></path><path d="M9 16h6"></path>',
    };
    const isHtmlPreviewExt = (ext) => ext === "html" || ext === "htm";
    const applyFileModalThemeDirect = () => {
      if (fileModalCurrentExt !== "md") return false;
      try {
        const frameWindow = fileModalFrame.contentWindow;
        const frameDoc = fileModalFrame.contentDocument || frameWindow?.document || null;
        if (typeof frameWindow?.__agentIndexApplyPreviewTheme === "function") {
          frameWindow.__agentIndexApplyPreviewTheme(fileModalPreviewTheme);
          return true;
        }
        if (frameDoc?.documentElement) {
          frameDoc.documentElement.setAttribute(
            "data-preview-theme",
            fileModalPreviewTheme === "light" ? "light" : "dark",
          );
          return true;
        }
      } catch (_) { }
      return false;
    };
    const postFileModalTheme = () => {
      if (fileModalCurrentExt !== "md") return;
      applyFileModalThemeDirect();
      try {
        fileModalFrame.contentWindow?.postMessage(
          { type: "agent-index-file-preview-theme", theme: fileModalPreviewTheme },
          window.location.origin,
        );
      } catch (_) { }
      requestAnimationFrame(() => { applyFileModalThemeDirect(); });
      setTimeout(() => { applyFileModalThemeDirect(); }, 60);
    };
    const applyFileModalHtmlPreviewModeDirect = () => {
      if (!isHtmlPreviewExt(fileModalCurrentExt)) return false;
      try {
        const frameWindow = fileModalFrame.contentWindow;
        const frameDoc = fileModalFrame.contentDocument || frameWindow?.document || null;
        const nextMode = fileModalHtmlPreviewMode === "text" ? "text" : "web";
        if (typeof frameWindow?.__agentIndexApplyHtmlPreviewMode === "function") {
          frameWindow.__agentIndexApplyHtmlPreviewMode(nextMode);
          return true;
        }
        if (frameDoc?.documentElement) {
          frameDoc.documentElement.setAttribute("data-preview-mode", nextMode);
          return true;
        }
      } catch (_) { }
      return false;
    };
    const postFileModalHtmlPreviewMode = () => {
      if (!isHtmlPreviewExt(fileModalCurrentExt)) return;
      applyFileModalHtmlPreviewModeDirect();
      try {
        fileModalFrame.contentWindow?.postMessage(
          { type: "agent-index-file-preview-mode", mode: fileModalHtmlPreviewMode },
          window.location.origin,
        );
      } catch (_) { }
      requestAnimationFrame(() => { applyFileModalHtmlPreviewModeDirect(); });
      setTimeout(() => { applyFileModalHtmlPreviewModeDirect(); }, 60);
      requestAnimationFrame(() => { bindFileModalScrollBridge(); });
      setTimeout(() => { bindFileModalScrollBridge(); }, 120);
    };
    const syncFileModalThemeToggle = () => {
      if (!fileModalThemeToggleBtn || !fileModalThemeToggleIcon) return;
      const isMd = fileModalCurrentExt === "md";
      fileModalThemeToggleBtn.hidden = !isMd;
      if (!isMd) return;
      const nextLabel = fileModalPreviewTheme === "dark" ? "Switch markdown preview to light" : "Switch markdown preview to dark";
      fileModalThemeToggleBtn.title = nextLabel;
      fileModalThemeToggleBtn.setAttribute("aria-label", nextLabel);
      fileModalThemeToggleIcon.innerHTML = FILE_MODAL_THEME_ICONS[fileModalPreviewTheme] || FILE_MODAL_THEME_ICONS.dark;
    };
    const syncFileModalHtmlModeToggle = () => {
      if (!fileModalHtmlModeBtn || !fileModalHtmlModeIcon) return;
      const isHtml = isHtmlPreviewExt(fileModalCurrentExt);
      fileModalHtmlModeBtn.hidden = !isHtml;
      if (!isHtml) return;
      const nextMode = fileModalHtmlPreviewMode === "text" ? "web" : "text";
      const title = nextMode === "text" ? "Switch HTML preview to text" : "Switch HTML preview to web";
      fileModalHtmlModeBtn.title = title;
      fileModalHtmlModeBtn.setAttribute("aria-label", title);
      fileModalHtmlModeIcon.innerHTML = FILE_MODAL_HTML_MODE_ICONS[nextMode] || FILE_MODAL_HTML_MODE_ICONS.text;
    };
    const syncFileModalShellTheme = () => {
      if (!fileModal) return;
      const useLightShell = fileModalCurrentExt === "md" && fileModalPreviewTheme === "light";
      fileModal.classList.toggle("theme-light", useLightShell);
    };
    const updateFileModalViewportMetrics = () => {
      fileModal.style.setProperty("--file-modal-top", "0px");
      fileModal.style.setProperty("--file-modal-left", "0px");
      fileModal.style.setProperty("--file-modal-width", "100vw");
    };
    const syncFileModalViewportMetrics = () => {
      if (fileModal.hidden) return;
      updateFileModalViewportMetrics();
    };
    const clearFileModalScrollBridge = ({ resetScrolled = true } = {}) => {
      if (typeof _fileModalScrollBridgeCleanup === "function") {
        try {
          _fileModalScrollBridgeCleanup();
        } catch (_) { }
      }
      _fileModalScrollBridgeCleanup = null;
      if (resetScrolled) fileModal.classList.remove("file-modal-scrolled");
    };
    const bindFileModalScrollBridge = () => {
      clearFileModalScrollBridge({ resetScrolled: false });
      if (fileModal.hidden) {
        fileModal.classList.remove("file-modal-scrolled");
        return;
      }
      let frameWindow = null;
      let frameDoc = null;
      try {
        frameWindow = fileModalFrame.contentWindow || null;
        frameDoc = fileModalFrame.contentDocument || frameWindow?.document || null;
      } catch (_) {
        fileModal.classList.remove("file-modal-scrolled");
        return;
      }
      if (!frameDoc?.documentElement) {
        fileModal.classList.remove("file-modal-scrolled");
        return;
      }
      const GRADIENT_SHOW_THRESHOLD = 12;
      const scrollTargets = [];
      const cleanupFns = [];
      const seenNodes = new Set();
      const addScrollTarget = (node) => {
        if (!node || seenNodes.has(node)) return;
        if (typeof node.addEventListener !== "function") return;
        seenNodes.add(node);
        scrollTargets.push(node);
      };
      const collectScrollTargets = (doc, depth = 0) => {
        if (!doc?.documentElement) return;
        addScrollTarget(doc.getElementById?.("viewContainer") || null);
        addScrollTarget(doc.querySelector?.(".md-preview-shell") || null);
        addScrollTarget(doc.getElementById?.("htmlTextViewContainer") || null);
        addScrollTarget(doc.querySelector?.(".html-preview-text-wrap") || null);
        addScrollTarget(doc.querySelector?.(".wrap") || null);
        addScrollTarget(doc.scrollingElement || doc.documentElement || doc.body);
        if (depth >= 1) return;
        const nestedFrames = Array.from(doc.querySelectorAll?.("iframe") || []);
        nestedFrames.forEach((frame) => {
          const handleNestedLoad = () => {
            requestAnimationFrame(() => bindFileModalScrollBridge());
          };
          frame.addEventListener("load", handleNestedLoad, { once: true });
          cleanupFns.push(() => frame.removeEventListener("load", handleNestedLoad));
          try {
            const childWin = frame.contentWindow || null;
            const childDoc = frame.contentDocument || childWin?.document || null;
            if (childDoc?.documentElement) collectScrollTargets(childDoc, depth + 1);
          } catch (_) { }
        });
      };
      const readScrollMetrics = (node) => {
        const scrollNode = node?.scrollingElement || node?.documentElement || node?.body || node;
        return {
          scrollTop: Number(scrollNode?.scrollTop || 0),
          clientHeight: Number(scrollNode?.clientHeight || 0),
          scrollHeight: Number(scrollNode?.scrollHeight || 0),
        };
      };
      collectScrollTargets(frameDoc, 0);
      if (!scrollTargets.length) {
        fileModal.classList.remove("file-modal-scrolled");
        return;
      }
      let lastScrollNode = null;
      let prevScrollTop = 0;
      const syncScrolledState = (scrollTop) => {
        fileModal.classList.toggle("file-modal-scrolled", Number(scrollTop || 0) > GRADIENT_SHOW_THRESHOLD);
      };
      const handleScroll = (event) => {
        const node = event.currentTarget;
        const { scrollTop: st } = readScrollMetrics(node);
        if (lastScrollNode !== node) {
          lastScrollNode = node;
          prevScrollTop = st;
          syncScrolledState(st);
          return;
        }
        prevScrollTop = st;
        syncScrolledState(st);
      };
      scrollTargets.forEach((node) => node.addEventListener("scroll", handleScroll, { passive: true }));
      _fileModalScrollBridgeCleanup = () => {
        scrollTargets.forEach((node) => node.removeEventListener("scroll", handleScroll));
        cleanupFns.forEach((fn) => fn());
      };
      const initial = readScrollMetrics(scrollTargets[0]);
      lastScrollNode = scrollTargets[0];
      prevScrollTop = initial.scrollTop;
      syncScrolledState(initial.scrollTop);
    };
    const closeFileModal = ({ restoreFocus = true } = {}) => {
      if (fileModal.hidden) return;
      clearFileModalScrollBridge();
      const focusTarget = restoreFocus ? lastFocusedElement : null;
      fileModal.classList.remove("visible");
      fileModal.classList.add("closing");
      document.body.classList.remove("file-modal-open");
      syncHeaderMenuFocus();
      setTimeout(() => {
        fileModal.hidden = true;
        fileModal.classList.remove("closing");
        fileModal.classList.remove("file-modal-from-repository");
        fileModal.classList.remove("file-modal-scrolled");
        fileModal.classList.remove("theme-light");
        fileModalFrame.removeAttribute("src");
        fileModalCurrentPath = "";
        fileModalCurrentExt = "";
        fileModalPreviewTheme = "dark";
        fileModalHtmlPreviewMode = "text";
        syncFileModalThemeToggle();
        syncFileModalHtmlModeToggle();
        if (fileModalBackBtn) fileModalBackBtn.hidden = true;
        if (fileModalOpenEditorBtn) fileModalOpenEditorBtn.hidden = true;
        window.removeEventListener("resize", syncFileModalViewportMetrics);
        window.removeEventListener("scroll", syncFileModalViewportMetrics, { capture: true });
        if (focusTarget && typeof focusTarget.focus === "function") {
          focusTarget.focus({ preventScroll: true });
        }
        lastFocusedElement = null;
      }, 300);
    };
    const openFileModal = (path, ext, sourceEl, triggerEvent) => {
      const normalizedExt = (ext || "").toLowerCase();
      const filename = (displayAttachmentFilename(path) || path || "Preview").trim();
      const viewerUrl = fileViewHrefForPath(path, { embed: true });
      const launchedFromRepository = !!(sourceEl && typeof sourceEl.closest === "function" && sourceEl.closest("#attachedFilesPanel"));
      fileModalCurrentPath = path;
      fileModalCurrentExt = normalizedExt;
      fileModalPreviewTheme = "dark";
      fileModalHtmlPreviewMode = "text";
      clearFileModalScrollBridge();
      fileModal.classList.remove("file-modal-scrolled");
      fileModal.classList.toggle("file-modal-from-repository", launchedFromRepository);
      if (fileModalBackBtn) fileModalBackBtn.hidden = !launchedFromRepository;
      syncFileModalThemeToggle();
      syncFileModalHtmlModeToggle();
      syncFileModalShellTheme();
      fileModalTitle.textContent = filename;
      lastFocusedElement = sourceEl || document.activeElement;

      // Prevent white flash by hiding iframe until it loads
      fileModalFrame.style.opacity = "0";
      fileModalFrame.onload = () => {
        fileModalFrame.style.transition = "opacity 200ms ease-out";
        fileModalFrame.style.opacity = "1";
        postFileModalTheme();
        postFileModalHtmlPreviewMode();
        bindFileModalScrollBridge();
        setTimeout(() => { bindFileModalScrollBridge(); }, 120);
      };
      fileModalFrame.src = viewerUrl;

      updateFileModalViewportMetrics();
      fileModal.hidden = false;
      fileModal.classList.add("visible");
      document.body.classList.add("file-modal-open");
      document.querySelector(".hub-page-header")?.classList.remove("header-hidden");
      syncHeaderMenuFocus();
      window.addEventListener("resize", syncFileModalViewportMetrics);
      window.addEventListener("scroll", syncFileModalViewportMetrics, { passive: true, capture: true });
    };
    const extFromPath = (path) => {
      const cleanPath = String(path || "").split(/[?#]/, 1)[0];
      const filename = cleanPath.split("/").pop() || "";
      if (!filename.includes(".")) return "";
      return filename.split(".").pop().toLowerCase();
    };
    const pathFromLocalHref = (href) => {
      const rawHref = String(href || "").trim();
      if (!rawHref || rawHref.startsWith("#") || rawHref.startsWith("//")) return "";
      try {
        const url = new URL(rawHref, window.location.href);
        if (url.origin === window.location.origin && ((CHAT_BASE_PATH && (url.pathname === `${CHAT_BASE_PATH}/file-raw` || url.pathname === `${CHAT_BASE_PATH}/file-view`)) || url.pathname === "/file-raw" || url.pathname === "/file-view")) {
          return url.searchParams.get("path") || "";
        }
      } catch (_) { }
      if (/^[a-z][a-z0-9+.-]*:/i.test(rawHref)) return "";
      if (rawHref.startsWith("/")) {
        if (/^\/(Users|private|var|tmp)\//.test(rawHref)) return rawHref.split(/[?#]/, 1)[0];
        return "";
      }
      const cleanHref = rawHref.split(/[?#]/, 1)[0];
      if (!cleanHref.includes("/")) return "";
      return cleanHref;
    };
    const decorateLocalFileLinks = (scope = document) => {
      if (!scope?.querySelectorAll) return;
      scope.querySelectorAll(".md-body a[href]").forEach((anchor) => {
        if (!anchor) return;
        const href = anchor.getAttribute("href") || "";
        const path = pathFromLocalHref(href);
        if (!path) return;
        anchor.classList.add("local-file-link");
        if (!anchor.dataset.filepath) anchor.dataset.filepath = path;
        if (!anchor.dataset.ext) anchor.dataset.ext = extFromPath(path);
        if (!anchor.title) anchor.title = path;
      });
    };
    const filePathFromLinkAnchor = (anchor) => {
      if (!anchor) return "";
      const fromDataset = String(anchor.dataset?.filepath || "").trim();
      if (fromDataset) return fromDataset;
      return pathFromLocalHref(anchor.getAttribute("href") || "");
    };
    const lineFromLinkAnchor = (anchor) => {
      if (!anchor) return 0;
      const raw = String(anchor.dataset?.line || "").trim();
      const n = parseInt(raw, 10);
      return Number.isFinite(n) && n > 0 ? n : 0;
    };
    const fileExistsOnDisk = async (path) => {
      const normalizedPath = String(path || "").trim();
      if (!normalizedPath) return false;
      const cached = _fileExistenceCache.get(normalizedPath);
      try {
        const res = await fetch("/files-exist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paths: [normalizedPath] }),
        });
        if (!res.ok) return false;
        const data = await res.json().catch(() => ({}));
        const exists = !!data?.[normalizedPath];
        _fileExistenceCache.set(normalizedPath, exists);
        return exists;
      } catch (_) {
        return cached === true;
      }
    };
    const openFileSurface = async (path, ext, sourceEl, triggerEvent) => {
      const normalizedPath = String(path || "").trim();
      if (!normalizedPath) return;
      if (isPublicChatView) {
        openFileModal(normalizedPath, ext, sourceEl, triggerEvent);
        return;
      }
      const exists = await fileExistsOnDisk(normalizedPath);
      if (!exists) {
        setStatus(`file not found: ${displayAttachmentFilename(normalizedPath) || normalizedPath}`, true);
        setTimeout(() => setStatus(""), 2200);
        return;
      }
      openFileModal(normalizedPath, ext, sourceEl, triggerEvent);
    };
    fileModal.addEventListener("click", (event) => {
      if (event.target.closest("[data-close-file-modal]")) {
        closeFileModal();
      }
    });
    fileModalCloseBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const launchedFromRepository = fileModal.classList.contains("file-modal-from-repository");
      closeFileModal({ restoreFocus: !launchedFromRepository });
      if (launchedFromRepository) {
        try { closeAttachedFilesSheet({ immediate: true }); } catch (_) { }
      }
    });
    fileModalBackBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      closeFileModal({ restoreFocus: false });
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !fileModal.hidden) {
        event.preventDefault();
        closeFileModal();
        return;
      }
      if (event.key === "Escape" && isComposerOverlayOpen()) {
        event.preventDefault();
        closeComposerOverlay({ restoreFocus: true });
      }
    });
    fileModalThemeToggleBtn?.addEventListener("click", () => {
      if (fileModalCurrentExt !== "md") return;
      fileModalPreviewTheme = fileModalPreviewTheme === "dark" ? "light" : "dark";
      syncFileModalThemeToggle();
      syncFileModalShellTheme();
      postFileModalTheme();
    });
    fileModalHtmlModeBtn?.addEventListener("click", () => {
      if (!isHtmlPreviewExt(fileModalCurrentExt)) return;
      fileModalHtmlPreviewMode = fileModalHtmlPreviewMode === "text" ? "web" : "text";
      syncFileModalHtmlModeToggle();
      postFileModalHtmlPreviewMode();
    });
    const scrollToBottomBtn = document.getElementById("scrollToBottomBtn");
__CHAT_INCLUDE:composer-overlay.js__    const updateScrollBtnPos = () => {
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
    let katexLoadPromise = null;
    const scopeNeedsMathRender = (node) => !!node?.querySelector?.(".math-render-needed");
    const clearMathMarkers = (node) => {
      node?.querySelectorAll?.(".math-render-needed").forEach((marker) => marker.remove());
    };
    const ensureKatexReady = async () => {
      if (typeof renderMathInElement === "function") return true;
      if (katexLoadPromise) return katexLoadPromise;
      katexLoadPromise = (async () => {
        const cssReady = await loadExternalStylesheetOnce(KATEX_CSS_HREF);
        const katexReady = await loadExternalScriptOnce(KATEX_JS_SRC);
        const autoRenderReady = katexReady ? await loadExternalScriptOnce(KATEX_AUTO_RENDER_SRC) : false;
        return cssReady && katexReady && autoRenderReady && typeof renderMathInElement === "function";
      })().catch(() => false);
      return katexLoadPromise;
    };
    const renderMathInScope = (node) => {
      if (!node || !scopeNeedsMathRender(node)) return;
      const applyMath = () => {
        if (typeof renderMathInElement === "undefined") return;
        renderMathInElement(node, mathRenderOptions);
        clearMathMarkers(node);
      };
      if (typeof renderMathInElement === "function") {
        applyMath();
        return;
      }
      ensureKatexReady().then((ready) => {
        if (ready) applyMath();
      });
    };
    // Mermaid diagram rendering — lazy-loaded only when a mermaid block appears
    let _mermaidReady = false;
    let _mermaidLoading = false;
    let _mermaidSeq = 0;
    const _mermaidQueue = [];
    // Color constants
    const DARK_BG = "__DARK_BG__";
    const getMermaidFontFamily = () => {
      const mode = document.documentElement.getAttribute("data-agent-font-mode");
      return mode === "gothic"
        ? '"anthropicSans","Anthropic Sans","SF Pro Text","Segoe UI","Hiragino Kaku Gothic ProN","Hiragino Sans","Meiryo",sans-serif'
        : '"anthropicSerif","Anthropic Serif","Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",Georgia,serif';
    };
    const initMermaid = () => {
      mermaid.initialize({
        startOnLoad: false,
        theme: "base",
        securityLevel: "loose",
        flowchart: { padding: 8, nodeSpacing: 30, rankSpacing: 40 },
        themeVariables: {
          background: DARK_BG,
          primaryColor: "rgb(30,30,30)",
          primaryBorderColor: "rgb(252,252,252)",
          primaryTextColor: "rgb(252,252,252)",
          secondaryColor: "rgb(30,30,30)",
          secondaryBorderColor: "rgb(252,252,252)",
          secondaryTextColor: "rgb(252,252,252)",
          tertiaryColor: "rgb(30,30,30)",
          tertiaryBorderColor: "rgb(252,252,252)",
          tertiaryTextColor: "rgb(252,252,252)",
          lineColor: "rgb(252,252,252)",
          textColor: "rgb(252,252,252)",
          mainBkg: "rgb(30,30,30)",
          nodeBorder: "rgb(252,252,252)",
          clusterBkg: DARK_BG,
          clusterBorder: "rgb(252,252,252)",
          edgeLabelBackground: "transparent",
          fontSize: "14px",
          fontFamily: getMermaidFontFamily()
        }
      });
      _mermaidReady = true;
    };
    const loadMermaid = () => {
      if (_mermaidReady || _mermaidLoading) return;
      _mermaidLoading = true;
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
      s.onload = () => {
        initMermaid();
        _mermaidQueue.forEach(fn => fn());
        _mermaidQueue.length = 0;
      };
      document.head.appendChild(s);
    };
    const doRenderMermaid = async (scope) => {
      for (const codeEl of scope.querySelectorAll("pre > code.language-mermaid")) {
        const pre = codeEl.parentElement;
        if (pre.dataset.mermaidRendered) continue;
        pre.dataset.mermaidRendered = "1";
        const id = `mermaid-${_mermaidSeq++}`;
        try {
          const { svg } = await mermaid.render(id, codeEl.textContent);
          const container = document.createElement("div");
          container.className = "mermaid-container";
          container.innerHTML = svg;
          const svgEl = container.querySelector("svg");
          if (svgEl) { svgEl.removeAttribute("width"); svgEl.removeAttribute("height"); svgEl.style.width = "100%"; svgEl.style.height = "auto"; }
          pre.replaceWith(container);
        } catch (_) { }
      }
    };
    const renderMermaidInScope = (scope) => {
      if (!scope || !scope.querySelector("pre > code.language-mermaid")) return;
      if (_mermaidReady) { doRenderMermaid(scope); return; }
      _mermaidQueue.push(() => doRenderMermaid(scope));
      loadMermaid();
    };
    const ensureWideTables = (scope = document) => {
      scope.querySelectorAll(".md-body table").forEach((table) => {
        if (table.closest(".table-scroll")) return;
        const parent = table.parentNode;
        if (!parent) return;
        const scroll = document.createElement("div");
        scroll.className = "table-scroll";
        parent.insertBefore(scroll, table);
        scroll.appendChild(table);
      });
    };
    const syncWideBlockRows = (scope = document) => {
      ensureWideTables(scope);
      scope.querySelectorAll(".message-body-row").forEach((row) => {
        const body = row.querySelector(".md-body");
        const hasStructuredBlock = !!body?.querySelector("ul, ol, blockquote, pre, .table-scroll, .katex-display");
        row.classList.toggle("has-structured-block", hasStructuredBlock);
      });
    };
    let stableCodeBlocksRaf = 0;
    const stableCodeBlockScopes = new Set();
    const queueStableCodeBlockSync = (scope = document) => {
      if (scope) stableCodeBlockScopes.add(scope);
      if (stableCodeBlocksRaf) return;
      stableCodeBlocksRaf = requestAnimationFrame(() => {
        stableCodeBlocksRaf = 0;
        const scopes = Array.from(stableCodeBlockScopes);
        stableCodeBlockScopes.clear();
        const seen = new Set();
        const pres = [];
        scopes.forEach((target) => {
          if (!target) return;
          const list = target?.matches?.(".md-body pre")
            ? [target]
            : Array.from(target.querySelectorAll?.(".md-body pre") || []);
          list.forEach((pre) => {
            if (!pre || !pre.isConnected || seen.has(pre)) return;
            seen.add(pre);
            pres.push(pre);
          });
        });
        pres.forEach((pre) => {
          const width = pre.clientWidth || 0;
          const prevWidth = Number.parseFloat(pre.dataset.stableWidth || "0");
          const widthChanged = Math.abs(width - prevWidth) > 0.5;
          if (widthChanged) {
            pre.style.removeProperty("--code-scroll-stable-height");
          }
          const hasHorizontalScroll = (pre.scrollWidth - pre.clientWidth) > 1;
          if (hasHorizontalScroll) {
            pre.style.setProperty("--code-scroll-stable-height", `${pre.offsetHeight}px`);
            pre.dataset.stableWidth = String(width);
            pre.dataset.stableCodeScroll = "1";
          } else if (widthChanged || pre.dataset.stableCodeScroll === "1") {
            pre.style.removeProperty("--code-scroll-stable-height");
            pre.dataset.stableWidth = String(width);
            delete pre.dataset.stableCodeScroll;
          } else {
            pre.dataset.stableWidth = String(width);
          }
        });
      });
    };
    updateScrollBtnPos();
    window.addEventListener("resize", () => {
      syncWideBlockRows(document);
      queueStableCodeBlockSync(document);
      syncUserMessageCollapse(document);
    });
    if (document.fonts?.ready) {
      document.fonts.ready.then(() => {
        syncWideBlockRows(document);
        queueStableCodeBlockSync(document);
        syncUserMessageCollapse(document);
      }).catch(() => { });
    }
    const AGENT_ICON_NAMES = __AGENT_ICON_NAMES_JS_SET__;
    const ALL_BASE_AGENTS = __ALL_BASE_AGENTS_JS_ARRAY__;
    const agentBaseName = (name) => (name || "").toLowerCase().replace(/-\d+$/, "");
    const agentIconInstanceSubDigits = (name) => {
      const m = String(name || "").toLowerCase().match(/-(\d+)$/);
      return m ? m[1] : "";
    };
    const agentIconInstanceSubHtml = (name) => {
      const d = agentIconInstanceSubDigits(name);
      return d ? `<span class="agent-icon-instance-sub" aria-hidden="true">${escapeHtml(d)}</span>` : "";
    };
    const roleClass = (sender) => {
      const base = agentBaseName(sender);
      if (base === "user" || AGENT_ICON_NAMES.has(base)) return base;
      return "system";
    };
    const agentIconSrc = (name) => {
      const raw = String(name || "").trim();
      if (!raw) return `${CHAT_ASSET_BASE}/icon/`;
      const base = agentBaseName(raw);
      const enc = encodeURIComponent(raw.toLowerCase());
      if (AGENT_ICON_DATA[base]) return AGENT_ICON_DATA[base];
      return `${CHAT_ASSET_BASE}/icon/${enc}`;
    };
    const agentPulseOffset = () => 0;
    const paneViewerTabIconHtml = (agent) => {
      const iconUrl = agentIconSrc(agent);
      const sub = agentIconInstanceSubHtml(agent);
      return `<span class="agent-icon-slot agent-icon-slot--pane-tab"><img class="pane-viewer-tab-icon" src="${escapeHtml(iconUrl)}" alt="" aria-hidden="true">${sub}</span>`;
    };
    const thinkingIconImg = (name, cls) => {
      const base = agentBaseName(name);
      if (!AGENT_ICON_NAMES.has(base)) return "";
      const sub = agentIconInstanceSubHtml(name);
      return `<span class="agent-icon-slot agent-icon-slot--thinking"><span class="${cls}" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(name))}')"></span>${sub}</span>`;
    };
    const entryQualifiesForStreamReveal = (entry) => {
      const s = String(entry?.sender || "").trim().toLowerCase();
      const kind = String(entry?.kind || "").trim().toLowerCase();
      if (kind === "agent-thinking") return false;
      return s !== "" && s !== "user" && s !== "system";
    };
    const STREAM_CHAR_SKIP_SEL = ".katex, .katex-display, .mermaid-container, table, .table-scroll, script, style";
    const STREAM_CHAR_ANIM_MS = 21;
    const STREAM_CHAR_CAP = 3600;
    const unwrapStreamCharSpans = (row) => {
      if (!row) return;
      row.querySelectorAll(".md-body").forEach((md) => {
        md.querySelectorAll(".stream-char").forEach((span) => {
          span.replaceWith(document.createTextNode(span.textContent));
        });
        try { md.normalize(); } catch (_) { }
        delete md.dataset.streamCharsApplied;
      });
    };
    const applyCharStreamRevealToRow = (row) => {
      const mdBody = row?.querySelector?.(".md-body");
      if (!mdBody || mdBody.dataset.streamCharsApplied) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        mdBody.dataset.streamCharsApplied = "1";
        row._streamRevealTotalMs = 0;
        return;
      }
      let idx = 0;
      const wrapText = (node) => {
        if (idx >= STREAM_CHAR_CAP) return;
        const text = node.nodeValue;
        if (!text || !/\S/.test(text)) return;
        const parentEl = node.parentElement;
        if (!parentEl || parentEl.closest(STREAM_CHAR_SKIP_SEL)) return;
        const take = Math.min(text.length, STREAM_CHAR_CAP - idx);
        const head = text.slice(0, take);
        const tail = text.slice(take);
        const frag = document.createDocumentFragment();
        for (let i = 0; i < head.length; i++) {
          const ch = head[i];
          const span = document.createElement("span");
          span.className = "stream-char";
          span.textContent = ch;
          span.style.setProperty("--stream-char-i", String(idx++));
          frag.appendChild(span);
        }
        if (tail) frag.appendChild(document.createTextNode(tail));
        node.parentNode.replaceChild(frag, node);
      };
      const walk = (node) => {
        if (idx >= STREAM_CHAR_CAP) return;
        if (node.nodeType === Node.TEXT_NODE) {
          wrapText(node);
          return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        if (node.matches(STREAM_CHAR_SKIP_SEL)) return;
        Array.from(node.childNodes).forEach(walk);
      };
      walk(mdBody);
      mdBody.dataset.streamCharsApplied = "1";
      const totalDuration = Math.min(idx * 8, 750);
      const charDelay = idx > 0 ? totalDuration / idx : 8;
      mdBody.style.setProperty("--stream-char-delay", charDelay + "ms");
      row._streamRevealTotalMs = totalDuration + STREAM_CHAR_ANIM_MS + 80;
    };
    const metaAgentLabel = (name, textClass, iconSide = "right", { iconOnly = false } = {}) => {
      const raw = (name || "").trim() || "unknown";
      const base = agentBaseName(raw);
      const hasIcon = AGENT_ICON_NAMES.has(base);
      const icon = hasIcon
        ? `<span class="agent-icon-slot agent-icon-slot--meta"><span class="meta-agent-icon" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(raw))}')"></span>${agentIconInstanceSubHtml(raw)}</span>`
        : iconOnly
          ? `<span class="agent-icon-slot agent-icon-slot--meta meta-agent-fallback" aria-hidden="true">—</span>`
          : "";
      const sideClass = iconSide === "right" ? " icon-right" : "";
      const titleAttr = ` title="${escapeHtml(raw).replaceAll('"', "&quot;")}"`;
      const labelAttr = iconOnly ? ` aria-label="${escapeHtml(raw).replaceAll('"', "&quot;")}"` : "";
      if (iconOnly) {
        return `<span class="meta-agent meta-agent--icon-only${sideClass}"${titleAttr}${labelAttr}>${icon}</span>`;
      }
      return `<span class="meta-agent${sideClass}">${icon}<span class="${textClass}">${escapeHtml(raw)}</span></span>`;
    };
    let selectedTargets = [];
    let sendLocked = false;
    let lastSubmitAt = 0;
    let sessionActive = true;
    let sessionLaunchPending = draftLaunchHintActive;
    let composerAutoOpenConsumed = false;
    const canComposeInSession = () => !!sessionActive;
    const canInteractWithSession = () => !!(sessionActive || sessionLaunchPending);
    let pendingAttachments = []; // [{path, name, label}]
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
    let _renderedIds = new Set(); // incremental render tracking
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

    /* ── SpaceX-style header hide on scroll ── */
    {
      const header = document.querySelector(".hub-page-header");
      let prevScrollTop = 0;
      let scrollUpAccum = 0;
      const HIDE_THRESHOLD = 50;
      /* 隠れたあと、わずかな上スクロールでは出さない（累積 px） */
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

    let lastMessagesSig = "";
    let lastMessagesEtag = "";
    let initialLoadDone = false;
    let lastNotifiedMsgId = "";
    let soundEnabled = __CHAT_SOUND_ENABLED__;
    let _audioCtx = null;
    let _notificationBuffers = [];
    let _notificationManifest = [];
    let _notificationManifestPromise = null;
    let _notificationBufferPromise = null;
    let _commitSoundBuffer = null;
    let _commitSoundPromise = null;
    let _audioPrimed = false;
    let _lastSoundAt = 0;
    const SOUND_COOLDOWN_MS = 700;
    const NOTIFICATION_SOUNDS_URL = "/notify-sounds";
    const notificationSoundUrl = (name) => `/notify-sound?name=${encodeURIComponent(name)}`;
    const ensureNotificationManifest = async () => {
      if (_notificationManifest.length) return _notificationManifest;
      if (_notificationManifestPromise) return _notificationManifestPromise;
      _notificationManifestPromise = fetch(NOTIFICATION_SOUNDS_URL)
        .then((res) => {
          if (!res.ok) throw new Error(`notify manifest http ${res.status}`);
          return res.json();
        })
        .then((items) => {
          _notificationManifest = Array.isArray(items) ? items.filter((item) => typeof item === "string" && item) : [];
          return _notificationManifest;
        })
        .catch((err) => {
          console.warn("notify manifest fallback", err);
          _notificationManifest = [];
          return _notificationManifest;
        })
        .finally(() => {
          _notificationManifestPromise = null;
        });
      return _notificationManifestPromise;
    };
    const ensureNotificationBuffer = async () => {
      if (_notificationBuffers.length || !_audioCtx) return _notificationBuffers;
      if (_notificationBufferPromise) return _notificationBufferPromise;
      _notificationBufferPromise = Promise.resolve()
        .then(async () => {
          const names = await ensureNotificationManifest();
          if (!names.length) return [];
          const decoded = [];
          for (const name of names) {
            try {
              const res = await fetch(notificationSoundUrl(name));
              if (!res.ok) continue;
              const buf = await res.arrayBuffer();
              decoded.push(await _audioCtx.decodeAudioData(buf.slice(0)));
            } catch (_) { }
          }
          _notificationBuffers = decoded;
          return decoded;
        })
        .catch((err) => {
          console.warn("notify sound fallback", err);
          return [];
        })
        .finally(() => {
          _notificationBufferPromise = null;
        });
      return _notificationBufferPromise;
    };
    const ensureCommitSoundBuffer = async () => {
      if (_commitSoundBuffer || !_audioCtx) return _commitSoundBuffer;
      if (_commitSoundPromise) return _commitSoundPromise;
      _commitSoundPromise = fetch(notificationSoundUrl("commit.ogg"))
        .then(async (res) => {
          if (!res.ok) return null;
          const buf = await res.arrayBuffer();
          _commitSoundBuffer = await _audioCtx.decodeAudioData(buf.slice(0));
          return _commitSoundBuffer;
        })
        .catch(() => null)
        .finally(() => { _commitSoundPromise = null; });
      return _commitSoundPromise;
    };
    let _commitBlobActive = false;
    const playCommitSound = () => {
      if (!_audioPrimed || !_audioCtx || !_commitSoundBuffer) return;
      if (_commitBlobActive) return;
      try {
        if (_audioCtx.state === "suspended") { _audioCtx.resume().catch(() => { }); return; }
        _commitBlobActive = true;
        const analyser = _audioCtx.createAnalyser();
        analyser.fftSize = 256;
        const freqData = new Uint8Array(analyser.frequencyBinCount);
        const src = _audioCtx.createBufferSource();
        src.buffer = _commitSoundBuffer;
        src.connect(analyser);
        analyser.connect(_audioCtx.destination);
        // Create floating container
        const wrap = document.createElement("div");
        wrap.className = "commit-blob-wrap";
        const cv = document.createElement("canvas");
        const SIZE = 60;
        const dpr = Math.max(1, devicePixelRatio || 1);
        cv.width = Math.round(SIZE * dpr);
        cv.height = Math.round(SIZE * dpr);
        cv.style.width = SIZE + "px";
        cv.style.height = SIZE + "px";
        wrap.appendChild(cv);
        document.body.appendChild(wrap);
        requestAnimationFrame(() => wrap.classList.add("visible"));
        const ctx = cv.getContext("2d");
        const N = 24;
        let playing = true;
        let frame = 0;
        const bands = [0, 0, 0, 0];
        const draw = () => {
          const W = cv.width, H = cv.height;
          ctx.clearRect(0, 0, W, H);
          const cx = W / 2, cy = H / 2;
          const baseR = Math.min(W, H) * 0.34;
          if (playing) {
            analyser.getByteFrequencyData(freqData);
            const binCount = freqData.length;
            const quarter = Math.floor(binCount / 4);
            for (let b = 0; b < 4; b++) {
              let sum = 0;
              for (let i = b * quarter; i < (b + 1) * quarter; i++) sum += freqData[i];
              const avg = sum / quarter / 255;
              bands[b] += (avg - bands[b]) * 0.25;
            }
          } else {
            for (let b = 0; b < 4; b++) bands[b] *= 0.9;
          }
          const t = frame * 0.016;
          frame++;
          const pts = [];
          for (let i = 0; i < N; i++) {
            const angle = (i / N) * Math.PI * 2;
            let deform = Math.sin(angle * 2 + t * 1.2) * 0.02
              + Math.sin(angle * 3 - t * 0.9) * 0.012
              + Math.sin(angle * 5 + t * 2.1) * 0.006;
            const breath = Math.sin(t * 0.8) * baseR * 0.015;
            if (playing) {
              const bIdx = Math.floor((i / N) * 4) % 4;
              deform += bands[bIdx] * 0.35 + bands[(bIdx + 1) % 4] * 0.15;
            }
            const r = (baseR + breath) * (1 + deform);
            pts.push([cx + Math.cos(angle) * r, cy + Math.sin(angle) * r]);
          }
          ctx.beginPath();
          for (let i = 0; i < N; i++) {
            const p0 = pts[(i - 1 + N) % N], p1 = pts[i], p2 = pts[(i + 1) % N], p3 = pts[(i + 2) % N];
            const cp1x = p1[0] + (p2[0] - p0[0]) / 6, cp1y = p1[1] + (p2[1] - p0[1]) / 6;
            const cp2x = p2[0] - (p3[0] - p1[0]) / 6, cp2y = p2[1] - (p3[1] - p1[1]) / 6;
            if (i === 0) ctx.moveTo(p1[0], p1[1]);
            ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]);
          }
          ctx.closePath();
          const alpha = playing ? 0.3 + bands[0] * 0.3 : 0.15;
          const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseR * 1.2);
          grad.addColorStop(0, "rgba(252,252,252," + (alpha * 1.2).toFixed(3) + ")");
          grad.addColorStop(1, "rgba(200,200,200," + (alpha * 0.4).toFixed(3) + ")");
          ctx.fillStyle = grad;
          ctx.fill();
          ctx.strokeStyle = "rgba(252,252,252," + (playing ? 0.2 + bands[1] * 0.3 : 0.08).toFixed(3) + ")";
          ctx.lineWidth = 1;
          ctx.stroke();
          if (playing && bands[0] > 0.05) {
            ctx.save();
            ctx.globalAlpha = Math.min(0.12, bands[0] * 0.15);
            ctx.filter = "blur(" + Math.round(6 + bands[0] * 10) + "px)";
            ctx.fillStyle = "rgba(252,252,252,1)";
            ctx.fill();
            ctx.restore();
          }
        };
        let animFrame = 0;
        const tick = () => { draw(); animFrame = requestAnimationFrame(tick); };
        tick();
        src.onended = () => {
          playing = false;
          setTimeout(() => {
            wrap.classList.remove("visible");
            wrap.addEventListener("transitionend", () => {
              cancelAnimationFrame(animFrame);
              wrap.remove();
              _commitBlobActive = false;
            }, { once: true });
            // Fallback removal
            setTimeout(() => { cancelAnimationFrame(animFrame); wrap.remove(); _commitBlobActive = false; }, 1000);
          }, 400);
        };
        src.start();
      } catch (_) { _commitBlobActive = false; }
    };
    // iOS audio unlock: must call during user gesture
    const primeSound = async () => {
      try {
        if (!_audioCtx) {
          _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (_audioCtx.state === "suspended") {
          await _audioCtx.resume();
        }
        if (!_audioPrimed) {
          // Play a silent 1-sample buffer to unlock AudioContext on iOS
          const silentBuf = _audioCtx.createBuffer(1, 1, _audioCtx.sampleRate);
          const src = _audioCtx.createBufferSource();
          src.buffer = silentBuf;
          src.connect(_audioCtx.destination);
          src.start();
          _audioPrimed = true;
        }
        await ensureNotificationBuffer();
        await ensureCommitSoundBuffer();
        loadScheduledSounds();
      } catch (e) { console.error("Audio prime failed", e); }
    };
    const playNotificationSound = () => {
      if (!soundEnabled || !_audioPrimed || !_audioCtx) return;
      if (!_notificationBuffers.length) return;
      const now = Date.now();
      if (now - _lastSoundAt < SOUND_COOLDOWN_MS) return;
      _lastSoundAt = now;
      try {
        if (_audioCtx.state === "suspended") { _audioCtx.resume().catch(() => { }); return; }
        const s = _audioCtx.createBufferSource();
        s.buffer = _notificationBuffers[Math.floor(Math.random() * _notificationBuffers.length)];
        s.connect(_audioCtx.destination);
        s.start();
      } catch (_) { }
    };
    // Resume AudioContext when page comes back to foreground
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && _audioCtx && _audioCtx.state === "suspended") {
        _audioCtx.resume().catch(() => { });
      }
    });
    // --- Scheduled sound auto-play ---
    // Files named like "HH-MM.ogg" (e.g. 20-30.ogg, 8-00.ogg, 1-00.ogg) play at that time daily.
    const _scheduledSoundsPlayed = new Set();
    const _scheduledSoundFiles = [];
    let _scheduledSoundsLoaded = false;
    const loadScheduledSounds = async () => {
      if (_scheduledSoundsLoaded) return;
      _scheduledSoundsLoaded = true;
      try {
        const res = await fetch("/notify-sounds-all");
        if (!res.ok) return;
        const all = await res.json();
        if (!Array.isArray(all)) return;
        const pat = /^(\d{1,2})-(\d{2})\.ogg$/;
        for (const name of all) {
          const m = pat.exec(name);
          if (m) {
            _scheduledSoundFiles.push({ name, hour: parseInt(m[1], 10), minute: parseInt(m[2], 10) });
          }
        }
      } catch (_) { }
    };
    const checkScheduledSounds = async () => {
      if (!_audioPrimed || !_audioCtx || !soundEnabled) return;
      const now = new Date();
      const hh = now.getHours();
      const mm = now.getMinutes();
      for (const entry of _scheduledSoundFiles) {
        if (entry.hour === hh && entry.minute === mm) {
          const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
          const key = `${entry.name}:${today}`;
          if (_scheduledSoundsPlayed.has(key)) continue;
          _scheduledSoundsPlayed.add(key);
          try {
            if (_audioCtx.state === "suspended") await _audioCtx.resume();
            const res = await fetch(notificationSoundUrl(entry.name));
            if (!res.ok) continue;
            const buf = await res.arrayBuffer();
            const audioBuffer = await _audioCtx.decodeAudioData(buf.slice(0));
            const src = _audioCtx.createBufferSource();
            src.buffer = audioBuffer;
            src.connect(_audioCtx.destination);
            src.start();
          } catch (_) { }
        }
      }
    };
    setInterval(checkScheduledSounds, 15000);
    const copyIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
    const checkIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`;
    const postRenderScope = (scope) => {
      decorateLocalFileLinks(scope);
      if (linkifyInlineCodeFileRefs(scope)) scheduleInlineFileListStaleRelink(scope);
      renderMathInScope(scope);
      renderMermaidInScope(scope);
      syncWideBlockRows(scope);
      syncUserMessageCollapse(scope);
      observeDeferredMessages(scope);
    };
    const clearFocusMsgParam = () => {
      const params = new URLSearchParams(window.location.search);
      if (!params.has(FOCUS_MSG_PARAM)) return;
      params.delete(FOCUS_MSG_PARAM);
      const nextQuery = params.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
      window.history.replaceState(window.history.state, "", nextUrl);
    };
    const notifyNewMessages = (displayEntries) => {
      if (!initialLoadDone || !soundEnabled) return;
      const lastSeenIndex = lastNotifiedMsgId
        ? displayEntries.findIndex((e) => e.msg_id === lastNotifiedMsgId)
        : -1;
      const newEntries = lastSeenIndex >= 0
        ? displayEntries.slice(lastSeenIndex + 1)
        : (lastNotifiedMsgId ? displayEntries.slice(-1) : []);
      if (newEntries.some((e) => e.kind === "git-commit") && soundEnabled) playCommitSound();
      const agentEntries = newEntries.filter((e) => e.sender !== "user" && e.sender !== "system");
      if (agentEntries.length > 0 && soundEnabled) {
        playNotificationSound();
      }
    };
    const overrideDisplayEntry = (entry) => {
      const msgId = String(entry?.msg_id || "");
      return (msgId && publicFullEntryCache.get(msgId)) || entry;
    };
    const mergeEntriesById = (...groups) => {
      const merged = [];
      const seen = new Set();
      for (const group of groups) {
        for (const rawEntry of (group || [])) {
          const entry = overrideDisplayEntry(rawEntry);
          const msgId = String(entry?.msg_id || "");
          if (msgId) {
            if (seen.has(msgId)) continue;
            seen.add(msgId);
          }
          merged.push(entry);
        }
      }
      return merged;
    };
    const entryRenderKey = (entry) => JSON.stringify([
      String(entry?.msg_id || ""),
      String(entry?.kind || ""),
      String(entry?.deferred_body || ""),
    ]);
    const displayEntriesForData = (data) => {
      const baseEntries = Array.isArray(data?.entries) ? data.entries : [];
      const merged = mergeEntriesById(olderEntries, baseEntries);
      return olderEntries.length ? merged : merged.slice(-INITIAL_MESSAGE_WINDOW);
    };
    const entryTargetsSignature = (entry) => {
      const targets = Array.isArray(entry?.targets) ? entry.targets : [];
      return targets.map((target) => String(target || "").trim().toLowerCase()).filter(Boolean).sort().join("\u001f");
    };
    const entryPeerKey = (sender, targetsSig) => {
      if (!sender || sender === "system") return "";
      const targets = targetsSig ? targetsSig.split("\u001f").filter(Boolean) : [];
      if (sender === "user") {
        return targets.length === 1 ? `peer:${targets[0]}` : `targets:${targetsSig}`;
      }
      return targets.length === 1 && targets[0] === "user"
        ? `peer:${sender}`
        : `sender:${sender}:targets:${targetsSig}`;
    };
    const computeThinkingMetaHiddenIds = (entries) => {
      const hiddenIds = new Set();
      let currentPeerKey = "";
      let seenDirectionsForPeer = new Set();
      for (const entry of (entries || [])) {
        const sender = String(entry?.sender || "").trim().toLowerCase();
        const msgId = String(entry?.msg_id || "").trim();
        const targetsSig = entryTargetsSignature(entry);
        if (!sender || sender === "system") {
          continue;
        }
        const peerKey = entryPeerKey(sender, targetsSig);
        if (!peerKey) continue;
        if (peerKey !== currentPeerKey) {
          currentPeerKey = peerKey;
          seenDirectionsForPeer = new Set();
        }
        if (sender === "user") {
          continue;
        }
        const directionKey = `${sender}:${targetsSig}`;
        if (seenDirectionsForPeer.has(directionKey) && msgId) {
          hiddenIds.add(msgId);
        } else {
          seenDirectionsForPeer.add(directionKey);
        }
      }
      return hiddenIds;
    };
    const messagesFetchUrl = (extra = {}) => {
      const params = new URLSearchParams();
      params.set("ts", String(Date.now()));
      params.set("limit", String(MESSAGE_BATCH));
      if (isPublicChatView) params.set("light", "1");
      Object.entries(extra || {}).forEach(([key, value]) => {
        if (value === undefined || value === null || value === "") return;
        params.set(key, String(value));
      });
      return `/messages?${params.toString()}`;
    };
    const emphasizeSystemMessageKeyword = (escapedMessage, kind = "") => {
      const message = String(escapedMessage || "");
      if (!message) return "";
      const kindKey = String(kind || "").trim().toLowerCase();
      const patterns = [];
      if (kindKey === "git-commit") patterns.push(/^Commit\b/i);
      patterns.push(
        /^\/(?:restart|resume|add-agent|remove-agent)\b/i,
        /^(?:Restarted|Resumed|Restart|Resume)\b/i,
        /^(?:Added agent|Removed agent|Add agent|Remove agent)\b/i,
      );
      for (const pattern of patterns) {
        if (pattern.test(message)) {
          return message.replace(pattern, (matched) => `<b>${matched}</b>`);
        }
      }
      return message;
    };
    const buildMsgHTML = (entry, options = {}) => {
      try {
        const safeEntry = (entry && typeof entry === "object") ? entry : {};
        if (safeEntry.sender === "system") {
          const kindRaw = String(safeEntry.kind || "");
          const systemMessage = emphasizeSystemMessageKeyword(escapeHtml(safeEntry.message || ""), kindRaw);
          const systemTitle = systemMessage.replaceAll('"', "&quot;").replace(/<[^>]+>/g, "");
          const msgId = escapeHtml(safeEntry.msg_id || "");
          return `<div class="sysmsg-row" data-msgid="${msgId}" data-sender="system" data-kind="${escapeHtml(safeEntry.kind || "")}"><span class="sysmsg-text" title="${systemTitle}">${systemMessage}</span></div>`;
        }
        const cls = roleClass(safeEntry.sender);
        const entryKindRaw = String(safeEntry?.kind || "").trim();
        const entryKind = entryKindRaw.toLowerCase();
        const kindClass = entryKind ? ` kind-${entryKind.replace(/[^a-z0-9_-]/g, "-")}` : "";
        const entryTargets = Array.isArray(safeEntry.targets) ? safeEntry.targets : [];
        const targetIconOnly = (t) => agentBaseName(t) !== "user";
        const targetSpans = (entryTargets.length > 0
          ? entryTargets.map(t => metaAgentLabel(t, "target-name", "right", { iconOnly: targetIconOnly(t) }))
          : [metaAgentLabel("no target", "target-name", "right", { iconOnly: true })]).join(`<span class="meta-agent-sep">,</span>`);
        const body = stripSenderPrefix(safeEntry.message || "");
        const rawAttr = escapeHtml(body).replaceAll('"', "&quot;");
        const previewAttr = escapeHtml(body.slice(0, 80)).replaceAll('"', "&quot;");
        const msgId = escapeHtml(safeEntry.msg_id || "");
        const targetMeta = `<span class="targets">${targetSpans}</span>`;
        const sender = escapeHtml(safeEntry.sender || "unknown");
        const isUser = cls === "user";
        const hideMetaRow = !!options.hideMetaRow;
        const thinkingMetaHiddenClass = hideMetaRow ? " thinking-meta-hidden" : "";
        const copyButtonHtml = `<button class="copy-btn" type="button" title="コピー" data-copy-icon="${escapeHtml(copyIcon).replaceAll('"', "&quot;")}" data-check-icon="${escapeHtml(checkIcon).replaceAll('"', "&quot;")}">${copyIcon}</button>`;
        const messageBodyHtml = `<div class="md-body">${renderMarkdown(body)}</div>`;
        const senderHtml = metaAgentLabel(safeEntry.sender || "unknown", "sender-label", "right", { iconOnly: true });
        const metaRowHtml = hideMetaRow
          ? ""
          : (isUser
            ? `<div class="message-meta-below user-message-meta"><span class="arrow">to</span>${targetMeta}${copyButtonHtml}</div>`
            : `<div class="message-meta-below">${senderHtml}<span class="arrow">to</span>${targetMeta}${copyButtonHtml}</div>`);
        const deferredBodyHtml = safeEntry.deferred_body && msgId
          ? `<div class="message-deferred-actions"><button class="message-deferred-btn" type="button" data-load-full-message="${msgId}">Load full message</button></div>`
          : "";

        return `<article class="message-row ${cls}${kindClass}${thinkingMetaHiddenClass}" data-msgid="${msgId}" data-sender="${sender}" data-kind="${escapeHtml(entryKindRaw)}">
        <div class="message ${cls}" data-raw="${rawAttr}" data-preview="${previewAttr}">
        ${metaRowHtml}
        <div class="message-body-row">
          ${messageBodyHtml}
          ${isUser ? `<button class="user-collapse-toggle" type="button" hidden>More</button>` : ""}
        </div>
        ${deferredBodyHtml}
        ${isUser ? `<div class="user-message-divider" aria-hidden="true"></div>` : ``}
        </div>
      </article>`;
      } catch (err) {
        const fallbackBody = escapeHtml(String(stripSenderPrefix(String((entry && entry.message) || "")) || ""));
        const fallbackMsgId = escapeHtml(String((entry && entry.msg_id) || ""));
        const fallbackSender = escapeHtml(String((entry && entry.sender) || "unknown"));
        return `<article class="message-row system" data-msgid="${fallbackMsgId}" data-sender="${fallbackSender}" data-kind=""><div class="message system"><div class="message-body-row"><div class="md-body">${fallbackBody}</div></div></div></article>`;
      }
    };
    const buildMsgHTMLFallback = (entry) => {
      const safeEntry = (entry && typeof entry === "object") ? entry : {};
      const sender = String(safeEntry.sender || "unknown");
      const senderLower = sender.toLowerCase();
      const msgId = escapeHtml(String(safeEntry.msg_id || ""));
      const kind = escapeHtml(String(safeEntry.kind || ""));
      const body = escapeHtml(stripSenderPrefix(String(safeEntry.message || ""))).replaceAll("\n", "<br>");
      if (senderLower === "system") {
        const systemMessage = emphasizeSystemMessageKeyword(body, String(safeEntry.kind || ""));
        return `<div class="sysmsg-row" data-msgid="${msgId}" data-sender="system" data-kind="${kind}"><span class="sysmsg-text">${systemMessage}</span></div>`;
      }
      return `<article class="message-row system" data-msgid="${msgId}" data-sender="${escapeHtml(sender)}" data-kind="${kind}">
        <div class="message system">
          <div class="message-meta-below"><span class="sender-label">${escapeHtml(sender)}</span></div>
          <div class="message-body-row"><div class="md-body">${body}</div></div>
        </div>
      </article>`;
    };
    const updateSessionUI = (data, displayEntries) => {
      currentSessionName = data.session || "";
      attachedFilesSession = currentSessionName;
      sessionActive = !!data.active;
      if (sessionActive) {
        clearDraftLaunchHints();
      }
      sessionLaunchPending = !sessionActive && (!!data.launch_pending || sessionLaunchPending || draftLaunchHintActive);
      const sessionCanInteract = canInteractWithSession();
      const resolvedTargets = normalizedSessionTargets(data.targets);
      const picker = document.getElementById("targetPicker");
      if (!picker.dataset.loaded) {
        const restoredTargets = loadTargetSelection(currentSessionName, resolvedTargets);
        selectedTargets = restoredTargets.length ? restoredTargets : [];
        saveTargetSelection(currentSessionName, selectedTargets);
        picker.dataset.loaded = "1";
        renderAgentStatus(Object.fromEntries(resolvedTargets.map((t) => [t, "idle"])));
      }
      const nextTargets = sessionCanInteract ? resolvedTargets : [];
      const nextTargetsSig = JSON.stringify(nextTargets);
      if (nextTargetsSig !== JSON.stringify(availableTargets)) {
        availableTargets = nextTargets;
        selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
        saveTargetSelection(data.session, selectedTargets);
        renderTargetPicker(availableTargets);
      }
      document.getElementById("message").disabled = !sessionActive;
      setQuickActionsDisabled(!sessionActive);
      if (sessionLaunchPending) {
        setStatus("select one initial agent and start the session");
      } else if (!sessionActive) {
        setStatus("archived session is read-only");
      }
      syncPendingLaunchControls();
      maybeAutoOpenComposer();
      updateAttachedFilesPanel(displayEntries);
    };
    const scheduleAnimateInCleanup = (row, opts = {}) => {
      const streamBody = !!opts.streamBody;
      if (!row) return;
      const isUserRow = row.classList.contains("user");
      if (row._animateInCleanupTimer) {
        clearTimeout(row._animateInCleanupTimer);
        row._animateInCleanupTimer = 0;
      }
      let animateInDone = false;
      const finishAnimateIn = () => {
        if (animateInDone) return;
        animateInDone = true;
        row.classList.remove("animate-in");
      };
      const messageEl = row.querySelector(".message");
      if (messageEl) {
        messageEl.addEventListener("animationend", (event) => {
          if (event.target !== messageEl) return;
          if (event.animationName === "msgPulse") {
            finishAnimateIn();
            return;
          }
          if (!isUserRow || event.animationName !== "userMsgReveal") return;
          const divider = row.querySelector(".user-message-divider");
          if (!divider) finishAnimateIn();
        }, { once: true });
      }
      if (isUserRow) {
        const dividerEl = row.querySelector(".user-message-divider");
        dividerEl?.addEventListener("animationend", (event) => {
          if (event.target !== dividerEl) return;
          if (event.animationName !== "userDividerReveal") return;
          finishAnimateIn();
        }, { once: true });
      }
      row.addEventListener("animationend", (event) => {
        if (event.target !== row || event.animationName !== "msgReveal") return;
        finishAnimateIn();
      }, { once: true });
      row._animateInCleanupTimer = setTimeout(finishAnimateIn, 850);
      if (!streamBody) return;
      let streamDone = false;
      const finishStream = () => {
        if (streamDone) return;
        streamDone = true;
        unwrapStreamCharSpans(row);
        row.classList.remove("streaming-body-reveal");
        delete row._streamRevealTotalMs;
      };
      const ms = typeof row._streamRevealTotalMs === "number" ? row._streamRevealTotalMs : 1700;
      if (ms <= 0) {
        queueMicrotask(finishStream);
      } else {
        setTimeout(finishStream, ms);
      }
    };
    const render = (data, { forceScroll = false, forceFullRender = false } = {}) => {
      try {
        const shouldStick = forceScroll;
        const displayEntries = displayEntriesForData(data);
        const thinkingMetaHiddenIds = computeThinkingMetaHiddenIds(displayEntries);
        const previousRenderedIds = new Set(_renderedIds);

        updateSessionUI(data, displayEntries);

        const renderSig = displayEntries.map((entry) => entryRenderKey(entry)).join("\u0002");
        if (!forceScroll && renderSig === lastMessagesSig) return;
        lastMessagesSig = renderSig;

        notifyNewMessages(displayEntries);
        lastNotifiedMsgId = displayEntries.at(-1)?.msg_id || lastNotifiedMsgId;
        initialLoadDone = true;

        const root = document.getElementById("messages");
        if (!displayEntries.length) {
          _renderedIds.clear();
          root.innerHTML = emptyConversationHTML();
          renderThinkingIndicator();
          syncCameraModeReplies();
          updateScrollBtn();
          return;
        }

        const preserveScrollTop = forceScroll ? null : timeline.scrollTop;
        let scrollAnchor = null;
        if (!forceScroll) {
          const tRect = timeline.getBoundingClientRect();
          for (const el of timeline.querySelectorAll("[data-msgid]")) {
            const mid = String(el.dataset.msgid || "");
            if (!mid) continue;
            const r = el.getBoundingClientRect();
            if (r.bottom <= tRect.top + 0.5) continue;
            if (r.top >= tRect.bottom - 0.5) break;
            scrollAnchor = { msgId: mid, vpTop: r.top - tRect.top };
            break;
          }
        }

        const displayIdSet = new Set(displayEntries.map(e => e.msg_id));
        const newEntries = displayEntries.filter(e => !previousRenderedIds.has(e.msg_id));
        const hasRemovals = previousRenderedIds.size > 0 && [...previousRenderedIds].some(id => !displayIdSet.has(id));
        const currentRenderedOrder = Array.from(root.querySelectorAll("[data-msgid]"))
          .map((node) => String(node.dataset.msgid || ""))
          .filter(Boolean);
        const nextRenderedOrder = displayEntries.map((entry) => String(entry.msg_id || ""));
        const nextIncrementalOrder = currentRenderedOrder
          .filter((id) => displayIdSet.has(id))
          .concat(newEntries.map((entry) => String(entry.msg_id || "")));
        const canIncrementallyTrimAndAppend = !forceFullRender
          && previousRenderedIds.size > 0
          && newEntries.length > 0
          && nextIncrementalOrder.length === nextRenderedOrder.length
          && nextIncrementalOrder.every((id, idx) => id === nextRenderedOrder[idx]);

        const isInitialBulkLoad =
          previousRenderedIds.size === 0
          && newEntries.length > 0
          && newEntries.length === displayEntries.length
          && displayEntries.length > 1;
        const shouldMarkNewRowsAnimated =
          newEntries.length > 0
          && !isInitialBulkLoad
          && (previousRenderedIds.size > 0 || displayEntries.length === 1);

        let pendingStreamRowCleanups = [];
        if (canIncrementallyTrimAndAppend) {
          if (hasRemovals) {
            root.querySelectorAll("[data-msgid]").forEach((node) => {
              const msgId = String(node.dataset.msgid || "");
              if (msgId && !displayIdSet.has(msgId)) node.remove();
            });
          }
          const frag = document.createDocumentFragment();
          const pendingRowCleanup = [];
          for (const entry of newEntries) {
            const entryMsgId = String(entry?.msg_id || "");
            const tmpl = document.createElement("template");
            tmpl.innerHTML = buildMsgHTML(entry, {
              hideMetaRow: entryMsgId ? thinkingMetaHiddenIds.has(entryMsgId) : false,
            });
            const row = tmpl.content.firstElementChild;
            if (row) {
              row.classList.add("animate-in");
              const stream = entryQualifiesForStreamReveal(entry);
              if (stream) row.classList.add("streaming-body-reveal");
              pendingRowCleanup.push({ row, stream });
            }
            frag.appendChild(tmpl.content);
          }
          root.appendChild(frag);
          _renderedIds = displayIdSet;
          postRenderScope(root);
          pendingStreamRowCleanups = pendingRowCleanup;
        } else {
          root.innerHTML = displayEntries.map((entry) => {
            const entryMsgId = String(entry?.msg_id || "");
            return buildMsgHTML(entry, {
              hideMetaRow: entryMsgId ? thinkingMetaHiddenIds.has(entryMsgId) : false,
            });
          }).join("");
          _renderedIds = new Set(displayEntries.map(e => e.msg_id));
          const pendingFullRowCleanup = [];
          if (shouldMarkNewRowsAnimated) {
            const newEntryById = new Map(newEntries.map((e) => [String(e.msg_id || ""), e]));
            root.querySelectorAll("[data-msgid]").forEach((row) => {
              const msgId = String(row.dataset.msgid || "");
              const entry = newEntryById.get(msgId);
              if (!msgId || !entry) return;
              row.classList.add("animate-in");
              const stream = entryQualifiesForStreamReveal(entry);
              if (stream) row.classList.add("streaming-body-reveal");
              pendingFullRowCleanup.push({ row, stream });
            });
          }
          postRenderScope(root);
          pendingStreamRowCleanups = pendingFullRowCleanup;
        }

        queueStableCodeBlockSync(root);
        pendingStreamRowCleanups.forEach(({ row, stream }) => {
          if (stream) applyCharStreamRevealToRow(row);
          scheduleAnimateInCleanup(row, { streamBody: stream });
        });
        renderThinkingIndicator();
        syncCameraModeReplies();

        // Poll refreshes: keep the same document offset (do not follow new bottom).
        // When previously scrolled to max, new rows extend below the fold so the viewport looks unchanged.
        if (shouldStick) {
          _pollScrollLockTop = null;
          _pollScrollAnchor = null;
          _programmaticScroll = true;
          timeline.scrollTop = timeline.scrollHeight;
          queueMicrotask(() => { _programmaticScroll = false; });
        } else if (preserveScrollTop != null) {
          const maxTop = Math.max(0, timeline.scrollHeight - timeline.clientHeight);
          _programmaticScroll = true;
          const applied = Math.min(preserveScrollTop, maxTop);
          timeline.scrollTop = applied;
          _pollScrollLockTop = applied;
          _pollScrollAnchor = scrollAnchor;
          queueMicrotask(() => { _programmaticScroll = false; });
          requestAnimationFrame(() => {
            requestAnimationFrame(maybeRestorePollScrollLock);
          });
          settleScrollLockFrames(36);
        }
        _stickyToBottom = isNearBottom();
        updateScrollBtn();
        requestCenteredMessageRowUpdate();
        {
          const input = document.getElementById("message");
          const sendBtnEl = document.querySelector(".send-btn");
          const micBtnEl = document.getElementById("micBtn");
          const hasText = !!(input && input.value.trim().length > 0);
          if (sessionLaunchPending || !sessionActive) {
            if (sendBtnEl) sendBtnEl.classList.remove("visible");
            if (micBtnEl) micBtnEl.classList.remove("hidden");
          } else {
            if (sendBtnEl) sendBtnEl.classList.toggle("visible", hasText);
            if (micBtnEl) micBtnEl.classList.toggle("hidden", hasText);
          }
        }
      } catch (err) {
        console.error("chat render failed; using fallback renderer", err);
        try {
          const root = document.getElementById("messages");
          if (!root) return;
          const fallbackBaseEntries = Array.isArray(data?.entries) ? data.entries : [];
          const fallbackEntries = mergeEntriesById(olderEntries, fallbackBaseEntries).slice(-INITIAL_MESSAGE_WINDOW);
          if (!fallbackEntries.length) {
            _renderedIds.clear();
            root.innerHTML = emptyConversationHTML();
            updateScrollBtn();
            return;
          }
          root.innerHTML = fallbackEntries.map((entry) => buildMsgHTMLFallback(entry)).join("");
          _renderedIds = new Set(fallbackEntries.map((entry) => String(entry?.msg_id || "")).filter(Boolean));
          postRenderScope(root);
          queueStableCodeBlockSync(root);
          syncCameraModeReplies();
          _stickyToBottom = isNearBottom();
          updateScrollBtn();
        } catch (fallbackErr) {
          console.error("chat fallback render failed", fallbackErr);
          const root = document.getElementById("messages");
          if (root) {
            root.innerHTML = `<div class="sysmsg-row"><span class="sysmsg-text">Rendering error. Please reload the page.</span></div>`;
          }
          _renderedIds.clear();
          syncCameraModeReplies();
          updateScrollBtn();
        }
      }
    };
    const setStatus = (text, isError = false) => {
      const node = document.getElementById("statusline");
      node.textContent = text;
      node.style.color = isError ? "#fda4af" : "";
    };
    const setReconnectStatus = (active) => {
      const node = document.getElementById("statusline");
      const current = node.textContent || "";
      if (active) {
        if (reconnectStatusVisible || !current || current === reconnectingStatusText) {
          setStatus(reconnectingStatusText);
          reconnectStatusVisible = true;
        }
        return;
      }
      if (reconnectStatusVisible || current === reconnectingStatusText) {
        setStatus("");
      }
      reconnectStatusVisible = false;
    };
    const SYNC_STATUS_SHEET_CLOSE_MS = 300;
    let syncStatusSheetCloseTimer = 0;
    let syncStatusSheetScrollY = 0;
    let syncStatusSheetScrollLocked = false;
    const clearSyncStatusSheetCloseTimer = () => {
      if (!syncStatusSheetCloseTimer) return;
      clearTimeout(syncStatusSheetCloseTimer);
      syncStatusSheetCloseTimer = 0;
    };
    const lockSyncStatusSheetScroll = () => {
      if (syncStatusSheetScrollLocked) return;
      syncStatusSheetScrollLocked = true;
      syncStatusSheetScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.documentElement.classList.add("sync-status-sheet-active");
      document.body.classList.add("sync-status-sheet-active");
      document.body.style.top = `-${syncStatusSheetScrollY}px`;
    };
    const unlockSyncStatusSheetScroll = () => {
      if (!syncStatusSheetScrollLocked) return;
      syncStatusSheetScrollLocked = false;
      document.documentElement.classList.remove("sync-status-sheet-active");
      document.body.classList.remove("sync-status-sheet-active");
      document.body.style.top = "";
      try { window.scrollTo(0, syncStatusSheetScrollY || 0); } catch (_) { }
    };
    const ensureSyncStatusOverlay = () => {
      let overlay = document.getElementById("syncStatusOverlay");
      if (overlay) return overlay;
      overlay = document.createElement("div");
      overlay.id = "syncStatusOverlay";
      overlay.className = "sync-status-overlay";
      overlay.hidden = true;
      overlay.innerHTML = `
        <div class="sync-status-sheet">
          <div class="sync-status-sheet-panel">
            <div class="sync-status-sheet-nav">
              <div class="sync-status-sheet-pill"></div>
              <div class="sync-status-sheet-nav-bar">
                <div class="sync-status-sheet-title">Sync Status</div>
                <button type="button" class="sync-status-sheet-close" aria-label="Close sync status">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            </div>
            <div class="sync-status-sheet-content"></div>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      overlay.addEventListener("click", (event) => {
        if (event.target !== overlay) return;
        closeSyncStatusPanel();
      });
      const closeBtn = overlay.querySelector(".sync-status-sheet-close");
      closeBtn?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        closeSyncStatusPanel();
      });
      return overlay;
    };
    const setSyncStatusLoading = (overlay) => {
      const content = overlay.querySelector(".sync-status-sheet-content");
      if (!content) return;
      content.innerHTML = `<div class="hub-page-menu-item inline-loading-row" style="cursor:default;opacity:0.72;padding:10px 0">${loadingIndicatorHtml("Loading…")}</div>`;
    };
    const closeSyncStatusPanel = ({ immediate = false } = {}) => {
      const overlay = document.getElementById("syncStatusOverlay");
      if (!overlay) return;
      clearSyncStatusSheetCloseTimer();
      overlay.classList.remove("open");
      if (immediate) {
        overlay.classList.remove("sheet-closing");
        overlay.hidden = true;
        unlockSyncStatusSheetScroll();
        return;
      }
      overlay.classList.add("sheet-closing");
      syncStatusSheetCloseTimer = setTimeout(() => {
        syncStatusSheetCloseTimer = 0;
        overlay.classList.remove("sheet-closing");
        overlay.hidden = true;
        unlockSyncStatusSheetScroll();
      }, SYNC_STATUS_SHEET_CLOSE_MS);
    };
    const showSyncStatusPanel = async () => {
      const overlay = ensureSyncStatusOverlay();
      clearSyncStatusSheetCloseTimer();
      lockSyncStatusSheetScroll();
      setSyncStatusLoading(overlay);
      overlay.hidden = false;
      overlay.classList.remove("sheet-closing");
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          overlay.classList.add("open");
        });
      });
      const content = overlay.querySelector(".sync-status-sheet-content");
      if (!content) return;
      try {
        const res = await fetch((CHAT_BASE_PATH || "") + "/sync-status");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const syncItems = Array.isArray(data) ? data : [];
        const formatBytes = (bytes) => {
          const value = Number(bytes);
          if (!Number.isFinite(value) || value < 0) return "-";
          if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} MB`;
          if (value >= 1024) return `${Math.round(value / 1024)} KB`;
          return `${value} B`;
        };
        let html = '<div class="sync-status-section-header">Sync Status</div>';
        if (!syncItems.length) {
          html += '<div class="sync-status-empty">No agent cursors found</div>';
        }
        for (const a of syncItems) {
          const isRunning = currentAgentStatuses[a.agent] === "running";
          const iconUrl = agentIconSrc(a.agent);
          const detailRows = [
            { label: "path", value: a.log_path || "-" },
            { label: "offset", value: a.log_path ? String(a.offset ?? "-") : "-" },
            { label: "size", value: a.log_path ? formatBytes(a.file_size) : "-" },
            { label: "session", value: a.session_id || "-" },
            { label: "last msg", value: a.last_msg_id || "-" },
            { label: "first seen", value: a.first_seen_ts || "-" },
          ];
          html += `
            <div class="sync-status-agent-block">
              <div class="sync-status-row sync-status-row-head">
                <div class="sync-status-row-left">
                  <div class="sync-status-row-icon" style="-webkit-mask-image:url(\'${escapeHtml(iconUrl)}\');mask-image:url(\'${escapeHtml(iconUrl)}\')"></div>
                  <div class="sync-status-row-label">${escapeHtml(a.agent)}</div>
                  <div class="sync-status-agent-status-dot ${isRunning ? "running" : ""}"></div>
                </div>
                <div class="sync-status-row-value">${isRunning ? "running" : "idle"}</div>
              </div>
              ${detailRows.map((row) => `
                <div class="sync-status-row sync-status-row-detail">
                  <div class="sync-status-row-label">${escapeHtml(row.label)}</div>
                  <div class="sync-status-row-value">${escapeHtml(String(row.value))}</div>
                </div>
              `).join("")}
            </div>
          `;
        }
        content.innerHTML = `<div class="sync-status-list">${html}</div>`;
      } catch (error) {
        content.innerHTML = `<div class="sync-status-error">Failed to load sync status: ${escapeHtml(String(error?.message || error || "unknown error"))}</div>`;
      }
    };
    const agentActionCandidates = (mode) => {
      if (mode === "add") return ALL_BASE_AGENTS.filter(Boolean);
      return (availableTargets || []).filter((agent) => agent && agent !== "others");
    };
    const performAgentAction = async (mode, selected) => {
      if (!selected) return;
      const adding = mode === "add";
      setStatus(`${adding ? "adding" : "removing"} ${selected}...`);
      try {
        const res = await fetch(adding ? "/add-agent" : "/remove-agent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agent: selected }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) {
          throw new Error(data.error || `failed to ${adding ? "add" : "remove"} agent`);
        }
        await new Promise((resolve) => setTimeout(resolve, adding ? 700 : 500));
        await refreshSessionState();
        setStatus(`${selected} ${adding ? "added" : "removed"}`);
        setTimeout(() => setStatus(""), 1800);
      } catch (err) {
        setStatus(err?.message || `${adding ? "add" : "remove"} agent failed`, true);
        setTimeout(() => setStatus(""), 2600);
      }
    };
    const resetAgentActionNativeMenu = ({ clearOptions = false } = {}) => {
      const select = document.getElementById("agentActionNativeMenuSelect");
      if (!select) return;
      select.value = "";
      if (clearOptions) {
        select.innerHTML = '<option value="" disabled selected>Agent</option>';
      }
      select.style.top = "-9999px";
      select.style.left = "-9999px";
    };
    const ensureAgentActionNativeMenu = () => {
      let select = document.getElementById("agentActionNativeMenuSelect");
      if (select) return select;
      select = document.createElement("select");
      select.id = "agentActionNativeMenuSelect";
      select.setAttribute("aria-hidden", "true");
      select.tabIndex = -1;
      select.style.position = "fixed";
      select.style.top = "-9999px";
      select.style.left = "-9999px";
      select.style.width = "1px";
      select.style.height = "1px";
      select.style.opacity = "0.001";
      select.style.pointerEvents = "auto";
      select.style.appearance = "none";
      select.style.webkitAppearance = "none";
      select.style.border = "0";
      select.style.outline = "none";
      select.style.background = "transparent";
      select.style.color = "transparent";
      select.style.fontSize = "13px";
      select.style.zIndex = "1000";
      select.addEventListener("change", () => {
        const value = String(select.value || "");
        resetAgentActionNativeMenu({ clearOptions: true });
        if (!value) return;
        const sep = value.indexOf(":");
        if (sep <= 0) return;
        void performAgentAction(value.slice(0, sep), value.slice(sep + 1));
      });
      select.addEventListener("blur", () => {
        setTimeout(() => resetAgentActionNativeMenu({ clearOptions: true }), 0);
      });
      document.body.appendChild(select);
      return select;
    };
    const anchorAgentActionNativeMenu = (select) => {
      const anchor = rightMenuBtn || document.activeElement || document.body;
      const rect = anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : { left: 0, top: 0, width: 1, height: 1 };
      select.style.left = `${Math.max(0, Math.round(rect.left))}px`;
      select.style.top = `${Math.max(0, Math.round(rect.top))}px`;
      select.style.width = `${Math.max(1, Math.round(rect.width || 1))}px`;
      select.style.height = `${Math.max(1, Math.round(rect.height || 1))}px`;
    };
    const openAgentActionNativeMenu = (mode) => {
      const candidates = agentActionCandidates(mode);
      if (mode === "remove" && candidates.length <= 1) {
        resetAgentActionNativeMenu({ clearOptions: true });
        setStatus("need at least 2 agents to remove one", true);
        setTimeout(() => setStatus(""), 2400);
        return true;
      }
      if (!candidates.length) {
        resetAgentActionNativeMenu({ clearOptions: true });
        setStatus("no agents available", true);
        setTimeout(() => setStatus(""), 2200);
        return true;
      }
      const select = ensureAgentActionNativeMenu();
      const title = mode === "add" ? "Add Agent" : "Remove Agent";
      resetAgentActionNativeMenu({ clearOptions: true });
      select.innerHTML = `<option value="" disabled selected>${title}</option>` + candidates
        .map((agent) => `<option value="${mode}:${escapeHtml(agent)}">${escapeHtml(agent)}</option>`)
        .join("");
      anchorAgentActionNativeMenu(select);
      let opened = false;
      const show = () => {
        if (typeof select.showPicker === "function") {
          try { select.showPicker(); opened = true; return true; } catch (_) { }
        }
        try { select.focus({ preventScroll: true }); } catch (_) {
          try { select.focus(); } catch (_) { }
        }
        try { select.click(); opened = true; return true; } catch (_) { }
        return false;
      };
      show();
      if (!opened) {
        setTimeout(() => {
          if (!show()) {
            resetAgentActionNativeMenu({ clearOptions: true });
            setStatus("agent menu unavailable", true);
            setTimeout(() => setStatus(""), 2200);
          }
        }, 0);
      }
      return true;
    };
    const showAddAgentModal = () => {
      openAgentActionNativeMenu("add");
    };
    const showRemoveAgentModal = () => {
      openAgentActionNativeMenu("remove");
    };
    const showGitCommitModal = ({ title, subject, defaultMessage, hint }) => new Promise((resolve) => {
      let settled = false;
      let overlay = document.getElementById("gitFileCommitOverlay");
      if (overlay) overlay.remove();
      overlay = document.createElement("div");
      overlay.id = "gitFileCommitOverlay";
      overlay.className = "add-agent-overlay attach-rename-overlay";
      overlay.innerHTML = `<div class="add-agent-panel attach-rename-panel"><h3>${escapeHtml(title || "Commit")}</h3><p class="attach-rename-copy">${escapeHtml(subject || "")}</p><label class="attach-rename-label" for="gitFileCommitInput">Commit message</label><input id="gitFileCommitInput" class="attach-rename-input" type="text" maxlength="200" autocapitalize="sentences" autocorrect="off" spellcheck="false" value="${escapeHtml(defaultMessage || "")}"><p class="attach-rename-hint">${escapeHtml(hint || "")}</p><div class="add-agent-actions"><button type="button" class="add-agent-cancel">Cancel</button><button type="button" class="add-agent-confirm">Commit</button></div></div>`;
      document.body.appendChild(overlay);
      const input = overlay.querySelector("#gitFileCommitInput");
      const confirmBtn = overlay.querySelector(".add-agent-confirm");
      const finish = (value) => {
        if (settled) return;
        settled = true;
        overlay.classList.remove("visible");
        setTimeout(() => {
          overlay.remove();
          resolve(value);
        }, 220);
      };
      const sync = () => {
        if (confirmBtn) confirmBtn.disabled = !(input?.value || "").trim();
      };
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          overlay.classList.add("visible");
          try {
            input?.focus({ preventScroll: true });
          } catch (_) {
            input?.focus();
          }
          input?.select();
        });
      });
      sync();
      overlay.addEventListener("click", (e) => { if (e.target === overlay) finish(null); });
      overlay.querySelector(".add-agent-cancel")?.addEventListener("click", () => finish(null));
      input?.addEventListener("input", sync);
      input?.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          finish(null);
          return;
        }
        if (e.key === "Enter") {
          e.preventDefault();
          if (!(input.value || "").trim()) return;
          finish(input.value.trim());
        }
      });
      confirmBtn?.addEventListener("click", () => {
        const next = (input?.value || "").trim();
        if (!next) return;
        finish(next);
      });
    });
    const showGitFileCommitModal = (filePath) => {
      const fileName = displayAttachmentFilename(filePath || "") || "file";
      return showGitCommitModal({
        title: "Commit File",
        subject: filePath || "",
        defaultMessage: `Update ${fileName}`,
        hint: "Only the currently selected file will be staged and committed.",
      });
    };
    const showGitAllCommitModal = () => {
      return showGitCommitModal({
        title: "Commit All Files",
        subject: "All current uncommitted changes",
        defaultMessage: "Update worktree",
        hint: "All currently uncommitted files will be staged and committed together.",
      });
    };
    const fetchWithTimeout = async (url, options = {}, timeoutMs = 5000) => {
      let timer = null;
      let timedOut = false;
      const controller = typeof AbortController === "function" ? new AbortController() : null;
      const requestOptions = {
        cache: "no-store",
        ...options,
      };
      const upstreamSignal = options?.signal || null;
      if (controller) {
        requestOptions.signal = controller.signal;
        if (upstreamSignal) {
          if (upstreamSignal.aborted) {
            controller.abort();
          } else if (typeof upstreamSignal.addEventListener === "function") {
            upstreamSignal.addEventListener("abort", () => controller.abort(), { once: true });
          }
        }
      } else if (upstreamSignal) {
        requestOptions.signal = upstreamSignal;
      }
      const fetchPromise = fetch(url, requestOptions);
      if (!(timeoutMs > 0)) return fetchPromise;
      const timeoutPromise = new Promise((_, reject) => {
        timer = setTimeout(() => {
          timedOut = true;
          try { controller?.abort(); } catch (_) { }
          reject(new Error("request timeout"));
        }, timeoutMs);
      });
      try {
        return await Promise.race([fetchPromise, timeoutPromise]);
      } catch (err) {
        if (timedOut && err?.name === "AbortError") {
          throw new Error("request timeout");
        }
        throw err;
      } finally {
        if (timer) clearTimeout(timer);
        if (timedOut) {
          fetchPromise.catch(() => { });
        }
      }
    };
    const purgeChatAssetCaches = async () => {
      if (!("caches" in window)) return;
      const baseUrl = `${window.location.origin}${CHAT_BASE_PATH || ""}`;
      const exactUrls = new Set([
        `${baseUrl}/app.webmanifest`,
        `${baseUrl}/pwa-icon-192.png`,
        `${baseUrl}/pwa-icon-512.png`,
        `${baseUrl}/apple-touch-icon.png`,
      ]);
      const prefixUrls = [
        `${baseUrl}/chat-assets/`,
      ];
      try {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map(async (cacheName) => {
          const cache = await caches.open(cacheName);
          const requests = await cache.keys();
          await Promise.all(requests.map((request) => {
            const url = String(request?.url || "");
            if (exactUrls.has(url) || prefixUrls.some((prefix) => url.startsWith(prefix))) {
              return cache.delete(request);
            }
            return Promise.resolve(false);
          }));
        }));
      } catch (_) { }
    };
    const refreshChatServiceWorkers = async () => {
      if (!("serviceWorker" in navigator)) return;
      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map((registration) => registration.update().catch(() => undefined)));
      } catch (_) { }
    };
    const waitForChatReady = async (timeoutMs = 15000, expectedPreviousInstance = "") => {
      const deadline = Date.now() + timeoutMs;
      let sawDisconnect = false;
      while (Date.now() < deadline) {
        try {
          const sessionRes = await fetchWithTimeout(`/session-state?ts=${Date.now()}`, {}, 3500);
          if (sessionRes.ok) {
            const sessionData = await sessionRes.json();
            const instance = sessionData?.server_instance || "";
            const instanceAdvanced = !expectedPreviousInstance || (instance && instance !== expectedPreviousInstance) || sawDisconnect;
            if (instanceAdvanced) {
              const messagesRes = await fetchWithTimeout(messagesFetchUrl({ limit: 1 }), {}, 3500);
              if (messagesRes.ok) {
                const messagesData = await messagesRes.json();
                if (Array.isArray(messagesData?.entries)) {
                  const liveInstance = messagesData?.server_instance || instance;
                  if (liveInstance) currentServerInstance = liveInstance;
                  return true;
                }
              }
            }
          }
        } catch (_) {
          sawDisconnect = true;
        }
        await sleep(250);
      }
      return false;
    };
    const navigateToFreshChat = () => {
      const params = new URLSearchParams(window.location.search);
      params.set("follow", followMode ? "1" : "0");
      params.set("launch_shell", "1");
      params.set("ts", String(Date.now()));
      window.location.replace(`${window.location.pathname}?${params.toString()}`);
    };
    const mergeRefreshOptions = (current = {}, next = {}) => {
      const currentOptions = current || {};
      const nextOptions = next || {};
      return {
        forceScroll: !!(currentOptions.forceScroll || nextOptions.forceScroll),
        forceFullRender: !!(currentOptions.forceFullRender || nextOptions.forceFullRender),
      };
    };
    const rerenderCurrentMessages = () => {
      if (!latestPayloadData) return;
      lastMessagesSig = "";
      render(latestPayloadData, { forceFullRender: true });
    };
    const ensurePublicDeferredObserver = () => {
      if (!isPublicChatView || publicDeferredObserver || typeof IntersectionObserver !== "function") return;
      publicDeferredObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const button = entry.target.closest("[data-load-full-message]") || entry.target.querySelector("[data-load-full-message]");
          if (!button) return;
          void loadFullMessageEntry(button.dataset.loadFullMessage || "", button);
        });
      }, {
        root: timeline,
        rootMargin: "220px 0px 220px 0px",
        threshold: 0.01,
      });
    };
    const observeDeferredMessages = (scope) => {
      if (!isPublicChatView) return;
      ensurePublicDeferredObserver();
      if (!publicDeferredObserver) return;
      (scope || document).querySelectorAll("[data-load-full-message]").forEach((button) => {
        const msgId = String(button.dataset.loadFullMessage || "");
        if (!msgId || publicFullEntryCache.has(msgId) || publicDeferredLoading.has(msgId)) return;
        publicDeferredObserver.observe(button);
      });
    };
    const loadOlderMessages = async () => {
      if (olderLoading || !latestPayloadData) return;
      const firstMsgId = displayEntriesForData(latestPayloadData)[0]?.msg_id || "";
      if (!firstMsgId) {
        olderHasMore = false;
        rerenderCurrentMessages();
        return;
      }
      olderLoading = true;
      const prevHeight = timeline.scrollHeight;
      const prevTop = timeline.scrollTop;
      rerenderCurrentMessages();
      try {
        const res = await fetchWithTimeout(messagesFetchUrl({ before_msg_id: firstMsgId }));
        if (!res.ok) throw new Error("older messages unavailable");
        const data = await res.json();
        const olderBatch = Array.isArray(data?.entries) ? data.entries : [];
        olderHasMore = !!data?.has_older;
        if (olderBatch.length) {
          olderEntries = mergeEntriesById(olderBatch, olderEntries);
        }
      } catch (_) {
      } finally {
        olderLoading = false;
        rerenderCurrentMessages();
        const delta = timeline.scrollHeight - prevHeight;
        timeline.scrollTop = prevTop + delta;
        updateScrollBtn();
      }
    };
    const loadFullMessageEntry = async (msgId, button) => {
      const targetMsgId = String(msgId || "").trim();
      if (!isPublicChatView || !targetMsgId) return;
      if (publicFullEntryCache.has(targetMsgId)) {
        rerenderCurrentMessages();
        return;
      }
      if (publicDeferredLoading.has(targetMsgId)) return;
      publicDeferredLoading.add(targetMsgId);
      if (publicDeferredObserver && button) {
        try { publicDeferredObserver.unobserve(button); } catch (_) { }
      }
      if (button) {
        button.disabled = true;
        button.textContent = "Loading...";
      }
      try {
        const res = await fetch(`/message-entry?msg_id=${encodeURIComponent(targetMsgId)}`, { cache: "no-store" });
        if (!res.ok) throw new Error("message body unavailable");
        const data = await res.json().catch(() => ({}));
        if (data?.entry) {
          publicFullEntryCache.set(targetMsgId, data.entry);
          rerenderCurrentMessages();
          return;
        }
      } catch (_) {
      } finally {
        publicDeferredLoading.delete(targetMsgId);
      }
      if (button) {
        button.disabled = false;
        button.textContent = "Retry full message";
      }
    };
    const refresh = async (options = {}) => {
      const refreshOptions = (!hasInitialRefreshHydrated && followMode)
        ? mergeRefreshOptions(options, { forceScroll: true })
        : options;
      if (refreshInFlight) {
        pendingRefreshOptions = mergeRefreshOptions(pendingRefreshOptions, refreshOptions);
        return;
      }
      refreshInFlight = true;
      try {
        const requestedFocusMsgId = String(pendingFocusMsgId || readFocusMsgIdFromUrl() || "").trim();
        const useFocusedWindow = !!requestedFocusMsgId && focusWindowRequestedMsgId !== requestedFocusMsgId;
        const url = useFocusedWindow
          ? messagesFetchUrl({ around_msg_id: requestedFocusMsgId })
          : messagesFetchUrl();
        const headers = {};
        if (!useFocusedWindow && lastMessagesEtag) {
          headers["If-None-Match"] = lastMessagesEtag;
        }
        const res = await fetchWithTimeout(
          url,
          Object.keys(headers).length ? { headers } : {}
        );
        if (res.status === 304) {
          messageRefreshFailures = 0;
          setReconnectStatus(false);
          if (!hasInitialRefreshHydrated) {
            hasInitialRefreshHydrated = true;
            releaseLaunchShellGate();
          }
          notifyHubChatRenderReady();
          return;
        }
        if (!res.ok) throw new Error("messages unavailable");
        const nextMessagesEtag = res.headers.get("ETag") || "";
        if (!useFocusedWindow && nextMessagesEtag) {
          lastMessagesEtag = nextMessagesEtag;
        }
        const data = await res.json();
        if (useFocusedWindow) {
          focusWindowRequestedMsgId = requestedFocusMsgId;
          const hasFocusedEntry = Array.isArray(data?.entries)
            && data.entries.some((entry) => String(entry?.msg_id || "") === requestedFocusMsgId);
          pendingFocusMsgId = hasFocusedEntry ? requestedFocusMsgId : "";
          if (!hasFocusedEntry) {
            focusWindowRequestedMsgId = "";
            clearFocusMsgParam();
          }
        }
        const nextServerInstance = data?.server_instance || "";
        if (nextServerInstance && currentServerInstance && nextServerInstance !== currentServerInstance) {
          olderEntries = [];
          olderHasMore = false;
          publicFullEntryCache = new Map();
          publicDeferredLoading = new Set();
        }
        if (nextServerInstance) currentServerInstance = nextServerInstance;
        latestPayloadData = data;
        if (!olderEntries.length) {
          olderHasMore = !!data?.has_older;
        }
        messageRefreshFailures = 0;
        setReconnectStatus(false);
        render(data, refreshOptions);
        if (!hasInitialRefreshHydrated) {
          hasInitialRefreshHydrated = true;
          releaseLaunchShellGate();
        }
        notifyHubChatRenderReady();
      } catch (_) {
        messageRefreshFailures += 1;
        if (followMode && messageRefreshFailures >= 3) {
          setReconnectStatus(true);
        }
      } finally {
        refreshInFlight = false;
        if (pendingRefreshOptions) {
          const nextOptions = pendingRefreshOptions;
          pendingRefreshOptions = null;
          queueMicrotask(() => refresh(nextOptions));
        }
      }
    };
    timeline.addEventListener("click", async (event) => {
      const fullBtn = event.target.closest("[data-load-full-message]");
      if (fullBtn) {
        event.preventDefault();
        await loadFullMessageEntry(fullBtn.dataset.loadFullMessage || "", fullBtn);
      }
    });
    const logSystem = (message) => fetch("/log-system", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const showProviderEventsModal = async (msgId) => {
      const targetMsgId = String(msgId || "").trim();
      if (!targetMsgId) return;
      let payload = null;
      try {
        const res = await fetch(`/normalized-events?msg_id=${encodeURIComponent(targetMsgId)}`, { cache: "no-store" });
        if (!res.ok) throw new Error("normalized events unavailable");
        payload = await res.json();
      } catch (err) {
        setStatus(err?.message || "normalized events unavailable", true);
        setTimeout(() => setStatus(""), 2200);
        return;
      }
      let overlay = document.getElementById("providerEventsOverlay");
      if (overlay) overlay.remove();
      const entry = payload?.entry || {};
      const events = Array.isArray(payload?.events) ? payload.events : [];
      const rendered = events.length
        ? events.map((event) => JSON.stringify(event, null, 2)).join("\n\n")
        : (payload?.missing ? "[normalized event log missing]" : "[no normalized events]");
      overlay = document.createElement("div");
      overlay.id = "providerEventsOverlay";
      overlay.className = "add-agent-overlay provider-events-overlay";
      overlay.innerHTML = `<div class="add-agent-panel provider-events-panel"><div class="provider-events-header"><div><h3 class="provider-events-title">Normalized Events</h3><p class="provider-events-meta">${escapeHtml([
        entry.provider_adapter || "",
        entry.provider_model || "",
        payload?.path ? `path: ${payload.path}` : "",
        entry.run_id ? `run: ${entry.run_id}` : "",
      ].filter(Boolean).join("\n"))}</p></div><button type="button" class="provider-events-close" aria-label="Close">×</button></div><pre class="provider-events-pre">${escapeHtml(rendered)}</pre></div>`;
      document.body.appendChild(overlay);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => overlay.classList.add("visible"));
      });
      const closeModal = () => {
        overlay.classList.remove("visible");
        setTimeout(() => overlay.remove(), 420);
      };
      overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
      overlay.querySelector(".provider-events-close")?.addEventListener("click", closeModal);
    };
    const submitMessage = async ({ overrideMessage = null, overrideTarget = null, raw = false, closeOverlayOnStart = false } = {}) => {
      if (sendLocked || Date.now() - lastSubmitAt < 500) {
        return false;
      }
      sendLocked = true;
      lastSubmitAt = Date.now();
      const message = document.getElementById("message");
      const rawInput = (overrideMessage ?? message.value).trim();
      const clearComposerDraft = () => {
        message.value = "";
        updateSendBtnVisibility();
        autoResizeTextarea();
      };
      // Slash command: /memo [text] → self-send (body optional if Import attachments exist)
      const memoMatch = !overrideMessage && rawInput.match(/^\/memo(?:\s+([\s\S]*))?$/);
      if (memoMatch) {
        overrideMessage = (memoMatch[1] || "").trim();
        overrideTarget = "user";
      }
      const paneDirectMatch = !overrideMessage && !memoMatch && rawInput.match(/^\/(model|up|down)(?:\s+(\d+))?$/);
      if (paneDirectMatch) {
        const cmd = paneDirectMatch[1];
        const count = Math.max(1, Math.min(parseInt(paneDirectMatch[2] || "1", 10) || 1, 100));
        overrideMessage = (cmd === "up" || cmd === "down") ? `${cmd} ${count}` : cmd;
      }
      const paneShortcutSlashMatch = !overrideMessage && !memoMatch && rawInput.match(/^\/(restart|resume|interrupt|enter|ctrlc)$/i);
      if (paneShortcutSlashMatch) {
        overrideMessage = paneShortcutSlashMatch[1].toLowerCase();
      }
      const payload = overrideMessage !== null ? overrideMessage : rawInput;
      let target = overrideTarget ?? selectedTargets.join(",");
      const shortcutMeta = parseControlShortcut(payload);
      const shortcut = shortcutMeta?.name || "";
      const isShortcut = !!shortcutMeta;
      const paneOnlyShortcuts = new Set(["interrupt", "ctrlc", "enter", "restart", "resume", "model", "up", "down"]);
      if (!target && shortcut !== "save") {
        if (isShortcut && paneOnlyShortcuts.has(shortcut)) {
          setStatus("select at least one target", true);
          sendLocked = false;
          return false;
        }
        target = "user";
      }
      const attachSuffix =
        !isShortcut && pendingAttachments.length
          ? pendingAttachments.map((a) => "\n[Attached: " + a.path + "]").join("")
          : "";
      const messageBody = (isShortcut ? payload : payload) + attachSuffix;
      if (memoMatch && !payload && !pendingAttachments.length) {
        setStatus("/memo needs text or an Import attachment", true);
        sendLocked = false;
        return false;
      }
      if (!messageBody.trim()) {
        setStatus("message is required", true);
        sendLocked = false;
        return false;
      }
      setQuickActionsDisabled(true);
      if (closeOverlayOnStart && isComposerOverlayOpen()) {
        message.blur();
        closeComposerOverlay();
      }
      const shortcutDisplay = shortcutLabel(shortcut || payload);
      const shortcutScope = (shortcut && shortcut !== "save") && target ? ` for ${target}` : "";
      const shortcutCountSuffix = (shortcutMeta && shortcutMeta.repeat && shortcutMeta.repeat > 1 && (shortcut === "up" || shortcut === "down"))
        ? ` x${shortcutMeta.repeat}`
        : "";
      setStatus(
        isShortcut
          ? `running ${shortcutDisplay}${shortcutCountSuffix}${shortcutScope}...`
          : `sending to ${target}...`
      );
      try {
        const res = await fetch("/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target,
            message: messageBody,
            ...(raw ? { raw: true } : {}),
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "send failed");
        }
        if (data.activated) {
          clearDraftLaunchHints();
          sessionLaunchPending = false;
          sessionActive = true;
          if (Array.isArray(data.targets) && data.targets.length) {
            availableTargets = normalizedSessionTargets(data.targets);
            selectedTargets = data.targets.filter((target) => availableTargets.includes(target));
            saveTargetSelection(currentSessionName, selectedTargets);
            renderTargetPicker(availableTargets);
          }
          setQuickActionsDisabled(false);
        }
        if (!overrideMessage || memoMatch || paneDirectMatch || paneShortcutSlashMatch) {
          clearComposerDraft();
          if (pendingAttachments.length) {
            pendingAttachments = [];
            const row = document.getElementById("attachPreviewRow");
            if (row) { row.innerHTML = ""; row.style.display = "none"; }
          }
          if (!shortcutMeta?.keepComposerOpen) message.blur();
          if (!shortcutMeta?.keepComposerOpen) closeComposerOverlay();
          _stickyToBottom = true;
        }
        setStatus(
          isShortcut
            ? `${shortcutDisplay}${shortcutCountSuffix}${shortcutScope} completed`
            : `sent to ${target}`
        );
        if (shortcut === "save") {
          await logSystem("Save Log");
          setTimeout(() => setStatus(""), 2000);
        }
        await refresh({ forceScroll: true });
        return true;
      } catch (error) {
        setStatus(error.message, true);
        return false;
      } finally {
        setQuickActionsDisabled(!sessionActive);
        sendLocked = false;
      }
    };
    document.getElementById("composer").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!canComposeInSession()) {
        setStatus(sessionLaunchPending ? "start the session first" : "archived session is read-only", true);
        return;
      }
      const submitter = event.submitter;
      const closeOverlayOnStart = !!(submitter && submitter.classList && submitter.classList.contains("send-btn"));
      await submitMessage({ closeOverlayOnStart });
    });
    const quickMore = document.querySelector(".quick-more");
    const composerPlusMenu = document.getElementById("composerPlusMenu");
    const hubBtn = document.getElementById("hubPageTitleLink");
    let keepComposerPlusMenuOnBlur = false;
    const hubRootUrl = () => {
      if (CHAT_BASE_PATH || String(window.location.pathname || "").startsWith("/session/")) {
        return `${window.location.origin}/`;
      }
      const portValue = Number(CHAT_BOOTSTRAP.hubPort || 0);
      const protocol = window.location.protocol || "http:";
      const host = window.location.hostname || "127.0.0.1";
      const defaultPort =
        (protocol === "https:" && portValue === 443) ||
        (protocol === "http:" && portValue === 80);
      if (portValue > 0 && !defaultPort) {
        return `${protocol}//${host}:${portValue}/`;
      }
      return `${protocol}//${host}/`;
    };
    const hubUrlForPath = (path = "/") => {
      const normalizedPath = String(path || "/").startsWith("/") ? String(path || "/") : `/${String(path || "/")}`;
      return `${hubRootUrl().replace(/\/$/, "")}${normalizedPath}`;
    };
    const requestHubTop = () => {
      const hubUrl = hubUrlForPath("/");
      if (window.self !== window.top) {
        try {
          window.parent.postMessage({ type: "multiagent-open-hub-path", url: hubUrl, reveal: true }, "*");
        } catch (_) {
          requestHubCloseChat();
        }
        return;
      }
      window.location.href = hubUrl;
    };
    const openHubPath = (path = "/") => {
      const normalizedPath = String(path || "/").startsWith("/") ? String(path || "/") : `/${String(path || "/")}`;
      const hubUrl = hubUrlForPath(normalizedPath);
      if (window.self !== window.top) {
        if (normalizedPath === "/") {
          requestHubTop();
          return;
        }
        try {
          window.parent.location.href = hubUrl;
          return;
        } catch (_err) {
          window.parent.postMessage({ type: "multiagent-open-hub-path", url: hubUrl }, "*");
          return;
        }
      }
      window.location.href = hubUrl;
    };
    hubBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      openHubPath("/");
    });
    composerPlusMenu && composerPlusMenu.addEventListener("toggle", () => {
      if (!composerPlusMenu.open) {
        composerPlusMenu.querySelectorAll(".plus-submenu").forEach(sub => { sub.open = false; });
      }
    });
    composerPlusMenu?.addEventListener("pointerdown", () => {
      keepComposerPlusMenuOnBlur = true;
      setTimeout(() => { keepComposerPlusMenuOnBlur = false; }, 240);
    });
    composerPlusMenu?.addEventListener("touchstart", () => {
      keepComposerPlusMenuOnBlur = true;
      setTimeout(() => { keepComposerPlusMenuOnBlur = false; }, 240);
    }, { passive: true });
    composerPlusMenu?.addEventListener("click", (event) => {
      const keepFocusTarget = event.target.closest(".plus-submenu-toggle, .composer-plus-panel .quick-action");
      if (!keepFocusTarget) return;
      if (event.target.closest("#cameraBtn")) return;
      requestAnimationFrame(() => {
        if (document.activeElement !== messageInput) {
          focusMessageInputWithoutScroll();
        }
      });
    });
    composerPlusMenu && composerPlusMenu.querySelectorAll(".plus-submenu").forEach(sub => {
      sub.addEventListener("toggle", () => {
        if (sub.open) {
          composerPlusMenu.querySelectorAll(".plus-submenu").forEach(other => {
            if (other !== sub) other.open = false;
          });
        }
      });
    });
    const closePlusMenu = () => {
      if (composerPlusMenu && composerPlusMenu.open) {
        composerPlusMenu.classList.add("closing");
        setTimeout(() => {
          composerPlusMenu.open = false;
          composerPlusMenu.classList.remove("closing");
        }, 160);
      }
    };
    composerPlusMenu?.querySelector(".composer-plus-toggle")?.addEventListener("mousedown", (e) => e.preventDefault());
    composerPlusMenu?.addEventListener("toggle", () => {
      if (composerPlusMenu.open) closeDrop();
    });
    const rightMenuBtn = document.getElementById("hubPageMenuBtn");
    const rightMenuPanel = document.getElementById("hubPageMenuPanel");
    const nativeHeaderMenuBridge = document.getElementById("hubPageNativeMenuBridge");
    {
      const bridge = nativeHeaderMenuBridge;
      if (bridge && rightMenuBtn) {
        const syncBridge = () => {
          if (!rightMenuBtn || rightMenuBtn.offsetParent === null) return;
          const rect = rightMenuBtn.getBoundingClientRect();
          const padX = 4;
          const padY = 4;
          let left = Math.max(0, rect.left - padX);
          let top = Math.max(0, rect.top - padY);
          const width = rect.width + (padX * 2);
          const height = rect.height + (padY * 2);
          const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
          const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
          if (viewportWidth > 0 && left + width > viewportWidth) {
            left = Math.max(0, viewportWidth - width);
          }
          if (viewportHeight > 0 && top + height > viewportHeight) {
            top = Math.max(0, viewportHeight - height);
          }
          bridge.style.left = `${left}px`;
          bridge.style.top = `${top}px`;
          bridge.style.width = `${width}px`;
          bridge.style.height = `${height}px`;
          // opacity:0 (not 0.001) so focus ring is invisible; pointer-events:auto keeps it tappable
          bridge.style.opacity = "0";
          bridge.style.pointerEvents = "auto";
          bridge.style.zIndex = "999";
          bridge.style.background = "transparent";
          bridge.style.color = "transparent";
          bridge.style.border = "0";
          bridge.style.outline = "none";
          bridge.style.webkitTapHighlightColor = "transparent";
          Array.from(bridge.options).forEach((opt) => {
            if (opt.dataset.mobileOnly === "1") {
              opt.hidden = false;
              opt.disabled = false;
            }
          });
        };
        syncBridge();
        window.addEventListener("resize", syncBridge, { passive: true });
        window.addEventListener("scroll", syncBridge, { passive: true });
        window.visualViewport && window.visualViewport.addEventListener("resize", syncBridge, { passive: true });
        window.visualViewport && window.visualViewport.addEventListener("scroll", syncBridge, { passive: true });
        rightMenuBtn.addEventListener("pointerdown", syncBridge, { passive: true });
        bridge.addEventListener("pointerdown", () => resetAgentActionNativeMenu({ clearOptions: true }), { passive: true });
        bridge.addEventListener("change", (e) => {
          const action = e.target.value;
          e.target.value = "";
          if (!action) return;
          void runForwardAction(action, { sourceNode: null, keepComposerOpen: false, keepHeaderOpen: false });
        });
      }
    }
    document.querySelectorAll("[data-desktop-only='1']").forEach((node) => {
      node.hidden = true;
      if (node.tagName === "OPTION") node.disabled = true;
    });
    document.querySelectorAll("[data-mobile-only='1']").forEach((node) => {
      node.hidden = false;
      if (node.tagName === "OPTION") node.disabled = false;
    });
    let paneViewerInterval = null;
    let paneViewerTabScrollRaf = 0;
    let paneViewerTabScrollEndTimer = null;
    let paneViewerOpenRaf = 0;
    let paneViewerInitialFetchTimer = 0;
    let lastPaneViewerTabIdx = 0;
    const gitBranchPanel = document.getElementById("gitBranchPanel");
    const attachedFilesPanel = document.getElementById("attachedFilesPanel");
    const paneTracePanel = document.getElementById("paneTracePanel");
    const nativeHeaderMenuSelect = document.getElementById("hubPageNativeMenuSelect");
    const isAppleTouchDevice = (() => {
      const ua = String(navigator.userAgent || "");
      if (/iP(hone|ad|od)/.test(ua)) return true;
      return navigator.platform === "MacIntel" && Number(navigator.maxTouchPoints || 0) > 1;
    })();
    const useNativeHeaderMenuPicker = !!(isAppleTouchDevice && nativeHeaderMenuSelect && rightMenuBtn);
    const clearNativeHeaderMenuSelection = () => {
      if (!nativeHeaderMenuSelect) return;
      nativeHeaderMenuSelect.value = "";
    };
    const syncNativeHeaderMenuSelectAnchor = () => {
      if (!useNativeHeaderMenuPicker || !nativeHeaderMenuSelect || !rightMenuBtn) return;
      const rect = rightMenuBtn.getBoundingClientRect();
      nativeHeaderMenuSelect.style.left = `${Math.round(rect.left)}px`;
      nativeHeaderMenuSelect.style.top = `${Math.round(rect.top)}px`;
      nativeHeaderMenuSelect.style.width = `${Math.max(1, Math.round(rect.width))}px`;
      nativeHeaderMenuSelect.style.height = `${Math.max(1, Math.round(rect.height))}px`;
    };
    const openNativeHeaderMenuPicker = () => {
      if (!useNativeHeaderMenuPicker || !nativeHeaderMenuSelect) return false;
      syncNativeHeaderMenuSelectAnchor();
      clearNativeHeaderMenuSelection();
      const show = () => {
        if (typeof nativeHeaderMenuSelect.showPicker === "function") {
          try { nativeHeaderMenuSelect.showPicker(); return true; } catch (_) { }
        }
        try { nativeHeaderMenuSelect.focus({ preventScroll: true }); } catch (_) {
          try { nativeHeaderMenuSelect.focus(); } catch (_) { }
        }
        try { nativeHeaderMenuSelect.click(); return true; } catch (_) { }
        return false;
      };
      const opened = show();
      if (!opened) setTimeout(() => { void show(); }, 0);
      return opened;
    };
    if (useNativeHeaderMenuPicker) {
      nativeHeaderMenuSelect.classList.add("is-ios-active");
      syncNativeHeaderMenuSelectAnchor();
    }
    nativeHeaderMenuSelect?.addEventListener("pointerdown", () => {
      resetAgentActionNativeMenu({ clearOptions: true });
    }, { passive: true });
    nativeHeaderMenuSelect?.addEventListener("change", () => {
      const target = String(nativeHeaderMenuSelect.value || "");
      clearNativeHeaderMenuSelection();
      if (!target) return;
      void runForwardAction(target, { sourceNode: null, keepComposerOpen: false, keepHeaderOpen: false });
    });
    nativeHeaderMenuSelect?.addEventListener("blur", () => {
      setTimeout(clearNativeHeaderMenuSelection, 0);
      // Avoid clearing the agent picker right after selecting Add/Remove Agent.
    });
    const headerRoot = document.querySelector(".hub-page-header");
    const hasOpenHeaderMenu = () => !!(gitBranchPanel?.classList.contains("open") || rightMenuPanel?.classList.contains("open") || attachedFilesPanel?.classList.contains("open") || paneTracePanel?.classList.contains("open"));
    const MOBILE_BOTTOM_SHEET_CLOSE_MS = 300;
    const animateBottomSheetOpen = (panel, onOpened = () => { }) => {
      if (!panel) return;
      panel.hidden = false;
      panel.classList.remove("sheet-closing");
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          panel.classList.add("open");
          onOpened();
        });
      });
    };
    const ATTACHED_FILES_SHEET_CLOSE_MS = MOBILE_BOTTOM_SHEET_CLOSE_MS;
    let attachedFilesSheetCloseTimer = 0;
    let attachedFilesSheetScrollY = 0;
    let attachedFilesSheetScrollLocked = false;
    const clearAttachedFilesSheetCloseTimer = () => {
      if (!attachedFilesSheetCloseTimer) return;
      clearTimeout(attachedFilesSheetCloseTimer);
      attachedFilesSheetCloseTimer = 0;
    };
    const lockAttachedFilesSheetScroll = () => {
      if (attachedFilesSheetScrollLocked) return;
      attachedFilesSheetScrollLocked = true;
      attachedFilesSheetScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.documentElement.classList.add("attached-files-sheet-active");
      document.body.classList.add("attached-files-sheet-active");
      document.body.style.top = `-${attachedFilesSheetScrollY}px`;
    };
    const unlockAttachedFilesSheetScroll = () => {
      if (!attachedFilesSheetScrollLocked) return;
      attachedFilesSheetScrollLocked = false;
      document.documentElement.classList.remove("attached-files-sheet-active");
      document.body.classList.remove("attached-files-sheet-active");
      document.body.style.top = "";
      try { window.scrollTo(0, attachedFilesSheetScrollY || 0); } catch (_) { }
    };
    const closeAttachedFilesSheet = ({ immediate = false } = {}) => {
      if (!attachedFilesPanel) return;
      clearAttachedFilesSheetCloseTimer();
      attachedFilesPanel.classList.remove("open");
      if (immediate) {
        attachedFilesPanel.classList.remove("sheet-closing");
        attachedFilesPanel.hidden = true;
        unlockAttachedFilesSheetScroll();
        syncHeaderMenuFocus();
        return;
      }
      attachedFilesPanel.classList.add("sheet-closing");
      attachedFilesSheetCloseTimer = window.setTimeout(() => {
        attachedFilesSheetCloseTimer = 0;
        attachedFilesPanel.classList.remove("sheet-closing");
        attachedFilesPanel.hidden = true;
        unlockAttachedFilesSheetScroll();
        syncHeaderMenuFocus();
      }, ATTACHED_FILES_SHEET_CLOSE_MS);
      syncHeaderMenuFocus();
    };
    const openAttachedFilesSheet = () => {
      if (!attachedFilesPanel) return;
      clearAttachedFilesSheetCloseTimer();
      lockAttachedFilesSheetScroll();
      animateBottomSheetOpen(attachedFilesPanel, () => {
        syncHeaderMenuFocus();
      });
      if (typeof attachedFilesPanel._syncCategoryUi === "function") {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => attachedFilesPanel._syncCategoryUi("auto"));
        });
      }
    };
    const PANE_TRACE_SHEET_CLOSE_MS = MOBILE_BOTTOM_SHEET_CLOSE_MS;
    let paneTraceSheetCloseTimer = 0;
    let paneTraceSheetScrollY = 0;
    let paneTraceSheetScrollLocked = false;
    const clearPaneTraceSheetCloseTimer = () => {
      if (!paneTraceSheetCloseTimer) return;
      clearTimeout(paneTraceSheetCloseTimer);
      paneTraceSheetCloseTimer = 0;
    };
    const lockPaneTraceSheetScroll = () => {
      if (paneTraceSheetScrollLocked) return;
      paneTraceSheetScrollLocked = true;
      paneTraceSheetScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.documentElement.classList.add("pane-trace-sheet-active");
      document.body.classList.add("pane-trace-sheet-active");
      document.body.style.top = `-${paneTraceSheetScrollY}px`;
    };
    const unlockPaneTraceSheetScroll = () => {
      if (!paneTraceSheetScrollLocked) return;
      paneTraceSheetScrollLocked = false;
      document.documentElement.classList.remove("pane-trace-sheet-active");
      document.body.classList.remove("pane-trace-sheet-active");
      document.body.style.top = "";
      try { window.scrollTo(0, paneTraceSheetScrollY || 0); } catch (_) { }
    };
    const paneTraceSheetContentEl = () => paneTracePanel?.querySelector(".pane-trace-sheet-content");
    const ensurePaneTraceSheetDom = () => {
      if (!paneTracePanel) return null;
      let contentEl = paneTraceSheetContentEl();
      if (contentEl) return contentEl;

      const existing = document.createDocumentFragment();
      while (paneTracePanel.firstChild) existing.appendChild(paneTracePanel.firstChild);

      const sheet = document.createElement("div");
      sheet.className = "pane-trace-sheet";
      const sheetPanel = document.createElement("div");
      sheetPanel.className = "pane-trace-sheet-panel";
      const sheetNav = document.createElement("div");
      sheetNav.className = "pane-trace-sheet-nav";
      sheetNav.innerHTML = `
        <div class="pane-trace-sheet-pill"></div>
        <div class="pane-trace-sheet-nav-bar">
          <div class="pane-trace-sheet-title">Pane Trace</div>
          <button type="button" class="pane-trace-sheet-close" aria-label="Close pane trace">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>`;

      contentEl = document.createElement("div");
      contentEl.className = "pane-trace-sheet-content";
      contentEl.appendChild(existing);

      const closeBtn = sheetNav.querySelector(".pane-trace-sheet-close");
      closeBtn?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        exitPaneTraceMode();
      });

      let startY = 0;
      let dragY = 0;
      let dragging = false;
      sheetNav.addEventListener("touchstart", (event) => {
        const touch = event.touches?.[0];
        if (!touch) return;
        startY = touch.clientY;
        dragY = 0;
        dragging = true;
        sheetPanel.style.transition = "none";
      }, { passive: true });
      sheetNav.addEventListener("touchmove", (event) => {
        if (!dragging) return;
        const touch = event.touches?.[0];
        if (!touch) return;
        dragY = Math.max(0, touch.clientY - startY);
        sheetPanel.style.transform = `translateY(${dragY}px)`;
      }, { passive: true });
      const finishDrag = () => {
        if (!dragging) return;
        dragging = false;
        sheetPanel.style.transition = "";
        sheetPanel.style.transform = "";
        if (dragY > 80) exitPaneTraceMode();
      };
      sheetNav.addEventListener("touchend", finishDrag, { passive: true });
      sheetNav.addEventListener("touchcancel", finishDrag, { passive: true });

      sheetPanel.append(sheetNav, contentEl);
      sheet.appendChild(sheetPanel);
      paneTracePanel.appendChild(sheet);
      return contentEl;
    };
    const closePaneTraceSheet = ({ immediate = false } = {}) => {
      if (!paneTracePanel) return;
      clearPaneTraceSheetCloseTimer();
      paneTracePanel.classList.remove("open");
      if (immediate) {
        paneTracePanel.classList.remove("sheet-closing");
        paneTracePanel.hidden = true;
        unlockPaneTraceSheetScroll();
        syncHeaderMenuFocus();
        return;
      }
      paneTracePanel.classList.add("sheet-closing");
      paneTraceSheetCloseTimer = window.setTimeout(() => {
        paneTraceSheetCloseTimer = 0;
        paneTracePanel.classList.remove("sheet-closing");
        paneTracePanel.hidden = true;
        unlockPaneTraceSheetScroll();
        syncHeaderMenuFocus();
      }, PANE_TRACE_SHEET_CLOSE_MS);
      syncHeaderMenuFocus();
    };
    const openPaneTraceSheet = (onOpened = () => { }) => {
      if (!paneTracePanel) return;
      ensurePaneTraceSheetDom();
      clearPaneTraceSheetCloseTimer();
      lockPaneTraceSheetScroll();
      animateBottomSheetOpen(paneTracePanel, () => {
        syncHeaderMenuFocus();
        onOpened();
      });
    };
    const GIT_BRANCH_SHEET_CLOSE_MS = MOBILE_BOTTOM_SHEET_CLOSE_MS;
    let gitBranchSheetCloseTimer = 0;
    let gitBranchSheetScrollY = 0;
    let gitBranchSheetScrollLocked = false;
    const clearGitBranchSheetCloseTimer = () => {
      if (!gitBranchSheetCloseTimer) return;
      clearTimeout(gitBranchSheetCloseTimer);
      gitBranchSheetCloseTimer = 0;
    };
    const lockGitBranchSheetScroll = () => {
      if (gitBranchSheetScrollLocked) return;
      gitBranchSheetScrollLocked = true;
      gitBranchSheetScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.documentElement.classList.add("git-branch-sheet-active");
      document.body.classList.add("git-branch-sheet-active");
      document.body.style.top = `-${gitBranchSheetScrollY}px`;
    };
    const unlockGitBranchSheetScroll = () => {
      if (!gitBranchSheetScrollLocked) return;
      gitBranchSheetScrollLocked = false;
      document.documentElement.classList.remove("git-branch-sheet-active");
      document.body.classList.remove("git-branch-sheet-active");
      document.body.style.top = "";
      try { window.scrollTo(0, gitBranchSheetScrollY || 0); } catch (_) { }
    };
    const gitBranchSheetContentEl = () => gitBranchPanel?.querySelector(".git-branch-sheet-content");
    const ensureGitBranchSheetDom = () => {
      if (!gitBranchPanel) return null;
      let contentEl = gitBranchSheetContentEl();
      if (contentEl) return contentEl;

      const existing = document.createDocumentFragment();
      while (gitBranchPanel.firstChild) existing.appendChild(gitBranchPanel.firstChild);

      const sheet = document.createElement("div");
      sheet.className = "git-branch-sheet";
      const sheetPanel = document.createElement("div");
      sheetPanel.className = "git-branch-sheet-panel";
      const sheetNav = document.createElement("div");
      sheetNav.className = "git-branch-sheet-nav";
      sheetNav.innerHTML = `
        <div class="git-branch-sheet-pill"></div>
        <div class="git-branch-sheet-nav-bar">
          <div class="git-branch-sheet-title">Git Branches</div>
          <button type="button" class="git-branch-sheet-close" aria-label="Close git branches">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>`;

      contentEl = document.createElement("div");
      contentEl.className = "git-branch-sheet-content";
      contentEl.appendChild(existing);

      const closeBtn = sheetNav.querySelector(".git-branch-sheet-close");
      closeBtn?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        closeGitBranchSheet();
      });

      let startY = 0;
      let dragY = 0;
      let dragging = false;
      sheetNav.addEventListener("touchstart", (event) => {
        const touch = event.touches?.[0];
        if (!touch) return;
        startY = touch.clientY;
        dragY = 0;
        dragging = true;
        sheetPanel.style.transition = "none";
      }, { passive: true });
      sheetNav.addEventListener("touchmove", (event) => {
        if (!dragging) return;
        const touch = event.touches?.[0];
        if (!touch) return;
        dragY = Math.max(0, touch.clientY - startY);
        sheetPanel.style.transform = `translateY(${dragY}px)`;
      }, { passive: true });
      const finishDrag = () => {
        if (!dragging) return;
        dragging = false;
        sheetPanel.style.transition = "";
        sheetPanel.style.transform = "";
        if (dragY > 80) closeGitBranchSheet();
      };
      sheetNav.addEventListener("touchend", finishDrag, { passive: true });
      sheetNav.addEventListener("touchcancel", finishDrag, { passive: true });

      sheetPanel.append(sheetNav, contentEl);
      sheet.appendChild(sheetPanel);
      gitBranchPanel.appendChild(sheet);
      return contentEl;
    };
    const closeGitBranchSheet = ({ immediate = false } = {}) => {
      if (!gitBranchPanel) return;
      clearGitBranchSheetCloseTimer();
      gitBranchPanel.classList.remove("open");
      if (immediate) {
        gitBranchPanel.classList.remove("sheet-closing");
        gitBranchPanel.hidden = true;
        unlockGitBranchSheetScroll();
        syncHeaderMenuFocus();
        return;
      }
      gitBranchPanel.classList.add("sheet-closing");
      gitBranchSheetCloseTimer = window.setTimeout(() => {
        gitBranchSheetCloseTimer = 0;
        gitBranchPanel.classList.remove("sheet-closing");
        gitBranchPanel.hidden = true;
        unlockGitBranchSheetScroll();
        syncHeaderMenuFocus();
      }, GIT_BRANCH_SHEET_CLOSE_MS);
      syncHeaderMenuFocus();
    };
    const openGitBranchSheet = async () => {
      if (!gitBranchPanel) return;
      clearGitBranchSheetCloseTimer();
      ensureGitBranchSheetDom();
      setGitBranchSheetTitle("Git Branches");
      lockGitBranchSheetScroll();
      animateBottomSheetOpen(gitBranchPanel, () => {
        syncHeaderMenuFocus();
      });
      const currentSession = currentSessionName || "";
      if (gitBranchLoadedFor !== currentSession) {
        await updateGitBranchPanel();
      } else {
        updateGitBranchLoadMoreUi();
        ensureGitBranchObserver();
      }
    };
    const updateHeaderMenuViewportMetrics = () => {
      if (!headerRoot) return;
      const rect = headerRoot.getBoundingClientRect();
      const top = Math.max(0, Math.round(rect.bottom));
      const left = Math.max(0, Math.round(rect.left));
      const width = Math.max(0, Math.round(rect.width));
      document.documentElement.style.setProperty("--header-menu-top", `${top}px`);
      document.documentElement.style.setProperty("--header-menu-left", `${left}px`);
      document.documentElement.style.setProperty("--header-menu-width", `${width}px`);
    };
    const syncHeaderMenuFocus = () => {
      const fileModalOpen = document.body.classList.contains("file-modal-open");
      const focused = hasOpenHeaderMenu() || fileModalOpen;
      if (focused) updateHeaderMenuViewportMetrics();
    };
    const clearPaneViewerOpenWork = () => {
      if (paneViewerOpenRaf) {
        cancelAnimationFrame(paneViewerOpenRaf);
        paneViewerOpenRaf = 0;
      }
      if (paneViewerInitialFetchTimer) {
        clearTimeout(paneViewerInitialFetchTimer);
        paneViewerInitialFetchTimer = 0;
      }
    };
    function exitPaneTraceMode() {
      const paneEl = document.getElementById("paneViewer");
      clearPaneViewerOpenWork();
      if (paneViewerTabScrollEndTimer) {
        clearTimeout(paneViewerTabScrollEndTimer);
        paneViewerTabScrollEndTimer = null;
      }
      if (paneEl?.classList?.contains("visible") && paneViewerCarousel && paneViewerAgents.length) {
        const w = paneViewerCarousel.offsetWidth;
        if (w) {
          const idx = Math.max(0, Math.min(paneViewerAgents.length - 1, Math.round(paneViewerCarousel.scrollLeft / w)));
          paneViewerLastAgent = paneViewerAgents[idx];
        }
      }
      if (paneEl) {
        paneEl.classList.remove("visible");
        paneEl.hidden = true;
      }
      closePaneTraceSheet();
      if (paneViewerInterval) {
        clearInterval(paneViewerInterval);
        paneViewerInterval = null;
      }
      syncHeaderMenuFocus();
    }
    const isLocalHubHostname = (host = String(location.hostname || "")) =>
      host === "127.0.0.1" || host === "localhost" || host === "[::1]" || host.startsWith("192.168.") || host.startsWith("10.") || /^172\\.(1[6-9]|2\\d|3[01])\\./.test(host);
    let attachedFilesSession = "";
    let attachedFilesPanelRenderSig = "";
    let attachedFilesPanelUpdateSeq = 0;
    let attachedFilesPanelEntries = [];
    let _attachedFilesBrowserPath = "";
    let gitBranchLoadedFor = "";
    let gitBranchCommits = [];
    let gitBranchNextOffset = 0;
    let gitBranchTotalCommits = 0;
    let gitBranchHasMore = false;
    let gitBranchPageLoading = false;
    let gitBranchLoadError = "";
    let gitBranchLoadSeq = 0;
    let gitBranchDetailContext = null;
    let gitBranchDetailNeedsRefresh = false;
    let gitBranchObserver = null;
    const GIT_BRANCH_BATCH = 50;
    const disconnectGitBranchObserver = () => {
      if (!gitBranchObserver) return;
      try { gitBranchObserver.disconnect(); } catch (_) { }
      gitBranchObserver = null;
    };
    const gitBranchCommitListEl = () => gitBranchPanel?.querySelector(".git-branch-commit-list");
    const gitBranchLoadMoreEl = () => gitBranchPanel?.querySelector(".git-branch-load-more");
    const gitBranchScrollRootEl = () => gitBranchSheetContentEl() || gitBranchPanel;
    const gitBranchSheetTitleEl = () => gitBranchPanel?.querySelector(".git-branch-sheet-title");
    const setGitBranchSheetTitle = () => {
      const titleEl = gitBranchSheetTitleEl();
      if (!titleEl) return;
      titleEl.textContent = "Git Branches";
      titleEl.title = "Git Branches";
    };
    const setGitBranchPanelBodyHtml = (html) => {
      const contentEl = ensureGitBranchSheetDom();
      if (contentEl) {
        contentEl.innerHTML = html;
        return;
      }
      if (gitBranchPanel) gitBranchPanel.innerHTML = html;
    };
    const loadingIndicatorHtml = (_label = "Loading…") =>
      '<span class="inline-loading"><span class="inline-loading-spinner" aria-hidden="true"></span></span>';
    const gitBranchCountsHtml = (ins, dels) => {
      const safeIns = Math.max(0, parseInt(ins) || 0);
      const safeDels = Math.max(0, parseInt(dels) || 0);
      const cleanClass = (safeIns || safeDels) ? "" : " clean";
      return `<span class="git-branch-summary-counts${cleanClass}"><span class="git-branch-summary-count ins">+${safeIns}</span><span class="git-branch-summary-count del">-${safeDels}</span></span>`;
    };
    const gitBranchPathCountText = (count) => {
      const safeCount = Math.max(0, parseInt(count) || 0);
      return `${safeCount} ${safeCount === 1 ? "path" : "paths"}`;
    };
    const buildGitBranchSummaryHtml = (data) => {
      const changedPaths = parseInt(data?.worktree_changed_paths) || 0;
      const worktreeAdded = parseInt(data?.worktree_added) || 0;
      const worktreeDeleted = parseInt(data?.worktree_deleted) || 0;
      const worktreeClickable = !!data?.worktree_has_diff;
      const worktreeLabel = changedPaths
        ? `Uncommitted changes`
        : "Working tree clean";
      const worktreeMeta = changedPaths
        ? `<span class="git-branch-summary-meta-text">${gitBranchPathCountText(changedPaths)}</span>`
        : `<span class="git-branch-summary-meta-text">No changes</span>`;
      const worktreeCounts = gitBranchCountsHtml(worktreeAdded, worktreeDeleted);
      const summaryIcon = '<span class="git-branch-summary-icon-wrap"><svg class="git-branch-summary-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M9 10h6"/><path d="M12 7v6"/><path d="M9 17h6"/></svg></span>';
      const summaryChevron = worktreeClickable
        ? '<svg class="git-commit-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>'
        : "";
      return `<div class="git-branch-summary-row${worktreeClickable ? " clickable" : ""}"${worktreeClickable ? ' data-diff-kind="worktree"' : ""}>` +
        summaryIcon +
        `<div class="git-commit-info"><div class="git-branch-summary-label">${escapeHtml(worktreeLabel)}</div><div class="git-commit-meta">${worktreeMeta}${worktreeCounts}</div></div>` +
        summaryChevron +
        `</div>`;
    };
    const buildGitBranchCommitRowHtml = (commit) => {
      const agent = commit?.agent || "";
      let iconInner;
      if (agent && AGENT_ICON_NAMES.has(agentBaseName(agent))) {
        const sub = agentIconInstanceSubHtml(agent);
        iconInner = `<span class="agent-icon-slot"><img class="git-commit-icon" src="${escapeHtml(agentIconSrc(agent))}" alt="${escapeHtml(agent)}">${sub}</span>`;
      } else {
        iconInner = '<span class="git-commit-icon-placeholder"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg></span>';
      }
      const iconHtml = `<span class="git-commit-icon-wrap">${iconInner}</span>`;
      const timeHtml = `<span class="git-commit-time">${escapeHtml(commit?.time || "")}</span>`;
      const subjHtml = `<div class="git-commit-subject">${escapeHtml(commit?.subject || "")}</div>`;
      const ins = Math.max(0, parseInt(commit?.ins) || 0);
      const dels = Math.max(0, parseInt(commit?.dels) || 0);
      const changedPaths = Math.max(0, parseInt(commit?.changed_paths) || 0);
      const pathMeta = `<span class="git-branch-summary-meta-text">${gitBranchPathCountText(changedPaths)}</span>`;
      const statHtml = gitBranchCountsHtml(ins, dels);
      const chevron = `<svg class="git-commit-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>`;
      return `<div class="git-commit-row" data-hash="${escapeHtml(commit?.hash || "")}">${iconHtml}<div class="git-commit-info">${subjHtml}<div class="git-commit-meta">${timeHtml}${pathMeta}${statHtml}</div></div>${chevron}</div>`;
    };
    const renderGitBranchCommitRows = (commits, { append = false } = {}) => {
      const listEl = gitBranchCommitListEl();
      if (!listEl) return;
      if (!append) {
        if (!commits.length) {
          listEl.innerHTML = '<div class="hub-page-menu-item" data-git-branch-empty="1" style="cursor:default;opacity:0.52">No commits</div>';
          return;
        }
        listEl.innerHTML = commits.map((commit) => buildGitBranchCommitRowHtml(commit)).join("");
        return;
      }
      if (!commits.length) return;
      listEl.querySelector("[data-git-branch-empty]")?.remove();
      listEl.insertAdjacentHTML("beforeend", commits.map((commit) => buildGitBranchCommitRowHtml(commit)).join(""));
    };
    const updateGitBranchLoadMoreUi = () => {
      const btn = gitBranchLoadMoreEl();
      if (!btn) return;
      if (!gitBranchHasMore && !gitBranchLoadError) {
        btn.hidden = true;
        btn.disabled = true;
        btn.classList.remove("inline-loading-row");
        btn.textContent = "";
        return;
      }
      btn.hidden = false;
      btn.disabled = gitBranchPageLoading;
      if (gitBranchLoadError) {
        btn.classList.remove("inline-loading-row");
        btn.textContent = "Retry loading commits";
      } else if (gitBranchPageLoading) {
        btn.classList.add("inline-loading-row");
        btn.innerHTML = loadingIndicatorHtml("Loading…");
      } else if (gitBranchTotalCommits > 0) {
        btn.classList.remove("inline-loading-row");
        btn.textContent = `Load more commits (${gitBranchCommits.length}/${gitBranchTotalCommits})`;
      } else {
        btn.classList.remove("inline-loading-row");
        btn.textContent = "Load more commits";
      }
    };
    const ensureGitBranchObserver = () => {
      disconnectGitBranchObserver();
      const btn = gitBranchLoadMoreEl();
      if (!btn || !gitBranchHasMore || gitBranchPageLoading || gitBranchLoadError || typeof IntersectionObserver !== "function") return;
      gitBranchObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          void loadGitBranchOverviewPage();
        });
      }, {
        root: gitBranchScrollRootEl(),
        rootMargin: "220px 0px 220px 0px",
        threshold: 0.01,
      });
      gitBranchObserver.observe(btn);
    };
    const renderGitBranchPanelShell = (data) => {
      const summaryHtml = buildGitBranchSummaryHtml(data);
      setGitBranchPanelBodyHtml(`
        <div class="git-branch-stack">
          <div class="git-branch-list-view">
            <div class="git-branch-summary-wrap">${summaryHtml}</div>
            <div class="git-branch-commit-list"></div>
            <button type="button" class="hub-page-menu-item git-branch-load-more" hidden></button>
          </div>
          <div class="git-branch-detail-view">
            <button type="button" class="git-commit-detail-head" aria-label="コミット一覧に戻る"></button>
            <div class="git-commit-detail-body"></div>
          </div>
        </div>`);
    };
    const applyGitBranchOverviewPage = (data, { reset = false } = {}) => {
      const commits = Array.isArray(data?.recent_commits) ? data.recent_commits : [];
      if (reset) {
        renderGitBranchPanelShell(data || {});
        gitBranchCommits = [];
      }
      if (commits.length) {
        gitBranchCommits = reset ? commits.slice() : gitBranchCommits.concat(commits);
      } else if (reset) {
        gitBranchCommits = [];
      }
      gitBranchTotalCommits = Math.max(0, parseInt(data?.total_commits) || 0);
      gitBranchNextOffset = Math.max(0, parseInt(data?.next_offset) || gitBranchCommits.length);
      gitBranchHasMore = !!data?.has_more;
      if (reset) {
        renderGitBranchCommitRows(gitBranchCommits, { append: false });
      } else if (commits.length) {
        renderGitBranchCommitRows(commits, { append: true });
      }
      updateGitBranchLoadMoreUi();
      ensureGitBranchObserver();
    };
    const buildGitCommitFileRowHtml = (entry, { allowUndo = false } = {}) => {
      const path = String(entry?.path || "").trim();
      const ins = Math.max(0, parseInt(entry?.ins) || 0);
      const dels = Math.max(0, parseInt(entry?.dels) || 0);
      const changed = Math.max(0, parseInt(entry?.changed) || (ins + dels));
      const binary = !!entry?.binary;
      const lineMeta = binary
        ? "binary"
        : `${changed} ${changed === 1 ? "line" : "lines"}`;
      const undoHtml = allowUndo
        ? `<button type="button" class="git-commit-file-undo" data-path="${escapeHtml(path)}">Undo</button>`
        : "";
      return `<div class="git-commit-file-row" data-path="${escapeHtml(path)}">` +
        `<div class="git-commit-file-top"><div class="git-commit-file-path" title="${escapeHtml(path)}">${escapeHtml(path)}</div>${undoHtml}</div>` +
        `<div class="git-commit-file-meta"><span class="git-branch-summary-meta-text">${escapeHtml(lineMeta)}</span>${gitBranchCountsHtml(ins, dels)}</div>` +
        `</div>`;
    };
    const renderGitCommitFileStatsInto = async (wrapEl, hash, { allowUndo = false } = {}) => {
      if (!wrapEl) return null;
      wrapEl.innerHTML = `<div class="git-commit-file-empty inline-loading-row">${loadingIndicatorHtml("Loading…")}</div>`;
      const res = await fetchWithTimeout(`/git-diff-files?hash=${encodeURIComponent(hash || "")}`, {}, 5000);
      const data = await res.json();
      const files = Array.isArray(data?.files) ? data.files : [];
      if (!files.length) {
        wrapEl.innerHTML = '<div class="git-commit-file-empty">No changed files</div>';
        return data;
      }
      wrapEl.innerHTML = `<div class="git-commit-file-list">${files.map((entry) => buildGitCommitFileRowHtml(entry, { allowUndo })).join("")}</div>`;
      return data;
    };
    const closeGitBranchInlineDiff = ({ refreshList = false } = {}) => {
      if (!gitBranchPanel) return;
      gitBranchPanel.classList.remove("git-branch-transitioning");
      gitBranchPanel.classList.remove("git-branch-mode-detail");
      setGitBranchSheetTitle("Git Branches");
      const body = gitBranchPanel.querySelector(".git-commit-detail-body");
      if (body) body.innerHTML = "";
      const head = gitBranchPanel.querySelector(".git-commit-detail-head");
      if (head) head.innerHTML = "";
      gitBranchDetailContext = null;
      updateGitBranchLoadMoreUi();
      ensureGitBranchObserver();
      const shouldRefresh = !!refreshList;
      gitBranchDetailNeedsRefresh = false;
      if (shouldRefresh) {
        void loadGitBranchOverviewPage({ reset: true });
      }
    };
    const loadGitBranchOverviewPage = async ({ reset = false } = {}) => {
      if (!gitBranchPanel) return;
      if (gitBranchPageLoading) return;
      if (!reset && !gitBranchHasMore && !gitBranchLoadError) return;
      const loadSeq = ++gitBranchLoadSeq;
      gitBranchPageLoading = true;
      gitBranchLoadError = "";
      disconnectGitBranchObserver();
      if (reset) {
        closeGitBranchInlineDiff();
        setGitBranchSheetTitle("Git Branches");
        gitBranchHasMore = false;
        gitBranchNextOffset = 0;
        gitBranchTotalCommits = 0;
        gitBranchCommits = [];
        setGitBranchPanelBodyHtml(`<div class="hub-page-menu-item inline-loading-row" style="cursor:default;opacity:0.72">${loadingIndicatorHtml("Loading…")}</div>`);
      } else {
        updateGitBranchLoadMoreUi();
      }
      try {
        const params = new URLSearchParams({
          offset: String(reset ? 0 : gitBranchNextOffset),
          limit: String(GIT_BRANCH_BATCH),
        });
        if (reset) params.set("refresh", "1");
        const res = await fetchWithTimeout(`/git-branch-overview?${params.toString()}`, {}, 5000);
        if (!res.ok) throw new Error(reset ? "Failed to load branch overview" : "Failed to load more commits");
        const data = await res.json();
        if (loadSeq !== gitBranchLoadSeq) return;
        applyGitBranchOverviewPage(data, { reset });
        gitBranchLoadedFor = currentSessionName || "";
      } catch (err) {
        if (loadSeq !== gitBranchLoadSeq) return;
        if (reset) {
          gitBranchLoadedFor = "";
          setGitBranchPanelBodyHtml(`<div class="hub-page-menu-item" style="cursor:default;opacity:0.72">${escapeHtml(err?.message || "Failed to load branch overview")}</div>`);
        } else {
          gitBranchLoadError = err?.message || "Failed to load more commits";
        }
      } finally {
        if (loadSeq !== gitBranchLoadSeq) return;
        gitBranchPageLoading = false;
        updateGitBranchLoadMoreUi();
        ensureGitBranchObserver();
      }
    };
    const updateGitBranchPanel = async () => {
      await loadGitBranchOverviewPage({ reset: true });
    };
    if (gitBranchPanel) {
      gitBranchPanel.addEventListener("click", async (e) => {
        const loadMoreBtn = e.target.closest(".git-branch-load-more");
        if (loadMoreBtn) {
          e.stopPropagation();
          e.preventDefault();
          await loadGitBranchOverviewPage();
          return;
        }
        const undoBtn = e.target.closest(".git-commit-file-undo");
        if (undoBtn) {
          e.stopPropagation();
          e.preventDefault();
          const filePath = String(undoBtn.dataset.path || "").trim();
          if (!filePath) return;
          if (undoBtn.dataset.busy === "1") return;
          undoBtn.dataset.busy = "1";
          undoBtn.disabled = true;
          setStatus(`undoing ${filePath}...`);
          try {
            const r = await fetch("/git-restore-file", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: filePath }),
            });
            const d = await r.json().catch(() => ({}));
            if (!r.ok || !d?.ok) {
              throw new Error(d?.error || "undo failed");
            }
            setStatus(`restored ${filePath}`);
            setTimeout(() => setStatus(""), 1800);
            gitBranchDetailNeedsRefresh = true;
            if (gitBranchDetailContext?.kind === "worktree" && gitBranchDetailContext?.wrapEl) {
              await renderGitCommitFileStatsInto(gitBranchDetailContext.wrapEl, "", { allowUndo: true });
              const stillHasRows = !!gitBranchDetailContext.wrapEl.querySelector(".git-commit-file-row");
              if (!stillHasRows) {
                closeGitBranchInlineDiff({ refreshList: true });
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
        if (e.target.closest(".git-commit-detail-head")) {
          e.stopPropagation();
          closeGitBranchInlineDiff({ refreshList: gitBranchDetailNeedsRefresh });
          return;
        }
        if (gitBranchPanel.classList.contains("git-branch-mode-detail")) return;
        const row = e.target.closest(".git-commit-row, .git-branch-summary-row");
        if (!row) return;
        const diffKind = row.dataset.diffKind || "";
        const hash = row.dataset.hash;
        if (!hash && !diffKind) return;
        e.stopPropagation();
        closeGitBranchInlineDiff();
        disconnectGitBranchObserver();
        gitBranchDetailNeedsRefresh = false;
        gitBranchPanel.classList.add("git-branch-transitioning");
        const subject = diffKind === "worktree"
          ? (row.querySelector(".git-branch-summary-label")?.textContent?.trim() || "Uncommitted changes")
          : (row.querySelector(".git-commit-subject")?.textContent?.trim() || hash.slice(0, 7));
        const headEl = gitBranchPanel.querySelector(".git-commit-detail-head");
        const bodyEl = gitBranchPanel.querySelector(".git-commit-detail-body");
        if (headEl) {
          headEl.title = subject;
          headEl.innerHTML = row.outerHTML;
        }
        if (!bodyEl) return;
        const wrapEl = document.createElement("div");
        wrapEl.className = "git-commit-file-wrap";
        bodyEl.appendChild(wrapEl);
        setGitBranchSheetTitle("Git Branches");
        gitBranchPanel.classList.add("git-branch-mode-detail");
        gitBranchDetailContext = {
          kind: diffKind === "worktree" ? "worktree" : "commit",
          hash: diffKind === "worktree" ? "" : String(hash || ""),
          wrapEl,
        };
        const scrollRoot = gitBranchScrollRootEl();
        if (scrollRoot) scrollRoot.scrollTop = 0;
        requestAnimationFrame(() => {
          gitBranchPanel?.classList.remove("git-branch-transitioning");
        });
        try {
          await renderGitCommitFileStatsInto(
            wrapEl,
            diffKind === "worktree" ? "" : hash,
            { allowUndo: diffKind === "worktree" },
          );
        } catch (err) {
          wrapEl.innerHTML = '<div class="git-commit-file-empty">Failed to load file stats</div>';
        }
      });
    }
    const updateAttachedFilesPanel = async (entries) => {
      if (!attachedFilesPanel) return;
      attachedFilesPanelEntries = Array.isArray(entries) ? entries : [];
      document.querySelectorAll(".hub-page-menu-btn .attached-files-badge").forEach((node) => node.remove());

      const normalizeRepoPath = (value) => String(value || "")
        .replace(/\\/g, "/")
        .replace(/^\/+|\/+$/g, "");
      const sessionKey = attachedFilesSession || currentSessionName || "";
      if (attachedFilesPanel._repoSessionKey !== sessionKey) {
        attachedFilesPanel._repoSessionKey = sessionKey;
        _attachedFilesBrowserPath = "";
        attachedFilesPanelRenderSig = "";
        attachedFilesPanel._repoDirCache = new Map();
        attachedFilesPanel._repoDirInFlight = new Map();
        attachedFilesPanel._repoDirCacheVersion = 0;
      }
      if (!(attachedFilesPanel._repoDirCache instanceof Map)) {
        attachedFilesPanel._repoDirCache = new Map();
      }
      if (!(attachedFilesPanel._repoDirInFlight instanceof Map)) {
        attachedFilesPanel._repoDirInFlight = new Map();
      }
      const dirCache = attachedFilesPanel._repoDirCache;
      const dirInFlight = attachedFilesPanel._repoDirInFlight;

      const fetchRepoDir = async (rawPath) => {
        const path = normalizeRepoPath(rawPath);
        if (dirCache.has(path)) return dirCache.get(path);
        if (dirInFlight.has(path)) return dirInFlight.get(path);
        const loadPromise = (async () => {
          let res;
          try {
            res = await fetchWithTimeout(`/files-dir?path=${encodeURIComponent(path)}`, {}, 12000);
          } catch (err) {
            const isTimeout = /timeout/i.test(String(err?.message || ""));
            if (!isTimeout) throw err;
            res = await fetchWithTimeout(`/files-dir?path=${encodeURIComponent(path)}`, {}, 20000);
          }
          if (!res.ok) {
            throw new Error(res.status === 404 ? "Directory not found" : "Failed to load directory");
          }
          const payload = await res.json().catch(() => ({}));
          const rawEntries = Array.isArray(payload?.entries) ? payload.entries : [];
          const normalizedEntries = rawEntries
            .filter((item) => item && typeof item.path === "string")
            .map((item) => {
              const entryPath = normalizeRepoPath(item.path);
              const entryName = String(item.name || entryPath.split("/").pop() || entryPath);
              const entryKind = item.kind === "dir" ? "dir" : "file";
              const rawSize = Number(item.size);
              return {
                name: entryName,
                path: entryPath,
                kind: entryKind,
                size: entryKind === "file" && Number.isFinite(rawSize) && rawSize >= 0 ? rawSize : null,
              };
            })
            .sort((a, b) => {
              if (a.kind !== b.kind) return a.kind === "dir" ? -1 : 1;
              return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
            });
          dirCache.set(path, normalizedEntries);
          attachedFilesPanel._repoDirCacheVersion = (Number(attachedFilesPanel._repoDirCacheVersion) || 0) + 1;
          return normalizedEntries;
        })().finally(() => {
          dirInFlight.delete(path);
        });
        dirInFlight.set(path, loadPromise);
        return loadPromise;
      };

      const isMobileMenu = document.documentElement.dataset.mobile === "1";
      const folderIcon = wrapFileIcon('<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h5.1a1.5 1.5 0 0 1 1.06.44l1.9 1.9a1.5 1.5 0 0 0 1.06.44H19.5A1.5 1.5 0 0 1 21 9.28V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>');
      const chevronRightIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 6 15 12 9 18"/></svg>';
      const backIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 6 9 12 15 18"/></svg>';

      const renderPanel = (rawPath, entriesForPath, { loading = false, error = "", transition = "none" } = {}) => {
        const path = normalizeRepoPath(rawPath);
        const dirVersion = Number(attachedFilesPanel._repoDirCacheVersion) || 0;
        const nextRenderSig = JSON.stringify({
          session: sessionKey,
          version: dirVersion,
          path,
          loading: loading ? 1 : 0,
          error: error ? 1 : 0,
        });
        if (nextRenderSig === attachedFilesPanelRenderSig && attachedFilesPanel.innerHTML) return;
        attachedFilesPanelRenderSig = nextRenderSig;
        _attachedFilesBrowserPath = path;
        attachedFilesPanel.innerHTML = "";

        const browser = document.createElement("div");
        browser.className = `repo-browser ${isMobileMenu ? "repo-browser-mobile" : "repo-browser-desktop"}`;
        const goToParentPath = () => {
          if (!path) return;
          const parts = path.split("/").filter(Boolean);
          parts.pop();
          void openRepoPath(parts.join("/"), { transition: "back" });
        };
        if (!isMobileMenu) {
          const head = document.createElement("div");
          head.className = "repo-browser-head";

          const backBtn = document.createElement("button");
          backBtn.type = "button";
          backBtn.className = "repo-browser-back";
          backBtn.innerHTML = backIcon;
          backBtn.title = "Go to parent directory";
          if (!path) backBtn.disabled = true;
          backBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            goToParentPath();
          });

          const pathText = document.createElement("div");
          pathText.className = "repo-browser-path";
          pathText.textContent = path ? `Repository / ${path}` : "Repository";

          head.append(backBtn, pathText);
          browser.appendChild(head);
        }
        const appendMessage = (container, text, className = "repo-browser-empty", { loading = false } = {}) => {
          const node = document.createElement("div");
          node.className = className;
          if (loading) {
            node.classList.add("inline-loading-row");
            node.innerHTML = loadingIndicatorHtml(text || "Loading…");
          } else {
            node.textContent = text;
          }
          container.appendChild(node);
        };
        const appendDirectoryItem = (container, dirEntry, selected = false) => {
          const btn = document.createElement("button");
          btn.type = "button";
          const isHidden = dirEntry.name.startsWith(".");
          btn.className = `repo-browser-item repo-browser-dir${selected ? " selected" : ""}${isHidden ? " repo-browser-item-dimmed" : ""}`;
          btn.title = dirEntry.path;

          const icon = document.createElement("span");
          icon.className = "repo-browser-item-icon";
          icon.setAttribute("aria-hidden", "true");
          icon.innerHTML = folderIcon;

          const name = document.createElement("span");
          name.className = "repo-browser-item-name";
          name.textContent = dirEntry.name;

          const chevron = document.createElement("span");
          chevron.className = "repo-browser-item-chevron";
          chevron.setAttribute("aria-hidden", "true");
          chevron.innerHTML = chevronRightIcon;

          btn.append(icon, name, chevron);
          btn.addEventListener("mousedown", (event) => event.preventDefault());
          btn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            void openRepoPath(dirEntry.path, { transition: "forward" });
          });
          container.appendChild(btn);
        };
        const appendFileItem = (container, fileEntry) => {
          const ext = fileExtForPath(fileEntry.path);
          const nameText = displayAttachmentFilename(fileEntry.path);
          const isHidden = nameText.startsWith(".");
          const iconMarkup = FILE_ICONS[ext] || FILE_SVG_ICONS.file;
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = `repo-browser-item repo-browser-file${isHidden ? " repo-browser-item-dimmed" : ""}`;
          btn.title = fileEntry.path;

          const icon = document.createElement("span");
          icon.className = "repo-browser-item-icon";
          icon.setAttribute("aria-hidden", "true");
          icon.innerHTML = iconMarkup;

          const name = document.createElement("span");
          name.className = "repo-browser-item-name";
          name.textContent = nameText;

          btn.append(icon, name);

          const sizeLabel = formatFileSize(fileEntry.size);
          if (sizeLabel) {
            const size = document.createElement("span");
            size.className = "repo-browser-item-size";
            size.textContent = sizeLabel;
            btn.appendChild(size);
          }

          btn.addEventListener("mousedown", (event) => event.preventDefault());
          btn.addEventListener("click", async (event) => {
            event.preventDefault();
            event.stopPropagation();
            await openFileSurface(fileEntry.path, ext, btn, event);
          });
          container.appendChild(btn);
        };
        const buildEntryGroups = (items) => {
          const list = Array.isArray(items) ? items : [];
          return {
            dirs: list.filter((entry) => entry?.kind === "dir"),
            files: list.filter((entry) => entry?.kind !== "dir"),
          };
        };
        const mountInMobileSheet = (contentEl) => {
          const sheet = document.createElement("div");
          sheet.className = "attached-files-sheet";
          const sheetPanel = document.createElement("div");
          sheetPanel.className = "attached-files-sheet-panel";
          const sheetNav = document.createElement("div");
          sheetNav.className = "attached-files-sheet-nav";
          sheetNav.innerHTML = `
            <div class="attached-files-sheet-pill"></div>
            <div class="attached-files-sheet-nav-bar">
              <button type="button" class="attached-files-sheet-back" aria-label="Go to parent directory">${backIcon}</button>
              <div class="attached-files-sheet-title"></div>
              <button type="button" class="attached-files-sheet-close" aria-label="Close attached files">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>`;
          const backBtn = sheetNav.querySelector(".attached-files-sheet-back");
          const titleEl = sheetNav.querySelector(".attached-files-sheet-title");
          if (titleEl) {
            titleEl.textContent = path ? `Repository / ${path}` : "Repository";
          }
          if (backBtn) {
            if (!path) backBtn.disabled = true;
            backBtn.addEventListener("click", (event) => {
              event.preventDefault();
              event.stopPropagation();
              goToParentPath();
            });
          }
          const closeBtn = sheetNav.querySelector(".attached-files-sheet-close");
          closeBtn?.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            closeAttachedFilesSheet();
          });
          let startY = 0;
          let dragY = 0;
          let dragging = false;
          sheetNav.addEventListener("touchstart", (event) => {
            const touch = event.touches?.[0];
            if (!touch) return;
            startY = touch.clientY;
            dragY = 0;
            dragging = true;
            sheetPanel.style.transition = "none";
          }, { passive: true });
          sheetNav.addEventListener("touchmove", (event) => {
            if (!dragging) return;
            const touch = event.touches?.[0];
            if (!touch) return;
            dragY = Math.max(0, touch.clientY - startY);
            sheetPanel.style.transform = `translateY(${dragY}px)`;
          }, { passive: true });
          const finishDrag = () => {
            if (!dragging) return;
            dragging = false;
            sheetPanel.style.transition = "";
            sheetPanel.style.transform = "";
            if (dragY > 80) {
              closeAttachedFilesSheet();
            }
          };
          sheetNav.addEventListener("touchend", finishDrag, { passive: true });
          sheetNav.addEventListener("touchcancel", finishDrag, { passive: true });
          let swipeStartX = 0;
          let swipeStartY = 0;
          let swipeTracking = false;
          let swipeBackReady = false;
          const resetSwipeBack = () => {
            swipeTracking = false;
            swipeBackReady = false;
          };
          contentEl.addEventListener("touchstart", (event) => {
            if (!path) return;
            const touch = event.touches?.[0];
            if (!touch) return;
            swipeStartX = touch.clientX;
            swipeStartY = touch.clientY;
            swipeTracking = true;
            swipeBackReady = false;
          }, { passive: true });
          contentEl.addEventListener("touchmove", (event) => {
            if (!swipeTracking) return;
            const touch = event.touches?.[0];
            if (!touch) {
              resetSwipeBack();
              return;
            }
            const deltaX = touch.clientX - swipeStartX;
            const deltaY = touch.clientY - swipeStartY;
            if (Math.abs(deltaY) > 42) {
              resetSwipeBack();
              return;
            }
            if (deltaX > 56 && Math.abs(deltaX) > Math.abs(deltaY) * 1.2) {
              swipeBackReady = true;
            }
          }, { passive: true });
          contentEl.addEventListener("touchend", () => {
            if (!swipeTracking) return;
            const shouldBack = swipeBackReady;
            resetSwipeBack();
            if (shouldBack) {
              goToParentPath();
            }
          }, { passive: true });
          contentEl.addEventListener("touchcancel", resetSwipeBack, { passive: true });
          sheetPanel.append(sheetNav, contentEl);
          sheet.appendChild(sheetPanel);
          attachedFilesPanel.appendChild(sheet);
        };

        const allEntries = Array.isArray(entriesForPath) ? entriesForPath : [];
        if (!isMobileMenu) {
          const columns = document.createElement("div");
          columns.className = "repo-browser-columns";
          const segments = path ? path.split("/").filter(Boolean) : [];
          const columnDefs = [];
          let prefix = "";
          columnDefs.push({ path: "", selectedName: segments[0] || "" });
          for (let idx = 0; idx < segments.length; idx += 1) {
            prefix = prefix ? `${prefix}/${segments[idx]}` : segments[idx];
            columnDefs.push({ path: prefix, selectedName: segments[idx + 1] || "" });
          }
          columnDefs.forEach((columnDef) => {
            const columnEl = document.createElement("div");
            columnEl.className = "repo-browser-column";
            const columnList = document.createElement("div");
            columnList.className = "repo-browser-column-list";
            const sourceEntries = columnDef.path === path ? allEntries : (dirCache.get(columnDef.path) || []);
            const { dirs, files } = buildEntryGroups(sourceEntries);
            const isActiveColumn = columnDef.path === path;
            if (isActiveColumn && loading) {
              appendMessage(columnList, "Loading…", "repo-browser-empty", { loading: true });
            } else if (isActiveColumn && error) {
              appendMessage(columnList, error, "repo-browser-empty error");
            } else if (!dirs.length && !files.length) {
              appendMessage(columnList, "No files in this directory");
            } else {
              dirs.forEach((dirEntry) => appendDirectoryItem(columnList, dirEntry, columnDef.selectedName === dirEntry.name));
              files.forEach((fileEntry) => appendFileItem(columnList, fileEntry));
            }
            columnEl.appendChild(columnList);
            columns.appendChild(columnEl);
          });
          browser.appendChild(columns);
          attachedFilesPanel.appendChild(browser);
          requestAnimationFrame(() => {
            columns.scrollLeft = columns.scrollWidth;
          });
          return;
        }

        const list = document.createElement("div");
        list.className = "repo-browser-list";
        if (isMobileMenu && (transition === "forward" || transition === "back")) {
          list.dataset.transition = transition;
        }
        const { dirs: directoryEntries, files: fileEntries } = buildEntryGroups(allEntries);
        if (loading) {
          appendMessage(list, "Loading…", "repo-browser-empty", { loading: true });
        } else if (error) {
          appendMessage(list, error, "repo-browser-empty error");
        } else if (!directoryEntries.length && !fileEntries.length) {
          appendMessage(list, "No files in this directory");
        } else {
          directoryEntries.forEach((dirEntry) => appendDirectoryItem(list, dirEntry));
          fileEntries.forEach((fileEntry) => appendFileItem(list, fileEntry));
        }
        browser.appendChild(list);
        if (isMobileMenu) {
          mountInMobileSheet(browser);
        } else {
          attachedFilesPanel.appendChild(browser);
        }
      };

      const openRepoPath = async (rawPath, { transition = "none" } = {}) => {
        const path = normalizeRepoPath(rawPath);
        if (attachedFilesPanel._repoSessionKey !== sessionKey) return;
        const ensurePathLoaded = async (targetPath) => {
          const normalizedPath = normalizeRepoPath(targetPath);
          const segments = normalizedPath ? normalizedPath.split("/").filter(Boolean) : [];
          await fetchRepoDir("");
          let prefix = "";
          for (const segment of segments) {
            prefix = prefix ? `${prefix}/${segment}` : segment;
            await fetchRepoDir(prefix);
          }
        };
        const hasPathChainCached = (targetPath) => {
          const normalizedPath = normalizeRepoPath(targetPath);
          if (!dirCache.has("")) return false;
          if (!normalizedPath) return true;
          const segments = normalizedPath.split("/").filter(Boolean);
          let prefix = "";
          for (const segment of segments) {
            prefix = prefix ? `${prefix}/${segment}` : segment;
            if (!dirCache.has(prefix)) return false;
          }
          return true;
        };
        const cachedEntries = dirCache.get(path);
        const hasAllColumns = hasPathChainCached(path);
        if (cachedEntries && hasAllColumns) {
          renderPanel(path, cachedEntries, { transition });
          return;
        }
        if (cachedEntries) {
          renderPanel(path, cachedEntries, { transition });
        } else {
          renderPanel(path, [], { loading: true, transition });
        }
        try {
          await ensurePathLoaded(path);
          if (attachedFilesPanel._repoSessionKey !== sessionKey) return;
          renderPanel(path, dirCache.get(path) || [], { transition });
        } catch (err) {
          if (attachedFilesPanel._repoSessionKey !== sessionKey) return;
          const errorText = String(err?.message || "Failed to load directory");
          if (path) {
            try {
              const rootEntries = await fetchRepoDir("");
              if (attachedFilesPanel._repoSessionKey !== sessionKey) return;
              renderPanel("", rootEntries, { transition: "back" });
              return;
            } catch (_) { }
          }
          renderPanel(path, [], { error: errorText, transition });
        }
      };

      attachedFilesPanel._syncCategoryUi = () => {
        void openRepoPath(_attachedFilesBrowserPath, { transition: "none" });
      };
      attachedFilesPanel._scrollToCategory = () => false;
      const panelVisible = attachedFilesPanel.classList.contains("open") && !attachedFilesPanel.hidden;
      if (!panelVisible) return;
      await openRepoPath(_attachedFilesBrowserPath, { transition: "none" });
    };
    const closeHeaderMenus = () => {
      resetAgentActionNativeMenu({ clearOptions: true });
      closeGitBranchInlineDiff();
      exitPaneTraceMode();
      closeGitBranchSheet({ immediate: true });
      closeSyncStatusPanel({ immediate: true });
      rightMenuPanel?.classList.remove("open");
      if (rightMenuPanel) rightMenuPanel.hidden = true;
      rightMenuBtn?.classList.remove("open");
      closeAttachedFilesSheet({ immediate: true });
      syncHeaderMenuFocus();
    };
    const toggleHeaderMenu = (panel, button) => {
      if (!panel || !button) return;
      const nextOpen = panel.hidden || !panel.classList.contains("open");
      if (nextOpen) updateHeaderMenuViewportMetrics();
      panel.hidden = !nextOpen;
      panel.classList.toggle("open", nextOpen);
      button.classList.toggle("open", nextOpen);
      if (!nextOpen && panel === rightMenuPanel) exitPaneTraceMode();
      syncHeaderMenuFocus();
    };
    const handleNativeMenuAction = async (payload) => {
      const data = payload || {};
      if (data.action === "agent") {
        const mode = String(data.mode || "");
        const agent = String(data.agent || "");
        if ((mode === "add" || mode === "remove") && agent) {
          closeHeaderMenus();
          await performAgentAction(mode, agent);
        }
        return;
      }
      const action = String(data.action || "");
      if (!action) return;
      await runForwardAction(action, { sourceNode: null, keepComposerOpen: false, keepHeaderOpen: false });
    };
    window.addEventListener("message", (event) => {
      if (!(event.data && event.data.type === "multiagent-native-menu-action")) return;
      void handleNativeMenuAction(event.data.payload);
    });
    window.addEventListener("multiagent-native-menu-action", (event) => {
      void handleNativeMenuAction(event.detail || {});
    });
    rightMenuBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      closeFileModal({ restoreFocus: false });
      resetAgentActionNativeMenu({ clearOptions: true });
      if (useNativeHeaderMenuPicker) {
        if (openNativeHeaderMenuPicker()) return;
      }
      closeHeaderMenus();
    });
    attachedFilesPanel?.addEventListener("click", (event) => {
      if (event.target !== attachedFilesPanel) return;
      event.preventDefault();
      event.stopPropagation();
      closeAttachedFilesSheet();
    });
    gitBranchPanel?.addEventListener("click", (event) => {
      if (event.target !== gitBranchPanel) return;
      event.preventDefault();
      event.stopPropagation();
      closeGitBranchSheet();
    });
    headerRoot?.addEventListener("click", (event) => {
      if (fileModal.hidden) return;
      if (event.defaultPrevented) return;
      if (event.target.closest(".hub-page-menu-btn, .hub-page-menu-panel, button, a, details, summary, input, textarea, select, label, [role='button']")) {
        return;
      }
      closeFileModal({ restoreFocus: false });
    });
    const closeQuickMore = () => {
      if (quickMore) quickMore.open = false;
      closePlusMenu();
      closeHeaderMenus();
    };
    const stopCameraModeStream = () => {
      if (cameraModeVideo) {
        try { cameraModeVideo.pause(); } catch (_) { }
        try { cameraModeVideo.srcObject = null; } catch (_) { }
      }
      if (cameraModeStream) {
        cameraModeStream.getTracks().forEach((track) => {
          try {
            track.onended = null;
            track.stop();
          } catch (_) { }
        });
      }
      cameraModeStream = null;
    };
    const canvasToJpegBlob = (canvas, quality = 0.7) => new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error("image encoding failed"));
      }, "image/jpeg", quality);
    });
    const decodeImageForResize = async (blob) => {
      if (typeof createImageBitmap === "function") {
        try {
          return await createImageBitmap(blob);
        } catch (_) { }
      }
      return await new Promise((resolve, reject) => {
        const url = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
          URL.revokeObjectURL(url);
          resolve(img);
        };
        img.onerror = () => {
          URL.revokeObjectURL(url);
          reject(new Error("image decode failed"));
        };
        img.src = url;
      });
    };
    const resizeCameraModeBlob = async (blob, { maxSide = 1280, quality = 0.7 } = {}) => {
      const image = await decodeImageForResize(blob);
      try {
        const width = Number(image.width || image.videoWidth || image.naturalWidth || 0);
        const height = Number(image.height || image.videoHeight || image.naturalHeight || 0);
        if (!width || !height) return blob;
        const scale = Math.min(1, maxSide / Math.max(width, height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        const ctx = canvas.getContext("2d", { alpha: false });
        if (!ctx) return blob;
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
        return await canvasToJpegBlob(canvas, quality);
      } finally {
        try { image.close?.(); } catch (_) { }
      }
    };
    const captureCameraModeFrameBlob = async ({ maxSide = 1280, quality = 0.7 } = {}) => {
      if (!cameraModeVideo) throw new Error("camera unavailable");
      const width = Number(cameraModeVideo.videoWidth || 0);
      const height = Number(cameraModeVideo.videoHeight || 0);
      if (!width || !height) throw new Error("camera not ready");
      const scale = Math.min(1, maxSide / Math.max(width, height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      const ctx = canvas.getContext("2d", { alpha: false });
      if (!ctx) throw new Error("camera capture unavailable");
      ctx.drawImage(cameraModeVideo, 0, 0, canvas.width, canvas.height);
      return canvasToJpegBlob(canvas, quality);
    };
    const uploadCameraModeBlob = async (blob, filename) => {
      const res = await fetch("/upload", {
        method: "POST",
        headers: {
          "Content-Type": blob.type || "image/jpeg",
          "X-Filename": encodeURIComponent(filename || `camera_${Date.now()}.jpg`),
        },
        body: blob,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok || !data.path) {
        throw new Error(data.error || "upload failed");
      }
      return data.path;
    };
    const sendCameraModeAttachment = async (path, target) => {
      const res = await fetch("/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, message: `[Attached: ${path}]` }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        throw new Error(data.error || "send failed");
      }
      return data;
    };
    const sendCameraModeText = async (text, target) => {
      const message = String(text || "").trim();
      if (!message) {
        throw new Error("message is required");
      }
      const res = await fetch("/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, message }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        throw new Error(data.error || "send failed");
      }
      return data;
    };
    const setCameraModeBusy = (busy, hint = "", isError = false) => {
      cameraModeBusy = !!busy;
      syncCameraModeBusyState();
      if (hint && isError) {
        setCameraModeHint(hint, isError);
      }
    };
    const closeCameraMode = () => {
      if (!cameraMode || cameraMode.hidden) return;
      cancelCameraModeMicRecognition();
      stopCameraModeStream();
      cameraMode.hidden = true;
      cameraMode.classList.remove("visible", "busy");
      document.body.classList.remove("camera-mode-open");
      cameraModeBackdropFrosted = false;
      syncCameraModeBackdrop();
      setCameraModeHint("");
      setCameraModeFallbackState(false);
      cameraModeBusy = false;
      cameraModeMicListening = false;
      cameraModeOpening = false;
      setCameraModeTargetsExpanded(false);
      restoreTimelineFromCameraMode();
      renderCameraModeReplies();
      renderCameraModeThinking();
      syncCameraModeBusyState();
      updateScrollBtn();
    };
    const startCameraModeStream = async () => {
      stopCameraModeStream();
      setCameraModeFallbackState(false);
      if (!window.isSecureContext) {
        return fallbackToCameraModeChat("HTTPS is required for camera.", true);
      }
      if (isCameraBlockedByPolicy()) {
        return fallbackToCameraModeChat("Camera is blocked by the parent page.", true);
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        return fallbackToCameraModeChat("Live camera is unavailable here.", true);
      }
      try {
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
        });
        cameraModeStream = stream;
        const track = stream.getVideoTracks()[0] || null;
        if (track) {
          track.onended = () => {
            if (cameraMode?.hidden) return;
            stopCameraModeStream();
            fallbackToCameraModeChat("Camera ended. Returned to chat.", true);
          };
        }
        if (cameraModeVideo) {
          cameraModeVideo.srcObject = stream;
          cameraModeVideo.muted = true;
          cameraModeVideo.playsInline = true;
          await cameraModeVideo.play().catch(() => { });
        }
        setCameraModeHint("");
        return true;
      } catch (err) {
        const name = String(err?.name || "");
        let message = "Live camera unavailable.";
        if (!window.isSecureContext) {
          message = "HTTPS is required for camera.";
        } else if (isCameraBlockedByPolicy()) {
          message = "Camera is blocked by the parent page.";
        } else if (name === "NotAllowedError") {
          message = "Camera access denied. Check browser settings.";
        } else if (name === "NotFoundError") {
          message = "No camera found on this device.";
        } else if (name === "NotReadableError") {
          message = "Camera is busy in another app.";
        }
        return fallbackToCameraModeChat(message, true);
      }
    };
    const flashCameraModeSendEffect = () => {
      if (!cameraMode) return;
      const el = document.createElement("div");
      el.className = "camera-mode-send-border";
      cameraMode.appendChild(el);
      el.addEventListener("animationend", () => el.remove(), { once: true });
    };
    const runCameraModeSend = async (sourceBlob) => {
      const target = syncCameraModeTarget();
      if (!target) {
        setCameraModeHint("No available agent target.", true);
        return false;
      }
      if (!sourceBlob) {
        setCameraModeHint("No image captured.", true);
        return false;
      }
      try {
        setCameraModeHint("");
        setCameraModeBusy(true);
        const prepared = await resizeCameraModeBlob(sourceBlob, { maxSide: 1280, quality: 0.7 });
        const filename = `camera_${Date.now()}.jpg`;
        const uploadedPath = await uploadCameraModeBlob(prepared, filename);
        await sendCameraModeAttachment(uploadedPath, target);
        await refresh({ forceScroll: true });
        setCameraModeBusy(false);
        flashCameraModeSendEffect();
        return true;
      } catch (err) {
        setCameraModeBusy(false, err?.message || "camera send failed", true);
        return false;
      }
    };
    const captureAndSendCameraMode = async () => {
      if (cameraModeBusy) return;
      if (cameraModeStream && cameraModeVideo && Number(cameraModeVideo.videoWidth || 0) > 0) {
        try {
          const blob = await captureCameraModeFrameBlob({ maxSide: 1280, quality: 0.7 });
          await runCameraModeSend(blob);
          return;
        } catch (err) {
          fallbackToCameraModeChat(err?.message || "camera capture failed", true);
          return;
        }
      }
      fallbackToCameraModeChat("Live camera is unavailable. Returned to chat.", true);
    };
    const openCameraMode = async () => {
      if (!cameraMode || cameraModeOpening) return;
      if (!sessionActive) {
        setStatus("archived session is read-only", true);
        setTimeout(() => setStatus(""), 2200);
        return;
      }
      if (!cameraModeAllowedTargets().length) {
        setStatus("no available camera target", true);
        setTimeout(() => setStatus(""), 2200);
        return;
      }
      cameraModeOpening = true;
      closeFileModal({ restoreFocus: false });
      closeQuickMore();
      if (isComposerOverlayOpen()) {
        try { messageInput?.blur?.(); } catch (_) { }
        closeComposerOverlay();
      }
      cameraModeBackdropFrosted = false;
      syncCameraModeBackdrop();
      cameraMode.hidden = false;
      cameraMode.classList.add("visible");
      document.body.classList.add("camera-mode-open");
      setCameraModeTargetsExpanded(false);
      mountTimelineIntoCameraMode();
      syncCameraModeReplies();
      renderCameraModeThinking();
      setCameraModeHint("");
      setCameraModeFallbackState(false);
      renderCameraModeTargets();
      syncCameraModeBusyState();
      updateScrollBtn();
      await startCameraModeStream();
      cameraModeOpening = false;
    };
    cameraModeCloseBtn?.addEventListener("click", () => {
      if (cameraModeBusy) return;
      closeCameraMode();
    });
    cameraModeTargetToggleBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (cameraModeBusy) return;
      setCameraModeTargetsExpanded(!cameraModeTargetsExpanded);
      renderCameraModeTargets();
    });
    cameraModeShutterBtn?.addEventListener("click", () => {
      setCameraModeTargetsExpanded(false);
      void captureAndSendCameraMode();
    });
    cameraModeBackdropBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (!cameraMode || cameraMode.hidden) return;
      cameraModeBackdropFrosted = !cameraModeBackdropFrosted;
      syncCameraModeBackdrop();
    });
    cameraModeShell?.addEventListener("click", (event) => {
      if (!cameraModeTargetsExpanded) return;
      if (event.target.closest(".camera-mode-thinking-shell")) return;
      setCameraModeTargetsExpanded(false);
      renderCameraModeTargets();
      renderCameraModeThinking();
    });
    window.addEventListener("resize", () => {
      if (hasOpenHeaderMenu()) updateHeaderMenuViewportMetrics();
      if (attachedFilesPanel && !attachedFilesPanel.hidden && typeof attachedFilesPanel._syncCategoryUi === "function") {
        attachedFilesPanel._syncCategoryUi("auto");
      }
      syncCameraModeMessageLayout();
    });
    window.addEventListener("scroll", () => {
      if (hasOpenHeaderMenu()) updateHeaderMenuViewportMetrics();
    }, { passive: true });
    document.addEventListener("click", (event) => {
      if (quickMore && quickMore.open && !quickMore.contains(event.target)) {
        quickMore.open = false;
      }
      if (composerPlusMenu && composerPlusMenu.open && !composerPlusMenu.contains(event.target) && !event.target.closest(".target-chip")) {
        closePlusMenu();
      }
      const inRightMenu = rightMenuBtn?.contains(event.target) || rightMenuPanel?.contains(event.target);
      const inGitBranchMenu = gitBranchPanel?.contains(event.target);
      const inFilesMenu = attachedFilesPanel?.contains(event.target);
      const inPaneTraceMenu = paneTracePanel?.contains(event.target);
      const inNativeBridgeMenu = nativeHeaderMenuBridge?.contains(event.target);
      const inNativeHeaderMenu = nativeHeaderMenuSelect?.contains(event.target);
      const agentActionNativeMenu = document.getElementById("agentActionNativeMenuSelect");
      const inAgentActionMenu = agentActionNativeMenu?.contains(event.target);
      if (!inRightMenu && !inGitBranchMenu && !inFilesMenu && !inPaneTraceMenu && !inNativeBridgeMenu && !inNativeHeaderMenu && !inAgentActionMenu) {
        closeHeaderMenus();
      }
    });
    async function runForwardAction(target, { sourceNode = null, keepComposerOpen = false, keepHeaderOpen = false } = {}) {
      const action = String(target || "");
      if (!action) return;
      if (keepComposerOpen) flashComposerAction(action);
      if (action === "save" || action === "interrupt" || action === "restart" || action === "resume" || action === "ctrlc" || action === "enter") {
        if (!keepComposerOpen) closeQuickMore();
        await submitMessage({ overrideMessage: action });
        if (keepComposerOpen && composerPlusMenu) {
          requestAnimationFrame(() => { composerPlusMenu.open = true; });
        }
        return;
      }
      if (action === "reloadChat") {
        if (reloadInFlight) return;
        reloadInFlight = true;
        armLaunchShellGate(15000);
        const btn = sourceNode;
        if (btn) {
          btn.disabled = true;
          btn.classList.add("restarting");
          btn.textContent = "Restarting…";
        }
        const previousInstance = currentServerInstance;
        let edgeReady = false;
        await Promise.allSettled([purgeChatAssetCaches(), refreshChatServiceWorkers()]);
        try {
          const res = await fetch("/new-chat", { method: "POST", cache: "no-store" });
          edgeReady = res.ok && res.headers.get("X-Multiagent-Chat-Ready") === "1";
        } catch (_) { }
        const ready = edgeReady || await waitForChatReady(12000, previousInstance);
        await Promise.allSettled([purgeChatAssetCaches(), refreshChatServiceWorkers()]);
        if (!ready) {
          navigateToFreshChat();
          return;
        }
        navigateToFreshChat();
        return;
      }
      if (action === "openGitBranchMenu") {
        openGitBranchSheet();
        return;
      }
      if (action === "openAttachedFilesMenu") {
        openAttachedFilesSheet();
        return;
      }
      if (action === "openCameraMode") {
        await openCameraMode();
        return;
      }
      if (action === "openPaneTraceWindow") {
        closeQuickMore();
        togglePaneViewer();
        return;
      }
      if (action === "addAgent") {
        closeQuickMore();
        if (!sessionActive) {
          setStatus("archived session is read-only", true);
          setTimeout(() => setStatus(""), 2000);
          return;
        }
        showAddAgentModal();
        return;
      }
      if (action === "removeAgent") {
        closeQuickMore();
        if (!sessionActive) {
          setStatus("archived session is read-only", true);
          setTimeout(() => setStatus(""), 2000);
          return;
        }
        showRemoveAgentModal();
        return;
      }
      if (action === "syncStatus") {
        closeQuickMore();
        closeHeaderMenus();
        requestAnimationFrame(() => {
          void showSyncStatusPanel();
        });
        return;
      }
      document.getElementById(action)?.click();
      if (keepComposerOpen && composerPlusMenu) {
        requestAnimationFrame(() => { composerPlusMenu.open = true; });
      }
      if (keepHeaderOpen && rightMenuPanel && rightMenuBtn) {
        requestAnimationFrame(() => {
          rightMenuPanel.hidden = false;
          rightMenuPanel.classList.add("open");
          rightMenuBtn.classList.add("open");
        });
      }
    }
    document.querySelectorAll("[data-forward-action]").forEach((node) => {
      node.addEventListener("mousedown", (e) => e.preventDefault());
      node.addEventListener("click", async () => {
        const target = node.dataset.forwardAction || "";
        const keepComposerOpen = !!(composerPlusMenu && composerPlusMenu.contains(node));
        const keepHeaderOpen = !!(rightMenuPanel && rightMenuPanel.contains(node));
        await runForwardAction(target, { sourceNode: node, keepComposerOpen, keepHeaderOpen });
      });
    });
    document.querySelectorAll(".quick-action:not(.quick-more-toggle):not(.plus-submenu-toggle):not([data-forward-action]):not(#cameraBtn)").forEach((node) => {
      node.addEventListener("click", async () => {
        closeQuickMore();
        await submitMessage({ overrideMessage: node.dataset.shortcut || "" });
      });
    });
    let composing = false;
    const messageInput = document.getElementById("message");
    const sendBtn = document.querySelector(".send-btn");
    const micBtn = document.getElementById("micBtn");
    document.getElementById("pendingLaunchBtn")?.addEventListener("click", async () => {
      if (!sessionLaunchPending || sessionActive) return;
      const launchTargets = selectedTargets.filter((target) => availableTargets.includes(target));
      if (launchTargets.length !== 1) {
        setStatus("select exactly one initial agent", true);
        syncPendingLaunchControls();
        return;
      }
      const selectedAgent = launchTargets[0];
      const pendingLaunchBtn = document.getElementById("pendingLaunchBtn");
      if (pendingLaunchBtn) pendingLaunchBtn.disabled = true;
      setStatus(`starting ${selectedAgent}...`);
      try {
        const res = await fetch("/launch-session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agent: selectedAgent }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "failed to start session");
        }
        await refreshSessionState();
        setStatus(`${selectedAgent} is ready`);
        setTimeout(() => setStatus(""), 1800);
        if (sessionActive) {
          openComposerOverlay({ immediateFocus: true });
        }
      } catch (error) {
        setStatus(error?.message || "failed to start session", true);
      } finally {
        syncPendingLaunchControls();
      }
    });
    let _fileImportInProgress = false;
    let _fileImportClearTimer = null;
    const scheduleComposerCloseFromKeyboardDismiss = () => {
      if (_fileImportInProgress) return;
      clearComposerBlurCloseTimer();
      composerBlurCloseTimer = setTimeout(() => {
        if (!isComposerOverlayOpen()) return;
        if (_fileImportInProgress) return;
        const active = document.activeElement;
        if (active === messageInput) return;
        if (composerForm && active && composerForm.contains(active)) return;
        closeComposerOverlay();
      }, 140);
    };
    messageInput?.addEventListener("focus", () => {
      clearComposerBlurCloseTimer();
    });
    messageInput?.addEventListener("blur", () => {
      scheduleComposerCloseFromKeyboardDismiss();
    });

    // Web Speech API setup
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const checkMicrophonePermission = (onDenied) => {
        if (!(navigator.permissions && navigator.permissions.query)) return;
        navigator.permissions.query({ name: "microphone" }).then((result) => {
          if (result.state === "denied") onDenied();
        }).catch(() => { });
      };

      if (micBtn) {
        const recognition = new SpeechRecognition();
        recognition.lang = "ja-JP";
        recognition.continuous = false;
        recognition.interimResults = true;
        let isListening = false;
        let finalTranscript = "";

        const toggleRecognition = () => {
          if (isListening) {
            recognition.stop();
            return;
          }
          finalTranscript = messageInput.value;
          checkMicrophonePermission(() => {
            setStatus("マイクがブロックされています。アドレスバー左のアイコン → サイトの設定 → マイクを「許可」に変更してください");
            setTimeout(() => setStatus(""), 8000);
          });
          try {
            recognition.start();
          } catch (err) {
            console.error("[mic] recognition.start() threw:", err);
            setStatus("音声認識の開始に失敗: " + err.message);
            setTimeout(() => setStatus(""), 5000);
          }
        };
        micBtn.addEventListener("click", toggleRecognition);
        micBtn.addEventListener("touchend", (e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleRecognition();
        }, { passive: false });

        recognition.onstart = () => {
          isListening = true;
          micBtn.classList.add("listening");
        };
        recognition.onresult = (event) => {
          let interim = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
              finalTranscript += event.results[i][0].transcript;
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          messageInput.value = finalTranscript + interim;
          updateSendBtnVisibility();
          messageInput.dispatchEvent(new Event("input"));
        };
        recognition.onend = () => {
          isListening = false;
          micBtn.classList.remove("listening");
          messageInput.value = finalTranscript;
          updateSendBtnVisibility();
          if (finalTranscript.trim()) {
            setTimeout(() => submitMessage(), 100);
          }
        };
        recognition.onerror = (e) => {
          console.error("[mic] recognition error:", e.error, e);
          isListening = false;
          micBtn.classList.remove("listening");
          if (e.error === "not-allowed") {
            setStatus("マイクのアクセスが拒否されています。設定 > プライバシー > マイクで許可してください。");
          } else if (e.error === "service-not-allowed") {
            setStatus("このモード（ホーム画面アプリ）では音声認識が使えません。Safariで開いてください。");
          } else if (e.error === "network") {
            setStatus("音声認識サービスに接続できません（ネットワークエラー）");
          } else if (e.error === "aborted") {
            setStatus("音声認識が中断されました");
          } else {
            setStatus("音声認識エラー: " + (e.error || "unknown"));
          }
          setTimeout(() => setStatus(""), 5000);
        };
      }

      if (cameraModeMicBtn) {
        const cameraRecognition = new SpeechRecognition();
        cameraRecognition.lang = "ja-JP";
        cameraRecognition.continuous = false;
        cameraRecognition.interimResults = true;
        let isListening = false;
        let suppressCommit = false;
        let finalTranscript = "";
        let audioVisualizerCtx = null;
        let audioVisualizerSource = null;
        let audioVisualizerStream = null;
        let audioVisualizerAnalyser = null;
        let audioVisualizerRafId = 0;
        let audioVisualizerLiveFrames = 0;

        const waveformEl = () => cameraModeHint?.querySelector(".camera-waveform");
        const waveformBars = () => Array.from(cameraModeHint?.querySelectorAll(".camera-waveform-bar") || []);
        const resetAudioVisualizerBars = () => {
          waveformEl()?.classList.remove("is-live");
          waveformBars().forEach((bar) => {
            bar.style.removeProperty("--camera-wave-scale");
            bar.style.removeProperty("--camera-wave-opacity");
          });
        };

        const ensureAudioVisualizerContext = async () => {
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          if (!AudioContext) return null;
          if (!audioVisualizerCtx || audioVisualizerCtx.state === "closed") {
            audioVisualizerCtx = new AudioContext();
          }
          if (audioVisualizerCtx.state === "suspended") {
            await audioVisualizerCtx.resume();
          }
          return audioVisualizerCtx;
        };

        const stopAudioVisualizer = () => {
          if (audioVisualizerRafId) cancelAnimationFrame(audioVisualizerRafId);
          audioVisualizerRafId = 0;
          audioVisualizerLiveFrames = 0;
          if (audioVisualizerSource) {
            try { audioVisualizerSource.disconnect(); } catch (_) { }
            audioVisualizerSource = null;
          }
          if (audioVisualizerAnalyser) {
            try { audioVisualizerAnalyser.disconnect(); } catch (_) { }
          }
          if (audioVisualizerStream) {
            audioVisualizerStream.getTracks().forEach(t => t.stop());
            audioVisualizerStream = null;
          }
          audioVisualizerAnalyser = null;
          resetAudioVisualizerBars();
        };

        const startAudioVisualizer = async () => {
          try {
            if (audioVisualizerStream) stopAudioVisualizer();

            // Best-effort only. If a second mic consumer is not allowed on this
            // browser, keep the CSS fallback waveform running instead.
            audioVisualizerStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const ctx = await ensureAudioVisualizerContext();
            if (!ctx) return;

            const src = ctx.createMediaStreamSource(audioVisualizerStream);
            audioVisualizerSource = src;
            audioVisualizerAnalyser = ctx.createAnalyser();
            audioVisualizerAnalyser.fftSize = 32;
            audioVisualizerAnalyser.smoothingTimeConstant = 0.72;
            src.connect(audioVisualizerAnalyser);

            const dataArray = new Uint8Array(audioVisualizerAnalyser.frequencyBinCount);
            const bars = waveformBars();
            const wave = waveformEl();

            const renderWaveform = () => {
              if (!audioVisualizerAnalyser) return;
              audioVisualizerRafId = requestAnimationFrame(renderWaveform);
              audioVisualizerAnalyser.getByteFrequencyData(dataArray);

              let energy = 0;
              for (let i = 0; i < dataArray.length; i++) energy += dataArray[i];
              energy = energy / (dataArray.length * 255);
              if (energy > 0.018) {
                audioVisualizerLiveFrames = Math.min(audioVisualizerLiveFrames + 1, 4);
              } else {
                audioVisualizerLiveFrames = Math.max(audioVisualizerLiveFrames - 1, 0);
              }
              wave?.classList.toggle("is-live", audioVisualizerLiveFrames >= 2);
              if (audioVisualizerLiveFrames < 2) return;

              bars.forEach((bar, i) => {
                const val = dataArray[i % dataArray.length] / 255.0;
                const scale = 0.2 + (val * 1.5);
                const opacity = 0.3 + (val * 0.7);
                bar.style.setProperty("--camera-wave-scale", scale.toFixed(2));
                bar.style.setProperty("--camera-wave-opacity", opacity.toFixed(2));
              });
            };
            renderWaveform();
          } catch (err) {
            console.warn("[mic] could not start audio visualizer:", err);
            resetAudioVisualizerBars();
          }
        };

        const clearCameraMicUi = () => {
          isListening = false;
          cameraModeMicListening = false;
          cameraModeMicBtn.classList.remove("listening");
          stopAudioVisualizer();
          syncCameraModeBusyState();
          setCameraModeHint("");
        };
        cancelCameraModeMicRecognition = () => {
          suppressCommit = true;
          finalTranscript = "";
          clearCameraMicUi();
          if (!cameraModeBusy) setCameraModeHint("");
          if (!isListening) return;
          try {
            cameraRecognition.abort();
          } catch (_) {
            try { cameraRecognition.stop(); } catch (_) { }
          }
        };
        const toggleCameraRecognition = async () => {
          if (isListening) {
            suppressCommit = false;
            cameraRecognition.stop();
            return;
          }
          if (cameraModeBusy || !cameraMode || cameraMode.hidden) return;
          const target = syncCameraModeTarget();
          if (!target) {
            setCameraModeHint("No available agent target.", true);
            return;
          }
          finalTranscript = "";
          suppressCommit = false;
          checkMicrophonePermission(() => {
            setCameraModeHint("Microphone access is blocked.", true);
          });
          try {
            await ensureAudioVisualizerContext().catch(() => { });
            cameraRecognition.start();
          } catch (err) {
            setCameraModeHint("Voice input failed to start.", true);
          }
        };
        cameraModeMicBtn.addEventListener("click", () => {
          void toggleCameraRecognition();
        });
        cameraModeMicBtn.addEventListener("touchend", (e) => {
          e.preventDefault();
          e.stopPropagation();
          void toggleCameraRecognition();
        }, { passive: false });
        cameraRecognition.onstart = () => {
          isListening = true;
          cameraModeMicListening = true;
          cameraModeMicBtn.classList.add("listening");
          syncCameraModeBusyState();
          setCameraModeHint("Listening...", false, true);
          void startAudioVisualizer();
        };
        cameraRecognition.onresult = (event) => {
          let interim = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
              finalTranscript += event.results[i][0].transcript;
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          const preview = `${finalTranscript}${interim}`.trim();
          setCameraModeHint(preview || "Listening...", false, true);
        };
        cameraRecognition.onend = () => {
          isListening = false;
          clearCameraMicUi();
          if (suppressCommit) {
            suppressCommit = false;
            finalTranscript = "";
            if (!cameraModeBusy) setCameraModeHint("");
            return;
          }
          const transcript = String(finalTranscript || "").trim();
          finalTranscript = "";
          if (!transcript) {
            if (!cameraModeBusy) setCameraModeHint("");
            return;
          }
          void (async () => {
            const target = syncCameraModeTarget();
            if (!target) {
              setCameraModeHint("No available agent target.", true);
              return;
            }
            try {
              setCameraModeBusy(true);
              await sendCameraModeText(transcript, target);
              await refresh({ forceScroll: true });
              setCameraModeBusy(false);
              setCameraModeHint("");
            } catch (err) {
              setCameraModeBusy(false, err?.message || "voice send failed", true);
            }
          })();
        };
        cameraRecognition.onerror = (e) => {
          console.error("[camera-mic] recognition error:", e.error, e);
          isListening = false;
          clearCameraMicUi();
          if (suppressCommit || e.error === "aborted") {
            suppressCommit = false;
            if (!cameraModeBusy) setCameraModeHint("");
            return;
          }
          if (e.error === "not-allowed") {
            setCameraModeHint("Microphone access denied.", true);
          } else if (e.error === "service-not-allowed") {
            setCameraModeHint("Voice input is unavailable here.", true);
          } else if (e.error === "network") {
            setCameraModeHint("Speech recognition network error.", true);
          } else if (e.error === "no-speech") {
            setCameraModeHint("No speech detected.", true);
          } else {
            setCameraModeHint("Voice input error.", true);
          }
          setTimeout(() => {
            if (!cameraModeMicListening && !cameraModeBusy) setCameraModeHint("");
          }, 3200);
        };
      }
    } else {
      if (micBtn) micBtn.classList.add("no-speech");
      if (cameraModeMicBtn) cameraModeMicBtn.classList.add("no-speech");
    }

    // Import / file attach
    const cameraBtn = document.getElementById("cameraBtn");
    const cameraInput = document.getElementById("cameraInput");
    const attachPreviewRow = document.getElementById("attachPreviewRow");
    const composerShellEl = document.querySelector(".composer-shell");
    if (cameraBtn && cameraInput && attachPreviewRow) {
      const attachmentBaseName = (value) => {
        const parts = String(value || "").split(/[\\/]/);
        return parts[parts.length - 1] || String(value || "");
      };
      const attachmentExt = (value) => {
        const base = attachmentBaseName(value);
        const dot = base.lastIndexOf(".");
        return dot > 0 ? base.slice(dot) : "";
      };
      const attachmentStem = (value) => {
        const base = attachmentBaseName(value);
        const dot = base.lastIndexOf(".");
        return dot > 0 ? base.slice(0, dot) : base;
      };
      const attachmentDisplayNameFromPath = (path, fallback = "") => {
        const base = attachmentBaseName(path);
        const ext = attachmentExt(base);
        const stem = ext ? base.slice(0, -ext.length) : base;
        const parts = stem.split("_");
        if (parts.length >= 3) {
          const label = parts.slice(2).join("_");
          if (label) return `${label}${ext}`;
        }
        return fallback || base;
      };
      const syncAttachmentCard = (card, attachment) => {
        if (!card || !attachment) return;
        card.dataset.path = attachment.path || "";
        card.setAttribute("aria-label", attachment.name ? `Rename attachment ${attachment.name}` : "Rename attachment");
        card.title = attachment.name ? `Rename ${attachment.name}` : "Rename attachment";
        const nameEl = card.querySelector(".attach-card-name");
        if (nameEl) {
          nameEl.textContent = attachment.name || attachmentDisplayNameFromPath(attachment.path, "Attachment");
        }
        const img = card.querySelector(".attach-card-thumb");
        if (img && attachment.name) img.alt = attachment.name;
      };
      const openAttachmentRenameModal = (attachment, card) => {
        if (!attachment || !pendingAttachments.includes(attachment)) return;
        let overlay = document.getElementById("attachRenameOverlay");
        if (overlay) overlay.remove();
        overlay = document.createElement("div");
        overlay.id = "attachRenameOverlay";
        overlay.className = "add-agent-overlay attach-rename-overlay";
        const currentName = attachment.name || attachmentDisplayNameFromPath(attachment.path, "attachment");
        const ext = attachmentExt(currentName) || attachmentExt(attachment.path);
        const initialLabel = (attachment.label || attachmentStem(currentName)).trim();
        const hint = ext ? `The ${escapeHtml(ext)} extension stays unchanged.` : "The file extension stays unchanged.";
        overlay.innerHTML = `<div class="add-agent-panel attach-rename-panel"><h3>Rename Attachment</h3><p class="attach-rename-copy">${escapeHtml(currentName)}</p><label class="attach-rename-label" for="attachRenameInput">Name</label><input id="attachRenameInput" class="attach-rename-input" type="text" placeholder="attachment name" maxlength="80" autocapitalize="off" autocorrect="off" spellcheck="false"><p class="attach-rename-hint">${hint}</p><div class="attach-rename-error" aria-live="polite"></div><div class="add-agent-actions"><button type="button" class="add-agent-cancel">Cancel</button><button type="button" class="add-agent-confirm">Rename</button></div></div>`;
        document.body.appendChild(overlay);
        requestAnimationFrame(() => overlay.classList.add("visible"));
        const input = overlay.querySelector("#attachRenameInput");
        input.value = initialLabel;
        const errorEl = overlay.querySelector(".attach-rename-error");
        const cancelBtn = overlay.querySelector(".add-agent-cancel");
        const confirmBtn = overlay.querySelector(".add-agent-confirm");
        const closeModal = ({ restoreFocus = true } = {}) => {
          overlay.classList.remove("visible");
          setTimeout(() => overlay.remove(), 420);
          if (restoreFocus) {
            try { card?.focus?.(); } catch (_) { }
          }
        };
        const syncConfirmState = () => {
          confirmBtn.disabled = !input.value.trim();
        };
        overlay.addEventListener("click", (e) => {
          if (e.target === overlay) closeModal();
        });
        cancelBtn.addEventListener("click", () => closeModal());
        input.addEventListener("input", () => {
          errorEl.textContent = "";
          syncConfirmState();
        });
        input.addEventListener("keydown", async (e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            closeModal();
            return;
          }
          if (e.key === "Enter" && !confirmBtn.disabled) {
            e.preventDefault();
            confirmBtn.click();
          }
        });
        confirmBtn.addEventListener("click", async () => {
          const label = input.value.trim();
          if (!label) {
            syncConfirmState();
            return;
          }
          if (!pendingAttachments.includes(attachment)) {
            closeModal({ restoreFocus: false });
            return;
          }
          confirmBtn.disabled = true;
          cancelBtn.disabled = true;
          errorEl.textContent = "";
          try {
            const res = await fetch("/rename-upload", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: attachment.path, label }),
            });
            const data = await res.json();
            if (!res.ok || !data.ok || !data.path) {
              throw new Error(data.error || "rename failed");
            }
            const nextName = attachmentDisplayNameFromPath(data.path, `${label}${ext}`);
            attachment.path = data.path;
            attachment.name = nextName;
            attachment.label = attachmentStem(nextName);
            syncAttachmentCard(card, attachment);
            setStatus("");
            closeModal();
          } catch (err) {
            errorEl.textContent = err?.message || "rename failed";
            confirmBtn.disabled = false;
            cancelBtn.disabled = false;
          }
        });
        syncConfirmState();
        setTimeout(() => {
          try {
            input.focus();
            input.select();
          } catch (_) { }
        }, 40);
      };
      const addCard = (file, attachment) => {
        const card = document.createElement("div");
        card.className = "attach-card";
        card.tabIndex = 0;
        card.setAttribute("role", "button");
        if (file.type.startsWith("image/")) {
          const img = document.createElement("img");
          img.className = "attach-card-thumb";
          img.src = URL.createObjectURL(file);
          img.alt = file.name;
          card.appendChild(img);
        } else {
          const ext = document.createElement("div");
          ext.className = "attach-card-ext";
          ext.textContent = file.name.split(".").pop().slice(0, 5) || "FILE";
          card.appendChild(ext);
        }
        const nameEl = document.createElement("div");
        nameEl.className = "attach-card-name";
        nameEl.textContent = attachment.name || file.name;
        card.appendChild(nameEl);
        const rmBtn = document.createElement("button");
        rmBtn.type = "button";
        rmBtn.className = "attach-card-remove";
        rmBtn.setAttribute("aria-label", "Remove");
        rmBtn.textContent = "\u2715";
        rmBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          pendingAttachments = pendingAttachments.filter((a) => a !== attachment);
          card.remove();
          if (!attachPreviewRow.children.length) attachPreviewRow.style.display = "none";
          if (attachment.path) {
            fetch("/delete-upload", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: attachment.path }),
            }).catch(() => {});
          }
        });
        card.appendChild(rmBtn);
        card.addEventListener("click", () => openAttachmentRenameModal(attachment, card));
        card.addEventListener("keydown", (e) => {
          if (e.key !== "Enter" && e.key !== " ") return;
          e.preventDefault();
          openAttachmentRenameModal(attachment, card);
        });
        syncAttachmentCard(card, attachment);
        attachPreviewRow.appendChild(card);
        attachPreviewRow.style.display = "flex";
      };
      const uploadAttachedFiles = async (fileList) => {
        const files = Array.from(fileList || []).filter((f) => f && typeof f.name === "string");
        if (!files.length) return false;
        /* iOS: 最初の await 前にフォーカス（非同期続きではキーボードが出にくい）。 */
        if (messageInput && isComposerOverlayOpen()) {
          focusComposerTextarea({ sync: true });
        }
        setStatus(files.length > 1 ? `uploading ${files.length} files...` : `uploading ${files[0].name}...`);
        try {
          await Promise.all(files.map(async (file) => {
            const res = await fetch("/upload", {
              method: "POST",
              headers: {
                "Content-Type": file.type || "application/octet-stream",
                "X-Filename": encodeURIComponent(file.name || "upload.bin"),
              },
              body: file,
            });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.error || "upload failed");
            const attachment = { path: data.path, name: file.name, label: "" };
            pendingAttachments.push(attachment);
            addCard(file, attachment);
          }));
          setStatus("");
          return true;
        } catch (err) {
          setStatus("upload failed: " + err.message, true);
          setTimeout(() => setStatus(""), 3000);
          return false;
        }
      };
      const dtHasFiles = (dt) => dt && [...dt.types].includes("Files");
      const isOnFileInputDrop = (t) => !!(t && t.closest && t.closest("input[type=file]"));
      const maybeOpenComposerForAttachDrag = () => {
        if (!isComposerOverlayOpen()) openComposerOverlay({ immediateFocus: false });
      };
      cameraBtn.addEventListener("click", () => {
        closePlusMenu();
        _fileImportInProgress = true;
        if (_fileImportClearTimer) clearTimeout(_fileImportClearTimer);
        _fileImportClearTimer = setTimeout(() => {
          _fileImportInProgress = false;
          _fileImportClearTimer = null;
        }, 20000);
        cameraInput.click();
      });
      cameraInput.addEventListener("change", async () => {
        _fileImportInProgress = false;
        if (_fileImportClearTimer) {
          clearTimeout(_fileImportClearTimer);
          _fileImportClearTimer = null;
        }
        const files = Array.from(cameraInput.files);
        cameraInput.value = "";
        await uploadAttachedFiles(files);
      });
      document.addEventListener("dragenter", (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        maybeOpenComposerForAttachDrag();
        composerOverlay?.classList.add("composer-attach-drag");
      }, true);
      document.addEventListener("dragover", (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }, true);
      document.addEventListener("dragleave", (e) => {
        if (!composerOverlay?.classList.contains("composer-attach-drag")) return;
        if (!dtHasFiles(e.dataTransfer)) return;
        const related = e.relatedTarget;
        if (!related || !document.documentElement.contains(related)) {
          composerOverlay.classList.remove("composer-attach-drag");
        }
      }, true);
      document.addEventListener("dragend", () => {
        composerOverlay?.classList.remove("composer-attach-drag");
      }, true);
      document.addEventListener("drop", async (e) => {
        if (!dtHasFiles(e.dataTransfer) || isOnFileInputDrop(e.target)) return;
        e.preventDefault();
        e.stopPropagation();
        composerOverlay?.classList.remove("composer-attach-drag");
        maybeOpenComposerForAttachDrag();
        await uploadAttachedFiles(e.dataTransfer.files);
      }, true);
    }

    const updateSendBtnVisibility = () => {
      if (sessionLaunchPending || !sessionActive) {
        if (sendBtn) sendBtn.classList.remove("visible");
        if (micBtn) micBtn.classList.remove("hidden");
        return;
      }
      const hasText = messageInput.value.trim().length > 0;
      if (sendBtn) sendBtn.classList.toggle("visible", hasText);
      if (micBtn) micBtn.classList.toggle("hidden", hasText);
    };
    messageInput.addEventListener("input", updateSendBtnVisibility);

    let _thinkingRowTouch = null;
    let _lastThinkingPaneMs = 0;
    document.documentElement.dataset.mobile = "1";

    /* ── Mobile: keep main::after height synced so iframe prewarm does not collapse bottom spacer ── */
    syncMainAfterHeight();
    window.addEventListener("resize", syncMainAfterHeight, { passive: true });

    /* ── Mobile viewport sync: do not move the overlay for the keyboard ── */
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

    messageInput.addEventListener("compositionstart", () => {
      composing = true;
    });
    messageInput.addEventListener("compositionend", () => {
      composing = false;
      setTimeout(updateFileAutocomplete, 10);
    });
    // @-file autocomplete
    let _fileList = null;
    let _fileListPromise = null;
    let _fileAutocompleteRequestSeq = 0;
    let _inlineFileLinkWarmupStarted = false;
    let _inlineFileLinkReplayQueued = false;
    let _inlineFileLinkStaleRelinkTimer = null;
    const _inlineFileLinkResolutionCache = new Map();
    const normalizeFileEntry = (entry) => {
      if (!entry) return null;
      if (typeof entry === "string") return { path: entry, size: null };
      const path = typeof entry.path === "string" ? entry.path : "";
      if (!path) return null;
      let size = null;
      if (Object.prototype.hasOwnProperty.call(entry, "size")) {
        const rawSize = entry.size;
        if (rawSize !== null && rawSize !== undefined && rawSize !== "") {
          const parsedSize = Number(rawSize);
          if (Number.isFinite(parsedSize) && parsedSize >= 0) {
            size = parsedSize;
          }
        }
      }
      return { path, size };
    };
    const loadFiles = async ({ refreshServer = false } = {}) => {
      if (!refreshServer) {
        if (_fileList) return _fileList;
        if (_fileListPromise) return _fileListPromise;
      }
      _fileListPromise = (async () => {
        try {
          const q = refreshServer ? "?refresh=1" : "";
          const r = await fetch(`${CHAT_BASE_PATH || ""}/files${q}`);
          const raw = r.ok ? await r.json() : [];
          _fileList = (Array.isArray(raw) ? raw : [])
            .map(normalizeFileEntry)
            .filter(Boolean);
        } catch (_) {
          _fileList = [];
        }
        _inlineFileLinkResolutionCache.clear();
        _fileExistenceCache.clear();
        return _fileList;
      })().finally(() => {
        _fileListPromise = null;
      });
      return _fileListPromise;
    };
    const forceRefreshFileListForLinkify = async () => {
      try {
        if (_fileListPromise) await _fileListPromise;
      } catch (_) {}
      _fileList = null;
      _fileListPromise = null;
      _inlineFileLinkResolutionCache.clear();
      return loadFiles({ refreshServer: true });
    };
    const loadFileSearchMatches = async (rawQuery, limit = 30) => {
      const query = String(rawQuery || "").trim();
      const normalizedLimit = Math.max(1, Math.min(120, Number(limit) || 30));
      try {
        const params = new URLSearchParams();
        if (query) params.set("q", query);
        params.set("limit", String(normalizedLimit));
        const response = await fetchWithTimeout(`${CHAT_BASE_PATH || ""}/files-search?${params.toString()}`, {}, 2500);
        if (response.ok) {
          const raw = await response.json();
          return (Array.isArray(raw) ? raw : [])
            .map(normalizeFileEntry)
            .filter(Boolean);
        }
      } catch (_) { }
      const files = await loadFiles();
      return query
        ? findFileMatches(files, query.toLowerCase()).slice(0, normalizedLimit)
        : files.slice(0, normalizedLimit);
    };
    const fileDrop = document.getElementById("fileDropdown");
    let _dropActiveIdx = -1;
    let _ignoreGlobalClick = false;
    let _keepAutocompleteMenuOnBlur = false;
    let _keepAutocompleteMenuBlurTimer = null;
    let _dropTimeout = null;
    const armAutocompleteMenuBlurGuard = () => {
      _keepAutocompleteMenuOnBlur = true;
      if (_keepAutocompleteMenuBlurTimer) clearTimeout(_keepAutocompleteMenuBlurTimer);
      _keepAutocompleteMenuBlurTimer = setTimeout(() => {
        _keepAutocompleteMenuOnBlur = false;
        _keepAutocompleteMenuBlurTimer = null;
      }, 260);
    };
    const _dropItems = () => fileDrop.querySelectorAll(".file-item");
    const closeDrop = () => {
      if (fileDrop.classList.contains("visible")) {
        fileDrop.classList.remove("visible");
        fileDrop.classList.add("closing");
        if (_dropTimeout) clearTimeout(_dropTimeout);
        _dropTimeout = setTimeout(() => {
          if (fileDrop.classList.contains("closing")) {
            fileDrop.style.display = "none";
            fileDrop.classList.remove("closing");
          }
          _dropTimeout = null;
        }, 160);
      } else if (!fileDrop.classList.contains("closing")) {
        fileDrop.style.display = "none";
      }
      _dropActiveIdx = -1;
    };
__CHAT_INCLUDE:../../shared/chat/file-autocomplete.js__
        .catch(() => { })
        .finally(() => {
          _inlineFileLinkWarmupStarted = false;
        });
    };
    const scheduleInlineFileListStaleRelink = (scope) => {
      if (_inlineFileLinkStaleRelinkTimer) clearTimeout(_inlineFileLinkStaleRelinkTimer);
      _inlineFileLinkStaleRelinkTimer = setTimeout(() => {
        _inlineFileLinkStaleRelinkTimer = null;
        void forceRefreshFileListForLinkify().then(() => {
          requestAnimationFrame(() => {
            const root = document.getElementById("messages");
            const target = scope?.isConnected ? scope : (root || document);
            linkifyInlineCodeFileRefs(target);
          });
        });
      }, 120);
    };
    const resolveInlineCodeFilePath = (rawValue) => {
      const parsed = parseInlineCodeFileToken(rawValue);
      if (!parsed) return { path: "", line: 0, needsIndex: false, needsStaleListRetry: false };
      const query = parsed.token;
      const cacheKey = query.toLowerCase();
      if (_inlineFileLinkResolutionCache.has(cacheKey)) {
        return {
          path: _inlineFileLinkResolutionCache.get(cacheKey) || "",
          line: parsed.line,
          needsIndex: false,
          needsStaleListRetry: false,
        };
      }
      const filesReady = Array.isArray(_fileList);
      let resolvedPath = "";
      if (filesReady && _fileList.length) {
        resolvedPath = resolveInlineFilePathFromList(_fileList, query);
      }
      if (resolvedPath) {
        _inlineFileLinkResolutionCache.set(cacheKey, resolvedPath);
        return { path: resolvedPath, line: parsed.line, needsIndex: false, needsStaleListRetry: false };
      }
      if (!filesReady) {
        const directCandidate = query
          .replace(/^\.\/+/, "")
          .replace(/^\/+/, "")
          .replace(/\\/g, "/")
          .trim();
        const isDirectPathLike =
          !!directCandidate
          && !directCandidate.startsWith("../")
          && !directCandidate.startsWith("~/")
          && !directCandidate.includes("//")
          && /^[A-Za-z0-9._/-]+$/.test(directCandidate)
          && (directCandidate.includes("/") || /\.[A-Za-z0-9]{1,10}$/.test(directCandidate));
        if (isDirectPathLike) {
          return { path: directCandidate, line: parsed.line, needsIndex: true, needsStaleListRetry: false };
        }
      }
      const needsIndex = !filesReady && /[\/._-]/.test(query);
      const looksFileLike = /[\/._-]/.test(query) || /\.[A-Za-z0-9]{1,10}$/.test(query);
      const needsStaleListRetry = !!(filesReady && !resolvedPath && looksFileLike);
      return { path: "", line: parsed.line, needsIndex, needsStaleListRetry };
    };
    const linkifyInlineCodeFileRefs = (scope = document) => {
      if (!scope?.querySelectorAll) return false;
      let needsIndexWarmup = false;
      let needsStaleRelink = false;
      scope.querySelectorAll(".md-body code").forEach((codeEl) => {
        if (!codeEl || codeEl.closest("pre") || codeEl.closest(".file-card")) return;
        if (codeEl.closest("a")) return;
        const resolved = resolveInlineCodeFilePath(codeEl.textContent || "");
        if (!resolved.path) {
          if (resolved.needsIndex) needsIndexWarmup = true;
          if (resolved.needsStaleListRetry) needsStaleRelink = true;
          return;
        }
        const path = resolved.path;
        const anchor = document.createElement("a");
        anchor.className = "inline-file-link";
        anchor.href = fileViewHrefForPath(path);
        anchor.dataset.filepath = path;
        anchor.dataset.ext = extFromPath(path);
        if (resolved.line > 0) {
          anchor.dataset.line = String(resolved.line);
        }
        anchor.title = path;
        const codeClone = codeEl.cloneNode(true);
        anchor.appendChild(codeClone);
        codeEl.replaceWith(anchor);
      });
      if (needsIndexWarmup) scheduleInlineFileListWarmup();
      return needsStaleRelink;
    };
    const buildAutocompleteFileItem = (entry) => {
      const path = String(entry?.path || "");
      const ext = fileExtForPath(path);
      const icon = FILE_ICONS[ext] || FILE_SVG_ICONS.file;
      const label = (displayAttachmentFilename(path) || basename(path) || path).trim() || path;
      const relDir = composerAutocompleteRelativeDir(path);
      const row = document.createElement("div");
      row.className = "file-item";
      row.dataset.path = path;
      const pathInner = relDir
        ? `<span class="file-item-name">${escapeHtml(label)}</span><span class="file-item-relpath">${escapeHtml(relDir)}</span>`
        : `<span class="file-item-name">${escapeHtml(label)}</span>`;
      row.innerHTML =
        `<span class="file-item-icon">${icon}</span>` +
        `<span class="file-item-path">${pathInner}</span>` +
        `<span class="file-item-size">${escapeHtml(formatFileSize(entry?.size))}</span>`;
      return row;
    };
    const selectFile = (path) => {
      const ta = messageInput;
      const pos = ta.selectionStart;
      const before = ta.value.slice(0, pos);
      const atIdx = before.lastIndexOf("@");
      if (atIdx === -1) return closeDrop();
      const inlineRef = "`" + path + "`";
      ta.value = ta.value.slice(0, atIdx) + inlineRef + ta.value.slice(pos);
      const newPos = atIdx + inlineRef.length;
      ta.setSelectionRange(newPos, newPos);
      focusMessageInputWithoutScroll(newPos, newPos);
      _ignoreGlobalClick = true;
      closeDrop();
    };
    fileDrop.addEventListener("click", (e) => {
      e.stopPropagation();
    });
    fileDrop.addEventListener("pointerdown", armAutocompleteMenuBlurGuard);
    fileDrop.addEventListener("touchstart", armAutocompleteMenuBlurGuard, { passive: true });
    fileDrop.addEventListener("mousedown", (e) => {
      const item = e.target.closest(".file-item");
      if (item) { e.preventDefault(); selectFile(item.dataset.path); }
    });
    const autoResizeTextarea = () => {
      const baseHeight = 54;
      messageInput.style.marginTop = "0px";
      messageInput.style.height = baseHeight + "px"; // Reset first to measure natural content height
      const scrollH = messageInput.scrollHeight;
      const maxHeight = 200;
      const nextHeight = Math.min(maxHeight, Math.max(baseHeight, scrollH + 2)); // +2px avoids tiny scroll jumps
      messageInput.style.height = nextHeight + "px";
      // Keep bottom edge fixed; grow upward when content exceeds one line.
      messageInput.style.marginTop = (baseHeight - nextHeight) + "px";
      composerShellEl?.style.setProperty("--composer-input-rise", Math.max(0, nextHeight - baseHeight) + "px");
    };
    const positionComposerDropdown = (dropdown) => {
      if (!dropdown) return;
      const taRect = messageInput.getBoundingClientRect();
      const aboveInput = document.querySelector(".composer-above-input");
      const aboveInputHeight = aboveInput ? Math.max(0, Math.ceil(aboveInput.getBoundingClientRect().height)) : 0;
      const gap = 8;
      const availableSpace = Math.max(96, taRect.top - aboveInputHeight - 20);
      dropdown.style.left = taRect.left + "px";
      dropdown.style.width = taRect.width + "px";
      dropdown.style.minWidth = "0";
      dropdown.style.bottom = Math.max(12, window.innerHeight - taRect.top + gap + aboveInputHeight) + "px";
      dropdown.style.maxHeight = Math.min(208, availableSpace) + "px";
    };
    messageInput.addEventListener("input", () => {
      autoResizeTextarea();
    });
    window.addEventListener("resize", autoResizeTextarea);
    const updateFileAutocomplete = async () => {
      const requestSeq = ++_fileAutocompleteRequestSeq;
      const pos = messageInput.selectionEnd;
      const val = messageInput.value;
      const before = val.slice(0, pos);
      // Capture '@' followed by any word chars, dots, slashes or dashes until end
      const match = before.match(/@[\w.\/-]*$/);

      if (!match) {
        if (requestSeq === _fileAutocompleteRequestSeq) closeDrop();
        return;
      }

      const query = match[0].slice(1);
      showFileAutocompleteLoading();
      const matches = await loadFileSearchMatches(query, 30);
      if (requestSeq !== _fileAutocompleteRequestSeq) return;

      if (!matches.length) {
        closeDrop();
        return;
      }

      fileDrop.replaceChildren();
      const list = document.createElement("div");
      list.className = "file-dropdown-list";
      matches.forEach((entry) => list.appendChild(buildAutocompleteFileItem(entry)));
      fileDrop.appendChild(list);

      _dropActiveIdx = -1;
      positionComposerDropdown(fileDrop);
      if (!fileDrop.classList.contains("visible")) {
        if (_dropTimeout) { clearTimeout(_dropTimeout); _dropTimeout = null; }
        fileDrop.classList.remove("closing");
        fileDrop.style.display = "block";
        fileDrop.classList.add("visible");
        closePlusMenu();
      }
    };
    messageInput.addEventListener("input", updateFileAutocomplete);
    messageInput.addEventListener("click", () => setTimeout(updateFileAutocomplete, 10));
    messageInput.addEventListener("focus", () => {
      updateFileAutocomplete();
    });
    messageInput.addEventListener("keydown", (e) => {
      if (fileDrop.style.display === "none") return;
      const items = _dropItems();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        items[_dropActiveIdx]?.classList.remove("active");
        _dropActiveIdx = Math.min(_dropActiveIdx + 1, items.length - 1);
        items[_dropActiveIdx]?.classList.add("active");
        items[_dropActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        items[_dropActiveIdx]?.classList.remove("active");
        _dropActiveIdx = Math.max(_dropActiveIdx - 1, 0);
        items[_dropActiveIdx]?.classList.add("active");
        items[_dropActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if ((e.key === "Enter" || e.key === "Tab") && _dropActiveIdx >= 0) {
        e.preventDefault();
        e.stopImmediatePropagation();
        selectFile(items[_dropActiveIdx].dataset.path);
      } else if (e.key === "Escape") {
        closeDrop();
      }
    }, true);

    /* ── Slash command autocomplete ── */
    const cmdDrop = document.getElementById("cmdDropdown");
    let _cmdActiveIdx = -1;
    let _cmdTimeout = null;
    let _lastCmdItemsData = [];
    const SLASH_COMMANDS = [
      { name: "/memo", desc: "自分宛にメモ（本文省略可＋Import添付可、target未選択送信もself扱い）", hasArg: true },
      { name: "/model", desc: "選択中 pane に /model を送信", action: () => { submitMessage({ overrideMessage: "model" }); } },
      { name: "/up", desc: "選択中 pane に上移動を送信", hasArg: true },
      { name: "/down", desc: "選択中 pane に下移動を送信", hasArg: true },
      { name: "/restart", desc: "エージェント再起動", action: () => { submitMessage({ overrideMessage: "restart" }); } },
      { name: "/resume", desc: "エージェント再開", action: () => { submitMessage({ overrideMessage: "resume" }); } },
      { name: "/ctrlc", desc: "エージェントに Ctrl+C 送信", action: () => { submitMessage({ overrideMessage: "ctrlc" }); } },
      { name: "/interrupt", desc: "エージェントに Esc 送信", action: () => { submitMessage({ overrideMessage: "interrupt" }); } },
      { name: "/enter", desc: "エージェントに Enter 送信", action: () => { submitMessage({ overrideMessage: "enter" }); } },
    ];
    const _cmdItems = () => cmdDrop.querySelectorAll(".cmd-item");
    const closeCmdDrop = () => {
      if (cmdDrop.classList.contains("visible")) {
        cmdDrop.classList.remove("visible");
        cmdDrop.classList.add("closing");
        _cmdTimeout = setTimeout(() => {
          if (cmdDrop.classList.contains("closing")) {
            cmdDrop.style.display = "none";
            cmdDrop.classList.remove("closing");
          }
        }, 160);
      } else if (!cmdDrop.classList.contains("closing")) {
        cmdDrop.style.display = "none";
      }
      _cmdActiveIdx = -1;
    };
    const selectCmd = (idx) => {
      const item = _lastCmdItemsData[idx];
      if (!item) return;
      if (item.hasArg) {
        // Replace input with command name + space, ready for argument
        messageInput.value = item.name + " ";
        autoResizeTextarea();
        closeCmdDrop();
        focusMessageInputWithoutScroll(messageInput.value.length);
        return;
      }
      messageInput.value = "";
      autoResizeTextarea();
      closeCmdDrop();
      item.action();
      requestAnimationFrame(() => focusMessageInputWithoutScroll(0));
    };
    let _lastCmdQuery = "";
    const updateCmdAutocomplete = () => {
      const pos = messageInput.selectionEnd;
      const val = messageInput.value;
      const before = val.slice(0, pos);
      // Only trigger when "/" is the first char and no space yet (typing command name)
      if (!before.match(/^\/[\w]*$/)) {
        closeCmdDrop();
        return;
      }
      const query = before.toLowerCase();
      _lastCmdQuery = query;
      const matches = SLASH_COMMANDS.filter((c) => !query || query === "/" || c.name.startsWith(query));
      if (!matches.length) {
        closeCmdDrop();
        return;
      }
      _lastCmdItemsData = matches.map((c) => ({ ...c, type: "command", label: c.name }));
      cmdDrop.innerHTML =
        `<div class="cmd-dropdown-list">` +
        _lastCmdItemsData.map((c, i) =>
          `<div class="cmd-item" data-idx="${i}">` +
          `<span class="cmd-item-name">${escapeHtml(c.label)}</span>` +
          `<span class="cmd-item-desc">${escapeHtml(c.desc)}</span>` +
          `</div>`
        ).join("") +
        `</div>`;
      _cmdActiveIdx = -1;
      positionComposerDropdown(cmdDrop);
      if (!cmdDrop.classList.contains("visible")) {
        if (_cmdTimeout) { clearTimeout(_cmdTimeout); _cmdTimeout = null; }
        cmdDrop.classList.remove("closing");
        cmdDrop.style.display = "block";
        cmdDrop.classList.add("visible");
      }
    };
    messageInput.addEventListener("input", updateCmdAutocomplete);
    cmdDrop.addEventListener("click", (e) => e.stopPropagation());
    cmdDrop.addEventListener("pointerdown", armAutocompleteMenuBlurGuard);
    cmdDrop.addEventListener("touchstart", armAutocompleteMenuBlurGuard, { passive: true });
    cmdDrop.addEventListener("mousedown", (e) => {
      const item = e.target.closest(".cmd-item");
      if (item) { e.preventDefault(); selectCmd(parseInt(item.dataset.idx, 10)); }
    });
    messageInput.addEventListener("keydown", (e) => {
      if (cmdDrop.style.display === "none" || !cmdDrop.classList.contains("visible")) return;
      const items = _cmdItems();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        items[_cmdActiveIdx]?.classList.remove("active");
        _cmdActiveIdx = Math.min(_cmdActiveIdx + 1, items.length - 1);
        items[_cmdActiveIdx]?.classList.add("active");
        items[_cmdActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        items[_cmdActiveIdx]?.classList.remove("active");
        _cmdActiveIdx = Math.max(_cmdActiveIdx - 1, 0);
        items[_cmdActiveIdx]?.classList.add("active");
        items[_cmdActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if ((e.key === "Enter" || e.key === "Tab") && _cmdActiveIdx >= 0) {
        e.preventDefault();
        e.stopImmediatePropagation();
        selectCmd(parseInt(items[_cmdActiveIdx].dataset.idx, 10));
      } else if (e.key === "Escape") {
        closeCmdDrop();
      }
    }, true);

    messageInput.addEventListener("blur", (event) => {
      document.body.classList.remove("composing");
      const nextTarget = event.relatedTarget;
      const keepPlusMenuOpen = keepComposerPlusMenuOnBlur
        || !!(nextTarget && composerPlusMenu && composerPlusMenu.contains(nextTarget));
      const keepAutocompleteMenusOpen = _keepAutocompleteMenuOnBlur
        || !!(nextTarget && (fileDrop.contains(nextTarget) || cmdDrop.contains(nextTarget)));
      if (!keepPlusMenuOpen) closePlusMenu();
      if (!keepAutocompleteMenusOpen) {
        setTimeout(closeDrop, 150);
        setTimeout(closeCmdDrop, 150);
      }
    });

    const doCopyFallback = (text) => {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      try { document.execCommand("copy"); } catch (_) { }
      document.body.removeChild(ta);
      return Promise.resolve();
    };
    const doCopyText = (text) => {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).catch(() => doCopyFallback(text));
      }
      return doCopyFallback(text);
    };
    const markCopied = (btn) => {
      if (!btn) return;
      const copyIcon = btn.dataset.copyIcon || btn.innerHTML;
      const checkIcon = btn.dataset.checkIcon || btn.innerHTML;
      const token = String(Date.now() + Math.random());
      btn.dataset.copyAnimToken = token;
      const swapIcon = (nextIcon, keyframes) => {
        const currentSvg = btn.querySelector("svg");
        if (currentSvg && currentSvg.animate) {
          currentSvg.animate(keyframes, { duration: nextIcon === checkIcon ? 70 : 140, easing: "ease", fill: "forwards" });
        }
        setTimeout(() => {
          if (btn.dataset.copyAnimToken !== token) return;
          btn.innerHTML = nextIcon;
          const nextSvg = btn.querySelector("svg");
          if (nextSvg && nextSvg.animate) {
            nextSvg.animate([
              { opacity: 0, transform: "scale(0.82)" },
              { opacity: 1, transform: "scale(1)" }
            ], { duration: nextIcon === checkIcon ? 90 : 160, easing: "cubic-bezier(0.2, 0.9, 0.2, 1)", fill: "forwards" });
          }
        }, nextIcon === checkIcon ? 55 : 120);
      };
      swapIcon(checkIcon, [
        { opacity: 1, transform: "scale(1)" },
        { opacity: 0, transform: "scale(0.82)" }
      ]);
      btn.classList.add("copied");
      setTimeout(() => {
        if (btn.dataset.copyAnimToken !== token) return;
        btn.classList.remove("copied");
        swapIcon(copyIcon, [
          { opacity: 1, transform: "scale(1)" },
          { opacity: 0, transform: "scale(1.08)" }
        ]);
      }, 1500);
    };
    const jumpToReplySource = (targetId) => {
      if (!targetId) return;
      const target = document.querySelector(`[data-msgid="${CSS.escape(targetId)}"]`);
      if (!target) return;
      const rowTarget = target.closest("article.message-row") || target;
      const messageBodyRow = target.querySelector(".message-body-row");
      const messageBox = target.querySelector(".message") || target;
      const isAgentMessage = rowTarget.classList?.contains("message-row") && !rowTarget.classList.contains("user") && !rowTarget.classList.contains("kind-agent-thinking");
      const bodyTarget = target.querySelector(".md-body") || messageBox || target;
      const scrollTarget = messageBodyRow || messageBox || target;
      scrollTarget.scrollIntoView({ behavior: "smooth", block: "center" });
      if (isAgentMessage) {
        const railTarget = messageBodyRow || messageBox;
        railTarget.classList.remove("msg-highlight-rail");
        void railTarget.offsetWidth;
        railTarget.classList.add("msg-highlight-rail");
        railTarget.addEventListener("animationend", () => railTarget.classList.remove("msg-highlight-rail"), { once: true });
        return;
      }
      if (rowTarget.classList?.contains("user")) {
        const dividerTarget = target.querySelector(".user-message-divider");
        if (dividerTarget) {
          dividerTarget.classList.remove("msg-highlight-user-divider");
          void dividerTarget.offsetWidth;
          dividerTarget.classList.add("msg-highlight-user-divider");
          dividerTarget.addEventListener("animationend", () => dividerTarget.classList.remove("msg-highlight-user-divider"), { once: true });
        }
        return;
      }
      bodyTarget.classList.remove("msg-highlight");
      void bodyTarget.offsetWidth;
      bodyTarget.classList.add("msg-highlight");
      bodyTarget.addEventListener("animationend", () => bodyTarget.classList.remove("msg-highlight"), { once: true });
    };
    document.getElementById("messages").addEventListener("click", (e) => {
      const metaBtn = e.target.closest(".message-meta-below button, .user-message-meta button, .message-meta-below .meta-agent, .user-message-meta .meta-agent");
      if (metaBtn) {
        const row = metaBtn.closest("article.message-row");
        if (row) {
          row.classList.add("meta-keep-visible");
          if (row._metaKeepTimer) clearTimeout(row._metaKeepTimer);
          row._metaKeepTimer = setTimeout(() => {
            row.classList.remove("meta-keep-visible");
            row._metaKeepTimer = null;
          }, 1800);
        }
      }
      const anyLink = e.target.closest("a[href]");
      if (anyLink) {
        const href = anyLink.getAttribute("href");
        const path = filePathFromLinkAnchor(anyLink);
        if (path) {
          e.preventDefault();
          e.stopPropagation();
          void openFileSurface(path, extFromPath(path), anyLink, e);
          return;
        }
        if (href && !href.startsWith("#") && !href.startsWith("javascript:")) {
          // Open external links in a new window to prevent whiteout in standalone/PWA mode.
          e.preventDefault();
          e.stopPropagation();
          window.open(href, "_blank", "noopener,noreferrer");
          return;
        }
      }
      const fileCard = e.target.closest(".file-card");
      if (fileCard) {
        e.stopPropagation();
        const path = fileCard.dataset.filepath;
        const ext = fileCard.dataset.ext || "";
        void openFileSurface(path, ext, fileCard, e);
        return;
      }
      const thinkingRowEarly = e.target.closest(".message-thinking-row");
      if (thinkingRowEarly) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      const collapseToggle = e.target.closest(".user-collapse-toggle");
      if (collapseToggle) {
        const row = collapseToggle.closest("article.message-row.user");
        const msgId = row?.dataset.msgid || "";
        if (!row || !msgId) return;
        if (expandedUserMessages.has(msgId)) {
          expandedUserMessages.delete(msgId);
        } else {
          expandedUserMessages.add(msgId);
        }
        syncUserMessageCollapse(row);
        return;
      }
      const providerEventsBtn = e.target.closest("[data-provider-events]");
      if (providerEventsBtn) {
        e.preventDefault();
        e.stopPropagation();
        void showProviderEventsModal(providerEventsBtn.dataset.providerEvents || "");
        return;
      }
      const btn = e.target.closest(".copy-btn");
      if (!btn) return;
      const raw = btn.closest(".message")?.dataset.raw ?? "";
      doCopyText(raw).then(() => {
        markCopied(btn);
      }).catch(() => { });
    });
    let currentAgentStatuses = {};
    let currentAgentRuntime = {};
    let currentProviderRuntime = {};
    const THINKING_RUNTIME_ENTER_MS = 320;
    const THINKING_RUNTIME_LEAVE_MS = 320;
    const THINKING_RUNTIME_AGE_TICK_MS = 1000;
    let thinkingRuntimeItems = {};
    let thinkingProviderRuntimeMeta = { id: "", phase: "live", updatedAt: 0, enterTimer: 0 };
    let thinkingRuntimeAgeTimer = 0;
    const clearThinkingRuntimeItemTimers = (item) => {
      if (!item) return;
      clearTimeout(item.enterTimer);
      item.enterTimer = 0;
    };
    const clearThinkingProviderRuntimeTimer = () => {
      clearTimeout(thinkingProviderRuntimeMeta.enterTimer);
      thinkingProviderRuntimeMeta.enterTimer = 0;
    };
    const resetThinkingProviderRuntimeMeta = () => {
      clearThinkingProviderRuntimeTimer();
      thinkingProviderRuntimeMeta.id = "";
      thinkingProviderRuntimeMeta.phase = "live";
      thinkingProviderRuntimeMeta.updatedAt = 0;
    };
    const syncThinkingProviderRuntimeMeta = (eventId) => {
      const nextId = String(eventId || "").trim();
      if (!nextId) {
        resetThinkingProviderRuntimeMeta();
        return thinkingProviderRuntimeMeta;
      }
      if (thinkingProviderRuntimeMeta.id !== nextId) {
        clearThinkingProviderRuntimeTimer();
        thinkingProviderRuntimeMeta.id = nextId;
        thinkingProviderRuntimeMeta.phase = "enter";
        thinkingProviderRuntimeMeta.updatedAt = Date.now();
        thinkingProviderRuntimeMeta.enterTimer = setTimeout(() => {
          if (thinkingProviderRuntimeMeta.id !== nextId || thinkingProviderRuntimeMeta.phase !== "enter") return;
          thinkingProviderRuntimeMeta.phase = "live";
          renderThinkingIndicator();
        }, THINKING_RUNTIME_ENTER_MS);
      }
      return thinkingProviderRuntimeMeta;
    };
    const currentThinkingRuntimeItem = (agent) => thinkingRuntimeItems[agent] || null;
    const clearThinkingRuntimeAgent = (agent, { suppressRender = false } = {}) => {
      const item = thinkingRuntimeItems[agent];
      if (!item) return false;
      clearThinkingRuntimeItemTimers(item);
      delete thinkingRuntimeItems[agent];
      if (!suppressRender) renderThinkingIndicator();
      return true;
    };
    const setThinkingRuntimeItem = (agent, event, { suppressRender = false } = {}) => {
      const entry = {
        id: String(event?.id || "").trim(),
        text: String(event?.text || "").trim(),
        phase: "enter",
        enterTimer: 0,
        updatedAt: Number.isFinite(Number(event?.updatedAt)) && Number(event.updatedAt) > 0
          ? Number(event.updatedAt)
          : Date.now(),
      };
      if (!entry.id || !entry.text) return false;
      entry.enterTimer = setTimeout(() => {
        const current = currentThinkingRuntimeItem(agent);
        if (!current || current.phase !== "enter") return;
        current.phase = "live";
        renderThinkingIndicator();
      }, THINKING_RUNTIME_ENTER_MS);
      const current = currentThinkingRuntimeItem(agent);
      if (current && current.id === entry.id && current.text === entry.text) return false;
      clearThinkingRuntimeItemTimers(current);
      thinkingRuntimeItems[agent] = entry;
      if (!suppressRender) renderThinkingIndicator();
      return true;
    };
    const syncThinkingRuntimeItems = (statuses, { suppressRender = false } = {}) => {
      const runningAgents = new Set(
        Object.entries(statuses || {})
          .filter(([, status]) => status === "running")
          .map(([agent]) => agent)
      );
      let changed = false;
      Object.keys(thinkingRuntimeItems).forEach((agent) => {
        if (runningAgents.has(agent)) return;
        changed = clearThinkingRuntimeAgent(agent, { suppressRender: true }) || changed;
      });
      runningAgents.forEach((agent) => {
        const payload = currentAgentRuntime?.[agent];
        const raw = payload?.current_event;
        const id = String(raw?.id || "").trim();
        const text = String(raw?.text || "").trim();
        if (!id || !text) {
          changed = clearThinkingRuntimeAgent(agent, { suppressRender: true }) || changed;
        } else {
          changed = setThinkingRuntimeItem(agent, { id, text }, { suppressRender: true }) || changed;
        }
      });
      if (changed && !suppressRender) {
        renderThinkingIndicator();
      }
    };
    const applySessionState = (data) => {
      if (!data || typeof data !== "object") return;
      if (typeof data.session === "string" && data.session) {
        currentSessionName = data.session;
      }
      if (typeof data.active === "boolean") {
        sessionActive = data.active;
        if (sessionActive) {
          clearDraftLaunchHints();
        }
      }
      if (typeof data.launch_pending === "boolean") {
        sessionLaunchPending = !sessionActive && (data.launch_pending || sessionLaunchPending || draftLaunchHintActive);
      }
      {
        const resolvedTargets = normalizedSessionTargets(data.targets);
        const nextTargets = canInteractWithSession() ? resolvedTargets : [];
        const nextTargetsSig = JSON.stringify(nextTargets);
        const currentTargetsSig = JSON.stringify(availableTargets);
        if (nextTargetsSig !== currentTargetsSig) {
          availableTargets = nextTargets;
          selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
          saveTargetSelection(currentSessionName, selectedTargets);
          renderTargetPicker(availableTargets);
          if (cameraMode && !cameraMode.hidden) {
            renderCameraModeTargets();
          }
        }
      }
      document.getElementById("message").disabled = !sessionActive;
      setQuickActionsDisabled(!sessionActive);
      if (sessionLaunchPending) {
        setStatus("select one initial agent and start the session");
      } else if (!sessionActive) {
        setStatus("archived session is read-only");
      }
      syncPendingLaunchControls();
      maybeAutoOpenComposer();
      if (data.agent_runtime && typeof data.agent_runtime === "object") {
        currentAgentRuntime = { ...data.agent_runtime };
      } else {
        currentAgentRuntime = {};
      }
      if (data.provider_runtime && typeof data.provider_runtime === "object") {
        currentProviderRuntime = { ...data.provider_runtime };
      } else {
        currentProviderRuntime = {};
      }
      if (data.statuses && typeof data.statuses === "object") {
        syncThinkingRuntimeItems(data.statuses, { suppressRender: true });
        renderAgentStatus(data.statuses);
      } else {
        renderThinkingIndicator();
      }
    };
    const formatCompactMetric = (value) => {
      const num = Number(value);
      if (!Number.isFinite(num)) return "";
      const abs = Math.abs(num);
      if (abs >= 1_000_000) {
        return `${(num / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1).replace(/\.0$/, "")}M`;
      }
      if (abs >= 1_000) {
        return `${(num / 1_000).toFixed(abs >= 10_000 ? 0 : 1).replace(/\.0$/, "")}k`;
      }
      return String(Math.trunc(num));
    };
    const providerRuntimeSummaryItems = (runtime) => {
      if (!runtime || typeof runtime !== "object") return [];
      const explicit = Array.isArray(runtime.summary_items)
        ? runtime.summary_items.map((item) => String(item || "").trim()).filter(Boolean)
        : [];
      if (explicit.length) return explicit;
      const derived = [];
      const chunkIndex = Number(runtime.chunk_index);
      if (Number.isFinite(chunkIndex)) derived.push(`chunk ${chunkIndex + 1}`);
      const chunkCount = Number(runtime.chunk_count);
      if (Number.isFinite(chunkCount) && chunkCount > 0) derived.push(`${chunkCount} chunks`);
      const totalTokens = formatCompactMetric(runtime.usage_total_tokens);
      if (totalTokens) derived.push(`${totalTokens} tok`);
      const thoughtTokens = formatCompactMetric(runtime.usage_thought_tokens);
      if (thoughtTokens) derived.push(`${thoughtTokens} think`);
      const outputChars = formatCompactMetric(runtime.output_chars);
      if (outputChars) derived.push(`${outputChars} chars`);
      const finishReason = String(runtime.finish_reason || "").trim();
      if (finishReason) derived.push(finishReason);
      const errorType = String(runtime.error_type || "").trim();
      if (errorType) derived.push(errorType);
      return derived;
    };
    const providerRuntimeStructuredText = (runtime) => {
      if (!runtime || typeof runtime !== "object") return "";
      const parts = [];
      const eventName = String(runtime.event_name || "").trim();
      if (eventName) parts.push(eventName);
      const summaryItems = providerRuntimeSummaryItems(runtime);
      if (summaryItems.length) parts.push(...summaryItems);
      return parts.join(" · ");
    };
    const providerRuntimePreviewText = (runtime) => {
      if (!runtime || typeof runtime !== "object") return "";
      const preview = String(runtime.preview || "").trim();
      if (!preview) return "";
      const structured = providerRuntimeStructuredText(runtime);
      return preview === structured ? "" : preview;
    };
    const buildThinkingPreviewStreamHtml = (text) => {
      const chars = Array.from(String(text || ""));
      if (!chars.length) return "";
      const limited = chars.slice(0, 320);
      const body = limited.map((ch, idx) =>
        `<span class="stream-char" style="--stream-char-i:${idx}">${escapeHtml(ch)}</span>`
      ).join("");
      return body + (chars.length > limited.length ? "…" : "");
    };
    const wrapThinkingChars = (text, offset = 0) => {
      return Array.from(String(text || "")).map((ch, i) =>
        `<span class="thinking-char" style="--char-i:${i + offset}">${escapeHtml(ch)}</span>`
      ).join("");
    };
    const normalizeThinkingRuntimeToken = (value) =>
      String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
    const classifyThinkingRuntimeTool = (toolNameRaw) => {
      const tool = normalizeThinkingRuntimeToken(toolNameRaw);
      if (!tool) return "";
      if (/^(view|viewimage|read|readfile|readlints|files?|openfile|attachmentfile)/.test(tool)) return "Read";
      if (/^(grep|rg|search|searchtext|googlesearch|grepsearch|query)/.test(tool)) return "Search";
      if (/^(glob|listdirectory|ls|explore|browser|webfetch|fetchurl|directory)/.test(tool)) return "Explore";
      if (/^(bash|shell|execcommand|runshellcommand|writestdin|command|interrupt|ctrlc|enter)/.test(tool)) return "Run";
      if (/^(applypatch|patch|replace|strreplace|edit|editedtextfile|update|rename)/.test(tool)) return "Edit";
      if (/^(write|writefile|create|newfile)/.test(tool)) return "Write";
      if (/^(delete|remove|unlink|rm)/.test(tool)) return "Delete";
      if (/^(skill|invokedskills|skilllisting|loadskill)/.test(tool)) return "Skill";
      if (/^(askuser|reportintent|model|permissionmode|queueoperation|sessioninfo|turnstart|turnend|taskstarted|taskcomplete)/.test(tool)) return "Status";
      return "";
    };
    const classifyThinkingRuntimeLabel = (line, token = "", rest = "") => {
      const lowerLine = String(line || "").toLowerCase();
      const key = normalizeThinkingRuntimeToken(token);
      const lowerRest = String(rest || "").toLowerCase();
      const has = (re) => re.test(lowerLine);
      if (String(line || "").trim().startsWith("✦") || has(/\b(thinking|reasoning|thought|reasoningopaque|agent_reasoning|response_item\.reasoning|gemini\.thoughts(?:\.[a-z_]+)?)\b/)) return "Thinking";
      if (has(/\b(error|failed|failure|exception|rate[\s-]?limit|invalid command(?: file)?|429|success\s*=\s*false)\b/)) return "Error";
      if (has(/\b(interrupted|turn_aborted|abort(?:ed)?)\b/)) return "Interrupted";
      if (has(/\b(compact(?:ed|ing|ion)?|context_compacted|compact_boundary|compact_boundary|compaction_(?:start|complete)|session\.compaction_(?:start|complete)|session\.compaction_start|session\.compaction_complete)\b/)) return "Compacted";
      if (has(/\b(plan(?:ning)?|plan tool|toolrequests?)\b/) || lowerLine.startsWith("i will ") || lowerLine.startsWith("i'll ")) return "Planning";
      if (has(/\b(usage|token_count|tokens?(?:\.|_|$)|input_tokens|output_tokens|cached_tokens?|usage_[a-z_]+)\b/)) return "Usage";
      if (has(/\b(task_reminder|reminder)\b/)) return "Reminder";
      if (has(/\b(skill|invoked_skills|skill_listing|loaded skill|skills available|invoked skill)\b/)) return "Skill";
      if (has(/\b(attachment\.edited_text_file|edited_text_file)\b/)) return "Edit";
      if (has(/\b(attachment\.file|file opened)\b/)) return "Read";
      if (has(/\b(result|result summary|resultdisplay|function_call_output|custom_tool_call_output|execution_complete|exec_command_end|patch_apply_end|tool[_-]?result|success|run finished|edit finished)\b/) && !has(/\b(error|failed|failure|success\s*=\s*false)\b/)) return "Result";
      if (has(/\b(status|task[_ ]started|task[_ ]complete|task finished|turn[_ ]start|turn[_ ]end|turn finished|queued|dequeued|queue[-_ ]removed|queue-operation\.(?:enqueue|dequeue|remove)|permission mode changed|permission-mode|model changed|session\.model_change|model info|session\.info|mcp connected|signed in|context changed|turn_context|date changed|date_change|tools changed|deferred_tools_delta|provider meta|provideroptions\.cursor|system initialized|command_permissions)\b/)) {
        return "Status";
      }
      const runtimeToolMatch = lowerLine.match(/(?:toolname|name)\s*[:=]\s*['"]?([a-z0-9_.-]+)/i);
      const runtimeToolLabel = classifyThinkingRuntimeTool(runtimeToolMatch?.[1] || "");
      if (runtimeToolLabel) return runtimeToolLabel;
      const tokenToolLabel = classifyThinkingRuntimeTool(token);
      if (tokenToolLabel) return tokenToolLabel;
      if (/^(run|running|ran|bashing|building|cloning|committing|fetching|installing|pushing|spawning|testing|execcommandend)$/.test(key)) return "Run";
      if (/^(read|reading|view|viewing|readfile|readlints|fileopened)$/.test(key)) return "Read";
      if (/^(search|searching|grepped|grep|rg|searchtext|googlesearch|grepsearch)$/.test(key)) return "Search";
      if (/^(explore|exploring|glob|globbing|listing|listdirectory|browser)$/.test(key)) return "Explore";
      if (/^(edit|editing|edited|patching|replace|updating|update|patchapplyend|editedtextfile)$/.test(key)) return "Edit";
      if (/^(write|writing|create|creating|wrote)$/.test(key)) return "Write";
      if (/^(delete|deleting|deleted|remove|removed)$/.test(key)) return "Delete";
      if (/^(status|context|queue|permission|model|authentication|mcp|turn|task|info|permissionmode|commandpermissions|datechange)$/.test(key)) return "Status";
      if (/^(result|finished|complete|completed|done)$/.test(key)) return "Result";
      if (/^(compacted|compacting|compaction)$/.test(key)) return "Compacted";
      if (/^(interrupted|abort|aborted)$/.test(key)) return "Interrupted";
      if (/^(skill|skills)$/.test(key) || lowerRest.includes("skill")) return "Skill";
      return "";
    };
    const buildThinkingRuntimeHtml = (text) => {
      const raw = String(text || "").replace(/\r\n?/g, "\n");
      if (!raw) return "";
      const lines = raw.split("\n");
      const firstLine = lines.find((line) => line.trim().length > 0) ?? lines[0] ?? "";
      /* Runtime activity stays on a single line; drop any later lines here and let CSS ellipsize long text. */
      if (firstLine.trim().startsWith("✦")) {
        return `<span class="message-thinking-runtime-keyword">${wrapThinkingChars("Thinking")}</span><span class="message-thinking-runtime-detail">${escapeHtml(` ${firstLine.trim()}`)}</span>`;
      }
      const cleanedLine = firstLine.replace(/^[⏺●•·◦○]\s+/, "").trim();
      const match = cleanedLine.match(/^([A-Za-z][A-Za-z0-9_.:-]*)([\s\S]*)$/);
      if (match) {
        const keyword = String(match[1] || "");
        const rest = String(match[2] || "");
        const label = classifyThinkingRuntimeLabel(cleanedLine, keyword, rest);
        if (label) {
          const trimmedRest = rest.trim();
          const tokenLooksStructured = /[._:]/.test(keyword);
          const detailText = trimmedRest
            ? (tokenLooksStructured ? ` ${cleanedLine}` : rest)
            : (keyword.toLowerCase() !== label.toLowerCase() ? ` ${cleanedLine}` : "");
          const detail = detailText
            ? `<span class="message-thinking-runtime-detail">${escapeHtml(detailText)}</span>`
            : "";
          return `<span class="message-thinking-runtime-keyword">${wrapThinkingChars(label)}</span>${detail}`;
        }
      }
      const fallbackLabel = classifyThinkingRuntimeLabel(cleanedLine);
      if (fallbackLabel) {
        return `<span class="message-thinking-runtime-keyword">${wrapThinkingChars(fallbackLabel)}</span><span class="message-thinking-runtime-detail">${escapeHtml(` ${cleanedLine}`)}</span>`;
      }
      const cleaned = cleanedLine || firstLine;
      return escapeHtml(cleaned || firstLine);
    };
    const formatThinkingRuntimeAgeText = (updatedAt, now = Date.now()) => {
      const value = Number(updatedAt);
      if (!Number.isFinite(value) || value <= 0) return "0s";
      const elapsedSec = Math.max(0, Math.floor((now - value) / 1000));
      return `${elapsedSec}s`;
    };
    const updateThinkingRuntimeAgeNode = (ageNode, now = Date.now()) => {
      if (!ageNode) return;
      const updatedAt = Number(ageNode.dataset.updatedAt || "0");
      ageNode.textContent = formatThinkingRuntimeAgeText(updatedAt, now);
    };
    const refreshThinkingRuntimeAges = (scope = document, now = Date.now()) => {
      const root = scope && typeof scope.querySelectorAll === "function" ? scope : document;
      root.querySelectorAll(".message-thinking-runtime-age[data-updated-at]").forEach((node) => {
        updateThinkingRuntimeAgeNode(node, now);
      });
    };
    const buildThinkingRuntimeLineInnerHtml = (contentHtml, updatedAt) => {
      const safeUpdatedAt = Math.max(0, Math.round(Number(updatedAt) || Date.now()));
      return `<span class="message-thinking-runtime-body">${contentHtml}</span><span class="message-thinking-runtime-age" data-runtime-age data-updated-at="${safeUpdatedAt}">${formatThinkingRuntimeAgeText(safeUpdatedAt)}</span>`;
    };
    const setThinkingRuntimeLineStateLater = (line, state, delayMs) => {
      if (!line) return;
      if (line._runtimeStateTimer) {
        clearTimeout(line._runtimeStateTimer);
        line._runtimeStateTimer = 0;
      }
      line._runtimeStateTimer = setTimeout(() => {
        line._runtimeStateTimer = 0;
        if (!line.isConnected) return;
        line.dataset.state = state;
      }, Math.max(0, Number(delayMs) || 0));
    };
    const removeThinkingRuntimeLineLater = (line, delayMs) => {
      if (!line) return;
      if (line._runtimeRemoveTimer) {
        clearTimeout(line._runtimeRemoveTimer);
        line._runtimeRemoveTimer = 0;
      }
      line._runtimeRemoveTimer = setTimeout(() => {
        line._runtimeRemoveTimer = 0;
        if (!line.isConnected) return;
        if (line._runtimeStateTimer) {
          clearTimeout(line._runtimeStateTimer);
          line._runtimeStateTimer = 0;
        }
        line.remove();
      }, Math.max(0, Number(delayMs) || 0));
    };
    const syncThinkingRuntimeSlot = (label, { contentHtml, state = "live", eventId = "", updatedAt = Date.now() }) => {
      if (!label) return;
      let slot = label.querySelector(".message-thinking-runtime-slot");
      if (!slot) {
        slot = document.createElement("span");
        slot.className = "message-thinking-runtime-slot";
        label.appendChild(slot);
      }
      const stableState = String(state || "live") === "enter" ? "enter" : "live";
      const stableId = String(eventId || "");
      const stableUpdatedAt = Math.max(0, Math.round(Number(updatedAt) || Date.now()));
      const lines = Array.from(slot.querySelectorAll(".message-thinking-runtime-line"));
      const activeLine = lines.find((line) => String(line.dataset.state || "") !== "leave") || lines[lines.length - 1] || null;
      const activeBody = activeLine?.querySelector(".message-thinking-runtime-body");
      const activeHtml = activeBody ? activeBody.innerHTML : "";
      const sameText = !!activeLine && activeHtml === contentHtml;
      const sameId = !!activeLine && String(activeLine.dataset.eventId || "") === stableId;

      if (activeLine && sameText && sameId) {
        activeLine.dataset.state = stableState;
        activeLine.dataset.updatedAt = String(stableUpdatedAt);
        const ageNode = activeLine.querySelector(".message-thinking-runtime-age");
        if (ageNode) {
          ageNode.dataset.updatedAt = String(stableUpdatedAt);
          updateThinkingRuntimeAgeNode(ageNode);
        }
        if (stableState === "enter") {
          setThinkingRuntimeLineStateLater(activeLine, "live", THINKING_RUNTIME_ENTER_MS);
        }
        return;
      }

      if (activeLine) {
        activeLine.dataset.state = "leave";
        removeThinkingRuntimeLineLater(activeLine, THINKING_RUNTIME_LEAVE_MS + 30);
      }

      const nextLine = document.createElement("span");
      nextLine.className = "message-thinking-runtime-line";
      nextLine.dataset.state = stableState;
      nextLine.dataset.eventId = stableId;
      nextLine.dataset.updatedAt = String(stableUpdatedAt);
      nextLine.innerHTML = buildThinkingRuntimeLineInnerHtml(contentHtml, stableUpdatedAt);
      slot.appendChild(nextLine);
      if (stableState === "enter") {
        setThinkingRuntimeLineStateLater(nextLine, "live", THINKING_RUNTIME_ENTER_MS);
      }

      const allLines = Array.from(slot.querySelectorAll(".message-thinking-runtime-line"));
      if (allLines.length > 2) {
        allLines.slice(0, allLines.length - 2).forEach((line) => {
          if (line._runtimeStateTimer) {
            clearTimeout(line._runtimeStateTimer);
            line._runtimeStateTimer = 0;
          }
          if (line._runtimeRemoveTimer) {
            clearTimeout(line._runtimeRemoveTimer);
            line._runtimeRemoveTimer = 0;
          }
          line.remove();
        });
      }
      refreshThinkingRuntimeAges(slot);
    };
    if (!thinkingRuntimeAgeTimer) {
      thinkingRuntimeAgeTimer = setInterval(() => {
        refreshThinkingRuntimeAges();
      }, THINKING_RUNTIME_AGE_TICK_MS);
    }
    const renderCameraModeThinking = () => {
      if (!cameraModeThinking) return;
      cameraModeThinking.hidden = true;
      cameraModeThinking.innerHTML = "";
      cameraModeThinking.dataset.sig = "";
    };
    let thinkingFloatingIconFrame = 0;
    const removeThinkingFloatingIcons = () => {
      if (thinkingFloatingIconFrame) {
        cancelAnimationFrame(thinkingFloatingIconFrame);
        thinkingFloatingIconFrame = 0;
      }
      document.getElementById("messageThinkingFloatingIcons")?.remove();
    };
    const ensureThinkingFloatingIcons = () => {
      let rail = document.getElementById("messageThinkingFloatingIcons");
      if (!rail) {
        rail = document.createElement("div");
        rail.id = "messageThinkingFloatingIcons";
        rail.className = "message-thinking-floating-icons";
        rail.hidden = true;
        document.body.appendChild(rail);
      }
      return rail;
    };
    const syncThinkingFloatingIcons = () => {
      thinkingFloatingIconFrame = 0;
      const root = document.getElementById("messages");
      const container = root?.querySelector(".message-thinking-container");
      if (!root || !timeline || !container || !document.body?.classList.contains("agent-runtime-running")) {
        removeThinkingFloatingIcons();
        return;
      }
      const sources = Array.from(container.querySelectorAll(".message-thinking-row"))
        .map((row) => {
          const wrap = row.querySelector(".message-thinking-icon-wrap");
          return wrap ? { row, wrap } : null;
        })
        .filter(Boolean);
      if (!sources.length) {
        removeThinkingFloatingIcons();
        return;
      }

      const rail = ensureThinkingFloatingIcons();
      const sig = sources.map(({ row, wrap }) => {
        const icon = wrap.querySelector(".message-thinking-icon");
        return [
          row.dataset.agent || "",
          row.dataset.provider || "",
          row.style.getPropertyValue("--agent-pulse-delay") || "",
          icon?.className || "",
          icon?.getAttribute("style") || "",
        ].join(":");
      }).join("|");
      if (rail.dataset.sig !== sig) {
        rail.dataset.sig = sig;
        rail.innerHTML = "";
        sources.forEach(({ row, wrap }) => {
          const clone = wrap.cloneNode(true);
          clone.classList.add("message-thinking-floating-icon-wrap");
          clone.style.setProperty("--agent-pulse-delay", row.style.getPropertyValue("--agent-pulse-delay") || "0s");
          rail.appendChild(clone);
        });
      }

      const sourceAnchor = sources[0].wrap.closest(".message-thinking-icons") || sources[0].wrap;
      const sourceRect = sourceAnchor.getBoundingClientRect();
      const timelineRect = timeline.getBoundingClientRect();
      if (!sourceRect.width || !sourceRect.height || !timelineRect.width || !timelineRect.height) {
        rail.hidden = true;
        rail.classList.remove("visible");
        return;
      }
      const bottomInset = 14;
      const expectedHeight = Math.max(24, sourceRect.height);
      const stickyTop = timelineRect.bottom - bottomInset - expectedHeight;
      const shouldStick = sourceRect.top > stickyTop || sourceRect.bottom < timelineRect.top;
      if (!shouldStick) {
        rail.classList.remove("visible");
        rail.hidden = true;
        return;
      }

      rail.hidden = false;
      const railWidth = rail.offsetWidth || sourceRect.width || 28;
      const left = Math.max(
        timelineRect.left + 8,
        Math.min(sourceRect.left, timelineRect.right - railWidth - 8)
      );
      const bottom = Math.max(12, window.innerHeight - timelineRect.bottom + bottomInset);
      rail.style.left = `${Math.round(left)}px`;
      rail.style.bottom = `${Math.round(bottom)}px`;
      rail.classList.add("visible");
    };
    const scheduleThinkingFloatingIcons = () => {
      if (thinkingFloatingIconFrame) return;
      thinkingFloatingIconFrame = requestAnimationFrame(syncThinkingFloatingIcons);
    };
    const renderThinkingIndicator = () => {
      const root = document.getElementById("messages");
      if (!root) {
        document.body?.classList.remove("agent-runtime-running");
        removeThinkingFloatingIcons();
        return;
      }
      const runningAgents = Object.keys(currentAgentStatuses).filter((agent) => currentAgentStatuses[agent] === "running");
      const providerRuntimeActive = !!currentProviderRuntime?.active && !!currentProviderRuntime?.provider;
      const hasRuntimeRunning = runningAgents.length > 0 || providerRuntimeActive;
      document.body?.classList.toggle("agent-runtime-running", hasRuntimeRunning);
      const existingContainer = root.querySelector(".message-thinking-container");

      if (!root.querySelector("article.message-row") || !hasRuntimeRunning) {
        if (existingContainer) existingContainer.remove();
        resetThinkingProviderRuntimeMeta();
        root.dataset.thinkingSig = "";
        renderCameraModeThinking();
        removeThinkingFloatingIcons();
        maybeRestorePollScrollLock();
        return;
      }

      const providerStructured = providerRuntimeStructuredText(currentProviderRuntime);
      const providerPreview = providerRuntimePreviewText(currentProviderRuntime);
      const providerRuntimeEventId = providerRuntimeActive
        ? JSON.stringify({
          provider: currentProviderRuntime.provider || "",
          runId: currentProviderRuntime.run_id || "",
          status: currentProviderRuntime.status || "",
          event: currentProviderRuntime.event_name || "",
          seq: currentProviderRuntime.event_seq || "",
          summary: providerRuntimeSummaryItems(currentProviderRuntime),
          preview: providerPreview,
        })
        : "";
      let providerRuntimeMeta = thinkingProviderRuntimeMeta;
      if (providerRuntimeActive) {
        providerRuntimeMeta = syncThinkingProviderRuntimeMeta(providerRuntimeEventId);
      } else {
        resetThinkingProviderRuntimeMeta();
      }
      const providerSig = providerRuntimeActive
        ? `${providerRuntimeEventId}|${providerRuntimeMeta.phase || "live"}`
        : "";
      const agentRuntimeSig = JSON.stringify(
        runningAgents.map((agent) => [
          agent,
          currentThinkingRuntimeItem(agent)
            ? [currentThinkingRuntimeItem(agent).id, currentThinkingRuntimeItem(agent).text, currentThinkingRuntimeItem(agent).phase]
            : null,
        ])
      );
      const nextThinkingSig = `${runningAgents.join(",")}|${agentRuntimeSig}|${providerSig}`;
      if (root.dataset.thinkingSig === nextThinkingSig && existingContainer) {
        if (root.lastElementChild !== existingContainer) {
          root.appendChild(existingContainer);
        }
        refreshThinkingRuntimeAges(existingContainer);
        scheduleThinkingFloatingIcons();
        return;
      }

      const container = existingContainer || document.createElement("div");
      container.className = "message-thinking-container";

      const ensureAgentRow = (agent) => {
        let row = Array.from(container.querySelectorAll(".message-thinking-row[data-agent]"))
          .find((node) => node.dataset.agent === agent);
        const pulse = agentPulseOffset(agent);
        if (!row) {
          row = document.createElement("div");
          row.className = "message-thinking-row";
          row.dataset.agent = agent;
          row.innerHTML = `
            <span class="message-thinking-icons">
              <span class="message-thinking-icon-wrap">
                <span class="message-thinking-glow"></span>
                ${thinkingIconImg(agent, `message-thinking-icon message-thinking-icon--${agentBaseName(agent)}`)}
              </span>
            </span>
            <span class="message-thinking-label message-thinking-label-agent"></span>
          `;
        }
        row.style.setProperty("--agent-pulse-delay", `${pulse}s`);
        const runtimeItem = currentThinkingRuntimeItem(agent);
        const label = row.querySelector(".message-thinking-label-agent");

        const nextText = runtimeItem ? buildThinkingRuntimeHtml(runtimeItem.text) : `<span class="message-thinking-runtime-keyword">${wrapThinkingChars("Running...")}</span>`;
        const nextState = runtimeItem ? (runtimeItem.phase || "live") : "live";
        const nextId = runtimeItem ? (String(runtimeItem.id || "")) : "generic";
        const nextUpdatedAt = runtimeItem?.updatedAt || Date.now();

        if (label) {
          syncThinkingRuntimeSlot(label, {
            contentHtml: nextText,
            state: nextState,
            eventId: nextId,
            updatedAt: nextUpdatedAt,
          });
        }
        return row;
      };

      const ensureProviderRow = () => {
        const providerAgent = agentBaseName(currentProviderRuntime.provider || "gemini") || "gemini";
        const pulse = agentPulseOffset(providerAgent);
        const providerPreviewHtml = providerPreview ? buildThinkingPreviewStreamHtml(providerPreview) : "";
        let row = container.querySelector(".message-thinking-row-provider");
        if (!row) {
          row = document.createElement("div");
          row.className = "message-thinking-row message-thinking-row-provider";
          row.innerHTML = `
            <span class="message-thinking-icons">
              <span class="message-thinking-icon-wrap">
                <span class="message-thinking-glow"></span>
                ${thinkingIconImg(providerAgent, `message-thinking-icon message-thinking-icon--${agentBaseName(providerAgent)}`)}
              </span>
            </span>
            <span class="message-thinking-label message-thinking-label-provider"></span>
          `;
        }
        row.dataset.providerEvents = String(currentProviderRuntime.system_msg_id || "");
        row.dataset.provider = providerAgent;
        row.style.setProperty("--agent-pulse-delay", `${pulse}s`);
        const label = row.querySelector(".message-thinking-label-provider");
        const syncProviderPreviewLine = (className, html) => {
          const existing = label?.querySelector(`.${className}`);
          if (!html) {
            existing?.remove();
            return;
          }
          if (existing && existing.innerHTML === html) return;
          const node = document.createElement("span");
          node.className = className;
          node.innerHTML = html;
          if (existing) existing.replaceWith(node);
          else label?.appendChild(node);
        };
        const providerText = providerStructured ? `<span class="message-thinking-runtime-keyword">${wrapThinkingChars(providerStructured)}</span>` : `<span class="message-thinking-runtime-keyword">${wrapThinkingChars("Running...")}</span>`;
        syncThinkingRuntimeSlot(label, {
          contentHtml: providerText,
          state: providerRuntimeMeta.phase || "live",
          eventId: providerRuntimeMeta.id || providerRuntimeEventId || "provider-runtime",
          updatedAt: providerRuntimeMeta.updatedAt || Date.now(),
        });
        syncProviderPreviewLine("message-thinking-label-preview", providerPreviewHtml);
        return row;
      };

      const desiredAgents = new Set(runningAgents);
      container.querySelectorAll(".message-thinking-row[data-agent]").forEach((row) => {
        if (!desiredAgents.has(row.dataset.agent || "")) {
          row.remove();
        }
      });
      if (!providerRuntimeActive) {
        resetThinkingProviderRuntimeMeta();
        container.querySelector(".message-thinking-row-provider")?.remove();
      }

      runningAgents.forEach((agent) => {
        container.appendChild(ensureAgentRow(agent));
      });
      if (providerRuntimeActive) {
        container.appendChild(ensureProviderRow());
      }
      if (root.lastElementChild !== container) {
        root.appendChild(container);
      }
      root.dataset.thinkingSig = nextThinkingSig;
      refreshThinkingRuntimeAges(container);
      renderCameraModeThinking();
      scheduleThinkingFloatingIcons();
      maybeRestorePollScrollLock();
    };
    timeline?.addEventListener("scroll", scheduleThinkingFloatingIcons, { passive: true });
    window.addEventListener("resize", scheduleThinkingFloatingIcons, { passive: true });
    const userCollapseScrollObserver =
      typeof IntersectionObserver === "function" && timeline && timeline.nodeType === 1
        ? new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (entry.isIntersecting) continue;
              const row = entry.target;
              const msgId = row?.dataset?.msgid || "";
              if (!msgId || !expandedUserMessages.has(msgId)) continue;
              expandedUserMessages.delete(msgId);
              syncUserMessageCollapse(row);
            }
          },
          { root: timeline, threshold: 0 }
        )
        : null;
    const syncUserMessageCollapse = (scope = document) => {
      const rows = scope?.matches?.("article.message-row.user")
        ? [scope]
        : Array.from(scope.querySelectorAll("article.message-row.user"));
      rows.forEach((row) => {
        const bodyRow = row.querySelector(".message-body-row");
        const body = row.querySelector(".md-body");
        const toggle = row.querySelector(".user-collapse-toggle");
        if (!bodyRow || !body || !toggle) return;
        const style = getComputedStyle(body);
        const lineHeight = Number.parseFloat(style.lineHeight);
        const paddingTop = Number.parseFloat(style.paddingTop) || 0;
        const paddingBottom = Number.parseFloat(style.paddingBottom) || 0;
        const maxHeight = Number.isFinite(lineHeight)
          ? Math.ceil((lineHeight * 10) + paddingTop + paddingBottom)
          : 245;
        bodyRow.style.setProperty("--user-collapse-max-height", `${maxHeight}px`);
        const bodyWidth = Math.round(body.getBoundingClientRect().width || bodyRow.clientWidth || 0);
        if (bodyWidth < 40) {
          row.classList.remove("is-collapsible");
          bodyRow.classList.remove("is-collapsed");
          toggle.classList.remove("is-visible");
          toggle.hidden = true;
          const retries = Math.max(0, parseInt(row.dataset.collapseRetry || "0", 10) || 0);
          if (retries < 3) {
            row.dataset.collapseRetry = String(retries + 1);
            requestAnimationFrame(() => requestAnimationFrame(() => syncUserMessageCollapse(row)));
          } else {
            row.dataset.collapseRetry = "0";
          }
          return;
        }
        row.dataset.collapseRetry = "0";
        let shouldCollapse = body.scrollHeight > (maxHeight + 4);
        const bodyText = String(body.textContent || "").trim();
        const hasHardBreak = bodyText.includes("\n") || !!body.querySelector("br");
        const hasStructuredBlocks = !!body.querySelector("pre, table, ul, ol, blockquote, img, video, iframe, details");
        if (shouldCollapse && bodyText.length <= 140 && !hasHardBreak && !hasStructuredBlocks) {
          shouldCollapse = false;
        }
        const msgId = row.dataset.msgid || "";
        const isExpanded = shouldCollapse && msgId && expandedUserMessages.has(msgId);
        row.classList.toggle("is-collapsible", shouldCollapse);
        bodyRow.classList.toggle("is-collapsed", shouldCollapse && !isExpanded);
        const showMoreBtn = shouldCollapse && !isExpanded;
        toggle.classList.toggle("is-visible", showMoreBtn);
        toggle.hidden = !showMoreBtn;
        toggle.textContent = "More";
        if (userCollapseScrollObserver) {
          if (isExpanded && shouldCollapse && msgId) {
            userCollapseScrollObserver.observe(row);
          } else {
            try {
              userCollapseScrollObserver.unobserve(row);
            } catch (_) { }
          }
        }
      });
    };
    const syncPaneViewerTabThinkingStatuses = () => {
      const tabsRoot = document.getElementById("paneViewerTabs");
      if (tabsRoot) {
        tabsRoot.querySelectorAll(".pane-viewer-tab").forEach((tab) => {
          const a = tab.dataset.agent;
          if (!a) return;
          tab.classList.toggle("pane-viewer-tab-thinking", currentAgentStatuses[a] === "running");
        });
      }
    };
    let lastHubRunningStateSig = "";
    const notifyHubRunningState = () => {
      if (window.parent === window) return;
      const sessionName = String(currentSessionName || "").trim();
      if (!sessionName) return;
      const runningAgents = Object.keys(currentAgentStatuses || {}).filter((agent) => currentAgentStatuses[agent] === "running");
      const isRunning = runningAgents.length > 0;
      const sig = `${sessionName}|${isRunning ? "1" : "0"}|${runningAgents.join(",")}`;
      if (sig === lastHubRunningStateSig) return;
      lastHubRunningStateSig = sig;
      try {
        window.parent.postMessage({
          type: "multiagent-session-running-state",
          sessionName,
          isRunning,
          runningAgents,
        }, "*");
      } catch (_) { }
    };
    const renderAgentStatus = (statuses) => {
      currentAgentStatuses = { ...statuses };
      syncPaneViewerTabThinkingStatuses();
      renderThinkingIndicator();
      notifyHubRunningState();
    };
    const refreshSessionState = async () => {
      if (sessionStateInFlight) {
        pendingSessionStateRefresh = true;
        return;
      }
      sessionStateInFlight = true;
      try {
        const res = await fetchWithTimeout(`/session-state?ts=${Date.now()}`, {}, 4000);
        if (res.ok) applySessionState(await res.json());
      } catch (_) {
      } finally {
        sessionStateInFlight = false;
        if (pendingSessionStateRefresh) {
          pendingSessionStateRefresh = false;
          queueMicrotask(() => { void refreshSessionState(); });
        }
      }
    };
    const hoverCapabilityMedia = window.matchMedia("(hover: hover) and (pointer: fine)");
    const canUseHoverInteractions = () => hoverCapabilityMedia.matches;
    const touchBlurSelector = [
      ".quick-action",
      ".hub-page-menu-btn",
      ".composer-plus-toggle",
      ".target-chip",
      ".copy-btn",
      ".file-card",
      ".file-modal-close",
      ".send-btn",
      "#scrollToBottomBtn"
    ].join(", ");
    const syncHoverCapabilityClass = () => {
      document.documentElement.classList.toggle("has-hover", canUseHoverInteractions());
    };
    const blurTouchControlAfterTap = (event) => {
      if (canUseHoverInteractions()) return;
      const control = event.target?.closest?.(touchBlurSelector);
      if (!control) return;
      setTimeout(() => {
        if (typeof control.blur === "function") control.blur();
        const active = document.activeElement;
        if (active && active.matches?.(touchBlurSelector) && typeof active.blur === "function") {
          active.blur();
        }
      }, 0);
    };
    syncHoverCapabilityClass();
    if (hoverCapabilityMedia.addEventListener) {
      hoverCapabilityMedia.addEventListener("change", syncHoverCapabilityClass);
    } else if (hoverCapabilityMedia.addListener) {
      hoverCapabilityMedia.addListener(syncHoverCapabilityClass);
    }
    // Sound
    const setSoundBtn = (on) => {
      soundEnabled = !!on;
    };
    setSoundBtn(soundEnabled);

    // Safari safe area layout hack
    const _safariDummy = document.createElement("div");
    _safariDummy.style.cssText = "position:absolute;bottom:0;width:100%;height:env(safe-area-inset-bottom);pointer-events:none;opacity:0;z-index:-1;";
    document.body.appendChild(_safariDummy);

    const syncChatNotificationDefaults = async () => {
      try {
        const res = await fetch("/hub-settings", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (typeof data?.agent_font_mode === "string" && data.agent_font_mode) {
          document.documentElement.dataset.agentFontMode = data.agent_font_mode;
        }
        if (typeof data?.chat_font_settings_css === "string") {
          const styleNode = document.getElementById("chatFontSettingsStyle");
          if (styleNode && styleNode.textContent !== data.chat_font_settings_css) {
            styleNode.textContent = data.chat_font_settings_css;
          }
        }
        if (typeof data?.chat_sound === "boolean") {
          setSoundBtn(data.chat_sound);
        }
      } catch (_) { }
    };
    syncChatNotificationDefaults();
    setInterval(syncChatNotificationDefaults, 30000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) syncChatNotificationDefaults();
    });

    // Auto-prime on first user gesture if sound is on
    const primeSoundOnGesture = async () => {
      if (_audioPrimed) return;
      await primeSound();
    };
    document.addEventListener("pointerdown", (e) => {
      const toggle = e.target.closest(".hub-page-menu-btn, .composer-plus-toggle, .quick-action");
      if (toggle) {
        if (toggle.classList.contains("animating")) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        flashHeaderToggle(toggle);
      }
    });
    document.addEventListener("click", primeSoundOnGesture);
    document.addEventListener("click", blurTouchControlAfterTap, true);
    // Delegated handler for code block copy buttons
    const codeCopySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    const codeCheckSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    document.addEventListener("click", (e) => {
      const btn = e.target.closest(".code-copy-btn");
      if (!btn) return;
      const wrap = btn.closest(".code-block-wrap");
      if (!wrap) return;
      const code = wrap.querySelector("code") || wrap.querySelector("pre");
      navigator.clipboard.writeText(code.textContent).then(() => {
        btn.innerHTML = codeCheckSvg;
        setTimeout(() => { btn.innerHTML = codeCopySvg; }, 1500);
      });
    });
    /** Strip ANSI escapes (fallback when ansi_up is unavailable). */
    const stripAnsiForTrace = (value) => String(value ?? "")
      .replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, "")
      .replace(/\u001b\][^\u0007]*\u0007/g, "");
    let paneTraceAnsiUp = null;
    let paneTraceAnsiLoadPromise = null;
    const ensurePaneTraceAnsiUp = async () => {
      if (paneTraceAnsiUp) return true;
      try {
        if (typeof AnsiUp === "function") {
          paneTraceAnsiUp = new AnsiUp();
          return true;
        }
      } catch (_) {
        paneTraceAnsiUp = null;
      }
      if (paneTraceAnsiLoadPromise) return paneTraceAnsiLoadPromise;
      paneTraceAnsiLoadPromise = loadExternalScriptOnce(ANSI_UP_SRC).then((ready) => {
        if (!ready) return false;
        try {
          if (typeof AnsiUp === "function") paneTraceAnsiUp = new AnsiUp();
        } catch (_) {
          paneTraceAnsiUp = null;
        }
        return !!paneTraceAnsiUp;
      }).finally(() => {
        if (!paneTraceAnsiUp) paneTraceAnsiLoadPromise = null;
      });
      return paneTraceAnsiLoadPromise;
    };
    const paneTraceHtml = (raw) => {
      const text = String(raw ?? "No output");
      if (!paneTraceAnsiUp) {
        try {
          if (typeof AnsiUp === "function") paneTraceAnsiUp = new AnsiUp();
        } catch (_) {
          paneTraceAnsiUp = null;
        }
      }
      let html;
      if (paneTraceAnsiUp) {
        try {
          html = paneTraceAnsiUp.ansi_to_html(text);
        } catch (_) {
          html = null;
        }
      }
      if (!html) {
        const plain = stripAnsiForTrace(text);
        html = escapeHtml(plain).replace(/\n/g, "<br>");
      }
      return html.replace(/[●⏺]/g, '<span class="trace-dot">●</span>');
    };

    // Mobile Pane Viewer（ハンバーガーパネル内の第2層）
    let paneViewerAgents = [];
    let paneViewerLastAgent = null;
    let paneViewerContentCache = Object.create(null);
    const paneViewerEl = document.getElementById("paneViewer");
    const paneViewerTabs = document.getElementById("paneViewerTabs");
    const paneViewerCarousel = document.getElementById("paneViewerCarousel");
    const scrollPaneSlideToBottom = (slide) => {
      if (!slide) return;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          slide.scrollTop = slide.scrollHeight;
        });
      });
    };
    const _paneSlideAtBottom = (el) => !el || el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    const fetchPaneViewerSlide = async (agent, slide, scrollToBottomAfter) => {
      if (!slide) return;
      if (!paneViewerEl?.classList?.contains("visible")) return;
      if (document.hidden) return;
      const body = slide.querySelector(".pane-viewer-body");
      if (!body) return;
      if (!scrollToBottomAfter && !_paneSlideAtBottom(body)) return;
      try {
        /* Pane Viewer はモバイル専用導線（Terminal ボタンはデスクトップでは /open-terminal）。常に軽量 tail。 */
        const ansiReady = ensurePaneTraceAnsiUp();
        const res = await fetch(`/trace?agent=${encodeURIComponent(agent)}&lines=160&ts=${Date.now()}`);
        if (!res.ok) return;
        const data = await res.json();
        if (!paneViewerEl?.classList?.contains("visible")) return;
        if (document.hidden) return;
        const content = String(data.content || "");
        const atBottom = _paneSlideAtBottom(body);
        const cacheKey = `${agent}`;
        if (!scrollToBottomAfter && paneViewerContentCache[cacheKey] === content) {
          return;
        }
        paneViewerContentCache[cacheKey] = content;
        await ansiReady;
        body.classList.remove("inline-loading-pane");
        body.innerHTML = paneTraceHtml(content || "No output");
        if (scrollToBottomAfter || atBottom) scrollPaneSlideToBottom(body);
      } catch (_) { }
    };
    const fetchPaneViewerSlideByIndex = (idx, scrollToBottomAfter = false) => {
      if (!paneViewerCarousel || !paneViewerAgents.length) return;
      const i = Math.max(0, Math.min(paneViewerAgents.length - 1, idx));
      const agent = paneViewerAgents[i];
      const slide = paneViewerCarousel.children[i];
      if (agent && slide) fetchPaneViewerSlide(agent, slide, scrollToBottomAfter);
    };
    /* カルーセルの見えているタブだけポーリング（全エージェント並列 /trace しない）。 */
    const fetchVisiblePaneViewerSlide = (scrollToBottomAfter = false) => {
      if (!paneViewerEl?.classList?.contains("visible")) return;
      if (document.hidden) return;
      if (!paneViewerCarousel || !paneViewerAgents.length) return;
      const width = paneViewerCarousel.offsetWidth;
      if (!width) {
        fetchPaneViewerSlideByIndex(lastPaneViewerTabIdx, scrollToBottomAfter);
        return;
      }
      const scrollLeft = paneViewerCarousel.scrollLeft;
      let idx = Math.round(scrollLeft / width);
      if (!Number.isFinite(idx)) idx = 0;
      idx = Math.max(0, Math.min(paneViewerAgents.length - 1, idx));
      fetchPaneViewerSlideByIndex(idx, scrollToBottomAfter);
    };
    function movePaneViewerIndicator(idx, { scrollTabIntoView = false } = {}) {
      const indicator = paneViewerTabs.querySelector(".pane-viewer-tab-indicator");
      const tabs = Array.from(paneViewerTabs.querySelectorAll(".pane-viewer-tab"));
      if (!indicator || !tabs.length) return;
      const safeIdx = Math.max(0, Math.min(tabs.length - 1, idx));
      const tab = tabs[safeIdx];
      indicator.style.left = tab.offsetLeft + "px";
      indicator.style.width = tab.offsetWidth + "px";
      if (scrollTabIntoView && tab) {
        tab.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
      }
    }
    const syncPaneViewerTab = () => {
      if (!paneViewerCarousel || !paneViewerAgents.length) return;
      const width = paneViewerCarousel.offsetWidth;
      if (!width) return;
      const scrollLeft = paneViewerCarousel.scrollLeft;
      let idx = Math.round(scrollLeft / width);
      if (!Number.isFinite(idx)) idx = 0;
      idx = Math.max(0, Math.min(paneViewerAgents.length - 1, idx));
      lastPaneViewerTabIdx = idx;
      paneViewerLastAgent = paneViewerAgents[idx];
      const tabs = Array.from(paneViewerTabs.querySelectorAll(".pane-viewer-tab"));
      tabs.forEach((t, i) => t.classList.toggle("active", i === idx));
      movePaneViewerIndicator(idx);
    };
    const onPaneViewerCarouselScroll = () => {
      if (!paneViewerTabScrollRaf) {
        paneViewerTabScrollRaf = requestAnimationFrame(() => {
          paneViewerTabScrollRaf = 0;
          syncPaneViewerTab();
        });
      }
      if (paneViewerTabScrollEndTimer) clearTimeout(paneViewerTabScrollEndTimer);
      paneViewerTabScrollEndTimer = setTimeout(() => {
        paneViewerTabScrollEndTimer = null;
        movePaneViewerIndicator(lastPaneViewerTabIdx, { scrollTabIntoView: true });
        fetchVisiblePaneViewerSlide(false);
      }, 120);
    };
    const schedulePaneViewerScrollAlign = () => {
      let tries = 0;
      const run = () => {
        if (!paneViewerCarousel || !paneViewerAgents.length) return;
        const w = paneViewerCarousel.offsetWidth;
        if (!w) {
          if (++tries > 48) return;
          requestAnimationFrame(run);
          return;
        }
        const agent = paneViewerLastAgent && paneViewerAgents.includes(paneViewerLastAgent)
          ? paneViewerLastAgent
          : paneViewerAgents[0];
        const idx = Math.max(0, paneViewerAgents.indexOf(agent));
        paneViewerCarousel.scrollTo({ left: idx * w, behavior: "auto" });
        syncPaneViewerTab();
        requestAnimationFrame(() => {
          movePaneViewerIndicator(lastPaneViewerTabIdx, { scrollTabIntoView: true });
        });
      };
      requestAnimationFrame(() => requestAnimationFrame(run));
    };
    const scrollToAgent = (agent) => {
      const idx = paneViewerAgents.indexOf(agent);
      if (idx < 0) return;
      lastPaneViewerTabIdx = idx;
      paneViewerLastAgent = agent;
      paneViewerCarousel.scrollTo({ left: idx * paneViewerCarousel.offsetWidth, behavior: "smooth" });
      const tabs = Array.from(paneViewerTabs.querySelectorAll(".pane-viewer-tab"));
      tabs.forEach((t, i) => t.classList.toggle("active", i === idx));
      movePaneViewerIndicator(idx, { scrollTabIntoView: true });
      fetchPaneViewerSlideByIndex(idx, true);
    };
    const buildPaneViewer = () => {
      paneViewerAgents = availableTargets.filter(t => t !== "others");
      const restoreAgent = paneViewerLastAgent && paneViewerAgents.includes(paneViewerLastAgent)
        ? paneViewerLastAgent
        : paneViewerAgents[0];
      const initialIdx = restoreAgent ? Math.max(0, paneViewerAgents.indexOf(restoreAgent)) : 0;
      paneViewerTabs.innerHTML = `<div class="pane-viewer-tab-indicator"></div>` + paneViewerAgents.map((a, i) =>
        `<button class="pane-viewer-tab${i === initialIdx ? " active" : ""}" data-agent="${escapeHtml(a)}" title="${escapeHtml(a)}" aria-label="${escapeHtml(a)}" style="--agent-pulse-delay:${agentPulseOffset(a)}s">${paneViewerTabIconHtml(a)}</button>`
      ).join("");
      paneViewerCarousel.innerHTML = paneViewerAgents.map(a =>
        `<div class="pane-viewer-slide" data-agent="${escapeHtml(a)}"><div class="pane-viewer-header-shadow"></div><div class="pane-viewer-body inline-loading-pane">${loadingIndicatorHtml("Loading…")}</div></div>`
      ).join("");
      paneViewerTabs.querySelectorAll(".pane-viewer-tab").forEach(tab => {
        tab.addEventListener("click", () => scrollToAgent(tab.dataset.agent));
      });
      if (paneViewerCarousel && !paneViewerCarousel._paneViewerScrollBound) {
        paneViewerCarousel._paneViewerScrollBound = true;
        paneViewerCarousel.addEventListener("scroll", onPaneViewerCarouselScroll, { passive: true });
      }
      syncPaneViewerTabThinkingStatuses();
      lastPaneViewerTabIdx = initialIdx;
      requestAnimationFrame(() => {
        movePaneViewerIndicator(initialIdx);
        const firstTab = paneViewerTabs.querySelector(".pane-viewer-tab.active");
        if (firstTab) firstTab.scrollIntoView({ inline: "center", block: "nearest" });
      });
    };
    const resolvePaneFocusAgent = (raw) => {
      if (!raw) return null;
      const allowed = availableTargets.filter(t => t !== "others");
      if (!allowed.length) return null;
      if (allowed.includes(raw)) return raw;
      const base = agentBaseName(raw);
      const hit = allowed.find((t) => t === base || agentBaseName(t) === base);
      return hit || null;
    };
    const showPaneTraceViewer = (focusAgent) => {
      if (!paneViewerEl) return;
      const resolved = resolvePaneFocusAgent(focusAgent);
      if (resolved) paneViewerLastAgent = resolved;
      if (paneTracePanel.classList.contains("open")) {
        if (resolved && paneViewerAgents.includes(resolved)) {
          scrollToAgent(resolved);
        }
        return;
      }
      closeGitBranchSheet({ immediate: true });
      closeAttachedFilesSheet({ immediate: true });

      // Close hamburger menu if open
      rightMenuPanel?.classList.remove("open");
      if (rightMenuPanel) rightMenuPanel.hidden = true;
      rightMenuBtn?.classList.remove("open");
      paneViewerEl.classList.remove("visible");
      paneViewerEl.hidden = true;

      openPaneTraceSheet(() => {
        paneViewerEl.hidden = false;
        paneViewerEl.classList.add("visible");
        paneViewerContentCache = Object.create(null);
        syncHeaderMenuFocus();
        clearPaneViewerOpenWork();
        paneViewerOpenRaf = requestAnimationFrame(() => {
          paneViewerOpenRaf = 0;
          buildPaneViewer();
          schedulePaneViewerScrollAlign();
          paneViewerInitialFetchTimer = setTimeout(() => {
            paneViewerInitialFetchTimer = 0;
            fetchPaneViewerSlideByIndex(lastPaneViewerTabIdx, true);
            /* LAN/Local は少し落として CPU を抑える。Public は従来どおり。 */
            const paneTracePollMs = isLocalHubHostname() ? 300 : 1500;
            if (paneViewerInterval) clearInterval(paneViewerInterval);
            paneViewerInterval = setInterval(() => fetchVisiblePaneViewerSlide(false), paneTracePollMs);
          }, 24);
        });
      });
    };
    const togglePaneViewer = () => {
      if (!paneViewerEl) return;
      if (paneTracePanel.classList.contains("open")) {
        exitPaneTraceMode();
        return;
      }
      showPaneTraceViewer(null);
    };
    const msgThinking = document.getElementById("messages");
    if (msgThinking) {
      msgThinking.addEventListener("touchstart", (e) => {
        const row = e.target.closest(".message-thinking-row");
        const providerEventsMsgId = row?.dataset?.providerEvents || "";
        if (!row || (!row.dataset.agent && !providerEventsMsgId)) {
          _thinkingRowTouch = null;
          return;
        }
        const t = e.touches && e.touches[0];
        if (!t) {
          _thinkingRowTouch = null;
          return;
        }
        _thinkingRowTouch = {
          agent: row.dataset.agent || "",
          providerEvents: providerEventsMsgId,
          x: t.clientX,
          y: t.clientY,
        };
      }, { passive: true });
      msgThinking.addEventListener("touchend", (e) => {
        if (!_thinkingRowTouch) return;
        const start = _thinkingRowTouch;
        _thinkingRowTouch = null;
        const row = e.target.closest(".message-thinking-row");
        if (!row) return;
        if ((row.dataset.providerEvents || "") !== (start.providerEvents || "")) {
          if ((row.dataset.agent || "") !== (start.agent || "")) return;
        }
        const t = e.changedTouches && e.changedTouches[0];
        if (!t) return;
        const dx = t.clientX - start.x;
        const dy = t.clientY - start.y;
        if (dx * dx + dy * dy > 100) return;
        const now = Date.now();
        if (now - _lastThinkingPaneMs < 400) return;
        _lastThinkingPaneMs = now;
        _ignoreGlobalClick = true;
        e.preventDefault();
        if (start.providerEvents) {
          void showProviderEventsModal(start.providerEvents);
        } else if (start.agent) {
          showPaneTraceViewer(start.agent);
        }
      }, { passive: false });
      msgThinking.addEventListener("touchcancel", () => {
        _thinkingRowTouch = null;
      }, { passive: true });
    }
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) return;
      if (!paneViewerEl?.classList?.contains("visible")) return;
      fetchVisiblePaneViewerSlide(false);
    });
    refreshSessionState();
    setInterval(refreshSessionState, 1500);
    setInterval(() => {
      if (Object.keys(currentAgentStatuses).length) {
        renderAgentStatus(currentAgentStatuses);
      }
    }, 1000);

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
