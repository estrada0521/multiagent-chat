    let _cmdActiveIdx = -1;
    let _cmdTimeout = null;
    let _lastCmdItemsData = [];
    const _cmdItems = () => cmdDrop.querySelectorAll(".cmd-item");
    const closeCmdDrop = () => {
      if (cmdDrop.classList.contains("visible")) {
        cmdDrop.classList.remove("visible");
        cmdDrop.classList.add("closing");
        _cmdTimeout = setTimeout(() => {
          if (cmdDrop.classList.contains("closing")) {
            cmdDrop.style.display = "none";
            cmdDrop.classList.remove("closing");
          }
        }, 160);
      } else if (!cmdDrop.classList.contains("closing")) {
        cmdDrop.style.display = "none";
      }
      _cmdActiveIdx = -1;
    };
    const selectCmd = (idx) => {
      const item = _lastCmdItemsData[idx];
      if (!item) return;
      if (item.has_arg) {
        messageInput.value = item.slash + " ";
        autoResizeTextarea();
        closeCmdDrop();
        focusMessageInputWithoutScroll(messageInput.value.length);
        return;
      }
      messageInput.value = "";
      autoResizeTextarea();
      closeCmdDrop();
      void postShortcutCommand({ command_id: item.id, arg: "" });
      requestAnimationFrame(() => focusMessageInputWithoutScroll(0));
    };
    let _lastCmdQuery = "";
    const updateCmdAutocomplete = () => {
      const pos = messageInput.selectionEnd;
      const val = messageInput.value;
      const before = val.slice(0, pos);
      if (!before.match(/^\/[\w-]*$/)) {
        closeCmdDrop();
        return;
      }
      const query = before.toLowerCase();
      _lastCmdQuery = query;
      void (async () => {
        let list;
        try {
          list = await loadShortcutCommandsOnce();
        } catch (err) {
          closeCmdDrop();
          setStatus(err?.message || "shortcut commands unavailable", true);
          return;
        }
        if (_lastCmdQuery !== query) return;
        const matches = list.filter((c) => {
          const slash = String(c.slash || "").toLowerCase();
          return !query || query === "/" || slash.startsWith(query);
        });
        if (!matches.length) {
          closeCmdDrop();
          return;
        }
        _lastCmdItemsData = matches.map((c) => ({
          id: c.id,
          slash: c.slash,
          desc: c.desc,
          has_arg: !!c.has_arg,
          type: "command",
          label: c.slash,
        }));
        cmdDrop.innerHTML =
          `<div class="cmd-dropdown-list">` +
          _lastCmdItemsData.map((c, i) =>
            `<div class="cmd-item" data-idx="${i}">` +
            `<span class="cmd-item-name">${escapeHtml(c.label)}</span>` +
            `<span class="cmd-item-desc">${escapeHtml(c.desc)}</span>` +
            `</div>`
          ).join("") +
          `</div>`;
        _cmdActiveIdx = -1;
        positionComposerDropdown(cmdDrop);
        if (!cmdDrop.classList.contains("visible")) {
          if (_cmdTimeout) { clearTimeout(_cmdTimeout); _cmdTimeout = null; }
          cmdDrop.classList.remove("closing");
          cmdDrop.style.display = "block";
          cmdDrop.classList.add("visible");
        }
      })();
    };
    messageInput.addEventListener("input", updateCmdAutocomplete);
    cmdDrop.addEventListener("click", (e) => e.stopPropagation());
    cmdDrop.addEventListener("pointerdown", armAutocompleteMenuBlurGuard);
    cmdDrop.addEventListener("touchstart", armAutocompleteMenuBlurGuard, { passive: true });
    cmdDrop.addEventListener("mousedown", (e) => {
      const item = e.target.closest(".cmd-item");
      if (item) { e.preventDefault(); selectCmd(parseInt(item.dataset.idx, 10)); }
    });
    messageInput.addEventListener("keydown", (e) => {
      if (cmdDrop.style.display === "none" || !cmdDrop.classList.contains("visible")) return;
      const items = _cmdItems();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        items[_cmdActiveIdx]?.classList.remove("active");
        _cmdActiveIdx = Math.min(_cmdActiveIdx + 1, items.length - 1);
        items[_cmdActiveIdx]?.classList.add("active");
        items[_cmdActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        items[_cmdActiveIdx]?.classList.remove("active");
        _cmdActiveIdx = Math.max(_cmdActiveIdx - 1, 0);
        items[_cmdActiveIdx]?.classList.add("active");
        items[_cmdActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if ((e.key === "Enter" || e.key === "Tab") && _cmdActiveIdx >= 0) {
        e.preventDefault();
        e.stopImmediatePropagation();
        selectCmd(parseInt(items[_cmdActiveIdx].dataset.idx, 10));
      } else if (e.key === "Escape") {
        closeCmdDrop();
      }
    }, true);

    messageInput.addEventListener("blur", (event) => {
      document.body.classList.remove("composing");
      const nextTarget = event.relatedTarget;
      const keepPlusMenuOpen = keepComposerPlusMenuOnBlur
        || !!(nextTarget && composerPlusMenu && composerPlusMenu.contains(nextTarget));
      const keepAutocompleteMenusOpen = _keepAutocompleteMenuOnBlur
        || !!(nextTarget && (fileDrop.contains(nextTarget) || cmdDrop.contains(nextTarget)));
      if (!keepPlusMenuOpen) closePlusMenu();
      if (!keepAutocompleteMenusOpen) {
        setTimeout(closeDrop, 150);
        setTimeout(closeCmdDrop, 150);
      }
    });

    const doCopyFallback = (text) => {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      try { document.execCommand("copy"); } catch (_) {}
      document.body.removeChild(ta);
      return Promise.resolve();
    };
    const doCopyText = (text) => {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).catch(() => doCopyFallback(text));
      }
      return doCopyFallback(text);
    };

    document.getElementById("messages").addEventListener("click", (e) => {
      const metaBtn = e.target.closest(".message-meta-below button, .user-message-meta button, .message-meta-below .meta-agent, .user-message-meta .meta-agent");
      if (metaBtn) {
        const row = metaBtn.closest("article.message-row");
        if (row) {
          row.classList.add("meta-keep-visible");
          if (row._metaKeepTimer) clearTimeout(row._metaKeepTimer);
          row._metaKeepTimer = setTimeout(() => {
            row.classList.remove("meta-keep-visible");
            row._metaKeepTimer = null;
          }, 1800);
        }
      }
      const anyLink = e.target.closest("a[href]");
      if (anyLink) {
        const href = anyLink.getAttribute("href");
        const path = filePathFromLinkAnchor(anyLink);
        if (path) {
          e.preventDefault();
          e.stopPropagation();
          void openFileSurface(path, extFromPath(path), anyLink, e, lineFromLinkAnchor(anyLink));
          return;
        }
        if (href && !href.startsWith("#") && !href.startsWith("javascript:")) {
          e.preventDefault();
          e.stopPropagation();
          window.open(href, "_blank", "noopener,noreferrer");
          return;
        }
      }
      const fileCard = e.target.closest(".file-card");
      if (fileCard) {
        e.stopPropagation();
        const path = fileCard.dataset.filepath;
        const ext = fileCard.dataset.ext || "";
        void openFileSurface(path, ext, fileCard, e, 0);
        return;
      }
      const thinkingRowEarly = e.target.closest(".message-thinking-row");
      if (thinkingRowEarly) {
        const providerEventsMsgId = thinkingRowEarly.dataset.providerEvents;
        if (providerEventsMsgId) {
          e.preventDefault();
          void showProviderEventsModal(providerEventsMsgId);
          return;
        }
      }
      const collapseToggle = e.target.closest(".message-collapse-toggle");
      if (collapseToggle) {
        const row = collapseToggle.closest("article.message-row");
        const msgId = row?.dataset.msgid || "";
        if (!row || !msgId || !isCollapsibleMessageRow(row)) return;
        if (expandedMessageBodies.has(msgId)) {
          expandedMessageBodies.delete(msgId);
        } else {
          expandedMessageBodies.add(msgId);
        }
        syncMessageCollapse(row);
        return;
      }
      const providerEventsBtn = e.target.closest("[data-provider-events]");
      if (providerEventsBtn) {
        e.preventDefault();
        e.stopPropagation();
        void showProviderEventsModal(providerEventsBtn.dataset.providerEvents || "");
        return;
      }
      const btn = e.target.closest(".copy-btn");
      if (!btn || btn.classList.contains("copy-animating")) return;
      const raw = btn.closest(".message")?.dataset.raw ?? "";
      doCopyText(raw).then(() => {
        markCopied(btn);
      }).catch(() => {});
    });

