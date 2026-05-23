    let currentAgentStatuses = {};
    let currentAgentRuntime = {};
    let currentProviderRuntime = {};
    const THINKING_RUNTIME_AGE_TICK_MS = 1000;
    let thinkingRuntimeItems = {};
    let thinkingRuntimeStartedAtByAgent = {};
    let thinkingProviderRuntimeMeta = { id: "", phase: "live", updatedAt: 0, enterTimer: 0 };
    let thinkingRuntimeAgeTimer = 0;
    const clearThinkingRuntimeItemTimers = (item) => {
      if (!item) return;
      clearTimeout(item.enterTimer);
      item.enterTimer = 0;
    };
    const clearThinkingProviderRuntimeTimer = () => {
      clearTimeout(thinkingProviderRuntimeMeta.enterTimer);
      thinkingProviderRuntimeMeta.enterTimer = 0;
    };
    const resetThinkingProviderRuntimeMeta = () => {
      clearThinkingProviderRuntimeTimer();
      thinkingProviderRuntimeMeta.id = "";
      thinkingProviderRuntimeMeta.phase = "live";
      thinkingProviderRuntimeMeta.updatedAt = 0;
    };
    const syncThinkingProviderRuntimeMeta = (eventId) => {
      const nextId = String(eventId || "").trim();
      if (!nextId) {
        resetThinkingProviderRuntimeMeta();
        return thinkingProviderRuntimeMeta;
      }
      if (thinkingProviderRuntimeMeta.id !== nextId) {
        clearThinkingProviderRuntimeTimer();
        thinkingProviderRuntimeMeta.id = nextId;
        thinkingProviderRuntimeMeta.phase = "live";
        thinkingProviderRuntimeMeta.updatedAt = Date.now();
      }
      return thinkingProviderRuntimeMeta;
    };
    const currentThinkingRuntimeItem = (agent) => thinkingRuntimeItems[agent] || null;
    const currentThinkingRuntimeStartedAt = (agent) => {
      const value = Number(thinkingRuntimeStartedAtByAgent[agent] || "0");
      return Number.isFinite(value) && value > 0 ? value : 0;
    };
    const ensureThinkingRuntimeStartedAt = (agent, preferred = 0) => {
      const existing = currentThinkingRuntimeStartedAt(agent);
      if (existing > 0) return existing;
      const next = Number(preferred);
      const startedAt = Number.isFinite(next) && next > 0 ? next : Date.now();
      thinkingRuntimeStartedAtByAgent[agent] = startedAt;
      return startedAt;
    };
    const clearThinkingRuntimeAgent = (agent, { suppressRender = false } = {}) => {
      const item = thinkingRuntimeItems[agent];
      if (!item) return false;
      clearThinkingRuntimeItemTimers(item);
      delete thinkingRuntimeItems[agent];
      if (!suppressRender) renderThinkingIndicator();
      return true;
    };
    const setThinkingRuntimeItem = (agent, event, { suppressRender = false } = {}) => {
      const entry = {
        id: String(event?.id || "").trim(),
        text: String(event?.text || "").trim(),
        phase: "live",
        enterTimer: 0,
        updatedAt: Number.isFinite(Number(event?.updatedAt)) && Number(event.updatedAt) > 0
          ? Number(event.updatedAt)
          : Date.now(),
      };
      if (!entry.id || !entry.text) return false;
      const current = currentThinkingRuntimeItem(agent);
      if (current && current.id === entry.id && current.text === entry.text) return false;
      clearThinkingRuntimeItemTimers(current);
      thinkingRuntimeItems[agent] = entry;
      if (!suppressRender) renderThinkingIndicator();
      return true;
    };
    const syncThinkingRuntimeItems = (statuses, { suppressRender = false } = {}) => {
      const runningAgents = new Set(
        Object.entries(statuses || {})
          .filter(([, status]) => status === "running")
          .map(([agent]) => agent)
      );
      let changed = false;
      Object.keys(thinkingRuntimeItems).forEach((agent) => {
        if (runningAgents.has(agent)) return;
        changed = clearThinkingRuntimeAgent(agent, { suppressRender: true }) || changed;
      });
      runningAgents.forEach((agent) => {
        const payload = currentAgentRuntime?.[agent];
        const raw = payload?.current_event;
        const id = String(raw?.id || "").trim();
        const text = String(raw?.text || "").trim();
        if (!id || !text) {
          changed = clearThinkingRuntimeAgent(agent, { suppressRender: true }) || changed;
        } else {
          changed = setThinkingRuntimeItem(agent, { id, text }, { suppressRender: true }) || changed;
        }
      });
      if (changed && !suppressRender) {
        renderThinkingIndicator();
      }
    };
    const applySessionState = (data) => {
      if (!data || typeof data !== "object") return;
      const hasOwn = (key) => Object.prototype.hasOwnProperty.call(data, key);
      if (typeof data.session === "string" && data.session) {
        currentSessionName = data.session;
      }
      let _justActivatedFromLaunch = false;
      if (typeof data.active === "boolean") {
        if (_sessionLaunching && !sessionActive && data.active) {
          _justActivatedFromLaunch = true;
          _sessionLaunching = false;
        }
        sessionActive = data.active;
        if (sessionActive) {
          clearDraftLaunchHints();
        }
      }
      if (typeof data.launch_pending === "boolean") {
        sessionLaunchPending = !sessionActive && (data.launch_pending || sessionLaunchPending || draftLaunchHintActive);
      }
      if (hasOwn("targets")) {
        const resolvedTargets = normalizedSessionTargets(data.targets);
        const nextTargets = canInteractWithSession() ? resolvedTargets : [];
        const nextTargetsSig = JSON.stringify(nextTargets);
        const currentTargetsSig = JSON.stringify(availableTargets);
        if (nextTargetsSig !== currentTargetsSig) {
          availableTargets = nextTargets;
          selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
          saveTargetSelection(currentSessionName, selectedTargets);
          if (!_justActivatedFromLaunch) {
            renderTargetPicker(availableTargets);
            if (cameraMode && !cameraMode.hidden) {
              renderCameraModeTargets();
            }
          }
        }
      }
      document.getElementById("message").disabled = !sessionActive;
      setQuickActionsDisabled(!sessionActive);
      if (sessionLaunchPending) {
        setStatus("");
      } else if (!sessionActive) {
        setStatus("archived session is read-only");
      }
      syncPendingLaunchControls();
      void maybeRestoreFileModalSessionState(currentSessionName);
      if (_justActivatedFromLaunch) {
        requestAnimationFrame(() => {
          renderTargetPicker(availableTargets);
          if (cameraMode && !cameraMode.hidden) renderCameraModeTargets();
          openComposerOverlay({ immediateFocus: true });
        });
      } else {
        maybeAutoOpenComposer();
      }
      if (hasOwn("agent_runtime") && data.agent_runtime && typeof data.agent_runtime === "object") {
        currentAgentRuntime = { ...data.agent_runtime };
      } else if (hasOwn("agent_runtime")) {
        currentAgentRuntime = {};
      }
      if (hasOwn("provider_runtime") && data.provider_runtime && typeof data.provider_runtime === "object") {
        currentProviderRuntime = { ...data.provider_runtime };
      } else if (hasOwn("provider_runtime")) {
        currentProviderRuntime = {};
      }
      if (data.statuses && typeof data.statuses === "object") {
        syncThinkingRuntimeItems(data.statuses, { suppressRender: true });
        renderAgentStatus(data.statuses);
      } else {
        if (hasOwn("agent_runtime")) {
          syncThinkingRuntimeItems(currentAgentStatuses, { suppressRender: true });
        }
        renderThinkingIndicator();
      }
      if (typeof data.session === "string" && data.session) {
        dpOnSessionSummaryPinReload();
      }
    };
    const formatCompactMetric = (value) => {
      const num = Number(value);
      if (!Number.isFinite(num)) return "";
      const abs = Math.abs(num);
      if (abs >= 1_000_000) {
        return `${(num / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1).replace(/\.0$/, "")}M`;
      }
      if (abs >= 1_000) {
        return `${(num / 1_000).toFixed(abs >= 10_000 ? 0 : 1).replace(/\.0$/, "")}k`;
      }
      return String(Math.trunc(num));
    };
    const providerRuntimeSummaryItems = (runtime) => {
      if (!runtime || typeof runtime !== "object") return [];
      const explicit = Array.isArray(runtime.summary_items)
        ? runtime.summary_items.map((item) => String(item || "").trim()).filter(Boolean)
        : [];
      if (explicit.length) return explicit;
      const derived = [];
      const chunkIndex = Number(runtime.chunk_index);
      if (Number.isFinite(chunkIndex)) derived.push(`chunk ${chunkIndex + 1}`);
      const chunkCount = Number(runtime.chunk_count);
      if (Number.isFinite(chunkCount) && chunkCount > 0) derived.push(`${chunkCount} chunks`);
      const totalTokens = formatCompactMetric(runtime.usage_total_tokens);
      if (totalTokens) derived.push(`${totalTokens} tok`);
      const thoughtTokens = formatCompactMetric(runtime.usage_thought_tokens);
      if (thoughtTokens) derived.push(`${thoughtTokens} think`);
      const outputChars = formatCompactMetric(runtime.output_chars);
      if (outputChars) derived.push(`${outputChars} chars`);
      const finishReason = String(runtime.finish_reason || "").trim();
      if (finishReason) derived.push(finishReason);
      const errorType = String(runtime.error_type || "").trim();
      if (errorType) derived.push(errorType);
      return derived;
    };
    const providerRuntimeStructuredText = (runtime) => {
      if (!runtime || typeof runtime !== "object") return "";
      const parts = [];
      const eventName = String(runtime.event_name || "").trim();
      if (eventName) parts.push(eventName);
      const summaryItems = providerRuntimeSummaryItems(runtime);
      if (summaryItems.length) parts.push(...summaryItems);
      return parts.join(" · ");
    };
    const providerRuntimePreviewText = (runtime) => {
      if (!runtime || typeof runtime !== "object") return "";
      const preview = String(runtime.preview || "").trim();
      if (!preview) return "";
      const structured = providerRuntimeStructuredText(runtime);
      return preview === structured ? "" : preview;
    };
    const buildThinkingPreviewStreamHtml = (text) => {
      const chars = Array.from(String(text || ""));
      if (!chars.length) return "";
      const limited = chars.slice(0, 320);
      const body = limited.map((ch, idx) =>
        `<span class="stream-char" style="--stream-char-i:${idx}">${escapeHtml(ch)}</span>`
      ).join("");
      return body + (chars.length > limited.length ? "…" : "");
    };
    const wrapThinkingChars = (text, offset = 0) => {
      return Array.from(String(text || "")).map((ch, i) =>
        `<span class="thinking-char" style="--char-i:${i + offset}">${escapeHtml(ch)}</span>`
      ).join("");
    };
    const buildThinkingRuntimeHtml = (text) => {
      const raw = String(text || "").replace(/\r\n?/g, "\n");
      if (!raw) return "";
      const lines = raw.split("\n");
      const firstLine = lines.find((line) => line.trim().length > 0) ?? lines[0] ?? "";
      const cleanedLine = firstLine.replace(/^[⏺●•·◦○]\s+/, "").trim();
      const asciiToken = cleanedLine.match(/^([A-Za-z][A-Za-z0-9_.:-]*)([\s\S]*)$/);
      if (asciiToken) {
        const keyword = String(asciiToken[1] || "");
        const rest = String(asciiToken[2] || "");
        const trimmedRest = rest.trim();
        const tokenLooksStructured = /[._:]/.test(keyword);
        const detailText = trimmedRest ? (tokenLooksStructured ? ` ${cleanedLine}` : rest) : "";
        const detail = detailText
          ? `<span class="message-thinking-runtime-detail">${escapeHtml(detailText)}</span>`
          : "";
        return `<span class="message-thinking-runtime-keyword">${wrapThinkingChars(keyword)}</span>${detail}`;
      }
      const leading = cleanedLine.match(/^(\S+)([\s\S]*)$/);
      if (leading) {
        const keyword = String(leading[1] || "");
        const rest = String(leading[2] || "");
        const detail = rest ? `<span class="message-thinking-runtime-detail">${escapeHtml(rest)}</span>` : "";
        return `<span class="message-thinking-runtime-keyword">${wrapThinkingChars(keyword)}</span>${detail}`;
      }
      return escapeHtml(cleanedLine || firstLine);
    };
    const formatThinkingRuntimeAgeText = (updatedAt, now = Date.now()) => {
      const value = Number(updatedAt);
      if (!Number.isFinite(value) || value <= 0) return "0s";
      const elapsedSec = Math.max(0, Math.floor((now - value) / 1000));
      return `${elapsedSec}s`;
    };
    const updateThinkingRuntimeAgeNode = (ageNode, now = Date.now()) => {
      if (!ageNode) return;
      const updatedAt = Number(ageNode.dataset.updatedAt || "0");
      ageNode.textContent = formatThinkingRuntimeAgeText(updatedAt, now);
    };
    const refreshThinkingRuntimeAges = (scope = document, now = Date.now()) => {
      const root = scope && typeof scope.querySelectorAll === "function" ? scope : document;
      root.querySelectorAll(".message-thinking-runtime-age[data-updated-at]").forEach((node) => {
        updateThinkingRuntimeAgeNode(node, now);
      });
    };
    const buildThinkingRuntimeLineInnerHtml = (contentHtml, updatedAt) => {
      const safeUpdatedAt = Math.max(0, Math.round(Number(updatedAt) || Date.now()));
      return `<span class="message-thinking-runtime-body">${contentHtml}</span><span class="message-thinking-runtime-age" data-runtime-age data-updated-at="${safeUpdatedAt}">${formatThinkingRuntimeAgeText(safeUpdatedAt)}</span>`;
    };
    const syncThinkingRuntimeSlot = (label, { contentHtml, eventId = "", updatedAt = Date.now() }) => {
      if (!label) return;
      let slot = label.querySelector(".message-thinking-runtime-slot");
      if (!slot) {
        slot = document.createElement("span");
        slot.className = "message-thinking-runtime-slot";
        label.appendChild(slot);
      }
      const stableId = String(eventId || "");
      const stableUpdatedAt = Math.max(0, Math.round(Number(updatedAt) || Date.now()));
      const lines = Array.from(slot.querySelectorAll(".message-thinking-runtime-line"));
      const activeLine = lines.find((line) => String(line.dataset.state || "") !== "leave") || lines[lines.length - 1] || null;
      const activeBody = activeLine?.querySelector(".message-thinking-runtime-body");
      const activeHtml = activeBody ? activeBody.innerHTML : "";
      const sameText = !!activeLine && activeHtml === contentHtml;
      const sameId = !!activeLine && String(activeLine.dataset.eventId || "") === stableId;

      if (activeLine && sameText && sameId) {
        activeLine.dataset.state = "live";
        activeLine.dataset.updatedAt = String(stableUpdatedAt);
        const ageNode = activeLine.querySelector(".message-thinking-runtime-age");
        if (ageNode) {
          ageNode.dataset.updatedAt = String(stableUpdatedAt);
          updateThinkingRuntimeAgeNode(ageNode);
        }
        return;
      }

      if (activeLine) {
        if (activeLine._runtimeStateTimer) {
          clearTimeout(activeLine._runtimeStateTimer);
          activeLine._runtimeStateTimer = 0;
        }
        if (activeLine._runtimeRemoveTimer) {
          clearTimeout(activeLine._runtimeRemoveTimer);
          activeLine._runtimeRemoveTimer = 0;
        }
        activeLine.dataset.state = "leave";
        const lineToRemove = activeLine;
        lineToRemove._runtimeRemoveTimer = setTimeout(() => {
          lineToRemove.remove();
        }, 300);
      }

      const nextLine = document.createElement("span");
      nextLine.className = "message-thinking-runtime-line";
      nextLine.dataset.state = "enter";
      nextLine.dataset.eventId = stableId;
      nextLine.dataset.updatedAt = String(stableUpdatedAt);
      nextLine.innerHTML = buildThinkingRuntimeLineInnerHtml(contentHtml, stableUpdatedAt);
      slot.appendChild(nextLine);

      // Use double requestAnimationFrame to guarantee layout transition triggers,
      // even if the element/container is currently detached or hidden during sync.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (nextLine.dataset.state === "enter") {
            nextLine.dataset.state = "live";
          }
        });
      });

      const allLines = Array.from(slot.querySelectorAll(".message-thinking-runtime-line"));
      if (allLines.length > 2) {
        allLines.slice(0, allLines.length - 2).forEach((line) => {
          if (line._runtimeStateTimer) {
            clearTimeout(line._runtimeStateTimer);
            line._runtimeStateTimer = 0;
          }
          if (line._runtimeRemoveTimer) {
            clearTimeout(line._runtimeRemoveTimer);
            line._runtimeRemoveTimer = 0;
          }
          line.remove();
        });
      }
      refreshThinkingRuntimeAges(slot);
    };
    if (!thinkingRuntimeAgeTimer) {
      thinkingRuntimeAgeTimer = setInterval(() => {
        refreshThinkingRuntimeAges();
      }, THINKING_RUNTIME_AGE_TICK_MS);
    }
    const renderCameraModeThinking = () => {
      if (!cameraModeThinking) return;
      cameraModeThinking.hidden = true;
      cameraModeThinking.innerHTML = "";
      cameraModeThinking.dataset.sig = "";
    };
    let thinkingFloatingIconFrame = 0;
    const animateScrollButtonContentSwap = (button, apply) => {
      if (!button || typeof apply !== "function") return;
      if (button.dataset.swapState === "1") return;
      button.dataset.swapState = "1";
      button.classList.add("thinking-scroll-btn-swapping");
      setTimeout(() => {
        apply();
        requestAnimationFrame(() => {
          button.classList.remove("thinking-scroll-btn-swapping");
          delete button.dataset.swapState;
        });
      }, 80);
    };
    const restoreThinkingScrollButton = () => {
      const button = document.getElementById("scrollToBottomBtn");
      if (!button || !button.classList.contains("thinking-scroll-btn")) return;
      animateScrollButtonContentSwap(button, () => {
        const defaultHtml = button.dataset.defaultHtml || "";
        if (defaultHtml) button.innerHTML = defaultHtml;
        button.classList.remove("thinking-scroll-btn");
        button.removeAttribute("data-thinking-sig");
        button.setAttribute("aria-label", "Scroll to bottom");
        button.setAttribute("title", "Scroll to bottom");
      });
    };
    const removeThinkingFloatingIcons = () => {
      if (thinkingFloatingIconFrame) {
        cancelAnimationFrame(thinkingFloatingIconFrame);
        thinkingFloatingIconFrame = 0;
      }
      document.getElementById("messageThinkingFloatingIcons")?.remove();
      restoreThinkingScrollButton();
    };
    const syncThinkingFloatingIcons = () => {
      thinkingFloatingIconFrame = 0;
      const root = document.getElementById("messages");
      const container = root?.querySelector(".message-thinking-container");
      if (!root || !timeline || !container || !document.body?.classList.contains("agent-runtime-running")) {
        removeThinkingFloatingIcons();
        return;
      }
      const sources = Array.from(container.querySelectorAll(".message-thinking-row"))
        .map((row) => {
          const wrap = row.querySelector(".message-thinking-icon-wrap");
          return wrap ? { row, wrap } : null;
        })
        .filter(Boolean);
      if (!sources.length) {
        removeThinkingFloatingIcons();
        return;
      }

      const visibleSources = sources.slice(0, 1);
      const sig = visibleSources.map(({ row, wrap }) => {
        const icon = wrap.querySelector(".message-thinking-icon");
        return [
          row.dataset.agent || "",
          row.dataset.provider || "",
          row.style.getPropertyValue("--agent-pulse-delay") || "",
          icon?.className || "",
          icon?.getAttribute("style") || "",
        ].join(":");
      }).join("|");

      const sourceAnchor = sources[0].wrap.closest(".message-thinking-icons") || sources[0].wrap;
      const sourceRect = sourceAnchor.getBoundingClientRect();
      const timelineRect = timeline.getBoundingClientRect();
      if (!sourceRect.width || !sourceRect.height || !timelineRect.width || !timelineRect.height) {
        restoreThinkingScrollButton();
        return;
      }
      const bottomInset = 14;
      const expectedHeight = Math.max(24, sourceRect.height);
      const stickyTop = timelineRect.bottom - bottomInset - expectedHeight;
      const shouldStick = sourceRect.top > stickyTop || sourceRect.bottom < timelineRect.top;
      if (!shouldStick || _stickyToBottom) {
        restoreThinkingScrollButton();
        return;
      }

      const button = document.getElementById("scrollToBottomBtn");
      if (!button) return;
      if (!button.dataset.defaultHtml) button.dataset.defaultHtml = button.innerHTML;
      const buttonSig = `scroll:${sig}`;
      if (button.getAttribute("data-thinking-sig") !== buttonSig) {
        animateScrollButtonContentSwap(button, () => {
          button.setAttribute("data-thinking-sig", buttonSig);
          button.innerHTML = "";
          visibleSources.forEach(({ row, wrap }) => {
            const clone = wrap.cloneNode(true);
            clone.classList.add("message-thinking-floating-icon-wrap");
            clone.style.setProperty("--agent-pulse-delay", row.style.getPropertyValue("--agent-pulse-delay") || "0s");
            button.appendChild(clone);
          });
          button.classList.add("thinking-scroll-btn");
          button.setAttribute("aria-label", "Scroll to bottom");
          button.setAttribute("title", "Scroll to bottom");
        });
        return;
      }
      button.classList.add("thinking-scroll-btn");
      button.setAttribute("aria-label", "Scroll to bottom");
      button.setAttribute("title", "Scroll to bottom");
    };
    const scheduleThinkingFloatingIcons = () => {
      if (thinkingFloatingIconFrame) return;
      thinkingFloatingIconFrame = requestAnimationFrame(syncThinkingFloatingIcons);
    };
    const renderThinkingIndicator = () => {
      const root = document.getElementById("messages");
      if (!root) {
        document.body?.classList.remove("agent-runtime-running");
        removeThinkingFloatingIcons();
        return;
      }
      const runningAgents = Object.keys(currentAgentStatuses).filter((agent) => currentAgentStatuses[agent] === "running");
      const providerRuntimeActive = !!currentProviderRuntime?.active && !!currentProviderRuntime?.provider;
      const hasRuntimeRunning = runningAgents.length > 0 || providerRuntimeActive;
      document.body?.classList.toggle("agent-runtime-running", hasRuntimeRunning);
      const existingContainer = root.querySelector(".message-thinking-container");

      if (!root.querySelector("article.message-row") || !hasRuntimeRunning) {
        if (existingContainer) existingContainer.remove();
        resetThinkingProviderRuntimeMeta();
        root.dataset.thinkingSig = "";
        renderCameraModeThinking();
        removeThinkingFloatingIcons();
        maybeRestorePollScrollLock();
        return;
      }

      const providerStructured = providerRuntimeStructuredText(currentProviderRuntime);
      const providerPreview = providerRuntimePreviewText(currentProviderRuntime);
      const providerRuntimeEventId = providerRuntimeActive
        ? JSON.stringify({
            provider: currentProviderRuntime.provider || "",
            runId: currentProviderRuntime.run_id || "",
            status: currentProviderRuntime.status || "",
            event: currentProviderRuntime.event_name || "",
            seq: currentProviderRuntime.event_seq || "",
            summary: providerRuntimeSummaryItems(currentProviderRuntime),
            preview: providerPreview,
          })
        : "";
      let providerRuntimeMeta = thinkingProviderRuntimeMeta;
      if (providerRuntimeActive) {
        providerRuntimeMeta = syncThinkingProviderRuntimeMeta(providerRuntimeEventId);
      } else {
        resetThinkingProviderRuntimeMeta();
      }
      const providerSig = providerRuntimeActive
        ? `${providerRuntimeEventId}|${providerRuntimeMeta.phase || "live"}`
        : "";
      const agentRuntimeSig = JSON.stringify(
        runningAgents.map((agent) => [
          agent,
          currentThinkingRuntimeItem(agent)
            ? [currentThinkingRuntimeItem(agent).id, currentThinkingRuntimeItem(agent).text, currentThinkingRuntimeItem(agent).phase]
            : null,
        ])
      );
      const nextThinkingSig = `${runningAgents.join(",")}|${agentRuntimeSig}|${providerSig}`;
      if (root.dataset.thinkingSig === nextThinkingSig && existingContainer) {
        if (root.lastElementChild !== existingContainer) {
          root.appendChild(existingContainer);
        }
        refreshThinkingRuntimeAges(existingContainer);
        scheduleThinkingFloatingIcons();
        return;
      }

      const container = existingContainer || document.createElement("div");
      container.className = "message-thinking-container";

      const ensureAgentRow = (agent) => {
        let row = Array.from(container.querySelectorAll(".message-thinking-row[data-agent]"))
          .find((node) => node.dataset.agent === agent);
        const pulse = agentPulseOffset(agent);
        if (!row) {
          row = document.createElement("div");
          row.className = "message-thinking-row";
          row.dataset.agent = agent;
          row.innerHTML = `
            <span class="message-thinking-icons">
              <span class="message-thinking-icon-wrap">
                <span class="message-thinking-glow"></span>
                ${thinkingIconImg(agent, `message-thinking-icon message-thinking-icon--${agentBaseName(agent)}`)}
              </span>
            </span>
            <span class="message-thinking-label message-thinking-label-agent"></span>
          `;
        }
        row.style.setProperty("--agent-pulse-delay", `${pulse}s`);
        const runtimeItem = currentThinkingRuntimeItem(agent);
        const label = row.querySelector(".message-thinking-label-agent");

        const nextText = runtimeItem ? buildThinkingRuntimeHtml(runtimeItem.text) : `<span class="message-thinking-runtime-keyword">${wrapThinkingChars("Running...")}</span>`;
        const nextId = runtimeItem ? (String(runtimeItem.id || "")) : "generic";
        const nextUpdatedAt = runtimeItem?.updatedAt || Date.now();

        if (label) {
          syncThinkingRuntimeSlot(label, {
            contentHtml: nextText,
            eventId: nextId,
            updatedAt: nextUpdatedAt,
          });
        }
        return row;
      };

      const ensureProviderRow = () => {
        const providerAgent = agentBaseName(currentProviderRuntime.provider || "gemini") || "gemini";
        const pulse = agentPulseOffset(providerAgent);
        const providerPreviewHtml = providerPreview ? buildThinkingPreviewStreamHtml(providerPreview) : "";
        let row = container.querySelector(".message-thinking-row-provider");
        if (!row) {
          row = document.createElement("div");
          row.className = "message-thinking-row message-thinking-row-provider";
          row.innerHTML = `
            <span class="message-thinking-icons">
              <span class="message-thinking-icon-wrap">
                <span class="message-thinking-glow"></span>
                ${thinkingIconImg(providerAgent, `message-thinking-icon message-thinking-icon--${agentBaseName(providerAgent)}`)}
              </span>
            </span>
            <span class="message-thinking-label message-thinking-label-provider"></span>
          `;
        }
        row.dataset.providerEvents = String(currentProviderRuntime.system_msg_id || "");
        row.dataset.provider = providerAgent;
        row.style.setProperty("--agent-pulse-delay", `${pulse}s`);
        const label = row.querySelector(".message-thinking-label-provider");
        const syncProviderPreviewLine = (className, html) => {
          const existing = label?.querySelector(`.${className}`);
          if (!html) {
            existing?.remove();
            return;
          }
          if (existing && existing.innerHTML === html) return;
          const node = document.createElement("span");
          node.className = className;
          node.innerHTML = html;
          if (existing) existing.replaceWith(node);
          else label?.appendChild(node);
        };
        const providerText = providerStructured ? `<span class="message-thinking-runtime-keyword">${wrapThinkingChars(providerStructured)}</span>` : `<span class="message-thinking-runtime-keyword">${wrapThinkingChars("Running...")}</span>`;
        syncThinkingRuntimeSlot(label, {
          contentHtml: providerText,
          eventId: providerRuntimeMeta.id || providerRuntimeEventId || "provider-runtime",
          updatedAt: providerRuntimeMeta.updatedAt || Date.now(),
        });
        syncProviderPreviewLine("message-thinking-label-preview", providerPreviewHtml);
        return row;
      };

      const desiredAgents = new Set(runningAgents);
      container.querySelectorAll(".message-thinking-row[data-agent]").forEach((row) => {
        if (!desiredAgents.has(row.dataset.agent || "")) {
          row.remove();
        }
      });
      if (!providerRuntimeActive) {
        resetThinkingProviderRuntimeMeta();
        container.querySelector(".message-thinking-row-provider")?.remove();
      }

      runningAgents.forEach((agent) => {
        container.appendChild(ensureAgentRow(agent));
      });
      if (providerRuntimeActive) {
        container.appendChild(ensureProviderRow());
      }
      if (root.lastElementChild !== container) {
        root.appendChild(container);
      }
      root.dataset.thinkingSig = nextThinkingSig;
      refreshThinkingRuntimeAges(container);
      renderCameraModeThinking();
      scheduleThinkingFloatingIcons();
      maybeRestorePollScrollLock();
    };
    timeline?.addEventListener("scroll", scheduleThinkingFloatingIcons, { passive: true });
    window.addEventListener("resize", scheduleThinkingFloatingIcons, { passive: true });
    timeline?.addEventListener("click", (event) => {
      const wrap = event.target.closest(".message-thinking-icon-wrap");
      if (!wrap) return;
      const row = wrap.closest(".message-thinking-row[data-agent]");
      if (!row) return;
      const agent = row.dataset.agent || "";
      if (!agent) return;
      fetch("/open-terminal-pane", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent }),
      }).catch(() => {});
    });
    const messageCollapseScrollObserver =
      typeof IntersectionObserver === "function" && timeline && timeline.nodeType === 1
        ? new IntersectionObserver(
            (entries) => {
              for (const entry of entries) {
                if (entry.isIntersecting) continue;
                const row = entry.target;
                const msgId = row?.dataset?.msgid || "";
                if (!msgId || !expandedMessageBodies.has(msgId)) continue;
                expandedMessageBodies.delete(msgId);
                syncMessageCollapse(row);
              }
            },
            { root: timeline, threshold: 0 }
          )
        : null;
    const syncMessageCollapse = (scope = document) => {
      const rows = scope?.matches?.("article.message-row")
        ? (isCollapsibleMessageRow(scope) ? [scope] : [])
        : Array.from(scope?.querySelectorAll?.("article.message-row") || []).filter(isCollapsibleMessageRow);
      rows.forEach((row) => {
        const bodyRow = row.querySelector(".message-body-row");
        const body = row.querySelector(".md-body");
        const toggle = row.querySelector(".message-collapse-toggle");
        if (!bodyRow || !body || !toggle) return;
        const style = getComputedStyle(body);
        const lineHeight = Number.parseFloat(style.lineHeight);
        const paddingTop = Number.parseFloat(style.paddingTop) || 0;
        const paddingBottom = Number.parseFloat(style.paddingBottom) || 0;
        if (!Number.isFinite(lineHeight)) {
          bodyRow.style.removeProperty("--message-collapse-max-height");
          row.classList.remove("is-collapsible");
          bodyRow.classList.remove("is-collapsed");
          toggle.classList.remove("is-visible");
          toggle.hidden = true;
          if (messageCollapseScrollObserver) {
            try {
              messageCollapseScrollObserver.unobserve(row);
            } catch (_) {}
          }
          return;
        }
        const maxHeight = Math.ceil((lineHeight * 20) + paddingTop + paddingBottom);
        bodyRow.style.setProperty("--message-collapse-max-height", `${maxHeight}px`);
        const shouldCollapse = body.scrollHeight > (maxHeight + 4);
        const msgId = row.dataset.msgid || "";
        const isExpanded = shouldCollapse && msgId && expandedMessageBodies.has(msgId);
        row.classList.toggle("is-collapsible", shouldCollapse);
        bodyRow.classList.toggle("is-collapsed", shouldCollapse && !isExpanded);
        const showMoreBtn = shouldCollapse && !isExpanded;
        toggle.classList.toggle("is-visible", showMoreBtn);
        toggle.hidden = !showMoreBtn;
        toggle.textContent = "More";
        if (messageCollapseScrollObserver) {
          if (isExpanded && shouldCollapse && msgId) {
            messageCollapseScrollObserver.observe(row);
          } else {
            try {
              messageCollapseScrollObserver.unobserve(row);
            } catch (_) {}
          }
        }
      });
    };
    const syncPaneViewerTabThinkingStatuses = () => {
      const tabsRoot = document.getElementById("paneViewerTabs");
      if (tabsRoot) {
        tabsRoot.querySelectorAll(".pane-viewer-tab").forEach((tab) => {
          const a = tab.dataset.agent;
          if (!a) return;
          tab.classList.toggle("pane-viewer-tab-thinking", currentAgentStatuses[a] === "running");
        });
      }
    };
