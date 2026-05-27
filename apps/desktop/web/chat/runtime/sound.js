    let lastMessagesSig = "";
    let lastMessagesEtag = "";
    let initialLoadDone = false;
    let lastNotifiedMsgId = "";
    const copyIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
    const checkIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`;
    const postRenderScope = (scope) => {
      decorateLocalFileLinks(scope);
      renderMathInScope(scope);
      syncWideBlockRows(scope);
      syncMessageCollapse(scope);
      observeDeferredMessages(scope);
    };
    const clearFocusMsgParam = () => {
      const params = new URLSearchParams(window.location.search);
      if (!params.has(FOCUS_MSG_PARAM)) return;
      params.delete(FOCUS_MSG_PARAM);
      const nextQuery = params.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
      window.history.replaceState(window.history.state, "", nextUrl);
    };
    const notifyNewMessages = (_displayEntries) => {};
    const overrideDisplayEntry = (entry) => {
      const msgId = String(entry?.msg_id || "");
      return (msgId && publicFullEntryCache.get(msgId)) || entry;
    };
    const mergeEntriesById = (...groups) => {
      const merged = [];
      const seen = new Set();
      for (const group of groups) {
        for (const rawEntry of (group || [])) {
          const entry = overrideDisplayEntry(rawEntry);
          const msgId = String(entry?.msg_id || "");
          if (msgId) {
            if (seen.has(msgId)) continue;
            seen.add(msgId);
          }
          merged.push(entry);
        }
      }
      return merged;
    };
    const entryRenderKey = (entry) => JSON.stringify([
      String(entry?.msg_id || ""),
      String(entry?.kind || ""),
      String(entry?.deferred_body || ""),
    ]);
    const displayEntriesForData = (data) => {
      const baseEntries = Array.isArray(data?.entries) ? data.entries : [];
      const merged = mergeEntriesById(olderEntries, baseEntries);
      const visibleEntries = merged.filter((entry) => String(entry?.kind || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-") !== "agent-thinking");
      return olderEntries.length ? visibleEntries : visibleEntries.slice(-INITIAL_MESSAGE_WINDOW);
    };
    const entryTargetsSignature = (entry) => {
      const targets = Array.isArray(entry?.targets) ? entry.targets : [];
      return targets.map((target) => String(target || "").trim().toLowerCase()).filter(Boolean).sort().join("\u001f");
    };
    const entryPeerKey = (sender, targetsSig) => {
      if (!sender || sender === "system") return "";
      const targets = targetsSig ? targetsSig.split("\u001f").filter(Boolean) : [];
      if (sender === "user") {
        return targets.length === 1 ? `peer:${targets[0]}` : `targets:${targetsSig}`;
      }
      return targets.length === 1 && targets[0] === "user"
        ? `peer:${sender}`
        : `sender:${sender}:targets:${targetsSig}`;
    };
    const computeMetaHiddenIds = (entries) => {
      const hiddenIds = new Set();
      let currentPeerKey = "";
      let seenDirectionsForPeer = new Set();
      for (const entry of (entries || [])) {
        const sender = String(entry?.sender || "").trim().toLowerCase();
        const msgId = String(entry?.msg_id || "").trim();
        const targetsSig = entryTargetsSignature(entry);
        if (!sender || sender === "system") {
          continue;
        }
        const peerKey = entryPeerKey(sender, targetsSig);
        if (!peerKey) continue;
        if (peerKey !== currentPeerKey) {
          currentPeerKey = peerKey;
          seenDirectionsForPeer = new Set();
        }
        if (sender === "user") {
          continue;
        }
        const directionKey = `${sender}:${targetsSig}`;
        if (seenDirectionsForPeer.has(directionKey) && msgId) {
          hiddenIds.add(msgId);
        } else {
          seenDirectionsForPeer.add(directionKey);
        }
      }
      return hiddenIds;
    };
    const messagesFetchUrl = (extra = {}) => {
      const params = new URLSearchParams();
      params.set("ts", String(Date.now()));
      params.set("limit", String(MESSAGE_BATCH));
      if (isPublicChatView) params.set("light", "1");
      Object.entries(extra || {}).forEach(([key, value]) => {
        if (value === undefined || value === null || value === "") return;
        params.set(key, String(value));
      });
      return `/messages?${params.toString()}`;
    };
    const emphasizeSystemMessageKeyword = (escapedMessage, kind = "") => {
      const message = String(escapedMessage || "");
      if (!message) return "";
      const kindKey = String(kind || "").trim().toLowerCase();
      const patterns = [];
      if (kindKey === "git-commit") patterns.push(/^Commit\b/i);
      patterns.push(
        /^\/(?:restart|resume|add-agent|remove-agent)\b/i,
        /^(?:Restarted|Resumed|Restart|Resume)\b/i,
        /^(?:Added agent|Removed agent|Add agent|Remove agent)\b/i,
      );
      for (const pattern of patterns) {
        if (pattern.test(message)) {
          return message.replace(pattern, (matched) => `<b>${matched}</b>`);
        }
      }
      return message;
    };
    const buildMsgHTML = (entry, options = {}) => {
      try {
      const safeEntry = (entry && typeof entry === "object") ? entry : {};
      if (safeEntry.sender === "system") {
        const kindRaw = String(safeEntry.kind || "");
        const systemMessage = emphasizeSystemMessageKeyword(escapeHtml(safeEntry.message || ""), kindRaw);
        const systemTitle = systemMessage.replaceAll('"', "&quot;").replace(/<[^>]+>/g, "");
        const msgId = escapeHtml(safeEntry.msg_id || "");
        return `<div class="sysmsg-row" data-msgid="${msgId}" data-sender="system" data-kind="${escapeHtml(safeEntry.kind || "")}"><span class="sysmsg-text" title="${systemTitle}">${systemMessage}</span></div>`;
      }
      const cls = roleClass(safeEntry.sender);
      const entryKindRaw = String(safeEntry?.kind || "").trim();
      const entryKind = entryKindRaw.toLowerCase();
      const kindClass = entryKind ? ` kind-${entryKind.replace(/[^a-z0-9_-]/g, "-")}` : "";
      const entryTargets = Array.isArray(safeEntry.targets) ? safeEntry.targets : [];
      const targetIconOnly = (t) => agentBaseName(t) !== "user";
      const targetSpans = (entryTargets.length > 0
        ? entryTargets.map(t => metaAgentLabel(t, "target-name", "right", { iconOnly: targetIconOnly(t) }))
        : [metaAgentLabel("no target", "target-name", "right", { iconOnly: true })]).join(`<span class="meta-agent-sep">,</span>`);
      const body = stripSenderPrefix(safeEntry.message || "");
      const rawAttr = escapeHtml(body).replaceAll('"', "&quot;");
      const previewAttr = escapeHtml(body.slice(0, 80)).replaceAll('"', "&quot;");
      const msgId = escapeHtml(safeEntry.msg_id || "");
      const targetMeta = `<span class="targets">${targetSpans}</span>`;
      const sender = escapeHtml(safeEntry.sender || "unknown");
      const isUser = cls === "user";
      const isCollapsibleMessage = isCollapsibleMessageSender(safeEntry.sender);
      const hideMetaRow = !!options.hideMetaRow;
      const metaHiddenClass = hideMetaRow ? " meta-hidden" : "";
      const copyButtonHtml = `<button class="copy-btn" type="button" title="コピー" data-copy-icon="${escapeHtml(copyIcon).replaceAll('"', "&quot;")}" data-check-icon="${escapeHtml(checkIcon).replaceAll('"', "&quot;")}">${copyIcon}</button>`;
      const messageBodyHtml = `<div class="md-body">${renderMarkdown(body)}</div>`;
      const senderHtml = metaAgentLabel(safeEntry.sender || "unknown", "sender-label", "right", { iconOnly: true });
      const metaRowHtml = hideMetaRow
        ? ""
        : (isUser
          ? `<div class="message-meta-below user-message-meta"><span class="arrow">to</span>${targetMeta}${copyButtonHtml}</div>`
          : `<div class="message-meta-below">${senderHtml}<span class="arrow">to</span>${targetMeta}${copyButtonHtml}</div>`);
      const deferredBodyHtml = safeEntry.deferred_body && msgId
        ? `<div class="message-deferred-actions"><button class="message-deferred-btn" type="button" data-load-full-message="${msgId}">Load full message</button></div>`
        : "";

      return `<article class="message-row ${cls}${kindClass}${metaHiddenClass}" data-msgid="${msgId}" data-sender="${sender}" data-kind="${escapeHtml(entryKindRaw)}">
        <div class="message ${cls}" data-raw="${rawAttr}" data-preview="${previewAttr}">
        ${metaRowHtml}
        <div class="message-body-row">
          ${messageBodyHtml}
          ${isCollapsibleMessage ? `<button class="message-collapse-toggle" type="button" hidden>More</button>` : ""}
        </div>
        ${deferredBodyHtml}
        ${isUser ? `<div class="user-message-divider" aria-hidden="true"></div>` : ``}
        </div>
      </article>`;
      } catch (err) {
        const fallbackBody = escapeHtml(String(stripSenderPrefix(String((entry && entry.message) || "")) || ""));
        const fallbackMsgId = escapeHtml(String((entry && entry.msg_id) || ""));
        const fallbackSender = escapeHtml(String((entry && entry.sender) || "unknown"));
        return `<article class="message-row agent" data-msgid="${fallbackMsgId}" data-sender="${fallbackSender}" data-kind=""><div class="message agent"><div class="message-body-row"><div class="md-body">${fallbackBody}</div></div></div></article>`;
      }
    };
    const buildMsgHTMLFallback = (entry) => {
      const safeEntry = (entry && typeof entry === "object") ? entry : {};
      const sender = String(safeEntry.sender || "unknown");
      const senderLower = sender.toLowerCase();
      const msgId = escapeHtml(String(safeEntry.msg_id || ""));
      const kind = escapeHtml(String(safeEntry.kind || ""));
      if (senderLower === "system") {
        const body = escapeHtml(stripSenderPrefix(String(safeEntry.message || ""))).replaceAll("\n", "<br>");
        const systemMessage = emphasizeSystemMessageKeyword(body, String(safeEntry.kind || ""));
        return `<div class="sysmsg-row" data-msgid="${msgId}" data-sender="system" data-kind="${kind}"><span class="sysmsg-text">${systemMessage}</span></div>`;
      }
      try {
        return buildMsgHTML(entry, { hideMetaRow: false });
      } catch (_) {
        const body = escapeHtml(stripSenderPrefix(String(safeEntry.message || ""))).replaceAll("\n", "<br>");
        return `<article class="message-row agent" data-msgid="${msgId}" data-sender="${escapeHtml(sender)}" data-kind="${kind}">
        <div class="message agent">
          <div class="message-meta-below"><span class="sender-label">${escapeHtml(sender)}</span></div>
          <div class="message-body-row"><div class="md-body">${body}</div></div>
        </div>
      </article>`;
      }
    };
    const updateSessionUI = (data, displayEntries) => {
      currentSessionName = data.session || "";
      sessionActive = !!data.active;
      const resolvedTargets = normalizedSessionTargets(data.targets);
      const picker = document.getElementById("targetPicker");
      if (!picker.dataset.loaded) {
        const restoredTargets = loadTargetSelection(currentSessionName, resolvedTargets);
        selectedTargets = restoredTargets.length ? restoredTargets : [];
        saveTargetSelection(currentSessionName, selectedTargets);
        picker.dataset.loaded = "1";
        renderAgentStatus(Object.fromEntries(resolvedTargets.map((t) => [t, "idle"])));
      }
      const nextTargetsSig = JSON.stringify(resolvedTargets);
      if (nextTargetsSig !== JSON.stringify(availableTargets)) {
        availableTargets = resolvedTargets;
        selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
        saveTargetSelection(data.session, selectedTargets);
        renderTargetPicker(availableTargets);
      }
      document.getElementById("message").disabled = !sessionActive;
      setQuickActionsDisabled(!sessionActive);
      if (!sessionActive) {
        setStatus("archived session is read-only");
      }
      void maybeRestoreFileModalSessionState(currentSessionName);
      maybeAutoOpenComposer();
      dpOnSessionSummaryPinReload();
    };
    const scheduleAnimateInCleanup = (row, opts = {}) => {
      const streamBody = !!opts.streamBody;
      if (!row) return;
      const isUserRow = row.classList.contains("user");
      if (row._animateInCleanupTimer) {
        clearTimeout(row._animateInCleanupTimer);
        row._animateInCleanupTimer = 0;
      }
      let animateInDone = false;
      const finishAnimateIn = () => {
        if (animateInDone) return;
        animateInDone = true;
        row.classList.remove("animate-in");
      };
      const messageEl = row.querySelector(".message");
      if (messageEl) {
        messageEl.addEventListener("animationend", (event) => {
          if (event.target !== messageEl) return;
          if (!isUserRow || event.animationName !== "userMsgReveal") return;
          const divider = row.querySelector(".user-message-divider");
          if (!divider) finishAnimateIn();
        }, { once: true });
      }
      if (isUserRow) {
        const dividerEl = row.querySelector(".user-message-divider");
        dividerEl?.addEventListener("animationend", (event) => {
          if (event.target !== dividerEl) return;
          if (event.animationName !== "userDividerReveal") return;
          finishAnimateIn();
        }, { once: true });
      }
      row.addEventListener("animationend", (event) => {
        if (event.target !== row || event.animationName !== "msgReveal") return;
        finishAnimateIn();
      }, { once: true });
      row._animateInCleanupTimer = setTimeout(finishAnimateIn, 850);
      if (!streamBody) {
        if (row.isConnected) linkifyInlineCodeFileRefsImmediate(row);
        return;
      }
      let streamDone = false;
      const finishStream = () => {
        if (streamDone) return;
        streamDone = true;
        row.classList.remove("streaming-body-reveal");
        delete row._streamRevealTotalMs;
        if (row.isConnected) linkifyInlineCodeFileRefsImmediate(row);
      };
      const ms = typeof row._streamRevealTotalMs === "number" ? row._streamRevealTotalMs : 1700;
      if (ms <= 0) {
        queueMicrotask(finishStream);
      } else {
        setTimeout(finishStream, ms);
      }
    };
