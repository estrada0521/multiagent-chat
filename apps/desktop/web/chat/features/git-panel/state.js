    const DP_GIT_BATCH = 50;
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
