// Multiagent Chat Desktop App -- native glass support.
(function() {
  const cssText = `
    html[data-tauri-app="1"] {
      --bg: rgb(10, 10, 10);
      --pane-trace-body-bg: rgb(12, 12, 12);
    }

    html[data-tauri-app="1"],
    html[data-tauri-app="1"] body,
    html[data-tauri-app="1"] .shell,
    html[data-tauri-app="1"] body > .shell,
    html[data-tauri-app="1"] .desk-workbench,
    html[data-tauri-app="1"] .desk-main,
    html[data-tauri-app="1"] .desk-chat-shell,
    html[data-tauri-app="1"] .desk-chat-frame,
    html[data-tauri-app="1"] main#messages,
    html[data-tauri-app="1"] #messages {
      background: var(--bg);
    }
  `;

  function applyCssToDocument(doc) {
    if (!doc || !doc.documentElement) return false;
    try {
      doc.documentElement.dataset.tauriApp = "1";
      doc.defaultView?.sessionStorage?.setItem("multiagent_tauri_app", "1");
      doc.defaultView.__multiagentIsTauriApp = true;
      doc.defaultView.__multiagentAppSettingsLoaded = true;
    } catch (_) {}
    const install = () => {
      try {
        let style = doc.getElementById("__ma-app-native-glass");
        if (!style) {
          style = doc.createElement("style");
          style.id = "__ma-app-native-glass";
          style = doc.head.appendChild(style);
        } else if (style.parentElement === doc.head) {
          doc.head.appendChild(style);
        }
        if (style.textContent !== cssText) style.textContent = cssText;
      } catch (_) {}
    };
    if (doc.head) install();
    else doc.addEventListener("DOMContentLoaded", install, { once: true });
    return true;
  }

  function applyToIframes(rootDoc = document, depth = 0) {
    if (!rootDoc || depth > 4) return;
    let frames = [];
    try {
      frames = Array.from(rootDoc.querySelectorAll("iframe"));
    } catch (_) {
      return;
    }
    frames.forEach((iframe) => {
      try {
        const childDoc = iframe.contentDocument || iframe.contentWindow?.document;
        if (!childDoc) return;
        applyCssToDocument(childDoc);
        applyToIframes(childDoc, depth + 1);
      } catch (_) {}
    });
  }

  applyCssToDocument(document);
  applyToIframes(document);
})();
