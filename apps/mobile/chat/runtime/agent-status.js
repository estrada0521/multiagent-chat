    let lastHubRunningStateSig = "";
    const notifyHubRunningState = () => {
      if (window.parent === window) return;
      const sessionName = String(currentSessionName || "").trim();
      if (!sessionName) return;
      const runningAgents = Object.keys(currentAgentStatuses || {}).filter((agent) => currentAgentStatuses[agent] === "running");
      const isRunning = runningAgents.length > 0;
      const sig = `${sessionName}|${isRunning ? "1" : "0"}|${runningAgents.join(",")}`;
      if (sig === lastHubRunningStateSig) return;
      lastHubRunningStateSig = sig;
      try {
        window.parent.postMessage({
          type: "multiagent-session-running-state",
          sessionName,
          isRunning,
          runningAgents,
        }, "*");
      } catch (_) { }
    };
    const renderAgentStatus = (statuses) => {
      currentAgentStatuses = { ...statuses };
      syncPaneViewerTabThinkingStatuses();
      renderThinkingIndicator();
      notifyHubRunningState();
    };
    const normalizeSessionStateProjections = (projections) => {
      const raw = Array.isArray(projections)
        ? projections
        : (typeof projections === "string" ? projections.split(",") : []);
      const seen = new Set();
      const ordered = [];
      raw.forEach((item) => {
        const key = String(item || "").trim();
        if (!key || seen.has(key)) return;
        seen.add(key);
        ordered.push(key);
      });
      return ordered;
    };
    const mergeSessionStateProjections = (left, right) => {
      const seen = new Set();
      const merged = [];
      [...normalizeSessionStateProjections(left), ...normalizeSessionStateProjections(right)].forEach((item) => {
        if (seen.has(item)) return;
        seen.add(item);
        merged.push(item);
      });
      return merged;
    };
    const refreshSessionState = async (projections = null) => {
      const requestedProjections = normalizeSessionStateProjections(projections);
      if (sessionStateInFlight) {
        pendingSessionStateRefresh = true;
        pendingSessionStateProjections = mergeSessionStateProjections(pendingSessionStateProjections, requestedProjections);
        return;
      }
      sessionStateInFlight = true;
      try {
        const params = new URLSearchParams();
        params.set("ts", String(Date.now()));
        if (requestedProjections.length) {
          params.set("projections", requestedProjections.join(","));
        }
        const res = await fetchWithTimeout(`/session-state?${params.toString()}`, {}, 4000);
        if (res.ok) applySessionState(await res.json());
      } catch (_) {
      } finally {
        sessionStateInFlight = false;
        if (pendingSessionStateRefresh) {
          const nextProjections = pendingSessionStateProjections;
          pendingSessionStateRefresh = false;
          pendingSessionStateProjections = [];
          queueMicrotask(() => { void refreshSessionState(nextProjections); });
        }
      }
    };
    const startSessionStateEvents = () => {
      const es = new EventSource("/session-state-events");
      es.addEventListener("state", (event) => {
        let projections = [];
        try {
          const payload = JSON.parse(event.data || "{}");
          projections = normalizeSessionStateProjections(payload?.projections);
        } catch (_) {}
        if (projections.includes("messages")) {
          void refresh({ forceScroll: !!followMode });
          projections = projections.filter((projection) => projection !== "messages");
        }
        if (projections.length) void refreshSessionState(projections);
      });
      es.onerror = () => {};
    };
    startSessionStateEvents();
    const hoverCapabilityMedia = window.matchMedia("(hover: hover) and (pointer: fine)");
    const canUseHoverInteractions = () => hoverCapabilityMedia.matches;
    const touchBlurSelector = [
      ".quick-action",
      ".hub-page-menu-btn",
      ".composer-plus-toggle",
      ".target-chip",
      ".copy-btn",
      ".file-card",
      ".file-modal-close",
      ".send-btn",
      "#scrollToBottomBtn"
    ].join(", ");
    const syncHoverCapabilityClass = () => {
      document.documentElement.classList.toggle("has-hover", canUseHoverInteractions());
    };
    const blurTouchControlAfterTap = (event) => {
      if (canUseHoverInteractions()) return;
      const control = event.target?.closest?.(touchBlurSelector);
      if (!control) return;
      setTimeout(() => {
        if (typeof control.blur === "function") control.blur();
        const active = document.activeElement;
        if (active && active.matches?.(touchBlurSelector) && typeof active.blur === "function") {
          active.blur();
        }
      }, 0);
    };
    syncHoverCapabilityClass();
    if (hoverCapabilityMedia.addEventListener) {
      hoverCapabilityMedia.addEventListener("change", syncHoverCapabilityClass);
    } else if (hoverCapabilityMedia.addListener) {
      hoverCapabilityMedia.addListener(syncHoverCapabilityClass);
    }
    const _safariDummy = document.createElement("div");
    _safariDummy.style.cssText = "position:absolute;bottom:0;width:100%;height:env(safe-area-inset-bottom);pointer-events:none;opacity:0;z-index:-1;";
    document.body.appendChild(_safariDummy);

    const syncChatNotificationDefaults = async () => {
      try {
        const res = await fetch("/hub-settings", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (data?.theme === "light" || data?.theme === "dark") {
          document.documentElement.dataset.theme = data.theme;
        }
        if (typeof data?.agent_font_mode === "string" && data.agent_font_mode) {
          document.documentElement.dataset.agentFontMode = data.agent_font_mode;
        }
        if (typeof data?.chat_font_settings_css === "string") {
          const styleNode = document.getElementById("chatFontSettingsStyle");
          if (styleNode && styleNode.textContent !== data.chat_font_settings_css) {
            styleNode.textContent = data.chat_font_settings_css;
            const fileFrame = document.getElementById("fileModalFrame");
            if (fileFrame?.contentWindow) {
              const sz = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--message-text-size")) || 0;
              if (sz >= 8) {
                try {
                  fileFrame.contentWindow.postMessage(
                    { type: "agent-preview-text-size", size: sz },
                    window.location.origin,
                  );
                } catch (_) {}
              }
            }
          }
        }
      } catch (_) { }
    };
    syncChatNotificationDefaults();
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) syncChatNotificationDefaults();
    });

    document.addEventListener("pointerdown", (e) => {
      const toggle = e.target.closest(".hub-page-menu-btn, .composer-plus-toggle, .quick-action");
      if (toggle) {
        if (toggle.classList.contains("animating")) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        flashHeaderToggle(toggle);
      }
    });
    document.addEventListener("click", blurTouchControlAfterTap, true);
    const codeCopySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    const codeCheckSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    document.addEventListener("click", (e) => {
      const btn = e.target.closest(".code-copy-btn");
      if (!btn) return;
      const wrap = btn.closest(".code-block-wrap");
      if (!wrap) return;
      const code = wrap.querySelector("code") || wrap.querySelector("pre");
      navigator.clipboard.writeText(code.textContent).then(() => {
        btn.innerHTML = codeCheckSvg;
        setTimeout(() => { btn.innerHTML = codeCopySvg; }, 1500);
      });
    });
    const stripAnsiForTrace = (value) => String(value ?? "")
      .replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, "")
      .replace(/\u001b\][^\u0007]*\u0007/g, "");
