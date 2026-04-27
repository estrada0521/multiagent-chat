    let lastMessagesSig = "";
    let lastMessagesEtag = "";
    let initialLoadDone = false;
    let lastNotifiedMsgId = "";
    let soundEnabled = __CHAT_SOUND_ENABLED__;
    let _audioCtx = null;
    let _notificationBuffers = [];
    let _notificationManifest = [];
    let _notificationManifestPromise = null;
    let _notificationBufferPromise = null;
    let _commitSoundBuffer = null;
    let _commitSoundPromise = null;
    let _audioPrimed = false;
    let _lastSoundAt = 0;
    const SOUND_COOLDOWN_MS = 700;
    const NOTIFICATION_SOUNDS_URL = "/notify-sounds";
    const notificationSoundUrl = (name) => `/notify-sound?name=${encodeURIComponent(name)}`;
    const ensureNotificationManifest = async () => {
      if (_notificationManifest.length) return _notificationManifest;
      if (_notificationManifestPromise) return _notificationManifestPromise;
      _notificationManifestPromise = fetch(NOTIFICATION_SOUNDS_URL)
        .then((res) => {
          if (!res.ok) throw new Error(`notify manifest http ${res.status}`);
          return res.json();
        })
        .then((items) => {
          _notificationManifest = Array.isArray(items) ? items.filter((item) => typeof item === "string" && item) : [];
          return _notificationManifest;
        })
        .catch((err) => {
          console.warn("notify manifest fallback", err);
          _notificationManifest = [];
          return _notificationManifest;
        })
        .finally(() => {
          _notificationManifestPromise = null;
        });
      return _notificationManifestPromise;
    };
    const ensureNotificationBuffer = async () => {
      if (_notificationBuffers.length || !_audioCtx) return _notificationBuffers;
      if (_notificationBufferPromise) return _notificationBufferPromise;
      _notificationBufferPromise = Promise.resolve()
        .then(async () => {
          const names = await ensureNotificationManifest();
          if (!names.length) return [];
          const decoded = [];
          for (const name of names) {
            try {
              const res = await fetch(notificationSoundUrl(name));
              if (!res.ok) continue;
              const buf = await res.arrayBuffer();
              decoded.push(await _audioCtx.decodeAudioData(buf.slice(0)));
            } catch (_) { }
          }
          _notificationBuffers = decoded;
          return decoded;
        })
        .catch((err) => {
          console.warn("notify sound fallback", err);
          return [];
        })
        .finally(() => {
          _notificationBufferPromise = null;
        });
      return _notificationBufferPromise;
    };
    const ensureCommitSoundBuffer = async () => {
      if (_commitSoundBuffer || !_audioCtx) return _commitSoundBuffer;
      if (_commitSoundPromise) return _commitSoundPromise;
      _commitSoundPromise = fetch(notificationSoundUrl("commit.ogg"))
        .then(async (res) => {
          if (!res.ok) return null;
          const buf = await res.arrayBuffer();
          _commitSoundBuffer = await _audioCtx.decodeAudioData(buf.slice(0));
          return _commitSoundBuffer;
        })
        .catch(() => null)
        .finally(() => { _commitSoundPromise = null; });
      return _commitSoundPromise;
    };
    let _commitBlobActive = false;
    const playCommitSound = () => {
      if (!_audioPrimed || !_audioCtx || !_commitSoundBuffer) return;
      if (_commitBlobActive) return;
      try {
        if (_audioCtx.state === "suspended") { _audioCtx.resume().catch(() => { }); return; }
        _commitBlobActive = true;
        const analyser = _audioCtx.createAnalyser();
        analyser.fftSize = 256;
        const freqData = new Uint8Array(analyser.frequencyBinCount);
        const src = _audioCtx.createBufferSource();
        src.buffer = _commitSoundBuffer;
        src.connect(analyser);
        analyser.connect(_audioCtx.destination);
        // Create floating container
        const wrap = document.createElement("div");
        wrap.className = "commit-blob-wrap";
        const cv = document.createElement("canvas");
        const SIZE = 60;
        const dpr = Math.max(1, devicePixelRatio || 1);
        cv.width = Math.round(SIZE * dpr);
        cv.height = Math.round(SIZE * dpr);
        cv.style.width = SIZE + "px";
        cv.style.height = SIZE + "px";
        wrap.appendChild(cv);
        document.body.appendChild(wrap);
        requestAnimationFrame(() => wrap.classList.add("visible"));
        const ctx = cv.getContext("2d");
        const N = 24;
        let playing = true;
        let frame = 0;
        const bands = [0, 0, 0, 0];
        const draw = () => {
          const W = cv.width, H = cv.height;
          ctx.clearRect(0, 0, W, H);
          const cx = W / 2, cy = H / 2;
          const baseR = Math.min(W, H) * 0.34;
          if (playing) {
            analyser.getByteFrequencyData(freqData);
            const binCount = freqData.length;
            const quarter = Math.floor(binCount / 4);
            for (let b = 0; b < 4; b++) {
              let sum = 0;
              for (let i = b * quarter; i < (b + 1) * quarter; i++) sum += freqData[i];
              const avg = sum / quarter / 255;
              bands[b] += (avg - bands[b]) * 0.25;
            }
          } else {
            for (let b = 0; b < 4; b++) bands[b] *= 0.9;
          }
          const t = frame * 0.016;
          frame++;
          const pts = [];
          for (let i = 0; i < N; i++) {
            const angle = (i / N) * Math.PI * 2;
            let deform = Math.sin(angle * 2 + t * 1.2) * 0.02
              + Math.sin(angle * 3 - t * 0.9) * 0.012
              + Math.sin(angle * 5 + t * 2.1) * 0.006;
            const breath = Math.sin(t * 0.8) * baseR * 0.015;
            if (playing) {
              const bIdx = Math.floor((i / N) * 4) % 4;
              deform += bands[bIdx] * 0.35 + bands[(bIdx + 1) % 4] * 0.15;
            }
            const r = (baseR + breath) * (1 + deform);
            pts.push([cx + Math.cos(angle) * r, cy + Math.sin(angle) * r]);
          }
          ctx.beginPath();
          for (let i = 0; i < N; i++) {
            const p0 = pts[(i - 1 + N) % N], p1 = pts[i], p2 = pts[(i + 1) % N], p3 = pts[(i + 2) % N];
            const cp1x = p1[0] + (p2[0] - p0[0]) / 6, cp1y = p1[1] + (p2[1] - p0[1]) / 6;
            const cp2x = p2[0] - (p3[0] - p1[0]) / 6, cp2y = p2[1] - (p3[1] - p1[1]) / 6;
            if (i === 0) ctx.moveTo(p1[0], p1[1]);
            ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]);
          }
          ctx.closePath();
          const alpha = playing ? 0.3 + bands[0] * 0.3 : 0.15;
          const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseR * 1.2);
          grad.addColorStop(0, "rgba(252,252,252," + (alpha * 1.2).toFixed(3) + ")");
          grad.addColorStop(1, "rgba(200,200,200," + (alpha * 0.4).toFixed(3) + ")");
          ctx.fillStyle = grad;
          ctx.fill();
          ctx.strokeStyle = "rgba(252,252,252," + (playing ? 0.2 + bands[1] * 0.3 : 0.08).toFixed(3) + ")";
          ctx.lineWidth = 1;
          ctx.stroke();
          if (playing && bands[0] > 0.05) {
            ctx.save();
            ctx.globalAlpha = Math.min(0.12, bands[0] * 0.15);
            ctx.filter = "blur(" + Math.round(6 + bands[0] * 10) + "px)";
            ctx.fillStyle = "rgba(252,252,252,1)";
            ctx.fill();
            ctx.restore();
          }
        };
        let animFrame = 0;
        const tick = () => { draw(); animFrame = requestAnimationFrame(tick); };
        tick();
        src.onended = () => {
          playing = false;
          setTimeout(() => {
            wrap.classList.remove("visible");
            wrap.addEventListener("transitionend", () => {
              cancelAnimationFrame(animFrame);
              wrap.remove();
              _commitBlobActive = false;
            }, { once: true });
            // Fallback removal
            setTimeout(() => { cancelAnimationFrame(animFrame); wrap.remove(); _commitBlobActive = false; }, 1000);
          }, 400);
        };
        src.start();
      } catch (_) { _commitBlobActive = false; }
    };
    // iOS audio unlock: must call during user gesture
    const primeSound = async () => {
      try {
        if (!_audioCtx) {
          _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (_audioCtx.state === "suspended") {
          await _audioCtx.resume();
        }
        if (!_audioPrimed) {
          // Play a silent 1-sample buffer to unlock AudioContext on iOS
          const silentBuf = _audioCtx.createBuffer(1, 1, _audioCtx.sampleRate);
          const src = _audioCtx.createBufferSource();
          src.buffer = silentBuf;
          src.connect(_audioCtx.destination);
          src.start();
          _audioPrimed = true;
        }
        await ensureNotificationBuffer();
        await ensureCommitSoundBuffer();
        loadScheduledSounds();
      } catch (e) { console.error("Audio prime failed", e); }
    };
    const playNotificationSound = () => {
      if (!soundEnabled || !_audioPrimed || !_audioCtx) return;
      if (!_notificationBuffers.length) return;
      const now = Date.now();
      if (now - _lastSoundAt < SOUND_COOLDOWN_MS) return;
      _lastSoundAt = now;
      try {
        if (_audioCtx.state === "suspended") { _audioCtx.resume().catch(() => { }); return; }
        const s = _audioCtx.createBufferSource();
        s.buffer = _notificationBuffers[Math.floor(Math.random() * _notificationBuffers.length)];
        s.connect(_audioCtx.destination);
        s.start();
      } catch (_) { }
    };
    // Resume AudioContext when page comes back to foreground
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && _audioCtx && _audioCtx.state === "suspended") {
        _audioCtx.resume().catch(() => { });
      }
    });
    // --- Scheduled sound auto-play ---
    // Files named like "HH-MM.ogg" (e.g. 20-30.ogg, 8-00.ogg, 1-00.ogg) play at that time daily.
    const _scheduledSoundsPlayed = new Set();
    const _scheduledSoundFiles = [];
    let _scheduledSoundsLoaded = false;
    const loadScheduledSounds = async () => {
      if (_scheduledSoundsLoaded) return;
      _scheduledSoundsLoaded = true;
      try {
        const res = await fetch("/notify-sounds-all");
        if (!res.ok) return;
        const all = await res.json();
        if (!Array.isArray(all)) return;
        const pat = /^(\d{1,2})-(\d{2})\.ogg$/;
        for (const name of all) {
          const m = pat.exec(name);
          if (m) {
            _scheduledSoundFiles.push({ name, hour: parseInt(m[1], 10), minute: parseInt(m[2], 10) });
          }
        }
      } catch (_) { }
    };
    const checkScheduledSounds = async () => {
      if (!_audioPrimed || !_audioCtx || !soundEnabled) return;
      const now = new Date();
      const hh = now.getHours();
      const mm = now.getMinutes();
      for (const entry of _scheduledSoundFiles) {
        if (entry.hour === hh && entry.minute === mm) {
          const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
          const key = `${entry.name}:${today}`;
          if (_scheduledSoundsPlayed.has(key)) continue;
          _scheduledSoundsPlayed.add(key);
          try {
            if (_audioCtx.state === "suspended") await _audioCtx.resume();
            const res = await fetch(notificationSoundUrl(entry.name));
            if (!res.ok) continue;
            const buf = await res.arrayBuffer();
            const audioBuffer = await _audioCtx.decodeAudioData(buf.slice(0));
            const src = _audioCtx.createBufferSource();
            src.buffer = audioBuffer;
            src.connect(_audioCtx.destination);
            src.start();
          } catch (_) { }
        }
      }
    };
    setInterval(checkScheduledSounds, 15000);
    const copyIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
    const checkIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`;
    const postRenderScope = (scope) => {
      decorateLocalFileLinks(scope);
      linkifyInlineCodeFileRefs(scope);
      renderMathInScope(scope);
      renderMermaidInScope(scope);
      syncWideBlockRows(scope);
      syncUserMessageCollapse(scope);
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
    const notifyNewMessages = (displayEntries) => {
      if (!initialLoadDone || !soundEnabled) return;
      const lastSeenIndex = lastNotifiedMsgId
        ? displayEntries.findIndex((e) => e.msg_id === lastNotifiedMsgId)
        : -1;
      const newEntries = lastSeenIndex >= 0
        ? displayEntries.slice(lastSeenIndex + 1)
        : (lastNotifiedMsgId ? displayEntries.slice(-1) : []);
      if (newEntries.some((e) => e.kind === "git-commit") && soundEnabled) playCommitSound();
      const agentEntries = newEntries.filter((e) => e.sender !== "user" && e.sender !== "system");
      if (agentEntries.length > 0 && soundEnabled) {
        playNotificationSound();
      }
    };
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
      return olderEntries.length ? merged : merged.slice(-INITIAL_MESSAGE_WINDOW);
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
    const computeThinkingMetaHiddenIds = (entries) => {
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
        const hideMetaRow = !!options.hideMetaRow;
        const thinkingMetaHiddenClass = hideMetaRow ? " thinking-meta-hidden" : "";
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

        return `<article class="message-row ${cls}${kindClass}${thinkingMetaHiddenClass}" data-msgid="${msgId}" data-sender="${sender}" data-kind="${escapeHtml(entryKindRaw)}">
        <div class="message ${cls}" data-raw="${rawAttr}" data-preview="${previewAttr}">
        ${metaRowHtml}
        <div class="message-body-row">
          ${messageBodyHtml}
          ${isUser ? `<button class="user-collapse-toggle" type="button" hidden>More</button>` : ""}
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
      attachedFilesSession = currentSessionName;
      sessionActive = !!data.active;
      if (sessionActive) {
        clearDraftLaunchHints();
      }
      sessionLaunchPending = !sessionActive && (!!data.launch_pending || sessionLaunchPending || draftLaunchHintActive);
      const sessionCanInteract = canInteractWithSession();
      const resolvedTargets = normalizedSessionTargets(data.targets);
      const picker = document.getElementById("targetPicker");
      if (!picker.dataset.loaded) {
        const restoredTargets = loadTargetSelection(currentSessionName, resolvedTargets);
        selectedTargets = restoredTargets.length ? restoredTargets : [];
        saveTargetSelection(currentSessionName, selectedTargets);
        picker.dataset.loaded = "1";
        renderAgentStatus(Object.fromEntries(resolvedTargets.map((t) => [t, "idle"])));
      }
      const nextTargets = sessionCanInteract ? resolvedTargets : [];
      const nextTargetsSig = JSON.stringify(nextTargets);
      if (nextTargetsSig !== JSON.stringify(availableTargets)) {
        availableTargets = nextTargets;
        selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
        saveTargetSelection(data.session, selectedTargets);
        renderTargetPicker(availableTargets);
      }
      document.getElementById("message").disabled = !sessionActive;
      setQuickActionsDisabled(!sessionActive);
      if (sessionLaunchPending) {
        setStatus("select one initial agent and start the session");
      } else if (!sessionActive) {
        setStatus("archived session is read-only");
      }
      syncPendingLaunchControls();
      maybeAutoOpenComposer();
      updateAttachedFilesPanel(displayEntries);
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
      if (!streamBody) return;
      let streamDone = false;
      const finishStream = () => {
        if (streamDone) return;
        streamDone = true;
        unwrapStreamCharSpans(row);
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
