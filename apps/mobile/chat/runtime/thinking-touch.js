    let _thinkingRowTouch = null;
    let _lastThinkingPaneMs = 0;
    document.documentElement.dataset.mobile = "1";

    /* ── Mobile: keep main::after height synced so iframe prewarm does not collapse bottom spacer ── */
    syncMainAfterHeight();
    window.addEventListener("resize", syncMainAfterHeight, { passive: true });

    /* ── Mobile viewport sync: do not move the overlay for the keyboard ── */
    if (window.visualViewport) {
      const onVVResize = () => {
        syncMainAfterHeight();
        updateScrollBtnPos();
        if (_stickyToBottom && timeline) {
          _pollScrollLockTop = null;
          _pollScrollAnchor = null;
          timeline.scrollTop = timeline.scrollHeight;
        }
      };
      visualViewport.addEventListener("resize", onVVResize);
      visualViewport.addEventListener("scroll", onVVResize);
    }

    messageInput.addEventListener("compositionstart", () => {
      composing = true;
    });
    messageInput.addEventListener("compositionend", () => {
      composing = false;
      setTimeout(updateFileAutocomplete, 10);
    });
    // @-file autocomplete
