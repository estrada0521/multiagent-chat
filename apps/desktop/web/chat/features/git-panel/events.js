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
      const fileActionBtn = event.target.closest(".git-commit-file-action");
      if (fileActionBtn) {
        event.preventDefault();
        event.stopPropagation();
        const filePath = String(fileActionBtn.dataset.path || "").trim();
        const action = String(fileActionBtn.dataset.action || "").trim();
        if (!filePath || !action || fileActionBtn.dataset.busy === "1") return;
        fileActionBtn.dataset.busy = "1";
        fileActionBtn.disabled = true;
        setStatus(`${action} ${filePath}...`);
        try {
          const endpoint = action === "track"
            ? "/git-track-file"
            : (action === "stage" ? "/git-stage-file" : "/git-delete-untracked-file");
          const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: filePath }),
          });
          const payload = await response.json().catch(() => ({}));
          if (!response.ok || !payload?.ok) throw new Error(payload?.error || `${action} failed`);
          setStatus(`${action === "track" ? "tracked" : (action === "stage" ? "staged" : "deleted")} ${filePath}`);
          setTimeout(() => setStatus(""), 1800);
          dpGitDetailNeedsRefresh = true;
          await dpRefreshGitOverview();
        } catch (err) {
          setStatus(err?.message || `${action} failed`, true);
        } finally {
          delete fileActionBtn.dataset.busy;
          fileActionBtn.disabled = false;
        }
        return;
      }
      const fileRow = event.target.closest(".git-commit-file-row");
      if (fileRow && !event.target.closest(".git-commit-file-undo")) {
        event.preventDefault();
        const p = String(fileRow.dataset.path || "").trim();
        if (p) {
          await dpPostOpenFileInEditor(p, 0, {
            diff: fileRow.dataset.untracked !== "1",
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
            body: JSON.stringify({
              path: filePath,
              scope: event.target.closest(".git-commit-file-section")?.dataset.scope || "",
            }),
          });
          const payload = await response.json().catch(() => ({}));
          if (!response.ok || !payload?.ok) throw new Error(payload?.error || "undo failed");
          setStatus(`restored ${filePath}`);
          setTimeout(() => setStatus(""), 1800);
          dpGitDetailNeedsRefresh = true;
          await dpRefreshGitOverview();
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
      const subject = diffKind
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
      const needReset = !dpGitContent.querySelector(".git-branch-stack");
      await openDesktopRightPanel({ view: "git", reset: needReset });
      await dpOpenGitDetail({
        diffKind: "worktree",
        hash: "",
        rowHtml: row.outerHTML,
        subject: row.querySelector(".git-branch-summary-label")?.textContent?.trim() || "Uncommitted changes",
      });
    });
