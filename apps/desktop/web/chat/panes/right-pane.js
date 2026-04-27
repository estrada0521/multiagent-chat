    let paneViewerInterval = null;
    let paneViewerTabScrollRaf = 0;
    let paneViewerTabScrollEndTimer = null;
    let paneViewerOpenRaf = 0;
    let paneViewerInitialFetchTimer = 0;
    let lastPaneViewerTabIdx = 0;
    const headerRoot = document.querySelector(".hub-page-header");
    const shellRoot = document.querySelector(".shell");
    const hasOpenHeaderMenu = () => !!rightMenuPanel?.classList.contains("open");
    const updateHeaderMenuViewportMetrics = () => {
      if (!headerRoot) return;
      const headerRect = headerRoot.getBoundingClientRect();
      const shellRect = shellRoot?.getBoundingClientRect?.() || headerRect;
      const top = Math.max(0, Math.round(headerRect.bottom));
      const left = Math.max(0, Math.round(shellRect.left));
      const width = Math.max(0, Math.round(shellRect.width));
      const right = Math.max(0, Math.round((window.innerWidth || 0) - (shellRect.right || (left + width))));
      document.documentElement.style.setProperty("--header-menu-top", `${top}px`);
      document.documentElement.style.setProperty("--header-menu-left", `${left}px`);
      document.documentElement.style.setProperty("--header-menu-width", `${width}px`);
      document.documentElement.style.setProperty("--chat-surface-left", `${left}px`);
      document.documentElement.style.setProperty("--chat-surface-width", `${width}px`);
      document.documentElement.style.setProperty("--chat-surface-right", `${right}px`);
    };
    const syncHeaderMenuFocus = () => {
      const paneTraceOpen = !!document.getElementById("paneViewer")?.classList.contains("visible");
      const fileModalOpen = document.body.classList.contains("file-modal-open");
      const focused = hasOpenHeaderMenu() || paneTraceOpen || fileModalOpen;
      if (focused) updateHeaderMenuViewportMetrics();
    };
    const needsHeaderViewportMetrics = () =>
      hasOpenHeaderMenu() || !!document.getElementById("paneViewer")?.classList.contains("visible");
    const clearPaneViewerOpenWork = () => {
      if (paneViewerOpenRaf) {
        cancelAnimationFrame(paneViewerOpenRaf);
        paneViewerOpenRaf = 0;
      }
      if (paneViewerInitialFetchTimer) {
        clearTimeout(paneViewerInitialFetchTimer);
        paneViewerInitialFetchTimer = 0;
      }
    };
    function exitPaneTraceMode() {
      const paneEl = document.getElementById("paneViewer");
      clearPaneViewerOpenWork();
      if (paneViewerTabScrollEndTimer) {
        clearTimeout(paneViewerTabScrollEndTimer);
        paneViewerTabScrollEndTimer = null;
      }
      if (paneEl?.classList?.contains("visible") && paneViewerCarousel && paneViewerAgents.length) {
        const w = paneViewerCarousel.offsetWidth;
        if (w) {
          const idx = Math.max(0, Math.min(paneViewerAgents.length - 1, Math.round(paneViewerCarousel.scrollLeft / w)));
          paneViewerLastAgent = paneViewerAgents[idx];
        }
      }
      if (paneEl) paneEl.classList.remove("visible");
      rightMenuPanel?.classList.remove("hub-menu-mode-pane");
      if (paneViewerInterval) {
        clearInterval(paneViewerInterval);
        paneViewerInterval = null;
      }
      syncHeaderMenuFocus();
    }
    const isLocalHubHostname = (host = String(location.hostname || "")) =>
      host === "127.0.0.1" || host === "localhost" || host === "[::1]" || host.startsWith("192.168.") || host.startsWith("10.") || /^172\\.(1[6-9]|2\\d|3[01])\\./.test(host);
    const closeHeaderMenus = () => {
      resetAgentActionMenus();
      exitPaneTraceMode();
      rightMenuPanel?.classList.remove("open");
      if (rightMenuPanel) rightMenuPanel.hidden = true;
      rightMenuBtn?.classList.remove("open");
      syncHeaderMenuFocus();
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
          for (let i = 0; i < px.length; i += 4) {
            px[i] = 255; px[i + 1] = 255; px[i + 2] = 255;
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
      for (const name of allAgentNames) {
        const base = agentBaseName(name);
        if (!agentIcons[base]) {
          try {
            const rgba = await renderAgentIconRgba(agentIconSrc(name));
            if (rgba) agentIcons[base] = rgba;
          } catch (_) {}
        }
      }

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
          type: "multiagent-show-chat-header-menu",
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
      void runForwardAction(action, { sourceNode: null, keepComposerOpen: false, keepHeaderOpen: false });
    };
    window.addEventListener("message", (event) => {
      if (!(event.data && event.data.type === "multiagent-native-menu-action")) return;
      void handleTauriNativeMenuAction(event.data.payload);
    });
    window.addEventListener("message", (event) => {
      if (!(event.data && event.data.type === "multiagent-open-chat-header-menu")) return;
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
      rightMenuBtn?.click();
    });
    window.addEventListener("multiagent-native-menu-action", (event) => {
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
    const closePreviewFromIcon = () => {
      closeFileModal({ restoreFocus: false });
    };
    fileModalIcon?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      closePreviewFromIcon();
    });
    fileModalIcon?.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      event.stopPropagation();
      closePreviewFromIcon();
    });
    const closeQuickMore = () => {
      if (quickMore) quickMore.open = false;
      closePlusMenu();
      closeHeaderMenus();
    };
    const stopCameraModeStream = () => {
      if (cameraModeVideo) {
        try { cameraModeVideo.pause(); } catch (_) {}
        try { cameraModeVideo.srcObject = null; } catch (_) {}
      }
      if (cameraModeStream) {
        cameraModeStream.getTracks().forEach((track) => {
          try {
            track.onended = null;
            track.stop();
          } catch (_) {}
        });
      }
      cameraModeStream = null;
    };
    const canvasToJpegBlob = (canvas, quality = 0.7) => new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error("image encoding failed"));
      }, "image/jpeg", quality);
    });
    const decodeImageForResize = async (blob) => {
      if (typeof createImageBitmap === "function") {
        try {
          return await createImageBitmap(blob);
        } catch (_) {}
      }
      return await new Promise((resolve, reject) => {
        const url = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
          URL.revokeObjectURL(url);
          resolve(img);
        };
        img.onerror = () => {
          URL.revokeObjectURL(url);
          reject(new Error("image decode failed"));
        };
        img.src = url;
      });
    };
    const resizeCameraModeBlob = async (blob, { maxSide = 1280, quality = 0.7 } = {}) => {
      const image = await decodeImageForResize(blob);
      try {
        const width = Number(image.width || image.videoWidth || image.naturalWidth || 0);
        const height = Number(image.height || image.videoHeight || image.naturalHeight || 0);
        if (!width || !height) return blob;
        const scale = Math.min(1, maxSide / Math.max(width, height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        const ctx = canvas.getContext("2d", { alpha: false });
        if (!ctx) return blob;
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
        return await canvasToJpegBlob(canvas, quality);
      } finally {
        try { image.close?.(); } catch (_) {}
      }
    };
    const captureCameraModeFrameBlob = async ({ maxSide = 1280, quality = 0.7 } = {}) => {
      if (!cameraModeVideo) throw new Error("camera unavailable");
      const width = Number(cameraModeVideo.videoWidth || 0);
      const height = Number(cameraModeVideo.videoHeight || 0);
      if (!width || !height) throw new Error("camera not ready");
      const scale = Math.min(1, maxSide / Math.max(width, height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      const ctx = canvas.getContext("2d", { alpha: false });
      if (!ctx) throw new Error("camera capture unavailable");
      ctx.drawImage(cameraModeVideo, 0, 0, canvas.width, canvas.height);
      return canvasToJpegBlob(canvas, quality);
    };
    const uploadCameraModeBlob = async (blob, filename) => {
      const res = await fetch("/upload", {
        method: "POST",
        headers: {
          "Content-Type": blob.type || "image/jpeg",
          "X-Filename": encodeURIComponent(filename || `camera_${Date.now()}.jpg`),
        },
        body: blob,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok || !data.path) {
        throw new Error(data.error || "upload failed");
      }
      return data.path;
    };
    const sendCameraModeAttachment = async (path, target) => {
      const res = await fetch("/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, message: `[Attached: ${path}]` }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        throw new Error(data.error || "send failed");
      }
      return data;
    };
    const sendCameraModeText = async (text, target) => {
      const message = String(text || "").trim();
      if (!message) {
        throw new Error("message is required");
      }
      const res = await fetch("/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, message }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        throw new Error(data.error || "send failed");
      }
      return data;
    };
    const setCameraModeBusy = (busy, hint = "", isError = false) => {
      cameraModeBusy = !!busy;
      syncCameraModeBusyState();
      if (hint && isError) {
        setCameraModeHint(hint, isError);
      }
    };
    const closeCameraMode = () => {
      if (!cameraMode || cameraMode.hidden) return;
      cancelCameraModeMicRecognition();
      stopCameraModeStream();
      cameraMode.hidden = true;
      cameraMode.classList.remove("visible", "busy");
      document.body.classList.remove("camera-mode-open");
      cameraModeBackdropFrosted = false;
      syncCameraModeBackdrop();
      setCameraModeHint("");
      setCameraModeFallbackState(false);
      cameraModeBusy = false;
      cameraModeMicListening = false;
      cameraModeOpening = false;
      setCameraModeTargetsExpanded(false);
      restoreTimelineFromCameraMode();
      renderCameraModeReplies();
      renderCameraModeThinking();
      syncCameraModeBusyState();
      updateScrollBtn();
    };
    const startCameraModeStream = async () => {
      stopCameraModeStream();
      setCameraModeFallbackState(false);
      if (!window.isSecureContext) {
        return fallbackToCameraModeChat("HTTPS is required for camera.", true);
      }
      if (isCameraBlockedByPolicy()) {
        return fallbackToCameraModeChat("Camera is blocked by the parent page.", true);
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        return fallbackToCameraModeChat("Live camera is unavailable here.", true);
      }
      try {
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
        });
        cameraModeStream = stream;
        const track = stream.getVideoTracks()[0] || null;
        if (track) {
          track.onended = () => {
            if (cameraMode?.hidden) return;
            stopCameraModeStream();
            fallbackToCameraModeChat("Camera ended. Returned to chat.", true);
          };
        }
        if (cameraModeVideo) {
          cameraModeVideo.srcObject = stream;
          cameraModeVideo.muted = true;
          cameraModeVideo.playsInline = true;
          await cameraModeVideo.play().catch(() => {});
        }
        setCameraModeHint("");
        return true;
      } catch (err) {
        const name = String(err?.name || "");
        let message = "Live camera unavailable.";
        if (!window.isSecureContext) {
          message = "HTTPS is required for camera.";
        } else if (isCameraBlockedByPolicy()) {
          message = "Camera is blocked by the parent page.";
        } else if (name === "NotAllowedError") {
          message = "Camera access denied. Check browser settings.";
        } else if (name === "NotFoundError") {
          message = "No camera found on this device.";
        } else if (name === "NotReadableError") {
          message = "Camera is busy in another app.";
        }
        return fallbackToCameraModeChat(message, true);
      }
    };
    const flashCameraModeSendEffect = () => {
      if (!cameraMode) return;
      const el = document.createElement("div");
      el.className = "camera-mode-send-border";
      cameraMode.appendChild(el);
      el.addEventListener("animationend", () => el.remove(), { once: true });
    };
    const runCameraModeSend = async (sourceBlob) => {
      const target = syncCameraModeTarget();
      if (!target) {
        setCameraModeHint("No available agent target.", true);
        return false;
      }
      if (!sourceBlob) {
        setCameraModeHint("No image captured.", true);
        return false;
      }
      try {
        setCameraModeHint("");
        setCameraModeBusy(true);
        const prepared = await resizeCameraModeBlob(sourceBlob, { maxSide: 1280, quality: 0.7 });
        const filename = `camera_${Date.now()}.jpg`;
        const uploadedPath = await uploadCameraModeBlob(prepared, filename);
        await sendCameraModeAttachment(uploadedPath, target);
        await refresh({ forceScroll: true });
        setCameraModeBusy(false);
        flashCameraModeSendEffect();
        return true;
      } catch (err) {
        setCameraModeBusy(false, err?.message || "camera send failed", true);
        return false;
      }
    };
    const captureAndSendCameraMode = async () => {
      if (cameraModeBusy) return;
      if (cameraModeStream && cameraModeVideo && Number(cameraModeVideo.videoWidth || 0) > 0) {
        try {
          const blob = await captureCameraModeFrameBlob({ maxSide: 1280, quality: 0.7 });
          await runCameraModeSend(blob);
          return;
        } catch (err) {
          fallbackToCameraModeChat(err?.message || "camera capture failed", true);
          return;
        }
      }
      fallbackToCameraModeChat("Live camera is unavailable. Returned to chat.", true);
    };
    const openCameraMode = async () => {
      if (!cameraMode || cameraModeOpening) return;
      if (!sessionActive) {
        setStatus("archived session is read-only", true);
        setTimeout(() => setStatus(""), 2200);
        return;
      }
      if (!cameraModeAllowedTargets().length) {
        setStatus("no available camera target", true);
        setTimeout(() => setStatus(""), 2200);
        return;
      }
      cameraModeOpening = true;
      closeFileModal({ restoreFocus: false });
      closeQuickMore();
      if (isComposerOverlayOpen()) {
        try { messageInput?.blur?.(); } catch (_) {}
        closeComposerOverlay();
      }
      cameraModeBackdropFrosted = false;
      syncCameraModeBackdrop();
      cameraMode.hidden = false;
      cameraMode.classList.add("visible");
      document.body.classList.add("camera-mode-open");
      setCameraModeTargetsExpanded(false);
      mountTimelineIntoCameraMode();
      syncCameraModeReplies();
      renderCameraModeThinking();
      setCameraModeHint("");
      setCameraModeFallbackState(false);
      renderCameraModeTargets();
      syncCameraModeBusyState();
      updateScrollBtn();
      await startCameraModeStream();
      cameraModeOpening = false;
    };
    cameraModeCloseBtn?.addEventListener("click", () => {
      if (cameraModeBusy) return;
      closeCameraMode();
    });
    cameraModeTargetToggleBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (cameraModeBusy) return;
      setCameraModeTargetsExpanded(!cameraModeTargetsExpanded);
      renderCameraModeTargets();
    });
    cameraModeShutterBtn?.addEventListener("click", () => {
      setCameraModeTargetsExpanded(false);
      void captureAndSendCameraMode();
    });
    cameraModeBackdropBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (!cameraMode || cameraMode.hidden) return;
      cameraModeBackdropFrosted = !cameraModeBackdropFrosted;
      syncCameraModeBackdrop();
    });
    cameraModeShell?.addEventListener("click", (event) => {
      if (!cameraModeTargetsExpanded) return;
      if (event.target.closest(".camera-mode-thinking-shell")) return;
      setCameraModeTargetsExpanded(false);
      renderCameraModeTargets();
      renderCameraModeThinking();
    });
    window.addEventListener("resize", () => {
      if (document.body.classList.contains("file-modal-desktop-split")) {
        applyDesktopFilePaneWidthPx(getDesktopFilePaneWidthPx());
        updateFileModalViewportMetrics();
      } else {
        void maybeRestoreFileModalSessionState(currentSessionName);
      }
      if (dpPanelOpen) {
        dpApplyPanelWidth();
        if (!fileModal.hidden) updateFileModalViewportMetrics();
      }
      if (needsHeaderViewportMetrics()) updateHeaderMenuViewportMetrics();
      syncCameraModeMessageLayout();
    });
    window.addEventListener("scroll", () => {
      if (needsHeaderViewportMetrics()) updateHeaderMenuViewportMetrics();
    }, { passive: true });
    document.addEventListener("click", (event) => {
      if (quickMore && quickMore.open && !quickMore.contains(event.target)) {
        quickMore.open = false;
      }
      if (composerPlusMenu && composerPlusMenu.open && !composerPlusMenu.contains(event.target) && !event.target.closest(".target-chip")) {
        closePlusMenu();
      }
      const inRightMenu = rightMenuBtn?.contains(event.target) || rightMenuPanel?.contains(event.target);
      const inNativeBridgeMenu = nativeHeaderMenuBridge?.contains(event.target);
      const agentActionNativeMenu = document.getElementById("agentActionNativeMenuSelect");
      const inAgentActionMenu = agentActionNativeMenu?.contains(event.target);
      if (!inRightMenu && !inNativeBridgeMenu && !inAgentActionMenu) {
        closeHeaderMenus();
      }
    });
    async function runForwardAction(target, { sourceNode = null, keepComposerOpen = false, keepHeaderOpen = false } = {}) {
      const action = String(target || "");
      if (!action) return;
      if (keepComposerOpen) flashComposerAction(action);
      if (action === "save" || action === "interrupt" || action === "restart" || action === "resume" || action === "ctrlc" || action === "enter") {
        if (!keepComposerOpen) closeQuickMore();
        await submitMessage({ overrideMessage: action });
        if (keepComposerOpen && composerPlusMenu) {
          requestAnimationFrame(() => { composerPlusMenu.open = true; });
        }
        return;
      }
      if (action === "reloadChat") {
        if (reloadInFlight) return;
        reloadInFlight = true;
        armLaunchShellGate(15000);
        const btn = sourceNode;
        if (btn) {
          btn.disabled = true;
          btn.classList.add("restarting");
          btn.textContent = "Restarting…";
        }
        const previousInstance = currentServerInstance;
        let edgeReady = false;
        await Promise.allSettled([purgeChatAssetCaches(), refreshChatServiceWorkers()]);
        try {
          const res = await fetch("/new-chat", { method: "POST", cache: "no-store" });
          edgeReady = res.ok && res.headers.get("X-Multiagent-Chat-Ready") === "1";
        } catch (_) {}
        const ready = edgeReady || await waitForChatReady(12000, previousInstance);
        await Promise.allSettled([purgeChatAssetCaches(), refreshChatServiceWorkers()]);
        if (!ready) {
          navigateToFreshChat();
          return;
        }
        navigateToFreshChat();
        return;
      }
      if (action === "openTerminal") {
        closeQuickMore();
        fetch("/open-terminal", { method: "POST" }).catch(() => {});
        return;
      }
      if (action === "openFinder") {
        closeQuickMore();
        try {
          const res = await fetch("/open-finder", { method: "POST" });
          if (res.ok) {
            setStatus("opened Finder");
            setTimeout(() => setStatus(""), 1800);
          } else {
            const data = await res.json().catch(() => ({}));
            setStatus(data.error || "Finder open failed", true);
            setTimeout(() => setStatus(""), 2600);
          }
        } catch (err) {
          setStatus(`Finder open error: ${err.message}`, true);
          setTimeout(() => setStatus(""), 2600);
        }
        return;
      }
      if (action === "openCameraMode") {
        await openCameraMode();
        return;
      }
      if (action === "addAgent") {
        if (!sessionActive) {
          setStatus("archived session is read-only", true);
          setTimeout(() => setStatus(""), 2000);
          return;
        }
        if (!keepHeaderOpen) closeQuickMore();
        showAddAgentModal();
        return;
      }
      if (action === "removeAgent") {
        if (!sessionActive) {
          setStatus("archived session is read-only", true);
          setTimeout(() => setStatus(""), 2000);
          return;
        }
        if (!keepHeaderOpen) closeQuickMore();
        showRemoveAgentModal();
        return;
      }
      document.getElementById(action)?.click();
      if (keepComposerOpen && composerPlusMenu) {
        requestAnimationFrame(() => { composerPlusMenu.open = true; });
      }
      if (keepHeaderOpen && rightMenuPanel && rightMenuBtn) {
        requestAnimationFrame(() => {
          rightMenuPanel.hidden = false;
          rightMenuPanel.classList.add("open");
          rightMenuBtn.classList.add("open");
        });
      }
    }
    document.querySelectorAll("[data-forward-action]").forEach((node) => {
      node.addEventListener("mousedown", (e) => e.preventDefault());
      node.addEventListener("click", async () => {
        const target = node.dataset.forwardAction || "";
        const keepComposerOpen = !!(composerPlusMenu && composerPlusMenu.contains(node));
        const keepHeaderOpen = !!(rightMenuPanel && rightMenuPanel.contains(node));
        await runForwardAction(target, { sourceNode: node, keepComposerOpen, keepHeaderOpen });
      });
    });
    document.querySelectorAll(".quick-action:not(.quick-more-toggle):not(.plus-submenu-toggle):not([data-forward-action]):not(#cameraBtn)").forEach((node) => {
      node.addEventListener("click", async () => {
        closeQuickMore();
        await submitMessage({ overrideMessage: node.dataset.shortcut || "" });
      });
    });
    let composing = false;
    const messageInput = document.getElementById("message");
    const sendBtn = document.querySelector(".send-btn");
    const micBtn = document.getElementById("micBtn");
    document.getElementById("pendingLaunchBtn")?.addEventListener("click", async () => {
      if (!sessionLaunchPending || sessionActive) return;
      const launchTargets = selectedTargets.filter((target) => availableTargets.includes(target));
      if (launchTargets.length !== 1) {
        setStatus("select exactly one initial agent", true);
        syncPendingLaunchControls();
        return;
      }
      const selectedAgent = launchTargets[0];
      const pendingLaunchBtn = document.getElementById("pendingLaunchBtn");
      if (pendingLaunchBtn) {
        pendingLaunchBtn.disabled = true;
        pendingLaunchBtn.textContent = "Starting…";
      }
      _sessionLaunching = true;
      try {
        const res = await fetch("/launch-session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agent: selectedAgent }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "failed to start session");
        }
      } catch (error) {
        _sessionLaunching = false;
        setStatus(error?.message || "failed to start session", true);
        syncPendingLaunchControls();
      }
    });
