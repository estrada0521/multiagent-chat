    const fileModal = document.getElementById("fileModal");
    const fileModalFrame = document.getElementById("fileModalFrame");
    const fileModalSplitResizer = document.getElementById("fileModalSplitResizer");
    const fileModalTitle = document.getElementById("fileModalTitle");
    const fileModalIcon = document.getElementById("fileModalIcon");
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
    let currentBoldModeMobile = false;
    let currentBoldModeDesktop = false;
    let openFilesDirectInExternalEditor = false;
    let _desktopFilePaneWidthPx = 0;
    let _fileModalResizeState = null;
    let _fileModalRestoreAttemptedSession = "";
    let _fileModalRestoreInFlightSession = "";
    let _fileModalScrollBridgeCleanup = null;
    let _fileModalViewportMetricsRaf = 0;
    let lastFocusedElement = null;
    const _fileExistenceCache = new Map();
    const FILE_MODAL_PANE_WIDTH_KEY = "multiagent_file_pane_width_px";
    const FILE_MODAL_STATE_KEY_PREFIX = "multiagent_file_pane_state_v1:";
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
      } catch (_) {}
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
      } catch (_) {}
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
      } catch (_) {}
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
      } catch (_) {}
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
    const syncFileModalShellTheme = () => {
      if (!fileModal) return;
      const useLightShell = fileModalCurrentExt === "md" && fileModalPreviewTheme === "light";
      fileModal.classList.toggle("theme-light", useLightShell);
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
    const getDesktopRightPanelReservedWidthPx = () => {
      const raw = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--desktop-right-panel-reserved-width"));
      return Number.isFinite(raw) ? Math.max(0, Math.round(raw)) : 0;
    };
    const clampDesktopFilePaneWidthPx = (value) => {
      const viewportWidth = Math.max(0, window.innerWidth || 0);
      const reservedRight = getDesktopRightPanelReservedWidthPx();
      const availableWidth = Math.max(0, viewportWidth - reservedRight);
      const minWidth = 300;
      const maxWidth = Math.max(minWidth, Math.min(860, availableWidth - 360));
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return Math.max(minWidth, Math.min(560, Math.round(availableWidth * 0.38)));
      }
      return Math.max(minWidth, Math.min(maxWidth, Math.round(numeric)));
    };
    try {
      const storedWidth = Number.parseInt(window.localStorage?.getItem(FILE_MODAL_PANE_WIDTH_KEY) || "", 10);
      if (Number.isFinite(storedWidth) && storedWidth > 0) {
        _desktopFilePaneWidthPx = storedWidth;
      }
    } catch (_) {}
    const getDesktopFilePaneWidthPx = () => clampDesktopFilePaneWidthPx(_desktopFilePaneWidthPx || Math.round((window.innerWidth || 0) * 0.34));
    const persistDesktopFilePaneWidthPx = () => {
      try {
        if (_desktopFilePaneWidthPx > 0) {
          window.localStorage?.setItem(FILE_MODAL_PANE_WIDTH_KEY, String(_desktopFilePaneWidthPx));
        }
      } catch (_) {}
    };
    const applyDesktopFilePaneWidthPx = (value, { persist = false } = {}) => {
      _desktopFilePaneWidthPx = clampDesktopFilePaneWidthPx(value);
      document.documentElement.style.setProperty("--desktop-file-pane-width", `${_desktopFilePaneWidthPx}px`);
      if (persist) persistDesktopFilePaneWidthPx();
      return _desktopFilePaneWidthPx;
    };
    const shouldUseDesktopFilePane = () => (window.innerWidth || 0) >= DESKTOP_FILE_PANE_MIN_VIEWPORT_PX;
    const syncFileModalLayoutMode = () => {
      const useDesktopPane = !fileModal.hidden && shouldUseDesktopFilePane();
      const paneWidth = useDesktopPane ? applyDesktopFilePaneWidthPx(getDesktopFilePaneWidthPx()) : 0;
      document.body.classList.toggle("file-modal-desktop-split", useDesktopPane);
      document.documentElement.style.setProperty("--desktop-file-pane-width", `${paneWidth}px`);
      return { useDesktopPane, paneWidth };
    };
    const updateFileModalViewportMetrics = () => {
      const { useDesktopPane, paneWidth } = syncFileModalLayoutMode();
      if (useDesktopPane) {
        const rightReserved = getDesktopRightPanelReservedWidthPx();
        fileModal.style.setProperty("--file-modal-top", "0px");
        fileModal.style.setProperty("--file-modal-left", `${Math.max(0, (window.innerWidth || 0) - rightReserved - paneWidth)}px`);
        fileModal.style.setProperty("--file-modal-width", `${paneWidth}px`);
        return;
      }
      const headerRoot = document.querySelector(".hub-page-header");
      if (!headerRoot) return;
      const rect = headerRoot.getBoundingClientRect();
      const top = Math.max(0, Math.round(rect.bottom));
      const left = Math.max(0, Math.round(rect.left));
      const width = Math.max(0, Math.round(rect.width));
      fileModal.style.setProperty("--file-modal-top", `${top}px`);
      fileModal.style.setProperty("--file-modal-left", `${left}px`);
      fileModal.style.setProperty("--file-modal-width", `${width}px`);
    };
    const syncFileModalViewportMetrics = () => {
      if (fileModal.hidden) return;
      updateFileModalViewportMetrics();
    };
    const scheduleFileModalViewportMetrics = () => {
      if (fileModal.hidden) return;
      if (_fileModalViewportMetricsRaf) {
        cancelAnimationFrame(_fileModalViewportMetricsRaf);
      }
      _fileModalViewportMetricsRaf = requestAnimationFrame(() => {
        _fileModalViewportMetricsRaf = 0;
        if (fileModal.hidden) return;
        updateFileModalViewportMetrics();
      });
    };
    const resetFileModalPreviewMetrics = () => {
      if (!fileModal) return;
      fileModal.style.setProperty("--file-modal-preview-gutter-width", "0px");
      fileModal.style.setProperty("--file-modal-preview-title-offset", "0px");
      fileModal.style.removeProperty("--file-modal-preview-gutter-bg");
      fileModal.style.removeProperty("--file-modal-preview-gutter-divider");
      fileModal.classList.remove("has-preview-gutter");
    };
    const syncFileModalPreviewMetrics = () => {
      if (!fileModal || fileModal.hidden) return;
      let frameWindow = null;
      let frameDoc = null;
      try {
        frameWindow = fileModalFrame.contentWindow || null;
        frameDoc = fileModalFrame.contentDocument || frameWindow?.document || null;
      } catch (_) {
        resetFileModalPreviewMetrics();
        return;
      }
      const root = frameDoc?.documentElement || null;
      if (!root) {
        resetFileModalPreviewMetrics();
        return;
      }
      const gutterWidthRaw = Number.parseFloat(root.dataset.previewGutterWidth || "0");
      const titleOffsetRaw = Number.parseFloat(root.dataset.previewTitleOffset || "0");
      const gutterWidth = Number.isFinite(gutterWidthRaw) ? Math.max(0, Math.round(gutterWidthRaw)) : 0;
      const titleOffset = Number.isFinite(titleOffsetRaw) ? Math.max(0, Math.round(titleOffsetRaw)) : 0;
      fileModal.style.setProperty("--file-modal-preview-gutter-width", `${gutterWidth}px`);
      fileModal.style.setProperty("--file-modal-preview-title-offset", `${titleOffset}px`);
      const gutterBg = String(root.dataset.previewGutterBg || "").trim();
      const gutterDivider = String(root.dataset.previewGutterDivider || "").trim();
      if (gutterBg) fileModal.style.setProperty("--file-modal-preview-gutter-bg", gutterBg);
      else fileModal.style.removeProperty("--file-modal-preview-gutter-bg");
      if (gutterDivider) fileModal.style.setProperty("--file-modal-preview-gutter-divider", gutterDivider);
      else fileModal.style.removeProperty("--file-modal-preview-gutter-divider");
      fileModal.classList.toggle("has-preview-gutter", gutterWidth > 0);
    };
    const clearFileModalScrollBridge = ({ resetChrome = true } = {}) => {
      if (typeof _fileModalScrollBridgeCleanup === "function") {
        try {
          _fileModalScrollBridgeCleanup();
        } catch (_) {}
      }
      if (_fileModalViewportMetricsRaf) {
        cancelAnimationFrame(_fileModalViewportMetricsRaf);
        _fileModalViewportMetricsRaf = 0;
      }
      _fileModalScrollBridgeCleanup = null;
      if (resetChrome) fileModal.classList.remove("file-modal-chrome-hidden");
    };
    const bindFileModalScrollBridge = () => {
      clearFileModalScrollBridge({ resetChrome: false });
      fileModal.classList.remove("file-modal-chrome-hidden");
    };
    const closeFileModal = ({ restoreFocus = true } = {}) => {
      if (fileModal.hidden) return;
      clearFileModalScrollBridge();
      clearFileModalSessionState();
      const focusTarget = restoreFocus ? lastFocusedElement : null;
      fileModal.classList.remove("visible");
      fileModal.classList.add("closing");
      document.body.classList.remove("file-modal-open");
      document.body.classList.remove("file-modal-desktop-split");
      document.body.classList.remove("file-modal-resizing");
      document.documentElement.style.setProperty("--desktop-file-pane-width", "0px");
      _fileModalResizeState = null;
      syncHeaderMenuFocus();
      setTimeout(() => {
        fileModal.hidden = true;
        fileModal.classList.remove("closing");
        fileModalFrame.removeAttribute("src");
        fileModalCurrentPath = "";
        fileModalCurrentExt = "";
        fileModalPreviewTheme = "dark";
        fileModalHtmlPreviewMode = "text";
        fileModal.classList.remove("theme-light");
        resetFileModalPreviewMetrics();
        syncFileModalThemeToggle();
        syncFileModalHtmlModeToggle();
        if (fileModalOpenEditorBtn) fileModalOpenEditorBtn.hidden = true;
        window.removeEventListener("resize", syncFileModalViewportMetrics);
        window.removeEventListener("scroll", syncFileModalViewportMetrics, { capture: true });
        if (focusTarget && typeof focusTarget.focus === "function") {
          focusTarget.focus({ preventScroll: true });
        }
        lastFocusedElement = null;
      }, 300);
    };
    const setFileModalEnterOffset = (sourceEl, triggerEvent) => {
      let originX = window.innerWidth / 2;
      let originY = window.innerHeight / 2;
      if (triggerEvent && typeof triggerEvent.clientX === "number" && typeof triggerEvent.clientY === "number") {
        originX = triggerEvent.clientX;
        originY = triggerEvent.clientY;
      } else if (sourceEl && typeof sourceEl.getBoundingClientRect === "function") {
        const rect = sourceEl.getBoundingClientRect();
        originX = rect.left + rect.width / 2;
        originY = rect.top + rect.height / 2;
      }
      const offsetX = Math.round(originX - window.innerWidth / 2);
      const offsetY = Math.round(originY - window.innerHeight / 2);
      fileModal.style.setProperty("--file-modal-enter-x", `${offsetX}px`);
      fileModal.style.setProperty("--file-modal-enter-y", `${offsetY}px`);
    };
    const openFileModal = (path, ext, sourceEl, triggerEvent) => {
      const normalizedExt = (ext || "").toLowerCase();
      const filename = (displayAttachmentFilename(path) || path || "Preview").trim();
      const viewerUrl = fileViewHrefForPath(path, { embed: true });
      fileModalCurrentPath = path;
      fileModalCurrentExt = normalizedExt;
      fileModalPreviewTheme = "dark";
      fileModalHtmlPreviewMode = "text";
      clearFileModalScrollBridge();
      fileModal.classList.remove("file-modal-chrome-hidden");
      resetFileModalPreviewMetrics();
      syncFileModalThemeToggle();
      syncFileModalHtmlModeToggle();
      syncFileModalShellTheme();
      fileModalTitle.textContent = filename;
      fileModalIcon.innerHTML = FILE_ICONS[normalizedExt] || FILE_SVG_ICONS.file;
      lastFocusedElement = sourceEl || document.activeElement;
      setFileModalEnterOffset(sourceEl, triggerEvent);
      if (fileModalOpenEditorBtn) {
        fileModalOpenEditorBtn.hidden = true;
        fetch(`/file-openability?path=${encodeURIComponent(path)}`)
          .then((res) => res.ok ? res.json() : null)
          .then((data) => {
            if (fileModalCurrentPath !== path || !fileModalOpenEditorBtn) return;
            fileModalOpenEditorBtn.hidden = !(data && data.editable);
          })
          .catch(() => {});
      }
      
      // Prevent white flash by hiding iframe until it loads
      fileModalFrame.style.opacity = "0";
      fileModalFrame.onload = () => {
        fileModalFrame.style.transition = "opacity 200ms ease-out";
        fileModalFrame.style.opacity = "1";
        syncFileModalPreviewMetrics();
        postFileModalTheme();
        postFileModalHtmlPreviewMode();
        bindFileModalScrollBridge();
        setTimeout(() => {
          syncFileModalPreviewMetrics();
          bindFileModalScrollBridge();
        }, 120);
      };
      fileModalFrame.src = viewerUrl;

      fileModal.hidden = false;
      updateFileModalViewportMetrics();
      fileModal.classList.add("visible");
      document.body.classList.add("file-modal-open");
      document.querySelector(".hub-page-header")?.classList.remove("header-hidden");
      syncHeaderMenuFocus();
      saveFileModalSessionState();
      window.addEventListener("resize", syncFileModalViewportMetrics);
      window.addEventListener("scroll", syncFileModalViewportMetrics, { passive: true, capture: true });
    };
    const extFromPath = (path) => {
      const cleanPath = String(path || "").split(/[?#]/, 1)[0];
      const filename = cleanPath.split("/").pop() || "";
      if (!filename.includes(".")) return "";
      return filename.split(".").pop().toLowerCase();
    };
    function fileModalStateStorageKey(session = currentSessionName) {
      const name = String(session || "").trim();
      return name ? `${FILE_MODAL_STATE_KEY_PREFIX}${name}` : "";
    }
    function loadFileModalSessionState(session = currentSessionName) {
      const key = fileModalStateStorageKey(session);
      if (!key) return null;
      try {
        const raw = window.localStorage?.getItem(key);
        if (!raw) return null;
        const data = JSON.parse(raw);
        const path = String(data?.path || "").trim();
        if (!path) return null;
        return {
          path,
          ext: String(data?.ext || extFromPath(path)).trim().toLowerCase(),
          theme: data?.theme === "light" ? "light" : "dark",
          mode: data?.mode === "text" ? "text" : "web",
        };
      } catch (_) {
        return null;
      }
    }
    function clearFileModalSessionState(session = currentSessionName) {
      const key = fileModalStateStorageKey(session);
      if (!key) return;
      try {
        window.localStorage?.removeItem(key);
      } catch (_) {}
    }
    function saveFileModalSessionState(session = currentSessionName) {
      const key = fileModalStateStorageKey(session);
      if (!key) return;
      if (!fileModalCurrentPath || !(document.body.classList.contains("file-modal-open") || !fileModal.hidden) || !shouldUseDesktopFilePane()) {
        clearFileModalSessionState(session);
        return;
      }
      const payload = {
        path: fileModalCurrentPath,
        ext: String(fileModalCurrentExt || extFromPath(fileModalCurrentPath) || "").trim().toLowerCase(),
        theme: fileModalPreviewTheme === "light" ? "light" : "dark",
        mode: fileModalHtmlPreviewMode === "text" ? "text" : "web",
      };
      try {
        window.localStorage?.setItem(key, JSON.stringify(payload));
      } catch (_) {}
    }
    async function maybeRestoreFileModalSessionState(session = currentSessionName) {
      const sessionName = String(session || "").trim();
      if (openFilesDirectInExternalEditor) return false;
      if (!sessionName || !shouldUseDesktopFilePane() || !fileModal.hidden || fileModalCurrentPath) return false;
      if (_fileModalRestoreAttemptedSession === sessionName || _fileModalRestoreInFlightSession === sessionName) return false;
      _fileModalRestoreAttemptedSession = sessionName;
      const stored = loadFileModalSessionState(sessionName);
      if (!stored?.path) return false;
      _fileModalRestoreInFlightSession = sessionName;
      try {
        const exists = await fileExistsOnDisk(stored.path);
        if (!exists || currentSessionName !== sessionName || !shouldUseDesktopFilePane()) {
          if (!exists) clearFileModalSessionState(sessionName);
          return false;
        }
        openFileModal(stored.path, stored.ext || extFromPath(stored.path), null, null);
        fileModalPreviewTheme = stored.theme === "light" ? "light" : "dark";
        fileModalHtmlPreviewMode = stored.mode === "web" ? "web" : "text";
        syncFileModalThemeToggle();
        syncFileModalHtmlModeToggle();
        syncFileModalShellTheme();
        requestAnimationFrame(() => {
          postFileModalTheme();
          postFileModalHtmlPreviewMode();
          saveFileModalSessionState(sessionName);
        });
        return true;
      } finally {
        _fileModalRestoreInFlightSession = "";
      }
    }
    const pathFromLocalHref = (href) => {
      const rawHref = String(href || "").trim();
      if (!rawHref || rawHref.startsWith("#") || rawHref.startsWith("//")) return "";
      try {
        const url = new URL(rawHref, window.location.href);
        if (url.origin === window.location.origin && ((CHAT_BASE_PATH && (url.pathname === `${CHAT_BASE_PATH}/file-raw` || url.pathname === `${CHAT_BASE_PATH}/file-view`)) || url.pathname === "/file-raw" || url.pathname === "/file-view")) {
          return url.searchParams.get("path") || "";
        }
      } catch (_) {}
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
        const path = normalizeWorkspaceFilePath(pathFromLocalHref(href));
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
      const raw = fromDataset || pathFromLocalHref(anchor.getAttribute("href") || "");
      return normalizeWorkspaceFilePath(raw);
    };
    const lineFromLinkAnchor = (anchor) => {
      if (!anchor) return 0;
      const raw = String(anchor.dataset?.line || "").trim();
      const n = parseInt(raw, 10);
      return Number.isFinite(n) && n > 0 ? n : 0;
    };
    const fileExistsOnDisk = async (path) => {
      const normalizedPath = normalizeWorkspaceFilePath(path);
      if (!normalizedPath) return false;
      const cached = _fileExistenceCache.get(normalizedPath);
      try {
        const res = await fetch("/files-exist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paths: [normalizedPath] }),
        });
        if (!res.ok) {
          return cached === true;
        }
        const data = await res.json().catch(() => ({}));
        const exists = !!data?.[normalizedPath];
        if (exists) {
          _fileExistenceCache.set(normalizedPath, true);
        } else {
          _fileExistenceCache.delete(normalizedPath);
        }
        return exists;
      } catch (_) {
        return cached === true;
      }
    };
    let _openSurfaceChain = Promise.resolve();
    const runOpenSurfaceSerialized = (fn) => {
      const next = _openSurfaceChain.then(fn).catch(() => {});
      _openSurfaceChain = next;
      return next;
    };
    const openFileSurface = (path, ext, sourceEl, triggerEvent, lineArg = 0) =>
      runOpenSurfaceSerialized(() => openFileSurfaceImpl(path, ext, sourceEl, triggerEvent, lineArg));
    const openFileSurfaceImpl = async (path, ext, sourceEl, triggerEvent, lineArg = 0) => {
      const normalizedPath = normalizeWorkspaceFilePath(path);
      if (!normalizedPath) return;
      const lineNum = Number.isFinite(lineArg) && lineArg > 0 ? Math.floor(lineArg) : 0;
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
      if (openFilesDirectInExternalEditor) {
        try {
          const obRes = await fetch(`/file-openability?path=${encodeURIComponent(normalizedPath)}`, { cache: "no-store" });
          if (obRes.ok) {
            const ob = await obRes.json().catch(() => ({}));
            const mk = ob && ob.media_kind;
            if (mk === "image" || mk === "video" || mk === "audio" || mk === "pdf") {
              await openFileInEditor(normalizedPath, 0);
              return;
            }
            if (ob && ob.editable) {
              await openFileInEditor(normalizedPath, lineNum);
              return;
            }
          }
        } catch (_) {}
      }
      openFileModal(normalizedPath, ext, sourceEl, triggerEvent);
    };
    const openFileInEditor = async (path, line = 0) => {
      const normalizedPath = normalizeWorkspaceFilePath(path);
      if (!normalizedPath) return false;
      const normalizedLine = Number.isFinite(line) && line > 0 ? Math.floor(line) : 0;
      const payload = { path: normalizedPath, line: normalizedLine };
      const tryPost = () =>
        fetch("/open-file-in-editor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      const delay = (ms) => new Promise((r) => setTimeout(r, ms));
      try {
        let res = await tryPost();
        if (!res.ok && (res.status >= 500 || res.status === 429)) {
          await delay(220);
          res = await tryPost();
        }
        if (!res.ok) {
          let detail = "Failed to open file in editor.";
          try {
            const data = await res.json();
            if (data && data.error) detail = data.error;
          } catch (_) {}
          throw new Error(detail);
        }
        return true;
      } catch (err) {
        try {
          _fileExistenceCache.delete(normalizedPath);
        } catch (_) {}
        setStatus(err?.message || "Failed to open file in editor.", true);
        setTimeout(() => setStatus(""), 2200);
        return false;
      }
    };
    fileModal.addEventListener("click", (event) => {
      if (event.target.closest(".file-modal-close[data-close-file-modal]")) {
        closeFileModal();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isComposerOverlayOpen()) {
        event.preventDefault();
        closeComposerOverlay({ restoreFocus: true });
      }
    });
    const stopFileModalResize = ({ persist = true } = {}) => {
      if (!_fileModalResizeState) return;
      _fileModalResizeState = null;
      document.body.classList.remove("file-modal-resizing");
      if (persist) persistDesktopFilePaneWidthPx();
    };
    const handleFileModalResizeMove = (event) => {
      if (!_fileModalResizeState) return;
      const nextWidth = _fileModalResizeState.startWidth + (_fileModalResizeState.startX - event.clientX);
      applyDesktopFilePaneWidthPx(nextWidth);
      updateFileModalViewportMetrics();
      if (needsHeaderViewportMetrics()) updateHeaderMenuViewportMetrics();
    };
    fileModalSplitResizer?.addEventListener("pointerdown", (event) => {
      if (!shouldUseDesktopFilePane()) return;
      event.preventDefault();
      event.stopPropagation();
      _fileModalResizeState = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startWidth: getDesktopFilePaneWidthPx(),
      };
      document.body.classList.add("file-modal-resizing");
      try {
        fileModalSplitResizer.setPointerCapture(event.pointerId);
      } catch (_) {}
    });
    fileModalSplitResizer?.addEventListener("pointermove", (event) => {
      if (!_fileModalResizeState || _fileModalResizeState.pointerId !== event.pointerId) return;
      handleFileModalResizeMove(event);
    });
    fileModalSplitResizer?.addEventListener("pointerup", (event) => {
      if (!_fileModalResizeState || _fileModalResizeState.pointerId !== event.pointerId) return;
      stopFileModalResize({ persist: true });
    });
    fileModalSplitResizer?.addEventListener("pointercancel", () => {
      stopFileModalResize({ persist: true });
    });
    fileModalOpenEditorBtn?.addEventListener("click", async () => {
      if (!fileModalCurrentPath) return;
      try {
        const res = await fetch("/open-file-in-editor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: fileModalCurrentPath }),
        });
        if (!res.ok) {
          let detail = "Failed to open file in editor.";
          try {
            const data = await res.json();
            if (data && data.error) detail = data.error;
          } catch (_) {}
          throw new Error(detail);
        }
      } catch (err) {
        alert(err?.message || "Failed to open file in editor.");
      }
    });
    fileModalThemeToggleBtn?.addEventListener("click", () => {
      if (fileModalCurrentExt !== "md") return;
      fileModalPreviewTheme = fileModalPreviewTheme === "dark" ? "light" : "dark";
      syncFileModalThemeToggle();
      syncFileModalShellTheme();
      postFileModalTheme();
      saveFileModalSessionState();
    });
    fileModalHtmlModeBtn?.addEventListener("click", () => {
      if (!isHtmlPreviewExt(fileModalCurrentExt)) return;
      fileModalHtmlPreviewMode = fileModalHtmlPreviewMode === "text" ? "web" : "text";
      syncFileModalHtmlModeToggle();
      postFileModalHtmlPreviewMode();
      saveFileModalSessionState();
    });
    const scrollToBottomBtn = document.getElementById("scrollToBottomBtn");
