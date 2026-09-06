    const codeCopySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    const codeCheckSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    let _cmdActiveIdx = -1;
    let _cmdTimeout = null;
    let _lastCmdItemsData = [];
    const _cmdItems = () => cmdDrop.querySelectorAll(".cmd-item");
    const closeCmdDrop = ({ immediate = false } = {}) => {
      if (immediate) {
        if (_cmdTimeout) {
          clearTimeout(_cmdTimeout);
          _cmdTimeout = null;
        }
        cmdDrop.classList.remove("visible", "closing");
        cmdDrop.style.display = "none";
        _cmdActiveIdx = -1;
        return;
      }
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
    document.addEventListener("composer-overlay-close-start", () => closeCmdDrop({ immediate: true }));
    const selectCmd = (idx) => {
      const item = _lastCmdItemsData[idx];
      if (!item) return;
      if (item.insert) {
        const start = Number(item.replaceStart);
        const end = Number(item.replaceEnd);
        if (
          !Number.isInteger(start) ||
          !Number.isInteger(end) ||
          messageInput.value.slice(start, end).toLowerCase() !== item.query
        ) {
          closeCmdDrop();
          return;
        }
        messageInput.value = messageInput.value.slice(0, start) + item.insert + messageInput.value.slice(end);
        const newPos = start + item.insert.length;
        autoResizeTextarea();
        closeCmdDrop();
        focusMessageInputWithoutScroll(newPos);
        return;
      }
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
      void postShortcutCommand({ command_id: item.id, arg: "", path: item.path });
      requestAnimationFrame(() => focusMessageInputWithoutScroll(0));
    };
    let _lastCmdQuery = "";
    const updateCmdAutocomplete = () => {
      const pos = messageInput.selectionEnd;
      const val = messageInput.value;
      const before = val.slice(0, pos);
      const match = before.match(/(^|[^A-Za-z0-9._\/-])(\/[\w-]*)$/);
      if (!match) {
        _lastCmdQuery = "";
        closeCmdDrop();
        return;
      }
      const token = match[2];
      const tokenStart = pos - token.length;
      const atInputStart = tokenStart === 0;
      const query = token.toLowerCase();
      const contextKey = `${pos}:${before}`;
      _lastCmdQuery = contextKey;
      void (async () => {
        let list;
        try {
          list = await loadShortcutCommandsOnce();
        } catch (err) {
          closeCmdDrop();
          setStatus(err?.message || "shortcut commands unavailable", true);
          return;
        }
        if (_lastCmdQuery !== contextKey) return;
        const matches = list.filter((c) => {
          const slash = String(c.slash || "").toLowerCase();
          return (atInputStart || c.insert) && (!query || query === "/" || slash.startsWith(query));
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
          path: c.path,
          insert: c.insert || "",
          replaceStart: tokenStart,
          replaceEnd: pos,
          query,
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
    const markCopied = (btn) => {
      if (!btn) return;
      const copyIcon = btn.dataset.copyIcon || btn.innerHTML;
      const checkIcon = btn.dataset.checkIcon || btn.innerHTML;
      const token = String(Date.now() + Math.random());
      btn.dataset.copyAnimToken = token;
      
      btn.innerHTML = checkIcon;
      btn.classList.add("copied");
      
      setTimeout(() => {
        if (btn.dataset.copyAnimToken !== token) return;
        btn.classList.remove("copied");
        btn.innerHTML = copyIcon;
      }, 1500);
    };
    const messagesEl = document.getElementById("messages");
    if (document.documentElement.dataset.mobile !== "1") {
      let activeHoverCopyBody = null;
      let hoverCopyBody = null;
      let hoverCopyRect = null;
      const clearHoverCopyBody = () => {
        if (activeHoverCopyBody) {
          activeHoverCopyBody.classList.remove("is-hover-copy-hotspot");
        }
        activeHoverCopyBody = null;
        hoverCopyBody = null;
        hoverCopyRect = null;
      };
      messagesEl.addEventListener("pointermove", (e) => {
        const bodyRow = e.target.closest(".message-row .message-body-row");
        if (!bodyRow) {
          clearHoverCopyBody();
          return;
        }
        if (hoverCopyBody !== bodyRow) {
          hoverCopyBody = bodyRow;
          hoverCopyRect = bodyRow.getBoundingClientRect();
        }
        const rect = hoverCopyRect;
        if (!rect?.width) {
          clearHoverCopyBody();
          return;
        }
        const inHotspot = e.clientX >= rect.left + rect.width * (2 / 3);
        if (!inHotspot) {
          if (activeHoverCopyBody === bodyRow) clearHoverCopyBody();
          return;
        }
        if (activeHoverCopyBody === bodyRow) return;
        if (activeHoverCopyBody && activeHoverCopyBody !== bodyRow) {
          activeHoverCopyBody.classList.remove("is-hover-copy-hotspot");
        }
        activeHoverCopyBody = bodyRow;
        bodyRow.classList.add("is-hover-copy-hotspot");
      });
      messagesEl.addEventListener("pointerleave", clearHoverCopyBody);
      timeline?.addEventListener("scroll", clearHoverCopyBody, { passive: true });
      window.addEventListener("resize", clearHoverCopyBody, { passive: true });
    }
    const openExternalLink = (href) => {
      if (document.documentElement.dataset.tauriApp === "1") {
        if (window.parent && window.parent !== window) {
          window.parent.postMessage({ type: "open-external-url", url: href }, "*");
          return Promise.resolve();
        }
        const invoke = window.__TAURI__?.core?.invoke || window.__TAURI__?.invoke;
        if (typeof invoke === "function") return invoke("open_external_url", { url: href });
        return Promise.reject(new Error("Tauri external-link bridge is unavailable"));
      }
      window.open(href, "_blank", "noopener,noreferrer");
      return Promise.resolve();
    };
    const reportExternalLinkFailure = () => setStatus("could not open external link", true);
    window.addEventListener("message", (event) => {
      if (event.source !== window.parent || event.data?.type !== "external-url-open-failed") return;
      reportExternalLinkFailure();
    });
    messagesEl.addEventListener("click", (e) => {
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
          if (document.documentElement.dataset.mobile !== "1" && anyLink.dataset.fileLinkOpen === "editor") {
            void openFile(path);
            return;
          }
          void openFileSurface(path, extFromPath(path), anyLink, e);
          return;
        }
        if (href && !href.startsWith("#") && !href.startsWith("javascript:")) {
          e.preventDefault();
          e.stopPropagation();
          void openExternalLink(href).catch(reportExternalLinkFailure);
          return;
        }
      }
      const collapseToggle = e.target.closest(".message-collapse-toggle");
      if (collapseToggle) {
        const row = collapseToggle.closest("article.message-row");
        const contextHash = row?.dataset.contextHash || "";
        if (!row || !contextHash || !isCollapsibleMessageRow(row)) return;
        if (expandedMessageBodies.has(contextHash)) {
          expandedMessageBodies.delete(contextHash);
        } else {
          expandedMessageBodies.add(contextHash);
        }
        syncMessageCollapse(row);
        return;
      }
      const codeCopyBtn = e.target.closest(".code-copy-btn");
      if (codeCopyBtn) {
        const wrap = codeCopyBtn.closest(".code-block-wrap");
        if (!wrap) return;
        const code = wrap.querySelector("code") || wrap.querySelector("pre");
        navigator.clipboard.writeText(code.textContent).then(() => {
          codeCopyBtn.innerHTML = codeCheckSvg;
          setTimeout(() => { codeCopyBtn.innerHTML = codeCopySvg; }, 1500);
        });
        return;
      }
      const btn = e.target.closest(".copy-btn");
      if (!btn) return;
      const raw = btn.closest(".message")?.dataset.raw ?? "";
      doCopyText(raw).then(() => {
        markCopied(btn);
      }).catch(() => {});
    });
    if (document.documentElement.dataset.mobile !== "1") {
      messagesEl.addEventListener("auxclick", (e) => {
        if (e.button !== 1) return;
        const anyLink = e.target.closest("a[href]");
        if (!anyLink) return;
        const href = anyLink.getAttribute("href");
        if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;
        e.preventDefault();
        e.stopPropagation();
        void openExternalLink(href).catch(reportExternalLinkFailure);
      });
    }
