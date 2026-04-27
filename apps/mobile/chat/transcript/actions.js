    const loadOlderMessages = async () => {
      if (olderLoading || !latestPayloadData) return;
      const firstMsgId = displayEntriesForData(latestPayloadData)[0]?.msg_id || "";
      if (!firstMsgId) {
        olderHasMore = false;
        rerenderCurrentMessages();
        return;
      }
      olderLoading = true;
      const prevHeight = timeline.scrollHeight;
      const prevTop = timeline.scrollTop;
      rerenderCurrentMessages();
      try {
        const res = await fetchWithTimeout(messagesFetchUrl({ before_msg_id: firstMsgId }));
        if (!res.ok) throw new Error("older messages unavailable");
        const data = await res.json();
        const olderBatch = Array.isArray(data?.entries) ? data.entries : [];
        olderHasMore = !!data?.has_older;
        if (olderBatch.length) {
          olderEntries = mergeEntriesById(olderBatch, olderEntries);
        }
      } catch (_) {
      } finally {
        olderLoading = false;
        rerenderCurrentMessages();
        const delta = timeline.scrollHeight - prevHeight;
        timeline.scrollTop = prevTop + delta;
        updateScrollBtn();
      }
    };
    const loadFullMessageEntry = async (msgId, button) => {
      const targetMsgId = String(msgId || "").trim();
      if (!isPublicChatView || !targetMsgId) return;
      if (publicFullEntryCache.has(targetMsgId)) {
        rerenderCurrentMessages();
        return;
      }
      if (publicDeferredLoading.has(targetMsgId)) return;
      publicDeferredLoading.add(targetMsgId);
      if (publicDeferredObserver && button) {
        try { publicDeferredObserver.unobserve(button); } catch (_) { }
      }
      if (button) {
        button.disabled = true;
        button.textContent = "Loading...";
      }
      try {
        const res = await fetch(`/message-entry?msg_id=${encodeURIComponent(targetMsgId)}`, { cache: "no-store" });
        if (!res.ok) throw new Error("message body unavailable");
        const data = await res.json().catch(() => ({}));
        if (data?.entry) {
          publicFullEntryCache.set(targetMsgId, data.entry);
          rerenderCurrentMessages();
          return;
        }
      } catch (_) {
      } finally {
        publicDeferredLoading.delete(targetMsgId);
      }
      if (button) {
        button.disabled = false;
        button.textContent = "Retry full message";
      }
    };
    const refresh = async (options = {}) => {
      const refreshOptions = (!hasInitialRefreshHydrated && followMode)
        ? mergeRefreshOptions(options, { forceScroll: true })
        : options;
      if (refreshInFlight) {
        pendingRefreshOptions = mergeRefreshOptions(pendingRefreshOptions, refreshOptions);
        return;
      }
      refreshInFlight = true;
      try {
        const requestedFocusMsgId = String(pendingFocusMsgId || readFocusMsgIdFromUrl() || "").trim();
        const useFocusedWindow = !!requestedFocusMsgId && focusWindowRequestedMsgId !== requestedFocusMsgId;
        const url = useFocusedWindow
          ? messagesFetchUrl({ around_msg_id: requestedFocusMsgId })
          : messagesFetchUrl();
        const headers = {};
        if (!useFocusedWindow && lastMessagesEtag) {
          headers["If-None-Match"] = lastMessagesEtag;
        }
        const res = await fetchWithTimeout(
          url,
          Object.keys(headers).length ? { headers } : {}
        );
        if (res.status === 304) {
          messageRefreshFailures = 0;
          setReconnectStatus(false);
          if (!hasInitialRefreshHydrated) {
            hasInitialRefreshHydrated = true;
            releaseLaunchShellGate();
          }
          notifyHubChatRenderReady();
          return;
        }
        if (!res.ok) throw new Error("messages unavailable");
        const nextMessagesEtag = res.headers.get("ETag") || "";
        if (!useFocusedWindow && nextMessagesEtag) {
          lastMessagesEtag = nextMessagesEtag;
        }
        const data = await res.json();
        if (useFocusedWindow) {
          focusWindowRequestedMsgId = requestedFocusMsgId;
          const hasFocusedEntry = Array.isArray(data?.entries)
            && data.entries.some((entry) => String(entry?.msg_id || "") === requestedFocusMsgId);
          pendingFocusMsgId = hasFocusedEntry ? requestedFocusMsgId : "";
          if (!hasFocusedEntry) {
            focusWindowRequestedMsgId = "";
            clearFocusMsgParam();
          }
        }
        const nextServerInstance = data?.server_instance || "";
        if (nextServerInstance && currentServerInstance && nextServerInstance !== currentServerInstance) {
          olderEntries = [];
          olderHasMore = false;
          publicFullEntryCache = new Map();
          publicDeferredLoading = new Set();
        }
        if (nextServerInstance) currentServerInstance = nextServerInstance;
        latestPayloadData = data;
        if (!olderEntries.length) {
          olderHasMore = !!data?.has_older;
        }
        messageRefreshFailures = 0;
        setReconnectStatus(false);
        render(data, refreshOptions);
        if (!hasInitialRefreshHydrated) {
          hasInitialRefreshHydrated = true;
          releaseLaunchShellGate();
        }
        notifyHubChatRenderReady();
      } catch (_) {
        messageRefreshFailures += 1;
        if (followMode && messageRefreshFailures >= 3) {
          setReconnectStatus(true);
        }
      } finally {
        refreshInFlight = false;
        if (pendingRefreshOptions) {
          const nextOptions = pendingRefreshOptions;
          pendingRefreshOptions = null;
          queueMicrotask(() => refresh(nextOptions));
        }
      }
    };
    timeline.addEventListener("click", async (event) => {
      const fullBtn = event.target.closest("[data-load-full-message]");
      if (fullBtn) {
        event.preventDefault();
        await loadFullMessageEntry(fullBtn.dataset.loadFullMessage || "", fullBtn);
      }
    });
    const logSystem = (message) => fetch("/log-system", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const showProviderEventsModal = async (msgId) => {
      const targetMsgId = String(msgId || "").trim();
      if (!targetMsgId) return;
      let payload = null;
      try {
        const res = await fetch(`/normalized-events?msg_id=${encodeURIComponent(targetMsgId)}`, { cache: "no-store" });
        if (!res.ok) throw new Error("normalized events unavailable");
        payload = await res.json();
      } catch (err) {
        setStatus(err?.message || "normalized events unavailable", true);
        setTimeout(() => setStatus(""), 2200);
        return;
      }
      let overlay = document.getElementById("providerEventsOverlay");
      if (overlay) overlay.remove();
      const entry = payload?.entry || {};
      const events = Array.isArray(payload?.events) ? payload.events : [];
      const rendered = events.length
        ? events.map((event) => JSON.stringify(event, null, 2)).join("\n\n")
        : (payload?.missing ? "[normalized event log missing]" : "[no normalized events]");
      overlay = document.createElement("div");
      overlay.id = "providerEventsOverlay";
      overlay.className = "add-agent-overlay provider-events-overlay";
      overlay.innerHTML = `<div class="add-agent-panel provider-events-panel"><div class="provider-events-header"><div><h3 class="provider-events-title">Normalized Events</h3><p class="provider-events-meta">${escapeHtml([
        entry.provider_adapter || "",
        entry.provider_model || "",
        payload?.path ? `path: ${payload.path}` : "",
        entry.run_id ? `run: ${entry.run_id}` : "",
      ].filter(Boolean).join("\n"))}</p></div><button type="button" class="provider-events-close" aria-label="Close">×</button></div><pre class="provider-events-pre">${escapeHtml(rendered)}</pre></div>`;
      document.body.appendChild(overlay);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => overlay.classList.add("visible"));
      });
      const closeModal = () => {
        overlay.classList.remove("visible");
        setTimeout(() => overlay.remove(), 420);
      };
      overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
      overlay.querySelector(".provider-events-close")?.addEventListener("click", closeModal);
    };
    const submitMessage = async ({ overrideMessage = null, overrideTarget = null, raw = false, closeOverlayOnStart = false } = {}) => {
      if (sendLocked || Date.now() - lastSubmitAt < 500) {
        return false;
      }
      sendLocked = true;
      lastSubmitAt = Date.now();
      const message = document.getElementById("message");
      const rawInput = (overrideMessage ?? message.value).trim();
      const clearComposerDraft = () => {
        message.value = "";
        updateSendBtnVisibility();
        autoResizeTextarea();
      };
      const memoMatch = !overrideMessage && rawInput.match(/^\/memo(?:\s+([\s\S]*))?$/);
      if (memoMatch) {
        overrideMessage = (memoMatch[1] || "").trim();
        overrideTarget = "user";
      }
      const paneDirectMatch = !overrideMessage && !memoMatch && rawInput.match(/^\/(model|up|down)(?:\s+(\d+))?$/);
      if (paneDirectMatch) {
        const cmd = paneDirectMatch[1];
        const count = Math.max(1, Math.min(parseInt(paneDirectMatch[2] || "1", 10) || 1, 100));
        overrideMessage = (cmd === "up" || cmd === "down") ? `${cmd} ${count}` : cmd;
      }
      const paneShortcutSlashMatch = !overrideMessage && !memoMatch && rawInput.match(/^\/(restart|resume|interrupt|enter|ctrlc)$/i);
      if (paneShortcutSlashMatch) {
        overrideMessage = paneShortcutSlashMatch[1].toLowerCase();
      }
      const payload = overrideMessage !== null ? overrideMessage : rawInput;
      let target = overrideTarget ?? selectedTargets.join(",");
      const shortcutMeta = parseControlShortcut(payload);
      const shortcut = shortcutMeta?.name || "";
      const isShortcut = !!shortcutMeta;
      const paneOnlyShortcuts = new Set(["interrupt", "ctrlc", "enter", "restart", "resume", "model", "up", "down"]);
      if (!target && shortcut !== "save") {
        if (isShortcut && paneOnlyShortcuts.has(shortcut)) {
          setStatus("select at least one target", true);
          sendLocked = false;
          return false;
        }
        target = "user";
      }
      const attachSuffix =
        !isShortcut && pendingAttachments.length
          ? pendingAttachments.map((a) => "\n[Attached: " + a.path + "]").join("")
          : "";
      const messageBody = (isShortcut ? payload : payload) + attachSuffix;
      if (memoMatch && !payload && !pendingAttachments.length) {
        setStatus("/memo needs text or an Import attachment", true);
        sendLocked = false;
        return false;
      }
      if (!messageBody.trim()) {
        setStatus("message is required", true);
        sendLocked = false;
        return false;
      }
      setQuickActionsDisabled(true);
      if (closeOverlayOnStart && isComposerOverlayOpen()) {
        message.blur();
        closeComposerOverlay();
      }
      const shortcutDisplay = shortcutLabel(shortcut || payload);
      const shortcutScope = (shortcut && shortcut !== "save") && target ? ` for ${target}` : "";
      const shortcutCountSuffix = (shortcutMeta && shortcutMeta.repeat && shortcutMeta.repeat > 1 && (shortcut === "up" || shortcut === "down"))
        ? ` x${shortcutMeta.repeat}`
        : "";
      setStatus(
        isShortcut
          ? `running ${shortcutDisplay}${shortcutCountSuffix}${shortcutScope}...`
          : `sending to ${target}...`
      );
      try {
        const res = await fetch("/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target,
            message: messageBody,
            ...(raw ? { raw: true } : {}),
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "send failed");
        }
        if (data.activated) {
          clearDraftLaunchHints();
          sessionLaunchPending = false;
          sessionActive = true;
          if (Array.isArray(data.targets) && data.targets.length) {
            availableTargets = normalizedSessionTargets(data.targets);
            selectedTargets = data.targets.filter((target) => availableTargets.includes(target));
            saveTargetSelection(currentSessionName, selectedTargets);
            renderTargetPicker(availableTargets);
          }
          setQuickActionsDisabled(false);
        }
        if (!overrideMessage || memoMatch || paneDirectMatch || paneShortcutSlashMatch) {
          clearComposerDraft();
          if (pendingAttachments.length) {
            pendingAttachments = [];
            const row = document.getElementById("attachPreviewRow");
            if (row) { row.innerHTML = ""; row.style.display = "none"; }
          }
          if (!shortcutMeta?.keepComposerOpen) message.blur();
          if (!shortcutMeta?.keepComposerOpen) closeComposerOverlay();
          _stickyToBottom = true;
        }
        setStatus(
          isShortcut
            ? `${shortcutDisplay}${shortcutCountSuffix}${shortcutScope} completed`
            : `sent to ${target}`
        );
        if (shortcut === "save") {
          await logSystem("Save Log");
          setTimeout(() => setStatus(""), 2000);
        }
        await refresh({ forceScroll: true });
        return true;
      } catch (error) {
        setStatus(error.message, true);
        return false;
      } finally {
        setQuickActionsDisabled(!sessionActive);
        sendLocked = false;
      }
    };
    document.getElementById("composer").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!canComposeInSession()) {
        setStatus(sessionLaunchPending ? "start the session first" : "archived session is read-only", true);
        return;
      }
      const submitter = event.submitter;
      const closeOverlayOnStart = !!(submitter && submitter.classList && submitter.classList.contains("send-btn"));
      await submitMessage({ closeOverlayOnStart });
    });
    const quickMore = document.querySelector(".quick-more");
    const composerPlusMenu = document.getElementById("composerPlusMenu");
    const hubBtn = document.getElementById("hubPageTitleLink");
