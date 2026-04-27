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
