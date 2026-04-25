    const render = (data, { forceScroll = false, forceFullRender = false } = {}) => {
      try {
        const shouldStick = forceScroll;
        const displayEntries = displayEntriesForData(data);
        const thinkingMetaHiddenIds = computeThinkingMetaHiddenIds(displayEntries);
        const previousRenderedIds = new Set(_renderedIds);

        updateSessionUI(data, displayEntries);

        const renderSig = displayEntries.map((entry) => entryRenderKey(entry)).join("\u0002");
        if (!forceScroll && renderSig === lastMessagesSig) return;
        lastMessagesSig = renderSig;

        notifyNewMessages(displayEntries);
        lastNotifiedMsgId = displayEntries.at(-1)?.msg_id || lastNotifiedMsgId;
        initialLoadDone = true;

        const root = document.getElementById("messages");
        if (!displayEntries.length) {
          _renderedIds.clear();
          root.innerHTML = emptyConversationHTML();
          renderThinkingIndicator();
          syncCameraModeReplies();
          updateScrollBtn();
          return;
        }

        const preserveScrollTop = forceScroll ? null : timeline.scrollTop;
        let scrollAnchor = null;
        if (!forceScroll) {
          const tRect = timeline.getBoundingClientRect();
          for (const el of timeline.querySelectorAll("[data-msgid]")) {
            const mid = String(el.dataset.msgid || "");
            if (!mid) continue;
            const r = el.getBoundingClientRect();
            if (r.bottom <= tRect.top + 0.5) continue;
            if (r.top >= tRect.bottom - 0.5) break;
            scrollAnchor = { msgId: mid, vpTop: r.top - tRect.top };
            break;
          }
        }

        const displayIdSet = new Set(displayEntries.map(e => e.msg_id));
        const newEntries = displayEntries.filter(e => !previousRenderedIds.has(e.msg_id));
        const hasRemovals = previousRenderedIds.size > 0 && [...previousRenderedIds].some(id => !displayIdSet.has(id));
        const currentRenderedOrder = Array.from(root.querySelectorAll("[data-msgid]"))
          .map((node) => String(node.dataset.msgid || ""))
          .filter(Boolean);
        const nextRenderedOrder = displayEntries.map((entry) => String(entry.msg_id || ""));
        const nextIncrementalOrder = currentRenderedOrder
          .filter((id) => displayIdSet.has(id))
          .concat(newEntries.map((entry) => String(entry.msg_id || "")));
        const canIncrementallyTrimAndAppend = !forceFullRender
          && previousRenderedIds.size > 0
          && newEntries.length > 0
          && nextIncrementalOrder.length === nextRenderedOrder.length
          && nextIncrementalOrder.every((id, idx) => id === nextRenderedOrder[idx]);

        const isInitialBulkLoad =
          previousRenderedIds.size === 0
          && newEntries.length > 0
          && newEntries.length === displayEntries.length
          && displayEntries.length > 1;
        const shouldMarkNewRowsAnimated =
          newEntries.length > 0
          && !isInitialBulkLoad
          && (previousRenderedIds.size > 0 || displayEntries.length === 1);

        let pendingStreamRowCleanups = [];
        if (canIncrementallyTrimAndAppend) {
          if (hasRemovals) {
            root.querySelectorAll("[data-msgid]").forEach((node) => {
              const msgId = String(node.dataset.msgid || "");
              if (msgId && !displayIdSet.has(msgId)) node.remove();
            });
          }
          const frag = document.createDocumentFragment();
          const pendingRowCleanup = [];
          for (const entry of newEntries) {
            const entryMsgId = String(entry?.msg_id || "");
            const tmpl = document.createElement("template");
            tmpl.innerHTML = buildMsgHTML(entry, {
              hideMetaRow: entryMsgId ? thinkingMetaHiddenIds.has(entryMsgId) : false,
            });
            const row = tmpl.content.firstElementChild;
            if (row) {
              row.classList.add("animate-in");
              const stream = entryQualifiesForStreamReveal(entry);
              if (stream) row.classList.add("streaming-body-reveal");
              pendingRowCleanup.push({ row, stream });
            }
            frag.appendChild(tmpl.content);
          }
          root.appendChild(frag);
          _renderedIds = displayIdSet;
          postRenderScope(root);
          pendingStreamRowCleanups = pendingRowCleanup;
        } else {
          root.innerHTML = displayEntries.map((entry) => {
            const entryMsgId = String(entry?.msg_id || "");
            return buildMsgHTML(entry, {
              hideMetaRow: entryMsgId ? thinkingMetaHiddenIds.has(entryMsgId) : false,
            });
          }).join("");
          _renderedIds = new Set(displayEntries.map(e => e.msg_id));
          const pendingFullRowCleanup = [];
          if (shouldMarkNewRowsAnimated) {
            const newEntryById = new Map(newEntries.map((e) => [String(e.msg_id || ""), e]));
            root.querySelectorAll("[data-msgid]").forEach((row) => {
              const msgId = String(row.dataset.msgid || "");
              const entry = newEntryById.get(msgId);
              if (!msgId || !entry) return;
              row.classList.add("animate-in");
              const stream = entryQualifiesForStreamReveal(entry);
              if (stream) row.classList.add("streaming-body-reveal");
              pendingFullRowCleanup.push({ row, stream });
            });
          }
          postRenderScope(root);
          pendingStreamRowCleanups = pendingFullRowCleanup;
        }

        queueStableCodeBlockSync(root);
        pendingStreamRowCleanups.forEach(({ row, stream }) => {
          if (stream) applyCharStreamRevealToRow(row);
          scheduleAnimateInCleanup(row, { streamBody: stream });
        });
        renderThinkingIndicator();
        syncCameraModeReplies();

        // Poll refreshes: keep the same document offset (do not follow new bottom).
        // When previously scrolled to max, new rows extend below the fold so the viewport looks unchanged.
        if (shouldStick) {
          _pollScrollLockTop = null;
          _pollScrollAnchor = null;
          _programmaticScroll = true;
          timeline.scrollTop = timeline.scrollHeight;
          queueMicrotask(() => { _programmaticScroll = false; });
        } else if (preserveScrollTop != null) {
          const maxTop = Math.max(0, timeline.scrollHeight - timeline.clientHeight);
          _programmaticScroll = true;
          const applied = Math.min(preserveScrollTop, maxTop);
          timeline.scrollTop = applied;
          _pollScrollLockTop = applied;
          _pollScrollAnchor = scrollAnchor;
          queueMicrotask(() => { _programmaticScroll = false; });
          requestAnimationFrame(() => {
            requestAnimationFrame(maybeRestorePollScrollLock);
          });
          settleScrollLockFrames(36);
        }
        _stickyToBottom = isNearBottom();
        updateScrollBtn();
        requestCenteredMessageRowUpdate();
        {
          const input = document.getElementById("message");
          const sendBtnEl = document.querySelector(".send-btn");
          const micBtnEl = document.getElementById("micBtn");
          const hasText = !!(input && input.value.trim().length > 0);
          if (sessionLaunchPending || !sessionActive) {
            if (sendBtnEl) sendBtnEl.classList.remove("visible");
            if (micBtnEl) micBtnEl.classList.remove("hidden");
          } else {
            if (sendBtnEl) sendBtnEl.classList.toggle("visible", hasText);
            if (micBtnEl) micBtnEl.classList.toggle("hidden", hasText);
          }
        }
      } catch (err) {
        console.error("chat render failed; using fallback renderer", err);
        try {
          const root = document.getElementById("messages");
          if (!root) return;
          const fallbackBaseEntries = Array.isArray(data?.entries) ? data.entries : [];
          const fallbackEntries = mergeEntriesById(olderEntries, fallbackBaseEntries).slice(-INITIAL_MESSAGE_WINDOW);
          if (!fallbackEntries.length) {
            _renderedIds.clear();
            root.innerHTML = emptyConversationHTML();
            updateScrollBtn();
            return;
          }
          root.innerHTML = fallbackEntries.map((entry) => buildMsgHTMLFallback(entry)).join("");
          _renderedIds = new Set(fallbackEntries.map((entry) => String(entry?.msg_id || "")).filter(Boolean));
          postRenderScope(root);
          queueStableCodeBlockSync(root);
          syncCameraModeReplies();
          _stickyToBottom = isNearBottom();
          updateScrollBtn();
        } catch (fallbackErr) {
          console.error("chat fallback render failed", fallbackErr);
          const root = document.getElementById("messages");
          if (root) {
            root.innerHTML = `<div class="sysmsg-row"><span class="sysmsg-text">Rendering error. Please reload the page.</span></div>`;
          }
          _renderedIds.clear();
          syncCameraModeReplies();
          updateScrollBtn();
        }
      }
    };
    const setStatus = (text, isError = false) => {
      const node = document.getElementById("statusline");
      node.textContent = text;
      node.style.color = isError ? "#fda4af" : "";
    };
    const setReconnectStatus = (active) => {
      const node = document.getElementById("statusline");
      const current = node.textContent || "";
      if (active) {
        if (reconnectStatusVisible || !current || current === reconnectingStatusText) {
          setStatus(reconnectingStatusText);
          reconnectStatusVisible = true;
        }
        return;
      }
      if (reconnectStatusVisible || current === reconnectingStatusText) {
        setStatus("");
      }
      reconnectStatusVisible = false;
    };
    const SYNC_STATUS_SHEET_CLOSE_MS = 300;
    let syncStatusSheetCloseTimer = 0;
    let syncStatusSheetScrollY = 0;
    let syncStatusSheetScrollLocked = false;
    const clearSyncStatusSheetCloseTimer = () => {
      if (!syncStatusSheetCloseTimer) return;
      clearTimeout(syncStatusSheetCloseTimer);
      syncStatusSheetCloseTimer = 0;
    };
    const lockSyncStatusSheetScroll = () => {
      if (syncStatusSheetScrollLocked) return;
      syncStatusSheetScrollLocked = true;
      syncStatusSheetScrollY = window.scrollY || document.documentElement.scrollTop || 0;
      document.documentElement.classList.add("sync-status-sheet-active");
      document.body.classList.add("sync-status-sheet-active");
      document.body.style.top = `-${syncStatusSheetScrollY}px`;
    };
    const unlockSyncStatusSheetScroll = () => {
      if (!syncStatusSheetScrollLocked) return;
      syncStatusSheetScrollLocked = false;
      document.documentElement.classList.remove("sync-status-sheet-active");
      document.body.classList.remove("sync-status-sheet-active");
      document.body.style.top = "";
      try { window.scrollTo(0, syncStatusSheetScrollY || 0); } catch (_) { }
    };
    const ensureSyncStatusOverlay = () => {
      let overlay = document.getElementById("syncStatusOverlay");
      if (overlay) return overlay;
      overlay = document.createElement("div");
      overlay.id = "syncStatusOverlay";
      overlay.className = "sync-status-overlay";
      overlay.hidden = true;
      overlay.innerHTML = `
        <div class="sync-status-sheet">
          <div class="sync-status-sheet-panel">
            <div class="sync-status-sheet-nav">
              <div class="sync-status-sheet-pill"></div>
              <div class="sync-status-sheet-nav-bar">
                <div class="sync-status-sheet-title">Sync Status</div>
                <button type="button" class="sync-status-sheet-close" aria-label="Close sync status">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            </div>
            <div class="sync-status-sheet-content"></div>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      overlay.addEventListener("click", (event) => {
        if (event.target !== overlay) return;
        closeSyncStatusPanel();
      });
      const closeBtn = overlay.querySelector(".sync-status-sheet-close");
      closeBtn?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        closeSyncStatusPanel();
      });
      return overlay;
    };
    const setSyncStatusLoading = (overlay) => {
      const content = overlay.querySelector(".sync-status-sheet-content");
      if (!content) return;
      content.innerHTML = `<div class="hub-page-menu-item inline-loading-row" style="cursor:default;opacity:0.72;padding:10px 0">${loadingIndicatorHtml("Loading…")}</div>`;
    };
    const closeSyncStatusPanel = ({ immediate = false } = {}) => {
      const overlay = document.getElementById("syncStatusOverlay");
      if (!overlay) return;
      clearSyncStatusSheetCloseTimer();
      overlay.classList.remove("open");
      if (immediate) {
        overlay.classList.remove("sheet-closing");
        overlay.hidden = true;
        unlockSyncStatusSheetScroll();
        return;
      }
      overlay.classList.add("sheet-closing");
      syncStatusSheetCloseTimer = setTimeout(() => {
        syncStatusSheetCloseTimer = 0;
        overlay.classList.remove("sheet-closing");
        overlay.hidden = true;
        unlockSyncStatusSheetScroll();
      }, SYNC_STATUS_SHEET_CLOSE_MS);
    };
    const showSyncStatusPanel = async () => {
      const overlay = ensureSyncStatusOverlay();
      clearSyncStatusSheetCloseTimer();
      lockSyncStatusSheetScroll();
      setSyncStatusLoading(overlay);
      overlay.hidden = false;
      overlay.classList.remove("sheet-closing");
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          overlay.classList.add("open");
        });
      });
      const content = overlay.querySelector(".sync-status-sheet-content");
      if (!content) return;
      try {
        const res = await fetch((CHAT_BASE_PATH || "") + "/sync-status");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const syncItems = Array.isArray(data) ? data : [];
        const formatBytes = (bytes) => {
          const value = Number(bytes);
          if (!Number.isFinite(value) || value < 0) return "-";
          if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} MB`;
          if (value >= 1024) return `${Math.round(value / 1024)} KB`;
          return `${value} B`;
        };
        let html = '<div class="sync-status-section-header">Sync Status</div>';
        if (!syncItems.length) {
          html += '<div class="sync-status-empty">No agent cursors found</div>';
        }
        for (const a of syncItems) {
          const isRunning = currentAgentStatuses[a.agent] === "running";
          const iconUrl = agentIconSrc(a.agent);
          const detailRows = [
            { label: "path", value: a.log_path || "-" },
            { label: "offset", value: a.log_path ? String(a.offset ?? "-") : "-" },
            { label: "size", value: a.log_path ? formatBytes(a.file_size) : "-" },
            { label: "session", value: a.session_id || "-" },
            { label: "last msg", value: a.last_msg_id || "-" },
            { label: "first seen", value: a.first_seen_ts || "-" },
          ];
          html += `
            <div class="sync-status-agent-block">
              <div class="sync-status-row sync-status-row-head">
                <div class="sync-status-row-left">
                  <div class="sync-status-row-icon" style="-webkit-mask-image:url(\'${escapeHtml(iconUrl)}\');mask-image:url(\'${escapeHtml(iconUrl)}\')"></div>
                  <div class="sync-status-row-label">${escapeHtml(a.agent)}</div>
                  <div class="sync-status-agent-status-dot ${isRunning ? "running" : ""}"></div>
                </div>
                <div class="sync-status-row-value">${isRunning ? "running" : "idle"}</div>
              </div>
              ${detailRows.map((row) => `
                <div class="sync-status-row sync-status-row-detail">
                  <div class="sync-status-row-label">${escapeHtml(row.label)}</div>
                  <div class="sync-status-row-value">${escapeHtml(String(row.value))}</div>
                </div>
              `).join("")}
            </div>
          `;
        }
        content.innerHTML = `<div class="sync-status-list">${html}</div>`;
      } catch (error) {
        content.innerHTML = `<div class="sync-status-error">Failed to load sync status: ${escapeHtml(String(error?.message || error || "unknown error"))}</div>`;
      }
    };
    const agentActionCandidates = (mode) => {
      if (mode === "add") return ALL_BASE_AGENTS.filter(Boolean);
      return (availableTargets || []).filter((agent) => agent && agent !== "others");
    };
    const performAgentAction = async (mode, selected) => {
      if (!selected) return;
      const adding = mode === "add";
      setStatus(`${adding ? "adding" : "removing"} ${selected}...`);
      try {
        const res = await fetch(adding ? "/add-agent" : "/remove-agent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agent: selected }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) {
          throw new Error(data.error || `failed to ${adding ? "add" : "remove"} agent`);
        }
        await new Promise((resolve) => setTimeout(resolve, adding ? 700 : 500));
        await refreshSessionState();
        setStatus(`${selected} ${adding ? "added" : "removed"}`);
        setTimeout(() => setStatus(""), 1800);
      } catch (err) {
        setStatus(err?.message || `${adding ? "add" : "remove"} agent failed`, true);
        setTimeout(() => setStatus(""), 2600);
      }
    };
    const resetAgentActionNativeMenu = ({ clearOptions = false } = {}) => {
      const select = document.getElementById("agentActionNativeMenuSelect");
      if (!select) return;
      select.value = "";
      if (clearOptions) {
        select.innerHTML = '<option value="" disabled selected>Agent</option>';
      }
      select.style.top = "-9999px";
      select.style.left = "-9999px";
    };
    const ensureAgentActionNativeMenu = () => {
      let select = document.getElementById("agentActionNativeMenuSelect");
      if (select) return select;
      select = document.createElement("select");
      select.id = "agentActionNativeMenuSelect";
      select.setAttribute("aria-hidden", "true");
      select.tabIndex = -1;
      select.style.position = "fixed";
      select.style.top = "-9999px";
      select.style.left = "-9999px";
      select.style.width = "1px";
      select.style.height = "1px";
      select.style.opacity = "0.001";
      select.style.pointerEvents = "auto";
      select.style.appearance = "none";
      select.style.webkitAppearance = "none";
      select.style.border = "0";
      select.style.outline = "none";
      select.style.background = "transparent";
      select.style.color = "transparent";
      select.style.fontSize = "13px";
      select.style.zIndex = "1000";
      select.addEventListener("change", () => {
        const value = String(select.value || "");
        resetAgentActionNativeMenu({ clearOptions: true });
        if (!value) return;
        const sep = value.indexOf(":");
        if (sep <= 0) return;
        void performAgentAction(value.slice(0, sep), value.slice(sep + 1));
      });
      select.addEventListener("blur", () => {
        setTimeout(() => resetAgentActionNativeMenu({ clearOptions: true }), 0);
      });
      document.body.appendChild(select);
      return select;
    };
    const anchorAgentActionNativeMenu = (select) => {
      const anchor = rightMenuBtn || document.activeElement || document.body;
      const rect = anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : { left: 0, top: 0, width: 1, height: 1 };
      select.style.left = `${Math.max(0, Math.round(rect.left))}px`;
      select.style.top = `${Math.max(0, Math.round(rect.top))}px`;
      select.style.width = `${Math.max(1, Math.round(rect.width || 1))}px`;
      select.style.height = `${Math.max(1, Math.round(rect.height || 1))}px`;
    };
    const openAgentActionNativeMenu = (mode) => {
      const candidates = agentActionCandidates(mode);
      if (mode === "remove" && candidates.length <= 1) {
        resetAgentActionNativeMenu({ clearOptions: true });
        setStatus("need at least 2 agents to remove one", true);
        setTimeout(() => setStatus(""), 2400);
        return true;
      }
      if (!candidates.length) {
        resetAgentActionNativeMenu({ clearOptions: true });
        setStatus("no agents available", true);
        setTimeout(() => setStatus(""), 2200);
        return true;
      }
      const select = ensureAgentActionNativeMenu();
      const title = mode === "add" ? "Add Agent" : "Remove Agent";
      resetAgentActionNativeMenu({ clearOptions: true });
      select.innerHTML = `<option value="" disabled selected>${title}</option>` + candidates
        .map((agent) => `<option value="${mode}:${escapeHtml(agent)}">${escapeHtml(agent)}</option>`)
        .join("");
      anchorAgentActionNativeMenu(select);
      let opened = false;
      const show = () => {
        if (typeof select.showPicker === "function") {
          try { select.showPicker(); opened = true; return true; } catch (_) { }
        }
        try { select.focus({ preventScroll: true }); } catch (_) {
          try { select.focus(); } catch (_) { }
        }
        try { select.click(); opened = true; return true; } catch (_) { }
        return false;
      };
      show();
      if (!opened) {
        setTimeout(() => {
          if (!show()) {
            resetAgentActionNativeMenu({ clearOptions: true });
            setStatus("agent menu unavailable", true);
            setTimeout(() => setStatus(""), 2200);
          }
        }, 0);
      }
      return true;
    };
    const showAddAgentModal = () => {
      openAgentActionNativeMenu("add");
    };
    const showRemoveAgentModal = () => {
      openAgentActionNativeMenu("remove");
    };
    const showGitCommitModal = ({ title, subject, defaultMessage, hint }) => new Promise((resolve) => {
      let settled = false;
      let overlay = document.getElementById("gitFileCommitOverlay");
      if (overlay) overlay.remove();
      overlay = document.createElement("div");
      overlay.id = "gitFileCommitOverlay";
      overlay.className = "add-agent-overlay attach-rename-overlay";
      overlay.innerHTML = `<div class="add-agent-panel attach-rename-panel"><h3>${escapeHtml(title || "Commit")}</h3><p class="attach-rename-copy">${escapeHtml(subject || "")}</p><label class="attach-rename-label" for="gitFileCommitInput">Commit message</label><input id="gitFileCommitInput" class="attach-rename-input" type="text" maxlength="200" autocapitalize="sentences" autocorrect="off" spellcheck="false" value="${escapeHtml(defaultMessage || "")}"><p class="attach-rename-hint">${escapeHtml(hint || "")}</p><div class="add-agent-actions"><button type="button" class="add-agent-cancel">Cancel</button><button type="button" class="add-agent-confirm">Commit</button></div></div>`;
      document.body.appendChild(overlay);
      const input = overlay.querySelector("#gitFileCommitInput");
      const confirmBtn = overlay.querySelector(".add-agent-confirm");
      const finish = (value) => {
        if (settled) return;
        settled = true;
        overlay.classList.remove("visible");
        setTimeout(() => {
          overlay.remove();
          resolve(value);
        }, 220);
      };
      const sync = () => {
        if (confirmBtn) confirmBtn.disabled = !(input?.value || "").trim();
      };
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          overlay.classList.add("visible");
          try {
            input?.focus({ preventScroll: true });
          } catch (_) {
            input?.focus();
          }
          input?.select();
        });
      });
      sync();
      overlay.addEventListener("click", (e) => { if (e.target === overlay) finish(null); });
      overlay.querySelector(".add-agent-cancel")?.addEventListener("click", () => finish(null));
      input?.addEventListener("input", sync);
      input?.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          finish(null);
          return;
        }
        if (e.key === "Enter") {
          e.preventDefault();
          if (!(input.value || "").trim()) return;
          finish(input.value.trim());
        }
      });
      confirmBtn?.addEventListener("click", () => {
        const next = (input?.value || "").trim();
        if (!next) return;
        finish(next);
      });
    });
    const showGitFileCommitModal = (filePath) => {
      const fileName = displayAttachmentFilename(filePath || "") || "file";
      return showGitCommitModal({
        title: "Commit File",
        subject: filePath || "",
        defaultMessage: `Update ${fileName}`,
        hint: "Only the currently selected file will be staged and committed.",
      });
    };
    const showGitAllCommitModal = () => {
      return showGitCommitModal({
        title: "Commit All Files",
        subject: "All current uncommitted changes",
        defaultMessage: "Update worktree",
        hint: "All currently uncommitted files will be staged and committed together.",
      });
    };
    const fetchWithTimeout = async (url, options = {}, timeoutMs = 5000) => {
      let timer = null;
      let timedOut = false;
      const controller = typeof AbortController === "function" ? new AbortController() : null;
      const requestOptions = {
        cache: "no-store",
        ...options,
      };
      const upstreamSignal = options?.signal || null;
      if (controller) {
        requestOptions.signal = controller.signal;
        if (upstreamSignal) {
          if (upstreamSignal.aborted) {
            controller.abort();
          } else if (typeof upstreamSignal.addEventListener === "function") {
            upstreamSignal.addEventListener("abort", () => controller.abort(), { once: true });
          }
        }
      } else if (upstreamSignal) {
        requestOptions.signal = upstreamSignal;
      }
      const fetchPromise = fetch(url, requestOptions);
      if (!(timeoutMs > 0)) return fetchPromise;
      const timeoutPromise = new Promise((_, reject) => {
        timer = setTimeout(() => {
          timedOut = true;
          try { controller?.abort(); } catch (_) { }
          reject(new Error("request timeout"));
        }, timeoutMs);
      });
      try {
        return await Promise.race([fetchPromise, timeoutPromise]);
      } catch (err) {
        if (timedOut && err?.name === "AbortError") {
          throw new Error("request timeout");
        }
        throw err;
      } finally {
        if (timer) clearTimeout(timer);
        if (timedOut) {
          fetchPromise.catch(() => { });
        }
      }
    };
    const purgeChatAssetCaches = async () => {
      if (!("caches" in window)) return;
      const baseUrl = `${window.location.origin}${CHAT_BASE_PATH || ""}`;
      const exactUrls = new Set([
        `${baseUrl}/app.webmanifest`,
        `${baseUrl}/pwa-icon-192.png`,
        `${baseUrl}/pwa-icon-512.png`,
        `${baseUrl}/apple-touch-icon.png`,
      ]);
      const prefixUrls = [
        `${baseUrl}/chat-assets/`,
      ];
      try {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map(async (cacheName) => {
          const cache = await caches.open(cacheName);
          const requests = await cache.keys();
          await Promise.all(requests.map((request) => {
            const url = String(request?.url || "");
            if (exactUrls.has(url) || prefixUrls.some((prefix) => url.startsWith(prefix))) {
              return cache.delete(request);
            }
            return Promise.resolve(false);
          }));
        }));
      } catch (_) { }
    };
    const refreshChatServiceWorkers = async () => {
      if (!("serviceWorker" in navigator)) return;
      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map((registration) => registration.update().catch(() => undefined)));
      } catch (_) { }
    };
    const waitForChatReady = async (timeoutMs = 15000, expectedPreviousInstance = "") => {
      const deadline = Date.now() + timeoutMs;
      let sawDisconnect = false;
      while (Date.now() < deadline) {
        try {
          const sessionRes = await fetchWithTimeout(`/session-state?ts=${Date.now()}`, {}, 3500);
          if (sessionRes.ok) {
            const sessionData = await sessionRes.json();
            const instance = sessionData?.server_instance || "";
            const instanceAdvanced = !expectedPreviousInstance || (instance && instance !== expectedPreviousInstance) || sawDisconnect;
            if (instanceAdvanced) {
              const messagesRes = await fetchWithTimeout(messagesFetchUrl({ limit: 1 }), {}, 3500);
              if (messagesRes.ok) {
                const messagesData = await messagesRes.json();
                if (Array.isArray(messagesData?.entries)) {
                  const liveInstance = messagesData?.server_instance || instance;
                  if (liveInstance) currentServerInstance = liveInstance;
                  return true;
                }
              }
            }
          }
        } catch (_) {
          sawDisconnect = true;
        }
        await sleep(250);
      }
      return false;
    };
    const navigateToFreshChat = () => {
      const params = new URLSearchParams(window.location.search);
      params.set("follow", followMode ? "1" : "0");
      params.set("launch_shell", "1");
      params.set("ts", String(Date.now()));
      window.location.replace(`${window.location.pathname}?${params.toString()}`);
    };
    const mergeRefreshOptions = (current = {}, next = {}) => {
      const currentOptions = current || {};
      const nextOptions = next || {};
      return {
        forceScroll: !!(currentOptions.forceScroll || nextOptions.forceScroll),
        forceFullRender: !!(currentOptions.forceFullRender || nextOptions.forceFullRender),
      };
    };
    const rerenderCurrentMessages = () => {
      if (!latestPayloadData) return;
      lastMessagesSig = "";
      render(latestPayloadData, { forceFullRender: true });
    };
    const ensurePublicDeferredObserver = () => {
      if (!isPublicChatView || publicDeferredObserver || typeof IntersectionObserver !== "function") return;
      publicDeferredObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const button = entry.target.closest("[data-load-full-message]") || entry.target.querySelector("[data-load-full-message]");
          if (!button) return;
          void loadFullMessageEntry(button.dataset.loadFullMessage || "", button);
        });
      }, {
        root: timeline,
        rootMargin: "220px 0px 220px 0px",
        threshold: 0.01,
      });
    };
    const observeDeferredMessages = (scope) => {
      if (!isPublicChatView) return;
      ensurePublicDeferredObserver();
      if (!publicDeferredObserver) return;
      (scope || document).querySelectorAll("[data-load-full-message]").forEach((button) => {
        const msgId = String(button.dataset.loadFullMessage || "");
        if (!msgId || publicFullEntryCache.has(msgId) || publicDeferredLoading.has(msgId)) return;
        publicDeferredObserver.observe(button);
      });
    };
