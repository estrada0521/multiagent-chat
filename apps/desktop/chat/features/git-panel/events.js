    dpGitContent?.addEventListener("click", async (event) => {
      await gitSession.handleClick(event, {
        onPin: () => dpToggleGitSummaryPinned(),
        requireOpen: () => dpPanelOpen,
        onFileRow: async (fileRow) => {
          const p = String(fileRow.dataset.path || "").trim();
          if (!p) return;
          const isUncommittedRow = !!fileRow.closest(".git-commit-file-section");
          const isUntracked = fileRow.dataset.untracked === "1";
          if (isUncommittedRow && !isUntracked) {
            await dpPostOpenDiff(p);
            return;
          }
          await dpPostOpenFile(p);
        },
        closeWorktreeSummaryClick: true,
      });
    });
    dpGitContent?.addEventListener("contextmenu", (event) => {
      const fileRow = event.target.closest(".git-commit-file-row");
      const path = String(fileRow?.dataset.path || "").trim();
      if (path) void dpOpenFileContextMenu(path, event);
    });
    document.getElementById("gitPinnedSummaryAside")?.addEventListener("click", async (event) => {
      if (event.target.closest(".git-summary-pin")) {
        event.preventDefault();
        event.stopPropagation();
        dpToggleGitSummaryPinned();
        return;
      }
      const row = event.target.closest('.git-summary-row[data-diff-kind="worktree"]');
      if (!row || !dpGitContent) return;
      event.preventDefault();
      event.stopPropagation();
      const needReset = !dpGitContent.querySelector(".git-stack");
      await openDesktopRightPanel({ view: "git", reset: needReset });
      await dpOpenGitDetail({
        diffKind: "worktree",
        hash: "",
        rowHtml: row.outerHTML,
        subject: row.querySelector(".git-summary-label")?.textContent?.trim() || "Uncommitted changes",
      });
    });

    (function initPinnedSummaryExpand() {
      const aside = document.getElementById("gitPinnedSummaryAside");
      const inner = document.getElementById("gitPinnedSummaryInner");
      if (!aside || !inner) return;

      const expand = document.createElement("div");
      expand.className = "git-pinned-expand";
      aside.appendChild(expand);

      // Fade the top/bottom edges of the scrolled file list, like the hub's
      // hover popover (see computeScrollFadeState in home.js).
      const updateExpandFade = () => {
        const { scrollTop, scrollHeight, clientHeight } = expand;
        if (scrollHeight <= clientHeight + 1) { expand.dataset.scrollFade = "none"; return; }
        const atTop = scrollTop <= 1;
        const atBottom = scrollTop + clientHeight >= scrollHeight - 1;
        expand.dataset.scrollFade = atTop && !atBottom ? "bottom" : atBottom && !atTop ? "top" : "both";
      };
      expand.addEventListener("scroll", updateExpandFade, { passive: true });

      let openTimer = null;
      let closeTimer = null;
      let fetchSeq = 0;
      const _e = (s) => String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

      function cancelTimers() {
        clearTimeout(openTimer); openTimer = null;
        clearTimeout(closeTimer); closeTimer = null;
      }

      function animatePopoverIn(popover, stableElement) {
        if (!popover || typeof popover.animate !== "function") return;
        if (window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) return;

        const frames = [];
        const stableFrames = [];
        const steps = 48;
        const frequency = Math.PI * 2.55;
        const damping = 3.8;
        for (let i = 0; i <= steps; i += 1) {
          const progress = i / steps;
          const decay = Math.exp(-damping * progress);
          const wave = Math.sin((frequency * progress) - (Math.PI / 2));
          let scaleX = 1;
          let scaleY = 1 + (0.24 * decay * wave);
          if (i === steps) {
            scaleX = 1;
            scaleY = 1;
          }
          frames.push({
            transform: `scale(${scaleX.toFixed(4)}, ${scaleY.toFixed(4)})`,
          });
          if (stableElement) {
            stableFrames.push({
              transform: `scale(1, ${ (1/scaleY).toFixed(4) })`
            });
          }
        }
        const animation = popover.animate(frames, {
          duration: 360,
          easing: "linear",
          fill: "both",
        });
        if (stableElement && stableFrames.length) {
          stableElement.animate(stableFrames, {
            duration: 360,
            easing: "linear",
            fill: "both",
          });
        }
        animation.addEventListener("finish", () => {
          popover.style.transform = "";
          if (stableElement) stableElement.style.transform = "";
        }, { once: true });
      }

      function close() {
        cancelTimers();
        aside.classList.remove("is-expanded");
        fetchSeq++;
        expand.innerHTML = "";
        expand.dataset.scrollFade = "none";
      }

      async function refreshContent() {
        if (!dpGitHeaderSummaryState?.clickable) {
          close();
          return;
        }
        const seq = ++fetchSeq;
        expand.innerHTML = `<div class="git-pinned-expand-loading"><span></span><span></span><span></span></div>`;

        try {
          const { sections } = await fetchGitWorktreeFileSections();
          if (seq !== fetchSeq) return;

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
              const icon = FILE_ICONS[extFromPath(path)] || FILE_SVG_ICONS.file;
              const counts = (!f.untracked && (ins || dels))
                ? `<span class="git-pinned-expand-counts"><span class="ins">+${ins}</span><span class="del">-${dels}</span></span>`
                : "";
              return `<div class="git-pinned-expand-file" data-path="${_e(path)}" data-scope="${_e(s.kind)}">` +
                `<span class="git-pinned-expand-file-main"><span class="git-pinned-expand-file-icon">${icon}</span>` +
                `<span class="git-pinned-expand-file-label"><span class="n">${_e(name)}</span>${dir ? `<span class="d">${_e(dir)}</span>` : ""}</span></span>` +
                counts +
                `</div>`;
            }).join("") +
            `</div>`
          ).join("");
        } catch (_) {
          if (seq !== fetchSeq) return;
          expand.innerHTML = `<div class="git-pinned-expand-empty">Failed to load</div>`;
        }
        requestAnimationFrame(updateExpandFade);
      }

      async function open() {
        cancelTimers();
        if (aside.hidden) return;
        if (!dpGitHeaderSummaryState?.clickable) {
          close();
          return;
        }
        aside.classList.add("is-expanded");
        animatePopoverIn(aside, inner);
        await refreshContent();
      }

      // The summary row's own counts already refresh whenever a workspace
      // sync event reports the git state changed (dpApplyGitOverviewHeader),
      // but this popover only ever fetched once, when the mouse first opened
      // it -- a commit landing while it's still open left it showing files
      // that no longer differ. Re-run the fetch in place (no re-triggered
      // pop-in animation) on that same event, if it's open.
      dpPinnedExpandRefresh = () => {
        if (aside.classList.contains("is-expanded")) void refreshContent();
      };

      expand.addEventListener("click", (event) => {
        const file = event.target.closest(".git-pinned-expand-file");
        if (!file) return;
        const path = file.dataset.path || "";
        if (!path) return;
        if (file.dataset.scope !== "untracked") {
          void dpPostOpenDiff(path);
          return;
        }
        void dpPostOpenFile(path);
      });

      aside.addEventListener("mouseenter", () => { cancelTimers(); openTimer = setTimeout(open, 60); });
      aside.addEventListener("mouseleave", () => { cancelTimers(); closeTimer = setTimeout(close, 60); });
    })();
