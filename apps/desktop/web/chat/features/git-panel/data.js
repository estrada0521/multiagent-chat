    let _dpGitOverviewFingerprint = null;
    let _dpGitRefreshInFlight = false;
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
    const dpRefreshGitOverview = async () => {
      if (dpGitPageLoading) return;
      if (!dpPanelOpen && !dpGitSummaryPinned) return;
      if (_dpGitRefreshInFlight) return;
      _dpGitRefreshInFlight = true;
      try {
        const params = new URLSearchParams({ offset: "0", limit: String(DP_GIT_BATCH) });
        params.set("refresh", "1");
        const res = await fetchWithTimeout(`/git-branch-overview?${params}`, {}, 5000);
        if (!res.ok) return;
        const data = await res.json();
        const fp = dpGitFingerprint(data);
        if (fp === _dpGitOverviewFingerprint) return;
        const isFirstRefresh = _dpGitOverviewFingerprint === null;
        _dpGitOverviewFingerprint = fp;

        if (!dpPanelOpen && dpGitSummaryPinned) {
          dpGitHeaderSummaryState = dpBuildSummaryState(data);
          dpApplyGitOverviewHeader();
          if (!isFirstRefresh && !dpGitDetailContext) dpKickWorktreeSummaryGlow();
          return;
        }

        let newHashes = null;
        if (!isFirstRefresh && Array.isArray(data?.recent_commits) && dpGitCommits.length > 0) {
          const oldHashes = new Set(dpGitCommits.map(c => c.hash));
          newHashes = new Set();
          for (const c of data.recent_commits) {
            if (!oldHashes.has(c.hash)) newHashes.add(c.hash);
          }
          if (newHashes.size === 0) newHashes = null;
        }

        dpGitHeaderSummaryState = dpBuildSummaryState(data);
        dpSyncSummaryWrap({ flash: !isFirstRefresh && !dpGitDetailContext });
        if (!dpGitDetailContext) {
          dpGitCommits = Array.isArray(data?.recent_commits) ? data.recent_commits.slice() : [];
          dpGitTotalCommits = Math.max(0, parseInt(data?.total_commits) || 0);
          dpGitNextOffset = Math.max(0, parseInt(data?.next_offset) || dpGitCommits.length);
          dpGitHasMore = !!data?.has_more;
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
        _dpGitRefreshInFlight = false;
      }
    };
    const dpToggleGitSummaryPinned = () => {
      dpGitSummaryPinned = !dpGitSummaryPinned;
      try {
        window.localStorage?.setItem(dpGitSummaryPinnedStorageKey(), dpGitSummaryPinned ? "1" : "0");
      } catch (_) {}
      if (dpGitSummaryPinned) {
        if (!dpGitHeaderSummaryState?.rowHtml) void dpBootstrapPinnedGitSummary();
        else dpSyncPinnedSummaryStrip();
      } else {
        dpSyncPinnedSummaryStrip();
      }
    };
    const dpBootstrapPinnedGitSummary = async () => {
      if (!hasDesktopRightPanelOverlay() || !dpGitSummaryPinned) return;
      try {
        const params = new URLSearchParams({ offset: "0", limit: String(DP_GIT_BATCH) });
        const res = await fetchWithTimeout(`/git-branch-overview?${params}`, {}, 5000);
        if (!res.ok) return;
        const data = await res.json();
        dpGitHeaderSummaryState = dpBuildSummaryState(data);
        dpApplyGitOverviewHeader();
        _dpGitOverviewFingerprint = dpGitFingerprint(data);
      } catch (_) {}
    };
    const dpOnSessionSummaryPinReload = ({ force = false } = {}) => {
      const storageKey = dpGitSummaryPinnedStorageKey();
      if (!force && _dpGitSummaryPinnedLoadedForKey === storageKey) return;
      _dpGitSummaryPinnedLoadedForKey = storageKey;
      dpReadGitSummaryPinnedFromStorage();
      _dpGitOverviewFingerprint = null;
      if (dpGitSummaryPinned) {
        void dpBootstrapPinnedGitSummary();
      }
      dpSyncPinnedSummaryStrip();
      dpApplyPanelWidth();
    };
    const dpApplyGitPage = (data, { reset = false, newHashes = null } = {}) => {
      const commits = Array.isArray(data?.recent_commits) ? data.recent_commits : [];
      if (reset) {
        dpRenderGitShell(data || {});
        dpGitCommits = [];
      }
      dpGitHeaderSummaryState = dpBuildSummaryState(data || {});
      _dpGitOverviewFingerprint = dpGitFingerprint(data || {});
      dpSyncSummaryWrap();
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
      } catch (err) {
        if (loadSeq !== dpGitLoadSeq) return;
        if (reset) {
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
      dpGitContent.scrollTop = 0;
      requestAnimationFrame(() => stack.classList.remove("git-branch-transitioning"));
      try {
        await dpRenderFileStatsInto(wrapEl, diffKind === "worktree" ? "" : hash, { allowUndo: diffKind === "worktree" });
      } catch (_) {
        wrapEl.innerHTML = '<div class="git-commit-file-empty">Failed to load file stats</div>';
      }
    };
