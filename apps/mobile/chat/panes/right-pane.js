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
