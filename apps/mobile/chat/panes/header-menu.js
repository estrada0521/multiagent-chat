    let keepComposerPlusMenuOnBlur = false;
    const hubRootUrl = () => {
      if (CHAT_BASE_PATH || String(window.location.pathname || "").startsWith("/session/")) {
        return `${window.location.origin}/`;
      }
      const portValue = Number(CHAT_BOOTSTRAP.hubPort || 0);
      const protocol = window.location.protocol || "http:";
      const host = window.location.hostname || "127.0.0.1";
      const defaultPort =
        (protocol === "https:" && portValue === 443) ||
        (protocol === "http:" && portValue === 80);
      if (portValue > 0 && !defaultPort) {
        return `${protocol}//${host}:${portValue}/`;
      }
      return `${protocol}//${host}/`;
    };
    const hubUrlForPath = (path = "/") => {
      const normalizedPath = String(path || "/").startsWith("/") ? String(path || "/") : `/${String(path || "/")}`;
      return `${hubRootUrl().replace(/\/$/, "")}${normalizedPath}`;
    };
    const requestHubTop = () => {
      const hubUrl = hubUrlForPath("/");
      if (window.self !== window.top) {
        try {
          window.parent.postMessage({ type: "multiagent-open-hub-path", url: hubUrl, reveal: true }, "*");
        } catch (_) {
          requestHubCloseChat();
        }
        return;
      }
      window.location.href = hubUrl;
    };
    const openHubPath = (path = "/") => {
      const normalizedPath = String(path || "/").startsWith("/") ? String(path || "/") : `/${String(path || "/")}`;
      const hubUrl = hubUrlForPath(normalizedPath);
      if (window.self !== window.top) {
        if (normalizedPath === "/") {
          requestHubTop();
          return;
        }
        try {
          window.parent.location.href = hubUrl;
          return;
        } catch (_err) {
          window.parent.postMessage({ type: "multiagent-open-hub-path", url: hubUrl }, "*");
          return;
        }
      }
      window.location.href = hubUrl;
    };
    hubBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      openHubPath("/");
    });
    composerPlusMenu && composerPlusMenu.addEventListener("toggle", () => {
      if (!composerPlusMenu.open) {
        composerPlusMenu.querySelectorAll(".plus-submenu").forEach(sub => { sub.open = false; });
      }
    });
    composerPlusMenu?.addEventListener("pointerdown", () => {
      keepComposerPlusMenuOnBlur = true;
      setTimeout(() => { keepComposerPlusMenuOnBlur = false; }, 240);
    });
    composerPlusMenu?.addEventListener("touchstart", () => {
      keepComposerPlusMenuOnBlur = true;
      setTimeout(() => { keepComposerPlusMenuOnBlur = false; }, 240);
    }, { passive: true });
    composerPlusMenu?.addEventListener("click", (event) => {
      const keepFocusTarget = event.target.closest(".plus-submenu-toggle, .composer-plus-panel .quick-action");
      if (!keepFocusTarget) return;
      if (event.target.closest("#cameraBtn")) return;
      requestAnimationFrame(() => {
        if (document.activeElement !== messageInput) {
          focusMessageInputWithoutScroll();
        }
      });
    });
    composerPlusMenu && composerPlusMenu.querySelectorAll(".plus-submenu").forEach(sub => {
      sub.addEventListener("toggle", () => {
        if (sub.open) {
          composerPlusMenu.querySelectorAll(".plus-submenu").forEach(other => {
            if (other !== sub) other.open = false;
          });
        }
      });
    });
    const closePlusMenu = () => {
      if (composerPlusMenu && composerPlusMenu.open) {
        composerPlusMenu.classList.add("closing");
        setTimeout(() => {
          composerPlusMenu.open = false;
          composerPlusMenu.classList.remove("closing");
        }, 160);
      }
    };
    composerPlusMenu?.querySelector(".composer-plus-toggle")?.addEventListener("mousedown", (e) => e.preventDefault());
    composerPlusMenu?.addEventListener("toggle", () => {
      if (composerPlusMenu.open) closeDrop();
    });
    const rightMenuBtn = document.getElementById("hubPageMenuBtn");
    const rightMenuPanel = document.getElementById("hubPageMenuPanel");
    const nativeHeaderMenuBridge = document.getElementById("hubPageNativeMenuBridge");
    {
      const bridge = nativeHeaderMenuBridge;
      if (bridge && rightMenuBtn) {
        const syncBridge = () => {
          if (!rightMenuBtn || rightMenuBtn.offsetParent === null) return;
          const rect = rightMenuBtn.getBoundingClientRect();
          const padX = 4;
          const padY = 4;
          let left = Math.max(0, rect.left - padX);
          let top = Math.max(0, rect.top - padY);
          const width = rect.width + (padX * 2);
          const height = rect.height + (padY * 2);
          const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
          const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
          if (viewportWidth > 0 && left + width > viewportWidth) {
            left = Math.max(0, viewportWidth - width);
          }
          if (viewportHeight > 0 && top + height > viewportHeight) {
            top = Math.max(0, viewportHeight - height);
          }
          bridge.style.left = `${left}px`;
          bridge.style.top = `${top}px`;
          bridge.style.width = `${width}px`;
          bridge.style.height = `${height}px`;
          // opacity:0 (not 0.001) so focus ring is invisible; pointer-events:auto keeps it tappable
          bridge.style.opacity = "0";
          bridge.style.pointerEvents = "auto";
          bridge.style.zIndex = "999";
          bridge.style.background = "transparent";
          bridge.style.color = "transparent";
          bridge.style.border = "0";
          bridge.style.outline = "none";
          bridge.style.webkitTapHighlightColor = "transparent";
          Array.from(bridge.options).forEach((opt) => {
            if (opt.dataset.mobileOnly === "1") {
              opt.hidden = false;
              opt.disabled = false;
            }
          });
        };
        syncBridge();
        window.addEventListener("resize", syncBridge, { passive: true });
        window.addEventListener("scroll", syncBridge, { passive: true });
        window.visualViewport && window.visualViewport.addEventListener("resize", syncBridge, { passive: true });
        window.visualViewport && window.visualViewport.addEventListener("scroll", syncBridge, { passive: true });
        rightMenuBtn.addEventListener("pointerdown", syncBridge, { passive: true });
        bridge.addEventListener("pointerdown", () => resetAgentActionNativeMenu({ clearOptions: true }), { passive: true });
        bridge.addEventListener("change", (e) => {
          const action = e.target.value;
          e.target.value = "";
          if (!action) return;
          void runForwardAction(action, { sourceNode: null, keepComposerOpen: false, keepHeaderOpen: false });
        });
      }
    }
    document.querySelectorAll("[data-desktop-only='1']").forEach((node) => {
      node.hidden = true;
      if (node.tagName === "OPTION") node.disabled = true;
    });
    document.querySelectorAll("[data-mobile-only='1']").forEach((node) => {
      node.hidden = false;
      if (node.tagName === "OPTION") node.disabled = false;
    });
