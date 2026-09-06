    // When a message is sent to an agent we mark it running immediately, before
    // the server round-trip. session-state polls can then briefly race back with
    // a stale "not running" and make the indicator flicker; hold the optimistic
    // "running" until the server confirms it running at least once (after which
    // its later "idle" is the genuine end of the turn) or a grace period lapses.
    const _optimisticRunning = new Map(); // agent -> { until, confirmed }
    const markAgentOptimisticallyRunning = (agent) => {
      _optimisticRunning.set(agent, { until: Date.now() + 4000, confirmed: false });
      currentAgentStatuses[agent] = "running";
    };
    const renderAgentStatus = (statuses) => {
      let merged = statuses;
      if (_optimisticRunning.size) {
        const now = Date.now();
        for (const [agent, o] of _optimisticRunning) {
          if (statuses[agent] === "running") { o.confirmed = true; continue; }
          if (!o.confirmed && now < o.until) {
            if (merged === statuses) merged = { ...statuses };
            merged[agent] = "running";
          } else {
            _optimisticRunning.delete(agent);
          }
        }
      }
      currentAgentStatuses = { ...merged };
      if (document.documentElement.dataset.mobile === "1") {
        syncPaneViewerTabThinkingStatuses();
      }
      renderThinkingIndicator();
    };
__CHAT_INCLUDE:../session-state-projections.js__
    const applySessionState = (data) => {
      if (!data || typeof data !== "object") return;
      const hasOwn = (key) => Object.prototype.hasOwnProperty.call(data, key);
      if (typeof data.session === "string" && data.session) {
        currentSessionName = data.session;
        if (document.documentElement.dataset.mobile === "1") {
          repoSession = currentSessionName;
          if (latestPayloadData) updateRepoPanel(displayEntriesForData(latestPayloadData));
        }
      }
      if (typeof data.active === "boolean") {
        sessionActive = data.active;
      }
      document.getElementById("message").disabled = !sessionActive;
      const _attachBtn = document.getElementById("attachBtn");
      if (_attachBtn) _attachBtn.disabled = !sessionActive;
      if (typeof data.session === "string" && data.session) {
        restoreComposerDraft();
      }
      if (hasOwn("targets")) {
        const resolvedTargets = normalizedSessionTargets(data.targets);
        const picker = document.getElementById("targetPicker");
        if (!picker.dataset.loaded) {
          selectedTargets = loadTargetSelection(currentSessionName, resolvedTargets);
          saveTargetSelection(currentSessionName, selectedTargets);
          picker.dataset.loaded = "1";
        }
        const nextTargetsSig = JSON.stringify(resolvedTargets);
        if (nextTargetsSig !== JSON.stringify(availableTargets)) {
          availableTargets = resolvedTargets;
          selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
          saveTargetSelection(currentSessionName, selectedTargets);
          renderTargetPicker(availableTargets);
        }
      }
      if (!sessionActive) {
        setStatus("archived session is read-only");
      }
      if (hasOwn("agent_runtime") && data.agent_runtime && typeof data.agent_runtime === "object") {
        currentAgentRuntime = { ...data.agent_runtime };
      } else if (hasOwn("agent_runtime")) {
        currentAgentRuntime = {};
      }
      if (data.statuses && typeof data.statuses === "object") {
        Object.keys(currentAgentRuntime).forEach((agent) => {
          if (data.statuses[agent] !== "running") {
            delete currentAgentRuntime[agent];
          }
        });
        syncThinkingRuntimeItems(data.statuses, { suppressRender: true });
        renderAgentStatus(data.statuses);
      } else {
        if (hasOwn("agent_runtime")) {
          syncThinkingRuntimeItems(currentAgentStatuses, { suppressRender: true });
        }
        renderThinkingIndicator();
      }
      if (document.documentElement.dataset.mobile !== "1" && typeof data.session === "string" && data.session) {
        dpOnSessionSummaryPinReload();
      }
    };
    const refreshSessionState = async (projections = null) => {
      const requestedProjections = normalizeSessionStateProjections(projections);
      if (refreshSessionState.inFlight) {
        refreshSessionState.pending = mergeSessionStateProjections(refreshSessionState.pending, requestedProjections);
        return;
      }
      refreshSessionState.inFlight = true;
      try {
        const params = new URLSearchParams();
        params.set("ts", String(Date.now()));
        if (requestedProjections.length) {
          params.set("projections", requestedProjections.join(","));
        }
        const res = await fetchWithTimeout(`/session-state?${params.toString()}`, {}, 4000);
        if (!res.ok) throw new Error("session state unavailable");
        applySessionState(await res.json());
      } catch (err) {
        setStatus(err?.message || String(err), true);
      } finally {
        refreshSessionState.inFlight = false;
        if (refreshSessionState.pending.length) {
          const nextProjections = [...refreshSessionState.pending];
          refreshSessionState.pending = [];
          queueMicrotask(() => { void refreshSessionState(nextProjections); });
        }
      }
    };
    refreshSessionState.inFlight = false;
    refreshSessionState.pending = [];
__CHAT_INCLUDE:../session-state-events.js__
