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
    const refreshSessionState = async () => {
      if (sessionStateInFlight) {
        pendingSessionStateRefresh = true;
        return;
      }
      sessionStateInFlight = true;
      try {
        const res = await fetchWithTimeout(`/session-state?ts=${Date.now()}`, {}, 4000);
        if (res.ok) applySessionState(await res.json());
      } catch (_) {
      } finally {
        sessionStateInFlight = false;
        if (pendingSessionStateRefresh) {
          pendingSessionStateRefresh = false;
          queueMicrotask(() => { void refreshSessionState(); });
        }
      }
    };
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
    // Sound
    const setSoundBtn = (on) => {
      soundEnabled = !!on;
    };
    setSoundBtn(soundEnabled);

    // Safari safe area layout hack
    const _safariDummy = document.createElement("div");
    _safariDummy.style.cssText = "position:absolute;bottom:0;width:100%;height:env(safe-area-inset-bottom);pointer-events:none;opacity:0;z-index:-1;";
    document.body.appendChild(_safariDummy);

    const syncChatNotificationDefaults = async () => {
      try {
        const res = await fetch("/hub-settings", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (typeof data?.agent_font_mode === "string" && data.agent_font_mode) {
          document.documentElement.dataset.agentFontMode = data.agent_font_mode;
        }
        if (typeof data?.chat_font_settings_css === "string") {
          const styleNode = document.getElementById("chatFontSettingsStyle");
          if (styleNode && styleNode.textContent !== data.chat_font_settings_css) {
            styleNode.textContent = data.chat_font_settings_css;
          }
        }
        if (typeof data?.chat_sound === "boolean") {
          setSoundBtn(data.chat_sound);
        }
      } catch (_) { }
    };
    syncChatNotificationDefaults();
    setInterval(syncChatNotificationDefaults, 30000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) syncChatNotificationDefaults();
    });

    // Auto-prime on first user gesture if sound is on
    const primeSoundOnGesture = async () => {
      if (_audioPrimed) return;
      await primeSound();
    };
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
    document.addEventListener("click", primeSoundOnGesture);
    document.addEventListener("click", blurTouchControlAfterTap, true);
    // Delegated handler for code block copy buttons
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
    /** Strip ANSI escapes (fallback when ansi_up is unavailable). */
    const stripAnsiForTrace = (value) => String(value ?? "")
      .replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, "")
      .replace(/\u001b\][^\u0007]*\u0007/g, "");
