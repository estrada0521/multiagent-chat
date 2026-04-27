    let katexLoadPromise = null;
    const scopeNeedsMathRender = (node) => !!node?.querySelector?.(".math-render-needed");
    const clearMathMarkers = (node) => {
      node?.querySelectorAll?.(".math-render-needed").forEach((marker) => marker.remove());
    };
    const ensureKatexReady = async () => {
      if (typeof renderMathInElement === "function") return true;
      if (katexLoadPromise) return katexLoadPromise;
      katexLoadPromise = (async () => {
        const cssReady = await loadExternalStylesheetOnce(KATEX_CSS_HREF);
        const katexReady = await loadExternalScriptOnce(KATEX_JS_SRC);
        const autoRenderReady = katexReady ? await loadExternalScriptOnce(KATEX_AUTO_RENDER_SRC) : false;
        return cssReady && katexReady && autoRenderReady && typeof renderMathInElement === "function";
      })().catch(() => false);
      return katexLoadPromise;
    };
    const renderMathInScope = (node) => {
      if (!node || !scopeNeedsMathRender(node)) return;
      const applyMath = () => {
        if (typeof renderMathInElement === "undefined") return;
        renderMathInElement(node, mathRenderOptions);
        clearMathMarkers(node);
      };
      if (typeof renderMathInElement === "function") {
        applyMath();
        return;
      }
      ensureKatexReady().then((ready) => {
        if (ready) applyMath();
      });
    };
    let _mermaidReady = false;
    let _mermaidLoading = false;
    let _mermaidSeq = 0;
    const _mermaidQueue = [];
    const getMermaidFontFamily = () => {
      const mode = document.documentElement.getAttribute("data-agent-font-mode");
      return mode === "gothic"
        ? '"anthropicSans","Anthropic Sans","SF Pro Text","Segoe UI","Hiragino Kaku Gothic ProN","Hiragino Sans","Meiryo",sans-serif'
        : '"anthropicSerif","Anthropic Serif","Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",Georgia,serif';
    };
    const DARK_BG = "__DARK_BG__";
    const initMermaid = () => {
      mermaid.initialize({
        startOnLoad: false,
        theme: "base",
        securityLevel: "loose",
        flowchart: { padding: 8, nodeSpacing: 30, rankSpacing: 40 },
        themeVariables: {
          background: DARK_BG,
          primaryColor: "rgb(30,30,30)",
          primaryBorderColor: "rgb(252,252,252)",
          primaryTextColor: "rgb(252,252,252)",
          secondaryColor: "rgb(30,30,30)",
          secondaryBorderColor: "rgb(252,252,252)",
          secondaryTextColor: "rgb(252,252,252)",
          tertiaryColor: "rgb(30,30,30)",
          tertiaryBorderColor: "rgb(252,252,252)",
          tertiaryTextColor: "rgb(252,252,252)",
          lineColor: "rgb(252,252,252)",
          textColor: "rgb(252,252,252)",
          mainBkg: "rgb(30,30,30)",
          nodeBorder: "rgb(252,252,252)",
          clusterBkg: DARK_BG,
          clusterBorder: "rgb(252,252,252)",
          edgeLabelBackground: "transparent",
          fontSize: "14px",
          fontFamily: getMermaidFontFamily()
        }
      });
      _mermaidReady = true;
    };
    const loadMermaid = () => {
      if (_mermaidReady || _mermaidLoading) return;
      _mermaidLoading = true;
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
      s.onload = () => {
        initMermaid();
        _mermaidQueue.forEach(fn => fn());
        _mermaidQueue.length = 0;
      };
      document.head.appendChild(s);
    };
    const doRenderMermaid = async (scope) => {
      for (const codeEl of scope.querySelectorAll("pre > code.language-mermaid")) {
        const pre = codeEl.parentElement;
        if (pre.dataset.mermaidRendered) continue;
        pre.dataset.mermaidRendered = "1";
        const id = `mermaid-${_mermaidSeq++}`;
        try {
          const { svg } = await mermaid.render(id, codeEl.textContent);
          const container = document.createElement("div");
          container.className = "mermaid-container";
          container.innerHTML = svg;
          const svgEl = container.querySelector("svg");
          if (svgEl) { svgEl.removeAttribute("width"); svgEl.removeAttribute("height"); svgEl.style.width = "100%"; svgEl.style.height = "auto"; }
          pre.replaceWith(container);
        } catch (_) {}
      }
    };
    const renderMermaidInScope = (scope) => {
      if (!scope || !scope.querySelector("pre > code.language-mermaid")) return;
      if (_mermaidReady) { doRenderMermaid(scope); return; }
      _mermaidQueue.push(() => doRenderMermaid(scope));
      loadMermaid();
    };
    const ensureWideTables = (scope = document) => {
      scope.querySelectorAll(".md-body table").forEach((table) => {
        if (table.closest(".table-scroll")) return;
        const parent = table.parentNode;
        if (!parent) return;
        const scroll = document.createElement("div");
        scroll.className = "table-scroll";
        parent.insertBefore(scroll, table);
        scroll.appendChild(table);
      });
    };
    const syncWideBlockRows = (scope = document) => {
      ensureWideTables(scope);
      scope.querySelectorAll(".message-body-row").forEach((row) => {
        const body = row.querySelector(".md-body");
        const hasStructuredBlock = !!body?.querySelector("ul, ol, blockquote, pre, .table-scroll, .katex-display");
        row.classList.toggle("has-structured-block", hasStructuredBlock);
      });
    };
    let stableCodeBlocksRaf = 0;
    const stableCodeBlockScopes = new Set();
    const queueStableCodeBlockSync = (scope = document) => {
      if (scope) stableCodeBlockScopes.add(scope);
      if (stableCodeBlocksRaf) return;
      stableCodeBlocksRaf = requestAnimationFrame(() => {
        stableCodeBlocksRaf = 0;
        const scopes = Array.from(stableCodeBlockScopes);
        stableCodeBlockScopes.clear();
        const seen = new Set();
        const pres = [];
        scopes.forEach((target) => {
          if (!target) return;
          const list = target?.matches?.(".md-body pre")
            ? [target]
            : Array.from(target.querySelectorAll?.(".md-body pre") || []);
          list.forEach((pre) => {
            if (!pre || !pre.isConnected || seen.has(pre)) return;
            seen.add(pre);
            pres.push(pre);
          });
        });
        pres.forEach((pre) => {
          const width = pre.clientWidth || 0;
          const prevWidth = Number.parseFloat(pre.dataset.stableWidth || "0");
          const widthChanged = Math.abs(width - prevWidth) > 0.5;
          if (widthChanged) {
            pre.style.removeProperty("--code-scroll-stable-height");
          }
          const hasHorizontalScroll = (pre.scrollWidth - pre.clientWidth) > 1;
          if (hasHorizontalScroll) {
            pre.style.setProperty("--code-scroll-stable-height", `${pre.offsetHeight}px`);
            pre.dataset.stableWidth = String(width);
            pre.dataset.stableCodeScroll = "1";
          } else if (widthChanged || pre.dataset.stableCodeScroll === "1") {
            pre.style.removeProperty("--code-scroll-stable-height");
            pre.dataset.stableWidth = String(width);
            delete pre.dataset.stableCodeScroll;
          } else {
            pre.dataset.stableWidth = String(width);
          }
        });
      });
    };
    updateScrollBtnPos();
    window.addEventListener("resize", () => { syncWideBlockRows(document); queueStableCodeBlockSync(document); });
    if (document.fonts?.ready) {
      document.fonts.ready.then(() => {
        syncWideBlockRows(document);
        queueStableCodeBlockSync(document);
      }).catch(() => {});
    }
    const AGENT_ICON_NAMES = __AGENT_ICON_NAMES_JS_SET__;
    const ALL_BASE_AGENTS = __ALL_BASE_AGENTS_JS_ARRAY__;
    const agentBaseName = (name) => (name || "").toLowerCase().replace(/-\d+$/, "");
    const agentIconInstanceSubDigits = (name) => {
      const m = String(name || "").toLowerCase().match(/-(\d+)$/);
      return m ? m[1] : "";
    };
    const agentIconInstanceSubHtml = (name) => {
      const d = agentIconInstanceSubDigits(name);
      return d ? `<span class="agent-icon-instance-sub" aria-hidden="true">${escapeHtml(d)}</span>` : "";
    };
    const roleClass = (sender) => {
      const base = agentBaseName(sender);
      if (base === "user" || AGENT_ICON_NAMES.has(base)) return base;
      return "agent";
    };
    const agentIconSrc = (name) => {
      const raw = String(name || "").trim();
      if (!raw) return `${CHAT_ASSET_BASE}/icon/`;
      const base = agentBaseName(raw);
      const enc = encodeURIComponent(raw.toLowerCase());
      if (AGENT_ICON_DATA[base]) return AGENT_ICON_DATA[base];
      return `${CHAT_ASSET_BASE}/icon/${enc}`;
    };
    const agentPulseOffset = () => 0;
    const paneViewerTabIconHtml = (agent) => {
      const iconUrl = agentIconSrc(agent);
      const sub = agentIconInstanceSubHtml(agent);
      return `<span class="agent-icon-slot agent-icon-slot--pane-tab"><img class="pane-viewer-tab-icon" src="${escapeHtml(iconUrl)}" alt="" aria-hidden="true">${sub}</span>`;
    };
    const thinkingIconImg = (name, cls) => {
      const base = agentBaseName(name);
      if (!AGENT_ICON_NAMES.has(base)) return "";
      const sub = agentIconInstanceSubHtml(name);
      return `<span class="agent-icon-slot agent-icon-slot--thinking"><span class="${cls}" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(name))}')"></span>${sub}</span>`;
    };
    const entryQualifiesForStreamReveal = (entry) => {
      const s = String(entry?.sender || "").trim().toLowerCase();
      const kind = String(entry?.kind || "").trim().toLowerCase();
      if (kind === "agent-thinking") return false;
      return s !== "" && s !== "user" && s !== "system";
    };
    const STREAM_CHAR_SKIP_SEL = ".katex, .katex-display, .mermaid-container, table, .table-scroll, script, style";
    const STREAM_CHAR_ANIM_MS = 21;
    const STREAM_CHAR_CAP = 3600;
    const unwrapStreamCharSpans = (row) => {
      if (!row) return;
      row.querySelectorAll(".md-body").forEach((md) => {
        md.querySelectorAll(".stream-char").forEach((span) => {
          span.replaceWith(document.createTextNode(span.textContent));
        });
        try { md.normalize(); } catch (_) {}
        delete md.dataset.streamCharsApplied;
      });
    };
    const applyCharStreamRevealToRow = (row) => {
      const mdBody = row?.querySelector?.(".md-body");
      if (!mdBody || mdBody.dataset.streamCharsApplied) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        mdBody.dataset.streamCharsApplied = "1";
        row._streamRevealTotalMs = 0;
        return;
      }
      let idx = 0;
      const wrapText = (node) => {
        if (idx >= STREAM_CHAR_CAP) return;
        const text = node.nodeValue;
        if (!text || !/\S/.test(text)) return;
        const parentEl = node.parentElement;
        if (!parentEl || parentEl.closest(STREAM_CHAR_SKIP_SEL)) return;
        const take = Math.min(text.length, STREAM_CHAR_CAP - idx);
        const head = text.slice(0, take);
        const tail = text.slice(take);
        const frag = document.createDocumentFragment();
        for (let i = 0; i < head.length; i++) {
          const ch = head[i];
          const span = document.createElement("span");
          span.className = "stream-char";
          span.textContent = ch;
          span.style.setProperty("--stream-char-i", String(idx++));
          frag.appendChild(span);
        }
        if (tail) frag.appendChild(document.createTextNode(tail));
        node.parentNode.replaceChild(frag, node);
      };
      const walk = (node) => {
        if (idx >= STREAM_CHAR_CAP) return;
        if (node.nodeType === Node.TEXT_NODE) {
          wrapText(node);
          return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        if (node.matches(STREAM_CHAR_SKIP_SEL)) return;
        Array.from(node.childNodes).forEach(walk);
      };
      walk(mdBody);
      mdBody.dataset.streamCharsApplied = "1";
      const totalDuration = Math.min(idx * 8, 750);
      const charDelay = idx > 0 ? totalDuration / idx : 8;
      mdBody.style.setProperty("--stream-char-delay", charDelay + "ms");
      row._streamRevealTotalMs = totalDuration + STREAM_CHAR_ANIM_MS + 80;
    };
    const metaAgentLabel = (name, textClass, iconSide = "right", { iconOnly = false } = {}) => {
      const raw = (name || "").trim() || "unknown";
      const base = agentBaseName(raw);
      const hasIcon = AGENT_ICON_NAMES.has(base);
      const icon = hasIcon
        ? `<span class="agent-icon-slot agent-icon-slot--meta"><span class="meta-agent-icon" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(raw))}')"></span>${agentIconInstanceSubHtml(raw)}</span>`
        : iconOnly
          ? `<span class="agent-icon-slot agent-icon-slot--meta meta-agent-fallback" aria-hidden="true">—</span>`
          : "";
      const sideClass = iconSide === "right" ? " icon-right" : "";
      const titleAttr = ` title="${escapeHtml(raw).replaceAll('"', "&quot;")}"`;
      const labelAttr = iconOnly ? ` aria-label="${escapeHtml(raw).replaceAll('"', "&quot;")}"` : "";
      if (iconOnly) {
        return `<span class="meta-agent meta-agent--icon-only${sideClass}"${titleAttr}${labelAttr}>${icon}</span>`;
      }
      return `<span class="meta-agent${sideClass}">${icon}<span class="${textClass}">${escapeHtml(raw)}</span></span>`;
    };
