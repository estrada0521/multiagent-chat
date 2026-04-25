from __future__ import annotations

from .chat_pane_trace_core import build_pane_trace_view_model
from .color_constants import DARK_BG


def render_pane_trace_popup_html(*, agent: str, agents: list[str] | None = None, bg: str, text: str, chat_base_path: str = "") -> str:
    view_model = build_pane_trace_view_model(
        agent=agent,
        agents=agents,
        bg=bg,
        text=text,
        chat_base_path=chat_base_path,
    )
    bg_value = view_model["bg_value"]
    text_value = view_model["text_value"]
    agents_json = view_model["agents_json"]
    initial_agent_json = view_model["initial_agent_json"]
    bg_json = view_model["bg_json"]
    text_json = view_model["text_json"]
    bg_effective = view_model["bg_effective"]
    header_overlay_bg = view_model["header_overlay_bg"]
    body_fg = view_model["body_fg"]
    body_dim_fg = view_model["body_dim_fg"]
    trace_path_prefix = view_model["trace_path_prefix"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="{bg_value}">
  <title>Pane Trace</title>
  <script src="https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js"></script>
  <style>
    :root {{
      color-scheme: dark;
      --popup-bg: {bg_value};
      --popup-text: {text_value};
      --pane-trace-body-bg: {bg_effective};
      --pane-trace-body-fg: {body_fg};
      --pane-trace-body-dim-fg: {body_dim_fg};
    }}
    html, body {{
      margin: 0;
      background: var(--pane-trace-body-bg);
      color: var(--popup-text);
      height: 100%;
      font-family: "SF Mono", "SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-weight: 400;
      font-style: normal;
    }}
    body {{
      display: flex;
      flex-direction: column;
      position: relative;
      overflow: hidden;
    }}
    .pane-trace-tabs {{
      position: relative;
      z-index: 10;
      display: flex;
      align-items: flex-end;
      --pane-trace-tab-overlap: 1px;
      --pane-trace-tab-strip-bg: {DARK_BG};
      gap: 2px;
      padding: 0 8px;
      height: 35px;
      margin-bottom: calc(-1 * var(--pane-trace-tab-overlap));
      background: linear-gradient(
        to bottom,
        var(--pane-trace-tab-strip-bg) 0 calc(100% - var(--pane-trace-tab-overlap)),
        transparent calc(100% - var(--pane-trace-tab-overlap))
      );
      flex: 0 0 auto;
      min-width: 0;
      overflow-x: auto;
      overflow-y: hidden;
      -webkit-overflow-scrolling: touch;
      justify-content: flex-start;
      -webkit-app-region: drag;
      scrollbar-width: none;
    }}
    .pane-trace-tabs::-webkit-scrollbar {{ display: none; }}
    .pane-trace-tab {{
      position: relative;
      display: flex;
      align-items: center;
      flex-shrink: 0;
      padding: 0 16px;
      height: 34px;
      box-sizing: border-box;
      font: 500 12px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
      color: rgba(255,255,255,0.5);
      background: transparent;
      border: none;
      border-radius: 10px 10px 0 0;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s ease;
      min-width: 0;
      max-width: 200px;
      overflow: visible;
      text-overflow: ellipsis;
      -webkit-app-region: no-drag;
    }}
    @media (hover: hover) and (pointer: fine) {{
    .pane-trace-tab:hover {{
      color: rgba(255,255,255,0.9);
      background: rgba(255,255,255,0.1);
    }}
    }}
    .pane-trace-tab.active {{
      color: #fff;
      background: {bg_effective};
      box-shadow: none;
      z-index: 2;
      margin-bottom: calc(-1 * var(--pane-trace-tab-overlap));
      border-radius: 10px 10px 0 0;
    }}
    .pane-trace-tab-label {{
      display: inline-flex;
      align-items: baseline;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .pane-trace-thinking-char {{
      color: rgba(252,252,252,0.42);
      animation: thinking-char-pulse 1.5s linear infinite;
    }}
    .pane-trace-tab:not(.pane-trace-tab-thinking) .pane-trace-thinking-char {{
      color: inherit;
      animation: none;
    }}
    .pane-trace-content {{
      position: relative;
      z-index: 1;
      flex: 1 1 auto;
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr;
      grid-template-rows: 1fr;
    }}
    .pane-trace-content.split-h {{ grid-template-columns: 1fr 1fr; }}
    .pane-trace-content.split-v {{ grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3bl {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3bl [data-slot="0"] {{ grid-column: 1; grid-row: 1; }}
    .pane-trace-content.split-3bl [data-slot="1"] {{ grid-column: 2; grid-row: 1 / -1; }}
    .pane-trace-content.split-3bl [data-slot="2"] {{ grid-column: 1; grid-row: 2; }}
    .pane-trace-content.split-3br {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3br [data-slot="0"] {{ grid-column: 1; grid-row: 1 / -1; }}
    .pane-trace-content.split-3br [data-slot="1"] {{ grid-column: 2; grid-row: 1; }}
    .pane-trace-content.split-3br [data-slot="2"] {{ grid-column: 2; grid-row: 2; }}
    .pane-trace-content.split-3span {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-content.split-3span [data-slot="2"] {{ grid-column: 1 / -1; }}
    .pane-trace-content.split-4 {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}
    .pane-trace-pane {{
      position: relative;
      min-width: 0;
      min-height: 0;
      display: flex;
      flex-direction: column;
      border: 0.5px solid rgba(255,255,255,0.06);
      overflow: hidden;
    }}
    .pane-trace-header-shadow {{
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 40px;
      background: linear-gradient({bg_effective} 0%, transparent 100%);
      pointer-events: none;
      z-index: 2;
    }}
    .pane-trace-pane-badge {{
      position: absolute;
      top: 6px; left: 8px; z-index: 11;
      width: 28px; height: 28px;
      padding: 4px;
      box-sizing: border-box;
      background: none;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: visible;
      transition: background 0.15s;
      user-select: none;
    }}
    .pane-trace-pane-badge-inner {{
      position: relative;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .pane-trace-pane-badge-glow {{
      position: absolute;
      inset: 0;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(250,249,245,0.65) 0%, rgba(250,249,245,0) 70%);
      pointer-events: none;
      animation: thinking-glow-follow 1s ease-in-out infinite;
      animation-delay: var(--agent-pulse-delay, 0s);
    }}
    .agent-icon-slot {{
      position: relative;
      display: inline-flex;
      align-items: flex-end;
      justify-content: center;
      width: 100%;
      height: 100%;
      line-height: 0;
      --agent-icon-sub-size: 10px;
      --agent-icon-sub-font-size: 6px;
      --agent-icon-sub-offset-x: 14%;
      --agent-icon-sub-offset-y: 10%;
    }}
    .agent-icon-instance-sub {{
      position: absolute;
      right: 0;
      bottom: 0;
      margin: 0;
      min-width: var(--agent-icon-sub-size);
      height: var(--agent-icon-sub-size);
      padding: 0 0.14em;
      border-radius: 999px;
      font-size: var(--agent-icon-sub-font-size);
      font-weight: 700;
      line-height: 1;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.01em;
      color: rgba(252,252,252,0.96);
      pointer-events: none;
      background: rgba(8, 10, 14, 0.9);
      border: 1px solid rgba(255,255,255,0.14);
      box-shadow: 0 1px 3px rgba(0,0,0,0.34);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transform: translate(var(--agent-icon-sub-offset-x), var(--agent-icon-sub-offset-y));
    }}
    .pane-trace-pane-badge-icon {{
      width: 100%; height: 100%;
      object-fit: contain;
      display: block;
      position: relative;
      filter: brightness(0) invert(0.92);
    }}
    .pane-trace-pane-badge-thinking .pane-trace-pane-badge-icon {{
      animation: thinking-icon-heartbeat 1s ease-in-out infinite;
      animation-delay: var(--agent-pulse-delay, 0s);
    }}
    .pane-trace-pane-badge:not(.pane-trace-pane-badge-thinking) .pane-trace-pane-badge-glow {{
      display: none;
    }}
    .pane-trace-pane-badge-thinking .pane-trace-pane-badge-glow {{
      display: block;
    }}
    .pane-trace-pane-badge:hover {{ background: rgba(220,40,40,0.7); }}
    .pane-trace-pane-badge:hover .pane-trace-pane-badge-icon {{ filter: brightness(0) invert(1); }}
    @keyframes thinking-glow-follow {{
      0%   {{ transform: scale(0.5); opacity: 0; }}
      50%  {{ transform: scale(1.4); opacity: 0.12; }}
      100% {{ transform: scale(0.5); opacity: 0; }}
    }}
    @keyframes thinking-icon-heartbeat {{
      0%   {{ transform: translateY(0);    filter: brightness(0) invert(0.92); }}
      50%  {{ transform: translateY(-1px); filter: brightness(0) invert(1); }}
      100% {{ transform: translateY(0);    filter: brightness(0) invert(0.92); }}
    }}
    @keyframes thinking-char-pulse {{
      0%   {{ color: rgba(252, 252, 252, 0.62); }}
      10%  {{ color: rgba(252, 252, 252, 0.82); }}
      22%  {{ color: rgba(252, 252, 252, 0.62); }}
      34%  {{ color: rgba(252, 252, 252, 0.42); }}
      88%  {{ color: rgba(252, 252, 252, 0.42); }}
      100% {{ color: rgba(252, 252, 252, 0.62); }}
    }}
    .pane-trace-drop-indicator {{
      position: absolute;
      background: rgba(255,255,255,0.1);
      border: 1.5px solid rgba(255,255,255,0.4);
      border-radius: 4px;
      z-index: 10;
      pointer-events: none;
      display: none;
    }}
    .pane-trace-body {{
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 10px 12px;
      padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
      box-sizing: border-box;
      -webkit-overflow-scrolling: touch;
      font-family: "SF Mono", "SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-weight: 400;
      font-style: normal;
      font-size: 11.5px;
      line-height: 1.15;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: anywhere;
      color: var(--pane-trace-body-fg);
    }}
    .pane-trace-body .ansi-bright-black-fg {{ color: var(--pane-trace-body-dim-fg); }}
    .trace-dot {{
      font-family: -apple-system, "Helvetica Neue", sans-serif;
      font-variant-emoji: text;
      text-rendering: geometricPrecision;
    }}
    @media (prefers-reduced-motion: reduce) {{
      .pane-trace-pane-badge-thinking .pane-trace-pane-badge-icon {{
        animation: none;
        filter: brightness(0) invert(0.92);
      }}
      .pane-trace-pane-badge-thinking .pane-trace-pane-badge-glow {{
        animation: none;
        display: none;
      }}
      .pane-trace-tab-thinking .pane-trace-thinking-char {{
        animation: none;
        color: rgba(252,252,252,0.6);
      }}
    }}
  </style>
</head>
<body>
  <div class="pane-trace-tabs" id="paneTraceTabs"></div>
  <div class="pane-trace-content" id="paneTraceContent">
    <div class="pane-trace-pane" data-slot="0">
      <span class="pane-trace-pane-badge" data-slot="0"></span>
      <div class="pane-trace-body">Loading...</div>
    </div>
  </div>
  <div class="pane-trace-drop-indicator" id="dropIndicator"></div>
  <script>
    const agents = {agents_json};
    const bg = {bg_json};
    const text = {text_json};
    document.documentElement.style.setProperty("--popup-bg", bg);
    document.documentElement.style.setProperty("--popup-text", text);

    const isLocalHost = (host) => host === "127.0.0.1" || host === "localhost" || host === "[::1]" || host.startsWith("192.168.") || host.startsWith("10.") || /^172\\.(1[6-9]|2\\d|3[01])\\./.test(host);
    const pollMs = isLocalHost(String(location.hostname || "")) ? 300 : 1500;
    const tabsEl = document.getElementById("paneTraceTabs");
    const contentEl = document.getElementById("paneTraceContent");
    const dropEl = document.getElementById("dropIndicator");
    const escapeHtml = (value) => String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
    const agentBaseName = (name) => String(name || "").toLowerCase().replace(/-\\d+$/, "");
    const agentPulseOffset = () => 0;
    const tabLabelHtml = (name) => {{
      const label = String(name || "");
      const offset = agentPulseOffset(name);
      const chars = [...label].map((ch, i) =>
        `<span class="pane-trace-thinking-char" style="animation-delay:${{offset + (i * 0.18)}}s">${{escapeHtml(ch)}}</span>`
      ).join("");
      return `<span class="pane-trace-tab-label">${{chars}}</span>`;
    }};

    /* ── state ── */
    let layout = "single";   /* "single" | "h" | "v" | "3bl" | "3br" | "3span" | "4" */
    let paneAgents = [{initial_agent_json}, null, null, null];
    let extraIntervals = [null, null, null];
    let statusInterval = null;
    let currentStatuses = {{}};
    let contentCache = Object.create(null);
    const slotCount = () => ({{ single: 1, h: 2, v: 2, "3bl": 3, "3br": 3, "3span": 3, "4": 4 }})[layout];

    /* ── ansi / fetch ── */
    let ansiUp = null;
    const traceHtml = (raw) => {{
      const txt = String(raw ?? "No output");
      if (!ansiUp) {{ try {{ if (typeof AnsiUp === "function") ansiUp = new AnsiUp(); }} catch (_) {{}} }}
      let html;
      if (ansiUp) {{ try {{ html = ansiUp.ansi_to_html(txt); }} catch (_) {{}} }}
      if (!html) html = txt.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\\n/g,"<br>");
      return html.replace(/[●⏺]/g, '<span class="trace-dot">●</span>');
    }};
    const _paneBodyAtBottom = (el) => !el || el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    const fetchTo = async (agent, bodyEl, scroll) => {{
      if (!agent || !bodyEl) return;
      if (document.hidden) return;
      if (!scroll && !_paneBodyAtBottom(bodyEl)) return;
      try {{
        const res = await fetch(`{trace_path_prefix}/trace?agent=${{encodeURIComponent(agent)}}&lines=160&ts=${{Date.now()}}`);
        if (!res.ok) return;
        const data = await res.json();
        if (document.hidden) return;
        const content = String(data.content || "");
        const atBottom = _paneBodyAtBottom(bodyEl);
        if (!scroll && contentCache[agent] === content) return;
        contentCache[agent] = content;
        bodyEl.innerHTML = traceHtml(content || "No output");
        if (scroll || atBottom) bodyEl.scrollTop = bodyEl.scrollHeight;
      }} catch (_) {{}}
    }};

    /* ── icon path helper ── */
    const agentIconInstanceSubHtml = (name) => {{
      const m = String(name || "").toLowerCase().match(/-(\\d+)$/);
      if (!m) return "";
      const d = m[1];
      return `<span class="agent-icon-instance-sub" aria-hidden="true">${{escapeHtml(d)}}</span>`;
    }};
    const agentIconUrl = (name) => `{trace_path_prefix}/icon/${{encodeURIComponent(String(name || "").toLowerCase())}}`;
    const paneBadgeHtml = (agent) => {{
      const pulse = agentPulseOffset(agent);
      return `<span class="pane-trace-pane-badge-inner" style="--agent-pulse-delay:${{pulse}}s"><span class="pane-trace-pane-badge-glow"></span><span class="agent-icon-slot agent-icon-slot--badge"><img class="pane-trace-pane-badge-icon" src="${{agentIconUrl(agent)}}" alt="${{escapeHtml(agent)}}">${{agentIconInstanceSubHtml(agent)}}</span></span>`;
    }};
    const applyThinkingState = () => {{
      tabsEl.querySelectorAll(".pane-trace-tab").forEach((tab) => {{
        const agent = tab.dataset.agent || "";
        tab.classList.toggle("pane-trace-tab-thinking", currentStatuses[agent] === "running");
      }});
      contentEl.querySelectorAll(".pane-trace-pane-badge").forEach((badge) => {{
        const slot = Number.parseInt(badge.dataset.slot || "-1", 10);
        const agent = slot >= 0 ? paneAgents[slot] : "";
        badge.classList.toggle("pane-trace-pane-badge-thinking", !!agent && currentStatuses[agent] === "running");
      }});
    }};
    const fetchStatuses = async () => {{
      try {{
        const res = await fetch(`{trace_path_prefix}/session-state?ts=${{Date.now()}}`, {{ cache: "no-store" }});
        if (!res.ok) return;
        const data = await res.json();
        currentStatuses = (data && typeof data.statuses === "object" && data.statuses) ? data.statuses : {{}};
        applyThinkingState();
      }} catch (_) {{}}
    }};

    /* ── make a pane element ── */
    const makePane = (slot, agent) => {{
      const d = document.createElement("div");
      d.className = "pane-trace-pane";
      d.setAttribute("data-slot", slot);
      d.innerHTML = `<div class="pane-trace-header-shadow"></div><span class="pane-trace-pane-badge" data-slot="${{slot}}">${{paneBadgeHtml(agent)}}</span><div class="pane-trace-body">Loading...</div>`;
      d.querySelector(".pane-trace-pane-badge").addEventListener("click", () => closePane(slot));
      return d;
    }};

    /* ── rebuild panes from state ── */
    const rebuildPanes = () => {{
      const n = slotCount();
      contentEl.className = "pane-trace-content" + (layout !== "single" ? ` split-${{layout}}` : "");
      extraIntervals.forEach((iv, i) => {{ if (iv) clearInterval(iv); extraIntervals[i] = null; }});
      contentCache = Object.create(null);
      contentEl.innerHTML = "";
      const used = new Set();
      for (let i = 0; i < n; i++) {{
        if (!paneAgents[i] || (i > 0 && used.has(paneAgents[i]))) {{
          paneAgents[i] = agents.find(a => !used.has(a)) || agents[0];
        }}
        used.add(paneAgents[i]);
        const pane = makePane(i, paneAgents[i]);
        contentEl.appendChild(pane);
        fetchTo(paneAgents[i], pane.querySelector(".pane-trace-body"), true);
        if (i > 0) {{
          const idx = i;
          extraIntervals[idx - 1] = setInterval(() => {{
            const b = contentEl.querySelector(`[data-slot="${{idx}}"] .pane-trace-body`);
            if (b && paneAgents[idx]) fetchTo(paneAgents[idx], b, false);
          }}, pollMs);
        }}
      }}
      for (let i = n; i < 4; i++) paneAgents[i] = null;
      document.title = layout === "single" ? `${{paneAgents[0]}} Pane Trace` : "Pane Trace";
      applyThinkingState();
    }};

    /* ── close a pane ── */
    const closePane = (slot) => {{
      const n = slotCount();
      if (n <= 1) return;
      paneAgents.splice(slot, 1);
      paneAgents.push(null);
      if (n === 4) {{ layout = "h"; }}
      else if (n === 3) {{ layout = "h"; }}
      else {{ layout = "single"; }}
      buildTabs();
      rebuildPanes();
    }};

    /* ── detect drop zone ── */
    const detectZone = (e) => {{
      const n = slotCount();
      if (n >= 4) {{
        const pane = e.target.closest(".pane-trace-pane");
        return pane ? {{ action: "replace", slot: parseInt(pane.getAttribute("data-slot"), 10) }} : null;
      }}
      const rect = contentEl.getBoundingClientRect();
      const rx = (e.clientX - rect.left) / rect.width;
      const ry = (e.clientY - rect.top) / rect.height;
      if (n === 1) {{
        const dRight = 1 - rx, dBottom = 1 - ry;
        if (dRight < 0.35 && dRight < dBottom) return {{ action: "split", dir: "h", zone: "right", rect }};
        if (dBottom < 0.35) return {{ action: "split", dir: "v", zone: "bottom", rect }};
        return {{ action: "replace", slot: 0 }};
      }}
      if (n === 2 && layout === "h") {{
        /* bottom edge of left or right pane → add 3rd pane */
        const isBottom = ry > 0.65;
        if (isBottom) {{
          /* left half of bottom → 3rd under left column, right half → 3rd under right column */
          /* center region → span full bottom */
          if (rx < 0.35) return {{ action: "expand3", sub: "3bl", rect }};
          if (rx > 0.65) return {{ action: "expand3", sub: "3br", rect }};
          return {{ action: "expand3", sub: "3span", rect }};
        }}
        return {{ action: "replace", slot: rx > 0.5 ? 1 : 0 }};
      }}
      if (n === 2 && layout === "v") {{
        const isRight = rx > 0.65;
        if (isRight) return {{ action: "split_to_h_then_3", rect }};
        return {{ action: "replace", slot: ry > 0.5 ? 1 : 0 }};
      }}
      if (n === 3) {{
        /* 3 panes: bottom edge → go to 4, otherwise replace */
        const isBottom = ry > 0.65;
        if (isBottom && (layout === "3bl" || layout === "3br")) {{
          return {{ action: "expand4", rect }};
        }}
        if (layout === "3span" && ry > 0.5) {{
          /* drop on bottom-span: check left/right to decide expand to 4 */
          if (rx < 0.35 || rx > 0.65) return {{ action: "expand4", rect }};
          return {{ action: "replace", slot: 2 }};
        }}
        const pane = e.target.closest(".pane-trace-pane");
        return pane ? {{ action: "replace", slot: parseInt(pane.getAttribute("data-slot"), 10) }} : null;
      }}
      return null;
    }};

    /* ── drop indicator ── */
    const showIndicator = (e) => {{
      const zone = detectZone(e);
      if (!zone) {{ dropEl.style.display = "none"; return; }}
      const cr = contentEl.getBoundingClientRect();
      dropEl.style.display = "block";
      if (zone.action === "split" && zone.zone === "right") {{
        dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
        dropEl.style.top = cr.top + "px";
        dropEl.style.width = (cr.width * 0.5) + "px";
        dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "split" && zone.zone === "bottom") {{
        dropEl.style.left = cr.left + "px";
        dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
        dropEl.style.width = cr.width + "px";
        dropEl.style.height = (cr.height * 0.5) + "px";
      }} else if (zone.action === "expand3") {{
        if (zone.sub === "3bl") {{
          dropEl.style.left = cr.left + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = (cr.width * 0.5) + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }} else if (zone.sub === "3br") {{
          dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = (cr.width * 0.5) + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }} else {{
          dropEl.style.left = cr.left + "px";
          dropEl.style.top = (cr.top + cr.height * 0.5) + "px";
          dropEl.style.width = cr.width + "px";
          dropEl.style.height = (cr.height * 0.5) + "px";
        }}
      }} else if (zone.action === "split_to_h_then_3") {{
        dropEl.style.left = (cr.left + cr.width * 0.5) + "px";
        dropEl.style.top = cr.top + "px";
        dropEl.style.width = (cr.width * 0.5) + "px";
        dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "expand4") {{
        dropEl.style.left = cr.left + "px"; dropEl.style.top = cr.top + "px";
        dropEl.style.width = cr.width + "px"; dropEl.style.height = cr.height + "px";
      }} else if (zone.action === "replace") {{
        const pane = contentEl.querySelector(`[data-slot="${{zone.slot}}"]`);
        if (pane) {{
          const pr = pane.getBoundingClientRect();
          dropEl.style.left = pr.left + "px"; dropEl.style.top = pr.top + "px";
          dropEl.style.width = pr.width + "px"; dropEl.style.height = pr.height + "px";
        }}
      }}
    }};

    /* ── drag events on content ── */
    contentEl.addEventListener("dragover", e => {{ e.preventDefault(); showIndicator(e); }});
    contentEl.addEventListener("dragleave", () => {{ dropEl.style.display = "none"; }});
    contentEl.addEventListener("drop", e => {{
      e.preventDefault();
      dropEl.style.display = "none";
      const agent = e.dataTransfer.getData("text/plain");
      if (!agent || !agents.includes(agent)) return;
      const zone = detectZone(e);
      if (!zone) return;
      if (zone.action === "replace") {{
        paneAgents[zone.slot] = agent;
        const body = contentEl.querySelector(`[data-slot="${{zone.slot}}"] .pane-trace-body`);
        const badge = contentEl.querySelector(`[data-slot="${{zone.slot}}"].pane-trace-pane-badge, .pane-trace-pane[data-slot="${{zone.slot}}"] .pane-trace-pane-badge`);
        if (body) {{ body.innerHTML = "Loading..."; fetchTo(agent, body, true); }}
        if (badge) {{ badge.innerHTML = paneBadgeHtml(agent); }}
        if (zone.slot === 0) buildTabs();
        return;
      }}
      if (zone.action === "split") {{
        layout = zone.dir;
        paneAgents[1] = agent;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "expand3") {{
        /* 2 → 3: add one pane in the chosen sub-layout */
        layout = zone.sub;
        paneAgents[2] = agent;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "split_to_h_then_3") {{
        /* v2 → rearrange as 3bl (top-left, top-right=new, bottom-left=old-slot1) */
        const old1 = paneAgents[1];
        layout = "3span";
        paneAgents[1] = agent;
        paneAgents[2] = old1;
        buildTabs();
        rebuildPanes();
        return;
      }}
      if (zone.action === "expand4") {{
        const prevN = slotCount();
        layout = "4";
        if (prevN === 3) {{
          paneAgents[3] = agent;
        }} else {{
          paneAgents[2] = agent;
          paneAgents[3] = agents.find(a => a !== paneAgents[0] && a !== paneAgents[1] && a !== agent) || agents[0];
        }}
        buildTabs();
        rebuildPanes();
      }}
    }});

    /* ── tab bar ── */
    const buildTabs = () => {{
      const n = slotCount();
      const activeSet = new Set(paneAgents.slice(0, n).filter(Boolean));
      tabsEl.innerHTML = agents.map(a =>
        `<button class="pane-trace-tab${{activeSet.has(a) ? " active" : ""}}" data-agent="${{escapeHtml(a)}}" draggable="true">${{tabLabelHtml(a)}}</button>`
      ).join("");
      tabsEl.querySelectorAll(".pane-trace-tab").forEach(tab => {{
        tab.addEventListener("click", () => switchAgent(tab.dataset.agent));
        tab.addEventListener("dragstart", (e) => {{
          e.dataTransfer.setData("text/plain", tab.dataset.agent);
          e.dataTransfer.effectAllowed = "copyMove";
        }});
      }});
      applyThinkingState();
      requestAnimationFrame(() => {{
        const active = tabsEl.querySelector(".pane-trace-tab.active");
        if (active) active.scrollIntoView({{ inline: "center", block: "nearest" }});
      }});
    }};

    /* ── switch main agent (slot 0) ── */
    const switchAgent = (agent) => {{
      if (!agents.includes(agent)) return;
      paneAgents[0] = agent;
      document.title = layout === "single" ? `${{agent}} Pane Trace` : "Pane Trace";
      buildTabs();
      const body = contentEl.querySelector('[data-slot="0"] .pane-trace-body');
      const badge = contentEl.querySelector('.pane-trace-pane[data-slot="0"] .pane-trace-pane-badge');
      if (body) {{ body.innerHTML = "Loading..."; fetchTo(agent, body, true); }}
      if (badge) {{ badge.innerHTML = paneBadgeHtml(agent); }}
    }};

    /* ── postMessage from parent ── */
    window.addEventListener("message", (e) => {{
      if (e.data && e.data.type === "switchAgent" && e.data.agent) switchAgent(e.data.agent);
    }});

    /* ── init ── */
    buildTabs();
    rebuildPanes();
    fetchStatuses();
    statusInterval = setInterval(fetchStatuses, pollMs);
    setInterval(() => {{
      const body = contentEl.querySelector('[data-slot="0"] .pane-trace-body');
      if (body && paneAgents[0]) fetchTo(paneAgents[0], body, false);
    }}, pollMs);
    document.addEventListener("visibilitychange", () => {{
      if (document.hidden) return;
      const n = slotCount();
      for (let i = 0; i < n; i++) {{
        const body = contentEl.querySelector(`[data-slot="${{i}}"] .pane-trace-body`);
        if (body && paneAgents[i]) fetchTo(paneAgents[i], body, false);
      }}
      fetchStatuses();
    }});
  </script>
</body>
</html>"""
