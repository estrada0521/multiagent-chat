    function markTauriDesktopApp() {
      document.documentElement.dataset.tauriApp = "1";
      try { sessionStorage.setItem("multiagent_tauri_app", "1"); } catch (_) {}
      window.__multiagentIsTauriApp = true;
      return true;
    }
    function isTauriDesktopApp() {
      if (document.documentElement.dataset.tauriApp === "1" || window.__multiagentIsTauriApp) return true;
      try {
        const params = new URLSearchParams(window.location.search || "");
        if (params.get("tauri") === "1" || sessionStorage.getItem("multiagent_tauri_app") === "1") {
          return markTauriDesktopApp();
        }
      } catch (_) {}
      try {
        if (
          typeof window.__TAURI__ !== "undefined" ||
          typeof window.__TAURI_INTERNALS__ !== "undefined" ||
          window.__multiagentAppSettingsLoaded
        ) {
          return markTauriDesktopApp();
        }
      } catch (_) {}
      return false;
    }
    isTauriDesktopApp();
    const PHONE_VIEWPORT_MAX_PX = 480;
    const _deskWorkbench = document.getElementById("deskWorkbench");
    const _deskSidebar = document.getElementById("deskSidebar");
    const _deskSidebarResizer = document.getElementById("deskSidebarResizer");
    const _deskAppSidebarToggle = document.getElementById("deskAppSidebarToggle");
    const _deskSessionList = document.getElementById("deskSessionList");
    const _deskChatFrame = document.getElementById("deskChatFrame");
    const _deskChatMenuBtn = document.getElementById("deskChatMenuBtn");
    const _deskPanelToggle = document.getElementById("deskPanelToggle");
    const _deskChatShell = document.querySelector(".desk-chat-shell");
    const _deskReloadShell = document.getElementById("deskReloadShell");
    const _deskMain = document.querySelector(".desk-main");
    const _deskSidebarSessions = document.getElementById("deskSidebarSessions");
    const _deskSidebarPane = document.getElementById("deskSidebarPane");
    const _deskSidebarFrame = document.getElementById("deskSidebarFrame");
    const _deskSidebarPaneTitle = document.getElementById("deskSidebarPaneTitle");
    const _deskSettingsBtn = document.getElementById("deskSettingsBtn");
    const _deskReloadBtn = document.getElementById("deskReloadBtn");
    const _deskNewSessionToggle = document.getElementById("deskNewSessionToggle");
    const DESK_SELECTED_KEY = "multiagent_hub_selected_session";
    const DESK_SIDEBAR_WIDTH_KEY = "multiagent_hub_sidebar_width";
    const HUB_PENDING_ERROR_KEY = "multiagent_hub_pending_error";
    const DESK_DEFAULT_SIDEBAR_WIDTH = 304;
    const DESK_MIN_SIDEBAR_WIDTH = 160;
    const DESK_MAX_SIDEBAR_WIDTH = 420;
    const DESK_SWIPE_ACTION_WIDTH = 92;
    const DESK_SWIPE_OPEN_THRESHOLD = 40;
    const DESK_ACTIVE_PREWARM_LIMIT = 3;
    const DESK_ACTIVE_PREWARM_CONCURRENCY = 2;
    const DESK_SIDEBAR_CLOSE_SWIPE_EDGE_PX = 36;
    const DESK_SIDEBAR_CLOSE_SWIPE_THRESHOLD = 54;
    const DESK_CHAT_URL_CACHE_LIMIT = 3;
    const DESK_RUNNING_LIVE_TTL_MS = 15000;
    const DESK_RUNNING_SERVER_TTL_MS = 6500;
    let _deskPanelActiveMode = "";
    let _deskPanelWidth = 0;
    const _phoneViewportQuery = window.matchMedia(`(max-width: ${PHONE_VIEWPORT_MAX_PX}px)`);
    const esc = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
    const cssEsc = (value) => {
      const normalized = String(value || "");
      try {
        return window.CSS && typeof window.CSS.escape === "function"
          ? window.CSS.escape(normalized)
          : normalized.replace(/["\\]/g, "\\$&");
      } catch (_) {
        return normalized.replace(/["\\]/g, "\\$&");
      }
    };

    window.addEventListener("multiagent-native-menu-action", (event) => {
      try {
        _deskChatFrame?.contentWindow?.postMessage({
          type: "multiagent-native-menu-action",
          payload: event.detail || {},
        }, "*");
      } catch (_) {}
    });

    let _hubSessionsCache = { active: [], archived: [] };
    let _deskSessionsRequestSeq = 0;
    let _deskSessionsRenderedOnce = false;
    let _deskSessionsColdFailures = 0;
    let _deskSelectedSessionName = "";
    let _deskOpenToken = 0;
    let _deskSidebarMode = "list";
    let _deskSidebarWidth = DESK_DEFAULT_SIDEBAR_WIDTH;
    let _deskChatUrlCache = new Map();
    let _deskChatUrlInflight = new Map();
    let _deskActivePrewarmToken = 0;
    let _deskOpenSwipeRow = null;
    let _deskNewSessionStarting = false;
    let _deskBoldModeState = document.documentElement.dataset.boldMode === "1";
    const _deskSessionRunningState = new Map();

    function applyDeskBoldMode(enabled) {
      if (enabled) {
        document.documentElement.dataset.boldMode = "1";
        return;
      }
      delete document.documentElement.dataset.boldMode;
    }

    function syncDeskBoldModeFromSessionsPayload(payload) {
      const next = !!payload?.bold_mode_desktop;
      if (next === _deskBoldModeState) return;
      _deskBoldModeState = next;
      applyDeskBoldMode(next);
    }
    function pruneDeskSessionRunningState(now = Date.now()) {
      _deskSessionRunningState.forEach((entry, name) => {
        const ttl = entry?.source === "live" ? DESK_RUNNING_LIVE_TTL_MS : DESK_RUNNING_SERVER_TTL_MS;
        if (!entry || (now - Number(entry.ts || 0)) > ttl) {
          _deskSessionRunningState.delete(name);
        }
      });
    }
    function setDeskSessionRunningState(sessionName, isRunning, source = "server") {
      const normalized = String(sessionName || "").trim();
      if (!normalized) return;
      const now = Date.now();
      if (source === "server") {
        const existing = _deskSessionRunningState.get(normalized);
        if (existing && existing.source === "live" && (now - Number(existing.ts || 0)) <= DESK_RUNNING_LIVE_TTL_MS) {
          return;
        }
      }
      _deskSessionRunningState.set(normalized, { isRunning: !!isRunning, source, ts: now });
      pruneDeskSessionRunningState(now);
    }
    function syncDeskSessionRunningFromServer(activeSessions) {
      (activeSessions || []).forEach((session) => {
        const name = String(session?.name || "").trim();
        if (!name) return;
        setDeskSessionRunningState(name, !!session?.is_running, "server");
      });
    }
    function resolveDeskSessionRunningState(sessionName, fallback) {
      const normalized = String(sessionName || "").trim();
      if (!normalized) return !!fallback;
      pruneDeskSessionRunningState();
      const entry = _deskSessionRunningState.get(normalized);
      if (!entry) return !!fallback;
      return !!entry.isRunning;
    }
    function refreshDeskSessionRunningRow(sessionName) {
      if (!_deskSessionList) return;
      const normalized = String(sessionName || "").trim();
      if (!normalized) return;
      const row = _deskSessionList.querySelector(`.desk-session-row[data-session-name="${cssEsc(normalized)}"]`);
      if (!row || row.classList.contains("archived")) return;
      const bullet = row.querySelector(".desk-row-bullet");
      if (!bullet) return;
      bullet.classList.toggle("is-running", resolveDeskSessionRunningState(normalized, bullet.classList.contains("is-running")));
    }
    function updateDeskPanelButtonState(mode = "", width = _deskPanelWidth) {
      _deskPanelActiveMode = mode ? "open" : "";
      _deskPanelWidth = Math.max(0, Number(width) || 0);
      if (_deskPanelToggle) {
        _deskPanelToggle.classList.toggle("active", !!_deskPanelActiveMode);
        _deskPanelToggle.setAttribute("aria-pressed", _deskPanelActiveMode ? "true" : "false");
      }
    }
    function setDeskChatLoading(active) {
      if (!_deskChatShell) return;
      _deskChatShell.classList.toggle("loading", !!active);
    }
    function setDeskReloadShell(active) {
      if (!_deskReloadShell) return;
      _deskReloadShell.hidden = !active;
      _deskReloadShell.classList.toggle("visible", !!active);
    }

    function openDeskChatHeaderMenu() {
      const frameWin = _deskChatFrame?.contentWindow;
      if (!frameWin) return;
      const frameRect = _deskChatFrame?.getBoundingClientRect?.() || { left: 0, top: 0 };
      const btnRect = _deskChatMenuBtn?.getBoundingClientRect?.() || null;
      const anchor = btnRect
        ? {
            left: Number(btnRect.left || 0) - Number(frameRect.left || 0),
            top: Number(btnRect.top || 0) - Number(frameRect.top || 0),
            right: Number(btnRect.right || 0) - Number(frameRect.left || 0),
            bottom: Number(btnRect.bottom || 0) - Number(frameRect.top || 0),
            width: Number(btnRect.width || 24),
            height: Number(btnRect.height || 24),
          }
        : null;
      frameWin.postMessage({ type: "multiagent-open-chat-header-menu", anchor }, "*");
    }
    function sendDeskPanelCommand(mode) {
      const frameWin = _deskChatFrame?.contentWindow;
      if (!frameWin) return;
      frameWin.postMessage({ type: "multiagent-desktop-panel", mode: String(mode || "") }, "*");
    }

    function consumeHubPendingError() {
      let message = "";
      try {
        message = String(sessionStorage.getItem(HUB_PENDING_ERROR_KEY) || "");
        if (message) sessionStorage.removeItem(HUB_PENDING_ERROR_KEY);
      } catch (_) {
        message = "";
      }
      if (!message) return;
      window.setTimeout(() => {
        window.alert(message);
      }, 0);
    }

    function isPhoneViewport() {
      if (isTauriDesktopApp()) return false;
      return !!_phoneViewportQuery.matches;
    }

    function activeTextEntryElement() {
      const active = document.activeElement;
      if (!active) return null;
      const tag = String(active.tagName || "").toUpperCase();
      if (tag === "TEXTAREA") return active;
      if (tag !== "INPUT") return null;
      const type = String(active.getAttribute("type") || active.type || "").toLowerCase();
      if (!type || ["text", "search", "email", "url", "tel", "number", "password"].includes(type)) {
        return active;
      }
      return null;
    }

    function syncAppShellHeight({ force = false } = {}) {
      if (!isPhoneViewport()) {
        document.documentElement.style.removeProperty("--app-shell-height");
        return;
      }
      const vv = window.visualViewport;
      let nextHeight = Math.round(window.innerHeight || 0);
      if (vv && vv.height > 0) {
        nextHeight = Math.round(vv.height + Math.max(0, vv.offsetTop || 0));
      }
      if (nextHeight <= 0) return;
      const prevHeight = parseInt(document.documentElement.style.getPropertyValue("--app-shell-height"), 10) || 0;
      if (!force && activeTextEntryElement() && prevHeight && nextHeight < prevHeight - 120) {
        return;
      }
      document.documentElement.style.setProperty("--app-shell-height", `${nextHeight}px`);
    }

    syncAppShellHeight({ force: true });
    if (typeof _phoneViewportQuery.addEventListener === "function") {
      _phoneViewportQuery.addEventListener("change", () => {
        syncAppShellHeight({ force: true });
        syncDeskSidebarResizerVisibility();
      });
    } else if (typeof _phoneViewportQuery.addListener === "function") {
      _phoneViewportQuery.addListener(() => {
        syncAppShellHeight({ force: true });
        syncDeskSidebarResizerVisibility();
      });
    }
    window.addEventListener("pageshow", () => syncAppShellHeight({ force: true }));
    window.addEventListener("resize", () => syncAppShellHeight());
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", () => syncAppShellHeight());
      window.visualViewport.addEventListener("scroll", () => syncAppShellHeight());
    }

    function clampDeskSidebarWidth(value) {
      return Math.max(DESK_MIN_SIDEBAR_WIDTH, Math.min(DESK_MAX_SIDEBAR_WIDTH, Math.round(Number(value) || DESK_DEFAULT_SIDEBAR_WIDTH)));
    }

    function readDeskSidebarWidth() {
      try {
        return clampDeskSidebarWidth(localStorage.getItem(DESK_SIDEBAR_WIDTH_KEY));
      } catch (_) {
        return DESK_DEFAULT_SIDEBAR_WIDTH;
      }
    }

    function setDeskSidebarWidth(nextWidth, { persist = true } = {}) {
      _deskSidebarWidth = clampDeskSidebarWidth(nextWidth);
      if (_deskWorkbench) {
        _deskWorkbench.style.setProperty("--desk-sidebar-width", `${_deskSidebarWidth}px`);
      }
      if (_deskAppSidebarToggle) {
        _deskAppSidebarToggle.classList.toggle("is-active", isDeskSidebarOpen());
      }
      if (persist) {
        try {
          localStorage.setItem(DESK_SIDEBAR_WIDTH_KEY, String(_deskSidebarWidth));
        } catch (_) {}
      }
    }

    const deskDtHasFiles = (dt) => !!(dt && Array.from(dt.types || []).includes("Files"));
    const isDeskChatFrameDropTarget = (target) => target === _deskChatFrame;
    const postDeskChatFrameMessage = (payload) => {
      try {
        _deskChatFrame?.contentWindow?.postMessage(payload, "*");
        return true;
      } catch (_) {
        return false;
      }
    };
    const setDeskAttachDragActive = (active) => {
      postDeskChatFrameMessage({ type: "multiagent-parent-attach-drag", active: !!active });
    };
    const forwardDeskDroppedFiles = (files) => {
      const dropped = Array.from(files || []).filter((file) => file && typeof file.name === "string");
      if (!dropped.length) return false;
      return postDeskChatFrameMessage({ type: "multiagent-parent-drop-files", files: dropped });
    };
    function sortActiveSessions(active) {
      return [...active];
    }

    function setDeskSelectionInUrl(name) {
      try {
        const next = new URL(window.location.href);
        if (name) next.searchParams.set("session", name);
        else next.searchParams.delete("session");
        history.replaceState(null, "", `${next.pathname}${next.search}${next.hash}`);
      } catch (_) {}
    }

    function persistDeskSelection(name) {
      try {
        if (name) sessionStorage.setItem(DESK_SELECTED_KEY, name);
        else sessionStorage.removeItem(DESK_SELECTED_KEY);
      } catch (_) {}
    }

    function getRequestedDeskSelection() {
      try {
        const queryName = new URL(window.location.href).searchParams.get("session");
        if (queryName) return queryName;
      } catch (_) {}
      try {
        return sessionStorage.getItem(DESK_SELECTED_KEY) || "";
      } catch (_) {
        return "";
      }
    }

    function findSessionRecord(name) {
      const active = (_hubSessionsCache.active || []).find((session) => session.name === name);
      if (active) return { session: active, archived: false };
      const archived = (_hubSessionsCache.archived || []).find((session) => session.name === name);
      if (archived) return { session: archived, archived: true };
      return null;
    }

    function buildSessionOpenHref(sessionName, archived) {
      const base = archived ? "/revive-session" : "/open-session";
      return `${base}?session=${encodeURIComponent(sessionName)}`;
    }

    function normalizeComparableUrl(rawUrl) {
      const value = String(rawUrl || "").trim();
      if (!value) return "";
      try {
        return new URL(value, window.location.href).toString();
      } catch (_) {
        return value;
      }
    }

    function buildDeskChatFrameUrl(chatUrl) {
      const raw = String(chatUrl || "").trim();
      if (!raw) return "";
      const isTauri = isTauriDesktopApp();
      try {
        const parsed = new URL(raw, window.location.href);
        parsed.searchParams.set("hub_shell", "1");
        if (isTauri) parsed.searchParams.set("tauri", "1");
        if (parsed.origin === window.location.origin) {
          return `${parsed.pathname}${parsed.search}${parsed.hash}`;
        }
        return parsed.toString();
      } catch (_) {
        if (/[?&]hub_shell=/.test(raw)) return raw;
        let q = raw + (raw.includes("?") ? "&" : "?") + "hub_shell=1";
        if (isTauri) q += "&tauri=1";
        return q;
      }
    }

    window.__multiagentRefreshTauriFrames = () => {
      if (!isTauriDesktopApp()) return;
      if (!_deskChatFrame) return;
      const current = String(_deskChatFrame.getAttribute("src") || _deskChatFrame.src || "");
      if (!current || current === "about:blank") return;
      const next = buildDeskChatFrameUrl(current);
      if (next && normalizeComparableUrl(current) !== normalizeComparableUrl(next)) {
        _deskChatFrame.src = next;
      }
    };

    function cacheDeskChatUrl(cacheKey, chatUrl) {
      const key = String(cacheKey || "");
      const value = String(chatUrl || "");
      if (!key || !value) return;
      if (_deskChatUrlCache.has(key)) _deskChatUrlCache.delete(key);
      _deskChatUrlCache.set(key, value);
      while (_deskChatUrlCache.size > DESK_CHAT_URL_CACHE_LIMIT) {
        const oldest = _deskChatUrlCache.keys().next();
        if (oldest && !oldest.done) _deskChatUrlCache.delete(oldest.value);
        else break;
      }
    }

    function readCachedDeskChatUrl(cacheKey) {
      const key = String(cacheKey || "");
      if (!key || !_deskChatUrlCache.has(key)) return "";
      const value = _deskChatUrlCache.get(key) || "";
      if (value) cacheDeskChatUrl(key, value);
      return value;
    }

    function prioritizedDeskActiveSessions() {
      const active = sortActiveSessions(_hubSessionsCache.active || []);
      if (!active.length) return [];
      const byName = new Map();
      active.forEach((session) => {
        const sessionName = String(session?.name || "").trim();
        if (sessionName && !byName.has(sessionName)) byName.set(sessionName, session);
      });
      const ordered = [];
      const pushed = new Set();
      const pushSession = (name) => {
        const sessionName = String(name || "").trim();
        if (!sessionName || pushed.has(sessionName)) return;
        const session = byName.get(sessionName);
        if (!session) return;
        pushed.add(sessionName);
        ordered.push(session);
      };
      pushSession(_deskSelectedSessionName);
      pushSession(getRequestedDeskSelection());
      active.forEach((session) => pushSession(session?.name));
      return ordered;
    }

    function scheduleDeskActivePrewarm() {
      const active = prioritizedDeskActiveSessions().slice(0, DESK_ACTIVE_PREWARM_LIMIT);
      if (!active.length) return;
      const queue = active
        .map((session) => buildSessionOpenHref(session.name, false))
        .filter((href) => href && !readCachedDeskChatUrl(href) && !_deskChatUrlInflight.has(href));
      if (!queue.length) return;
      const token = ++_deskActivePrewarmToken;
      let running = 0;
      const pump = () => {
        if (token !== _deskActivePrewarmToken) return;
        while (running < DESK_ACTIVE_PREWARM_CONCURRENCY && queue.length) {
          const href = queue.shift();
          if (!href) continue;
          running += 1;
          resolveSessionChatUrl(href)
            .catch(() => {})
            .finally(() => {
              running -= 1;
              pump();
            });
        }
      };
      pump();
    }

    function deskSidebarPageUrl(mode) {
      if (mode === "new") return `/new-session?embed=1&ts=${Date.now()}`;
      if (mode === "settings") return `/hub-launch-shell.html?target=${encodeURIComponent("/settings?embed=1")}`;
      return "about:blank";
    }

    function syncDeskChatShellState() {
      if (_deskChatFrame) {
        if (isDeskSidebarOpen()) _deskChatFrame.dataset.hubSidebarOpen = "1";
        else delete _deskChatFrame.dataset.hubSidebarOpen;
      }
      try {
        _deskChatFrame?.contentWindow?.postMessage({
          type: "multiagent-hub-sidebar-state",
          open: !!isDeskSidebarOpen(),
        }, "*");
      } catch (_) {}
    }

    function setDeskComposerOverlayOpen(isOpen) {
      _deskMain?.classList.toggle("composer-overlay-open", !!isOpen);
    }

    function syncDeskSidebarResizerVisibility() {
      if (!_deskSidebarResizer) return;
      if (isTauriDesktopApp()) {
        _deskSidebarResizer.hidden = false;
        return;
      }
      if (isPhoneViewport()) {
        _deskSidebarResizer.hidden = true;
        return;
      }
      _deskSidebarResizer.hidden = !isDeskSidebarOpen();
    }

    function setDeskSidebarOpen(isOpen) {
      if (!_deskWorkbench) return;
      _deskWorkbench.classList.toggle("sidebar-open", !!isOpen);
      if (_deskAppSidebarToggle) {
        _deskAppSidebarToggle.classList.toggle("is-active", !!isOpen);
      }
      syncDeskSidebarResizerVisibility();
      syncDeskChatShellState();
      if (isOpen) {
        scheduleDeskActivePrewarm();
      }
    }

    function isDeskSidebarOpen() {
      return !!(_deskWorkbench && _deskWorkbench.classList.contains("sidebar-open"));
    }

    function setDeskSidebarMode(mode) {
      _deskSidebarMode = mode;
      const settingsActive = mode === "settings";
      if (_deskSidebarSessions) _deskSidebarSessions.hidden = settingsActive;
      if (_deskSidebarPane) _deskSidebarPane.hidden = !settingsActive;
      if (_deskSidebarPane) _deskSidebarPane.classList.toggle("settings-mode", settingsActive);
      if (_deskSettingsBtn) _deskSettingsBtn.classList.toggle("is-active", settingsActive);
    }

    function showDeskSidebarList({ open = true } = {}) {
      setDeskSidebarMode("list");
      if (open) setDeskSidebarOpen(true);
    }

    async function pickWorkspaceForNewSession() {
      const nativePickerSupported =
        /mac/i.test(String(navigator.platform || "")) &&
        !/iphone|ipad|ipod|android/i.test(String(navigator.userAgent || ""));
      if (!nativePickerSupported) {
        const manual = window.prompt("Workspace path", "");
        return manual === null ? "" : String(manual || "").trim();
      }
      const res = await fetch("/pick-workspace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json().catch(() => ({}));
      if (data.ok && data.path) return String(data.path || "");
      if (data.canceled) return "";
      throw new Error(data.error || "Workspace picker failed.");
    }

    function promptSessionNameConflict(original, proposed) {
      return new Promise((resolve) => {
        const overlay = document.createElement("div");
        overlay.style.cssText = "position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;";
        const panel = document.createElement("div");
        panel.style.cssText = "background:var(--surface,#1a1a1a);border:1px solid var(--border,#333);border-radius:14px;padding:24px 28px;min-width:320px;max-width:420px;box-shadow:0 8px 32px rgba(0,0,0,0.5);";
        panel.innerHTML = `
          <div style="font-size:13px;font-weight:600;margin-bottom:6px;color:var(--fg,#eee);">セッション名が重複しています</div>
          <div style="font-size:12px;color:var(--fg-muted,#888);margin-bottom:16px;">「${original}」は既に使われています。別の名前を入力してください。</div>
          <input id="_snConflictInput" type="text" value="${proposed}" maxlength="64"
            style="width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;border:1px solid var(--border,#444);background:var(--surface-alt,#222);color:var(--fg,#eee);font-size:13px;outline:none;margin-bottom:16px;">
          <div style="display:flex;gap:8px;justify-content:flex-end;">
            <button id="_snConflictCancel" style="padding:7px 16px;border-radius:8px;border:1px solid var(--border,#444);background:transparent;color:var(--fg-muted,#888);font-size:12px;cursor:pointer;">キャンセル</button>
            <button id="_snConflictOk" style="padding:7px 16px;border-radius:8px;border:none;background:var(--accent,#3b82f6);color:#fff;font-size:12px;cursor:pointer;font-weight:600;">作成</button>
          </div>`;
        overlay.appendChild(panel);
        document.body.appendChild(overlay);
        const input = panel.querySelector("#_snConflictInput");
        const ok = panel.querySelector("#_snConflictOk");
        const cancel = panel.querySelector("#_snConflictCancel");
        const cleanup = (result) => { overlay.remove(); resolve(result); };
        ok.addEventListener("click", () => cleanup(input.value.trim() || null));
        cancel.addEventListener("click", () => cleanup(null));
        overlay.addEventListener("click", (e) => { if (e.target === overlay) cleanup(null); });
        input.addEventListener("keydown", (e) => { if (e.key === "Enter") cleanup(input.value.trim() || null); if (e.key === "Escape") cleanup(null); });
        setTimeout(() => { input.select(); }, 30);
      });
    }

    async function startDeskNewSessionFlow() {
      if (_deskNewSessionStarting) return;
      _deskNewSessionStarting = true;
      _deskNewSessionToggle?.classList.add("archived");
      try {
        const workspace = await pickWorkspaceForNewSession();
        if (!workspace) return;
        const checkRes = await fetch(`/check-session-name?workspace=${encodeURIComponent(workspace)}`);
        const checkData = await checkRes.json().catch(() => ({}));
        if (!checkData.ok) throw new Error(checkData.error || "Failed to check session name.");
        let sessionName = null;
        if (checkData.conflict) {
          const confirmed = await promptSessionNameConflict(checkData.original, checkData.name);
          if (!confirmed) return;
          sessionName = confirmed;
        }
        const body = sessionName ? { workspace, session_name: sessionName } : { workspace };
        const res = await fetch("/start-session-draft", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok || !data.chat_url) {
          throw new Error(data.error || "Failed to open draft session.");
        }
        openChatInDesk(data.chat_url, data.session || "");
        if (isPhoneViewport()) {
          setDeskSidebarOpen(false);
        } else {
          showDeskSidebarList({ open: true });
        }
        void refreshHubSessions(true, { skipRestore: true });
      } catch (err) {
        window.alert(err?.message || "Failed to open draft session.");
      } finally {
        _deskNewSessionStarting = false;
        _deskNewSessionToggle?.classList.remove("archived");
      }
    }

    function openDeskSidebarPage(mode) {
      if (mode === "new") {
        startDeskNewSessionFlow();
        return;
      }
      if (!_deskSidebarFrame || !_deskSidebarPaneTitle) return;
      if (_deskSidebarMode === "settings") {
        showDeskSidebarList({ open: true });
        return;
      }
      const settingsUrl = deskSidebarPageUrl("settings");
      const currentUrl = normalizeComparableUrl(_deskSidebarFrame.src);
      const nextUrl = normalizeComparableUrl(settingsUrl);
      if (!currentUrl || currentUrl !== nextUrl) {
        _deskSidebarFrame.src = settingsUrl;
      }
      _deskSidebarPaneTitle.textContent = "";
      setDeskSidebarMode("settings");
      setDeskSidebarOpen(true);
    }

    function clearDeskChatFrame() {
      if (_deskChatFrame) _deskChatFrame.src = "about:blank";
      setDeskChatLoading(false);
    }

    function clearDeskSelection() {
      _deskOpenToken += 1;
      _deskSelectedSessionName = "";
      persistDeskSelection("");
      setDeskSelectionInUrl("");
      clearDeskChatFrame();
      renderDesktopSessions(_hubSessionsCache.active || [], _hubSessionsCache.archived || []);
    }

    function openChatInDesk(url, name) {
      if (!_deskChatFrame) return;
      _deskSelectedSessionName = name || "";
      persistDeskSelection(_deskSelectedSessionName);
      setDeskSelectionInUrl(_deskSelectedSessionName);
      setDeskComposerOverlayOpen(false);
      if (isDeskSidebarOpen()) _deskChatFrame.dataset.hubSidebarOpen = "1";
      else delete _deskChatFrame.dataset.hubSidebarOpen;
      if (_deskSelectedSessionName) {
        cacheDeskChatUrl(buildSessionOpenHref(_deskSelectedSessionName, false), url);
      }
      const frameUrl = buildDeskChatFrameUrl(url);
      if (frameUrl) {
        const currentUrl = normalizeComparableUrl(_deskChatFrame.src);
        const nextUrl = normalizeComparableUrl(frameUrl);
        if (!currentUrl || currentUrl !== nextUrl) {
          setDeskChatLoading(true);
          _deskChatFrame.src = frameUrl;
        } else {
          setDeskChatLoading(false);
        }
      } else {
        setDeskChatLoading(false);
      }
      renderDesktopSessions(_hubSessionsCache.active || [], _hubSessionsCache.archived || []);
    }

    async function resolveSessionChatUrl(openHref) {
      const cached = readCachedDeskChatUrl(openHref);
      if (cached) return cached;
      const inflight = _deskChatUrlInflight.get(openHref);
      if (inflight) return inflight;
      const url = openHref + (openHref.includes("?") ? "&" : "?") + "format=json";
      const request = fetch(url, { cache: "no-store" })
        .then(async (response) => {
          const data = await response.json();
          if (response.ok && data && data.chat_url) {
            cacheDeskChatUrl(openHref, data.chat_url);
            return data.chat_url;
          }
          throw new Error((data && data.error) || "chat url unavailable");
        })
        .finally(() => {
          _deskChatUrlInflight.delete(openHref);
        });
      _deskChatUrlInflight.set(openHref, request);
      return request;
    }

    async function openSessionFrame(openHref, name) {
      if (!name) {
        window.location.href = openHref;
        return;
      }
      const needsReviveTransition = /^\/revive-session(?:[/?]|$)/.test(String(openHref || ""));
      const closeOnOpen = isPhoneViewport();
      _deskSelectedSessionName = name;
      persistDeskSelection(name);
      setDeskSelectionInUrl(name);
      renderDesktopSessions(_hubSessionsCache.active || [], _hubSessionsCache.archived || []);
      if (needsReviveTransition) setDeskChatLoading(true);
      const openToken = ++_deskOpenToken;
      try {
        const chatUrl = await resolveSessionChatUrl(openHref);
        if (openToken !== _deskOpenToken) return;
        openChatInDesk(chatUrl, name);
        if (closeOnOpen) setDeskSidebarOpen(false);
      } catch (_) {
        if (openToken !== _deskOpenToken) return;
        window.location.href = openHref;
      }
    }

    function getDeskSessionRows() {
      if (!_deskSessionList) return [];
      return Array.from(_deskSessionList.querySelectorAll(".desk-session-row[data-open-href][data-session-name]"))
        .filter((row) => row && row.getClientRects().length > 0);
    }

    function focusDeskSessionRow(row) {
      if (!row) return;
      try {
        row.focus({ preventScroll: true });
      } catch (_) {
        try { row.focus(); } catch (_) {}
      }
      try {
        row.scrollIntoView({ block: "nearest" });
      } catch (_) {}
    }

    function focusDeskSessionByName(name) {
      if (!_deskSessionList || !name) return;
      const row = _deskSessionList.querySelector(`.desk-session-row[data-session-name="${cssEsc(name)}"]`);
      focusDeskSessionRow(row);
    }

    function openDeskSessionRow(row) {
      if (!row) return false;
      const href = row.dataset.openHref;
      const name = row.dataset.sessionName || "";
      if (!href || !name) return false;
      openSessionFrame(href, name);
      requestAnimationFrame(() => focusDeskSessionByName(name));
      return true;
    }

    function moveDeskSessionSelection(direction, fromRow = null, fromEdge = "") {
      const rows = getDeskSessionRows();
      if (!rows.length) return false;
      let index = -1;
      if (fromEdge === "after") {
        index = rows.length;
      } else if (fromEdge === "before") {
        index = -1;
      } else if (fromRow && rows.includes(fromRow)) {
        index = rows.indexOf(fromRow);
      } else {
        const activeRow = document.activeElement?.closest?.(".desk-session-row");
        if (activeRow && rows.includes(activeRow)) {
          index = rows.indexOf(activeRow);
        } else if (_deskSelectedSessionName) {
          index = rows.findIndex((row) => row.dataset.sessionName === _deskSelectedSessionName);
        }
      }
      const nextIndex = index < 0 || index >= rows.length
        ? (direction > 0 ? 0 : rows.length - 1)
        : (index + direction + rows.length) % rows.length;
      return openDeskSessionRow(rows[nextIndex]);
    }

    function pickDeskFallbackSession(excludedName = "") {
      const blocked = String(excludedName || "");
      const active = sortActiveSessions((_hubSessionsCache.active || []).filter((session) => session.name !== blocked));
      if (active.length) {
        return { name: active[0].name, archived: false };
      }
      const archived = (_hubSessionsCache.archived || []).filter((session) => session.name !== blocked);
      if (archived.length) {
        return { name: archived[0].name, archived: true };
      }
      return null;
    }

    function maybeRestoreDeskSelection() {
      if (_deskSelectedSessionName) {
        if (findSessionRecord(_deskSelectedSessionName)) return;
        persistDeskSelection("");
        setDeskSelectionInUrl("");
        _deskSelectedSessionName = "";
        const fallback = pickDeskFallbackSession();
        if (fallback) {
          openSessionFrame(buildSessionOpenHref(fallback.name, fallback.archived), fallback.name);
          return;
        }
        clearDeskSelection();
        return;
      }
      const requested = getRequestedDeskSelection();
      if (requested) {
        const match = findSessionRecord(requested);
        if (!match) {
          persistDeskSelection("");
          setDeskSelectionInUrl("");
        } else {
          openSessionFrame(buildSessionOpenHref(requested, match.archived), requested);
          return;
        }
      }
      const active = _hubSessionsCache.active || [];
      if (active.length) {
        openSessionFrame(buildSessionOpenHref(active[0].name, false), active[0].name);
        return;
      }
      showDeskSidebarList({ open: true });
      clearDeskChatFrame();
    }

    function renderDeskSessionRow(session, archived) {
      const sessionName = String(session.name || "");
      const launchPending = !!session.launch_pending;
      const archivedClass = archived ? " archived" : "";
      const selectedClass = _deskSelectedSessionName === sessionName ? " is-selected" : "";
      const swipeActionLabel = (archived || launchPending) ? "Delete" : "Kill";
      const swipeActionRoute = (archived || launchPending) ? "delete-archived" : "kill";
      const trashSvg = `<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"></path><path d="M19 6l-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
      const runningClass = !archived && resolveDeskSessionRunningState(sessionName, !!session.is_running) ? " is-running" : "";
      const previewText = String(session.latest_message_preview || "").trim();
      const previewSender = String(session.latest_message_sender || "").trim();
      const previewHtml = previewText
        ? `<div class="desk-row-preview"><span class="sender">${esc(previewSender || "latest")}</span>${esc(previewText)}</div>`
        : "";
      return `<div class="desk-swipe-row" data-session-name="${esc(sessionName)}" data-desk-swipe-kind="${esc(swipeActionRoute)}">` +
        `<div class="desk-swipe-action-rail">` +
          `<button type="button" class="desk-swipe-action-btn" data-desk-swipe-action="${esc(swipeActionRoute)}" aria-label="${esc(swipeActionLabel + " " + sessionName)}">` +
            `<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"></path><path d="M19 6l-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>` +
            `<span>${esc(swipeActionLabel)}</span>` +
          `</button>` +
        `</div>` +
        `<div class="desk-swipe-track">` +
          `<div class="desk-session-row${archivedClass}${selectedClass}" data-session-name="${esc(sessionName)}" data-open-href="${buildSessionOpenHref(sessionName, archived)}" tabindex="0" role="button" aria-current="${selectedClass ? "page" : "false"}">` +
            `<div class="desk-row-head">` +
                `<div class="desk-row-main">` +
                  `<span class="desk-row-bullet${runningClass}" aria-hidden="true">` +
                    `<i style="grid-area:1/1"></i><i style="grid-area:1/2"></i><i style="grid-area:2/2"></i>` +
                    `<i style="grid-area:3/2"></i><i style="grid-area:3/1"></i><i style="grid-area:2/1"></i>` +
                  `</span>` +
                  `<div class="desk-row-stack">` +
                    `<div class="desk-row-name">${esc(sessionName)}</div>` +
                    previewHtml +
                  `</div>` +
                `</div>` +
                `<button type="button" class="desk-row-hover-action" data-desk-hover-action="${esc(swipeActionRoute)}" aria-label="${esc(swipeActionLabel + " " + sessionName)}" title="${esc(swipeActionLabel)}">` +
                  trashSvg +
                `</button>` +
              `</div>` +
            `</div>` +
          `</div>` +
        `</div>`;
    }

    function closeDeskSwipeRow(wrapper, animate = true) {
      if (!wrapper) return;
      const track = wrapper.querySelector(".desk-swipe-track");
      if (!track) return;
      track.style.transition = animate ? "transform 220ms cubic-bezier(.25,.46,.45,.94)" : "none";
      track.style.transform = "";
      wrapper.dataset.swipeOpen = "0";
      if (_deskOpenSwipeRow === wrapper) _deskOpenSwipeRow = null;
    }

    async function runDeskContextAction(sessionName, kind) {
      if (!sessionName || !kind) return;
      const isDelete = kind === "delete-archived";
      const confirmed = isTauriDesktopApp()
        ? true
        : (isDelete
          ? confirm("Delete archived logs for " + sessionName + "? This cannot be undone.")
          : confirm("Kill " + sessionName + "?"));
      if (!confirmed) return;
      const route = isDelete ? "/delete-archived-session" : "/kill-session";
      const isSelected = _deskSelectedSessionName === sessionName;
      try {
        const response = await fetch(
          `${route}?session=${encodeURIComponent(sessionName)}&format=json&ts=${Date.now()}`,
          { cache: "no-store" }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error(data.error || (isDelete ? "Failed to delete session." : "Failed to kill session."));
        }
        const activeHref = buildSessionOpenHref(sessionName, false);
        const archivedHref = buildSessionOpenHref(sessionName, true);
        _deskChatUrlCache.delete(activeHref);
        _deskChatUrlCache.delete(archivedHref);
        _deskChatUrlInflight.delete(activeHref);
        _deskChatUrlInflight.delete(archivedHref);
        if (isSelected) {
          _deskOpenToken += 1;
          _deskSelectedSessionName = "";
          persistDeskSelection("");
          setDeskSelectionInUrl("");
        }
        await refreshHubSessions(true, { skipRestore: true });
        if (!isSelected) return;
        const fallback = pickDeskFallbackSession(sessionName);
        if (fallback) {
          await openSessionFrame(buildSessionOpenHref(fallback.name, fallback.archived), fallback.name);
          return;
        }
        clearDeskSelection();
        showDeskSidebarList({ open: true });
      } catch (err) {
        window.alert(err?.message || (isDelete ? "Failed to delete session." : "Failed to kill session."));
      }
    }

    function initDeskSwipeRow(wrapper) {
      if (!wrapper || wrapper.dataset.swipeBound === "1") return;
      const track = wrapper.querySelector(".desk-swipe-track");
      const row = wrapper.querySelector(".desk-session-row");
      const actionBtn = wrapper.querySelector("[data-desk-swipe-action]");
      if (!track || !row || !actionBtn) return;
      wrapper.dataset.swipeBound = "1";
      wrapper.dataset.swipeOpen = "0";
      let startX = 0;
      let startY = 0;
      let deltaX = 0;
      let axis = "";
      let active = false;
      let didSwipe = false;
      let baseX = 0;
      const clearHoverHalf = () => {
        delete row.dataset.hoverHalf;
      };
      const updateHoverHalf = (clientX) => {
        if (isPhoneViewport()) {
          clearHoverHalf();
          return;
        }
        const rect = row.getBoundingClientRect();
        if (!rect.width) {
          clearHoverHalf();
          return;
        }
        row.dataset.hoverHalf = clientX >= rect.left + (rect.width / 2) ? "right" : "left";
      };
      const setTrackX = (x, animate = false) => {
        track.style.transition = animate ? "transform 220ms cubic-bezier(.25,.46,.45,.94)" : "none";
        track.style.transform = x ? `translateX(${x}px)` : "";
        wrapper.dataset.swipeOpen = x ? "1" : "0";
        if (!x && _deskOpenSwipeRow === wrapper) _deskOpenSwipeRow = null;
        if (x) _deskOpenSwipeRow = wrapper;
      };
      row.addEventListener("mousemove", (event) => updateHoverHalf(event.clientX));
      row.addEventListener("mouseleave", clearHoverHalf);
      const startDrag = (clientX, clientY) => {
        if (_deskOpenSwipeRow && _deskOpenSwipeRow !== wrapper) {
          closeDeskSwipeRow(_deskOpenSwipeRow, true);
        }
        startX = clientX;
        startY = clientY;
        deltaX = 0;
        axis = "";
        active = true;
        didSwipe = false;
        baseX = wrapper.dataset.swipeOpen === "1" ? -DESK_SWIPE_ACTION_WIDTH : 0;
        track.style.transition = "none";
      };
      const moveDrag = (clientX, clientY, preventDefault) => {
        if (!active) return;
        const moveX = clientX - startX;
        const moveY = clientY - startY;
        if (!axis) {
          if (Math.abs(moveY) > Math.abs(moveX) + 4) {
            axis = "y";
            return;
          }
          if (Math.abs(moveX) > 6) axis = "x";
        }
        if (axis !== "x") return;
        if (preventDefault) preventDefault();
        didSwipe = true;
        deltaX = moveX;
        let nextX = Math.max(-DESK_SWIPE_ACTION_WIDTH, Math.min(0, baseX + moveX));
        track.style.transform = nextX ? `translateX(${nextX}px)` : "";
      };
      const endDrag = () => {
        if (!active) return;
        active = false;
        if (axis !== "x") return;
        const finalX = Math.max(-DESK_SWIPE_ACTION_WIDTH, Math.min(0, baseX + deltaX));
        if (finalX < -DESK_SWIPE_OPEN_THRESHOLD) {
          setTrackX(-DESK_SWIPE_ACTION_WIDTH, true);
        } else {
          setTrackX(0, true);
        }
        if (didSwipe) {
          wrapper._swipeConsumedUntil = Date.now() + 260;
        }
        deltaX = 0;
      };
      track.addEventListener("touchstart", (event) => {
        if (event.target.closest("[data-desk-action]")) return;
        const touch = event.touches[0];
        if (!touch) return;
        startDrag(touch.clientX, touch.clientY);
      }, { passive: true });
      track.addEventListener("touchmove", (event) => {
        const touch = event.touches[0];
        if (!touch) return;
        moveDrag(touch.clientX, touch.clientY, () => event.preventDefault());
      }, { passive: false });
      track.addEventListener("touchend", endDrag, { passive: true });
      track.addEventListener("touchcancel", endDrag, { passive: true });
      track.addEventListener("mousedown", (event) => {
        if (!isPhoneViewport()) return;
        if (event.target.closest("[data-desk-action], a, button")) return;
        event.preventDefault();
        startDrag(event.clientX, event.clientY);
        const onMove = (moveEvent) => moveDrag(moveEvent.clientX, moveEvent.clientY, () => moveEvent.preventDefault());
        const onUp = () => {
          endDrag();
          document.removeEventListener("mousemove", onMove);
          document.removeEventListener("mouseup", onUp);
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
      });
      actionBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const sessionName = wrapper.dataset.sessionName || "";
        const kind = actionBtn.dataset.deskSwipeAction || "";
        runDeskContextAction(sessionName, kind);
      });
    }

    function renderDesktopSessions(active, archived) {
      if (!_deskSessionList) return;
      const sortedActive = sortActiveSessions(active);
      let html = "";
      if (sortedActive.length) {
        html += `<div class="desk-section-label">Active</div>`;
        html += sortedActive.map((session) => renderDeskSessionRow(session, false)).join("");
      }
      if (archived.length) {
        html += `<div class="desk-section-label">Archived</div>`;
        html += archived.map((session) => renderDeskSessionRow(session, true)).join("");
      }
      if (!sortedActive.length && !archived.length) {
        html = `<div class="desk-empty-list">No sessions found</div>`;
      }
      _deskSessionList.innerHTML = html;
      _deskSessionList.querySelectorAll(".desk-swipe-row").forEach(initDeskSwipeRow);
    }

    async function refreshHubSessions(force = false, options = {}) {
      const skipRestore = !!(options && options.skipRestore);
      const requestSeq = ++_deskSessionsRequestSeq;
      try {
        const response = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) throw new Error("failed");
        const data = await response.json();
        if (requestSeq !== _deskSessionsRequestSeq) return;
        syncDeskBoldModeFromSessionsPayload(data);
        const active = data.active_sessions || data.sessions || [];
        const archived = data.archived_sessions || [];
        syncDeskSessionRunningFromServer(active);
        _hubSessionsCache = { active, archived };
        _deskSessionsColdFailures = 0;

        const signature = JSON.stringify({
          active,
          archived,
          selected: _deskSelectedSessionName,
        });
        if (force || window._lastHubRenderSig !== signature) {
          window._lastHubRenderSig = signature;
          renderDesktopSessions(active, archived);
        } else {
          active.forEach((session) => refreshDeskSessionRunningRow(session?.name || ""));
        }
        _deskSessionsRenderedOnce = true;
        scheduleDeskActivePrewarm();
        if (!skipRestore) maybeRestoreDeskSelection();
      } catch (_) {
        if (requestSeq !== _deskSessionsRequestSeq) return;
        if (_deskSessionsRenderedOnce || _hubSessionsCache.active.length || _hubSessionsCache.archived.length) return;
        _deskSessionsColdFailures += 1;
        if (_deskSessionsColdFailures < 2) return;
        if (_deskSessionList) {
          _deskSessionList.innerHTML = `<div class="desk-empty-list">Failed to load sessions</div>`;
        }
      }
    }

    window.addEventListener("message", (event) => {
      if (event.data && event.data.type === "multiagent-session-running-state" && event.source === _deskChatFrame?.contentWindow) {
        const sessionName = String(event.data.sessionName || "").trim();
        if (!sessionName) return;
        setDeskSessionRunningState(sessionName, !!event.data.isRunning, "live");
        refreshDeskSessionRunningRow(sessionName);
        return;
      }
      if (event.data && event.data.type === "multiagent-desktop-panel-state" && event.source === _deskChatFrame?.contentWindow) {
        updateDeskPanelButtonState(
          String(event.data.mode || ""),
          Number(event.data.width || 0),
        );
        return;
      }
      if (event.data && event.data.type === "multiagent-show-chat-header-menu") {
        const invoke = (() => {
          try { return window.__TAURI__?.core?.invoke || window.__TAURI__?.invoke || null; } catch (_) { return null; }
        })();
        if (typeof invoke !== "function") return;
        const childPayload = event.data.payload || {};
        const frameRect = _deskChatFrame?.getBoundingClientRect?.() || { left: 0, top: 0 };
        invoke("show_chat_header_menu", {
          payload: {
            ...childPayload,
            x: Math.round(Number(childPayload.x || 0) + Number(frameRect.left || 0)),
            y: Math.round(Number(childPayload.y || 0) + Number(frameRect.top || 0)),
          },
        }).catch(() => {});
        return;
      }
      if (event.data && event.data.type === "multiagent-composer-overlay-state" && event.source === _deskChatFrame?.contentWindow) {
        setDeskComposerOverlayOpen(!!event.data.open);
        return;
      }
      if (event.data === "hub_close_chat") {
        showDeskSidebarList({ open: true });
        return;
      }
      if (event.data && event.data.type === "multiagent-toggle-hub-sidebar") {
        setDeskSidebarOpen(!isDeskSidebarOpen());
        if (isDeskSidebarOpen()) setDeskSidebarMode("list");
        return;
      }
      if (event.data && event.data.type === "multiagent-hub-open-chat-session") {
        const chatUrl = typeof event.data.chatUrl === "string" ? event.data.chatUrl : "";
        const sessionName = typeof event.data.sessionName === "string" ? event.data.sessionName : "";
        if (chatUrl && sessionName) {
          openChatInDesk(chatUrl, sessionName);
          if (isPhoneViewport()) {
            setDeskSidebarOpen(false);
          } else {
            showDeskSidebarList({ open: true });
          }
          void refreshHubSessions(true, { skipRestore: true });
        }
        return;
      }
      if (event.data && event.data.type === "multiagent-hub-close-sidebar-page") {
        showDeskSidebarList({ open: true });
        return;
      }
      if (event.data && event.data.type === "multiagent-open-hub-path") {
        const nextUrl = typeof event.data.url === "string" ? event.data.url : "";
        if (!nextUrl) return;
        try {
          const parsed = new URL(nextUrl, window.location.href);
          if (parsed.pathname === "/new-session") {
            setDeskSidebarOpen(true);
            openDeskSidebarPage("new");
            return;
          }
          if (parsed.pathname === "/settings") {
            setDeskSidebarOpen(true);
            openDeskSidebarPage("settings");
            return;
          }
        } catch (_) {}
        window.location.href = nextUrl;
      }
    });
    document.addEventListener("dragenter", (event) => {
      if (!deskDtHasFiles(event.dataTransfer) || isDeskChatFrameDropTarget(event.target)) return;
      setDeskAttachDragActive(true);
    }, true);
    document.addEventListener("dragover", (event) => {
      if (!deskDtHasFiles(event.dataTransfer) || isDeskChatFrameDropTarget(event.target)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      setDeskAttachDragActive(true);
    }, true);
    document.addEventListener("dragleave", (event) => {
      if (!deskDtHasFiles(event.dataTransfer) || isDeskChatFrameDropTarget(event.target)) return;
      const related = event.relatedTarget;
      if (!related || !document.documentElement.contains(related)) {
        setDeskAttachDragActive(false);
      }
    }, true);
    document.addEventListener("dragend", () => {
      setDeskAttachDragActive(false);
    }, true);
    document.addEventListener("drop", (event) => {
      if (!deskDtHasFiles(event.dataTransfer) || isDeskChatFrameDropTarget(event.target)) return;
      event.preventDefault();
      event.stopPropagation();
      setDeskAttachDragActive(false);
      forwardDeskDroppedFiles(event.dataTransfer.files);
    }, true);

    _deskChatFrame && _deskChatFrame.addEventListener("load", () => {
      setDeskChatLoading(false);
      syncDeskChatShellState();
      try {
        _deskChatFrame.contentWindow?.postMessage({ type: "multiagent-desktop-panel-sync-request" }, "*");
      } catch (_) {}
    });

    _deskMain && _deskMain.addEventListener("click", () => {
      if (isPhoneViewport() && isDeskSidebarOpen()) {
        setDeskSidebarOpen(false);
      }
    });
    _deskAppSidebarToggle && _deskAppSidebarToggle.addEventListener("click", (event) => {
      event.preventDefault();
      if (isDeskSidebarOpen()) {
        setDeskSidebarOpen(false);
        return;
      }
      showDeskSidebarList({ open: true });
    });
    _deskSidebar && _deskSidebar.addEventListener("touchstart", (event) => {
      if (!isPhoneViewport() || !isDeskSidebarOpen()) return;
      const touch = event.touches[0];
      if (!touch) return;
      const rect = _deskSidebar.getBoundingClientRect();
      const fromRightEdge = rect.right - touch.clientX;
      if (fromRightEdge > DESK_SIDEBAR_CLOSE_SWIPE_EDGE_PX) return;
      _deskSidebar._closeSwipeStartX = touch.clientX;
      _deskSidebar._closeSwipeStartY = touch.clientY;
      _deskSidebar._closeSwipeTracking = true;
      _deskSidebar._closeSwipeAxis = "";
    }, { passive: true });
    _deskSidebar && _deskSidebar.addEventListener("touchmove", (event) => {
      if (!_deskSidebar._closeSwipeTracking) return;
      const touch = event.touches[0];
      if (!touch) return;
      const moveX = touch.clientX - (_deskSidebar._closeSwipeStartX || 0);
      const moveY = touch.clientY - (_deskSidebar._closeSwipeStartY || 0);
      if (!_deskSidebar._closeSwipeAxis) {
        if (Math.abs(moveY) > Math.abs(moveX) + 6) {
          _deskSidebar._closeSwipeAxis = "y";
          return;
        }
        if (Math.abs(moveX) > 8) _deskSidebar._closeSwipeAxis = "x";
      }
      if (_deskSidebar._closeSwipeAxis !== "x") return;
      _deskSidebar._closeSwipeDeltaX = moveX;
    }, { passive: true });
    const finishDeskSidebarSwipeClose = () => {
      if (!_deskSidebar || !_deskSidebar._closeSwipeTracking) return;
      const moveX = Number(_deskSidebar._closeSwipeDeltaX || 0);
      const shouldClose = _deskSidebar._closeSwipeAxis === "x" && moveX < -DESK_SIDEBAR_CLOSE_SWIPE_THRESHOLD;
      _deskSidebar._closeSwipeTracking = false;
      _deskSidebar._closeSwipeAxis = "";
      _deskSidebar._closeSwipeDeltaX = 0;
      if (shouldClose) setDeskSidebarOpen(false);
    };
    _deskSidebar && _deskSidebar.addEventListener("touchend", finishDeskSidebarSwipeClose, { passive: true });
    _deskSidebar && _deskSidebar.addEventListener("touchcancel", finishDeskSidebarSwipeClose, { passive: true });
    _deskSidebarResizer && _deskSidebarResizer.addEventListener("pointerdown", (event) => {
      if (isPhoneViewport()) return;
      event.preventDefault();
      const startWidth = _deskSidebarWidth;
      const startX = event.clientX;
      _deskSidebarResizer.setPointerCapture?.(event.pointerId);
      document.body.classList.add("desk-workbench-resizing");
      const onMove = (moveEvent) => {
        const nextWidth = startWidth + (moveEvent.clientX - startX);
        setDeskSidebarWidth(nextWidth);
      };
      const onUp = () => {
        document.body.classList.remove("desk-workbench-resizing");
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
    });

    setDeskSidebarWidth(readDeskSidebarWidth(), { persist: false });
    syncDeskSidebarResizerVisibility();
    try {
      sessionStorage.removeItem("hub_chat_frame");
    } catch (_) {}

    _deskNewSessionToggle && _deskNewSessionToggle.addEventListener("click", (event) => {
      event.preventDefault();
      startDeskNewSessionFlow();
    });
    _deskNewSessionToggle && _deskNewSessionToggle.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        event.stopPropagation();
        moveDeskSessionSelection(event.key === "ArrowDown" ? 1 : -1, event.currentTarget, event.key === "ArrowDown" ? "before" : "after");
        return;
      }
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      startDeskNewSessionFlow();
    });
    _deskChatMenuBtn && _deskChatMenuBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openDeskChatHeaderMenu();
    });
    _deskPanelToggle && _deskPanelToggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (_deskPanelActiveMode) {
        updateDeskPanelButtonState("", 0);
        sendDeskPanelCommand("close");
        return;
      }
      updateDeskPanelButtonState("open", _deskPanelWidth);
      sendDeskPanelCommand("repo");
    });
    _deskSettingsBtn && _deskSettingsBtn.addEventListener("click", () => openDeskSidebarPage("settings"));
    _deskReloadBtn && _deskReloadBtn.addEventListener("click", () => {
      if (_deskReloadBtn.classList.contains("restarting")) return;
      _deskReloadBtn.classList.add("restarting");
      _deskReloadBtn.disabled = true;
      setDeskReloadShell(true);
      const launchShellTarget = `/hub-launch-shell.html?restart=1&target=${encodeURIComponent("/")}`;
      window.location.replace(launchShellTarget);
    });
    if (_deskSessionList) {
      _deskSessionList.addEventListener("click", (event) => {
        const hoverAction = event.target.closest("[data-desk-hover-action]");
        if (hoverAction) {
          event.preventDefault();
          event.stopPropagation();
          const row = hoverAction.closest(".desk-session-row");
          const sessionName = row?.dataset.sessionName || "";
          const kind = hoverAction.dataset.deskHoverAction || "";
          if (sessionName && kind) {
            void runDeskContextAction(sessionName, kind);
          }
          return;
        }
        const swipeAction = event.target.closest("[data-desk-swipe-action]");
        if (swipeAction) return;
        const row = event.target.closest(".desk-session-row");
        if (!row) return;
        const swipeRow = row.closest(".desk-swipe-row");
        if (swipeRow && swipeRow._swipeConsumedUntil && swipeRow._swipeConsumedUntil > Date.now()) {
          return;
        }
        if (swipeRow && swipeRow.dataset.swipeOpen === "1") {
          event.preventDefault();
          event.stopPropagation();
          closeDeskSwipeRow(swipeRow, true);
          return;
        }
        const href = row.dataset.openHref;
        const name = row.dataset.sessionName || "";
        if (href) openSessionFrame(href, name);
      });
      _deskSessionList.addEventListener("keydown", (event) => {
        const row = event.target.closest(".desk-session-row");
        if (!row) return;
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          event.stopPropagation();
          moveDeskSessionSelection(event.key === "ArrowDown" ? 1 : -1, row);
          return;
        }
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openDeskSessionRow(row);
      });
    }

    window.refreshHubSessionLists = refreshHubSessions;
    consumeHubPendingError();
    refreshHubSessions(true);
    setInterval(() => {
      refreshHubSessions(false);
    }, 5000);
  __HUB_HEADER_JS__
