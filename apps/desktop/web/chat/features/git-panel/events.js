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
            : (action === "stage" ? "/git-stage-file" : (action === "ignore" ? "/git-ignore-file" : "/git-delete-untracked-file"));
          const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: filePath }),
          });
          const payload = await response.json().catch(() => ({}));
          if (!response.ok || !payload?.ok) throw new Error(payload?.error || `${action} failed`);
          let okMsg = `${action}d ${filePath}`;
          if (action === "track") okMsg = `tracked ${filePath}`;
          else if (action === "stage") okMsg = `staged ${filePath}`;
          else if (action === "ignore") okMsg = `ignored ${filePath}`;
          else if (action === "delete") okMsg = `deleted ${filePath}`;
          setStatus(okMsg);
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
      const revertBtn = event.target.closest(".git-commit-revert");
      if (revertBtn) {
        event.preventDefault();
        event.stopPropagation();
        const hash = String(revertBtn.dataset.hash || "").trim();
        if (!hash || revertBtn.dataset.busy === "1") return;
        revertBtn.dataset.busy = "1";
        revertBtn.disabled = true;
        setStatus(`reverting ${hash.slice(0, 7)}...`);
        try {
          const response = await fetch("/git-revert-commit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ hash }),
          });
          const payload = await response.json().catch(() => ({}));
          if (!response.ok || !payload?.ok) throw new Error(payload?.error || "revert failed");
          setStatus(`reverted ${hash.slice(0, 7)}`);
          setTimeout(() => setStatus(""), 1800);
          dpGitDetailNeedsRefresh = true;
          await dpRefreshGitOverview();
        } catch (err) {
          setStatus(err?.message || "revert failed", true);
        } finally {
          delete revertBtn.dataset.busy;
          revertBtn.disabled = false;
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

    (function initPinnedSummaryExpand() {
      const aside = document.getElementById("gitPinnedSummaryAside");
      const inner = document.getElementById("gitPinnedSummaryInner");
      if (!aside || !inner) return;

      const expand = document.createElement("div");
      expand.className = "git-pinned-expand";
      aside.appendChild(expand);

      let openTimer = null;
      let closeTimer = null;
      let fetchSeq = 0;
      const _e = (s) => String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

      function cancelTimers() {
        clearTimeout(openTimer); openTimer = null;
        clearTimeout(closeTimer); closeTimer = null;
      }

      function close() {
        cancelTimers();
        aside.classList.remove("is-expanded");
        fetchSeq++;
        expand.innerHTML = "";
      }

      async function open() {
        cancelTimers();
        if (aside.hidden) return;
        if (!dpGitHeaderSummaryState?.clickable) {
          close();
          return;
        }
        aside.classList.add("is-expanded");

        const seq = ++fetchSeq;
        expand.innerHTML = `<div class="git-pinned-expand-loading"><span></span><span></span><span></span></div>`;

        try {
          const [staged, unstaged, untracked] = await Promise.all([
            fetchWithTimeout("/git-diff-files?scope=staged",    {}, 4000).then(r => r.json()),
            fetchWithTimeout("/git-diff-files?scope=unstaged",  {}, 4000).then(r => r.json()),
            fetchWithTimeout("/git-diff-files?scope=untracked", {}, 4000).then(r => r.json()),
          ]);
          if (seq !== fetchSeq) return;

          const sections = [
            { label: "Staged",    scope: "staged",    files: staged?.files    || [] },
            { label: "Unstaged",  scope: "unstaged",  files: unstaged?.files  || [] },
            { label: "Untracked", scope: "untracked", files: untracked?.files || [] },
          ].filter(s => s.files.length);

          if (!sections.length) {
            close();
            return;
          }

          expand.innerHTML = sections.map(s =>
            `<div class="git-pinned-expand-section">` +
            s.files.map(f => {
              const path = String(f.path || "");
              const slash = path.lastIndexOf("/");
              const name = slash >= 0 ? path.slice(slash + 1) : path;
              const dir  = slash >= 0 ? path.slice(0, slash)  : "";
              const ins  = Math.max(0, parseInt(f.ins)  || 0);
              const dels = Math.max(0, parseInt(f.dels) || 0);
              const counts = (!f.untracked && (ins || dels))
                ? `<span class="git-pinned-expand-counts"><span class="ins">+${ins}</span><span class="del">-${dels}</span></span>`
                : "";
              return `<div class="git-pinned-expand-file" data-path="${_e(path)}" data-scope="${_e(s.scope)}">` +
                `<span class="git-pinned-expand-file-label"><span class="n">${_e(name)}</span>${dir ? `<span class="d">${_e(dir)}</span>` : ""}</span>` +
                counts +
                `</div>`;
            }).join("") +
            `</div>`
          ).join("");
        } catch (_) {
          if (seq !== fetchSeq) return;
          expand.innerHTML = `<div class="git-pinned-expand-empty">読み込み失敗</div>`;
        }
      }

      expand.addEventListener("click", (event) => {
        const file = event.target.closest(".git-pinned-expand-file");
        if (!file) return;
        const path = file.dataset.path || "";
        if (path) dpPostOpenFileInEditor(path, 0, { diff: file.dataset.scope !== "untracked" });
      });

      aside.addEventListener("mouseenter", () => { cancelTimers(); openTimer = setTimeout(open, 60); });
      aside.addEventListener("mouseleave", () => { cancelTimers(); closeTimer = setTimeout(close, 60); });
    })();

