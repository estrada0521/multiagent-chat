    const composerFabBtn = document.getElementById("composerFabBtn");
    const composerOverlay = document.getElementById("composerOverlay");
    const composerForm = document.getElementById("composer");
    const isComposerOverlayOpen = () => !!composerOverlay && !composerOverlay.hidden && composerOverlay.classList.contains("visible");
    if (document.documentElement.dataset.mobile === "1" && document.documentElement.dataset.hubIframeChat === "1") {
      const mobileComposerInput = document.getElementById("message");
      composerOverlay?.addEventListener("touchstart", (event) => {
        if (event.target !== composerOverlay) return;
        event.preventDefault();
        if (composing && document.activeElement === mobileComposerInput) return;
        closeComposerOverlay();
      }, { passive: false });
      composerOverlay?.addEventListener("touchmove", (event) => {
        const target = event.target;
        if (target instanceof Element && target.closest("textarea, .attach-preview-row, .target-picker")) return;
        event.preventDefault();
      }, { passive: false });
      mobileComposerInput?.addEventListener("touchstart", (event) => {
        if (document.activeElement !== mobileComposerInput) return;
        const parentChromeGap = Number.parseFloat(
          getComputedStyle(document.documentElement).getPropertyValue("--hub-parent-chrome-gap"),
        );
        if (!Number.isFinite(parentChromeGap) || parentChromeGap >= HUB_KEYBOARD_GAP_THRESHOLD) return;
        event.preventDefault();
        mobileComposerInput.blur();
        mobileComposerInput.focus({ preventScroll: true });
      }, { passive: false });
    }
    const setComposerCaretToEnd = () => {
      if (!messageInput) return;
      const end = messageInput.value.length;
      if (typeof messageInput.setSelectionRange === "function") {
        try {
          messageInput.setSelectionRange(end, end);
        } catch (_) {}
      }
      messageInput.scrollTop = messageInput.scrollHeight;
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
        if (document.documentElement.dataset.mobile === "1" && composerForm) {
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
      if (!composerOverlay) return;
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
        if (typeof autoResizeTextarea === "function") autoResizeTextarea();
        setComposerCaretToEnd();
        composerOverlay.classList.add("visible");
        document.dispatchEvent(new CustomEvent("composer-overlay-open"));
        if (!immediateFocus && canFocus) {
          focusComposerTextarea();
        }
      });
    };
    const closeComposerOverlay = ({ restoreFocus = false } = {}) => {
      if (!composerOverlay || composerOverlay.hidden) return;
      const isMobileComposer = document.documentElement.dataset.mobile === "1";
      if (isMobileComposer && document.activeElement === messageInput) {
        messageInput.blur();
      }
      document.dispatchEvent(new CustomEvent("composer-overlay-close-start"));
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
      if (!isMobileComposer && restoreFocus && composerFabBtn && typeof composerFabBtn.focus === "function") {
        try {
          composerFabBtn.focus({ preventScroll: true });
        } catch (_) {
          composerFabBtn.focus();
        }
      }
    };
    const messageStepTopGap = () => {
      const value = parseFloat(getComputedStyle(timeline).getPropertyValue("--message-step-top-gap"));
      return Number.isFinite(value) ? Math.max(0, value) : 0;
    };
    const positionConversationRowAtStepTop = (row, behavior) => {
      const timelineTop = timeline.getBoundingClientRect().top;
      const top = timeline.scrollTop + row.getBoundingClientRect().top - timelineTop - messageStepTopGap();
      timeline.scrollTo({ top, behavior });
    };
    const jumpConversationToBottom = () => {
      if (document.documentElement.dataset.autoWindowHeight === "1" && typeof fitStepToLatest === "function") {
        fitStepToLatest();
        return;
      }
      _pollScrollLockTop = null;
      _pollScrollAnchor = null;
      _stickyToBottom = true;
      scrollConversationToBottom("smooth");
    };
    const jumpConversationToTop = () => {
      // Top of what's loaded, not the first entry ever -- the transcript is a
      // tail window and older batches auto-load on the way up.
      _pollScrollLockTop = null;
      _pollScrollAnchor = null;
      _stickyToBottom = false;
      _programmaticScroll = true;
      timeline.scrollTo({ top: 0, behavior: "smooth" });
      requestAnimationFrame(() => { _programmaticScroll = false; });
    };
    scrollToBottomBtn.addEventListener("click", jumpConversationToBottom);
    // ⌘↑ / ⌘↓ are the keyboard version of jumping the transcript to its ends.
    // It is an inner scroll container, so the native ⌘↑/⌘↓ never reach it; skip
    // only when a text field wants the caret move it would otherwise do.
    document.addEventListener("keydown", (event) => {
      if (!event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return;
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      const active = document.activeElement;
      if (active && active.matches && active.matches("input, textarea, [contenteditable='true']")) return;
      event.preventDefault();
      (event.key === "ArrowDown" ? jumpConversationToBottom : jumpConversationToTop)();
    });
    // ⌥↓ / ⌥↑ step to the top of the next / previous message.
    const stepConversationByMessage = (down) => {
      if (document.documentElement.dataset.autoWindowHeight === "1") {
        if (typeof fitStepToMessage === "function") fitStepToMessage(down);
        return;
      }
      const rows = timeline.querySelectorAll("article.message-row");
      if (!rows.length) return;
      const tTop = timeline.getBoundingClientRect().top;
      const stepTop = tTop + messageStepTopGap();
      let target = null;
      if (down) {
        for (const row of rows) {
          if (row.getBoundingClientRect().top - stepTop > 2) { target = row; break; }
        }
      } else {
        for (const row of rows) {
          if (row.getBoundingClientRect().top - stepTop < -2) target = row; else break;
        }
      }
      _pollScrollLockTop = null;
      _pollScrollAnchor = null;
      if (!down) _stickyToBottom = false;
      _programmaticScroll = true;
      if (target) positionConversationRowAtStepTop(target, "smooth");
      else timeline.scrollTo({ top: down ? timeline.scrollHeight : 0, behavior: "smooth" });
      requestAnimationFrame(() => { _programmaticScroll = false; });
    };
    document.addEventListener("keydown", (event) => {
      if (!event.altKey || event.metaKey || event.ctrlKey || event.shiftKey) return;
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      const active = document.activeElement;
      if (active && active.matches && active.matches("input, textarea, [contenteditable='true']")) return;
      event.preventDefault();
      stepConversationByMessage(event.key === "ArrowDown");
    });
    composerFabBtn?.addEventListener("click", () => {
      openComposerOverlay({ immediateFocus: canComposeInSession() });
    });
    composerOverlay?.addEventListener("click", (event) => {
      if (event.target === composerOverlay) {
        closeComposerOverlay({ restoreFocus: true });
      }
    });
    // Esc closes the expanded composer. Capture phase so it runs before the
    // @/-menu Esc handlers on the textarea: if one of those menus is open, bail
    // and let it consume the Esc (a second Esc then closes the overlay).
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || event.isComposing || event.keyCode === 229) return;
      if (!isComposerOverlayOpen()) return;
      const fileDrop = document.getElementById("fileDropdown");
      const cmdDrop = document.getElementById("cmdDropdown");
      if (fileDrop?.classList.contains("visible") || cmdDrop?.classList.contains("visible")) return;
      event.preventDefault();
      event.stopPropagation();
      closeComposerOverlay({ restoreFocus: true });
    }, true);
    if (document.documentElement.dataset.mobile !== "1") {
      const shouldIgnoreComposerMouseShortcut = (target) => !!target?.closest?.("a, button, input, textarea, select, summary, label, [contenteditable='true'], #fileDropdown, #cmdDropdown");
      document.addEventListener("mousedown", (event) => {
        if (event.button !== 1) return;
        if (shouldIgnoreComposerMouseShortcut(event.target)) return;
        event.preventDefault();
        openComposerOverlay({ immediateFocus: canComposeInSession() });
      }, { capture: true });
      document.addEventListener("auxclick", (event) => {
        if (event.button !== 1) return;
        if (shouldIgnoreComposerMouseShortcut(event.target)) return;
        event.preventDefault();
      }, { capture: true });
      // Enter anywhere in the transcript opens the composer (Esc still closes).
      document.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
        if (event.isComposing || event.keyCode === 229) return;
        if (isComposerOverlayOpen() || !canComposeInSession()) return;
        const active = document.activeElement;
        if (active && active.matches && active.matches("input, textarea, select, button, a, summary, [contenteditable='true']")) return;
        event.preventDefault();
        openComposerOverlay({ immediateFocus: true });
      });
    }
