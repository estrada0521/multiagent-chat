    const renderTargetPicker = (targets) => {
      const root = document.getElementById("targetPicker");
      const selectedSet = new Set(selectedTargets);
      const targetsSig = JSON.stringify(targets);
      const selectionSig = JSON.stringify([...selectedSet].sort());
      const renderSig = `${targetsSig}|${selectionSig}`;
      if (root.dataset.renderSig === renderSig) return;

      if (root.dataset.targetsSig !== targetsSig) {
        root.dataset.targetsSig = targetsSig;
        root.innerHTML = targets.map((target) => {
          return `<button type="button" class="target-chip" data-target="${target}" data-base-agent="${agentBaseName(target)}" title="${escapeHtml(target)}"><span class="agent-icon-slot agent-icon-slot--chip"><img class="target-icon" src="${escapeHtml(agentIconSrc(target))}" alt="${escapeHtml(target)}">${agentIconInstanceSubHtml(target)}</span></button>`;
        }).join("");
        root.querySelectorAll(".target-chip").forEach((node) => {
          node.addEventListener("mousedown", (e) => e.preventDefault());
          node.addEventListener("click", () => {
            const target = node.dataset.target;
            if (sessionLaunchPending) {
              selectedTargets = selectedTargets.includes(target) ? [] : [target];
            } else if (selectedTargets.includes(target)) {
              selectedTargets = selectedTargets.filter((item) => item !== target);
            } else {
              selectedTargets = [...selectedTargets, target];
            }
            saveTargetSelection(currentSessionName, selectedTargets);
            renderTargetPicker(availableTargets);
            syncPendingLaunchControls();
          });
        });
      }
      root.querySelectorAll(".target-chip").forEach((node) => {
        node.classList.toggle("active", selectedSet.has(node.dataset.target));
      });
      root.dataset.renderSig = renderSig;
    };
    const cameraModeAllowedTargets = () => availableTargets.filter((target) => target && target !== "others");
    const preferredCameraModeTarget = () =>
      (selectedTargets.find((target) => target && target !== "others") || "") ||
      (cameraModeAllowedTargets()[0] || "");
    const syncCameraModeTarget = () => {
      const allowed = cameraModeAllowedTargets();
      if (!allowed.length) {
        cameraModeTarget = "";
        return "";
      }
      if (cameraModeTarget && allowed.includes(cameraModeTarget)) {
        return cameraModeTarget;
      }
      cameraModeTarget = preferredCameraModeTarget();
      return cameraModeTarget;
    };
    const setCameraModeHint = (text = "", isError = false, isListening = false) => {
      const hintText = document.getElementById("cameraModeHintText");
      if (!cameraModeHint || !hintText) return;
      const value = String(text || "").trim();
      cameraModeHint.hidden = !value;
      hintText.textContent = value;
      cameraModeHint.classList.toggle("error", !!(value && isError));
      cameraModeHint.classList.toggle("is-listening", !!(value && isListening));
    };
    const syncCameraModeBackdrop = () => {
      const enabled = !!cameraModeBackdropFrosted;
      if (!enabled && cameraModeTargetsExpanded) {
        setCameraModeTargetsExpanded(false);
      }
      cameraModeShell?.classList.toggle("backdrop-frosted", enabled);
      if (!cameraModeBackdropBtn) return;
      cameraModeBackdropBtn.classList.toggle("active", enabled);
      cameraModeBackdropBtn.setAttribute("aria-pressed", enabled ? "true" : "false");
      const title = enabled ? "Disable frosted background" : "Enable frosted background";
      cameraModeBackdropBtn.setAttribute("title", title);
      cameraModeBackdropBtn.setAttribute("aria-label", title);
      syncCameraModeMessageLayout();
    };
    const setCameraModeFallbackState = (active, message = "") => {
      if (cameraModeVideo) cameraModeVideo.classList.toggle("is-hidden", !!active);
      if (cameraModeEmpty) cameraModeEmpty.hidden = !active;
      if (cameraModeEmptyCopy && message) cameraModeEmptyCopy.textContent = message;
    };
    const fallbackToCameraModeChat = (message = "", isError = false) => {
      closeCameraMode();
      if (!message) return false;
      setStatus(message, isError);
      setTimeout(() => setStatus(""), 2600);
      return false;
    };
    const isCameraBlockedByPolicy = () => {
      try {
        const policy = document.permissionsPolicy || document.featurePolicy || null;
        return !!(policy && typeof policy.allowsFeature === "function" && !policy.allowsFeature("camera"));
      } catch (_) {
        return false;
      }
    };
    const syncCameraModeBusyState = () => {
      const interactionLocked = !!cameraModeBusy || !!cameraModeMicListening;
      cameraMode?.classList.toggle("busy", !!cameraModeBusy);
      if (cameraModeShutterBtn) cameraModeShutterBtn.disabled = interactionLocked;
      if (cameraModeMicBtn) cameraModeMicBtn.disabled = !!cameraModeBusy;
      if (cameraModeCloseBtn) cameraModeCloseBtn.disabled = !!cameraModeBusy;
      if (cameraModeTargetToggleBtn) cameraModeTargetToggleBtn.disabled = interactionLocked;
      cameraModeTargets?.querySelectorAll(".camera-mode-target").forEach((node) => {
        node.disabled = interactionLocked;
      });
    };
    const setCameraModeTargetsExpanded = (expanded) => {
      cameraModeTargetsExpanded = !!expanded;
      cameraModeTargetRail?.classList.toggle("is-open", cameraModeTargetsExpanded);
      if (cameraModeTargetToggleBtn) {
        cameraModeTargetToggleBtn.classList.toggle("is-open", cameraModeTargetsExpanded);
        cameraModeTargetToggleBtn.setAttribute("aria-expanded", cameraModeTargetsExpanded ? "true" : "false");
      }
    };
    const syncCameraModeMessageLayout = () => {
      const mounted = !!timeline && timeline.parentElement === cameraModeReplies;
      const compact = mounted && !cameraModeBackdropFrosted;
      cameraModeReplies?.classList.toggle("is-compact", compact);
      const activeTarget = mounted ? syncCameraModeTarget() : "";
      cameraModeTargetRail?.classList.toggle("is-visible", !!(mounted && compact && activeTarget));
      if (!timeline) return;
      if (!mounted) {
        if (cameraModePrevMainAfterHeight !== null) {
          if (cameraModePrevMainAfterHeight) timeline.style.setProperty("--main-after-height", cameraModePrevMainAfterHeight);
          else timeline.style.removeProperty("--main-after-height");
          cameraModePrevMainAfterHeight = null;
        }
        return;
      }
      if (cameraModePrevMainAfterHeight === null) {
        cameraModePrevMainAfterHeight = timeline.style.getPropertyValue("--main-after-height");
      }
      if (compact) {
        const shellPx = parseInt(document.documentElement.style.getPropertyValue("--app-shell-height"), 10) || 0;
        const baseHeight = shellPx > 0 ? shellPx : (window.innerHeight || 0);
        const compactHeight = Math.max(0, Math.round(baseHeight * 0.15));
        timeline.style.setProperty("--main-after-height", compactHeight > 0 ? `${compactHeight}px` : "15vh");
        return;
      }
      if (cameraModePrevMainAfterHeight) timeline.style.setProperty("--main-after-height", cameraModePrevMainAfterHeight);
      else timeline.style.removeProperty("--main-after-height");
    };
    const renderCameraModeTargets = () => {
      if (!cameraModeTargets) return;
      const targets = cameraModeAllowedTargets();
      const active = syncCameraModeTarget();
      const displayTargets = cameraModeTargetsExpanded
        ? targets.filter((target) => target !== active)
        : [];
      if (cameraModeTargetToggleBtn) {
        if (!active) {
          cameraModeTargetToggleBtn.hidden = true;
          cameraModeTargetToggleBtn.innerHTML = "";
        } else {
          const base = agentBaseName(active);
          cameraModeTargetToggleBtn.hidden = false;
          cameraModeTargetToggleBtn.dataset.target = active;
          cameraModeTargetToggleBtn.dataset.baseAgent = base;
          cameraModeTargetToggleBtn.title = active;
          cameraModeTargetToggleBtn.innerHTML = `<span class="agent-icon-slot agent-icon-slot--camera"><img class="camera-mode-target-icon" src="${escapeHtml(agentIconSrc(active))}" alt="${escapeHtml(active)}">${agentIconInstanceSubHtml(active)}</span>`;
        }
      }
      cameraModeTargets.innerHTML = displayTargets.map((target) => {
        const base = agentBaseName(target);
        return `<button type="button" class="camera-mode-target${target === active ? " active" : ""}" data-target="${escapeHtml(target)}" data-base-agent="${base}" aria-pressed="${target === active ? "true" : "false"}" aria-label="${escapeHtml(target)}" title="${escapeHtml(target)}"><span class="agent-icon-slot agent-icon-slot--camera"><img class="camera-mode-target-icon" src="${escapeHtml(agentIconSrc(target))}" alt="${escapeHtml(target)}">${agentIconInstanceSubHtml(target)}</span><span class="camera-mode-target-label">${escapeHtml(target)}</span></button>`;
      }).join("");
      cameraModeTargets.querySelectorAll(".camera-mode-target").forEach((node) => {
        node.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (cameraModeBusy) return;
          cameraModeTarget = node.dataset.target || "";
          setCameraModeTargetsExpanded(false);
          renderCameraModeTargets();
          renderCameraModeThinking();
        });
      });
      syncCameraModeMessageLayout();
      syncCameraModeBusyState();
    };
    const mountTimelineIntoCameraMode = () => {
      if (!cameraModeReplies || !timeline) return;
      if (timeline.parentElement === cameraModeReplies) return;
      const parent = timeline.parentNode;
      if (!parent) return;
      cameraModeTimelinePlaceholder = document.createComment("camera-mode-timeline-placeholder");
      parent.insertBefore(cameraModeTimelinePlaceholder, timeline);
      cameraModeReplies.insertBefore(timeline, cameraModeRepliesInner || null);
      syncCameraModeMessageLayout();
      requestAnimationFrame(() => {
        if (!timeline) return;
        timeline.scrollTop = timeline.scrollHeight;
      });
    };
    const restoreTimelineFromCameraMode = () => {
      if (!timeline || !cameraModeTimelinePlaceholder?.parentNode) return;
      cameraModeTimelinePlaceholder.parentNode.insertBefore(timeline, cameraModeTimelinePlaceholder);
      cameraModeTimelinePlaceholder.remove();
      cameraModeTimelinePlaceholder = null;
      syncCameraModeMessageLayout();
      requestAnimationFrame(() => {
        if (!timeline) return;
        timeline.scrollTop = timeline.scrollHeight;
      });
    };
    const renderCameraModeReplies = () => {
      if (!cameraModeReplies || !cameraModeRepliesInner) return;
      const mounted = timeline?.parentElement === cameraModeReplies;
      cameraModeReplies.classList.toggle("has-live-messages", mounted);
      cameraModeRepliesInner.hidden = mounted;
      cameraModeReplies.hidden = !mounted;
    };
    const syncCameraModeReplies = () => {
      if (!cameraMode || cameraMode.hidden) return;
      renderCameraModeReplies();
    };
    const setQuickActionsDisabled = (disabled) => {
      document.querySelectorAll(".quick-action").forEach((node) => {
        node.disabled = disabled;
      });
    };
    const STICKY_THRESHOLD = 450;
    const PUBLIC_OLDER_AUTOLOAD_THRESHOLD = 120;
    let _stickyToBottom = false;
    let _programmaticScroll = false;
    let _pollScrollRestoreRaf = 0;
    const maybeRestorePollScrollLock = () => {
      if (_programmaticScroll) return;
      const hasAnchor = _pollScrollAnchor && _pollScrollAnchor.msgId;
      const hasLock = _pollScrollLockTop != null;
      if (!hasAnchor && !hasLock) return;

      if (hasAnchor) {
        const row = timeline.querySelector(`[data-msgid="${CSS.escape(String(_pollScrollAnchor.msgId))}"]`);
        if (row) {
          const tRect = timeline.getBoundingClientRect();
          const drift = (row.getBoundingClientRect().top - tRect.top) - _pollScrollAnchor.vpTop;
          if (Math.abs(drift) > 0.5) {
            _programmaticScroll = true;
            timeline.scrollTop += drift;
            const maxTop = Math.max(0, timeline.scrollHeight - timeline.clientHeight);
            timeline.scrollTop = Math.min(Math.max(0, timeline.scrollTop), maxTop);
            _pollScrollLockTop = timeline.scrollTop;
            queueMicrotask(() => { _programmaticScroll = false; });
            return;
          }
        }
      }
      if (!hasLock) return;
      const maxTop = Math.max(0, timeline.scrollHeight - timeline.clientHeight);
      const target = Math.min(_pollScrollLockTop, maxTop);
      if (Math.abs(timeline.scrollTop - target) > 0.5) {
        _programmaticScroll = true;
        timeline.scrollTop = target;
        queueMicrotask(() => { _programmaticScroll = false; });
      }
    };
    const schedulePollScrollRestore = () => {
      if (_pollScrollLockTop == null && !(_pollScrollAnchor && _pollScrollAnchor.msgId)) return;
      if (_pollScrollRestoreRaf) return;
      _pollScrollRestoreRaf = requestAnimationFrame(() => {
        _pollScrollRestoreRaf = 0;
        maybeRestorePollScrollLock();
      });
    };
    if (typeof MutationObserver === "function") {
      try {
        new MutationObserver(() => schedulePollScrollRestore()).observe(timeline, {
          childList: true,
          subtree: true,
        });
