// Multiagent Chat Desktop App -- native glass support.
(function() {
  const cssText = `
    html[data-tauri-app="1"] {
      --pane-trace-body-bg: rgb(12, 12, 12);
      --tauri-drag-height: 36px;
      --tauri-window-inset-top: 31px;
      --tauri-window-inset-x: 8px;
      --tauri-window-inset-bottom: 8px;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] {
      --app-shell-height: calc(100dvh - var(--tauri-window-inset-top) - var(--tauri-window-inset-bottom));
    }
    html[data-tauri-app="1"][data-tauri-root-window="0"] {
      --app-shell-height: 100dvh;
    }

    html[data-tauri-app="1"] .shell > .hub-page-header {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      background: transparent;
      border-bottom: none;
      box-shadow: none;
    }

    html[data-tauri-app="1"] .tauri-top-drag-strip,
    html[data-tauri-app="1"] [data-tauri-drag-region],
    html[data-tauri-app="1"] .hub-page-header,
    html[data-tauri-app="1"] .hub-page-header-top {
      app-region: drag;
      -webkit-app-region: drag;
    }

    html[data-tauri-app="1"] .tauri-top-drag-strip {
      position: fixed;
      top: 0;
      left: 0;
      right: calc(var(--page-side-pad, 14px) + var(--chrome-icon-btn-size, 28px) + 12px);
      height: var(--tauri-drag-height);
      z-index: 1205;
      background: transparent;
      pointer-events: auto;
    }

    html[data-tauri-app="1"] .shell > .hub-page-header > .hub-page-header-top {
      min-height: var(--tauri-drag-height);
    }

    html[data-tauri-app="1"] button,
    html[data-tauri-app="1"] a,
    html[data-tauri-app="1"] input,
    html[data-tauri-app="1"] select,
    html[data-tauri-app="1"] textarea,
    html[data-tauri-app="1"] [role="button"],
    html[data-tauri-app="1"] .desk-sidebar-resizer,
    html[data-tauri-app="1"] .hub-page-header-actions,
    html[data-tauri-app="1"] .hub-page-menu-panel {
      app-region: no-drag;
      -webkit-app-region: no-drag;
    }

    html[data-tauri-app="1"],
    html[data-tauri-app="1"] body {
      background: transparent !important;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] body {
      margin: 0;
      padding: var(--tauri-window-inset-top) var(--tauri-window-inset-x) var(--tauri-window-inset-bottom);
      box-sizing: border-box;
      min-height: 100dvh;
      overflow: hidden;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .shell,
    html[data-tauri-app="1"][data-tauri-root-window="1"] body > .shell {
      background: transparent;
      border: none;
      border-radius: 26px;
      overflow: hidden;
      min-height: var(--app-shell-height);
      max-height: var(--app-shell-height);
      box-shadow: none;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .hub-page-header .hub-page-header-actions,
    html[data-tauri-app="1"][data-tauri-root-window="1"] .hub-page-header-actions.hub-page-header-actions-floating {
      position: fixed !important;
      top: calc(4px + env(safe-area-inset-top, 0px)) !important;
      right: calc(6px + env(safe-area-inset-right, 0px)) !important;
      width: 24px !important;
      height: 24px !important;
      margin: 0 !important;
      padding: 0 !important;
      gap: 0 !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      z-index: 1306 !important;
      pointer-events: auto;
      line-height: 0;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .hub-page-header .hub-page-header-actions .hub-page-menu-btn,
    html[data-tauri-app="1"][data-tauri-root-window="1"] .hub-page-header-actions.hub-page-header-actions-floating .hub-page-menu-btn {
      width: 24px !important;
      height: 24px !important;
      margin: 0 !important;
      padding: 0 !important;
      color: #fff !important;
      opacity: 1 !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .hub-page-header .hub-page-header-actions .hub-page-menu-btn svg,
    html[data-tauri-app="1"][data-tauri-root-window="1"] .hub-page-header-actions.hub-page-header-actions-floating .hub-page-menu-btn svg {
      width: 15px !important;
      height: 15px !important;
      margin: 0 auto !important;
      transform: none !important;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .desk-app-sidebar-toggle {
      top: calc(4px + env(safe-area-inset-top, 0px)) !important;
      left: calc(74px + env(safe-area-inset-left, 0px)) !important;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .desk-chat-menu-btn {
      top: calc(4px + env(safe-area-inset-top, 0px)) !important;
      right: calc(6px + env(safe-area-inset-right, 0px)) !important;
      color: #fff !important;
      opacity: 1 !important;
      z-index: 1306 !important;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .hub-page-header-actions.hub-page-header-actions-floating {
      top: calc(4px + env(safe-area-inset-top, 0px)) !important;
      right: calc(6px + env(safe-area-inset-right, 0px)) !important;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .desk-floating-controls {
      left: calc(102px + env(safe-area-inset-left, 0px)) !important;
      top: calc(4px + env(safe-area-inset-top, 0px)) !important;
      right: auto !important;
      bottom: auto !important;
      gap: 4px !important;
      z-index: 1306 !important;
    }
    html[data-tauri-app="1"][data-tauri-root-window="1"] .desk-floating-controls .desk-settings-icon-btn {
      color: #fff !important;
      opacity: 1 !important;
    }
    html[data-tauri-app="1"][data-tauri-root-window="0"] .hub-page-header-actions.hub-page-header-actions-floating {
      display: none !important;
    }
    html[data-tauri-app="1"] .tauri-top-drag-strip {
      top: 0;
    }

    html[data-tauri-app="1"] .desk-workbench,
    html[data-tauri-app="1"] .desk-main,
    html[data-tauri-app="1"] .desk-chat-shell {
      background: transparent;
    }
    html[data-tauri-app="1"] main#messages,
    html[data-tauri-app="1"] #messages {
      background: var(--bg);
    }
  `;
  const DRAG_REGION_SELECTOR = ".tauri-top-drag-strip, [data-tauri-drag-region], .hub-page-header, .hub-page-header-top";
  const NO_DRAG_SELECTOR = [
    "button",
    "a",
    "input",
    "select",
    "textarea",
    "[role=\"button\"]",
    ".hub-page-header-actions",
    ".hub-page-menu-panel",
    ".hub-page-menu-btn",
    "#hubPageNativeMenuBridge",
    ".desk-sidebar-resizer",
  ].join(", ");

  function ensureTopDragStrip(doc) {
    if (!doc || !doc.documentElement || !doc.body) return;
    let hasHeader = false;
    try {
      hasHeader = !!doc.querySelector(".hub-page-header");
    } catch (_) {}
    if (!hasHeader) return;
    try {
      let strip = doc.getElementById("__ma-top-drag-strip");
      if (!strip) {
        strip = doc.createElement("div");
        strip.id = "__ma-top-drag-strip";
        strip.className = "tauri-top-drag-strip";
        strip.setAttribute("data-tauri-drag-region", "");
        doc.body.appendChild(strip);
      } else if (strip.parentElement !== doc.body) {
        doc.body.appendChild(strip);
      }
    } catch (_) {}
  }

  function markDragRegions(doc) {
    if (!doc || !doc.documentElement) return;
    try {
      doc
        .querySelectorAll(".hub-page-header, .hub-page-header-top")
        .forEach((node) => node.setAttribute("data-tauri-drag-region", ""));
    } catch (_) {}
  }

  function isNoDragTarget(target) {
    return !!(target && typeof target.closest === "function" && target.closest(NO_DRAG_SELECTOR));
  }

  async function startWindowDrag(view) {
    const candidates = [];
    if (view) candidates.push(view);
    try {
      if (view?.parent && view.parent !== view) candidates.push(view.parent);
    } catch (_) {}
    for (const candidate of candidates) {
      const tauri = candidate?.__TAURI__;
      const invoke = tauri?.core?.invoke || tauri?.invoke || candidate?.__TAURI_INTERNALS__?.invoke;
      const label = candidate?.__TAURI_INTERNALS?.metadata?.currentWindow?.label || "main";
      if (typeof invoke === "function") {
        try {
          await invoke("plugin:window|start_dragging", { label });
          return true;
        } catch (_) {}
      }
      if (!tauri) continue;
      try {
        const getCurrentWindow = tauri.window?.getCurrentWindow;
        if (typeof getCurrentWindow === "function") {
          const currentWindow = getCurrentWindow();
          if (currentWindow && typeof currentWindow.startDragging === "function") {
            await currentWindow.startDragging();
            return true;
          }
        }
      } catch (_) {}
      try {
        const appWindow = tauri.window?.appWindow;
        if (appWindow && typeof appWindow.startDragging === "function") {
          await appWindow.startDragging();
          return true;
        }
      } catch (_) {}
    }
    return false;
  }

  function installDragHandler(doc) {
    if (!doc || !doc.documentElement || doc.__multiagentDragHandlerInstalled) return;
    doc.__multiagentDragHandlerInstalled = true;
    doc.addEventListener("mousedown", (event) => {
      if (event.button !== 0 || event.defaultPrevented) return;
      const target = event.target;
      if (!target || isNoDragTarget(target)) return;
      const inDragRegion = !!(typeof target.closest === "function" && target.closest(DRAG_REGION_SELECTOR));
      if (!inDragRegion) return;
      void startWindowDrag(doc.defaultView);
    }, { capture: true });
  }

  function applyCssToDocument(doc) {
    if (!doc || !doc.documentElement) return false;
    let isRootWindow = true;
    try {
      const view = doc.defaultView;
      isRootWindow = !!(view && view.top === view);
    } catch (_) {
      isRootWindow = true;
    }
    try {
      doc.documentElement.dataset.tauriApp = "1";
      doc.documentElement.dataset.tauriRootWindow = isRootWindow ? "1" : "0";
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
      ensureTopDragStrip(doc);
      markDragRegions(doc);
      installDragHandler(doc);
    };
    if (doc.head) install();
    else doc.addEventListener("DOMContentLoaded", install, { once: true });
    if (doc.readyState === "loading") {
      doc.addEventListener("DOMContentLoaded", () => {
        ensureTopDragStrip(doc);
        markDragRegions(doc);
        installDragHandler(doc);
      }, { once: true });
    } else {
      ensureTopDragStrip(doc);
      markDragRegions(doc);
      installDragHandler(doc);
    }
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
