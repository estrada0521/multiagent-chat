// Multiagent Chat Desktop App -- fixed opaque app chrome.
(function() {
  document.documentElement.dataset.tauriApp = "1";
  try { sessionStorage.setItem("multiagent_tauri_app", "1"); } catch (_) {}
  try { localStorage.removeItem("multiagent_app_vibrancy"); } catch (_) {}
  window.__multiagentIsTauriApp = true;
  window.__multiagentAppSettingsLoaded = true;

  const cssText = `
    :root {
      --bg-rgb: 10, 10, 10;
      --bg: rgb(10, 10, 10) !important;
      --panel: rgba(20, 20, 20, 0.98) !important;
      --panel-2: rgb(25, 25, 25) !important;
      --panel-strong: rgb(10, 10, 10) !important;
      --surface: rgb(20, 20, 19) !important;
      --surface-alt: rgb(25, 25, 24) !important;
      --bg-hover: rgb(30, 30, 29) !important;
      --pane-trace-body-bg: rgb(10, 10, 10) !important;
    }

    html,
    body,
    body > .shell,
    .desk-workbench,
    .desk-main,
    .desk-chat-shell,
    .desk-chat-frame,
    main#messages,
    #messages,
    .file-modal,
    .file-modal-dialog,
    .file-modal-body,
    .file-modal-frame,
    body.file-modal-desktop-split .file-modal-dialog {
      background: rgb(10, 10, 10) !important;
    }

    .desk-sidebar-shell,
    .desk-inline-panel,
    .desk-context-menu,
    .hub-page-header,
    .hub-header-chrome,
    .hub-page-menu-panel,
    #hubPageMenuPanel.open.hub-menu-mode-pane,
    #attachedFilesPanel.open,
    #gitBranchPanel.open,
    .chat-header,
    .composer,
    .composer-main-shell,
    .composer-plus-panel,
    .plus-submenu-panel,
    .pane-viewer-tabs,
    .pane-viewer-slide,
    .pane-viewer-body,
    .add-agent-panel,
    .sync-status-panel,
    .attach-rename-panel,
    .provider-events-panel,
    .settings-page,
    .settings-shell,
    .new-session-page,
    .camera-mode-shell {
      background: rgb(10, 10, 10) !important;
    }

    .file-modal-header::before {
      background: linear-gradient(180deg, rgba(10, 10, 10, 0.92) 0%, rgba(10, 10, 10, 0.5) 52%, rgba(10, 10, 10, 0) 100%) !important;
    }
  `;

  function removeOldControls(doc) {
    try {
      doc.getElementById("__ma-gear")?.remove();
      doc.getElementById("__ma-panel")?.remove();
      doc.getElementById("__ma-vibrancy")?.remove();
      doc.getElementById("__ma-vibrancy-iframe")?.remove();
    } catch (_) {}
  }

  function applyCssToDocument(doc) {
    if (!doc || !doc.documentElement) return false;
    try {
      doc.documentElement.dataset.tauriApp = "1";
      doc.defaultView?.sessionStorage?.setItem("multiagent_tauri_app", "1");
      doc.defaultView.__multiagentIsTauriApp = true;
      doc.defaultView.__multiagentAppSettingsLoaded = true;
    } catch (_) {}
    removeOldControls(doc);
    try {
      let style = doc.getElementById("__ma-app-fixed-opaque");
      if (!style) {
        style = doc.createElement("style");
        style.id = "__ma-app-fixed-opaque";
        if (doc.head) style = doc.head.appendChild(style);
        else return false;
      }
      if (style.textContent !== cssText) style.textContent = cssText;
      return true;
    } catch (_) {
      return false;
    }
  }

  function refreshTauriIframes(rootDoc = document, depth = 0) {
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
        const ready = childDoc.readyState === "complete" || childDoc.readyState === "interactive";
        if (ready) {
          applyCssToDocument(childDoc);
          refreshTauriIframes(childDoc, depth + 1);
        }
      } catch (_) {}
    });
  }

  applyCssToDocument(document);
  try {
    if (typeof window.__multiagentRefreshTauriFrames === "function") {
      window.__multiagentRefreshTauriFrames();
    }
  } catch (_) {}

  setInterval(() => {
    applyCssToDocument(document);
    refreshTauriIframes();
  }, 1000);
})();
