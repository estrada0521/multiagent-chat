    let currentAgentStatuses = {};
    let currentAgentRuntime = {};
    let currentProviderRuntime = {};
    const THINKING_RUNTIME_ENTER_MS = 320;
    const THINKING_RUNTIME_LEAVE_MS = 320;
    const THINKING_RUNTIME_AGE_TICK_MS = 1000;
    let thinkingRuntimeItems = {};
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
        thinkingProviderRuntimeMeta.phase = "enter";
        thinkingProviderRuntimeMeta.updatedAt = Date.now();
        thinkingProviderRuntimeMeta.enterTimer = setTimeout(() => {
          if (thinkingProviderRuntimeMeta.id !== nextId || thinkingProviderRuntimeMeta.phase !== "enter") return;
          thinkingProviderRuntimeMeta.phase = "live";
          renderThinkingIndicator();
        }, THINKING_RUNTIME_ENTER_MS);
      }
      return thinkingProviderRuntimeMeta;
    };
    const currentThinkingRuntimeItem = (agent) => thinkingRuntimeItems[agent] || null;
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
        phase: "enter",
        enterTimer: 0,
        updatedAt: Number.isFinite(Number(event?.updatedAt)) && Number(event.updatedAt) > 0
          ? Number(event.updatedAt)
          : Date.now(),
      };
      if (!entry.id || !entry.text) return false;
      entry.enterTimer = setTimeout(() => {
        const current = currentThinkingRuntimeItem(agent);
        if (!current || current.phase !== "enter") return;
        current.phase = "live";
        renderThinkingIndicator();
      }, THINKING_RUNTIME_ENTER_MS);
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
      if (typeof data.session === "string" && data.session) {
        currentSessionName = data.session;
      }
      if (typeof data.active === "boolean") {
        sessionActive = data.active;
        if (sessionActive) {
          clearDraftLaunchHints();
        }
      }
      if (typeof data.launch_pending === "boolean") {
        sessionLaunchPending = !sessionActive && (data.launch_pending || sessionLaunchPending || draftLaunchHintActive);
      }
      {
        const resolvedTargets = normalizedSessionTargets(data.targets);
        const nextTargets = canInteractWithSession() ? resolvedTargets : [];
        const nextTargetsSig = JSON.stringify(nextTargets);
        const currentTargetsSig = JSON.stringify(availableTargets);
        if (nextTargetsSig !== currentTargetsSig) {
          availableTargets = nextTargets;
          selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
          saveTargetSelection(currentSessionName, selectedTargets);
          renderTargetPicker(availableTargets);
          if (cameraMode && !cameraMode.hidden) {
            renderCameraModeTargets();
          }
        }
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
      if (data.agent_runtime && typeof data.agent_runtime === "object") {
        currentAgentRuntime = { ...data.agent_runtime };
      } else {
        currentAgentRuntime = {};
      }
      if (data.provider_runtime && typeof data.provider_runtime === "object") {
        currentProviderRuntime = { ...data.provider_runtime };
      } else {
        currentProviderRuntime = {};
      }
      if (data.statuses && typeof data.statuses === "object") {
        syncThinkingRuntimeItems(data.statuses, { suppressRender: true });
        renderAgentStatus(data.statuses);
      } else {
        renderThinkingIndicator();
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
    const normalizeThinkingRuntimeToken = (value) =>
      String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
    const classifyThinkingRuntimeTool = (toolNameRaw) => {
      const tool = normalizeThinkingRuntimeToken(toolNameRaw);
      if (!tool) return "";
      if (/^(view|viewimage|read|readfile|readlints|files?|openfile|attachmentfile)/.test(tool)) return "Read";
      if (/^(grep|rg|search|searchtext|googlesearch|grepsearch|query)/.test(tool)) return "Search";
      if (/^(glob|listdirectory|ls|explore|browser|webfetch|fetchurl|directory)/.test(tool)) return "Explore";
      if (/^(bash|shell|execcommand|runshellcommand|writestdin|command|interrupt|ctrlc|enter)/.test(tool)) return "Run";
      if (/^(applypatch|patch|replace|strreplace|edit|editedtextfile|update|rename)/.test(tool)) return "Edit";
      if (/^(write|writefile|create|newfile)/.test(tool)) return "Write";
      if (/^(delete|remove|unlink|rm)/.test(tool)) return "Delete";
      if (/^(skill|invokedskills|skilllisting|loadskill)/.test(tool)) return "Skill";
      if (/^(askuser|reportintent|model|permissionmode|queueoperation|sessioninfo|turnstart|turnend|taskstarted|taskcomplete)/.test(tool)) return "Status";
      return "";
    };
    const classifyThinkingRuntimeLabel = (line, token = "", rest = "") => {
      const lowerLine = String(line || "").toLowerCase();
      const key = normalizeThinkingRuntimeToken(token);
      const lowerRest = String(rest || "").toLowerCase();
      const has = (re) => re.test(lowerLine);
      if (String(line || "").trim().startsWith("✦") || has(/\b(thinking|reasoning|thought|reasoningopaque|agent_reasoning|response_item\.reasoning|gemini\.thoughts(?:\.[a-z_]+)?)\b/)) return "Thinking";
      if (has(/\b(error|failed|failure|exception|rate[\s-]?limit|invalid command(?: file)?|429|success\s*=\s*false)\b/)) return "Error";
      if (has(/\b(interrupted|turn_aborted|abort(?:ed)?)\b/)) return "Interrupted";
      if (has(/\b(compact(?:ed|ing|ion)?|context_compacted|compact_boundary|compact_boundary|compaction_(?:start|complete)|session\.compaction_(?:start|complete)|session\.compaction_start|session\.compaction_complete)\b/)) return "Compacted";
      if (has(/\b(plan(?:ning)?|plan tool|toolrequests?)\b/) || lowerLine.startsWith("i will ") || lowerLine.startsWith("i'll ")) return "Planning";
      if (has(/\b(usage|token_count|tokens?(?:\.|_|$)|input_tokens|output_tokens|cached_tokens?|usage_[a-z_]+)\b/)) return "Usage";
      if (has(/\b(task_reminder|reminder)\b/)) return "Reminder";
      if (has(/\b(skill|invoked_skills|skill_listing|loaded skill|skills available|invoked skill)\b/)) return "Skill";
      if (has(/\b(attachment\.edited_text_file|edited_text_file)\b/)) return "Edit";
      if (has(/\b(attachment\.file|file opened)\b/)) return "Read";
      if (has(/\b(result|result summary|resultdisplay|function_call_output|custom_tool_call_output|execution_complete|exec_command_end|patch_apply_end|tool[_-]?result|success|run finished|edit finished)\b/) && !has(/\b(error|failed|failure|success\s*=\s*false)\b/)) return "Result";
      if (has(/\b(status|task[_ ]started|task[_ ]complete|task finished|turn[_ ]start|turn[_ ]end|turn finished|queued|dequeued|queue[-_ ]removed|queue-operation\.(?:enqueue|dequeue|remove)|permission mode changed|permission-mode|model changed|session\.model_change|model info|session\.info|mcp connected|signed in|context changed|turn_context|date changed|date_change|tools changed|deferred_tools_delta|provider meta|provideroptions\.cursor|system initialized|command_permissions)\b/)) {
        return "Status";
      }
      const runtimeToolMatch = lowerLine.match(/(?:toolname|name)\s*[:=]\s*['"]?([a-z0-9_.-]+)/i);
      const runtimeToolLabel = classifyThinkingRuntimeTool(runtimeToolMatch?.[1] || "");
      if (runtimeToolLabel) return runtimeToolLabel;
      const tokenToolLabel = classifyThinkingRuntimeTool(token);
      if (tokenToolLabel) return tokenToolLabel;
      if (/^(run|running|ran|bashing|building|cloning|committing|fetching|installing|pushing|spawning|testing|execcommandend)$/.test(key)) return "Run";
      if (/^(read|reading|view|viewing|readfile|readlints|fileopened)$/.test(key)) return "Read";
      if (/^(search|searching|grepped|grep|rg|searchtext|googlesearch|grepsearch)$/.test(key)) return "Search";
      if (/^(explore|exploring|glob|globbing|listing|listdirectory|browser)$/.test(key)) return "Explore";
      if (/^(edit|editing|edited|patching|replace|updating|update|patchapplyend|editedtextfile)$/.test(key)) return "Edit";
      if (/^(write|writing|create|creating|wrote)$/.test(key)) return "Write";
      if (/^(delete|deleting|deleted|remove|removed)$/.test(key)) return "Delete";
      if (/^(status|context|queue|permission|model|authentication|mcp|turn|task|info|permissionmode|commandpermissions|datechange)$/.test(key)) return "Status";
      if (/^(result|finished|complete|completed|done)$/.test(key)) return "Result";
      if (/^(compacted|compacting|compaction)$/.test(key)) return "Compacted";
      if (/^(interrupted|abort|aborted)$/.test(key)) return "Interrupted";
      if (/^(skill|skills)$/.test(key) || lowerRest.includes("skill")) return "Skill";
      return "";
    };
    const buildThinkingRuntimeHtml = (text) => {
      const raw = String(text || "").replace(/\r\n?/g, "\n");
      if (!raw) return "";
      const lines = raw.split("\n");
      const firstLine = lines.find((line) => line.trim().length > 0) ?? lines[0] ?? "";
      /* Runtime activity stays on a single line; drop any later lines here and let CSS ellipsize long text. */
      if (firstLine.trim().startsWith("✦")) {
        return `<span class="message-thinking-runtime-keyword">${wrapThinkingChars("Thinking")}</span><span class="message-thinking-runtime-detail">${escapeHtml(` ${firstLine.trim()}`)}</span>`;
      }
      const cleanedLine = firstLine.replace(/^[⏺●•·◦○]\s+/, "").trim();
      const match = cleanedLine.match(/^([A-Za-z][A-Za-z0-9_.:-]*)([\s\S]*)$/);
      if (match) {
        const keyword = String(match[1] || "");
        const rest = String(match[2] || "");
        const label = classifyThinkingRuntimeLabel(cleanedLine, keyword, rest);
        if (label) {
          const trimmedRest = rest.trim();
          const tokenLooksStructured = /[._:]/.test(keyword);
          const detailText = trimmedRest
            ? (tokenLooksStructured ? ` ${cleanedLine}` : rest)
            : (keyword.toLowerCase() !== label.toLowerCase() ? ` ${cleanedLine}` : "");
          const detail = detailText
            ? `<span class="message-thinking-runtime-detail">${escapeHtml(detailText)}</span>`
            : "";
          return `<span class="message-thinking-runtime-keyword">${wrapThinkingChars(label)}</span>${detail}`;
        }
      }
      const fallbackLabel = classifyThinkingRuntimeLabel(cleanedLine);
      if (fallbackLabel) {
        return `<span class="message-thinking-runtime-keyword">${wrapThinkingChars(fallbackLabel)}</span><span class="message-thinking-runtime-detail">${escapeHtml(` ${cleanedLine}`)}</span>`;
      }
      const cleaned = cleanedLine || firstLine;
      return escapeHtml(cleaned || firstLine);
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
    const setThinkingRuntimeLineStateLater = (line, state, delayMs) => {
      if (!line) return;
      if (line._runtimeStateTimer) {
        clearTimeout(line._runtimeStateTimer);
        line._runtimeStateTimer = 0;
      }
      line._runtimeStateTimer = setTimeout(() => {
        line._runtimeStateTimer = 0;
        if (!line.isConnected) return;
        line.dataset.state = state;
      }, Math.max(0, Number(delayMs) || 0));
    };
    const removeThinkingRuntimeLineLater = (line, delayMs) => {
      if (!line) return;
      if (line._runtimeRemoveTimer) {
        clearTimeout(line._runtimeRemoveTimer);
        line._runtimeRemoveTimer = 0;
      }
      line._runtimeRemoveTimer = setTimeout(() => {
        line._runtimeRemoveTimer = 0;
        if (!line.isConnected) return;
        if (line._runtimeStateTimer) {
          clearTimeout(line._runtimeStateTimer);
          line._runtimeStateTimer = 0;
        }
        line.remove();
      }, Math.max(0, Number(delayMs) || 0));
    };
    const syncThinkingRuntimeSlot = (label, { contentHtml, state = "live", eventId = "", updatedAt = Date.now() }) => {
      if (!label) return;
      let slot = label.querySelector(".message-thinking-runtime-slot");
      if (!slot) {
        slot = document.createElement("span");
        slot.className = "message-thinking-runtime-slot";
        label.appendChild(slot);
      }
      const stableState = String(state || "live") === "enter" ? "enter" : "live";
      const stableId = String(eventId || "");
      const stableUpdatedAt = Math.max(0, Math.round(Number(updatedAt) || Date.now()));
      const lines = Array.from(slot.querySelectorAll(".message-thinking-runtime-line"));
      const activeLine = lines.find((line) => String(line.dataset.state || "") !== "leave") || lines[lines.length - 1] || null;
      const activeBody = activeLine?.querySelector(".message-thinking-runtime-body");
      const activeHtml = activeBody ? activeBody.innerHTML : "";
      const sameText = !!activeLine && activeHtml === contentHtml;
      const sameId = !!activeLine && String(activeLine.dataset.eventId || "") === stableId;

      if (activeLine && sameText && sameId) {
        activeLine.dataset.state = stableState;
        activeLine.dataset.updatedAt = String(stableUpdatedAt);
        const ageNode = activeLine.querySelector(".message-thinking-runtime-age");
        if (ageNode) {
          ageNode.dataset.updatedAt = String(stableUpdatedAt);
          updateThinkingRuntimeAgeNode(ageNode);
        }
        if (stableState === "enter") {
          setThinkingRuntimeLineStateLater(activeLine, "live", THINKING_RUNTIME_ENTER_MS);
        }
        return;
      }

      if (activeLine) {
        activeLine.dataset.state = "leave";
        removeThinkingRuntimeLineLater(activeLine, THINKING_RUNTIME_LEAVE_MS + 30);
      }

      const nextLine = document.createElement("span");
      nextLine.className = "message-thinking-runtime-line";
      nextLine.dataset.state = stableState;
      nextLine.dataset.eventId = stableId;
      nextLine.dataset.updatedAt = String(stableUpdatedAt);
      nextLine.innerHTML = buildThinkingRuntimeLineInnerHtml(contentHtml, stableUpdatedAt);
      slot.appendChild(nextLine);
      if (stableState === "enter") {
        setThinkingRuntimeLineStateLater(nextLine, "live", THINKING_RUNTIME_ENTER_MS);
      }

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
    const removeThinkingFloatingIcons = () => {
      if (thinkingFloatingIconFrame) {
        cancelAnimationFrame(thinkingFloatingIconFrame);
        thinkingFloatingIconFrame = 0;
      }
      document.getElementById("messageThinkingFloatingIcons")?.remove();
    };
    const ensureThinkingFloatingIcons = () => {
      let rail = document.getElementById("messageThinkingFloatingIcons");
      if (!rail) {
        rail = document.createElement("div");
        rail.id = "messageThinkingFloatingIcons";
        rail.className = "message-thinking-floating-icons";
        rail.hidden = true;
        document.body.appendChild(rail);
      }
      return rail;
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

      const rail = ensureThinkingFloatingIcons();
      const sig = sources.map(({ row, wrap }) => {
        const icon = wrap.querySelector(".message-thinking-icon");
        return [
          row.dataset.agent || "",
          row.dataset.provider || "",
          row.style.getPropertyValue("--agent-pulse-delay") || "",
          icon?.className || "",
          icon?.getAttribute("style") || "",
        ].join(":");
      }).join("|");
      if (rail.dataset.sig !== sig) {
        rail.dataset.sig = sig;
        rail.innerHTML = "";
        sources.forEach(({ row, wrap }) => {
          const clone = wrap.cloneNode(true);
          clone.classList.add("message-thinking-floating-icon-wrap");
          clone.style.setProperty("--agent-pulse-delay", row.style.getPropertyValue("--agent-pulse-delay") || "0s");
          rail.appendChild(clone);
        });
      }

      const sourceAnchor = sources[0].wrap.closest(".message-thinking-icons") || sources[0].wrap;
      const sourceRect = sourceAnchor.getBoundingClientRect();
      const timelineRect = timeline.getBoundingClientRect();
      if (!sourceRect.width || !sourceRect.height || !timelineRect.width || !timelineRect.height) {
        rail.hidden = true;
        rail.classList.remove("visible");
        return;
      }
      const bottomInset = 14;
      const expectedHeight = Math.max(24, sourceRect.height);
      const stickyTop = timelineRect.bottom - bottomInset - expectedHeight;
      const shouldStick = sourceRect.top > stickyTop || sourceRect.bottom < timelineRect.top;
      if (!shouldStick) {
        rail.classList.remove("visible");
        rail.hidden = true;
        return;
      }

      rail.hidden = false;
      const railWidth = rail.offsetWidth || sourceRect.width || 28;
      const left = Math.max(
        timelineRect.left + 8,
        Math.min(sourceRect.left, timelineRect.right - railWidth - 8)
      );
      const bottom = Math.max(12, window.innerHeight - timelineRect.bottom + bottomInset);
      rail.style.left = `${Math.round(left)}px`;
      rail.style.bottom = `${Math.round(bottom)}px`;
      rail.classList.add("visible");
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
        const nextState = runtimeItem ? (runtimeItem.phase || "live") : "live";
        const nextId = runtimeItem ? (String(runtimeItem.id || "")) : "generic";
        const nextUpdatedAt = runtimeItem?.updatedAt || Date.now();

        if (label) {
          syncThinkingRuntimeSlot(label, {
            contentHtml: nextText,
            state: nextState,
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
          state: providerRuntimeMeta.phase || "live",
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
    const userCollapseScrollObserver =
      typeof IntersectionObserver === "function" && timeline && timeline.nodeType === 1
        ? new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (entry.isIntersecting) continue;
              const row = entry.target;
              const msgId = row?.dataset?.msgid || "";
              if (!msgId || !expandedUserMessages.has(msgId)) continue;
              expandedUserMessages.delete(msgId);
              syncUserMessageCollapse(row);
            }
          },
          { root: timeline, threshold: 0 }
        )
        : null;
    const syncUserMessageCollapse = (scope = document) => {
      const rows = scope?.matches?.("article.message-row.user")
        ? [scope]
        : Array.from(scope.querySelectorAll("article.message-row.user"));
      rows.forEach((row) => {
        const bodyRow = row.querySelector(".message-body-row");
        const body = row.querySelector(".md-body");
        const toggle = row.querySelector(".user-collapse-toggle");
        if (!bodyRow || !body || !toggle) return;
        const style = getComputedStyle(body);
        const lineHeight = Number.parseFloat(style.lineHeight);
        const paddingTop = Number.parseFloat(style.paddingTop) || 0;
        const paddingBottom = Number.parseFloat(style.paddingBottom) || 0;
        const maxHeight = Number.isFinite(lineHeight)
          ? Math.ceil((lineHeight * 10) + paddingTop + paddingBottom)
          : 245;
        bodyRow.style.setProperty("--user-collapse-max-height", `${maxHeight}px`);
        const bodyWidth = Math.round(body.getBoundingClientRect().width || bodyRow.clientWidth || 0);
        if (bodyWidth < 40) {
          row.classList.remove("is-collapsible");
          bodyRow.classList.remove("is-collapsed");
          toggle.classList.remove("is-visible");
          toggle.hidden = true;
          const retries = Math.max(0, parseInt(row.dataset.collapseRetry || "0", 10) || 0);
          if (retries < 3) {
            row.dataset.collapseRetry = String(retries + 1);
            requestAnimationFrame(() => requestAnimationFrame(() => syncUserMessageCollapse(row)));
          } else {
            row.dataset.collapseRetry = "0";
          }
          return;
        }
        row.dataset.collapseRetry = "0";
        let shouldCollapse = body.scrollHeight > (maxHeight + 4);
        const bodyText = String(body.textContent || "").trim();
        const hasHardBreak = bodyText.includes("\n") || !!body.querySelector("br");
        const hasStructuredBlocks = !!body.querySelector("pre, table, ul, ol, blockquote, img, video, iframe, details");
        if (shouldCollapse && bodyText.length <= 140 && !hasHardBreak && !hasStructuredBlocks) {
          shouldCollapse = false;
        }
        const msgId = row.dataset.msgid || "";
        const isExpanded = shouldCollapse && msgId && expandedUserMessages.has(msgId);
        row.classList.toggle("is-collapsible", shouldCollapse);
        bodyRow.classList.toggle("is-collapsed", shouldCollapse && !isExpanded);
        const showMoreBtn = shouldCollapse && !isExpanded;
        toggle.classList.toggle("is-visible", showMoreBtn);
        toggle.hidden = !showMoreBtn;
        toggle.textContent = "More";
        if (userCollapseScrollObserver) {
          if (isExpanded && shouldCollapse && msgId) {
            userCollapseScrollObserver.observe(row);
          } else {
            try {
              userCollapseScrollObserver.unobserve(row);
            } catch (_) { }
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
