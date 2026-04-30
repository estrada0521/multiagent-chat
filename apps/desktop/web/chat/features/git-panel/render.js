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
      const chevron = worktreeClickable
        ? '<svg class="git-commit-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>'
        : "";
      const pinBtn = `<button type="button" class="git-branch-summary-pin" aria-pressed="false" aria-label="未コミット概要をチャット右端に固定表示" title="右ペインを閉じても右端にこの概要を表示">${DP_GIT_SUMMARY_PIN_SVG}</button>`;
      return `<div class="git-branch-summary-row${worktreeClickable ? " clickable" : ""}"${worktreeClickable ? ' data-diff-kind="worktree"' : ""}>${pinBtn}<div class="git-commit-info"><div class="git-branch-summary-label">${escapeHtml(worktreeLabel)}</div><div class="git-commit-meta">${worktreeMeta}${worktreeCounts}</div></div>${chevron}</div>`;
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
      const iconInner = '<span class="git-commit-dot" aria-hidden="true"></span>';
      const subjHtml = `<div class="git-commit-subject">${escapeHtml(commit?.subject || "")}</div>`;
      const ins = Math.max(0, parseInt(commit?.ins) || 0);
      const dels = Math.max(0, parseInt(commit?.dels) || 0);
      const statHtml = dpGitCountsHtml(ins, dels);
      const animClass = animate ? " new-commit-slide" : "";
      return `<div class="git-commit-row${animClass}" data-hash="${escapeHtml(commit?.hash || "")}"><span class="git-commit-icon-wrap">${iconInner}</span><div class="git-commit-info">${subjHtml}<div class="git-commit-meta">${statHtml}</div></div></div>`;
    };
    const dpBuildFileRowHtml = (entry, { allowUndo = false } = {}) => {
      const path = String(entry?.path || "").trim();
      const ins = Math.max(0, parseInt(entry?.ins) || 0);
      const dels = Math.max(0, parseInt(entry?.dels) || 0);
      const undoHtml = allowUndo
        ? `<button type="button" class="git-commit-file-undo" data-path="${escapeHtml(path)}" aria-label="Restore ${escapeHtml(path)}" title="Restore"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14 4 9l5-5"></path><path d="M4 9h10.5a5.5 5.5 0 1 1 0 11H11"></path></svg></button>`
        : "";
      const ext = extFromPath(path);
      const iconSvg = FILE_ICONS[ext] || FILE_SVG_ICONS.file;
      const iconHtml = `<span class="git-commit-file-icon">${iconSvg}</span>`;
      const slashIdx = path.lastIndexOf("/");
      const fileName = slashIdx >= 0 ? path.slice(slashIdx + 1) : path;
      const dirPath = slashIdx >= 0 ? path.slice(0, slashIdx) : "";
      const pathHtml = dirPath
        ? `<span class="git-commit-file-name">${escapeHtml(fileName)}</span><span class="git-commit-file-dir">${escapeHtml(dirPath)}</span>`
        : `<span class="git-commit-file-name">${escapeHtml(fileName)}</span>`;
      const fileMetaHtml = `<div class="git-commit-file-meta">${dpGitCountsHtml(ins, dels)}</div>`;
      const actionsHtml = allowUndo ? `${undoHtml}${fileMetaHtml}` : fileMetaHtml;
      const undoClass = allowUndo ? " has-undo" : "";
      return `<div class="git-commit-file-row clickable${undoClass}" data-path="${escapeHtml(path)}"><div class="git-commit-file-header">${iconHtml}<div class="git-commit-file-path" title="${escapeHtml(path)}">${pathHtml}</div><div class="git-commit-file-actions">${actionsHtml}</div></div></div>`;
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
