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
  bottom: calc(12px + env(safe-area-inset-bottom, 0px));
  right: calc(12px + env(safe-area-inset-right, 0px));
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid rgba(120,120,130,0.35);
  background: rgba(55,55,62,0.92);
  color: #e8e8ee;
  font: 600 16px/1 system-ui, sans-serif;
  cursor: pointer;
  z-index: 9998;
  box-shadow: 0 2px 10px rgba(0,0,0,0.25);
  padding: 0;
}
#${FAB_ID}:hover { filter: brightness(1.08); }
#${FAB_ID}:focus-visible { outline: 2px solid rgba(120,160,255,0.9); outline-offset: 2px; }
#${MODAL_ID} {
  position: fixed;
  inset: 0;
  z-index: 10050;
  display: none;
  align-items: center;
  justify-content: center;
  padding: 16px;
  box-sizing: border-box;
  background: rgba(0,0,0,0.45);
}
#${MODAL_ID}[data-open="1"] { display: flex; }
#${MODAL_ID} .nl-debug-panel {
  max-width: min(560px, 100%);
  max-height: min(80vh, 640px);
  overflow: auto;
  background: var(--nl-debug-bg, #1a1a1f);
  color: var(--nl-debug-fg, #e8e8ee);
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.12);
  padding: 14px 16px;
  font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  box-shadow: 0 12px 40px rgba(0,0,0,0.35);
}
#${MODAL_ID} .nl-debug-panel h2 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  font-family: system-ui, sans-serif;
}
#${MODAL_ID} .nl-debug-panel pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
#${MODAL_ID} .nl-debug-close {
  float: right;
  margin: -4px -4px 8px 8px;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  opacity: 0.75;
}
#${MODAL_ID} .nl-debug-close:hover { opacity: 1; }
`;
        document.head.appendChild(style);
    };

    const closeModal = () => {
        const modal = document.getElementById(MODAL_ID);
        if (modal) modal.dataset.open = "0";
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
                if (e.target === modal) closeModal();
            });
            document.body.appendChild(modal);
        }
        const panel = modal.querySelector(".nl-debug-panel");
        panel.innerHTML =
            `<button type="button" class="nl-debug-close" aria-label="閉じる">×</button>` +
            `<h2 id="nl-debug-title">解決済み native log パス（デバッグ）</h2>` +
            innerHtml;
        panel.querySelector(".nl-debug-close").addEventListener("click", closeModal);
        modal.dataset.open = "1";
    };

    const formatPayload = (data) => {
        const agents = Array.isArray(data.agents) ? data.agents : [];
        if (!agents.length) {
            return `<pre>(エージェントなし)</pre>`;
        }
        const lines = agents.map((row) => {
            const a = esc(row.agent ?? "");
            const p = esc(row.path ?? "");
            return `${a}\n  ${p}`;
        });
        return `<pre>${lines.join("\n\n")}</pre>`;
    };

    const showNativeLogSyncDebug = async () => {
        injectStyles();
        openModalWithBody(`<p style="margin:0 0 10px;font-family:system-ui,sans-serif;opacity:0.85">読み込み中…</p>`);
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
