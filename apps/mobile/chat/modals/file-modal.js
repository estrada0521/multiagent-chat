    const _fileExistenceCache = new Map();
    const FILE_PREVIEW_THEME_ICONS = {
      dark: '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>',
      light: '<path d="M21 12.79A9 9 0 1 1 11.21 3c0 0 0 0 0 0A7 7 0 0 0 21 12.79z"></path>',
    };
    const FILE_PREVIEW_HTML_MODE_ICONS = {
      web: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"></rect><path d="M3.5 9.5h17"></path><circle cx="7.5" cy="7" r="0.8" fill="currentColor" stroke="none"></circle><circle cx="10.5" cy="7" r="0.8" fill="currentColor" stroke="none"></circle><path d="M9.5 13.5h6"></path><path d="M9.5 16.5h4"></path>',
      text: '<path d="M14 3.5H7.5A2.5 2.5 0 0 0 5 6v12a2.5 2.5 0 0 0 2.5 2.5h9A2.5 2.5 0 0 0 19 18V8.5z"></path><path d="M14 3.5V8.5H19"></path><path d="M9 12.5h6"></path><path d="M9 16h6"></path>',
    };
    let attachedFilesPreviewTheme = "dark";
    let attachedFilesPreviewBaseTheme = document.documentElement.dataset.theme === "light" ? "light" : "dark";
    let attachedFilesHtmlPreviewMode = "text";
    let attachedFilesPreviewControlsWired = false;
    const currentFileModalBaseTheme = () => document.documentElement.dataset.theme === "light" ? "light" : "dark";
    const isHtmlPreviewExt = (ext) => ext === "html" || ext === "htm";
    const attachedFilesPreviewFrameEl = () => attachedFilesPanel?.querySelector(".attached-files-preview-frame");
    const attachedFilesPreviewThemeToggleBtn = () => attachedFilesPanel?.querySelector(".attached-files-preview-theme-toggle");
    const attachedFilesPreviewThemeToggleIcon = () => attachedFilesPanel?.querySelector(".attached-files-preview-theme-toggle-icon");
    const attachedFilesPreviewHtmlModeBtn = () => attachedFilesPanel?.querySelector(".attached-files-preview-html-mode");
    const attachedFilesPreviewHtmlModeIcon = () => attachedFilesPanel?.querySelector(".attached-files-preview-html-mode-icon");
    const attachedFilesPreviewExt = () => String(attachedFilesPanel?._previewExt || "").toLowerCase();
    const attachedFilesPreviewInPreviewMode = () => !!attachedFilesPanel?.classList.contains("attached-files-mode-preview");
    const syncAttachedFilesPreviewThemeToggle = () => {
      const btn = attachedFilesPreviewThemeToggleBtn();
      const icon = attachedFilesPreviewThemeToggleIcon();
      if (!btn || !icon) return;
      const isMd = attachedFilesPreviewExt() === "md";
      btn.hidden = !attachedFilesPreviewInPreviewMode() || !isMd;
      if (btn.hidden) return;
      const nextLabel = attachedFilesPreviewTheme === "dark" ? "Switch markdown preview to light" : "Switch markdown preview to dark";
      btn.title = nextLabel;
      btn.setAttribute("aria-label", nextLabel);
      icon.innerHTML = FILE_PREVIEW_THEME_ICONS[attachedFilesPreviewTheme] || FILE_PREVIEW_THEME_ICONS.dark;
    };
    const syncAttachedFilesPreviewHtmlModeToggle = () => {
      const btn = attachedFilesPreviewHtmlModeBtn();
      const icon = attachedFilesPreviewHtmlModeIcon();
      if (!btn || !icon) return;
      const isHtml = isHtmlPreviewExt(attachedFilesPreviewExt());
      btn.hidden = !attachedFilesPreviewInPreviewMode() || !isHtml;
      if (btn.hidden) return;
      const nextMode = attachedFilesHtmlPreviewMode === "text" ? "web" : "text";
      const title = nextMode === "text" ? "Switch HTML preview to text" : "Switch HTML preview to web";
      btn.title = title;
      btn.setAttribute("aria-label", title);
      icon.innerHTML = FILE_PREVIEW_HTML_MODE_ICONS[nextMode] || FILE_PREVIEW_HTML_MODE_ICONS.text;
    };
    const syncAttachedFilesPreviewShellTheme = () => {
      if (!attachedFilesPanel) return;
      const isMd = attachedFilesPreviewExt() === "md";
      attachedFilesPanel.classList.toggle("attached-files-preview-shell-light", isMd && attachedFilesPreviewTheme === "light");
      attachedFilesPanel.classList.toggle("attached-files-preview-shell-dark", isMd && attachedFilesPreviewBaseTheme === "light" && attachedFilesPreviewTheme === "dark");
    };
    const resetAttachedFilesPreviewControls = () => {
      attachedFilesPreviewTheme = currentFileModalBaseTheme();
      attachedFilesPreviewBaseTheme = attachedFilesPreviewTheme;
      attachedFilesHtmlPreviewMode = "text";
      syncAttachedFilesPreviewThemeToggle();
      syncAttachedFilesPreviewHtmlModeToggle();
      syncAttachedFilesPreviewShellTheme();
    };
    const initAttachedFilesPreviewControls = () => {
      attachedFilesPreviewBaseTheme = currentFileModalBaseTheme();
      attachedFilesPreviewTheme = attachedFilesPreviewBaseTheme;
      attachedFilesHtmlPreviewMode = "text";
      syncAttachedFilesPreviewThemeToggle();
      syncAttachedFilesPreviewHtmlModeToggle();
      syncAttachedFilesPreviewShellTheme();
    };
    const applyPreviewHtmlModeToFrame = (frame, ext, mode) => {
      if (!isHtmlPreviewExt(ext)) return false;
      const nextMode = mode === "text" ? "text" : "web";
      try {
        const frameWindow = frame.contentWindow;
        const frameDoc = frame.contentDocument || frameWindow?.document || null;
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
    const postPreviewHtmlModeToFrame = (frame, ext, mode) => {
      if (!frame || !isHtmlPreviewExt(ext)) return;
      applyPreviewHtmlModeToFrame(frame, ext, mode);
      try {
        frame.contentWindow?.postMessage(
          { type: "agent-index-file-preview-mode", mode },
          window.location.origin,
        );
      } catch (_) { }
      requestAnimationFrame(() => {
        applyPreviewHtmlModeToFrame(frame, ext, mode);
      });
      setTimeout(() => {
        applyPreviewHtmlModeToFrame(frame, ext, mode);
      }, 60);
    };
    const postAttachedFilesPreviewTheme = () => {
      const frame = attachedFilesPreviewFrameEl();
      if (!frame?.src) return;
      postPreviewThemeToFrame(frame, attachedFilesPreviewExt(), attachedFilesPreviewTheme, attachedFilesPreviewBaseTheme);
    };
    const postAttachedFilesPreviewHtmlMode = () => {
      const frame = attachedFilesPreviewFrameEl();
      if (!frame?.src) return;
      postPreviewHtmlModeToFrame(frame, attachedFilesPreviewExt(), attachedFilesHtmlPreviewMode);
    };
    const wireAttachedFilesPreviewControls = (sheetNav) => {
      if (attachedFilesPreviewControlsWired || !sheetNav) return;
      const navBar = sheetNav.querySelector(".attached-files-sheet-nav-bar");
      const closeBtn = navBar?.querySelector(".attached-files-sheet-close");
      if (!navBar || !closeBtn) return;
      attachedFilesPreviewControlsWired = true;
      const actions = document.createElement("div");
      actions.className = "attached-files-preview-actions";
      const themeBtn = document.createElement("button");
      themeBtn.type = "button";
      themeBtn.className = "attached-files-preview-theme-toggle mobile-bottom-sheet-button mobile-floating-sheet-button";
      themeBtn.hidden = true;
      themeBtn.innerHTML = '<svg class="attached-files-preview-theme-toggle-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"></svg>';
      const htmlBtn = document.createElement("button");
      htmlBtn.type = "button";
      htmlBtn.className = "attached-files-preview-html-mode mobile-bottom-sheet-button mobile-floating-sheet-button";
      htmlBtn.hidden = true;
      htmlBtn.innerHTML = '<svg class="attached-files-preview-html-mode-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"></svg>';
      actions.append(themeBtn, htmlBtn, closeBtn);
      navBar.appendChild(actions);
      themeBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (attachedFilesPreviewExt() !== "md") return;
        attachedFilesPreviewTheme = attachedFilesPreviewTheme === "dark" ? "light" : "dark";
        syncAttachedFilesPreviewThemeToggle();
        syncAttachedFilesPreviewShellTheme();
        postAttachedFilesPreviewTheme();
      });
      htmlBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!isHtmlPreviewExt(attachedFilesPreviewExt())) return;
        attachedFilesHtmlPreviewMode = attachedFilesHtmlPreviewMode === "text" ? "web" : "text";
        syncAttachedFilesPreviewHtmlModeToggle();
        postAttachedFilesPreviewHtmlMode();
      });
      resetAttachedFilesPreviewControls();
    };
    const applyPreviewThemeToFrame = (frame, ext, previewTheme, baseTheme) => {
      if (!frame) return false;
      const normalizedExt = String(ext || "").toLowerCase();
      const resolvedPreviewTheme = previewTheme === "light" ? "light" : "dark";
      const resolvedBaseTheme = baseTheme === "light" ? "light" : "dark";
      try {
        const frameWindow = frame.contentWindow;
        const frameDoc = frame.contentDocument || frameWindow?.document || null;
        if (normalizedExt === "md" && typeof frameWindow?.__agentIndexApplyPreviewTheme === "function") {
          frameWindow.__agentIndexApplyPreviewTheme(resolvedPreviewTheme, resolvedBaseTheme);
          return true;
        }
        if (!frameDoc?.documentElement) return false;
        if (normalizedExt === "md") {
          frameDoc.documentElement.setAttribute(
            "data-preview-theme",
            resolvedPreviewTheme === "light" ? "light" : "dark",
          );
          if (resolvedPreviewTheme === resolvedBaseTheme) {
            frameDoc.documentElement.removeAttribute("data-preview-explicit-bg");
          } else {
            frameDoc.documentElement.setAttribute("data-preview-explicit-bg", "1");
          }
          return true;
        }
        const isLight = resolvedBaseTheme === "light";
        const bg = isLight ? "rgb(255,255,255)" : "rgb(0,0,0)";
        const fg = isLight ? "rgb(0,0,0)" : "rgb(255,255,255)";
        const lnFg = isLight ? "rgba(0,0,0,0.22)" : "rgba(255,255,255,0.22)";
        const scheme = isLight ? "light" : "dark";
        frameDoc.documentElement.setAttribute("data-preview-base-theme", scheme);
        let style = frameDoc.getElementById("agent-index-base-theme-style");
        if (!style) {
          style = frameDoc.createElement("style");
          style.id = "agent-index-base-theme-style";
          frameDoc.head?.appendChild(style);
        }
        style.textContent = `html,body{color-scheme:${scheme};background:${bg};color:${fg}}.view-container,.html-preview-shell,.wrap{background:${bg}}.fn{color:${fg}}.code-gutter-table .ln,.html-preview-gutter-table .ln{color:${lnFg}}.code-table,.html-preview-text-table,pre{color:${fg}}`;
        return true;
      } catch (_) { }
      return false;
    };
    const postPreviewThemeToFrame = (frame, ext, previewTheme, baseTheme) => {
      applyPreviewThemeToFrame(frame, ext, previewTheme, baseTheme);
      try {
        frame.contentWindow?.postMessage(
          { type: "agent-index-file-preview-theme", theme: previewTheme, baseTheme },
          window.location.origin,
        );
      } catch (_) { }
      requestAnimationFrame(() => {
        applyPreviewThemeToFrame(frame, ext, previewTheme, baseTheme);
      });
      setTimeout(() => {
        applyPreviewThemeToFrame(frame, ext, previewTheme, baseTheme);
      }, 60);
    };
    const resetEmbeddedFilePreviewFrame = (frame) => {
      if (!frame) return;
      frame.onload = null;
      frame.style.opacity = "";
      frame.style.transition = "";
      frame.removeAttribute("src");
    };
    const wireEmbeddedFilePreviewFrame = (frame, path, ext) => {
      const normalizedPath = String(path || "").trim();
      const normalizedExt = String(ext || "").toLowerCase();
      if (!frame || !normalizedPath) return;
      resetEmbeddedFilePreviewFrame(frame);
      frame.style.opacity = "0";
      frame.onload = () => {
        frame.style.transition = "opacity 200ms ease-out";
        frame.style.opacity = "1";
        postPreviewThemeToFrame(frame, normalizedExt, attachedFilesPreviewTheme, attachedFilesPreviewBaseTheme);
        postPreviewHtmlModeToFrame(frame, normalizedExt, attachedFilesHtmlPreviewMode);
      };
      frame.src = fileViewHrefForPath(normalizedPath, { embed: true });
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
    const closeFileModal = () => {
      if (attachedFilesPanel?.classList.contains("attached-files-mode-preview")) {
        closeAttachedFilesRepoPreview();
      }
      if (attachedFilesPanel?.classList.contains("open") && !attachedFilesPanel.hidden) {
        closeAttachedFilesSheet();
      }
    };
    const openFileSurface = async (path, ext, sourceEl, triggerEvent) => {
      const normalizedPath = String(path || "").trim();
      if (!normalizedPath) return;
      const normalizedExt = String(ext || extFromPath(normalizedPath) || "").toLowerCase();
      if (typeof attachedFilesPanel?._openFilePreview !== "function") return;
      if (!isPublicChatView) {
        const exists = await fileExistsOnDisk(normalizedPath);
        if (!exists) {
          setStatus(`file not found: ${displayAttachmentFilename(normalizedPath) || normalizedPath}`, true);
          setTimeout(() => setStatus(""), 2200);
          return;
        }
      }
      await attachedFilesPanel._openFilePreview(normalizedPath, normalizedExt);
    };
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && attachedFilesPanel?.classList.contains("attached-files-mode-preview")) {
        event.preventDefault();
        closeAttachedFilesRepoPreview();
        return;
      }
      if (event.key === "Escape" && isComposerOverlayOpen()) {
        event.preventDefault();
        closeComposerOverlay({ restoreFocus: true });
      }
    });
    if (typeof MutationObserver !== "undefined") {
      new MutationObserver((mutations) => {
        if (!attachedFilesPanel?.classList.contains("attached-files-mode-preview")) return;
        if (!mutations.some((mutation) => mutation.attributeName === "data-theme")) return;
        const frame = attachedFilesPreviewFrameEl();
        if (!frame?.src) return;
        const prevBase = attachedFilesPreviewBaseTheme;
        const wasOpposite = attachedFilesPreviewTheme !== prevBase;
        attachedFilesPreviewBaseTheme = currentFileModalBaseTheme();
        if (attachedFilesPreviewExt() === "md") {
          attachedFilesPreviewTheme = wasOpposite
            ? (attachedFilesPreviewBaseTheme === "dark" ? "light" : "dark")
            : attachedFilesPreviewBaseTheme;
        } else {
          attachedFilesPreviewTheme = attachedFilesPreviewBaseTheme;
        }
        syncAttachedFilesPreviewThemeToggle();
        syncAttachedFilesPreviewShellTheme();
        postAttachedFilesPreviewTheme();
      }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    }
    const scrollToBottomBtn = document.getElementById("scrollToBottomBtn");
