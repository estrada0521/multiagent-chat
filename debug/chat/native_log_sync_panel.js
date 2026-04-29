(() => {
  try {
    if (typeof isPublicChatView !== "undefined" && isPublicChatView) return;
  } catch (_) {
    /* keep if parent script context changes */
  }
  const FAB_ID = "multiagent-debug-native-log-sync-fab";
  const MODAL_ID = "multiagent-debug-native-log-sync-modal";
  if (document.getElementById(FAB_ID)) return;

  const esc = (s) => {
    const d = document.createElement("div");
    d.textContent = String(s ?? "");
    return d.innerHTML;
  };

  const injectStyles = () => {
    if (document.getElementById("multiagent-debug-native-log-sync-styles")) return;
    const style = document.createElement("style");
    style.id = "multiagent-debug-native-log-sync-styles";
    style.textContent = `
#${FAB_ID} {
  position: fixed;
  bottom: calc(16px + env(safe-area-inset-bottom, 0px));
  right: calc(16px + env(safe-area-inset-right, 0px));
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--line-strong, rgba(255,255,255,0.12));
  background: #000000;
  color: var(--muted, #9e9e9e);
  font: 500 13px/1 "SF Pro Text", system-ui, sans-serif;
  cursor: pointer;
  z-index: 9998;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 140ms ease;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
#${FAB_ID}:hover {
  background: rgb(20, 20, 20);
  color: var(--text, #fcfcfc);
  border-color: rgba(255,255,255,0.2);
}
#${FAB_ID}:focus-visible { outline: 2px solid var(--inline-file-link-fg, #58a6ff); outline-offset: 2px; }

#${MODAL_ID} {
  position: fixed;
  inset: 0;
  z-index: 10050;
  display: none;
  align-items: center;
  justify-content: center;
  padding: 20px;
  box-sizing: border-box;
  background: rgba(0,0,0,0.42);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}
#${MODAL_ID}[data-open="1"] { display: flex; }

#${MODAL_ID} .nl-debug-panel {
  width: 100%;
  max-width: 480px;
  max-height: min(80vh, 520px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #000000;
  color: var(--text, #fcfcfc);
  border-radius: 20px;
  border: 1px solid var(--line-strong, rgba(255,255,255,0.12));
  box-shadow: 0 12px 48px rgba(0,0,0,0.6);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  animation: dropdownIn 240ms cubic-bezier(0.16, 1, 0.3, 1);
}

#${MODAL_ID} .nl-debug-header {
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line, rgba(255,255,255,0.07));
}

#${MODAL_ID} .nl-debug-panel h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  font-family: "SF Pro Display", system-ui, sans-serif;
  letter-spacing: -0.01em;
  text-align: center;
}

#${MODAL_ID} .nl-debug-content {
  padding: 16px 20px 24px;
  overflow-y: auto;
  flex: 1;
}

#${MODAL_ID} .nl-debug-content::-webkit-scrollbar {
  width: 14px;
}
#${MODAL_ID} .nl-debug-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border: 4px solid transparent;
  background-clip: padding-box;
  border-radius: 999px;
}

#${MODAL_ID} .nl-debug-description {
  margin: 0 0 16px;
  font-family: "SF Pro Text", system-ui, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  color: var(--muted, #9e9e9e);
}

#${MODAL_ID} .nl-debug-rows {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

#${MODAL_ID} .nl-debug-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

#${MODAL_ID} .nl-debug-agent {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #ffffff;
  font-family: "SF Pro Text", system-ui, sans-serif;
}

#${MODAL_ID} .nl-debug-path {
  font-family: var(--code-font-family, monospace);
  font-size: 12px;
  line-height: 1.4;
  word-break: break-all;
  white-space: pre-wrap;
  color: var(--text, #fcfcfc);
  opacity: 0.9;
}

#${MODAL_ID} .nl-debug-meta {
  font-family: var(--code-font-family, monospace);
  font-size: 11px;
  color: var(--muted, #9e9e9e);
  margin-top: 2px;
}

#${MODAL_ID} button.nl-debug-path.nl-debug-open {
  display: block;
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  color: var(--inline-file-link-fg, #58a6ff);
  text-decoration: none;
  transition: opacity 140ms ease;
}
#${MODAL_ID} button.nl-debug-path.nl-debug-open:hover {
  opacity: 0.8;
  text-decoration: underline;
}

#${MODAL_ID} .nl-debug-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: rgba(255,255,255,0.06);
  color: var(--text, #fcfcfc);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  transition: all 140ms ease;
  z-index: 2;
}
#${MODAL_ID} .nl-debug-close:hover {
  background: rgba(255,255,255,0.12);
}
`;
    document.head.appendChild(style);
  };

  const closeModal = () => {
    const modal = document.getElementById(MODAL_ID);
    if (modal) modal.dataset.open = "0";
  };

  const openNativeLogPathInEditor = async (absPath) => {
    const url =
      typeof withChatBase === "function" ? withChatBase("/open-file-in-editor") : "/open-file-in-editor";
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: absPath, allow_native_log_home: true, line: 0 }),
    });
    let payload;
    try {
      payload = await res.json();
    } catch (_) {
      payload = {};
    }
    if (!res.ok || !payload.ok) {
      const detail = (payload && payload.error) || res.statusText || "open failed";
      window.alert(`外部エディタで開けませんでした: ${detail}`);
    }
  };

  const openModalWithBody = (innerHtml) => {
    let modal = document.getElementById(MODAL_ID);
    if (!modal) {
      modal = document.createElement("div");
      modal.id = MODAL_ID;
      modal.dataset.open = "1";
      modal.innerHTML =
        `<div class="nl-debug-panel" role="dialog" aria-labelledby="nl-debug-title" aria-modal="true"></div>`;
      modal.addEventListener("click", (e) => {
        if (e.target === modal) {
          closeModal();
          return;
        }
        const btn = e.target.closest("button.nl-debug-open");
        if (!btn) return;
        e.preventDefault();
        const enc = btn.getAttribute("data-native-path");
        if (!enc) return;
        let path;
        try {
          path = decodeURIComponent(enc);
        } catch (_) {
          return;
        }
        void openNativeLogPathInEditor(path);
      });
      document.body.appendChild(modal);
    }
    const panel = modal.querySelector(".nl-debug-panel");
    panel.innerHTML =
        `<div class="nl-debug-header">` +
        `<button type="button" class="nl-debug-close" aria-label="閉じる">×</button>` +
        `<h2 id="nl-debug-title">Native Log Watcher (kqueue)</h2>` +
        `</div>` +
        `<div class="nl-debug-content">` +
        innerHtml +
        `</div>`;    panel.querySelector(".nl-debug-close").addEventListener("click", closeModal);
    modal.dataset.open = "1";
  };

  const fmtBytes = (n) => {
    if (n == null) return null;
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(2)} MB`;
  };

  const formatPayload = (data) => {
    const agents = Array.isArray(data.agents) ? data.agents : [];
    if (!agents.length) {
      return `<pre class="nl-debug-path">(No active agents)</pre>`;
    }
    const rows = agents.map((row) => {
      const a = esc(row.agent ?? "");
      const raw = String(row.watched_path ?? "").trim();
      const openable =
        raw &&
        !raw.startsWith("(") &&
        (raw.startsWith("/") || raw.startsWith("~")) &&
        !raw.includes("\n");

      const offset = row.offset != null ? row.offset : null;
      const size = row.file_size != null ? row.file_size : null;
      const metaParts = [];
      if (offset != null) metaParts.push(`read ${fmtBytes(offset)}`);
      if (size != null) metaParts.push(`total ${fmtBytes(size)}`);
      const meta = metaParts.length
        ? `<div class="nl-debug-meta">${esc(metaParts.join(" / "))}</div>`
        : "";

      if (!openable) {
        const p = esc(raw || "—");
        return `<div class="nl-debug-row"><div class="nl-debug-agent">${a}</div><div class="nl-debug-path">${p}</div>${meta}</div>`;
      }
      const enc = encodeURIComponent(raw);
      const label = esc(raw);
      return (
        `<div class="nl-debug-row">` +
        `<div class="nl-debug-agent">${a}</div>` +
        `<button type="button" class="nl-debug-path nl-debug-open" data-native-path="${enc}" title="Open in external editor">${label}</button>` +
        meta +
        `</div>`
      );
    });
    return `<div class="nl-debug-rows">${rows.join("")}</div>`;
  };

  const showNativeLogSyncDebug = async () => {
    injectStyles();
    openModalWithBody(`<p class="nl-debug-description">Loading…</p>`);
    const url = typeof withChatBase === "function" ? withChatBase("/debug/native-log-sync") : "/debug/native-log-sync";
    try {
      const res = await fetch(url, { cache: "no-store", credentials: "same-origin" });
      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (_) {
        openModalWithBody(`<pre>${esc(text.slice(0, 4000))}</pre>`);
        return;
      }
      if (!data.ok && data.error) {
        openModalWithBody(`<pre>${esc(JSON.stringify(data, null, 2))}</pre>`);
        return;
      }
      openModalWithBody(formatPayload(data));
    } catch (err) {
      openModalWithBody(`<pre>${esc(err && err.message ? err.message : String(err))}</pre>`);
    }
  };

  injectStyles();
  const fab = document.createElement("button");
  fab.id = FAB_ID;
  fab.type = "button";
  fab.title = "デバッグ: 同期中の native log パス";
  fab.setAttribute("aria-label", "デバッグ: 同期中の native log パス");
  fab.appendChild(document.createTextNode("i"));
  fab.addEventListener("click", () => {
    void showNativeLogSyncDebug();
  });
  document.body.appendChild(fab);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });
})();
