    let lastRenderPrepended = false;
    let _firstContentSettleFired = false;
    const render = (data, {
      forceScroll = false,
      forceFullRender = false,
      suppressEntryAnimation = false,
    } = {}) => {
      try {
        lastRenderPrepended = false;
        const shouldStick = forceScroll || _stickyToBottom || isNearBottom();
        const displayEntries = displayEntriesForData(data);
        const metaHiddenIds = computeMetaHiddenIds(displayEntries);
        const previousRenderedIds = new Set(_renderedIds);

        updateMessageProjectionUI(displayEntries);

        const renderSig = displayEntries.map((entry) => entryRenderKey(entry)).join("\u0002");
        if (!forceScroll && renderSig === lastMessagesSig) return;
        lastMessagesSig = renderSig;

        initialLoadDone = true;

        const root = document.getElementById("messages");
        if (!displayEntries.length) {
          _renderedIds.clear();
          root.innerHTML = emptyConversationHTML();
          renderThinkingIndicator();
          updateScrollBtn();
          return;
        }

        const preserveScrollTop = shouldStick ? null : timeline.scrollTop;
        let scrollAnchor = null;
        if (!shouldStick) {
          const tRect = timeline.getBoundingClientRect();
          for (const el of timeline.querySelectorAll("[data-context-hash]")) {
            const mid = String(el.dataset.contextHash || "");
            if (!mid) continue;
            const r = el.getBoundingClientRect();
            if (r.bottom <= tRect.top + 0.5) continue;
            if (r.top >= tRect.bottom - 0.5) break;
            scrollAnchor = { contextHash: mid, vpTop: r.top - tRect.top };
            break;
          }
        }

        const displayIdSet = new Set(displayEntries.map((e) => String(e.context_hash || "")).filter(Boolean));
        const newEntries = displayEntries.filter((e) => {
          const id = String(e.context_hash || "");
          return id && !previousRenderedIds.has(id);
        });
        const hasRemovals = previousRenderedIds.size > 0 && [...previousRenderedIds].some((id) => !displayIdSet.has(String(id)));
        const currentRenderedOrder = Array.from(root.querySelectorAll("[data-context-hash]"))
          .map((node) => String(node.dataset.contextHash || ""))
          .filter(Boolean);
        const nextRenderedOrder = displayEntries.map((entry) => String(entry.context_hash || ""));
        const nextIncrementalOrder = currentRenderedOrder
          .filter((id) => displayIdSet.has(id))
          .concat(newEntries.map((entry) => String(entry.context_hash || "")));
        const canIncrementallyTrimAndAppend = !forceFullRender
          && previousRenderedIds.size > 0
          && newEntries.length > 0
          && nextIncrementalOrder.length === nextRenderedOrder.length
          && nextIncrementalOrder.every((id, idx) => id === nextRenderedOrder[idx]);
        const canIncrementallyPrepend = !forceFullRender
          && previousRenderedIds.size > 0
          && newEntries.length > 0
          && !hasRemovals
          && nextRenderedOrder.length === currentRenderedOrder.length + newEntries.length
          && newEntries.every((entry, idx) => nextRenderedOrder[idx] === String(entry.context_hash || ""))
          && currentRenderedOrder.every((id, idx) => nextRenderedOrder[idx + newEntries.length] === id);

        const isInitialBulkLoad =
          previousRenderedIds.size === 0
          && newEntries.length > 0
          && newEntries.length === displayEntries.length
          && displayEntries.length > 1;
        const shouldMarkNewRowsAnimated =
          newEntries.length > 0
          && !isInitialBulkLoad
          && !suppressEntryAnimation
          && (previousRenderedIds.size > 0 || displayEntries.length === 1);

        let pendingStreamRowCleanups = [];
        if (canIncrementallyTrimAndAppend) {
          if (hasRemovals) {
            root.querySelectorAll("[data-context-hash]").forEach((node) => {
              const contextHash = String(node.dataset.contextHash || "");
              if (contextHash && !displayIdSet.has(contextHash)) node.remove();
            });
          }
          const frag = document.createDocumentFragment();
          const pendingRowCleanup = [];
          for (const entry of newEntries) {
            const entryContextHash = String(entry?.context_hash || "");
            const tmpl = document.createElement("template");
            tmpl.innerHTML = buildMsgHTML(entry, {
              hideMetaRow: entryContextHash ? metaHiddenIds.has(entryContextHash) : false,
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
          for (const { row } of pendingRowCleanup) {
            if (row.isConnected) postRenderScope(row);
          }
          pendingStreamRowCleanups = pendingRowCleanup;
        } else if (canIncrementallyPrepend) {
          const heightBefore = timeline.scrollHeight;
          const topBefore = timeline.scrollTop;
          const frag = document.createDocumentFragment();
          const pendingRowCleanup = [];
          for (const entry of newEntries) {
            const entryContextHash = String(entry?.context_hash || "");
            const tmpl = document.createElement("template");
            tmpl.innerHTML = buildMsgHTML(entry, {
              hideMetaRow: entryContextHash ? metaHiddenIds.has(entryContextHash) : false,
            });
            const row = tmpl.content.firstElementChild;
            if (row) pendingRowCleanup.push({ row, stream: false });
            frag.appendChild(tmpl.content);
          }
          const firstMsg = root.querySelector("[data-context-hash]");
          root.insertBefore(frag, firstMsg || root.firstChild);
          _renderedIds = displayIdSet;
          for (const { row } of pendingRowCleanup) {
            if (row.isConnected) postRenderScope(row);
          }
          pendingStreamRowCleanups = pendingRowCleanup;
          void timeline.offsetHeight;
          _programmaticScroll = true;
          timeline.scrollTop = topBefore + (timeline.scrollHeight - heightBefore);
          _pollScrollLockTop = timeline.scrollTop;
          _pollScrollAnchor = scrollAnchor;
          lastRenderPrepended = true;
          queueMicrotask(() => { _programmaticScroll = false; });
        } else {
          root.innerHTML = displayEntries.map((entry) => {
            const entryContextHash = String(entry?.context_hash || "");
            return buildMsgHTML(entry, {
              hideMetaRow: entryContextHash ? metaHiddenIds.has(entryContextHash) : false,
            });
          }).join("");
          _renderedIds = displayIdSet;
          const pendingFullRowCleanup = [];
          if (shouldMarkNewRowsAnimated) {
            const newEntryById = new Map(newEntries.map((e) => [String(e.context_hash || ""), e]));
            root.querySelectorAll("[data-context-hash]").forEach((row) => {
              const contextHash = String(row.dataset.contextHash || "");
              const entry = newEntryById.get(contextHash);
              if (!contextHash || !entry) return;
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

        if (canIncrementallyPrepend) {
          _stickyToBottom = isNearBottom();
          requestAnimationFrame(() => {
            requestAnimationFrame(maybeRestorePollScrollLock);
          });
          settleScrollLockFrames(10);
        } else if (shouldStick) {
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
          settleScrollLockFrames(10);
        }
        _stickyToBottom = isNearBottom();
        updateScrollBtn();
        requestCenteredMessageRowUpdate();
        {
          const input = document.getElementById("message");
          const sendBtnEl = document.querySelector(".send-btn");
          const hasText = !!(input && input.value.trim().length > 0);
          if (!sessionActive) {
            if (sendBtnEl) sendBtnEl.classList.remove("visible");
          } else {
            if (sendBtnEl) sendBtnEl.classList.toggle("visible", hasText);
          }
        }
        // The message's final height is known the instant its row is in the DOM
        // (the char reveal is a client-side opacity animation over text that's
        // already there). Fire now so "Fit Height to Message" resizes in step
        // with the message appearing, not after the reveal finishes. Also fire
        // once on the first content render of the page so switching session or
        // reloading the chat re-fits the window.
        if (pendingStreamRowCleanups.length || !_firstContentSettleFired) {
          _firstContentSettleFired = true;
          document.dispatchEvent(new CustomEvent("chat-transcript-settled"));
        }
      } catch (err) {
        console.error("chat render failed", err);
        const root = document.getElementById("messages");
        if (root) {
          const detail = escapeHtml(String(err?.message || err));
          root.innerHTML = `<div class="sysmsg-row"><span class="sysmsg-text" style="color: var(--error);">Rendering error: ${detail}</span></div>`;
        }
        _renderedIds.clear();
        updateScrollBtn();
        notifyHubChatRenderError(err?.message || err);
        throw err;
      }
    };
    const setStatus = (text, isError = false) => {
      const node = document.getElementById("statusline");
      if (!sessionActive) {
        // Archived session: the statusline is a fixed read-only label. Nothing
        // transient (toasts, the SSE reconnect blank) gets to overwrite it.
        node.textContent = "archived session is read-only";
        node.classList.remove("is-error");
        return;
      }
      node.textContent = text;
      node.classList.toggle("is-error", isError);
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
        setStatus(`${selected} ${adding ? "added" : "removed"}`);
        setTimeout(() => setStatus(""), STATUS_TOAST_MS);
      } catch (err) {
        setStatus(err?.message || `${adding ? "add" : "remove"} agent failed`, true);
        setTimeout(() => setStatus(""), STATUS_TOAST_MS);
      }
    };
    let nativeBridgeAgentActionMode = "";
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
    const resetAgentActionMenus = () => {
      resetAgentActionNativeMenu({ clearOptions: true });
      nativeBridgeAgentActionMode = "";
    };
    const agentActionSelectIsArmed = () => {
      const select = document.getElementById("agentActionNativeMenuSelect");
      if (!select) return false;
      return select.options.length > 1 && select.style.top !== "-9999px";
    };
    const showArmedAgentActionPicker = () => {
      const select = document.getElementById("agentActionNativeMenuSelect");
      if (!select || !agentActionSelectIsArmed()) return false;
      if (typeof select.showPicker === "function") {
        try { select.showPicker(); return true; } catch (_) {}
      }
      try { select.click(); return true; } catch (_) {}
      return false;
    };
    let skipAgentMenuBlur = false;
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
        setTimeout(() => {
          if (skipAgentMenuBlur) return;
          resetAgentActionNativeMenu({ clearOptions: true });
        }, 0);
      });
      document.body.appendChild(select);
      return select;
    };
    const anchorAgentActionNativeMenu = (select) => {
      const anchor = rightMenuBtn || document.activeElement || document.body;
      if (document.documentElement.dataset.mobile === "1") {
        const rect = anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : { left: 0, top: 0, width: 1, height: 1 };
        select.style.left = `${Math.max(0, Math.round(rect.left))}px`;
        select.style.top = `${Math.max(0, Math.round(rect.top))}px`;
        select.style.width = `${Math.max(1, Math.round(rect.width || 1))}px`;
        select.style.height = `${Math.max(1, Math.round(rect.height || 1))}px`;
        return;
      }
      const rect = anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : { left: 0, top: 0, right: 0, width: 1, height: 1 };
      const gap = 8;
      const vw = window.innerWidth || document.documentElement.clientWidth || 0;
      const width = 220;
      const height = Math.max(1, Math.round(rect.height || 28));
      const rightSideLeft = Math.round((rect.right || ((rect.left || 0) + (rect.width || 1))) + gap);
      const fallbackLeft = Math.round((rect.left || 0) - width - gap);
      const left = (vw && rightSideLeft + width > vw - 8)
        ? Math.max(8, fallbackLeft)
        : Math.max(0, rightSideLeft);
      select.style.left = `${left}px`;
      select.style.top = `${Math.max(0, Math.round(rect.top || 0))}px`;
      select.style.width = `${width}px`;
      select.style.height = `${height}px`;
    };
    const openAgentActionMenu = (mode) => {
      const candidates = agentActionCandidates(mode);
      if (mode === "remove" && candidates.length <= 1) {
        resetAgentActionMenus();
        setStatus("need at least 2 agents to remove one", true);
        setTimeout(() => setStatus(""), STATUS_TOAST_MS);
        return true;
      }
      if (!candidates.length) {
        resetAgentActionMenus();
        setStatus("no agents available", true);
        setTimeout(() => setStatus(""), STATUS_TOAST_MS);
        return true;
      }
      const select = ensureAgentActionNativeMenu();
      const title = mode === "add" ? "Add Agent" : "Remove Agent";
      resetAgentActionNativeMenu({ clearOptions: true });
      select.innerHTML = `<option value="" disabled selected>${title}</option>` + candidates
        .map((agent) => `<option value="${mode}:${escapeHtml(agent)}">${escapeHtml(agent)}</option>`)
        .join("");
      anchorAgentActionNativeMenu(select);
      skipAgentMenuBlur = document.documentElement.dataset.mobile === "1";
      let opened = false;
      const show = () => {
        if (typeof select.showPicker === "function") {
          try { select.showPicker(); opened = true; return true; } catch (_) {}
        }
        try { select.focus({ preventScroll: true }); } catch (_) {
          try { select.focus(); } catch (_) {}
        }
        try { select.click(); opened = true; return true; } catch (_) {}
        return false;
      };
      show();
      if (!opened) {
        setTimeout(() => { void show(); }, 0);
      }
      return true;
    };
    const showAddAgentModal = () => {
      openAgentActionMenu("add");
    };
    const showRemoveAgentModal = () => {
      openAgentActionMenu("remove");
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
          try { controller?.abort(); } catch (_) {}
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
          fetchPromise.catch(() => {});
        }
      }
    };
__CHAT_INCLUDE:../new-chat.js__
    const mergeRefreshOptions = (current = {}, next = {}) => {
      const currentOptions = current || {};
      const nextOptions = next || {};
      return {
        forceScroll: !!(currentOptions.forceScroll || nextOptions.forceScroll),
        forceFullRender: !!(currentOptions.forceFullRender || nextOptions.forceFullRender),
        suppressEntryAnimation: !!(currentOptions.suppressEntryAnimation || nextOptions.suppressEntryAnimation),
      };
    };
    const rerenderCurrentMessages = ({ suppressEntryAnimation = false } = {}) => {
      if (!latestPayloadData) return;
      lastMessagesSig = "";
      render(latestPayloadData, { forceFullRender: true, suppressEntryAnimation });
    };
