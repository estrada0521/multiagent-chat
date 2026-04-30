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
    let _shortcutCommandsCache = null;
    const loadShortcutCommandsOnce = async () => {
      if (_shortcutCommandsCache) return _shortcutCommandsCache;
      const r = await fetch("/shortcut-commands", { cache: "no-store" });
      if (!r.ok) throw new Error("shortcut-commands failed");
      const j = await r.json();
      const list = Array.isArray(j.commands) ? j.commands : [];
      if (!list.length) throw new Error("empty shortcut commands");
      _shortcutCommandsCache = list;
      return list;
    };
    const parseSlashCommandInput = (rawInput, list) => {
      const normalized = rawInput.trim();
      const sorted = [...list].sort((a, b) => String(b.slash || "").length - String(a.slash || "").length);
      for (const c of sorted) {
        const slash = String(c.slash || "");
        if (!slash.startsWith("/")) continue;
        if (normalized === slash) {
          return { id: c.id, arg: "" };
        }
        if (c.has_arg && normalized.startsWith(slash + " ")) {
          return { id: c.id, arg: normalized.slice(slash.length + 1) };
        }
      }
      return null;
    };
    const postShortcutCommand = async ({ command_id, arg = "" }) => {
      if (sendLocked || Date.now() - lastSubmitAt < 500) {
        return false;
      }
      sendLocked = true;
      lastSubmitAt = Date.now();
      const target = selectedTargets.join(",");
      if (!target.trim()) {
        setStatus("select at least one target", true);
        sendLocked = false;
        return false;
      }
      setQuickActionsDisabled(true);
      setStatus(`running ${command_id}...`);
      try {
        const res = await fetch("/shortcut-command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            command_id,
            arg,
            target,
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "shortcut failed");
        }
        if (data.activated) {
          clearDraftLaunchHints();
          sessionLaunchPending = false;
          sessionActive = true;
          if (Array.isArray(data.targets) && data.targets.length) {
            availableTargets = normalizedSessionTargets(data.targets);
            selectedTargets = data.targets.filter((t) => availableTargets.includes(t));
            saveTargetSelection(currentSessionName, selectedTargets);
            renderTargetPicker(availableTargets);
          }
          setQuickActionsDisabled(false);
        }
        setStatus(data.status_message || "done");
        void refresh({ forceScroll: true });
        if (data.activated || data.launch_pending) {
          void refreshSessionState();
        }
        return true;
      } catch (error) {
        setStatus(error.message, true);
        return false;
      } finally {
        setQuickActionsDisabled(!sessionActive);
        sendLocked = false;
      }
    };
    const submitMessage = async ({ closeOverlayOnStart = false, forcedText = null } = {}) => {
      if (sendLocked || Date.now() - lastSubmitAt < 500) {
        return false;
      }
      sendLocked = true;
      lastSubmitAt = Date.now();
      const message = document.getElementById("message");
      const rawInput = (forcedText != null ? forcedText : message.value).trim();
      const clearComposerDraft = () => {
        message.value = "";
        updateSendBtnVisibility();
        autoResizeTextarea();
      };
      if (rawInput.startsWith("/")) {
        let list;
        try {
          list = await loadShortcutCommandsOnce();
        } catch (err) {
          setStatus(err?.message || "shortcut commands unavailable", true);
          sendLocked = false;
          return false;
        }
        const parsed = parseSlashCommandInput(rawInput, list);
        if (!parsed) {
          setStatus("unknown shortcut", true);
          sendLocked = false;
          return false;
        }
        const arg = parsed.arg;
        setQuickActionsDisabled(true);
        if (closeOverlayOnStart && isComposerOverlayOpen()) {
          message.blur();
          closeComposerOverlay();
        }
        try {
          const res = await fetch("/shortcut-command", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              command_id: parsed.id,
              arg,
              target: selectedTargets.join(","),
            }),
          });
          const data = await res.json();
          if (!res.ok || !data.ok) {
            throw new Error(data.error || "shortcut failed");
          }
          if (data.activated) {
            clearDraftLaunchHints();
            sessionLaunchPending = false;
            sessionActive = true;
            if (Array.isArray(data.targets) && data.targets.length) {
              availableTargets = normalizedSessionTargets(data.targets);
              selectedTargets = data.targets.filter((t) => availableTargets.includes(t));
              saveTargetSelection(currentSessionName, selectedTargets);
              renderTargetPicker(availableTargets);
            }
            setQuickActionsDisabled(false);
          }
          clearComposerDraft();
          message.blur();
          if (pendingAttachments.length) {
            pendingAttachments = [];
            const row = document.getElementById("attachPreviewRow");
            if (row) { row.innerHTML = ""; row.style.display = "none"; }
          }
          closeComposerOverlay();
          _stickyToBottom = true;
          setStatus(data.status_message || "done");
          void refresh({ forceScroll: true });
          if (data.activated || data.launch_pending) {
            void refreshSessionState();
          }
          return true;
        } catch (error) {
          setStatus(error.message, true);
          return false;
        } finally {
          setQuickActionsDisabled(!sessionActive);
          sendLocked = false;
        }
      }
      let target = selectedTargets.join(",");
      const indexOnly = !target;
      const attachSuffix =
        pendingAttachments.length
          ? pendingAttachments.map((a) => "\n[Attached: " + a.path + "]").join("")
          : "";
      const messageBody = rawInput + attachSuffix;
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
      setStatus(indexOnly ? "saving note..." : `sending to ${target}...`);
      try {
        const res = await fetch("/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target, message: messageBody }),
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
            selectedTargets = data.targets.filter((t) => availableTargets.includes(t));
            saveTargetSelection(currentSessionName, selectedTargets);
            renderTargetPicker(availableTargets);
          }
          setQuickActionsDisabled(false);
        }
        clearComposerDraft();
        message.blur();
        if (pendingAttachments.length) {
          pendingAttachments = [];
          const row = document.getElementById("attachPreviewRow");
          if (row) { row.innerHTML = ""; row.style.display = "none"; }
        }
        closeComposerOverlay();
        _stickyToBottom = true;
        setStatus(
          indexOnly
            ? "note saved"
            : (data.queued
              ? (data.launch_pending ? `launching ${target}...` : `queued for ${target}`)
              : `sent to ${target}`)
        );
        void refresh({ forceScroll: true });
        if (data.activated || data.launch_pending) {
          void refreshSessionState();
        }
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
