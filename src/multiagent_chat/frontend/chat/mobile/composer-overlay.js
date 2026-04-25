    const composerFabBtn = document.getElementById("composerFabBtn");
    const composerOverlay = document.getElementById("composerOverlay");
    const composerForm = document.getElementById("composer");
    const isComposerOverlayOpen = () => !!composerOverlay && !composerOverlay.hidden && composerOverlay.classList.contains("visible");
    const isCameraModeOpen = () => !!cameraMode && !cameraMode.hidden && cameraMode.classList.contains("visible");
    let composerBlurCloseTimer = null;
    const clearComposerBlurCloseTimer = () => {
      if (composerBlurCloseTimer) {
        clearTimeout(composerBlurCloseTimer);
        composerBlurCloseTimer = null;
      }
    };
    const setComposerCaretToEnd = () => {
      if (!messageInput) return;
      const end = messageInput.value.length;
      if (typeof messageInput.setSelectionRange === "function") {
        try {
          messageInput.setSelectionRange(end, end);
        } catch (_) { }
      }
    };
    const focusComposerTextarea = ({ sync = false } = {}) => {
      if (!messageInput) return;
      const applyFocus = () => {
        try {
          messageInput.focus({ preventScroll: true });
        } catch (_) {
          messageInput.focus();
        }
        setComposerCaretToEnd();
      };
      if (sync) {
        if (composerForm) {
          composerForm.classList.add("composer-focus-hack");
          applyFocus();
          let restored = false;
          const restore = () => {
            if (restored) return;
            restored = true;
            composerForm.classList.remove("composer-focus-hack");
            setComposerCaretToEnd();
          };
          requestAnimationFrame(() => requestAnimationFrame(restore));
          setTimeout(restore, 120);
          return;
        }
        applyFocus();
        setTimeout(applyFocus, 0);
        requestAnimationFrame(applyFocus);
        return;
      }
      requestAnimationFrame(() => {
        applyFocus();
        setTimeout(applyFocus, 0);
      });
    };
    const openComposerOverlay = ({ immediateFocus = false } = {}) => {
      if (!composerOverlay || isCameraModeOpen()) return;
      const canFocus = canComposeInSession();
      if (isComposerOverlayOpen()) {
        if (canFocus) focusComposerTextarea({ sync: immediateFocus });
        return;
      }
      requestHubParentLayout();
      bumpHubIframeLayoutLock();
      composerOverlay.hidden = false;
      composerOverlay.classList.remove("closing");
      document.body.classList.add("composer-overlay-open");
      updateScrollBtn();
      if (immediateFocus && canFocus) {
        focusComposerTextarea({ sync: true });
      }
      requestAnimationFrame(() => {
        composerOverlay.classList.add("visible");
        if (!immediateFocus && canFocus) {
          focusComposerTextarea();
        }
      });
    };
    const closeComposerOverlay = ({ restoreFocus = false } = {}) => {
      if (!composerOverlay || composerOverlay.hidden) return;
      clearComposerBlurCloseTimer();
      composerOverlay.classList.remove("visible");
      composerOverlay.classList.add("closing");
      document.body.classList.remove("composer-overlay-open");
      setTimeout(() => {
        if (!composerOverlay.classList.contains("visible")) {
          composerOverlay.hidden = true;
          composerOverlay.classList.remove("closing");
        }
      }, 90);
      updateScrollBtn();
      if (restoreFocus && composerFabBtn && typeof composerFabBtn.focus === "function") {
        try {
          composerFabBtn.focus({ preventScroll: true });
        } catch (_) {
          composerFabBtn.focus();
        }
      }
    };
    const maybeAutoOpenComposer = () => {
      if (!composerAutoOpenRequested || composerAutoOpenConsumed) return;
      if (!sessionLaunchPending && !draftLaunchHintActive) return;
      if (!canInteractWithSession()) return;
      composerAutoOpenConsumed = true;
      try {
        const params = new URLSearchParams(window.location.search);
        if (params.has("compose")) {
          params.delete("compose");
          const nextQuery = params.toString();
          window.history.replaceState(window.history.state, "", `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`);
        }
      } catch (_) { }
      requestAnimationFrame(() => openComposerOverlay({ immediateFocus: canComposeInSession() }));
    };
    scrollToBottomBtn.addEventListener("click", () => {
      _pollScrollLockTop = null;
      _pollScrollAnchor = null;
      _stickyToBottom = true;
      scrollConversationToBottom("smooth");
    });
    composerFabBtn?.addEventListener("click", () => {
      openComposerOverlay({ immediateFocus: canComposeInSession() });
    });
    composerOverlay?.addEventListener("click", (event) => {
      if (event.target === composerOverlay) {
        closeComposerOverlay({ restoreFocus: true });
      }
    });
