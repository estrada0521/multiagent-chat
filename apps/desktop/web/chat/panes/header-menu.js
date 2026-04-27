    let rightMenuBtn = document.getElementById("hubPageMenuBtn");
    const rightMenuPanel = document.getElementById("hubPageMenuPanel");
    let nativeHeaderMenuBridge = document.getElementById("hubPageNativeMenuBridge");
    if (isTauriHubIframeChat) {
      rightMenuBtn?.remove();
      nativeHeaderMenuBridge?.remove();
      rightMenuBtn = null;
      nativeHeaderMenuBridge = null;
    }
    const DESKTOP_HUB_CHROME_SIZE_PX = 24;
    const getTauriInvoke = () => {
      try {
        return window.__TAURI__?.core?.invoke || window.__TAURI__?.invoke || null;
      } catch (_) {
        return null;
      }
    };
    const hasTauriNativeHeaderMenu = () => document.documentElement.dataset.tauriApp === "1";
    {
      const bridge = nativeHeaderMenuBridge;
      if (!isTauriHubIframeChat && bridge && rightMenuBtn) {
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
            bridge.style.pointerEvents = hasTauriNativeHeaderMenu() ? "none" : "auto";
            bridge.style.zIndex = "2";
            syncNativeBridgeOptionVisibility();
            return;
          }
          if (hasTauriNativeHeaderMenu()) {
            bridge.style.top = "-9999px";
            bridge.style.left = "-9999px";
            bridge.style.right = "auto";
            bridge.style.pointerEvents = "none";
            return;
          }
          const rect = btnRect;
          bridge.style.right = "auto";
          const rawLeft = Number.isFinite(rect.left) ? rect.left : 0;
          const rawTop = Number.isFinite(rect.top) ? rect.top : 0;
          const genericLeft = Math.max(0, Math.min(rawLeft, Math.max(0, viewportWidth - width)));
          const genericTop = Math.max(0, Math.min(rawTop, Math.max(0, viewportHeight - height)));
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
        window.visualViewport && window.visualViewport.addEventListener("resize", syncBridge, { passive: true });
        window.visualViewport && window.visualViewport.addEventListener("scroll", syncBridge, { passive: true });
        bridge.addEventListener("change", (e) => {
          const action = String(e.target.value || "");
          e.target.value = "";
          if (!action) return;
          void runForwardAction(action, { sourceNode: null, keepComposerOpen: false, keepHeaderOpen: false });
        });
      }
    }
    document.querySelectorAll("[data-desktop-only='1']").forEach((node) => {
      node.hidden = false;
      if (node.tagName === "OPTION") node.disabled = false;
    });
    document.querySelectorAll("[data-mobile-only='1']").forEach((node) => {
      node.hidden = true;
      if (node.tagName === "OPTION") node.disabled = true;
    });
