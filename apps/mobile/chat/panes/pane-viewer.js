    let paneTraceAnsiUp = null;
    let paneTraceAnsiLoadPromise = null;
    const ensurePaneTraceAnsiUp = async () => {
      if (paneTraceAnsiUp) return true;
      try {
        if (typeof AnsiUp === "function") {
          paneTraceAnsiUp = new AnsiUp();
          return true;
        }
      } catch (_) {
        paneTraceAnsiUp = null;
      }
      if (paneTraceAnsiLoadPromise) return paneTraceAnsiLoadPromise;
      paneTraceAnsiLoadPromise = loadExternalScriptOnce(ANSI_UP_SRC).then((ready) => {
        if (!ready) return false;
        try {
          if (typeof AnsiUp === "function") paneTraceAnsiUp = new AnsiUp();
        } catch (_) {
          paneTraceAnsiUp = null;
        }
        return !!paneTraceAnsiUp;
      }).finally(() => {
        if (!paneTraceAnsiUp) paneTraceAnsiLoadPromise = null;
      });
      return paneTraceAnsiLoadPromise;
    };
    const paneTraceHtml = (raw) => {
      const text = String(raw ?? "No output");
      if (!paneTraceAnsiUp) {
        try {
          if (typeof AnsiUp === "function") paneTraceAnsiUp = new AnsiUp();
        } catch (_) {
          paneTraceAnsiUp = null;
        }
      }
      let html;
      if (paneTraceAnsiUp) {
        try {
          html = paneTraceAnsiUp.ansi_to_html(text);
        } catch (_) {
          html = null;
        }
      }
      if (!html) {
        const plain = stripAnsiForTrace(text);
        html = escapeHtml(plain).replace(/\n/g, "<br>");
      }
      return html.replace(/[●⏺]/g, '<span class="trace-dot">●</span>');
    };

    // Mobile Pane Viewer（ハンバーガーパネル内の第2層）
    let paneViewerAgents = [];
    let paneViewerLastAgent = null;
    let paneViewerContentCache = Object.create(null);
    const paneViewerEl = document.getElementById("paneViewer");
    const paneViewerTabs = document.getElementById("paneViewerTabs");
    const paneViewerCarousel = document.getElementById("paneViewerCarousel");
    const scrollPaneSlideToBottom = (slide) => {
      if (!slide) return;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          slide.scrollTop = slide.scrollHeight;
        });
      });
    };
    const _paneSlideAtBottom = (el) => !el || el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    const fetchPaneViewerSlide = async (agent, slide, scrollToBottomAfter) => {
      if (!slide) return;
      if (!paneViewerEl?.classList?.contains("visible")) return;
      if (document.hidden) return;
      const body = slide.querySelector(".pane-viewer-body");
      if (!body) return;
      if (!scrollToBottomAfter && !_paneSlideAtBottom(body)) return;
      try {
        /* Pane Viewer はモバイル専用導線（Terminal ボタンはデスクトップでは /open-terminal）。常に軽量 tail。 */
        const ansiReady = ensurePaneTraceAnsiUp();
        const res = await fetch(`/trace?agent=${encodeURIComponent(agent)}&lines=160&ts=${Date.now()}`);
        if (!res.ok) return;
        const data = await res.json();
        if (!paneViewerEl?.classList?.contains("visible")) return;
        if (document.hidden) return;
        const content = String(data.content || "");
        const atBottom = _paneSlideAtBottom(body);
        const cacheKey = `${agent}`;
        if (!scrollToBottomAfter && paneViewerContentCache[cacheKey] === content) {
          return;
        }
        paneViewerContentCache[cacheKey] = content;
        await ansiReady;
        body.classList.remove("inline-loading-pane");
        body.innerHTML = paneTraceHtml(content || "No output");
        if (scrollToBottomAfter || atBottom) scrollPaneSlideToBottom(body);
      } catch (_) { }
    };
    const fetchPaneViewerSlideByIndex = (idx, scrollToBottomAfter = false) => {
      if (!paneViewerCarousel || !paneViewerAgents.length) return;
      const i = Math.max(0, Math.min(paneViewerAgents.length - 1, idx));
      const agent = paneViewerAgents[i];
      const slide = paneViewerCarousel.children[i];
      if (agent && slide) fetchPaneViewerSlide(agent, slide, scrollToBottomAfter);
    };
    /* カルーセルの見えているタブだけポーリング（全エージェント並列 /trace しない）。 */
    const fetchVisiblePaneViewerSlide = (scrollToBottomAfter = false) => {
      if (!paneViewerEl?.classList?.contains("visible")) return;
      if (document.hidden) return;
      if (!paneViewerCarousel || !paneViewerAgents.length) return;
      const width = paneViewerCarousel.offsetWidth;
      if (!width) {
        fetchPaneViewerSlideByIndex(lastPaneViewerTabIdx, scrollToBottomAfter);
        return;
      }
      const scrollLeft = paneViewerCarousel.scrollLeft;
      let idx = Math.round(scrollLeft / width);
      if (!Number.isFinite(idx)) idx = 0;
      idx = Math.max(0, Math.min(paneViewerAgents.length - 1, idx));
      fetchPaneViewerSlideByIndex(idx, scrollToBottomAfter);
    };
    function movePaneViewerIndicator(idx, { scrollTabIntoView = false } = {}) {
      const indicator = paneViewerTabs.querySelector(".pane-viewer-tab-indicator");
      const tabs = Array.from(paneViewerTabs.querySelectorAll(".pane-viewer-tab"));
      if (!indicator || !tabs.length) return;
      const safeIdx = Math.max(0, Math.min(tabs.length - 1, idx));
      const tab = tabs[safeIdx];
      indicator.style.left = tab.offsetLeft + "px";
      indicator.style.width = tab.offsetWidth + "px";
      if (scrollTabIntoView && tab) {
        tab.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
      }
    }
    const syncPaneViewerTab = () => {
      if (!paneViewerCarousel || !paneViewerAgents.length) return;
      const width = paneViewerCarousel.offsetWidth;
      if (!width) return;
      const scrollLeft = paneViewerCarousel.scrollLeft;
      let idx = Math.round(scrollLeft / width);
      if (!Number.isFinite(idx)) idx = 0;
      idx = Math.max(0, Math.min(paneViewerAgents.length - 1, idx));
      lastPaneViewerTabIdx = idx;
      paneViewerLastAgent = paneViewerAgents[idx];
      const tabs = Array.from(paneViewerTabs.querySelectorAll(".pane-viewer-tab"));
      tabs.forEach((t, i) => t.classList.toggle("active", i === idx));
      movePaneViewerIndicator(idx);
    };
    const onPaneViewerCarouselScroll = () => {
      if (!paneViewerTabScrollRaf) {
        paneViewerTabScrollRaf = requestAnimationFrame(() => {
          paneViewerTabScrollRaf = 0;
          syncPaneViewerTab();
        });
      }
      if (paneViewerTabScrollEndTimer) clearTimeout(paneViewerTabScrollEndTimer);
      paneViewerTabScrollEndTimer = setTimeout(() => {
        paneViewerTabScrollEndTimer = null;
        movePaneViewerIndicator(lastPaneViewerTabIdx, { scrollTabIntoView: true });
        fetchVisiblePaneViewerSlide(false);
      }, 120);
    };
    const schedulePaneViewerScrollAlign = () => {
      let tries = 0;
      const run = () => {
        if (!paneViewerCarousel || !paneViewerAgents.length) return;
        const w = paneViewerCarousel.offsetWidth;
        if (!w) {
          if (++tries > 48) return;
          requestAnimationFrame(run);
          return;
        }
        const agent = paneViewerLastAgent && paneViewerAgents.includes(paneViewerLastAgent)
          ? paneViewerLastAgent
          : paneViewerAgents[0];
        const idx = Math.max(0, paneViewerAgents.indexOf(agent));
        paneViewerCarousel.scrollTo({ left: idx * w, behavior: "auto" });
        syncPaneViewerTab();
        requestAnimationFrame(() => {
          movePaneViewerIndicator(lastPaneViewerTabIdx, { scrollTabIntoView: true });
        });
      };
      requestAnimationFrame(() => requestAnimationFrame(run));
    };
    const scrollToAgent = (agent) => {
      const idx = paneViewerAgents.indexOf(agent);
      if (idx < 0) return;
      lastPaneViewerTabIdx = idx;
      paneViewerLastAgent = agent;
      paneViewerCarousel.scrollTo({ left: idx * paneViewerCarousel.offsetWidth, behavior: "smooth" });
      const tabs = Array.from(paneViewerTabs.querySelectorAll(".pane-viewer-tab"));
      tabs.forEach((t, i) => t.classList.toggle("active", i === idx));
      movePaneViewerIndicator(idx, { scrollTabIntoView: true });
      fetchPaneViewerSlideByIndex(idx, true);
    };
    const buildPaneViewer = () => {
      paneViewerAgents = availableTargets.filter(t => t !== "others");
      const restoreAgent = paneViewerLastAgent && paneViewerAgents.includes(paneViewerLastAgent)
        ? paneViewerLastAgent
        : paneViewerAgents[0];
      const initialIdx = restoreAgent ? Math.max(0, paneViewerAgents.indexOf(restoreAgent)) : 0;
      paneViewerTabs.innerHTML = `<div class="pane-viewer-tab-indicator"></div>` + paneViewerAgents.map((a, i) =>
        `<button class="pane-viewer-tab${i === initialIdx ? " active" : ""}" data-agent="${escapeHtml(a)}" title="${escapeHtml(a)}" aria-label="${escapeHtml(a)}" style="--agent-pulse-delay:${agentPulseOffset(a)}s">${paneViewerTabIconHtml(a)}</button>`
      ).join("");
      paneViewerCarousel.innerHTML = paneViewerAgents.map(a =>
        `<div class="pane-viewer-slide" data-agent="${escapeHtml(a)}"><div class="pane-viewer-header-shadow"></div><div class="pane-viewer-body inline-loading-pane">${loadingIndicatorHtml("Loading…")}</div></div>`
      ).join("");
      paneViewerTabs.querySelectorAll(".pane-viewer-tab").forEach(tab => {
        tab.addEventListener("click", () => scrollToAgent(tab.dataset.agent));
      });
      if (paneViewerCarousel && !paneViewerCarousel._paneViewerScrollBound) {
        paneViewerCarousel._paneViewerScrollBound = true;
        paneViewerCarousel.addEventListener("scroll", onPaneViewerCarouselScroll, { passive: true });
      }
      syncPaneViewerTabThinkingStatuses();
      lastPaneViewerTabIdx = initialIdx;
      requestAnimationFrame(() => {
        movePaneViewerIndicator(initialIdx);
        const firstTab = paneViewerTabs.querySelector(".pane-viewer-tab.active");
        if (firstTab) firstTab.scrollIntoView({ inline: "center", block: "nearest" });
      });
    };
    const resolvePaneFocusAgent = (raw) => {
      if (!raw) return null;
      const allowed = availableTargets.filter(t => t !== "others");
      if (!allowed.length) return null;
      if (allowed.includes(raw)) return raw;
      const base = agentBaseName(raw);
      const hit = allowed.find((t) => t === base || agentBaseName(t) === base);
      return hit || null;
    };
    const showPaneTraceViewer = (focusAgent) => {
      if (!paneViewerEl) return;
      const resolved = resolvePaneFocusAgent(focusAgent);
      if (resolved) paneViewerLastAgent = resolved;
      if (paneTracePanel.classList.contains("open")) {
        if (resolved && paneViewerAgents.includes(resolved)) {
          scrollToAgent(resolved);
        }
        return;
      }
      closeGitBranchSheet({ immediate: true });
      closeAttachedFilesSheet({ immediate: true });

      // Close hamburger menu if open
      rightMenuPanel?.classList.remove("open");
      if (rightMenuPanel) rightMenuPanel.hidden = true;
      rightMenuBtn?.classList.remove("open");
      paneViewerEl.classList.remove("visible");
      paneViewerEl.hidden = true;

      openPaneTraceSheet(() => {
        paneViewerEl.hidden = false;
        paneViewerEl.classList.add("visible");
        paneViewerContentCache = Object.create(null);
        syncHeaderMenuFocus();
        clearPaneViewerOpenWork();
        paneViewerOpenRaf = requestAnimationFrame(() => {
          paneViewerOpenRaf = 0;
          buildPaneViewer();
          schedulePaneViewerScrollAlign();
          paneViewerInitialFetchTimer = setTimeout(() => {
            paneViewerInitialFetchTimer = 0;
            fetchPaneViewerSlideByIndex(lastPaneViewerTabIdx, true);
            /* LAN/Local は少し落として CPU を抑える。Public は従来どおり。 */
            const paneTracePollMs = isLocalHubHostname() ? 300 : 1500;
            if (paneViewerInterval) clearInterval(paneViewerInterval);
            paneViewerInterval = setInterval(() => fetchVisiblePaneViewerSlide(false), paneTracePollMs);
          }, 24);
        });
      });
    };
    const togglePaneViewer = () => {
      if (!paneViewerEl) return;
      if (paneTracePanel.classList.contains("open")) {
        exitPaneTraceMode();
        return;
      }
      showPaneTraceViewer(null);
    };
    const msgThinking = document.getElementById("messages");
    if (msgThinking) {
      msgThinking.addEventListener("touchstart", (e) => {
        const row = e.target.closest(".message-thinking-row");
        const providerEventsMsgId = row?.dataset?.providerEvents || "";
        if (!row || (!row.dataset.agent && !providerEventsMsgId)) {
          _thinkingRowTouch = null;
          return;
        }
        const t = e.touches && e.touches[0];
        if (!t) {
          _thinkingRowTouch = null;
          return;
        }
        _thinkingRowTouch = {
          agent: row.dataset.agent || "",
          providerEvents: providerEventsMsgId,
          x: t.clientX,
          y: t.clientY,
        };
      }, { passive: true });
      msgThinking.addEventListener("touchend", (e) => {
        if (!_thinkingRowTouch) return;
        const start = _thinkingRowTouch;
        _thinkingRowTouch = null;
        const row = e.target.closest(".message-thinking-row");
        if (!row) return;
        if ((row.dataset.providerEvents || "") !== (start.providerEvents || "")) {
          if ((row.dataset.agent || "") !== (start.agent || "")) return;
        }
        const t = e.changedTouches && e.changedTouches[0];
        if (!t) return;
        const dx = t.clientX - start.x;
        const dy = t.clientY - start.y;
        if (dx * dx + dy * dy > 100) return;
        const now = Date.now();
        if (now - _lastThinkingPaneMs < 400) return;
        _lastThinkingPaneMs = now;
        _ignoreGlobalClick = true;
        e.preventDefault();
        if (start.providerEvents) {
          void showProviderEventsModal(start.providerEvents);
        } else if (start.agent) {
          showPaneTraceViewer(start.agent);
        }
      }, { passive: false });
      msgThinking.addEventListener("touchcancel", () => {
        _thinkingRowTouch = null;
      }, { passive: true });
    }
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) return;
      if (!paneViewerEl?.classList?.contains("visible")) return;
      fetchVisiblePaneViewerSlide(false);
    });
    refreshSessionState();
    setInterval(refreshSessionState, 1500);
    setInterval(() => {
      if (Object.keys(currentAgentStatuses).length) {
        renderAgentStatus(currentAgentStatuses);
      }
    }, 1000);

