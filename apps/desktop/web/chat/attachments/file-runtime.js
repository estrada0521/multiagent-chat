    let _fileList = null;
    let _fileListPromise = null;
    let _fileAutocompleteRequestSeq = 0;
    let _inlineFileLinkWarmupStarted = false;
    let _inlineFileLinkReplayQueued = false;
    let _inlineFileLinkStaleRelinkTimer = null;
    const _inlineFileLinkResolutionCache = new Map();
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
    const loadFiles = async ({ refreshServer = false } = {}) => {
      if (!refreshServer) {
        if (_fileList) return _fileList;
        if (_fileListPromise) return _fileListPromise;
      }
      _fileListPromise = (async () => {
        try {
          const q = refreshServer ? "?refresh=1" : "";
          const r = await fetch(`${CHAT_BASE_PATH || ""}/files${q}`);
          const raw = r.ok ? await r.json() : [];
          _fileList = (Array.isArray(raw) ? raw : [])
            .map(normalizeFileEntry)
            .filter(Boolean);
        } catch (_) {
          _fileList = [];
        }
        _inlineFileLinkResolutionCache.clear();
        try { clearFileAutocompleteScoreCache(); } catch (_) {}
        _fileExistenceCache.clear();
        return _fileList;
      })().finally(() => {
        _fileListPromise = null;
      });
      return _fileListPromise;
    };
    const forceRefreshFileListForLinkify = async () => {
      try {
        if (_fileListPromise) await _fileListPromise;
      } catch (_) {}
      _fileList = null;
      _fileListPromise = null;
      _inlineFileLinkResolutionCache.clear();
      try { clearFileAutocompleteScoreCache(); } catch (_) {}
      return loadFiles({ refreshServer: true });
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
      const files = await loadFiles();
      return query
        ? findFileMatches(files, query.toLowerCase(), normalizedLimit)
        : files.slice(0, normalizedLimit);
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
    const loadingIndicatorHtml = (_label = "Loading...") =>
      '<span class="inline-loading"><span class="inline-loading-spinner" aria-hidden="true"></span></span>';
__CHAT_INCLUDE:../../../../shared/chat/file-autocomplete.js__
        .catch(() => {})
        .finally(() => {
          _inlineFileLinkWarmupStarted = false;
        });
    };
    const scheduleInlineFileListStaleRelink = (scope) => {
      if (_inlineFileLinkStaleRelinkTimer) clearTimeout(_inlineFileLinkStaleRelinkTimer);
      _inlineFileLinkStaleRelinkTimer = setTimeout(() => {
        _inlineFileLinkStaleRelinkTimer = null;
        void forceRefreshFileListForLinkify().then(() => {
          requestAnimationFrame(() => {
            const root = document.getElementById("messages");
            const target = scope?.isConnected ? scope : (root || document);
            linkifyInlineCodeFileRefsImmediate(target);
          });
        });
      }, 120);
    };
    const resolveInlineCodeFilePath = (rawValue) => {
      const parsed = parseInlineCodeFileToken(rawValue);
      if (!parsed) return { path: "", line: 0, needsIndex: false, needsStaleListRetry: false };
      const query = parsed.token;
      const cacheKey = query.toLowerCase();
      if (_inlineFileLinkResolutionCache.has(cacheKey)) {
        const raw = _inlineFileLinkResolutionCache.get(cacheKey) || "";
        return {
          path: normalizeWorkspaceFilePath(raw) || raw,
          line: parsed.line,
          needsIndex: false,
          needsStaleListRetry: false,
        };
      }
      const filesReady = Array.isArray(_fileList);
      let resolvedPath = "";
      if (filesReady && _fileList.length) {
        resolvedPath = resolveInlineFilePathFromList(_fileList, query);
      }
      if (resolvedPath) {
        const np = normalizeWorkspaceFilePath(resolvedPath) || resolvedPath;
        _inlineFileLinkResolutionCache.set(cacheKey, np);
        return { path: np, line: parsed.line, needsIndex: false, needsStaleListRetry: false };
      }
      if (!filesReady) {
        const directCandidate = query
          .replace(/^\.\/+/, "")
          .replace(/^\/+/, "")
          .replace(/\\/g, "/")
          .trim();
        const isDirectPathLike =
          !!directCandidate
          && !directCandidate.startsWith("../")
          && !directCandidate.startsWith("~/")
          && !directCandidate.includes("//")
          && /^[A-Za-z0-9._/-]+$/.test(directCandidate)
          && (directCandidate.includes("/") || /\.[A-Za-z0-9]{1,10}$/.test(directCandidate));
        if (isDirectPathLike) {
          return { path: directCandidate, line: parsed.line, needsIndex: true, needsStaleListRetry: false };
        }
      }
      const needsIndex = !filesReady && /[\/._-]/.test(query);
      const looksFileLike = /[\/._-]/.test(query) || /\.[A-Za-z0-9]{1,10}$/.test(query);
      const needsStaleListRetry = !!(filesReady && !resolvedPath && looksFileLike);
      return { path: "", line: parsed.line, needsIndex, needsStaleListRetry };
    };
    const LINKIFY_INLINE_CODE_CHUNK = 20;
    let _linkifyInlineCodeRunSeq = 0;
    let _linkifyDebounceTimer = null;
    let _linkifyDebouncedScope = null;
    const LINKIFY_POST_RENDER_DEBOUNCE_MS = 50;
    let _lastInlineStaleRelinkScheduleMs = 0;
    const INLINE_STALE_RELINK_MIN_GAP_MS = 5000;
    const linkifyInlineCodeFileRefsImmediate = (scope = document) => {
      if (!scope?.querySelectorAll) return;
      const snapshot = [];
      scope.querySelectorAll(".md-body code").forEach((codeEl) => {
        if (!codeEl || codeEl.closest("pre") || codeEl.closest(".file-card")) return;
        if (codeEl.closest("a")) return;
        snapshot.push(codeEl);
      });
      if (!snapshot.length) return;
      const runId = ++_linkifyInlineCodeRunSeq;
      let i = 0;
      let needsIndexWarmup = false;
      let needsStaleRelink = false;
      const processEl = (codeEl) => {
        const resolved = resolveInlineCodeFilePath(codeEl.textContent || "");
        if (!resolved.path) {
          if (resolved.needsIndex) needsIndexWarmup = true;
          if (resolved.needsStaleListRetry) needsStaleRelink = true;
          return;
        }
        const path = normalizeWorkspaceFilePath(resolved.path) || resolved.path;
        const anchor = document.createElement("a");
        anchor.className = "inline-file-link";
        anchor.href = fileViewHrefForPath(path);
        anchor.dataset.filepath = path;
        anchor.dataset.ext = extFromPath(path);
        if (resolved.line > 0) {
          anchor.dataset.line = String(resolved.line);
        }
        anchor.title = path;
        const codeClone = codeEl.cloneNode(true);
        anchor.appendChild(codeClone);
        codeEl.replaceWith(anchor);
      };
      const pump = () => {
        if (runId !== _linkifyInlineCodeRunSeq) return;
        const end = Math.min(i + LINKIFY_INLINE_CODE_CHUNK, snapshot.length);
        while (i < end) {
          const el = snapshot[i++];
          if (el.isConnected) processEl(el);
        }
        if (i < snapshot.length) {
          requestAnimationFrame(pump);
        } else {
          if (needsIndexWarmup) scheduleInlineFileListWarmup();
          if (needsStaleRelink) {
            const now = Date.now();
            if (now - _lastInlineStaleRelinkScheduleMs >= INLINE_STALE_RELINK_MIN_GAP_MS) {
              _lastInlineStaleRelinkScheduleMs = now;
              scheduleInlineFileListStaleRelink(scope);
            }
          }
        }
      };
      pump();
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
      const composerFieldEl = document.querySelector(".composer-field");
      messageInput.style.marginTop = "0px";
      messageInput.style.height = baseHeight + "px"; // Reset first to measure natural content height
      const scrollH = messageInput.scrollHeight;
      const maxHeight = 200;
      const nextHeight = Math.min(maxHeight, Math.max(baseHeight, scrollH + 2)); // +2px avoids tiny scroll jumps
      messageInput.style.height = nextHeight + "px";
      if (composerFieldEl) {
        composerFieldEl.style.minHeight = nextHeight + "px";
        composerFieldEl.style.height = nextHeight + "px";
      }
      messageInput.style.marginTop = "0px";
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
      // Capture '@' followed by any word chars, dots, slashes or dashes until end
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

    /* ── Slash command autocomplete ── */
    const cmdDrop = document.getElementById("cmdDropdown");
