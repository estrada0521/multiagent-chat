(() => {
  const desktopApp = window.__MULTIAGENT_DESKTOP_APP__ || {};
  const DESKTOP_HUB_CHROME_SIZE_PX = 24;
  const bootstrapClientVariant = () => {
    try {
      const raw = String(window.__CHAT_BOOTSTRAP__?.clientVariant || "").trim().toLowerCase();
      return raw || "";
    } catch (_) {
      return "";
    }
  };

  desktopApp.isTauriDesktopApp = () => {
    const clientVariant = bootstrapClientVariant();
    if (clientVariant) return clientVariant === "desktop-app";
    return document.documentElement.dataset.tauriApp === "1";
  };
  desktopApp.isTauriHubIframeChat = () => (
    desktopApp.isTauriDesktopApp()
    && document.documentElement.dataset.hubIframeChat === "1"
  );
  desktopApp.shouldFloatHeaderActions = () => (
    desktopApp.isTauriDesktopApp() && !desktopApp.isTauriHubIframeChat()
  );
  desktopApp.hasNativeHeaderMenu = () => desktopApp.isTauriDesktopApp();
  desktopApp.getTauriInvoke = () => {
    try {
      return window.__TAURI__?.core?.invoke || window.__TAURI__?.invoke || null;
    } catch (_) {
      return null;
    }
  };
  desktopApp.detachHubIframeHeaderMenu = ({
    isTauriHubIframeChat,
    rightMenuBtn,
    nativeHeaderMenuBridge,
  }) => {
    if (!isTauriHubIframeChat) {
      return { rightMenuBtn, nativeHeaderMenuBridge };
    }
    rightMenuBtn?.remove();
    nativeHeaderMenuBridge?.remove();
    return { rightMenuBtn: null, nativeHeaderMenuBridge: null };
  };
  desktopApp.installHeaderMenuBridge = ({
    isTauriHubIframeChat,
    rightMenuBtn,
    nativeHeaderMenuBridge,
    syncNativeBridgeOptionVisibility,
    runForwardAction,
  }) => {
    const bridge = nativeHeaderMenuBridge;
    if (isTauriHubIframeChat || !bridge || !rightMenuBtn) return;
    const syncBridge = () => {
      if (!rightMenuBtn || !rightMenuBtn.isConnected) return;
      const btnRect = rightMenuBtn.getBoundingClientRect();
      const fallbackWidth = DESKTOP_HUB_CHROME_SIZE_PX;
      const fallbackHeight = DESKTOP_HUB_CHROME_SIZE_PX;
      const width = Number.isFinite(btnRect.width) && btnRect.width > 0 ? btnRect.width : fallbackWidth;
      const height = Number.isFinite(btnRect.height) && btnRect.height > 0 ? btnRect.height : fallbackHeight;
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
      const dockedToFloatingActions = !!bridge.parentElement?.classList.contains("hub-page-header-actions-floating");
      if (dockedToFloatingActions) {
        bridge.style.position = "absolute";
        bridge.style.left = "0px";
        bridge.style.top = "0px";
        bridge.style.right = "auto";
        bridge.style.width = "100%";
        bridge.style.height = "100%";
        bridge.style.opacity = "0.001";
        bridge.style.pointerEvents = desktopApp.hasNativeHeaderMenu() ? "none" : "auto";
        bridge.style.zIndex = "2";
        syncNativeBridgeOptionVisibility();
        return;
      }
      if (desktopApp.hasNativeHeaderMenu()) {
        bridge.style.top = "-9999px";
        bridge.style.left = "-9999px";
        bridge.style.right = "auto";
        bridge.style.pointerEvents = "none";
        return;
      }
      const rawLeft = Number.isFinite(btnRect.left) ? btnRect.left : 0;
      const rawTop = Number.isFinite(btnRect.top) ? btnRect.top : 0;
      const genericLeft = Math.max(0, Math.min(rawLeft, Math.max(0, viewportWidth - width)));
      const genericTop = Math.max(0, Math.min(rawTop, Math.max(0, viewportHeight - height)));
      bridge.style.right = "auto";
      bridge.style.left = `${Math.round(genericLeft)}px`;
      bridge.style.top = `${Math.round(genericTop)}px`;
      bridge.style.width = `${Math.max(1, Math.round(width))}px`;
      bridge.style.height = `${Math.max(1, Math.round(height))}px`;
      bridge.style.opacity = "0.001";
      bridge.style.pointerEvents = "auto";
      bridge.style.zIndex = "999";
      syncNativeBridgeOptionVisibility();
    };
    syncBridge();
    requestAnimationFrame(syncBridge);
    window.addEventListener("load", syncBridge, { once: true });
    window.addEventListener("resize", syncBridge, { passive: true });
    window.addEventListener("scroll", syncBridge, { passive: true, capture: true });
    window.visualViewport?.addEventListener("resize", syncBridge, { passive: true });
    window.visualViewport?.addEventListener("scroll", syncBridge, { passive: true });
    bridge.addEventListener("change", (event) => {
      const action = String(event.target.value || "");
      event.target.value = "";
      if (!action) return;
      void runForwardAction(action, { sourceNode: null, keepComposerOpen: false, keepHeaderOpen: false });
    });
  };
  desktopApp.openChatHeaderMenu = async ({
    anchorRect = null,
    rightMenuBtn,
    sessionActive,
    allBaseAgents,
    agentActionCandidates,
    agentBaseName,
    agentIconSrc,
    renderAgentIconRgba,
  }) => {
    const invoke = desktopApp.getTauriInvoke();
    const fallbackRect = rightMenuBtn?.getBoundingClientRect?.() || null;
    const rectSource = anchorRect && typeof anchorRect === "object" ? anchorRect : fallbackRect;
    if (!rectSource) return false;
    const rect = {
      left: Number(rectSource.left || 0),
      top: Number(rectSource.top || 0),
      right: Number(rectSource.right || 0),
      bottom: Number(rectSource.bottom || 0),
      width: Number(rectSource.width || 24),
      height: Number(rectSource.height || 24),
    };
    const agentIcons = {};
    const allAgentNames = [...new Set([
      ...allBaseAgents.filter(Boolean),
      ...agentActionCandidates("remove"),
    ])];
    for (const name of allAgentNames) {
      const base = agentBaseName(name);
      if (agentIcons[base]) continue;
      try {
        const rgba = await renderAgentIconRgba(agentIconSrc(name));
        if (rgba) agentIcons[base] = rgba;
      } catch (_) {}
    }
    const payload = {
      x: Math.round(rect.left || 0),
      y: Math.round((rect.bottom || ((rect.top || 0) + (rect.height || 28))) + 2),
      sessionActive: !!sessionActive,
      addAgents: allBaseAgents.filter(Boolean),
      removeAgents: agentActionCandidates("remove"),
      agentIcons,
    };
    if (typeof invoke === "function") {
      await invoke("show_chat_header_menu", { payload });
    } else if (window.parent && window.parent !== window) {
      window.parent.postMessage({
        type: "multiagent-show-chat-header-menu",
        payload,
      }, "*");
    } else {
      return false;
    }
    return true;
  };
  desktopApp.handleChatHeaderMenuAction = async ({
    payload,
    closeHeaderMenus,
    performAgentAction,
    runForwardAction,
  }) => {
    const data = payload || {};
    if (data.action === "agent") {
      const mode = String(data.mode || "");
      const agent = String(data.agent || "");
      if ((mode === "add" || mode === "remove") && agent) {
        closeHeaderMenus();
        await performAgentAction(mode, agent);
      }
      return;
    }
    const action = String(data.action || "");
    if (!action) return;
    void runForwardAction(action, { sourceNode: null, keepComposerOpen: false, keepHeaderOpen: false });
  };
  window.__MULTIAGENT_DESKTOP_APP__ = desktopApp;
})();
