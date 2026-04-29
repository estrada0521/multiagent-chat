    let _fileAutocompleteRequestSeq = 0;
    const normalizeFileEntry = (entry) => {
      if (!entry) return null;
      if (typeof entry === "string") return { path: entry, size: null };
      const path = typeof entry.path === "string" ? entry.path : "";
      if (!path) return null;
      let size = null;
      if (Object.prototype.hasOwnProperty.call(entry, "size")) {
        const rawSize = entry.size;
        if (rawSize !== null && rawSize !== undefined && rawSize !== "") {
          const parsedSize = Number(rawSize);
          if (Number.isFinite(parsedSize) && parsedSize >= 0) {
            size = parsedSize;
          }
        }
      }
      return { path, size };
    };
    const loadFileSearchMatches = async (rawQuery, limit = 30) => {
      const query = String(rawQuery || "").trim();
      const normalizedLimit = Math.max(1, Math.min(120, Number(limit) || 30));
      try {
        const params = new URLSearchParams();
        if (query) params.set("q", query);
        params.set("limit", String(normalizedLimit));
        const response = await fetchWithTimeout(`${CHAT_BASE_PATH || ""}/files-search?${params.toString()}`, {}, 2500);
        if (response.ok) {
          const raw = await response.json();
          return (Array.isArray(raw) ? raw : [])
            .map(normalizeFileEntry)
            .filter(Boolean);
        }
      } catch (_) { }
      return [];
    };
    const resolveInlineCodeFilePaths = async (queries) => {
      const unique = [...new Set((Array.isArray(queries) ? queries : []).map((item) => String(item || "").trim()).filter(Boolean))];
      if (!unique.length) return new Map();
      try {
        const response = await fetch(`${CHAT_BASE_PATH || ""}/files-resolve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ queries: unique }),
        });
        const payload = response.ok ? await response.json() : null;
        const resolved = payload && typeof payload === "object" ? payload.resolved : null;
        const out = new Map();
        for (const query of unique) {
          const path = resolved && typeof resolved[query] === "string" ? resolved[query] : "";
          if (path) out.set(query, path);
        }
        return out;
      } catch (_) {
        return new Map();
      }
    };
    const fileDrop = document.getElementById("fileDropdown");
    let _dropActiveIdx = -1;
    let _ignoreGlobalClick = false;
    let _keepAutocompleteMenuOnBlur = false;
    let _keepAutocompleteMenuBlurTimer = null;
    let _dropTimeout = null;
    const armAutocompleteMenuBlurGuard = () => {
      _keepAutocompleteMenuOnBlur = true;
      if (_keepAutocompleteMenuBlurTimer) clearTimeout(_keepAutocompleteMenuBlurTimer);
      _keepAutocompleteMenuBlurTimer = setTimeout(() => {
        _keepAutocompleteMenuOnBlur = false;
        _keepAutocompleteMenuBlurTimer = null;
      }, 260);
    };
    const _dropItems = () => fileDrop.querySelectorAll(".file-item");
    const closeDrop = () => {
      if (fileDrop.classList.contains("visible")) {
        fileDrop.classList.remove("visible");
        fileDrop.classList.add("closing");
        if (_dropTimeout) clearTimeout(_dropTimeout);
        _dropTimeout = setTimeout(() => {
          if (fileDrop.classList.contains("closing")) {
            fileDrop.style.display = "none";
            fileDrop.classList.remove("closing");
          }
          _dropTimeout = null;
        }, 160);
      } else if (!fileDrop.classList.contains("closing")) {
        fileDrop.style.display = "none";
      }
      _dropActiveIdx = -1;
    };
__CHAT_INCLUDE:../../../shared/chat/file-autocomplete.js__
    const LINKIFY_INLINE_CODE_CHUNK = 20;
    let _linkifyInlineCodeRunSeq = 0;
    let _linkifyDebounceTimer = null;
    let _linkifyDebouncedScope = null;
    const LINKIFY_POST_RENDER_DEBOUNCE_MS = 50;
    const linkifyInlineCodeFileRefsImmediate = (scope = document) => {
      if (!scope?.querySelectorAll) return;
      const snapshot = [];
      scope.querySelectorAll(".md-body code").forEach((codeEl) => {
        if (!codeEl || codeEl.closest("pre") || codeEl.closest(".file-card")) return;
        if (codeEl.closest("a")) return;
        if (codeEl.closest(".streaming-body-reveal")) return;
        snapshot.push(codeEl);
      });
      if (!snapshot.length) return;
      const runId = ++_linkifyInlineCodeRunSeq;
      const parsedEntries = snapshot.map((codeEl) => ({
        codeEl,
        parsed: parseInlineCodeFileToken(codeEl.textContent || ""),
      }));
      const queries = parsedEntries.map((item) => item.parsed?.token || "").filter(Boolean);
      if (!queries.length) return;
      void resolveInlineCodeFilePaths(queries).then((resolvedMap) => {
        if (runId !== _linkifyInlineCodeRunSeq) return;
        let i = 0;
        const processEl = (entry) => {
          const codeEl = entry.codeEl;
          const parsed = entry.parsed;
          if (!parsed || !codeEl?.isConnected) return;
          const path = resolvedMap.get(parsed.token) || "";
          if (!path) return;
          const anchor = document.createElement("a");
          anchor.className = "inline-file-link";
          anchor.href = fileViewHrefForPath(path);
          anchor.dataset.filepath = path;
          anchor.dataset.ext = extFromPath(path);
          if (parsed.line > 0) {
            anchor.dataset.line = String(parsed.line);
          }
          anchor.title = path;
          const codeClone = codeEl.cloneNode(true);
          anchor.appendChild(codeClone);
          codeEl.replaceWith(anchor);
        };
        const pump = () => {
          if (runId !== _linkifyInlineCodeRunSeq) return;
          const end = Math.min(i + LINKIFY_INLINE_CODE_CHUNK, parsedEntries.length);
          while (i < end) {
            processEl(parsedEntries[i++]);
          }
          if (i < parsedEntries.length) {
            requestAnimationFrame(pump);
          }
        };
        pump();
      });
    };
    const linkifyInlineCodeFileRefs = (scope = document) => {
      if (!scope?.querySelectorAll) return;
      _linkifyDebouncedScope = scope;
      if (_linkifyDebounceTimer) return;
      _linkifyDebounceTimer = setTimeout(() => {
        _linkifyDebounceTimer = null;
        const s = _linkifyDebouncedScope;
        _linkifyDebouncedScope = null;
        if (s?.querySelectorAll) linkifyInlineCodeFileRefsImmediate(s);
      }, LINKIFY_POST_RENDER_DEBOUNCE_MS);
    };
    const buildAutocompleteFileItem = (entry) => {
      const path = String(entry?.path || "");
      const ext = fileExtForPath(path);
      const icon = FILE_ICONS[ext] || FILE_SVG_ICONS.file;
      const label = (displayAttachmentFilename(path) || basename(path) || path).trim() || path;
      const relDir = composerAutocompleteRelativeDir(path);
      const row = document.createElement("div");
      row.className = "file-item";
      row.dataset.path = path;
      const pathInner = relDir
        ? `<span class="file-item-name">${escapeHtml(label)}</span><span class="file-item-relpath">${escapeHtml(relDir)}</span>`
        : `<span class="file-item-name">${escapeHtml(label)}</span>`;
      row.innerHTML =
        `<span class="file-item-icon">${icon}</span>` +
        `<span class="file-item-path">${pathInner}</span>` +
        `<span class="file-item-size">${escapeHtml(formatFileSize(entry?.size))}</span>`;
      return row;
    };
    const selectFile = (path) => {
      const ta = messageInput;
      const pos = ta.selectionStart;
      const before = ta.value.slice(0, pos);
      const atIdx = before.lastIndexOf("@");
      if (atIdx === -1) return closeDrop();
      const inlineRef = "`" + path + "`";
      ta.value = ta.value.slice(0, atIdx) + inlineRef + ta.value.slice(pos);
      const newPos = atIdx + inlineRef.length;
      ta.setSelectionRange(newPos, newPos);
      focusMessageInputWithoutScroll(newPos, newPos);
      _ignoreGlobalClick = true;
      closeDrop();
    };
    fileDrop.addEventListener("click", (e) => {
      e.stopPropagation();
    });
    fileDrop.addEventListener("pointerdown", armAutocompleteMenuBlurGuard);
    fileDrop.addEventListener("touchstart", armAutocompleteMenuBlurGuard, { passive: true });
    fileDrop.addEventListener("mousedown", (e) => {
      const item = e.target.closest(".file-item");
      if (item) { e.preventDefault(); selectFile(item.dataset.path); }
    });
    const autoResizeTextarea = () => {
      const baseHeight = 54;
      messageInput.style.marginTop = "0px";
      messageInput.style.height = baseHeight + "px";
      const scrollH = messageInput.scrollHeight;
      const maxHeight = 200;
      const nextHeight = Math.min(maxHeight, Math.max(baseHeight, scrollH + 2));
      messageInput.style.height = nextHeight + "px";
      messageInput.style.marginTop = (baseHeight - nextHeight) + "px";
      composerShellEl?.style.setProperty("--composer-input-rise", Math.max(0, nextHeight - baseHeight) + "px");
    };
    const positionComposerDropdown = (dropdown) => {
      if (!dropdown) return;
      const taRect = messageInput.getBoundingClientRect();
      const aboveInput = document.querySelector(".composer-above-input");
      const aboveInputHeight = aboveInput ? Math.max(0, Math.ceil(aboveInput.getBoundingClientRect().height)) : 0;
      const gap = 8;
      const availableSpace = Math.max(96, taRect.top - aboveInputHeight - 20);
      dropdown.style.left = taRect.left + "px";
      dropdown.style.width = taRect.width + "px";
      dropdown.style.minWidth = "0";
      dropdown.style.bottom = Math.max(12, window.innerHeight - taRect.top + gap + aboveInputHeight) + "px";
      dropdown.style.maxHeight = Math.min(208, availableSpace) + "px";
    };
    messageInput.addEventListener("input", () => {
      autoResizeTextarea();
    });
    window.addEventListener("resize", autoResizeTextarea);
    const updateFileAutocomplete = async () => {
      const requestSeq = ++_fileAutocompleteRequestSeq;
      const pos = messageInput.selectionEnd;
      const val = messageInput.value;
      const before = val.slice(0, pos);
      const match = before.match(/@[\w.\/-]*$/);

      if (!match) {
        if (requestSeq === _fileAutocompleteRequestSeq) closeDrop();
        return;
      }

      const query = match[0].slice(1);
      showFileAutocompleteLoading();
      const matches = await loadFileSearchMatches(query, 30);
      if (requestSeq !== _fileAutocompleteRequestSeq) return;

      if (!matches.length) {
        closeDrop();
        return;
      }

      fileDrop.replaceChildren();
      const list = document.createElement("div");
      list.className = "file-dropdown-list";
      matches.forEach((entry) => list.appendChild(buildAutocompleteFileItem(entry)));
      fileDrop.appendChild(list);

      _dropActiveIdx = -1;
      positionComposerDropdown(fileDrop);
      if (!fileDrop.classList.contains("visible")) {
        if (_dropTimeout) { clearTimeout(_dropTimeout); _dropTimeout = null; }
        fileDrop.classList.remove("closing");
        fileDrop.style.display = "block";
        fileDrop.classList.add("visible");
        closePlusMenu();
      }
    };
    messageInput.addEventListener("input", updateFileAutocomplete);
    messageInput.addEventListener("click", () => setTimeout(updateFileAutocomplete, 10));
    messageInput.addEventListener("focus", () => {
      updateFileAutocomplete();
    });
    messageInput.addEventListener("keydown", (e) => {
      if (fileDrop.style.display === "none") return;
      const items = _dropItems();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        items[_dropActiveIdx]?.classList.remove("active");
        _dropActiveIdx = Math.min(_dropActiveIdx + 1, items.length - 1);
        items[_dropActiveIdx]?.classList.add("active");
        items[_dropActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        items[_dropActiveIdx]?.classList.remove("active");
        _dropActiveIdx = Math.max(_dropActiveIdx - 1, 0);
        items[_dropActiveIdx]?.classList.add("active");
        items[_dropActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if ((e.key === "Enter" || e.key === "Tab") && _dropActiveIdx >= 0) {
        e.preventDefault();
        e.stopImmediatePropagation();
        selectFile(items[_dropActiveIdx].dataset.path);
      } else if (e.key === "Escape") {
        closeDrop();
      }
    }, true);

    const cmdDrop = document.getElementById("cmdDropdown");
