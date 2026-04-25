    const CHAT_BASE_PATH = "__CHAT_BASE_PATH__";
    const CHAT_ASSET_BASE = CHAT_BASE_PATH || "";
    const withChatBase = (path) => {
      const raw = String(path || "");
      if (!CHAT_BASE_PATH || !raw.startsWith("/") || raw.startsWith("//")) return raw;
      return `${CHAT_BASE_PATH}${raw}`;
    };
    if (CHAT_BASE_PATH) {
      const __origFetch = window.fetch.bind(window);
      window.fetch = (input, init) => {
        if (typeof input === "string" && input.startsWith("/") && !input.startsWith("//")) {
          return __origFetch(`${CHAT_BASE_PATH}${input}`, init);
        }
        if (input instanceof Request) {
          const url = input.url || "";
          if (url.startsWith(window.location.origin + "/")) {
            const nextUrl = `${window.location.origin}${CHAT_BASE_PATH}${url.slice(window.location.origin.length)}`;
            return __origFetch(new Request(nextUrl, input), init);
          }
        }
        return __origFetch(input, init);
      };
    }
    const loadExternalScriptOnce = (() => {
      const pending = new Map();
      return (src) => {
        const raw = String(src || "").trim();
        if (!raw) return Promise.resolve(false);
        const href = new URL(raw, window.location.href).href;
        for (const script of document.scripts) {
          if ((script.src || "") === href) return Promise.resolve(true);
        }
        if (pending.has(href)) return pending.get(href);
        const promise = new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.src = href;
          script.onload = () => resolve(true);
          script.onerror = () => reject(new Error(`failed to load ${href}`));
          document.head.appendChild(script);
        }).catch(() => false);
        pending.set(href, promise);
        return promise;
      };
    })();
    const loadExternalStylesheetOnce = (() => {
      const pending = new Map();
      return (href) => {
        const raw = String(href || "").trim();
        if (!raw) return Promise.resolve(false);
        const absHref = new URL(raw, window.location.href).href;
        for (const link of document.querySelectorAll('link[rel="stylesheet"]')) {
          if ((link.href || "") === absHref) return Promise.resolve(true);
        }
        if (pending.has(absHref)) return pending.get(absHref);
        const promise = new Promise((resolve, reject) => {
          const link = document.createElement("link");
          link.rel = "stylesheet";
          link.href = absHref;
          link.onload = () => resolve(true);
          link.onerror = () => reject(new Error(`failed to load ${absHref}`));
          document.head.appendChild(link);
        }).catch(() => false);
        pending.set(absHref, promise);
        return promise;
      };
    })();
    const ANSI_UP_SRC = "https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js";
    const KATEX_CSS_HREF = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css";
    const KATEX_JS_SRC = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js";
    const KATEX_AUTO_RENDER_SRC = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js";
    const renderMarkdown = (text) => {
      if (typeof marked !== "undefined") {
        try {
          const mathBlocks = [];
          let placeholderCount = 0;

          // Phase 1: protect code blocks and inline code from math extraction
          const codeBlocks = [];
          let codeCount = 0;
          let processedText = text.replace(/(```[\s\S]*?```|`[^`\n]+`)/g, (match) => {
            const id = `code-placeholder-${codeCount++}`;
            codeBlocks.push({ id, content: match });
            return `\x00CODE:${id}\x00`;
          });

          // Phase 2: wrap shell variables in no-math spans so KaTeX ignores them
          // $VAR_NAME → <span class="no-math">&#36;VAR_NAME</span>
          // ${...} and $(...) → <span class="no-math">&#36;{...}</span> etc.
          processedText = processedText.replace(/(?<!\$)\$([A-Z_][A-Z0-9_]+)/g, '<span class="no-math">&#36;$1</span>');
          processedText = processedText.replace(/\$([{(][^})\n]*[})])/g, '<span class="no-math">&#36;$1</span>');

          // Phase 3: extract math before marked.js inserts <br> into multiline blocks
          processedText = processedText.replace(/(\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$|\$[\s\S]+?\$)/g, (match) => {
            const id = `math-placeholder-${placeholderCount++}`;
            mathBlocks.push({ id, content: match });
            return `<span class="MATH_SAFE_BLOCK" data-id="${id}"></span>`;
          });

          // Phase 4: restore code blocks so marked.js can parse them
          processedText = processedText.replace(/\x00CODE:(code-placeholder-\d+)\x00/g, (_, id) => {
            const block = codeBlocks.find(b => b.id === id);
            return block ? block.content : "";
          });

          let html = marked.parse(processedText, { breaks: true, gfm: true });

          // Restoration: replace the safe spans back with original math content
          const tempDiv = document.createElement("div");
          tempDiv.innerHTML = html;
          tempDiv.querySelectorAll(".MATH_SAFE_BLOCK").forEach(span => {
            const block = mathBlocks.find(b => b.id === span.dataset.id);
            if (block) {
              // We use textContent to ensure it's not double-parsed by HTML
              span.outerHTML = block.content;
            }
          });
          if (mathBlocks.length) {
            const marker = document.createElement("span");
            marker.className = "math-render-needed";
            marker.hidden = true;
            tempDiv.prepend(marker);
          }
          // Prism syntax highlighting (skip diff blocks — handled separately)
          if (typeof Prism !== "undefined") {
            tempDiv.querySelectorAll('code[class*="language-"]').forEach(codeEl => {
              if (codeEl.classList.contains("language-diff")) return;
              Prism.highlightElement(codeEl);
            });
          }
          // Diff syntax highlighting
          tempDiv.querySelectorAll('code.language-diff').forEach(codeEl => {
            const raw = codeEl.textContent;
            codeEl.innerHTML = raw.split("\n").map(line => {
              if (line.startsWith("+")) return `<span class="diff-add"><span class="diff-sign">+</span>${escapeHtml(line.slice(1))}</span>`;
              if (line.startsWith("-")) return `<span class="diff-del"><span class="diff-sign">-</span>${escapeHtml(line.slice(1))}</span>`;
              return escapeHtml(line);
            }).join("\n");
          });

          // Inject copy button into each <pre> block
          const copySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
          tempDiv.querySelectorAll("pre").forEach(pre => {
            const wrap = document.createElement("div");
            wrap.className = "code-block-wrap";
            pre.parentNode.insertBefore(wrap, pre);
            wrap.appendChild(pre);
            wrap.insertAdjacentHTML("beforeend", `<button class="code-copy-btn" title="Copy">${copySvg}</button>`);
          });

          return injectFileCards(tempDiv.innerHTML);
        } catch (_) {}
      }
      // fallback: plain text
      return injectFileCards("<pre>" + escapeHtml(text) + "</pre>");
    };
    const wrapFileIcon = (path) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
    const FILE_SVG_ICONS = {
      image: wrapFileIcon('<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>'),
      video: wrapFileIcon('<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>'),
      audio: wrapFileIcon('<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>'),
      file: wrapFileIcon('<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>'),
      code: wrapFileIcon('<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>'),
      archive: wrapFileIcon('<path d="M21 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v3"/><path d="m3 8 9 6 9-6"/><path d="M3 18v-8"/><path d="M21 18v-8"/><path d="M3 18a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2"/>'),
      web: wrapFileIcon('<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>')
    };
    const FILE_ICONS = {
      png: FILE_SVG_ICONS.image, jpg: FILE_SVG_ICONS.image, jpeg: FILE_SVG_ICONS.image, gif: FILE_SVG_ICONS.image, webp: FILE_SVG_ICONS.image, svg: FILE_SVG_ICONS.image, ico: FILE_SVG_ICONS.image,
      pdf: FILE_SVG_ICONS.file,
      mp4: FILE_SVG_ICONS.video, mov: FILE_SVG_ICONS.video, webm: FILE_SVG_ICONS.video, avi: FILE_SVG_ICONS.video, mkv: FILE_SVG_ICONS.video,
      mp3: FILE_SVG_ICONS.audio, wav: FILE_SVG_ICONS.audio, ogg: FILE_SVG_ICONS.audio, m4a: FILE_SVG_ICONS.audio, flac: FILE_SVG_ICONS.audio,
      zip: FILE_SVG_ICONS.archive, tar: FILE_SVG_ICONS.archive, gz: FILE_SVG_ICONS.archive, bz2: FILE_SVG_ICONS.archive, rar: FILE_SVG_ICONS.archive,
      md: FILE_SVG_ICONS.file, txt: FILE_SVG_ICONS.file,
      py: FILE_SVG_ICONS.code, js: FILE_SVG_ICONS.code, ts: FILE_SVG_ICONS.code, sh: FILE_SVG_ICONS.code, json: FILE_SVG_ICONS.code, yaml: FILE_SVG_ICONS.code, yml: FILE_SVG_ICONS.code,
      html: FILE_SVG_ICONS.web, css: FILE_SVG_ICONS.web,
    };
    const displayAttachmentFilename = (path) => {
      const filename = String(path || "").split("/").pop() || String(path || "");
      if (!/(?:^|\/)uploads\//.test(String(path || ""))) return filename;
      const match = filename.match(/^\d{8}_\d{6}_(.+)$/);
      return match ? match[1] : filename;
    };
    const currentFilePreviewFontMode = () => {
      const mode = String(document.documentElement.getAttribute("data-agent-font-mode") || "").trim().toLowerCase();
      return mode === "gothic" ? "gothic" : "serif";
    };
    const currentFilePreviewTextSize = () => {
      try {
        const rawSize = window.getComputedStyle(document.documentElement).getPropertyValue("--message-text-size") || "";
        const parsedSize = Number.parseInt(String(rawSize).trim(), 10);
        if (Number.isFinite(parsedSize) && parsedSize >= 11 && parsedSize <= 18) {
          return String(parsedSize);
        }
      } catch (_) {}
      return "";
    };
