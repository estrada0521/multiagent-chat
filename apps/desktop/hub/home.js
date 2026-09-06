    function markTauriDesktopApp() {
      document.documentElement.dataset.tauriApp = "1";
      try { sessionStorage.setItem("agent_window_tauri_app", "1"); } catch (_) {}
      window.__agentWindowNative = window.__agentWindowNative || {};
      window.__agentWindowNative.isTauriApp = true;
      return true;
    }
    function isTauriDesktopApp() {
      if (document.documentElement.dataset.tauriApp === "1" || window.__agentWindowNative?.isTauriApp) return true;
      try {
        const params = new URLSearchParams(window.location.search || "");
        if (params.get("tauri") === "1" || sessionStorage.getItem("agent_window_tauri_app") === "1") {
          return markTauriDesktopApp();
        }
      } catch (_) {}
      try {
        if (
          typeof window.__TAURI__ !== "undefined" ||
          typeof window.__TAURI_INTERNALS__ !== "undefined" ||
          window.__agentWindowNative?.appSettingsLoaded
        ) {
          return markTauriDesktopApp();
        }
      } catch (_) {}
      return false;
    }
    function getTauriInvoke() {
      try { return window.__TAURI__?.core?.invoke || window.__TAURI__?.invoke || null; } catch (_) { return null; }
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
    const _deskChatReloadBtn = document.getElementById("deskChatReloadBtn");
    const _deskPanelToggle = document.getElementById("deskPanelToggle");
    const _deskChatShell = document.querySelector(".desk-chat-shell");
    const _deskReloadShell = document.getElementById("deskReloadShell");
    const _deskMain = document.querySelector(".desk-main");
    const _deskSettingsBtn = document.getElementById("deskSettingsBtn");
    const _deskReloadBtn = document.getElementById("deskReloadBtn");
    const _deskNewSessionToggle = document.getElementById("deskNewSessionToggle");
    const _deskHubMessage = document.getElementById("deskHubMessage");
    const _deskFloatingControls = document.querySelector(".desk-floating-controls");
    const _deskTopRightControls = document.querySelector(".desk-top-right-controls");
    const _deskSessionTitleTextEl = document.getElementById("deskSessionTitleText");
    const DESK_SELECTED_KEY = "agent_window_hub_selected_session";
    const DESK_SIDEBAR_WIDTH_KEY = "agent_window_hub_sidebar_width";
    const DESK_SIDEBAR_OPEN_KEY = "agent_window_hub_sidebar_open";
    const DESK_AUTO_HEIGHT_KEY = "agent_window_hub_auto_window_height";
    const HUB_PENDING_ERROR_KEY = "agent_window_hub_pending_error";
    const DESK_DEFAULT_SIDEBAR_WIDTH = 262;
    const DESK_MIN_SIDEBAR_WIDTH = 160;
    const DESK_MAX_SIDEBAR_WIDTH = 420;
    const DESK_SWIPE_ACTION_WIDTH = 92;
    const DESK_SWIPE_OPEN_THRESHOLD = 40;
    const DESK_SIDEBAR_CLOSE_SWIPE_EDGE_PX = 36;
    const DESK_SIDEBAR_CLOSE_SWIPE_THRESHOLD = 54;
    const DESK_CHAT_URL_CACHE_LIMIT = 3;
    const DESK_HUB_MESSAGE_VISIBLE_MS = 5000;
    const hubChatUrls = createHubChatUrlResolver({
      cacheLimit: DESK_CHAT_URL_CACHE_LIMIT,
      cacheKey: (openHref) => String(openHref || "").trim(),
      wrapUrl: (url) => String(url || "").trim(),
      errorMessage: "chat url unavailable",
    });
    let _deskPanelActiveMode = "";
    let _deskPanelWidth = 0;
    let _deskOutwardResizeInFlight = false;
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

    function persistHubSettings(partial) {
      try {
        fetch("/settings", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
          body: new URLSearchParams(partial).toString(),
          cache: "no-store",
        }).catch(() => {});
      } catch (_) {}
    }

    const DESK_TEXT_SIZE_MIN = 8;
    const DESK_TEXT_SIZE_MAX = 16;
    const DESK_TEXT_SIZE_DEFAULT = 13;
    function currentDeskTextSizePx() {
      const raw = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--text-size"));
      return Number.isFinite(raw) ? raw : DESK_TEXT_SIZE_DEFAULT;
    }
    function applyDeskTextSizeLocal(px) {
      const clamped = Math.max(DESK_TEXT_SIZE_MIN, Math.min(DESK_TEXT_SIZE_MAX, Math.round(px)));
      document.documentElement.style.setProperty("--text-size", `${clamped}px`);
      return clamped;
    }
    function applyDeskTextSizeAndBroadcast(px) {
      const clamped = applyDeskTextSizeLocal(px);
      persistHubSettings({ text_size: String(clamped) });
      try {
        _deskChatFrame?.contentWindow?.postMessage({ type: "hub-text-size-changed", textSize: clamped }, "*");
      } catch (_) {}
    }
    function dispatchDeskNativeMenuAction(payload) {
      try {
        _deskChatFrame?.contentWindow?.postMessage({ type: "native-menu-action", payload }, "*");
      } catch (_) {}
    }
    function resetDeskChatView() {
      try {
        _deskChatFrame?.contentWindow?.postMessage({ type: "desktop-chat-reset" }, "*");
      } catch (_) {}
    }
    // Always on Top and Fit Height to Message are per-session toggles: both
    // start off on every launch and are never written back to hub settings.
    let _deskAlwaysOnTop = false;
    function applyDeskAlwaysOnTop(on) {
      _deskAlwaysOnTop = !!on;
      // Marks the settings button (its ⌥⌘P / menu is what toggles this).
      if (_deskAlwaysOnTop) document.documentElement.dataset.alwaysOnTop = "1";
      else delete document.documentElement.dataset.alwaysOnTop;
      const invoke = getTauriInvoke();
      if (typeof invoke === "function") {
        invoke("set_always_on_top", { on: _deskAlwaysOnTop }).catch((err) => {
          showDeskHubMessage(`always on top failed: ${err}`, { error: true });
        });
      }
    }
    function toggleDeskAlwaysOnTop() {
      applyDeskAlwaysOnTop(!_deskAlwaysOnTop);
    }

    // "Fit Height to Message" mode: on each agent-message stream completion the
    // chat frame reports the height it needs, and we resize the window to it
    // (width and x untouched). Between messages the user is free to resize.
    const DESK_FIT_BOTTOM_BUFFER = 16;
    // Mirrors DEFAULT_WINDOW_SIZE in tauri_app/src-tauri/src/main.rs -- the
    // height Fit Height restores on exit.
    const DESK_DEFAULT_WINDOW_HEIGHT = 896;
    let _deskAutoWindowHeight = false;
    let _deskLastFitTarget = 0;
    // Set on entering Fit Height: the first fit resize also snaps the window to
    // the compact width, so entry is one motion instead of a visible width jump
    // followed by a height shrink.
    let _deskFitWidthSnapPending = false;
    function pushDeskAutoWindowHeight() {
      try {
        _deskChatFrame?.contentWindow?.postMessage(
          { type: "hub-auto-window-height", on: _deskAutoWindowHeight },
          "*",
        );
      } catch (_) {}
    }
    function applyDeskFitHeightMin() {
      const invoke = getTauriInvoke();
      if (typeof invoke === "function") {
        invoke("set_fit_height_min", { enabled: _deskAutoWindowHeight }).catch(() => {});
      }
    }
    function setDeskAutoWindowHeight(on) {
      const next = !!on;
      if (next === _deskAutoWindowHeight) return;
      _deskAutoWindowHeight = next;
      _deskLastFitTarget = 0;
      // Fit Height hides the traffic lights, so the 26px title-bar inset at the
      // top of the window can shrink to match the 4px sides.
      if (next) document.documentElement.dataset.autoWindowHeight = "1";
      else delete document.documentElement.dataset.autoWindowHeight;
      // sessionStorage, not localStorage: a same-session hub reload keeps Fit
      // Height mode, but a fresh app launch has no entry and starts off.
      try { sessionStorage.setItem(DESK_AUTO_HEIGHT_KEY, next ? "1" : "0"); } catch (_) {}
      // The window is too short for the hub sidebar in this mode; sessions are
      // switched through a native menu instead (collapsed sidebar, on click).
      if (_deskAutoWindowHeight) setDeskSidebarOpen(false);
      // Fit Height needs the window minimum height dropped to ~0.
      applyDeskFitHeightMin();
      pushDeskAutoWindowHeight();
    }
    // Entering Fit Height (⌥⌘H or the menu item) snaps the window to the
    // compact width -- the ⌥⌘9 width that always got paired with it by hand --
    // folded into the first fit resize (see _deskFitWidthSnapPending), and pins
    // the window, since Fit Height is only useful kept in front. Leaving the
    // mode unpins and restores the default height (the width and position at
    // that point are kept -- entry shrank the height, so exit grows it back).
    function toggleDeskAutoWindowHeight() {
      if (_deskAutoWindowHeight) {
        setDeskAutoWindowHeight(false);
        applyDeskAlwaysOnTop(false);
        const invoke = getTauriInvoke();
        if (typeof invoke === "function") {
          invoke("set_window_height", { height: DESK_DEFAULT_WINDOW_HEIGHT }).catch((err) => {
            showDeskHubMessage(`fit height exit resize failed: ${err}`, { error: true });
          });
        }
        return;
      }
      resetDeskChatView();
      _deskFitWidthSnapPending = true;
      setDeskAutoWindowHeight(true);
      applyDeskAlwaysOnTop(true);
    }
    function fitDeskWindowHeight(contentHeight) {
      if (!_deskAutoWindowHeight) return;
      const content = Number(contentHeight);
      if (!Number.isFinite(content) || content <= 0) return;
      const invoke = getTauriInvoke();
      if (typeof invoke !== "function" || !_deskChatFrame) return;
      const iframeH = _deskChatFrame.getBoundingClientRect().height;
      // Chrome around the chat frame (hub header + window insets). Clamped so a
      // transient bad iframe measurement can't blow the target up to full screen.
      const overhead = Math.min(240, Math.max(0, window.innerHeight - iframeH));
      const target = Math.round(content + overhead + DESK_FIT_BOTTOM_BUFFER);
      // On the first fit after entering the mode, pull the window to the
      // compact width in the same resize (see toggleDeskAutoWindowHeight).
      const snapWidth = _deskFitWidthSnapPending;
      _deskFitWidthSnapPending = false;
      // The composer predict + ResizeObserver paths both fire per keystroke;
      // drop the redundant second call so it isn't two invokes per line.
      if (!snapWidth && Math.abs(target - _deskLastFitTarget) < 4) return;
      _deskLastFitTarget = target;
      invoke("set_window_height", { height: target, snapCompactWidth: snapWidth }).catch((err) => {
        showDeskHubMessage(`fit height failed: ${err}`, { error: true });
      });
    }

    // The chat view reset (which scrolls the transcript back to the bottom) is
    // sent *after* the window geometry lands, so the chat frame measures the
    // final size -- not the pre-preset one, whatever it was.
    async function resetDeskWindowState() {
      showDeskSidebarList({ open: true });
      setDeskSidebarWidth(DESK_DEFAULT_SIDEBAR_WIDTH);
      setDeskAutoWindowHeight(false);
      applyDeskAlwaysOnTop(false);
      const invoke = getTauriInvoke();
      if (typeof invoke === "function") {
        try {
          await invoke("reset_window_geometry");
        } catch (err) {
          showDeskHubMessage(`reset window failed: ${err}`, { error: true });
        }
      } else {
        showDeskHubMessage("reset window: no tauri invoke available", { error: true });
      }
      resetDeskChatView();
    }

    async function compactDeskWindowState(command = "compact_window_geometry", label = "compact window") {
      setDeskSidebarOpen(false);
      setDeskAutoWindowHeight(false);
      applyDeskAlwaysOnTop(false);
      const invoke = getTauriInvoke();
      if (typeof invoke === "function") {
        try {
          await invoke(command);
        } catch (err) {
          showDeskHubMessage(`${label} failed: ${err}`, { error: true });
        }
      } else {
        showDeskHubMessage(`${label}: no tauri invoke available`, { error: true });
      }
      resetDeskChatView();
    }

    // Pure reposition -- unlike reset/compact above, this touches only the
    // window's position (size untouched, no sidebar/chat-view/height reset).
    // The command is move_window_top / _top_left / _top_right / _center.
    async function moveDeskWindowToSpot(command) {
      const invoke = getTauriInvoke();
      if (typeof invoke !== "function") {
        showDeskHubMessage(`${command}: no tauri invoke available`, { error: true });
        return;
      }
      try {
        await invoke(command);
      } catch (err) {
        showDeskHubMessage(`${command} failed: ${err}`, { error: true });
      }
    }

    async function resizeDeskWindowAroundPane({ edge, delta, apply, rollback, label }) {
      if (_deskOutwardResizeInFlight || _deskAutoWindowHeight) return;
      const invoke = getTauriInvoke();
      if (typeof invoke !== "function") {
        showDeskHubMessage(`${label}: no tauri invoke available`, { error: true });
        return;
      }
      _deskOutwardResizeInFlight = true;
      let applied = false;
      try {
        const resizing = invoke("resize_window_from_edge", { edge, delta });
        apply();
        applied = true;
        await resizing;
      } catch (err) {
        if (applied) rollback();
        showDeskHubMessage(`${label} failed: ${err}`, { error: true });
      } finally {
        _deskOutwardResizeInFlight = false;
      }
    }

    function toggleDeskSidebar() {
      if (!_deskAutoWindowHeight) setDeskSidebarOpen(!isDeskSidebarOpen());
    }

    function toggleDeskRightPanel() {
      if (!_deskAutoWindowHeight) sendDeskPanelCommand("");
    }

    function toggleDeskSidebarOutward() {
      if (_deskAutoWindowHeight) return;
      const opening = !isDeskSidebarOpen();
      const width = _deskSidebarWidth;
      void resizeDeskWindowAroundPane({
        edge: "left",
        delta: opening ? width : -width,
        apply: () => setDeskSidebarOpen(opening),
        rollback: () => setDeskSidebarOpen(!opening),
        label: "toggle Hub sidebar outward",
      });
    }

    function toggleDeskRightPanelOutward() {
      if (_deskAutoWindowHeight) return;
      const width = _deskPanelWidth;
      if (!(width > 0)) {
        showDeskHubMessage("toggle right pane outward: pane width unavailable", { error: true });
        return;
      }
      const opening = !_deskPanelActiveMode;
      void resizeDeskWindowAroundPane({
        edge: "right",
        delta: opening ? width : -width,
        apply: () => {
          updateDeskPanelButtonState(opening ? "open" : "", width);
          sendDeskPanelCommand("");
        },
        rollback: () => {
          updateDeskPanelButtonState(opening ? "" : "open", width);
          sendDeskPanelCommand("");
        },
        label: "toggle right pane outward",
      });
    }

    window.addEventListener("keydown", (event) => {
      if (event.metaKey && event.altKey) {
        if (event.code === "KeyB") {
          event.preventDefault();
          toggleDeskSidebarOutward();
          return;
        }
        if (event.code === "KeyE") {
          event.preventDefault();
          toggleDeskRightPanelOutward();
          return;
        }
        if (event.code === "KeyT") {
          event.preventDefault();
          dispatchDeskNativeMenuAction({ action: "openTerminal" });
          return;
        }
        if (event.code === "KeyP") {
          event.preventDefault();
          toggleDeskAlwaysOnTop();
          return;
        }
        if (event.code === "KeyH") {
          event.preventDefault();
          void toggleDeskAutoWindowHeight();
          return;
        }
        if (event.code === "KeyR") {
          event.preventDefault();
          dispatchDeskNativeMenuAction({ action: "openFinder" });
          return;
        }
        if (event.code === "ArrowUp") {
          event.preventDefault();
          void moveDeskWindowToSpot("move_window_top");
          return;
        }
        if (event.code === "ArrowLeft") {
          event.preventDefault();
          void moveDeskWindowToSpot("move_window_top_left");
          return;
        }
        if (event.code === "ArrowRight") {
          event.preventDefault();
          void moveDeskWindowToSpot("move_window_top_right");
          return;
        }
        if (event.code === "ArrowDown") {
          event.preventDefault();
          void moveDeskWindowToSpot("move_window_center");
          return;
        }
      }
      if (event.metaKey && event.altKey && (event.code === "Digit0" || event.key === "0")) {
        event.preventDefault();
        void resetDeskWindowState();
        return;
      }
      if (event.metaKey && event.altKey && (event.code === "Digit9" || event.key === "9")) {
        event.preventDefault();
        void compactDeskWindowState();
        return;
      }
      if (event.metaKey && event.altKey && (event.code === "Digit8" || event.key === "8")) {
        event.preventDefault();
        void compactDeskWindowState("mini_window_geometry", "mini window");
        return;
      }
      if (event.metaKey && event.code === "Comma") {
        event.preventDefault();
        dispatchDeskNativeMenuAction({ action: "openSettingsFile" });
        return;
      }
      // In-app view toggles: plain ⌘ (like ⌘, and the text-size chords), not
      // the ⌥⌘ family that resizes/moves the window. No-ops in Fit Height,
      // where both panels are native menus.
      if (event.metaKey && !event.altKey && event.code === "KeyB") {
        event.preventDefault();
        toggleDeskSidebar();
        return;
      }
      if (event.metaKey && !event.altKey && event.code === "KeyE") {
        event.preventDefault();
        toggleDeskRightPanel();
        return;
      }
      if (event.metaKey && !event.altKey && !event.shiftKey && !event.ctrlKey && event.code === "KeyT") {
        event.preventDefault();
        dispatchDeskNativeMenuAction({ action: "openShell" });
        return;
      }
      if (event.metaKey && !event.altKey && !event.ctrlKey && event.code === "KeyR") {
        event.preventDefault();
        if (event.shiftKey) triggerDeskHubReload();
        else sendDeskChatAction("reloadChat");
        return;
      }
      if (event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey && event.code === "KeyN") {
        event.preventDefault();
        void startDeskNewSessionFlow();
        return;
      }
      if (event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey && /^Digit[1-9]$/.test(event.code || "")) {
        event.preventDefault();
        switchToDeskActiveSession(Number(event.code.slice(5)) - 1);
        return;
      }
      if (event.metaKey && event.shiftKey && !event.altKey && !event.ctrlKey && event.code === "KeyP") {
        event.preventDefault();
        postDeskChatFrameMessage({ type: "toggle-git-pin" });
        return;
      }
      if (!(event.metaKey || event.ctrlKey)) return;
      // event.code (physical key) instead of event.key: with metaKey held,
      // some WebViews don't reliably report the shift-modified character for
      // "=" (i.e. "+"), so matching on .key alone silently misses ⌘+. Also
      // accept "Semicolon": on JIS keyboards the physical key that types "+"
      // reports code "Semicolon", not "Equal" (confirmed via live testing).
      if (event.code === "Equal" || event.code === "Semicolon" || event.key === "=" || event.key === "+") {
        event.preventDefault();
        applyDeskTextSizeAndBroadcast(currentDeskTextSizePx() + 1);
      } else if (event.code === "Minus" || event.key === "-" || event.key === "_") {
        event.preventDefault();
        applyDeskTextSizeAndBroadcast(currentDeskTextSizePx() - 1);
      } else if (event.code === "Digit0" || event.key === "0") {
        event.preventDefault();
        applyDeskTextSizeAndBroadcast(DESK_TEXT_SIZE_DEFAULT);
      }
    });

    async function openAppearanceMenu() {
      const invoke = getTauriInvoke();
      if (typeof invoke !== "function" || !_deskSettingsBtn) return;
      const rect = _deskSettingsBtn.getBoundingClientRect();
      _deskSettingsBtn.classList.add("is-active");
      try {
        await invoke("show_appearance_menu", {
          payload: {
            x: Math.round(rect.left || 0),
            y: Math.round((rect.bottom || 0) + 2),
            themeDesktop: document.documentElement.dataset.themeDesktop || "dark",
            textSize: currentDeskTextSizePx(),
            textSizeDefault: DESK_TEXT_SIZE_DEFAULT,
            alwaysOnTop: _deskAlwaysOnTop,
            autoWindowHeight: _deskAutoWindowHeight,
          },
        });
      } catch (_) {
      } finally {
        _deskSettingsBtn.classList.remove("is-active");
      }
    }

    // Fit Height to Message shrinks the window past what the DOM session
    // popover needs, and a DOM popover can't cross the window edge. In that
    // mode the collapsed sidebar opens a native menu (which can) instead.
    let _deskSessionSwitcherItems = [];
    let _deskSessionSwitcherOpen = false;
    async function openDeskNativeSessionSwitcher() {
      const invoke = getTauriInvoke();
      if (typeof invoke !== "function" || !_deskSessionList || !_deskAppSidebarToggle) return;
      if (_deskSessionSwitcherOpen) return;
      const items = [];
      for (const child of Array.from(_deskSessionList.children)) {
        if (child.classList.contains("desk-section-label")) {
          items.push({ label: child.textContent.trim(), section: true });
        } else if (child.classList.contains("desk-swipe-row")) {
          const row = child.querySelector(".desk-session-row");
          const href = row?.dataset.openHref || "";
          if (!row || !href) continue;
          items.push({
            label: (row.querySelector(".desk-row-name")?.textContent || row.dataset.sessionName || "").trim(),
            current: row.classList.contains("is-selected"),
            href,
            name: row.dataset.sessionName || "",
          });
        }
      }
      if (!items.some((it) => !it.section)) return;
      _deskSessionSwitcherItems = items;
      const rect = _deskAppSidebarToggle.getBoundingClientRect();
      _deskSessionSwitcherOpen = true;
      try {
        await invoke("show_session_switcher_menu", {
          payload: {
            x: Math.round(rect.right || 0),
            y: Math.round(rect.top || 0),
            items: items.map(({ label, section, current }) => ({ label, section: !!section, current: !!current })),
          },
        });
      } catch (_) {
      } finally {
        _deskSessionSwitcherOpen = false;
      }
    }

    // Fit Height to Message: the right panel can't paint past the tiny window,
    // so its toggle pops the uncommitted-file list through a native menu. The
    // list lives in the chat frame; ask it, then build the menu.
    let _deskGitChangesItems = [];
    let _deskGitChangesOpen = false;
    function requestDeskGitChanges(timeoutMs = 4000) {
      return new Promise((resolve) => {
        const frameWin = _deskChatFrame?.contentWindow;
        if (!frameWin) { resolve(null); return; }
        let settled = false;
        const done = (value) => {
          if (settled) return;
          settled = true;
          window.removeEventListener("message", onMsg);
          resolve(value);
        };
        const onMsg = (e) => {
          if (e.source !== frameWin || !e.data || e.data.type !== "desk-git-changes") return;
          done(e.data);
        };
        window.addEventListener("message", onMsg);
        setTimeout(() => done(null), timeoutMs);
        frameWin.postMessage({ type: "desk-git-changes-request" }, "*");
      });
    }
    function buildDeskGitChangesItems(files) {
      if (!files.length) return [{ label: "No uncommitted changes", section: true }];
      const norm = files
        .map((f) => ({
          path: String(f.path || "").trim(),
          ins: Number(f.ins) || 0,
          dels: Number(f.dels) || 0,
          untracked: !!f.untracked,
        }))
        .filter((f) => f.path)
        .sort((a, b) => a.path.localeCompare(b.path));
      const ins = norm.reduce((n, f) => n + f.ins, 0);
      const dels = norm.reduce((n, f) => n + f.dels, 0);
      const items = [{ label: `${norm.length} file${norm.length === 1 ? "" : "s"}  +${ins} -${dels}`, section: true }];
      const base = (p) => { const s = p.lastIndexOf("/"); return s >= 0 ? p.slice(s + 1) : p; };
      const push = (f, withStat) => {
        const stat = withStat && (f.ins || f.dels) ? `  +${f.ins} -${f.dels}` : "";
        items.push({ label: `${base(f.path)}${stat}`, path: f.path, untracked: f.untracked });
      };
      for (const f of norm.filter((f) => !f.untracked)) push(f, true);
      const untracked = norm.filter((f) => f.untracked);
      if (untracked.length) {
        items.push({ label: "Untracked", section: true });
        for (const f of untracked) push(f, false);
      }
      return items;
    }
    async function openDeskNativeGitChanges() {
      const invoke = getTauriInvoke();
      if (typeof invoke !== "function" || !_deskPanelToggle || _deskGitChangesOpen) return;
      _deskGitChangesOpen = true;
      try {
        const data = await requestDeskGitChanges();
        const files = Array.isArray(data?.files) ? data.files : [];
        const items = data?.error
          ? [{ label: "Git unavailable", section: true }]
          : buildDeskGitChangesItems(files);
        _deskGitChangesItems = items;
        const rect = _deskPanelToggle.getBoundingClientRect();
        await invoke("show_git_changes_menu", {
          payload: {
            x: Math.round(rect.right || 0),
            y: Math.round(rect.bottom || 0),
            items: items.map(({ label, section }) => ({ label, section: !!section })),
          },
        });
      } catch (_) {
      } finally {
        _deskGitChangesOpen = false;
      }
    }

    window.addEventListener("native-menu-action", (event) => {
      const detail = event.detail || {};
      if (detail.action === "switchSession") {
        const item = _deskSessionSwitcherItems[Number(detail.mode)];
        if (item && item.href) openSessionFrame(item.href, item.name);
        return;
      }
      if (detail.action === "gitChange") {
        const item = _deskGitChangesItems[Number(detail.mode)];
        if (item && item.path) {
          _deskChatFrame?.contentWindow?.postMessage(
            { type: "desk-open-git-file", path: item.path, untracked: !!item.untracked }, "*",
          );
        }
        return;
      }
      if (detail.action === "renameSession") {
        if (_deskContextSessionName) beginDeskSessionRename(_deskContextSessionName);
        return;
      }
      if (detail.action === "copyWorkspacePath") {
        if (_deskContextSessionName) void copyDeskSessionWorkspace(_deskContextSessionName);
        return;
      }
      if (detail.action === "changeWorkspace") {
        if (_deskContextSessionName) void changeDeskSessionWorkspace(_deskContextSessionName);
        return;
      }
      if (detail.action === "resetAgents") {
        if (_deskContextSessionName) void resetDeskSessionAgents(_deskContextSessionName);
        return;
      }
      if (detail.action === "archiveSession") {
        if (_deskContextSessionName) void runDeskContextAction(_deskContextSessionName, "kill");
        return;
      }
      if (detail.action === "deleteSession") {
        if (_deskContextSessionName) void runDeskContextAction(_deskContextSessionName, "delete-archived");
        return;
      }
      if (detail.action === "reviveSession") {
        if (_deskContextSessionName) {
          openSessionFrame(
            `/revive-session?session=${encodeURIComponent(_deskContextSessionName)}`,
            _deskContextSessionName,
          );
        }
        return;
      }
      if (detail.action === "textSize") {
        const mode = String(detail.mode || "");
        if (mode === "increase") {
          applyDeskTextSizeAndBroadcast(currentDeskTextSizePx() + 1);
        } else if (mode === "decrease") {
          applyDeskTextSizeAndBroadcast(currentDeskTextSizePx() - 1);
        } else if (mode === "actual") {
          applyDeskTextSizeAndBroadcast(DESK_TEXT_SIZE_DEFAULT);
        }
        return;
      }
      if (detail.action === "resetWindow") {
        void resetDeskWindowState();
        return;
      }
      if (detail.action === "compactWindow") {
        void compactDeskWindowState();
        return;
      }
      if (detail.action === "miniWindow") {
        void compactDeskWindowState("mini_window_geometry", "mini window");
        return;
      }
      if (detail.action === "moveWindowTop") {
        void moveDeskWindowToSpot("move_window_top");
        return;
      }
      if (detail.action === "moveWindowTopLeft") {
        void moveDeskWindowToSpot("move_window_top_left");
        return;
      }
      if (detail.action === "moveWindowTopRight") {
        void moveDeskWindowToSpot("move_window_top_right");
        return;
      }
      if (detail.action === "moveWindowCenter") {
        void moveDeskWindowToSpot("move_window_center");
        return;
      }
      if (detail.action === "toggleHubSidebar") {
        toggleDeskSidebar();
        return;
      }
      if (detail.action === "toggleRightPane") {
        toggleDeskRightPanel();
        return;
      }
      if (detail.action === "toggleHubSidebarOutward") {
        toggleDeskSidebarOutward();
        return;
      }
      if (detail.action === "toggleRightPaneOutward") {
        toggleDeskRightPanelOutward();
        return;
      }
      if (detail.action === "toggleAlwaysOnTop") {
        toggleDeskAlwaysOnTop();
        return;
      }
      if (detail.action === "toggleAutoWindowHeight") {
        void toggleDeskAutoWindowHeight();
        return;
      }
      if (detail.action === "theme") {
        const theme = String(detail.theme || "").trim().toLowerCase();
        if (theme !== "system" && theme !== "light" && theme !== "dark") return;
        applyIncomingThemeDesktop(theme);
        persistHubSettings({ theme_desktop: theme });
        return;
      }
      dispatchDeskNativeMenuAction(detail);
    });

    let _hubSessionsCache = { active: [], archived: [] };
    let _deskPreviewRevisions = new Map();
    const _deskUnreadSessions = new Set();
    let _deskSessionsRequestSeq = 0;
    let _deskSessionsRenderedOnce = false;
    let _deskSelectedSessionName = "";
    let _deskChatFrameLoadedUrl = "";
    let _deskOpenToken = 0;
    let _deskSidebarWidth = DESK_DEFAULT_SIDEBAR_WIDTH;
    let _deskOpenSwipeRow = null;
    let _deskContextSessionName = "";
    let _deskSessionRename = null;
    let _deskNewSessionStarting = false;
    let _deskHubMessageTimer = 0;

    function updateDeskWindowTitle(name) {
      const textEl = _deskSessionTitleTextEl;
      if (!textEl) return;
      textEl.textContent = "";
      if (name) {
        const port = findSessionRecord(name)?.session?.chat_port;
        // Two spans so updateDeskChromeOverflow can drop just the "(port)"
        // suffix a step before hiding the whole label.
        const nameEl = document.createElement("span");
        nameEl.className = "desk-session-title-name";
        nameEl.textContent = name;
        const portEl = document.createElement("span");
        portEl.className = "desk-session-title-port";
        portEl.textContent = port ? ` (${port})` : "";
        textEl.append(nameEl, portEl);
      }
      updateDeskChromeOverflow();
    }
    function updateDeskPanelButtonState(mode = "", width = _deskPanelWidth) {
      _deskPanelActiveMode = mode ? "open" : "";
      const nextWidth = Math.max(0, Number(width) || 0);
      if (nextWidth > 0) _deskPanelWidth = nextWidth;
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
      if (active) {
        const card = _deskReloadShell.querySelector(".desk-reload-shell-card");
        if (card) {
          card.classList.remove("is-error");
          card.innerHTML = '<span class="desk-reload-shell-spinner" aria-hidden="true"></span>';
        }
      }
      _deskReloadShell.hidden = !active;
      _deskReloadShell.classList.toggle("visible", !!active);
    }
    function triggerDeskHubReload() {
      if (!_deskReloadBtn || _deskReloadBtn.classList.contains("restarting")) return;
      setDeskReloadShell(true);
      beginHubRestart(_deskReloadBtn);
    }
    function failDeskOpen(message) {
      const card = _deskReloadShell?.querySelector(".desk-reload-shell-card");
      if (card) {
        card.classList.add("is-error");
        card.textContent = String(message || "open session failed");
      }
      if (_deskReloadShell) {
        _deskReloadShell.hidden = false;
        _deskReloadShell.classList.add("visible");
      }
      setDeskChatLoading(false);
      showDeskSidebarList({ open: true });
    }

    function showDeskHubMessage(message = "", { error = false } = {}) {
      if (!_deskHubMessage) return;
      window.clearTimeout(_deskHubMessageTimer);
      _deskHubMessageTimer = 0;
      const text = String(message || "").trim();
      _deskHubMessage.textContent = text;
      _deskHubMessage.classList.toggle("is-error", !!text && error);
      _deskHubMessage.hidden = !text;
      if (text) {
        _deskHubMessageTimer = window.setTimeout(() => {
          _deskHubMessage.textContent = "";
          _deskHubMessage.classList.remove("is-error");
          _deskHubMessage.hidden = true;
          _deskHubMessageTimer = 0;
        }, DESK_HUB_MESSAGE_VISIBLE_MS);
      }
    }

    async function copyDeskText(text) {
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(text);
          return;
        } catch (_) {}
      }
      const input = document.createElement("textarea");
      input.value = text;
      input.style.cssText = "position:fixed;opacity:0;top:0;left:0";
      document.body.appendChild(input);
      input.focus();
      input.select();
      const copied = document.execCommand("copy");
      input.remove();
      if (!copied) throw new Error("Clipboard is unavailable.");
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
      frameWin.postMessage({ type: "open-chat-header-menu", anchor }, "*");
    }
    function sendDeskPanelCommand(mode) {
      const frameWin = _deskChatFrame?.contentWindow;
      if (!frameWin) return;
      frameWin.postMessage({ type: "desktop-panel", mode: String(mode || "") }, "*");
    }
    function sendDeskChatAction(action) {
      const frameWin = _deskChatFrame?.contentWindow;
      if (!frameWin) return;
      frameWin.postMessage({
        type: "native-menu-action",
        payload: { action: String(action || "") },
      }, "*");
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
      showDeskHubMessage(message, { error: true });
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
        _deskAppSidebarToggle.classList.toggle("is-active", isDeskSessionSidebarOpen());
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
      postDeskChatFrameMessage({ type: "parent-attach-drag", active: !!active });
    };
    let deskAttachDragClearTimer = 0;
    const showDeskAttachDrag = () => {
      if (deskAttachDragClearTimer) {
        clearTimeout(deskAttachDragClearTimer);
        deskAttachDragClearTimer = 0;
      }
      setDeskAttachDragActive(true);
    };
    const hideDeskAttachDrag = ({ immediate = false } = {}) => {
      if (deskAttachDragClearTimer) {
        clearTimeout(deskAttachDragClearTimer);
        deskAttachDragClearTimer = 0;
      }
      if (immediate) {
        setDeskAttachDragActive(false);
        return;
      }
      deskAttachDragClearTimer = setTimeout(() => {
        setDeskAttachDragActive(false);
        deskAttachDragClearTimer = 0;
      }, 120);
    };
    const forwardDeskDroppedFiles = (files) => {
      const dropped = Array.from(files || []).filter((file) => file && typeof file.name === "string");
      if (!dropped.length) return false;
      return postDeskChatFrameMessage({ type: "parent-drop-files", files: dropped });
    };
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
        if (name) localStorage.setItem(DESK_SELECTED_KEY, name);
        else localStorage.removeItem(DESK_SELECTED_KEY);
      } catch (_) {}
    }

    function getRequestedDeskSelection() {
      try {
        const queryName = new URL(window.location.href).searchParams.get("session");
        if (queryName) return queryName;
      } catch (_) {}
      try {
        return localStorage.getItem(DESK_SELECTED_KEY) || "";
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

    function buildSessionOpenHref(sessionName, _archived) {
      return `/open-session?session=${encodeURIComponent(sessionName)}`;
    }

    // ⌘1..⌘9 -> the 1st..9th active session (sidebar order). Capped at 9;
    // archived / warning sessions are not addressable this way.
    function switchToDeskActiveSession(index) {
      const target = (_hubSessionsCache.active || [])[index];
      if (!target || !target.name || target.name === _deskSelectedSessionName) return;
      openSessionFrame(buildSessionOpenHref(target.name, false), target.name);
    }

    function systemPrefersDark() {
      try { return window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (_) { return true; }
    }

    function deskChatThemeFromDesktop(themeDesktop) {
      const value = String(
        themeDesktop || document.documentElement.dataset.themeDesktop || document.documentElement.dataset.theme || "dark"
      ).trim().toLowerCase();
      if (value === "system") return systemPrefersDark() ? "dark" : "light";
      return value === "light" ? "light" : "dark";
    }

    function applyDeskChatTheme(themeDesktop) {
      const resolvedThemeDesktop = themeDesktop || document.documentElement.dataset.themeDesktop || document.documentElement.dataset.theme || "dark";
      const chatTheme = deskChatThemeFromDesktop(resolvedThemeDesktop);
      try {
        const root = _deskChatFrame?.contentDocument?.documentElement;
        if (root) {
          root.dataset.theme = chatTheme;
          if (resolvedThemeDesktop) {
            root.dataset.themeDesktop = resolvedThemeDesktop;
          } else {
            delete root.dataset.themeDesktop;
          }
        }
      } catch (_) {}
      try {
        _deskChatFrame?.contentWindow?.postMessage(
          { type: "hub-theme-changed", theme: chatTheme, chatTheme, themeDesktop: resolvedThemeDesktop },
          "*"
        );
      } catch (_) {}
    }

    function applyIncomingThemeDesktop(themeDesktopRaw) {
      const themeDesktop = String(
        themeDesktopRaw || document.documentElement.dataset.themeDesktop || "dark"
      ).trim().toLowerCase();
      const hubTheme = themeDesktop === "system"
        ? (systemPrefersDark() ? "dark" : "light")
        : (themeDesktop === "light" ? "light" : "dark");
      document.documentElement.dataset.theme = hubTheme;
      document.documentElement.dataset.themeDesktop = themeDesktop;
      applyDeskChatTheme(themeDesktop);
    }

    if ((document.documentElement.dataset.themeDesktop || "").trim().toLowerCase() === "system") {
      applyIncomingThemeDesktop("system");
    }
    try {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
        if ((document.documentElement.dataset.themeDesktop || "").trim().toLowerCase() === "system") {
          applyIncomingThemeDesktop("system");
        }
      });
    } catch (_) {}

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

    window.__agentWindowRefreshTauriFrames = () => {
      if (!isTauriDesktopApp()) return;
      if (!_deskChatFrame) return;
      const current = _deskChatFrameLoadedUrl || String(_deskChatFrame.getAttribute("src") || _deskChatFrame.src || "");
      if (!current || current === "about:blank") return;
      const next = buildDeskChatFrameUrl(current);
      if (next && normalizeComparableUrl(current) !== normalizeComparableUrl(next)) {
        navigateDeskChatFrame(next);
      }
    };

    function cacheDeskChatUrl(cacheKey, chatUrl) {
      hubChatUrls.write(cacheKey, chatUrl);
    }

    function syncDeskChatShellState() {
      if (_deskChatFrame) {
        if (isDeskSessionSidebarOpen()) _deskChatFrame.dataset.hubSidebarOpen = "1";
        else delete _deskChatFrame.dataset.hubSidebarOpen;
      }
      try {
        _deskChatFrame?.contentWindow?.postMessage({
          type: "hub-sidebar-state",
          open: !!isDeskSessionSidebarOpen(),
        }, "*");
      } catch (_) {}
    }

    function syncDeskSidebarResizerVisibility() {
      if (!_deskSidebarResizer) return;
      if (isTauriDesktopApp()) {
        _deskSidebarResizer.hidden = !isDeskSidebarOpen();
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
      try { sessionStorage.setItem(DESK_SIDEBAR_OPEN_KEY, isOpen ? "1" : "0"); } catch (_) {}
      if (_deskAppSidebarToggle) {
        _deskAppSidebarToggle.classList.toggle("is-active", isDeskSessionSidebarOpen());
      }
      syncDeskSidebarResizerVisibility();
      syncDeskChatShellState();
    }

    function isDeskSidebarOpen() {
      return !!(_deskWorkbench && _deskWorkbench.classList.contains("sidebar-open"));
    }

    function isDeskSessionSidebarOpen() {
      return isDeskSidebarOpen();
    }

    function showDeskSidebarList({ open = true } = {}) {
      if (open) setDeskSidebarOpen(true);
    }

    function initDeskSidebarHoverPopover() {
      if (!_deskAppSidebarToggle) return;

      let hoverPopover = null;
      let dismissTimer = null;

      function cancelDismiss() {
        if (dismissTimer) { clearTimeout(dismissTimer); dismissTimer = null; }
      }

      function dismiss() {
        cancelDismiss();
        if (hoverPopover) { hoverPopover.remove(); hoverPopover = null; }
      }

      function scheduleDismiss() {
        cancelDismiss();
        dismissTimer = setTimeout(dismiss, 60);
      }

      function animatePopoverIn(popover) {
        if (!popover || typeof popover.animate !== "function") return;
        if (window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) return;

        const frames = [];
        const steps = 48;
        const frequency = Math.PI * 2.55;
        const damping = 3.8;
        for (let i = 0; i <= steps; i += 1) {
          const progress = i / steps;
          const decay = Math.exp(-damping * progress);
          const wave = Math.sin((frequency * progress) - (Math.PI / 2));
          const opacity = Math.sin((Math.PI / 2) * Math.min(1, progress / 0.42));
          let scaleX = 1 + (0.14 * decay * wave);
          let scaleY = 1 + (0.20 * decay * wave);
          if (i === steps) {
            scaleX = 1;
            scaleY = 1;
          }
          frames.push({
            opacity: String(opacity),
            transform: `scale(${scaleX.toFixed(4)}, ${scaleY.toFixed(4)})`,
          });
        }
        const animation = popover.animate(frames, {
          duration: 360,
          easing: "linear",
          fill: "both",
        });
        animation.addEventListener("finish", () => {
          popover.style.opacity = "";
          popover.style.transform = "";
        }, { once: true });
      }

      function open() {
        cancelDismiss();
        if (isDeskSidebarOpen()) return;
        if (_deskAutoWindowHeight) return; // this mode switches sessions via a native menu on click
        if (hoverPopover) return;
        if (!_deskSessionList) return;

        const listEl = document.createElement("div");
        listEl.className = "desk-sidebar-hover-list";
        for (const child of Array.from(_deskSessionList.children)) {
          if (child.classList.contains("desk-section-label")) {
            listEl.appendChild(child.cloneNode(true));
          } else if (child.classList.contains("desk-swipe-row")) {
            const row = child.querySelector(".desk-session-row");
            if (row) {
              const clone = row.cloneNode(true);
              clone.querySelectorAll(".desk-row-hover-action").forEach(b => b.remove());
              listEl.appendChild(clone);
            }
          }
        }
        if (!listEl.children.length) return;

        hoverPopover = document.createElement("div");
        hoverPopover.className = "desk-sidebar-hover-popover";
        hoverPopover.addEventListener("mouseenter", cancelDismiss);
        hoverPopover.addEventListener("mouseleave", scheduleDismiss);
        hoverPopover.addEventListener("click", (event) => {
          const row = event.target.closest(".desk-session-row");
          if (!row) return;
          const href = row.dataset.openHref;
          const name = row.dataset.sessionName || "";
          if (href) { dismiss(); openSessionFrame(href, name); }
        });
        hoverPopover.appendChild(listEl);
        document.body.appendChild(hoverPopover);

        const wbRect = _deskWorkbench ? _deskWorkbench.getBoundingClientRect() : null;
        const gap = 10;
        hoverPopover.style.top = `${Math.round((wbRect ? wbRect.top : _deskAppSidebarToggle.getBoundingClientRect().bottom) + gap)}px`;
        hoverPopover.style.left = `${Math.round((wbRect ? wbRect.left : 0) + gap)}px`;
        animatePopoverIn(hoverPopover);

        const updatePopoverFade = () => {
          listEl.dataset.scrollFade = computeScrollFadeState(listEl);
        };
        updatePopoverFade();
        listEl.addEventListener("scroll", updatePopoverFade, { passive: true });
      }

      _deskAppSidebarToggle.addEventListener("mouseenter", open);
      _deskAppSidebarToggle.addEventListener("mouseleave", scheduleDismiss);

      if (_deskWorkbench) {
        new MutationObserver(() => {
          if (isDeskSidebarOpen()) dismiss();
        }).observe(_deskWorkbench, { attributes: true, attributeFilter: ["class"] });
      }
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

    async function startDeskNewSessionFlow() {
      if (_deskNewSessionStarting) return;
      _deskNewSessionStarting = true;
      _deskNewSessionToggle?.classList.add("archived");
      showDeskHubMessage();
      try {
        const workspace = await pickWorkspaceForNewSession();
        if (!workspace) return;
        const res = await fetch("/start-session-draft", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspace }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok || !data.chat_url) {
          throw new Error(data.error || "Failed to open draft session.");
        }
        openChatInDesk(data.chat_url, data.session || "");
        showDeskHubMessage(data.notice || "", { error: !!data.notice });
        // Leave the sidebar however it was -- New Session is reachable with it
        // closed (⌘N). Phone still dismisses its overlay so the new chat shows.
        if (isPhoneViewport()) {
          setDeskSidebarOpen(false);
        }
        void refreshHubSessions(true, { skipRestore: true });
      } catch (err) {
        showDeskHubMessage(err?.message || "Failed to open draft session.", { error: true });
      } finally {
        _deskNewSessionStarting = false;
        _deskNewSessionToggle?.classList.remove("archived");
      }
    }

    // One persistent iframe is reused for every session. Assigning `.src` is a
    // navigation that appends an entry to the Hub's joint session history, and
    // WebKit then keeps the whole outgoing chat Document resident (bfcache) so
    // "back" would be instant -- measured at ~+150 MB per switch, never freed.
    // location.replace() navigates without adding a history entry (verified to
    // work even though the chat frame is a cross-origin per-session origin), so
    // the outgoing Document has no entry pinning it and can be torn down.
    function navigateDeskChatFrame(url) {
      const target = String(url || "") || "about:blank";
      _deskChatFrameLoadedUrl = target === "about:blank" ? "" : target;
      const win = _deskChatFrame && _deskChatFrame.contentWindow;
      if (win) {
        try {
          win.location.replace(target);
          return;
        } catch (_) {
          // detached document -- fall back to an attribute navigation
        }
      }
      if (_deskChatFrame) _deskChatFrame.src = target;
    }

    function clearDeskChatFrame() {
      navigateDeskChatFrame("about:blank");
      setDeskChatLoading(false);
    }

    function clearDeskSelection() {
      _deskOpenToken += 1;
      _deskSelectedSessionName = "";
      updateDeskWindowTitle("");
      persistDeskSelection("");
      setDeskSelectionInUrl("");
      clearDeskChatFrame();
      renderDesktopSessions(_hubSessionsCache.active, _hubSessionsCache.archived);
    }

    function openChatInDesk(url, name) {
      if (!_deskChatFrame) return;
      _deskSelectedSessionName = name || "";
      _deskUnreadSessions.delete(_deskSelectedSessionName);
      updateDeskWindowTitle(_deskSelectedSessionName);
      persistDeskSelection(_deskSelectedSessionName);
      setDeskSelectionInUrl(_deskSelectedSessionName);
      if (isDeskSessionSidebarOpen()) _deskChatFrame.dataset.hubSidebarOpen = "1";
      else delete _deskChatFrame.dataset.hubSidebarOpen;
      if (_deskSelectedSessionName) {
        cacheDeskChatUrl(buildSessionOpenHref(_deskSelectedSessionName, false), url);
      }
      const frameUrl = buildDeskChatFrameUrl(url);
      if (frameUrl) {
        const currentUrl = normalizeComparableUrl(_deskChatFrameLoadedUrl);
        const nextUrl = normalizeComparableUrl(frameUrl);
        if (!currentUrl || currentUrl !== nextUrl) {
          setDeskChatLoading(true);
          navigateDeskChatFrame(frameUrl);
        } else {
          setDeskChatLoading(false);
        }
      } else {
        setDeskChatLoading(false);
      }
      renderDesktopSessions(_hubSessionsCache.active, _hubSessionsCache.archived);
    }

    function resolveSessionChatUrl(openHref, { force = false } = {}) {
      return hubChatUrls.resolve(openHref, "", { force });
    }

    async function openSessionFrame(openHref, name) {
      if (!name) {
        failDeskOpen("Session not found");
        return;
      }
      setDeskReloadShell(false);
      const needsReviveTransition = /^\/revive-session(?:[/?]|$)/.test(String(openHref || ""));
      const archived = !!findSessionRecord(name)?.archived;
      const closeOnOpen = isPhoneViewport();
      _deskSelectedSessionName = name;
      updateDeskWindowTitle(name);
      persistDeskSelection(name);
      setDeskSelectionInUrl(name);
      renderDesktopSessions(_hubSessionsCache.active, _hubSessionsCache.archived);
      setDeskChatLoading(true);
      const openToken = ++_deskOpenToken;
      try {
        // Only one archived chat server remains alive. Opening another archived
        // session stops the previous one, so its cached URL cannot be reused.
        const chatUrl = await resolveSessionChatUrl(openHref, { force: archived || needsReviveTransition });
        if (openToken !== _deskOpenToken) return;
        if (needsReviveTransition) {
          await refreshHubSessions(true, { skipRestore: true });
          if (openToken !== _deskOpenToken) return;
        }
        openChatInDesk(chatUrl, name);
        if (closeOnOpen) setDeskSidebarOpen(false);
      } catch (err) {
        if (openToken !== _deskOpenToken) return;
        failDeskOpen(err?.message || "open session failed");
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

    function deskSessionOpenHref(row) {
      const name = row?.dataset.sessionName || "";
      
      return row?.dataset.openHref || "";
    }

    function openDeskSessionRow(row) {
      if (!row) return false;
      const href = deskSessionOpenHref(row);
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

    function maybeRestoreDeskSelection() {
      if (_deskSelectedSessionName) {
        if (findSessionRecord(_deskSelectedSessionName)) return;
        clearDeskSelection();
        showDeskSidebarList({ open: true });
        return;
      }
      const requested = getRequestedDeskSelection();
      if (requested) {
        const match = findSessionRecord(requested);
        if (match && !match.archived) {
          openSessionFrame(buildSessionOpenHref(requested, false), requested);
          return;
        }
        persistDeskSelection("");
        setDeskSelectionInUrl("");
        failDeskOpen("Session not found");
        showDeskSidebarList({ open: true });
        return;
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
      const sessionName = String(session.name);
      const archivedClass = archived ? " archived" : "";
      const selectedClass = _deskSelectedSessionName === sessionName ? " is-selected" : "";
      const isSelected = _deskSelectedSessionName === sessionName;
      const unreadClass = !isSelected && _deskUnreadSessions.has(sessionName) ? " is-unread" : "";
      const showDelete = archived && isSelected;
      const swipeActionLabel = showDelete ? "Delete" : (archived ? "Revive" : "Archive");
      const swipeActionRoute = showDelete ? "delete-archived" : (archived ? "revive" : "kill");
      const trashSvg = `<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"></path><path d="M19 6l-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
      const killSvg = `<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>`;
      const reviveSvg = `<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>`;
      const actionSvg = showDelete ? trashSvg : (archived ? reviveSvg : killSvg);
      const previewText = String(session.latest_message_preview || "").trim();
      const previewSender = String(session.latest_message_sender || "").trim();
      const previewDisplay = previewSender ? `${previewSender} ${previewText}` : previewText;
      const previewHtml = previewText
        ? `<div class="desk-row-preview">${esc(previewDisplay)}</div>`
        : "";
      return `<div class="desk-swipe-row" data-session-name="${esc(sessionName)}" data-desk-swipe-kind="${esc(swipeActionRoute)}">` +
        `<div class="desk-swipe-action-rail">` +
          `<button type="button" class="desk-swipe-action-btn" data-desk-swipe-action="${esc(swipeActionRoute)}" aria-label="${esc(swipeActionLabel + " " + sessionName)}">` +
            actionSvg +
            `<span>${esc(swipeActionLabel)}</span>` +
          `</button>` +
        `</div>` +
        `<div class="desk-swipe-track">` +
          `<div class="desk-session-row desk-action-session-row${archivedClass}${selectedClass}${unreadClass}" data-session-name="${esc(sessionName)}" data-open-href="${buildSessionOpenHref(sessionName, archived)}" tabindex="0" role="button" aria-current="${selectedClass ? "page" : "false"}">` +
            `<div class="desk-row-head">` +
                `<div class="desk-row-main">` +
                  `<span class="desk-row-bullet" aria-hidden="true"><i></i></span>` +
                  `<div class="desk-row-stack">` +
                    `<div class="desk-row-name">${esc(sessionName)}</div>` +
                    previewHtml +
                  `</div>` +
                `</div>` +
                `<button type="button" class="desk-row-hover-action" data-desk-hover-action="${esc(swipeActionRoute)}" aria-label="${esc(swipeActionLabel + " " + sessionName)}" title="${esc(swipeActionLabel)}">` +
                  actionSvg +
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
      showDeskHubMessage();
      const isDelete = kind === "delete-archived";
      const confirmed = isTauriDesktopApp()
        ? true
        : (isDelete
          ? confirm("Delete archived logs for " + sessionName + "? This cannot be undone.")
          : confirm("Archive " + sessionName + "?"));
      if (!confirmed) return;
      const route = isDelete ? "/delete-archived-session" : "/kill-session";
      const isSelected = _deskSelectedSessionName === sessionName;
      try {
        const response = await fetch(
          `${route}?session=${encodeURIComponent(sessionName)}&format=json&ts=${Date.now()}`,
          { cache: "no-store" }
        );
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || (isDelete ? "Failed to delete session." : "Failed to archive session."));
        }
        const activeHref = buildSessionOpenHref(sessionName, false);
        const archivedHref = buildSessionOpenHref(sessionName, true);
        hubChatUrls.forget(activeHref);
        hubChatUrls.forget(archivedHref);
        if (isSelected) {
          _deskOpenToken += 1;
          _deskSelectedSessionName = "";
          updateDeskWindowTitle("");
          persistDeskSelection("");
          setDeskSelectionInUrl("");
        }
        await refreshHubSessions(true, { skipRestore: true });
        if (!isSelected) return;
        clearDeskSelection();
        showDeskSidebarList({ open: true });
      } catch (err) {
        showDeskHubMessage(
          err?.message || (isDelete ? "Failed to delete session." : "Failed to archive session."),
          { error: true },
        );
      }
    }

    async function renameDeskSession(oldName, requestedName) {
      const newName = String(requestedName || "").trim();
      if (!oldName) return false;
      if (oldName === newName) return true;
      showDeskHubMessage();
      try {
        const response = await fetch("/rename-session", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
          body: new URLSearchParams({ old_name: oldName, new_name: newName }).toString(),
          cache: "no-store",
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "Failed to rename session.");
        }
        const renamed = String(data.new_name || newName);
        hubChatUrls.forget(buildSessionOpenHref(oldName, false));
        hubChatUrls.forget(buildSessionOpenHref(oldName, true));
        if (_deskUnreadSessions.delete(oldName)) _deskUnreadSessions.add(renamed);
        if (_deskSelectedSessionName === oldName) {
          _deskSelectedSessionName = renamed;
          updateDeskWindowTitle(renamed);
          persistDeskSelection(renamed);
          setDeskSelectionInUrl(renamed);
        }
        return true;
      } catch (err) {
        showDeskHubMessage(err?.message || "Failed to rename session.", { error: true });
        return false;
      }
    }

    async function changeDeskSessionWorkspace(sessionName) {
      if (!sessionName) return;
      showDeskHubMessage();
      let picked;
      try {
        const res = await fetch("/pick-workspace", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
          cache: "no-store",
        });
        picked = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(picked.error || "Workspace picker failed.");
      } catch (err) {
        showDeskHubMessage(err?.message || "Workspace picker failed.", { error: true });
        return;
      }
      if (picked.canceled || !picked.path) return;
      try {
        const res = await fetch("/change-session-workspace", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
          body: new URLSearchParams({ session: sessionName, workspace: picked.path }).toString(),
          cache: "no-store",
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) throw new Error(data.error || "Failed to change workspace.");
      } catch (err) {
        showDeskHubMessage(err?.message || "Failed to change workspace.", { error: true });
        return;
      }
      // A chat URL cached for this archived session was resolved against the
      // old workspace's port; drop it so the next open re-resolves.
      hubChatUrls.forget(buildSessionOpenHref(sessionName, true));
      showDeskHubMessage(`Workspace updated for ${sessionName}.`);
    }

    async function copyDeskSessionWorkspace(sessionName) {
      if (!sessionName) return;
      showDeskHubMessage();
      try {
        const res = await fetch(`/session-workspace?session=${encodeURIComponent(sessionName)}`, { cache: "no-store" });
        const data = await res.json().catch(() => ({}));
        const workspace = String(data.workspace || "").trim();
        if (!res.ok || !data.ok || !workspace) {
          throw new Error(data.error || "Workspace path is unavailable.");
        }
        await copyDeskText(workspace);
      } catch (err) {
        showDeskHubMessage(err?.message || "Failed to copy workspace path.", { error: true });
        return;
      }
      showDeskHubMessage(`Copied workspace path for ${sessionName}.`);
    }

    async function resetDeskSessionAgents(sessionName) {
      if (!sessionName) return;
      showDeskHubMessage();
      try {
        const res = await fetch("/reset-session-agents", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
          body: new URLSearchParams({ session: sessionName }).toString(),
          cache: "no-store",
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) throw new Error(data.error || "Failed to reset agents.");
      } catch (err) {
        showDeskHubMessage(err?.message || "Failed to reset agents.", { error: true });
        return;
      }
      if (_deskSelectedSessionName === sessionName) {
        postDeskChatFrameMessage({ type: "refresh-session-state", projections: ["targets"] });
      }
      await refreshHubSessions(true, { skipRestore: true });
      showDeskHubMessage(`Agents reset for ${sessionName}.`);
    }

    function beginDeskSessionRename(sessionName) {
      if (_deskSessionRename) _deskSessionRename.cancel();
      const row = Array.from(_deskSessionList?.querySelectorAll(".desk-action-session-row") || [])
        .find((candidate) => candidate.dataset.sessionName === sessionName);
      const nameEl = row?.querySelector(".desk-row-name");
      if (!row || !nameEl) return;

      const input = document.createElement("input");
      input.type = "text";
      input.className = "desk-row-rename-input";
      input.value = sessionName;
      input.setAttribute("aria-label", `Rename ${sessionName}`);
      nameEl.replaceWith(input);
      row.classList.add("is-renaming");

      let settling = false;
      const cancel = () => {
        if (_deskSessionRename?.input !== input) return;
        _deskSessionRename = null;
        row.classList.remove("is-renaming");
        if (input.isConnected) input.replaceWith(nameEl);
      };
      const commit = async () => {
        if (_deskSessionRename?.input !== input || settling) return;
        settling = true;
        input.disabled = true;
        const renamed = await renameDeskSession(sessionName, input.value);
        if (renamed) {
          _deskSessionRename = null;
          await refreshHubSessions(true, { skipRestore: true });
          return;
        }
        settling = false;
        input.disabled = false;
        requestAnimationFrame(() => {
          input.focus();
          input.select();
        });
      };
      _deskSessionRename = { input, cancel };
      input.addEventListener("keydown", (event) => {
        event.stopPropagation();
        if (event.key === "Enter") {
          event.preventDefault();
          void commit();
        } else if (event.key === "Escape") {
          event.preventDefault();
          cancel();
        }
      });
      input.addEventListener("blur", () => { void commit(); });
      input.addEventListener("click", (event) => event.stopPropagation());
      input.addEventListener("contextmenu", (event) => event.stopPropagation());
      input.focus();
      input.select();
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
      const setTrackX = (x, animate = false) => {
        track.style.transition = animate ? "transform 220ms cubic-bezier(.25,.46,.45,.94)" : "none";
        track.style.transform = x ? `translateX(${x}px)` : "";
        wrapper.dataset.swipeOpen = x ? "1" : "0";
        if (!x && _deskOpenSwipeRow === wrapper) _deskOpenSwipeRow = null;
        if (x) _deskOpenSwipeRow = wrapper;
      };
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
      let html = "";
      if (active.length) {
        html += `<div class="desk-section-label">Active</div>`;
        html += active.map((session) => renderDeskSessionRow(session, false)).join("");
      }
      if (archived.length) {
        html += `<div class="desk-section-label">Archived</div>`;
        html += archived.map((session) => renderDeskSessionRow(session, true)).join("");
      }
      if (!active.length && !archived.length) {
        html = `<div class="desk-empty-list">No sessions found</div>`;
      }
      _deskSessionList.innerHTML = html;
      _deskSessionList.querySelectorAll(".desk-swipe-row").forEach(initDeskSwipeRow);
      updateDeskSessionListFade();
    }

    function computeScrollFadeState(el) {
      const { scrollTop, scrollHeight, clientHeight } = el;
      const overflowing = scrollHeight > clientHeight + 1;
      if (!overflowing) return "none";
      const atTop = scrollTop <= 1;
      const atBottom = scrollTop + clientHeight >= scrollHeight - 1;
      if (atTop && !atBottom) return "bottom";
      if (atBottom && !atTop) return "top";
      return "both";
    }

    const DESK_CHROME_GROUP_GAP = 16;
    // macOS centers the native traffic-light cluster (close/miniaturize/zoom)
    // on the window's full width -- see center_traffic_lights() in main.rs.
    // It isn't in the DOM, so its safe zone has to be computed the same way
    // here rather than measured.
    const DESK_TRAFFIC_LIGHTS_WIDTH = 56;
    function updateDeskChromeOverflow() {
      if (!_deskFloatingControls || !_deskTopRightControls) return;
      _deskFloatingControls.classList.remove("is-port-hidden", "is-title-hidden", "is-buttons-hidden");
      _deskTopRightControls.classList.remove("is-buttons-hidden");
      // Left and right groups are mirror-symmetric (same buttons, same
      // --desk-chrome-edge inset), and the traffic lights are centered, so
      // checking the left group against the traffic-light zone alone is
      // enough -- the right side collides at the same threshold.
      const trafficLeft = window.innerWidth / 2 - (DESK_TRAFFIC_LIGHTS_WIDTH / 2);
      const collides = () => _deskFloatingControls.getBoundingClientRect().right + DESK_CHROME_GROUP_GAP > trafficLeft;
      if (!collides()) return;
      // Drop the "(port)" suffix first -- the session name alone often still fits.
      _deskFloatingControls.classList.add("is-port-hidden");
      if (!collides()) return;
      _deskFloatingControls.classList.add("is-title-hidden");
      if (!collides()) return;
      _deskFloatingControls.classList.add("is-buttons-hidden");
      _deskTopRightControls.classList.add("is-buttons-hidden");
    }

    function updateDeskSessionListFade() {
      if (!_deskSessionList) return;
      _deskSessionList.dataset.scrollFade = computeScrollFadeState(_deskSessionList);
    }

    function updateDeskUnreadSessions(active) {
      const nextRevisions = new Map();
      const activeNames = new Set();
      active.forEach((session) => {
        const name = String(session.name || "").trim();
        if (!name) return;
        activeNames.add(name);
        const revision = String(session.latest_message_revision || "").trim();
        const previousRevision = _deskPreviewRevisions.get(name);
        if (
          previousRevision &&
          revision &&
          revision !== previousRevision &&
          name !== _deskSelectedSessionName &&
          String(session.latest_message_sender || "").trim() !== "user"
        ) {
          _deskUnreadSessions.add(name);
        }
        nextRevisions.set(name, revision);
      });
      Array.from(_deskUnreadSessions).forEach((name) => {
        if (!activeNames.has(name)) _deskUnreadSessions.delete(name);
      });
      _deskPreviewRevisions = nextRevisions;
    }

    async function refreshHubSessions(force = false, options = {}) {
      const skipRestore = !!(options && options.skipRestore);
      const requestSeq = ++_deskSessionsRequestSeq;
      try {
        const response = await fetch(`/sessions?ts=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) throw new Error("failed");
        const data = await response.json();
        const active = data.active_sessions;
        const archived = data.archived_sessions;
        _hubSessionsCache = { active, archived };
        if (requestSeq === _deskSessionsRequestSeq) {
          updateDeskUnreadSessions(active);
          if (_deskSelectedSessionName) updateDeskWindowTitle(_deskSelectedSessionName);

          const signature = JSON.stringify({
            active,
            archived,
            selected: _deskSelectedSessionName,
          });
          if (!_deskSessionRename && (force || window._lastHubRenderSig !== signature)) {
            window._lastHubRenderSig = signature;
            renderDesktopSessions(active, archived);
          }
          _deskSessionsRenderedOnce = true;
        }
        if (!skipRestore) maybeRestoreDeskSelection();
      } catch (_) {
        if (requestSeq !== _deskSessionsRequestSeq) return;
        if (_deskSessionsRenderedOnce || _hubSessionsCache.active.length || _hubSessionsCache.archived.length) return;
        if (_deskSessionList) {
          _deskSessionList.innerHTML = `<div class="desk-empty-list">Failed to load sessions</div>`;
        }
      }
    }

    window.addEventListener("message", (event) => {
      if (event.data && event.data.type === "hub-session-error") {
        failDeskOpen(event.data.message || "open session failed");
        return;
      }
      if (event.data && event.data.type === "desktop-panel-state" && event.source === _deskChatFrame?.contentWindow) {
        updateDeskPanelButtonState(
          String(event.data.mode || ""),
          Number(event.data.width || 0),
        );
        return;
      }
      if (event.data && event.data.type === "open-external-url" && event.source === _deskChatFrame?.contentWindow) {
        const invoke = getTauriInvoke();
        if (typeof invoke !== "function") {
          event.source?.postMessage({ type: "external-url-open-failed" }, "*");
          return;
        }
        invoke("open_external_url", { url: String(event.data.url || "") }).catch(() => {
          event.source?.postMessage({ type: "external-url-open-failed" }, "*");
        });
        return;
      }
      if (event.data && event.data.type === "show-chat-header-menu") {
        const invoke = getTauriInvoke();
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
      if (event.data && event.data.type === "show-file-context-menu" && event.source === _deskChatFrame?.contentWindow) {
        const invoke = getTauriInvoke();
        const childPayload = event.data.payload || {};
        const frameRect = _deskChatFrame?.getBoundingClientRect?.() || { left: 0, top: 0 };
        if (typeof invoke !== "function") {
          event.source?.postMessage({ type: "file-context-menu-error", message: "Native file menu is unavailable." }, "*");
          return;
        }
        invoke("show_file_context_menu", {
          payload: {
            x: Math.round(Number(childPayload.x || 0) + Number(frameRect.left || 0)),
            y: Math.round(Number(childPayload.y || 0) + Number(frameRect.top || 0)),
            revealEnabled: !!childPayload.revealEnabled,
          },
        }).catch((err) => {
          event.source?.postMessage({ type: "file-context-menu-error", message: String(err || "Failed to open file menu.") }, "*");
        });
        return;
      }
      if (event.data === "hub_close_chat") {
        showDeskSidebarList({ open: true });
        return;
      }
      if (event.data && event.data.type === "toggle-hub-sidebar") {
        toggleDeskSidebar();
        return;
      }
      if (event.data && event.data.type === "toggle-hub-sidebar-outward" && event.source === _deskChatFrame?.contentWindow) {
        toggleDeskSidebarOutward();
        return;
      }
      if (event.data && event.data.type === "toggle-desktop-panel-outward" && event.source === _deskChatFrame?.contentWindow) {
        toggleDeskRightPanelOutward();
        return;
      }
      if (event.data && event.data.type === "hub-open-chat-session") {
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
      if (event.data && event.data.type === "hub-theme-changed") {
        applyIncomingThemeDesktop(event.data.themeDesktop || event.data.theme);
        return;
      }
      if (event.data && event.data.type === "text-size-shortcut") {
        if (event.data.reset) {
          applyDeskTextSizeAndBroadcast(DESK_TEXT_SIZE_DEFAULT);
        } else {
          const delta = Number(event.data.delta) || 0;
          if (delta) applyDeskTextSizeAndBroadcast(currentDeskTextSizePx() + delta);
        }
        return;
      }
      if (event.data && event.data.type === "desktop-menu-shortcut") {
        dispatchDeskNativeMenuAction({ action: String(event.data.action || "") });
        return;
      }
      if (event.data && event.data.type === "reload-shortcut") {
        if (event.data.scope === "hub") triggerDeskHubReload();
        else sendDeskChatAction("reloadChat");
        return;
      }
      if (event.data && event.data.type === "new-session-shortcut") {
        void startDeskNewSessionFlow();
        return;
      }
      if (event.data && event.data.type === "switch-session-shortcut") {
        switchToDeskActiveSession(Number(event.data.index));
        return;
      }
      if (event.data && event.data.type === "reset-window-shortcut") {
        void resetDeskWindowState();
        return;
      }
      if (event.data && event.data.type === "compact-window-shortcut") {
        void compactDeskWindowState();
        return;
      }
      if (event.data && event.data.type === "mini-window-shortcut") {
        void compactDeskWindowState("mini_window_geometry", "mini window");
        return;
      }
      if (event.data && event.data.type === "always-on-top-shortcut") {
        toggleDeskAlwaysOnTop();
        return;
      }
      if (event.data && event.data.type === "auto-window-height-shortcut") {
        void toggleDeskAutoWindowHeight();
        return;
      }
      if (event.data && event.data.type === "move-window-shortcut") {
        void moveDeskWindowToSpot(String(event.data.command || ""));
        return;
      }
      if (event.data && event.data.type === "fit-window-height" && event.source === _deskChatFrame?.contentWindow) {
        fitDeskWindowHeight(event.data.contentHeight);
        return;
      }
      if (event.data && event.data.type === "open-hub-path") {
        const nextUrl = typeof event.data.url === "string" ? event.data.url : "";
        if (!nextUrl) return;
        window.location.href = nextUrl;
      }
    });
    document.addEventListener("dragenter", (event) => {
      if (!deskDtHasFiles(event.dataTransfer) || isDeskChatFrameDropTarget(event.target)) return;
      showDeskAttachDrag();
    }, true);
    document.addEventListener("dragover", (event) => {
      if (!deskDtHasFiles(event.dataTransfer) || isDeskChatFrameDropTarget(event.target)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      showDeskAttachDrag();
    }, true);
    document.addEventListener("dragleave", (event) => {
      if (!deskDtHasFiles(event.dataTransfer) || isDeskChatFrameDropTarget(event.target)) return;
      const related = event.relatedTarget;
      if (!related || !document.documentElement.contains(related)) {
        hideDeskAttachDrag();
      }
    }, true);
    document.addEventListener("dragend", () => {
      hideDeskAttachDrag({ immediate: true });
    }, true);
    document.addEventListener("drop", (event) => {
      if (!deskDtHasFiles(event.dataTransfer) || isDeskChatFrameDropTarget(event.target)) return;
      event.preventDefault();
      event.stopPropagation();
      hideDeskAttachDrag({ immediate: true });
      forwardDeskDroppedFiles(event.dataTransfer.files);
    }, true);

    _deskChatFrame && _deskChatFrame.addEventListener("load", () => {
      setDeskChatLoading(false);
      syncDeskChatShellState();
      applyDeskChatTheme();
      pushDeskAutoWindowHeight();
      try {
        _deskChatFrame.contentWindow?.postMessage({ type: "desktop-panel-sync-request" }, "*");
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
      if (_deskAutoWindowHeight) {
        void openDeskNativeSessionSwitcher();
        return;
      }
      showDeskSidebarList({ open: true });
    });
    initDeskSidebarHoverPopover();
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
    _deskChatReloadBtn && _deskChatReloadBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      sendDeskChatAction("reloadChat");
    });
    _deskPanelToggle && _deskPanelToggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (_deskAutoWindowHeight) {
        void openDeskNativeGitChanges();
        return;
      }
      if (_deskPanelActiveMode) {
        updateDeskPanelButtonState("", 0);
        sendDeskPanelCommand("close");
        return;
      }
      updateDeskPanelButtonState("open", _deskPanelWidth);
      sendDeskPanelCommand("repo");
    });
    // The Fit Height traffic-light indicator (shown only in that mode) is a
    // live stand-in for the hidden native buttons.
    (function armFitWindowDots() {
      const dotsEl = document.querySelector(".fit-window-dots");
      const win = window.__TAURI__?.window?.getCurrentWindow?.();
      if (!dotsEl || !win) return;
      const actions = [
        ["Close", () => win.close()],
        ["Minimize", () => win.minimize()],
        ["Zoom", () => win.toggleMaximize()],
      ];
      dotsEl.querySelectorAll("i").forEach((bar, i) => {
        const [label, run] = actions[i] || [];
        if (!run) return;
        bar.setAttribute("role", "button");
        bar.setAttribute("aria-label", label);
        bar.addEventListener("click", () => { try { void run(); } catch (_) {} });
      });
    })();
    _deskSettingsBtn && _deskSettingsBtn.addEventListener("click", () => { void openAppearanceMenu(); });
    _deskReloadBtn && _deskReloadBtn.addEventListener("click", triggerDeskHubReload);
    window.addEventListener("resize", updateDeskChromeOverflow, { passive: true });
    updateDeskChromeOverflow();
    if (_deskSessionList) {
      _deskSessionList.addEventListener("scroll", updateDeskSessionListFade, { passive: true });
      window.addEventListener("resize", updateDeskSessionListFade, { passive: true });
      _deskSessionList.addEventListener("contextmenu", (event) => {
        const row = event.target.closest(".desk-action-session-row");
        const invoke = getTauriInvoke();
        const sessionName = row?.dataset.sessionName || "";
        if (!sessionName || typeof invoke !== "function") return;
        event.preventDefault();
        _deskContextSessionName = sessionName;
        const rec = findSessionRecord(sessionName);
        const archived = !!(rec && rec.archived);
        const selected = sessionName === _deskSelectedSessionName;
        invoke("show_session_context_menu", {
          payload: {
            x: Math.round(event.clientX),
            y: Math.round(event.clientY),
            resetAgentsEnabled: archived && !rec.session.agents_reset,
            changeWorkspaceEnabled: archived && !selected,
            archiveEnabled: !archived,
            deleteEnabled: archived && selected,
            reviveEnabled: archived,
          },
        }).catch((err) => {
          showDeskHubMessage(String(err || "Failed to open session menu."), { error: true });
        });
      });
      _deskSessionList.addEventListener("click", (event) => {
        const hoverAction = event.target.closest("[data-desk-hover-action]");
        if (hoverAction) {
          event.preventDefault();
          event.stopPropagation();
          const row = hoverAction.closest(".desk-session-row");
          const sessionName = row?.dataset.sessionName || "";
          const kind = hoverAction.dataset.deskHoverAction || "";
          if (sessionName && kind) {
            if (kind === "revive") {
              const href = `/revive-session?session=${encodeURIComponent(sessionName)}`;
              openSessionFrame(href, sessionName);
            } else {
              void runDeskContextAction(sessionName, kind);
            }
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
        const href = deskSessionOpenHref(row);
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
    startHubSessionMessagesEvents(() => refreshHubSessions(true, { skipRestore: true }));
    consumeHubPendingError();
    if (isTauriDesktopApp() && !isPhoneViewport()) {
      // sessionStorage, not localStorage: a same-session reload keeps whatever
      // state it was in, but a fresh app launch has no entry and falls back to
      // open -- the default stays "open".
      let wantSidebarOpen = true;
      try { wantSidebarOpen = sessionStorage.getItem(DESK_SIDEBAR_OPEN_KEY) !== "0"; } catch (_) {}
      if (wantSidebarOpen) showDeskSidebarList({ open: true });
      else setDeskSidebarOpen(false);
      let wantAutoHeight = false;
      try { wantAutoHeight = sessionStorage.getItem(DESK_AUTO_HEIGHT_KEY) === "1"; } catch (_) {}
      if (wantAutoHeight) setDeskAutoWindowHeight(true);
    }
    refreshHubSessions(true);
  __HUB_HEADER_JS__
