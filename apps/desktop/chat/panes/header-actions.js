    const closeHeaderMenus = () => {
      resetAgentActionMenus();
    };
    const renderAgentIconRgba = (src) => new Promise((resolve) => {
      if (!src) return resolve(null);
      const SIZE = 22;
      const PAD = 3;
      const img = new window.Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        try {
          const canvas = document.createElement("canvas");
          canvas.width = SIZE;
          canvas.height = SIZE;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, PAD, PAD, SIZE - PAD * 2, SIZE - PAD * 2);
          const imgData = ctx.getImageData(0, 0, SIZE, SIZE);
          const px = imgData.data;
          const iconVal = window.matchMedia("(prefers-color-scheme: dark)").matches ? 255 : 0;
          for (let i = 0; i < px.length; i += 4) {
            px[i] = iconVal; px[i + 1] = iconVal; px[i + 2] = iconVal;
          }
          resolve(Array.from(px));
        } catch (e) { resolve(null); }
      };
      img.onerror = () => resolve(null);
      img.src = src;
    });
    const openTauriHeaderMenu = async (anchorRect = null) => {
      const invoke = getTauriInvoke();
      const fallbackRect = rightMenuBtn?.getBoundingClientRect?.() || null;
      const hasExplicitAnchor = !!(anchorRect && typeof anchorRect === "object");
      const rectSource = hasExplicitAnchor ? anchorRect : fallbackRect;
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
        ...ALL_BASE_AGENTS.filter(Boolean),
        ...agentActionCandidates("remove"),
      ])];
      await Promise.all(allAgentNames.map(async (name) => {
        const base = agentBaseName(name);
        if (!agentIcons[base]) {
          try {
            const rgba = await renderAgentIconRgba(agentIconSrc(name));
            if (rgba) agentIcons[base] = rgba;
          } catch (_) {}
        }
      }));

      const payload = {
        x: Math.round(rect.left || 0),
        y: Math.round((rect.bottom || ((rect.top || 0) + (rect.height || 28))) + 2),
        sessionActive: !!sessionActive,
        addAgents: ALL_BASE_AGENTS.filter(Boolean),
        removeAgents: agentActionCandidates("remove"),
        agentIcons,
      };
      if (typeof invoke === "function") {
        await invoke("show_chat_header_menu", { payload });
      } else if (window.parent && window.parent !== window) {
        window.parent.postMessage({
          type: "show-chat-header-menu",
          payload,
        }, "*");
      } else {
        return false;
      }
      return true;
    };
    const handleTauriNativeMenuAction = async (payload) => {
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
      void runForwardAction(action, { sourceNode: null });
    };
    window.addEventListener("message", (event) => {
      if (!(event.data && event.data.type === "native-menu-action")) return;
      void handleTauriNativeMenuAction(event.data.payload);
    });
    window.addEventListener("message", (event) => {
      if (!(event.data && event.data.type === "open-chat-header-menu")) return;
      const anchorData = event.data.anchor || null;
      const anchorRect = anchorData && typeof anchorData === "object"
        ? {
            left: Number(anchorData.left || 0),
            top: Number(anchorData.top || 0),
            right: Number(anchorData.right || 0),
            bottom: Number(anchorData.bottom || 0),
            width: Number(anchorData.width || 24),
            height: Number(anchorData.height || 24),
          }
        : null;
      if (hasTauriNativeHeaderMenu()) {
        closeHeaderMenus();
        openTauriHeaderMenu(anchorRect).catch(() => {});
        return;
      }
      if (typeof nativeHeaderMenuBridge?.showPicker === "function") {
        try { nativeHeaderMenuBridge.showPicker(); } catch (_) {}
      }
    });
    window.addEventListener("native-menu-action", (event) => {
      void handleTauriNativeMenuAction(event.detail || {});
    });
    rightMenuBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();

      if (hasTauriNativeHeaderMenu()) {
        closeHeaderMenus();
        openTauriHeaderMenu().catch(() => {});
        return;
      }
      closeHeaderMenus();
    });
    window.addEventListener("resize", () => {
      if (dpPanelOpen) {
        dpApplyPanelWidth();
      }
      notifyParentPanelState();
    });
    document.addEventListener("click", (event) => {

      const inRightMenu = rightMenuBtn?.contains(event.target);
      const inNativeBridgeMenu = nativeHeaderMenuBridge?.contains(event.target);
      const agentActionNativeMenu = document.getElementById("agentActionNativeMenuSelect");
      const inAgentActionMenu = agentActionNativeMenu?.contains(event.target);
      if (!inRightMenu && !inNativeBridgeMenu && !inAgentActionMenu) {
        closeHeaderMenus();
      }
    });
    async function runForwardAction(target, { sourceNode = null } = {}) {
      const action = String(target || "");
      if (!action) return;
      if (action === "esc" || action === "restart" || action === "resume" || action === "ctrlc" || action === "enter") {
        await postShortcutCommand({ command_id: action, arg: "" });
        return;
      }
      if (action === "reloadChat") {
        await beginNewChat(sourceNode);
        return;
      }
      if (action === "openTerminal") {
        fetch("/open-terminal", { method: "POST" }).catch(() => {});
        return;
      }
      if (action === "openFinder") {
        try {
          const res = await fetch("/open-finder", { method: "POST" });
          if (res.ok) {
            setStatus("opened Finder");
            setTimeout(() => setStatus(""), STATUS_TOAST_MS);
          } else {
            const data = await res.json().catch(() => ({}));
            setStatus(data.error || "Finder open failed", true);
            setTimeout(() => setStatus(""), STATUS_TOAST_MS);
          }
        } catch (err) {
          setStatus(`Finder open error: ${err.message}`, true);
          setTimeout(() => setStatus(""), STATUS_TOAST_MS);
        }
        return;
      }
      if (action === "openSettingsFile") {
        try {
          const res = await fetch("/open-settings-file", { method: "POST" });
          if (res.ok) {
            setStatus("opened settings file");
            setTimeout(() => setStatus(""), STATUS_TOAST_MS);
          } else {
            const data = await res.json().catch(() => ({}));
            setStatus(data.error || "settings file open failed", true);
            setTimeout(() => setStatus(""), STATUS_TOAST_MS);
          }
        } catch (err) {
          setStatus(`settings file open error: ${err.message}`, true);
          setTimeout(() => setStatus(""), STATUS_TOAST_MS);
        }
        return;
      }
      if (action === "addAgent") {
        if (!sessionActive) {
          setStatus("archived session is read-only", true);
          setTimeout(() => setStatus(""), STATUS_TOAST_MS);
          return;
        }
        showAddAgentModal();
        return;
      }
      if (action === "removeAgent") {
        if (!sessionActive) {
          setStatus("archived session is read-only", true);
          setTimeout(() => setStatus(""), STATUS_TOAST_MS);
          return;
        }
        showRemoveAgentModal();
        return;
      }
      throw new Error(`unknown menu action: ${action}`);
    }
