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
  padding: 24px 12px;
  box-sizing: border-box;
  background: transparent;
  opacity: 0;
  pointer-events: none;
  transition: opacity 240ms ease, backdrop-filter 320ms ease, -webkit-backdrop-filter 320ms ease;
}
#${MODAL_ID}::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(
    125% 100% at 50% 50%,
    rgba(0, 0, 0, 0.90) 0%,
    rgba(0, 0, 0, 0.80) 38%,
    rgba(0, 0, 0, 0.58) 72%,
    rgba(0, 0, 0, 0.28) 100%
  );
}
#${MODAL_ID}[data-open="1"] {
  display: flex;
  opacity: 1;
  pointer-events: auto;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}
html[data-mobile="1"] #${MODAL_ID}[data-open="1"] {
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
html[data-mobile="1"] #${MODAL_ID}::before {
  background: rgba(0, 0, 0, 0.16);
}

#${MODAL_ID} .nl-debug-panel {
  position: relative;
  z-index: 1;
  width: min(680px, calc(100vw - 24px));
  max-width: 680px;
  max-height: min(80vh, 560px);
  overflow: visible;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
  padding: 0;
  margin: 0;
  isolation: isolate;
  background: transparent;
  color: var(--text, #fcfcfc);
  border: none;
  box-shadow: none;
  opacity: 1;
  filter: blur(0);
  transform: translateY(0) scale(1);
  animation: nlDebugPanelIn 620ms cubic-bezier(0.18, 0.9, 0.22, 1);
}
#${MODAL_ID} .nl-debug-panel::before {
  content: "";
  position: absolute;
  inset: 1px 8px;
  border-radius: 14px;
  background: radial-gradient(circle at 50% 18%, rgba(255,255,255,0.11) 0%, rgba(255,255,255,0.045) 34%, rgba(255,255,255,0.012) 58%, rgba(255,255,255,0) 76%);
  filter: blur(18px);
  opacity: 0.82;
  pointer-events: none;
  z-index: -1;
}
@keyframes nlDebugPanelIn {
  from {
    opacity: 0;
    filter: blur(18px);
    transform: translateY(42px) scale(0.952);
  }
  to {
    opacity: 1;
    filter: blur(0);
    transform: translateY(0) scale(1);
  }
}

#${MODAL_ID} .nl-debug-header {
  display: flex;
  align-items: center;
  padding: 4px 2px 10px;
  border: none;
  box-sizing: border-box;
  min-height: 32px;
}

#${MODAL_ID} .nl-debug-panel h2 {
  flex: 1;
  order: 0;
  margin: 0;
  padding-left: 32px;
  color: var(--text, #fcfcfc);
  font: 500 12px/1.2 "SF Pro Text", system-ui, sans-serif;
  letter-spacing: 0.02em;
  text-align: center;
}

#${MODAL_ID} .nl-debug-content {
  min-height: 54px;
  max-height: min(64vh, 480px);
  padding: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
  border-radius: 14px;
  border: 0.5px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.05);
  transition: border-color 150ms ease, box-shadow 150ms ease, background 150ms ease;
}
#${MODAL_ID} .nl-debug-content:focus-within {
  background: rgba(255, 255, 255, 0.09);
  border-color: rgba(255, 255, 255, 0.20);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.45), 0 0 0 2px rgba(255, 255, 255, 0.07), inset 0 1px 1px rgba(255, 255, 255, 0.07);
}

#${MODAL_ID} .nl-debug-body {
  min-height: 0;
  overflow-y: auto;
}

#${MODAL_ID} .nl-debug-body::-webkit-scrollbar {
  width: 14px;
}
#${MODAL_ID} .nl-debug-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border: 4px solid transparent;
  background-clip: padding-box;
  border-radius: 999px;
}

#${MODAL_ID} .nl-debug-description {
  margin: 6px 4px;
  font-family: "SF Pro Text", system-ui, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  color: var(--chrome-muted, var(--muted, #9e9e9e));
}

#${MODAL_ID} .nl-debug-content pre {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--text, #fcfcfc);
  font: 400 12px/1.45 var(--code-font-family, monospace);
}

#${MODAL_ID} .nl-debug-rows {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

#${MODAL_ID} .nl-debug-row {
  display: grid;
  grid-template-columns: minmax(58px, max-content) minmax(0, 1fr);
  column-gap: 10px;
  row-gap: 3px;
  align-items: start;
  min-width: 0;
  padding: 8px 6px;
  border-radius: 10px;
  box-sizing: border-box;
}

#${MODAL_ID} .nl-debug-agent {
  min-width: 0;
  color: var(--text, #fcfcfc);
  font: 500 11px/1.35 "SF Pro Text", system-ui, sans-serif;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

#${MODAL_ID} .nl-debug-path {
  font-family: var(--code-font-family, monospace);
  font-size: 12px;
  line-height: 1.45;
  word-break: break-all;
  white-space: pre-wrap;
  color: var(--text, #fcfcfc);
  opacity: 1;
  min-width: 0;
}

#${MODAL_ID} .nl-debug-meta {
  grid-column: 2;
  font-family: var(--code-font-family, monospace);
  font-size: 11px;
  line-height: 1.35;
  color: var(--chrome-muted, var(--muted, #9e9e9e));
  margin-top: 0;
}

#${MODAL_ID} button.nl-debug-path.nl-debug-open {
  display: inline-block;
  justify-self: start;
  width: fit-content;
  max-width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  color: var(--inline-file-link-fg, #58a6ff);
  text-decoration: none;
  transition: opacity 140ms ease;
}
.has-hover #${MODAL_ID} button.nl-debug-path.nl-debug-open:hover {
  opacity: 0.86;
  text-decoration: underline;
}

#${MODAL_ID} .nl-debug-close {
  order: 1;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text, #fcfcfc);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  line-height: 1;
  transition: background 150ms ease, color 150ms ease, transform 120ms ease;
}
.has-hover #${MODAL_ID} .nl-debug-close:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text, #fcfcfc);
}
#${MODAL_ID} .nl-debug-close:active {
  transform: scale(0.93);
}
html[data-mobile="1"] #${MODAL_ID} {
  padding: 24px 12px calc(24px + env(safe-area-inset-bottom, 0px));
}
html[data-mobile="1"] #${MODAL_ID} .nl-debug-panel {
  width: min(900px, calc(100vw - 24px));
  max-width: 900px;
  max-height: min(82vh, 560px);
}
html[data-mobile="1"] #${MODAL_ID} .nl-debug-panel::before {
  inset: 6px 8px 8px;
  border-radius: 30px;
}
html[data-mobile="1"] #${MODAL_ID} .nl-debug-content {
  border-radius: 22px;
}
html[data-mobile="1"] #${MODAL_ID} .nl-debug-row {
  grid-template-columns: minmax(0, 1fr);
  gap: 3px;
  padding: 9px 8px;
}
html[data-mobile="1"] #${MODAL_ID} .nl-debug-meta {
  grid-column: 1;
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
        `<div class="nl-debug-content">` +
        `<div class="nl-debug-header">` +
        `<button type="button" class="nl-debug-close" aria-label="閉じる">×</button>` +
        `<h2 id="nl-debug-title">Native Log Watcher (kqueue)</h2>` +
        `</div>` +
        `<div class="nl-debug-body">` +
        innerHtml +
        `</div>` +
        `</div>`;
    panel.querySelector(".nl-debug-close").addEventListener("click", closeModal);
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
