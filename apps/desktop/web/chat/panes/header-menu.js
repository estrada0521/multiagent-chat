    let rightMenuBtn = document.getElementById("hubPageMenuBtn");
    const rightMenuPanel = document.getElementById("hubPageMenuPanel");
    let nativeHeaderMenuBridge = document.getElementById("hubPageNativeMenuBridge");
    const desktopAppHeaderMenuRuntime = window.__MULTIAGENT_DESKTOP_APP__ || null;
    if (desktopAppHeaderMenuRuntime?.detachHubIframeHeaderMenu) {
      const detachedHeaderMenu = desktopAppHeaderMenuRuntime.detachHubIframeHeaderMenu({
        isTauriHubIframeChat,
        rightMenuBtn,
        nativeHeaderMenuBridge,
      });
      rightMenuBtn = detachedHeaderMenu.rightMenuBtn;
      nativeHeaderMenuBridge = detachedHeaderMenu.nativeHeaderMenuBridge;
    }
    const hasTauriNativeHeaderMenu = () => !!desktopAppHeaderMenuRuntime?.hasNativeHeaderMenu?.();
    desktopAppHeaderMenuRuntime?.installHeaderMenuBridge?.({
      isTauriHubIframeChat,
      rightMenuBtn,
      nativeHeaderMenuBridge,
      syncNativeBridgeOptionVisibility,
      runForwardAction,
    });
    document.querySelectorAll("[data-desktop-only='1']").forEach((node) => {
      node.hidden = false;
      if (node.tagName === "OPTION") node.disabled = false;
    });
    document.querySelectorAll("[data-mobile-only='1']").forEach((node) => {
      node.hidden = true;
      if (node.tagName === "OPTION") node.disabled = true;
    });
