from __future__ import annotations

import json

CHAT_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="rgb(38, 38, 36)">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="agent-index chat">
  <link rel="manifest" href="/app.webmanifest">
  <title>agent-index chat</title>
  <script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js"></script>
  <style>
    @font-face {
      font-family: "anthropicSerif";
      src: url("/font/anthropic-serif-roman.ttf") format("truetype");
      font-style: normal;
      font-weight: 300 800;
      font-display: swap;
    }
    @font-face {
      font-family: "anthropicSerif";
      src: url("/font/anthropic-serif-italic.ttf") format("truetype");
      font-style: italic;
      font-weight: 300 800;
      font-display: swap;
    }
    @font-face {
      font-family: "anthropicSans";
      src: url("/font/anthropic-sans-roman.ttf") format("truetype");
      font-style: normal;
      font-weight: 300 800;
      font-display: swap;
    }
    @font-face {
      font-family: "anthropicSans";
      src: url("/font/anthropic-sans-italic.ttf") format("truetype");
      font-style: italic;
      font-weight: 300 800;
      font-display: swap;
    }
    @font-face {
      font-family: "jetbrainsMono";
      src: local("JetBrains Mono"),
           local("JetBrainsMono-Regular"),
           url("/font/jetbrains-mono.ttf") format("truetype-variations"),
           url("/font/jetbrains-mono.ttf") format("truetype");
      font-style: normal;
      font-weight: 100 800;
      font-display: swap;
    }    @keyframes paneReveal {
      0% {
        opacity: 0;
        filter: blur(8px);
      }
      100% {
        opacity: 1;
        filter: blur(0);
      }
    }
    .trace-tooltip {
      position: fixed;
      background: rgba(38, 38, 36, 0.69);
      backdrop-filter: blur(16px) saturate(140%);
      -webkit-backdrop-filter: blur(16px) saturate(140%);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 18px;
      padding: 11px 12px;
      font-family: Menlo, Monaco, "Cascadia Mono", "SF Mono", monospace;
      font-size: 10px;
      line-height: 1.2;
      color: rgb(161, 168, 179);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: normal;
      z-index: 1000;
      display: none;
      box-shadow: none;
      pointer-events: none;
      width: max-content;
      max-height: calc(100vh - 40px);
      overflow: hidden;
      animation: paneReveal 450ms cubic-bezier(0.175, 0.885, 0.32, 1.2) forwards;
      transform-origin: top center;
      will-change: opacity, filter;
    }
    :root {
      color-scheme: dark;
      --bg-rgb: 38, 38, 36;
      --bg: rgb(var(--bg-rgb));
      --panel: rgba(0, 0, 0, 0.96);
      --panel-strong: rgba(0, 0, 0, 0.98);
      --line: rgba(255, 255, 255, 0.08);
      --text: #d7dde5;
      --muted: #88919b;
      --chrome-muted: rgb(156, 154, 147);
      --chip-border-idle: rgba(255, 255, 255, 0.12);
      --chip-border-active: rgba(255, 255, 255, 0.18);
      --chip-border-pressed: rgba(255, 255, 255, 0.24);
      --chip-border-mobile-active: rgba(255, 255, 255, 0.3);
      --mobile-message-inline-pad: 8px;
      --mobile-user-row-gutter: 28px;
      --math-display-inline-pad: 2px;
      --viewport-center-gutter: clamp(12px, 3vw, 28px);
      --user-accent: #b7c2d0;
      --claude-accent: #b7c2d0;
      --codex-accent: #b7c2d0;
      --gemini-accent: #b7c2d0;
      --copilot-accent: #b7c2d0;
      --system-accent: #6a7078;
    }
    * { box-sizing: border-box; }
    ::-webkit-scrollbar { width: 14px; height: 14px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border: 4px solid transparent; background-clip: padding-box; border-radius: 999px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); border: 4px solid transparent; background-clip: padding-box; }
    html,
    body {
      min-height: 100vh;
      min-height: 100svh;
      min-height: 100dvh;
      -webkit-text-size-adjust: 100%;
      text-size-adjust: 100%;
      background: var(--bg);
    }
    body {
      margin: 0;
      width: 100%;
      max-width: 100%;
      overflow-x: clip;
      display: flex;
      align-items: stretch;
      justify-content: center;
      font-family: "SF Pro Display", "Segoe UI", sans-serif;
      background: rgb(38, 38, 36);
      color: var(--text);
    }
    .shell {
      position: relative;
      width: 100vw;
      max-width: 100vw;
      height: 100vh;
      height: 100svh;
      height: 100dvh;
      margin: 0;
      display: grid;
      grid-template-rows: 1fr;
      grid-template-columns: 1fr;
      border: none;
      border-radius: 0;
      overflow: hidden;
      background: rgb(38, 38, 36);
      box-shadow: none;
    }
    .mobile-top-frost {
      display: none;
    }
    .mobile-bottom-frost {
      display: none;
    }
    header {
      grid-area: 1 / 1;
      align-self: start;
      min-width: 0;
      padding: 14px 18px 24px;
      border-bottom: none;
      background: transparent;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      position: relative;
      z-index: 20;
    }
    header::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(180deg,
        rgba(38,38,36,1.0)  0%,
        rgba(38,38,36,1.0)  48%,
        rgba(38,38,36,0.82) 84%,
        transparent      100%
      );
      backdrop-filter: blur(24px) saturate(160%);
      -webkit-backdrop-filter: blur(24px) saturate(160%);
      mask-image: linear-gradient(180deg, black 0%, black 74%, transparent 100%);
      -webkit-mask-image: linear-gradient(180deg, black 0%, black 74%, transparent 100%);
      z-index: -1;
      pointer-events: none;
    }
    .header-main {
      min-width: 0;
      width: 100%;
      display: flex;
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .header-left {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      min-width: 0;
      flex: 1;
    }
    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }
    .title-area {
      min-width: 0;
    }
    .agent-icon,
    .filter-chip .filter-icon {
      width: 14px;
      height: 14px;
      flex-shrink: 0;
      display: block;
    }
    .agent-icon {
      position: relative;
      background-color: rgb(156, 154, 147);
      -webkit-mask: var(--agent-icon-mask) center / contain no-repeat;
      mask: var(--agent-icon-mask) center / contain no-repeat;
      filter: none;
      opacity: 0.78;
      transition: background-color 140ms ease, filter 140ms ease, opacity 140ms ease;
    }
    .agent-icon::before {
      content: "";
      position: absolute;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      top: -2px;
      right: -2px;
      background: transparent;
      box-shadow: 0 0 4px transparent;
      z-index: 1;
      transition: background 150ms ease, box-shadow 150ms ease;
    }
    @keyframes dropdownIn {
      from { opacity: 0; transform: translateY(12px) scale(0.97); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes dropdownOut {
      from { opacity: 1; transform: translateY(0) scale(1); }
      to { opacity: 0; transform: translateY(8px) scale(0.98); }
    }
    @keyframes restartingPulse {
      0%, 100% {
        color: rgb(250, 249, 245);
        background-color: rgba(255, 255, 255, 0.02);
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04), 0 0 0 rgba(255, 255, 255, 0);
        text-shadow: none;
      }
      50% {
        color: #ffffff;
        background-color: rgba(255, 255, 255, 0.07);
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14), 0 0 14px rgba(255, 255, 255, 0.08);
        text-shadow: 0 0 12px rgba(255, 255, 255, 0.16);
      }
    }
    #fileDropdown {
      position: fixed;
      background: rgb(25, 24, 23);
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      border: none;
      border-radius: 16px;
      overflow-y: auto;
      overflow-x: hidden;
      max-height: 200px;
      z-index: 9998;
      display: none;
      box-shadow: none;
      padding: 0;
      box-sizing: border-box;
      will-change: transform, opacity;
    }
    #fileDropdown.visible {
      display: block !important;
      animation: dropdownIn 250ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    #fileDropdown.closing {
      display: block !important;
      animation: dropdownOut 150ms ease-in forwards;
    }
    .file-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 16px;
      border-radius: 0;
      font-family: "anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", sans-serif;
      font-style: normal;
      font-size: 14px;
      font-weight: 400;
      font-variation-settings: "wght" 400, "opsz" 14;
      letter-spacing: -0.01em;
      line-height: 20px;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      color: rgb(250, 249, 245);
      cursor: pointer;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      transition: background 120ms ease, color 120ms ease;
    }
    .file-item-icon {
      font-size: 14px;
      opacity: 0.85;
      flex-shrink: 0;
    }
    .file-item-path {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .file-item:not(:last-child) {
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .has-hover .file-item:hover, .file-item.active {
      background: rgb(20, 20, 19);
      color: rgb(250, 249, 245);
    }
    .eyebrow {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 10px;
      margin-bottom: 6px;
      display: none;
    }
    .title-row {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 12px;
      margin-bottom: 0;
      width: 100%;
    }
    .header-plus-title {
      display: block;
      padding: 4px 12px 10px;
      font: 500 12px/1.4 "SF Pro Text","Segoe UI",sans-serif;
      color: var(--chrome-muted);
      letter-spacing: 0.02em;
    }
    h1 { margin: 0; font-size: clamp(22px, 3vw, 30px); line-height: 1; }
    .title-row h1 { display: none; }
    .sub {
      display: none;
      align-items: center;
      justify-content: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 0;
      margin-left: 8px;
      padding: 8px 10px;
      width: auto;
      max-width: 100%;
      box-sizing: border-box;
      border: 1px solid rgba(255,255,255,0.16);
      border-radius: 18px;
      background: rgba(0, 0, 0, 0.24);
      backdrop-filter: blur(4px) saturate(110%);
      -webkit-backdrop-filter: blur(4px) saturate(110%);
      box-shadow:
        0 6px 18px rgba(0,0,0,0.18),
        inset 0 1px 0 rgba(255,255,255,0.06);
    }
    .sub #count,
    .sub #filter,
    .sub #mode,
    .sub #state,
    .sub #source,
    .sub .search-input,
    .sub .search-count,
    .sub .agent-filter-chips {
      display: none;
    }
    .pill {
      padding: 5px 9px;
      border-radius: 999px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
    }
    .composer {
      grid-area: 1 / 1;
      align-self: end;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
      padding: 30px 12px 14px;
      border-top: none;
      background: transparent;
      position: relative;
      z-index: 20;
    }
    .composer::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(0deg,
        rgba(38,38,36,1.0) 0%,
        rgba(38,38,36,0.88) 18%,
        rgba(38,38,36,0.58) 42%,
        rgba(38,38,36,0.18) 68%,
        transparent 100%
      );
      backdrop-filter: blur(24px) saturate(160%);
      -webkit-backdrop-filter: blur(24px) saturate(160%);
      mask-image: linear-gradient(0deg, black 35%, transparent 100%);
      -webkit-mask-image: linear-gradient(0deg, black 35%, transparent 100%);
      z-index: -1;
      pointer-events: none;
    }
    .composer > * {
      z-index: 1;
    }
    .composer > .mobile-bottom-frost {
      z-index: 0;
    }
    .composer-main-shell {
      grid-column: 1 / -1;
      display: grid;
      gap: 10px;
      min-width: 0;
      transition: border-color 0.4s ease;
    }
    .has-hover .composer-main-shell:hover {
      border-color: rgba(255, 255, 255, 0.16) !important;
    }
    .target-picker {
      grid-column: 1 / -1;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      min-width: 0;
      position: relative;
      z-index: 6;
      overflow: visible;
    }
    .composer-stack {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: end;
      gap: 10px;
      min-width: 0;
      position: relative;
      z-index: 1;
    }
    .quick-actions {
      grid-column: 1 / -1;
      display: none;
      flex-wrap: wrap;
      gap: 6px;
      min-width: 0;
    }
    .quick-more {
      display: contents;
    }
    .quick-more > summary {
      display: none;
    }
    .quick-more-menu {
      display: contents;
    }
    .composer-plus-menu {
      position: relative;
      display: block;
      grid-column: 1;
      align-self: end;
      width: 46px;
      height: 46px;
      flex: 0 0 auto;
      z-index: 100;
    }
    .composer-plus-toggle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 46px;
      height: 46px;
      padding: 0;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(0, 0, 0, 0.24);
      color: rgba(236, 241, 248, 0.92);
      box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.05),
        0 4px 12px rgba(0,0,0,0.18);
      cursor: pointer;
      list-style: none;
      backdrop-filter: blur(4px) saturate(110%);
      -webkit-backdrop-filter: blur(4px) saturate(110%);
      transition: transform 120ms ease, border-color 120ms ease, background 250ms ease;
    }
    .has-hover .composer-plus-toggle:hover {
      background: rgb(36, 35, 34);
      border-color: rgba(255,255,255,0.32);
      color: rgb(215, 215, 210);
    }
    .composer-plus-toggle:active {
      background: rgba(255,255,255,0.1);
      border-color: rgba(255,255,255,0.28);
    }
    .composer-plus-toggle::-webkit-details-marker {
      display: none;
    }
    .composer-plus-toggle svg {
      width: 20px;
      height: 20px;
      display: block;
    }
    .composer-plus-menu[open] .composer-plus-toggle {
      transform: scale(0.95);
      border-color: rgba(255,255,255,0.28);
      background: rgba(255,255,255,0.1);
    }
    .composer-plus-panel {
      position: absolute;
      left: 0;
      bottom: calc(100% + 12px);
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 160px;
      padding: 8px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(38, 38, 36, 0.72);
      box-shadow: none;
      backdrop-filter: blur(16px) saturate(140%);
      -webkit-backdrop-filter: blur(16px) saturate(140%);
      opacity: 0;
      visibility: hidden;
      transform: translateY(4px) scale(0.98);
      transform-origin: bottom left;
      pointer-events: none;
      transition: opacity 140ms ease, transform 180ms ease, visibility 0s linear 180ms;
    }
    .composer-plus-menu[open] .composer-plus-panel {
      opacity: 1;
      visibility: visible;
      transform: translateY(0) scale(1);
      pointer-events: auto;
      transition: opacity 140ms ease, transform 180ms ease, visibility 0s;
    }
    .composer-plus-panel .quick-action {
      all: unset;
      box-sizing: border-box;
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;
      padding: 9px 12px;
      font-family: "anthropicSans", sans-serif;
      font-style: normal;
      font-size: 14px;
      font-weight: 400;
      line-height: 20px;
      color: rgb(250, 249, 245);
      position: relative;
      cursor: pointer;
      border-radius: 10px;
      transition: color 150ms ease;
    }
    .has-hover .composer-plus-panel .quick-action:hover {
      color: #fff;
    }
    .composer-plus-panel .quick-action[data-forward-action="interrupt"] {
      color: rgba(245, 201, 96, 0.95);
    }
    .composer-plus-panel .quick-action.divider-after {
      background-image: linear-gradient(to right, rgba(255,255,255,0.08), rgba(255,255,255,0.08));
      background-repeat: no-repeat;
      background-size: calc(100% - 24px) 1px;
      background-position: 12px 100%;
    }
    .header-plus-menu {
      position: relative;
      display: block;
      width: 38px;
      height: 38px;
      flex: 0 0 auto;
      z-index: 100;
    }
    .header-plus-toggle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      padding: 0;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.12);
      background: transparent;
      color: rgb(156, 154, 147);
      box-shadow: none;
      cursor: pointer;
      list-style: none;
      font-size: 18px;
      font-weight: 600;
      transition: background 150ms ease, color 150ms ease, border-color 150ms ease;
    }
    .has-hover .header-plus-toggle:hover {
      background: rgb(24, 24, 23);
      border-color: rgba(255,255,255,0.32);
      color: rgb(215, 215, 210);
    }
    .header-plus-toggle:active {
      background: rgb(20, 20, 19);
      border-color: rgba(255,255,255,0.12); /* Keep border visible or use a fixed color */
      color: rgb(235, 235, 230);
      transform: none;
    }
    .header-plus-toggle::-webkit-details-marker {
      display: none;
    }
    .header-plus-toggle svg {
      width: 20px;
      height: 20px;
      display: block;
      stroke-width: 1.7;
    }
    .header-plus-menu[open] .header-plus-toggle {
      background: rgb(20, 20, 19);
      border-color: rgba(255,255,255,0.12); /* Don't use border: none */
      color: rgb(235, 235, 230);
      transform: none;
    }
    .header-plus-panel {
      position: absolute;
      top: calc(100% + 10px);
      left: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 168px;
      padding: 8px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(38, 38, 36, 0.72);
      box-shadow: none;
      backdrop-filter: blur(16px) saturate(140%);
      -webkit-backdrop-filter: blur(16px) saturate(140%);
      opacity: 0;
      visibility: hidden;
      transform: translateY(-4px) scale(0.98);
      transform-origin: top left;
      pointer-events: none;
      transition: opacity 140ms ease, transform 180ms ease, visibility 0s linear 180ms;
    }
    .header-plus-menu[open] .header-plus-panel {
      opacity: 1;
      visibility: visible;
      transform: translateY(0) scale(1);
      pointer-events: auto;
      transition: opacity 140ms ease, transform 180ms ease, visibility 0s;
    }
    .right-menu .header-plus-panel {
      left: auto;
      right: 0;
      transform-origin: top right;
    }
    #attachedFilesMenu .header-plus-panel {
      min-width: 220px;
      max-height: min(400px, 60vh);
      overflow-y: auto;
      left: auto;
      right: 0;
      transform-origin: top right;
    }
    #attachedFilesPanel .quick-action {
      padding: 12px 16px !important;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    #attachedFilesPanel .file-item-icon {
      font-size: 14px;
      opacity: 0.85;
      flex-shrink: 0;
    }
    #attachedFilesPanel .file-item-path {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .attached-files-badge {
      position: absolute;
      top: 3px;
      right: 3px;
      background: rgb(44, 132, 219);
      color: rgb(250, 249, 245);
      border-radius: 999px;
      font-size: 10px;
      font-weight: 700;
      line-height: 1;
      padding: 2px 4px;
      min-width: 16px;
      text-align: center;
      pointer-events: none;
    }
    .header-plus-panel .quick-action {
      all: unset;
      box-sizing: border-box;
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;
      padding: 9px 12px;
      font-family: "anthropicSans", sans-serif;
      font-style: normal;
      font-size: 14px;
      font-weight: 400;
      line-height: 20px;
      color: rgb(250, 249, 245);
      position: relative;
      cursor: pointer;
      background: transparent;
      border-radius: 10px;
    }
    .header-plus-panel .quick-action:hover {
      color: #fff;
    }
    .header-plus-panel .quick-action + .quick-action {
      background-image: linear-gradient(to right, rgba(255,255,255,0.08), rgba(255,255,255,0.08));
      background-repeat: no-repeat;
      background-size: calc(100% - 24px) 1px;
      background-position: 12px 0;
    }
    .quick-action::after {
      content: "";
      display: inline-block;
      width: 28px;
      height: 16px;
      border-radius: 99px;
      margin-left: auto;
      background: rgba(255,255,255,0.12);
      position: relative;
      transition: background 200ms ease;
      flex-shrink: 0;
      display: none; /* Hidden by default, shown for toggleable actions */
    }
    .quick-action::before {
      content: "";
      position: absolute;
      right: 26px;
      top: 13px;
      width: 12px;
      height: 12px;
      background: #fff;
      border-radius: 50%;
      z-index: 2;
      transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1), background 200ms ease;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
      pointer-events: none;
      display: none;
    }
    /* Show switch for toggleable actions */
    .quick-action.auto-on::after, .quick-action.auto-off::after,
    .quick-action.awake-on::after, .quick-action.awake-off::after,
    .quick-action.sound-on::after, .quick-action.sound-off::after,
    .quick-action.tts-on::after, .quick-action.tts-off::after,
    .quick-action.raw-on::after, .quick-action.raw-off::after {
      display: inline-block;
    }
    .quick-action.auto-on::before, .quick-action.auto-off::before,
    .quick-action.awake-on::before, .quick-action.awake-off::before,
    .quick-action.sound-on::before, .quick-action.sound-off::before,
    .quick-action.tts-on::before, .quick-action.tts-off::before,
    .quick-action.raw-on::before, .quick-action.raw-off::before {
      display: block;
    }

    .quick-action.auto-on::after,
    .quick-action.awake-on::after,
    .quick-action.sound-on::after,
    .quick-action.tts-on::after,
    .quick-action.raw-on::after {
      background: rgb(44, 132, 219);
    }
    .quick-action.auto-on::before,
    .quick-action.awake-on::before,
    .quick-action.sound-on::before,
    .quick-action.tts-on::before,
    .quick-action.raw-on::before {
      transform: translateX(12px);
    }
    .header-plus-panel .quick-action.toggle-flash {
      color: #f8fbff;
      text-shadow: 0 0 10px rgba(255,255,255,0.14);
    }
    .header-plus-panel .quick-action.restarting {
      animation: restartingPulse 900ms ease-in-out infinite;
    }
    .target-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      position: relative;
      padding: 7px 10px;
      border-radius: 8px; /* Reduced roundness */
      border: 0.5px solid rgba(255,255,255,0.18);
      background: rgba(255,255,255,0.06);
      color: rgb(156, 154, 147);
      font-size: 13px;
      line-height: 1.2;
      letter-spacing: 0.01em;
      cursor: pointer;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      transition: none;
    }
    .target-chip .target-icon {
      width: 15px;
      height: 15px;
      flex-shrink: 0;
      display: block;
      filter: brightness(0) invert(0.61) !important;
      opacity: 1;
    }
    .target-chip[data-target="codex"] .target-icon,
    .target-chip[data-target="copilot"] .target-icon,
    .filter-chip[data-agent="codex"] .filter-icon,
    .filter-chip[data-agent="copilot"] .filter-icon {
      filter: invert(1) grayscale(1) brightness(1.35);
    }
    .target-chip.active[data-target="codex"] .target-icon,
    .target-chip.active[data-target="copilot"] .target-icon {
      filter: none;
    }
    .avatar-icon img[alt="codex"],
    .avatar-icon img[alt="copilot"] {
      filter: invert(1) grayscale(1) brightness(1.35);
    }
    .target-chip .target-label {
      text-transform: capitalize;
    }
    .target-chip.auto-approval-notice::after {
      content: "Auto Approal";
      position: absolute;
      left: 50%;
      bottom: calc(100% + 4px);
      transform: translate(-50%, 4px);
      color: var(--chrome-muted);
      font-size: 11px;
      line-height: 1;
      white-space: nowrap;
      pointer-events: none;
      z-index: 3;
      opacity: 0;
      transition: opacity 220ms ease, transform 220ms ease;
    }
    .target-chip.auto-approval-notice.auto-approval-notice-visible::after {
      opacity: 1;
      transform: translate(-50%, 0);
    }
    .target-chip.auto-approval-notice {
      z-index: 7;
    }
    .quick-action {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 5px 9px;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.03);
      color: var(--muted);
      font: 600 12px/1.2 "SF Pro Text","Segoe UI",sans-serif;
      cursor: pointer;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      transition: background 150ms ease, color 150ms ease, border-color 150ms ease, transform 150ms cubic-bezier(0.4, 0, 0.2, 1), box-shadow 150ms ease;
    }
    .quick-action .action-emoji {
      font-size: 13px;
      line-height: 1;
    }
    .quick-action .action-icon {
      width: 14px;
      height: 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      color: currentColor;
    }
    .quick-action .action-icon svg {
      width: 14px;
      height: 14px;
      display: block;
      stroke: currentColor;
    }
    .quick-action .action-mobile {
      display: none;
    }
    .quick-action,
    .header-plus-toggle,
    .composer-plus-toggle,
    .target-chip,
    .copy-btn,
    .reply-btn,
    .reply-cancel-btn,
    .reply-jump-inline,
    .file-card,
    .file-modal-close,
    .filter-chip,
    .send-btn,
    #scrollToBottomBtn {
      -webkit-tap-highlight-color: transparent;
    }
    .quick-action:focus,
    .quick-action:focus-visible,
    .header-plus-toggle:focus,
    .header-plus-toggle:focus-visible,
    .composer-plus-toggle:focus,
    .composer-plus-toggle:focus-visible,
    .target-chip:focus,
    .target-chip:focus-visible,
    .copy-btn:focus,
    .copy-btn:focus-visible,
    .reply-btn:focus,
    .reply-btn:focus-visible,
    .reply-cancel-btn:focus,
    .reply-cancel-btn:focus-visible,
    .reply-jump-inline:focus,
    .reply-jump-inline:focus-visible,
    .file-card:focus,
    .file-card:focus-visible,
    .file-modal-close:focus,
    .file-modal-close:focus-visible,
    .filter-chip:focus,
    .filter-chip:focus-visible,
    .send-btn:focus,
    .send-btn:focus-visible,
    #scrollToBottomBtn:focus,
    #scrollToBottomBtn:focus-visible {
      outline: none !important;
      -webkit-focus-ring-color: transparent !important;
    }
    .has-hover .quick-action:hover:not(:disabled) {
      background: rgb(25, 25, 24);
      color: #fff;
      border-color: rgba(255,255,255,0.25);
      transform: none;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .quick-action:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .quick-action.restarting:disabled {
      opacity: 1;
      cursor: default;
    }
    .quick-action[data-shortcut="interrupt"] {
      margin-left: auto;
      border-color: rgba(245, 158, 11, 0.32);
      color: #fbbf24;
    }
    .has-hover .quick-action[data-shortcut="interrupt"]:hover:not(:disabled) {
      background: rgba(245, 158, 11, 0.12);
      border-color: rgba(245, 158, 11, 0.55);
      color: #fcd34d;
    }
    .quick-action.raw-send-btn {
      border-style: dashed;
      border-color: rgba(214, 222, 235, 0.2);
      background: rgba(214, 222, 235, 0.045);
      color: rgba(214, 222, 235, 0.82);
    }
    .has-hover .quick-action.raw-send-btn:hover:not(:disabled) {
      background: rgba(214, 222, 235, 0.1);
      border-color: rgba(214, 222, 235, 0.34);
      color: #eef3fb;
    }
    .quick-action[data-shortcut="kill"] {
      border-color: rgba(239, 68, 68, 0.45);
      color: #ef4444;
    }
    .has-hover .quick-action[data-shortcut="kill"]:hover:not(:disabled) {
      background: rgba(239, 68, 68, 0.1);
      border-color: rgba(239, 68, 68, 0.8);
      color: #f87171;
    }
    .sub #autoModeBtn,
    .sub #caffeinateBtn,
    .sub #soundBtn,
    .sub #ttsBtn,
    .sub #killBtn {
      all: unset;
      box-sizing: border-box;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font: 400 12px/1.4 "SF Pro Text","Segoe UI",sans-serif;
      cursor: pointer;
      letter-spacing: 0.02em;
    }
    .sub #autoModeBtn::after,
    .sub #caffeinateBtn::after,
    .sub #soundBtn::after,
    .sub #ttsBtn::after,
    .sub #killBtn::after {
      content: "";
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: rgba(255,255,255,0.14);
      opacity: 0.75;
      flex-shrink: 0;
    }
    .has-hover .sub #autoModeBtn:hover,
    .has-hover .sub #caffeinateBtn:hover,
    .has-hover .sub #soundBtn:hover,
    .has-hover .sub #ttsBtn:hover,
    .has-hover .sub #killBtn:hover {
      color: var(--text);
    }
    #autoModeBtn.auto-on::after {
      background: #4ade80;
      box-shadow: 0 0 6px rgba(74,222,128,0.35);
      opacity: 1;
    }
    #caffeinateBtn.awake-on::after {
      background: #fbbf24;
      box-shadow: 0 0 6px rgba(251,191,36,0.3);
      opacity: 1;
    }
    #soundBtn.sound-on::after {
      background: #63cab7;
      box-shadow: 0 0 6px rgba(99,202,183,0.3);
      opacity: 1;
    }
    .kill-btn {
      color: #ef4444;
    }
    .kill-btn::after {
      background: #ef4444 !important;
      box-shadow: 0 0 6px rgba(239,68,68,0.28);
      opacity: 1 !important;
    }
    .has-hover .kill-btn:hover {
      color: #f87171;
    }
    .has-hover #soundBtn:hover { color: var(--text); }
    .has-hover #soundBtn.sound-on:hover { background: rgba(99, 202, 183, 0.15); }
    #ttsBtn.tts-on::after {
      background: #a78bfa;
      box-shadow: 0 0 6px rgba(167,139,250,0.3);
      opacity: 1;
    }
    .has-hover #ttsBtn:hover { color: var(--text); }
    .has-hover #ttsBtn.tts-on:hover { background: rgba(167, 139, 250, 0.15); }
    /* Tactile button animations */
    .target-chip:active:not(:disabled),
    .quick-action:active:not(:disabled),
    .copy-btn:active,
    .reply-btn:active,
    .reply-cancel-btn:active,
    .header-plus-toggle:active,
    .composer-plus-toggle:active {
      transform: none;
    }
    #scrollToBottomBtn:active {
      transform: translateX(-50%) scale(0.92);
    }
    
    @media (hover: hover) and (pointer: fine) {
      .target-chip:hover:not(.active),
      .target-chip:active:not(.active) {
        background: rgb(46, 46, 44);
        border-color: rgba(255,255,255,0.32);
        color: rgb(215, 215, 210); /* Brighter text on hover */
        transform: none;
        box-shadow: none;
      }
      .target-chip:hover:not(.active) .target-icon,
      .target-chip:active:not(.active) .target-icon {
        filter: brightness(0) invert(0.82) !important; /* Brighter icon on hover */
      }
      /* Ensure absolute stability when hovering an active chip */
      .target-chip.active:hover {
        background: rgb(33, 32, 31) !important;
        color: rgb(235, 235, 230) !important;
        cursor: default;
      }
    }
    .target-chip:active:not(.active) {
      background: rgb(46, 46, 44);
      border-color: rgba(255,255,255,0.32);
      color: rgb(215, 215, 210);
      box-shadow: none;
    }
    .target-chip.active {
      color: rgb(235, 235, 230) !important;
      background: rgb(33, 32, 31) !important;
      border-color: rgba(255,255,255,0.18) !important;
      transform: none !important;
      box-shadow: none !important;
    }
    .target-chip.active .target-icon {
      filter: brightness(0) invert(0.92) !important;
      opacity: 1 !important;
    }
    .composer-shell {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      grid-column: 2;
      min-width: 0;
    }
    .composer-field {
      position: relative;
      border-radius: 24px;
    }
    .send-btn {
      display: none;
      position: absolute;
      right: 9px;
      bottom: 9px;
      width: 38px;
      height: 38px;
      border-radius: 8px; /* Squarish */
      border: 1px solid rgba(215, 225, 238, 0.18);
      background:
        linear-gradient(180deg, rgba(245, 248, 252, 0.98) 0%, rgba(215, 225, 238, 0.98) 100%);
      color: #0f1318;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      box-shadow:
        0 10px 24px rgba(0,0,0,0.28),
        inset 0 1px 0 rgba(255,255,255,0.45);
      transition: transform 120ms ease, box-shadow 150ms ease, filter 150ms ease, background 150ms ease;
    }
    .has-hover .send-btn:hover {
      filter: brightness(1.03);
      box-shadow:
        0 12px 28px rgba(0,0,0,0.34),
        inset 0 1px 0 rgba(255,255,255,0.5);
    }
    .send-btn:active {
      transform: translateY(1px) scale(0.98);
      background:
        linear-gradient(180deg, rgba(210, 218, 230, 0.98) 0%, rgba(175, 188, 206, 0.98) 100%);
      box-shadow:
        0 6px 16px rgba(0,0,0,0.24),
        inset 0 1px 0 rgba(255,255,255,0.34);
    }
    .send-btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
      box-shadow: none;
      filter: none;
    }
    .mic-btn {
      position: absolute;
      right: 9px;
      bottom: 9px;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      border: 1px solid rgba(215, 225, 238, 0.18);
      background:
        linear-gradient(180deg, rgba(245, 248, 252, 0.98) 0%, rgba(215, 225, 238, 0.98) 100%);
      color: #0f1318;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      box-shadow:
        0 10px 24px rgba(0,0,0,0.28),
        inset 0 1px 0 rgba(255,255,255,0.45);
      transition: transform 120ms ease, box-shadow 150ms ease, filter 150ms ease, opacity 150ms ease;
    }
    .has-hover .mic-btn:hover {
      filter: brightness(1.03);
    }
    .mic-btn:active {
      transform: translateY(1px) scale(0.98);
    }
    .mic-btn.hidden {
      opacity: 0;
      pointer-events: none;
      transform: scale(0.95);
    }
    .mic-btn.listening {
      background: linear-gradient(180deg, rgba(255, 80, 80, 0.95) 0%, rgba(210, 30, 30, 0.95) 100%);
      color: #fff;
      border-color: transparent;
      animation: micPulse 1s ease-in-out infinite;
    }
    @keyframes micPulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(255, 60, 60, 0.5), 0 10px 24px rgba(0,0,0,0.28); }
      50% { box-shadow: 0 0 0 7px rgba(255, 60, 60, 0), 0 10px 24px rgba(0,0,0,0.28); }
    }
    .mic-btn.no-speech { display: none; }
    .attach-preview-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 8px 10px 4px;
    }
    .attach-card {
      position: relative;
      width: 80px;
      flex-shrink: 0;
    }
    .attach-card-thumb {
      width: 80px;
      height: 80px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.1);
      object-fit: cover;
      display: block;
    }
    .attach-card-ext {
      width: 80px;
      height: 80px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgb(38,38,36);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: .04em;
      color: rgb(180,178,170);
      text-transform: uppercase;
    }
    .attach-card-name {
      font-size: 10px;
      color: var(--muted);
      text-align: center;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-top: 3px;
      max-width: 80px;
    }
    .attach-card-remove {
      position: absolute;
      top: -5px;
      left: -5px;
      background: rgb(20, 20, 19);
      border: none;
      color: rgb(250, 249, 245);
      width: 20px;
      height: 20px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 11px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      line-height: 1;
    }
    .has-hover .attach-card-remove:hover { filter: brightness(1.3); }
    .composer textarea {
      display: block;
      width: 100%;
      border: none;
      background: rgb(30, 30, 29);
      color: var(--text);
      border-radius: 22px;
      min-height: 46px;
      height: 46px;
      max-height: 200px;
      resize: none;
      padding: 11px 16px;
      font: 400 16px/1.5 "SF Pro Text","Segoe UI",sans-serif;
      box-shadow: none;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      transition: background-color 200ms ease;
      overflow-y: auto;
      box-sizing: border-box;
    }
    .composer textarea:focus {
      outline: none;
      background: rgb(30, 30, 29);
      box-shadow: none;
    }
    .composer textarea::placeholder {
      color: var(--chrome-muted);
    }
    .statusline {
      grid-column: 1 / -1;
      margin-top: -10px;
      padding-left: 72px;
      min-height: 1.3em;
      color: var(--chrome-muted);
      font-size: 11px;
    }
    @media (min-width: 360px) {
      :root {
        --text: rgb(250, 249, 246);
      }
      .header-main {
        align-items: center;
      }
      header::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 84px;
        background: linear-gradient(180deg, 
          rgba(var(--bg-rgb), 0.98) 0%,
          rgba(var(--bg-rgb), 0.88) 42%,
          rgba(var(--bg-rgb), 0.46) 76%,
          rgba(var(--bg-rgb), 0) 100%);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        mask-image: linear-gradient(180deg, black 0%, black 56%, transparent 100%);
        -webkit-mask-image: linear-gradient(180deg, black 0%, black 56%, transparent 100%);
        z-index: -1;
        pointer-events: none;
      }
      .title-row {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        min-height: 38px;
      }
      .header-left {
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: flex-start !important;
        min-width: 0 !important;
        width: auto !important;
        flex: 1 1 auto !important;
      }
      .header-right {
        display: flex !important;
        align-items: center !important;
        justify-content: flex-end !important;
        align-self: center !important;
        gap: 12px !important;
        min-height: 38px;
        flex: 0 0 auto !important;
      }

      .title-row .header-plus-menu {
        display: flex;
        align-items: center;
        justify-content: center;
        align-self: center;
        margin-left: -10px;
        margin-top: 0;
      }
      .right-menu {
        display: flex;
        align-items: center;
        justify-content: center;
        align-self: center;
        margin-left: 8px;
        margin-top: 0;
        margin-right: -10px;
      }
      .right-menu .header-plus-panel {
        left: auto;
        right: 0;
        transform-origin: top right;
      }
      .trace-tooltip {
        left: 50% !important;
        right: auto !important;
        transform: translateX(-50%) !important;
        width: calc(100vw - 32px) !important;
        max-width: calc(100vw - 32px) !important;
      }
      .header-plus-toggle {
        padding: 0;
        width: 38px;
        height: 38px;
        min-width: 38px;
        min-height: 38px;
        border: none;
        background: transparent;
        box-shadow: none;
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
        color: rgb(156, 154, 147);
        border-radius: 10px;
      }
      .has-hover .header-plus-toggle:hover {
        background: rgb(24, 24, 23);
        border-color: transparent;
        color: rgb(215, 215, 210);
      }
      .header-plus-toggle:active {
        background: rgba(20, 20, 19, 0.92);
        border-color: transparent;
        color: rgb(235, 235, 230);
        transform: none;
      }
      .header-plus-toggle svg {
        width: 20px;
        height: 20px;
        stroke-width: 1.7;
      }
      .header-plus-menu[open] .header-plus-toggle {
        background: rgb(20, 20, 19);
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: none;
        color: rgb(235, 235, 230);
        transform: none;
      }
      .message.claude .md-body,
      .message.codex .md-body,
      .message.gemini .md-body,
      .message.copilot .md-body {
        font-family: "anthropicSerif", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, serif;
      }
      .target-chip {
        padding: 10px 16px;
        border: 0.5px solid transparent;
        background: transparent; /* Transparent until hovered */
        color: var(--chrome-muted);
        box-shadow: none;
        font-size: 13px; /* Shrunk */
        border-radius: 12px;
        transition: none;
      }
      .target-chip .target-icon {
        width: 18px; /* Shrunk */
        height: 18px;
      }
      .has-hover .target-chip:hover:not(.active),
      .target-chip:active:not(.active) {
        background: transparent;
        border-color: var(--chip-border-idle);
        color: var(--chrome-muted);
        transform: none;
        box-shadow: none;
      }
      .has-hover .target-chip:hover:not(.active) .target-icon,
      .target-chip:active:not(.active) .target-icon {
        filter: brightness(0) invert(0.61) !important;
      }
      .has-hover .target-chip.active:hover {
        background: rgb(33, 32, 31) !important;
        border-color: rgba(255,255,255,0.18) !important;
        color: rgb(235, 235, 230) !important;
        cursor: default;
      }
      .target-chip:active:not(.active) {
        background: transparent;
        border-color: rgba(255,255,255,0.12);
        color: rgb(156, 154, 147);
        box-shadow: none;
      }
      .target-chip.active {
        border-color: rgba(255,255,255,0.08) !important;
        background: rgb(33, 32, 31) !important;
        color: rgb(235, 235, 230) !important;
        transform: none !important;
        box-shadow: none !important;
      }
      .target-chip.active .target-icon {
        filter: brightness(0) invert(0.92) !important;
        opacity: 1 !important;
      }
      .composer-main-shell {
        position: relative; /* Make container relative for send-btn */
        grid-template-columns: 46px minmax(0, 1fr);
        grid-template-areas:
          "input input"
          "plus targets";
        row-gap: 0;
        column-gap: 4px;
        padding: 3px 5px 5px 5px;
        border-radius: 20px; /* Adjusted to be less square */
        background: rgb(48, 48, 46);
        border: 0.5px solid rgb(58, 58, 56);
        transition: border-color 0.4s ease;
      }
      .has-hover .composer-main-shell:hover {
        border-color: rgba(255, 255, 255, 0.16) !important;
      }
      .target-picker {
        grid-area: targets;
        width: 100%;
        margin: -3px 0 0;
        padding-left: 14px;
        justify-self: start;
        align-self: center;
        justify-content: flex-start;
        gap: 6px;
      }
      .statusline {
        position: fixed;
        right: 12px;
        bottom: 0;
        padding: 4px 8px;
        font-size: 11px;
        color: var(--chrome-muted);
        text-align: right;
        z-index: 1000;
        pointer-events: none;
        background: transparent;
      }
      .composer-stack {
        display: contents;
      }
      .composer {
        padding-bottom: 24px;
      }
      .composer-shell {
        grid-area: input;
        align-self: stretch;
      }
      .composer-field {
        position: relative;
      }
      .composer-plus-menu {
        grid-area: plus;
        justify-self: start;
        align-self: center;
        width: 38px;
        height: 38px;
        margin: 0 0 1px 2px;
      }
      .composer-plus-panel {
        left: -24px;
        bottom: calc(100% + 8px);
      }
      .composer-plus-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        height: 38px;
        padding: 0;
        border: none;
        background: transparent;
        color: rgb(156, 154, 147);
        box-shadow: none;
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
        border-radius: 10px;
        transition: background 150ms ease, color 150ms ease;
      }
      .has-hover .composer-plus-toggle:hover {
        background: rgb(24, 24, 23);
        border-color: transparent;
        color: rgb(215, 215, 210);
      }
      .composer-plus-toggle:active {
        background: rgb(20, 20, 19);
        border-color: transparent;
        color: rgb(235, 235, 230);
        transform: none;
      }
      .composer-plus-toggle svg {
        width: 20px;
        height: 20px;
        stroke-width: 1.7;
      }
      .composer-plus-menu[open] .composer-plus-toggle {
        border: none;
        background: rgb(20, 20, 19);
        color: rgb(235, 235, 230);
        transform: none;
      }
      .composer textarea {
        appearance: none;
        -webkit-appearance: none;
        background: transparent;
        background-color: transparent !important;
        background-image: none !important;
        border-radius: 0;
        box-shadow: none !important;
        -webkit-box-shadow: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        padding: 8px 42px 8px 10px; /* Keep send button room while trimming inner space */
      }
      .composer textarea:focus {
        appearance: none;
        -webkit-appearance: none;
        background: transparent;
        background-color: transparent !important;
        background-image: none !important;
        box-shadow: none !important;
        -webkit-box-shadow: none !important;
      }
      .send-btn {
        display: flex !important;
        position: absolute;
        right: 4px;
        bottom: -40px;
        width: 38px;
        height: 38px;
        border-radius: 10px;
        background: rgb(186, 184, 176) !important;
        color: rgb(26, 25, 24) !important;
        z-index: 100;
        border: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        align-items: center;
        justify-content: center;
        padding: 0;
        opacity: 0;
        transform: translateY(8px) scale(0.95);
        pointer-events: none;
        transition: 
          opacity 150ms ease-in,
          transform 150ms ease-in,
          background 150ms ease,
          filter 150ms ease;
      }
      .send-btn.visible {
        opacity: 1;
        transform: translateY(0) scale(1);
        pointer-events: auto;
        transition: 
          opacity 400ms cubic-bezier(0.23, 1, 0.32, 1),
          transform 400ms cubic-bezier(0.23, 1, 0.32, 1),
          background 150ms ease,
          filter 150ms ease;
      }
      .has-hover .send-btn:hover {
        filter: brightness(1.08);
      }
      .send-btn:active {
        transform: scale(0.96);
        filter: brightness(0.92);
      }
      .mic-btn {
        display: flex !important;
        position: absolute;
        right: 4px;
        bottom: -40px;
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: rgb(186, 184, 176) !important;
        color: rgb(26, 25, 24) !important;
        z-index: 100;
        border: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        align-items: center;
        justify-content: center;
        padding: 0;
        opacity: 1;
        transform: translateY(0) scale(1);
        pointer-events: auto;
        transition:
          opacity 150ms ease,
          transform 150ms ease,
          background 150ms ease;
      }
      .mic-btn.hidden {
        opacity: 0;
        transform: translateY(8px) scale(0.95);
        pointer-events: none;
      }
      .mic-btn.listening {
        background: rgb(210, 50, 50) !important;
        color: #fff !important;
        animation: micPulse 1s ease-in-out infinite;
      }
    }
    @media (min-width: 360px) and (max-width: 430px) {
      html,
      body,
      .shell {
        overflow-x: clip;
        overscroll-behavior-x: none;
      }
      main {
        overflow-x: clip;
        overscroll-behavior-x: none;
      }
      .header-plus-menu {
        width: 48px;
        height: 48px;
      }
      @keyframes headerPop {
        0% { transform: scale(1); background: rgba(20, 20, 19, 0.48); }
        40% { transform: scale(1.25); background: rgba(24, 24, 23, 0.85); border-color: rgba(255, 255, 255, 0.25); }
        100% { transform: scale(1); background: rgba(20, 20, 19, 0.48); border-color: rgba(255, 255, 255, 0.18); }
      }
      .header-plus-toggle {
        width: 48px;
        height: 48px;
        min-width: 48px;
        min-height: 48px;
        border-radius: 999px;
        background: rgba(20, 20, 19, 0.48);
        border: 1px solid rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(12px) saturate(160%);
        -webkit-backdrop-filter: blur(12px) saturate(160%);
        box-shadow: none !important;
        color: rgb(235, 235, 230);
        -webkit-tap-highlight-color: transparent;
        transition: transform 200ms ease, background 200ms ease;
        outline: none !important;
      }
      .header-plus-toggle.animating {
        animation: headerPop 500ms cubic-bezier(0.25, 0.1, 0.25, 1) forwards;
        z-index: 10011;
      }
      .header-plus-toggle:active {
        background: rgba(24, 24, 23, 0.85) !important;
        transform: scale(1.15); /* Immediate feedback before animation starts */
        transition: transform 100ms ease;
      }
      .header-plus-toggle:focus {
        outline: none !important;
      }
      .header-plus-toggle svg {
        width: 22px;
        height: 22px;
      }
      .header-plus-menu[open] .header-plus-toggle {
        background: rgba(20, 20, 19, 0.48);
        border-color: rgba(255, 255, 255, 0.18);
        box-shadow: none;
        transform: none;
      }
      .header-plus-menu:not([open]) .header-plus-toggle:active {
        background: rgba(24, 24, 23, 0.85) !important;
        border-color: rgba(255, 255, 255, 0.25) !important;
        transform: scale(1.15);
      }
      .message-body-row {
        display: block !important;
        width: 100% !important;
      }
      .message.user .message-body-row {
        width: fit-content !important;
        max-width: 100% !important;
        margin-left: auto !important;
      }
      .message.user .message-body-row.has-wide-block,
      .message.user .message-body-row.has-structured-block {
        width: 100% !important;
      }
      .md-body ul, .md-body ol {
        display: block !important;
        width: 100% !important;
        padding-left: 1.2em !important;
        margin: 0.5em 0 !important;
      }
      .md-body li {
        display: list-item !important;
        white-space: normal !important;
        word-break: normal !important;
        overflow-wrap: anywhere !important;
      }
      .composer-plus-menu {
        width: 38px;
        height: 38px;
        margin: 0 0 4px 12px;
      }
      .composer-plus-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        height: 38px;
        padding: 0;
        border: none !important;
        background: transparent !important;
        color: rgb(156, 154, 147);
        box-shadow: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        border-radius: 10px;
        transition: background 150ms ease, color 150ms ease;
        -webkit-tap-highlight-color: transparent;
        outline: none !important;
      }
      .composer-plus-toggle svg {
        width: 20px;
        height: 20px;
      }
      .composer-plus-panel {
        backdrop-filter: blur(24px) saturate(160%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
      }
      .composer-plus-menu[open] .composer-plus-toggle {
        background: rgb(20, 20, 19) !important;
        color: rgb(235, 235, 230);
        transform: none;
      }
      .composer-plus-menu:not([open]) .composer-plus-toggle:active {
        background: rgb(20, 20, 19) !important;
        color: rgb(235, 235, 230);
        transform: none;
      }
      .composer-main-shell {
        background: rgba(30, 30, 28, 0.42);
        border-color: rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(18px) saturate(135%);
        -webkit-backdrop-filter: blur(18px) saturate(135%);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.08),
          0 10px 28px rgba(0,0,0,0.18);
      }
      body:not(.keyboard-locked) .composer-main-shell:not(:focus-within) {
        background: rgba(20, 20, 19, 0.48);
      }
      .target-chip:not(.active),
      .target-chip:not(.active):active,
      .target-chip:not(.active):focus,
      .target-chip:not(.active):focus-visible {
        background: transparent !important;
        background-color: transparent !important;
        background-image: none !important;
        border: none !important;
        border-color: transparent !important;
        box-shadow: none !important;
        -webkit-box-shadow: none !important;
        outline: none !important;
      }
      .target-chip.active {
        background: rgb(20, 20, 19) !important;
        border-color: transparent !important;
        box-shadow: none !important;
      }
      .composer-main-shell:focus-within {
        background: rgba(38, 38, 36, 0.58);
        border-color: rgba(255, 255, 255, 0.2);
      }
      .has-hover .composer-main-shell:hover {
        border-color: rgba(255, 255, 255, 0.16) !important;
      }
      .composer-field {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
      }
      .target-chip {
        appearance: none;
        -webkit-appearance: none;
        background-image: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        justify-content: center;
        gap: 0;
        padding-left: 10px;
        padding-right: 10px;
        border: none !important;
        box-shadow: none !important;
        -webkit-box-shadow: none !important;
        -webkit-tap-highlight-color: transparent;
      }
      .target-chip .target-label {
        display: none;
      }
      .target-chip:active:not(.active) {
        background: transparent;
        border-color: transparent;
        color: var(--chrome-muted);
        box-shadow: none;
      }
    }
    .keyboard-locked main {
      overflow: hidden !important;
      overscroll-behavior: none !important;
    }
    main {
      grid-area: 1 / 1;
      padding: 100px 14px 50dvh;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow-y: auto;
      overscroll-behavior: contain;
      background: transparent;
      z-index: 1;
    }
    #scrollToBottomBtn {
      position: absolute;
      bottom: 150px;
      left: 50%;
      transform: translateX(-50%);
      width: 38px;
      height: 38px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(38, 38, 36, 0.72);
      color: rgb(235, 235, 230);
      font-size: 17px;
      line-height: 1;
      cursor: pointer;
      display: none;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 16px rgba(0,0,0,0.2);
      transition: background 150ms ease, color 150ms ease, opacity 150ms ease, transform 150ms ease;
      z-index: 100;
      backdrop-filter: blur(12px) saturate(160%);
      -webkit-backdrop-filter: blur(12px) saturate(160%);
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
    }
    #scrollToBottomBtn svg {
      width: 20px;
      height: 20px;
      display: block;
      stroke: currentColor;
      stroke-width: 1.7;
    }
    .has-hover #scrollToBottomBtn:hover {
      background: rgba(48, 48, 46, 0.85);
      filter: brightness(1.1);
    }
    #scrollToBottomBtn:active {
      background: rgb(31, 31, 29);
      transform: translateX(-50%) scale(0.96);
    }
    #scrollToBottomBtn.visible { display: flex; }
    .daybreak {
      align-self: center;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgb(30, 30, 29);
      border: none;
      color: var(--chrome-muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .conversation-empty {
      display: grid;
      justify-items: center;
      gap: 14px;
      width: 100%;
      padding: 10px 12px 6px;
      box-sizing: border-box;
    }
    .conversation-empty-card {
      width: min(720px, 100%);
      padding: 18px 18px 16px;
      border-radius: 18px;
      background: rgba(25, 25, 24, 0.9);
      border: 0.5px solid rgba(255,255,255,0.08);
      box-shadow: none;
      color: var(--chrome-muted);
      backdrop-filter: blur(16px) saturate(140%);
      -webkit-backdrop-filter: blur(16px) saturate(140%);
    }
    .conversation-empty-title {
      margin: 0 0 6px;
      color: rgb(250, 249, 245);
      font: 400 18px/1.25 "anthropicSans", sans-serif;
      letter-spacing: -0.02em;
    }
    .conversation-empty-copy {
      margin: 0;
      color: var(--chrome-muted);
      font: 400 14px/1.6 "anthropicSans", sans-serif;
    }
    @media (max-width: 430px) {
      .conversation-empty {
        padding: 8px 10px 6px;
      }
      .conversation-empty-card {
        padding: 15px 14px 14px;
        border-radius: 16px;
      }
      .conversation-empty-title {
        font-size: 16px;
      }
      .conversation-empty-copy {
        font-size: 13px;
      }
    }
    @keyframes msgReveal {
      0% {
        opacity: 0;
        transform: translateY(16px) scale(0.9);
        filter: blur(8px);
      }
      100% {
        opacity: 1;
        transform: translateY(0) scale(1);
        filter: blur(0);
      }
    }
    .message-row {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      max-width: 100%;
      transform-origin: left center;
      will-change: transform, opacity, filter;
      margin-bottom: 0px;
    }
    .message-row:not(.user) {
      padding-left: 10px;
      padding-right: 20px;
      box-sizing: border-box;
    }
    .sender-label {
      font-weight: normal;
      color: var(--chrome-muted) !important;
      text-transform: capitalize;
    }

    .message-row:first-child:not(.user) {
      margin-top: 0;
    }
    /* エージェントメッセージの後にユーザーメッセージが来る場合 */
    .message-row:not(.user) + .message-row.user {
      margin-top: 0px;
    }
    /* ユーザーメッセージの後にエージェントメッセージが来る場合 */
    .message-row.user + .message-row:not(.user) {
      margin-top: 0px;
    }
    .message-row.animate-in {
      animation: msgReveal 180ms cubic-bezier(0.22, 1, 0.36, 1) forwards;
    }
    .message-row.user {
      justify-content: flex-end;
      transform-origin: right center;
      margin-bottom: 0px;
      padding-left: 64px;
      padding-right: 12px;
      box-sizing: border-box;
    }
    .message-row.user .avatar {
      display: none;
    }
    .avatar {
      width: 34px;
      height: 34px;
      flex: 0 0 34px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.03);
      color: var(--text);
      font: 700 12px/1 "SF Pro Text", "Segoe UI", sans-serif;
      text-transform: uppercase;
      box-shadow: 0 4px 10px rgba(0,0,0,0.2), inset 0 2px 4px rgba(255,255,255,0.05);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      position: relative;
      z-index: 1;
      margin-top: -8px; /* Higher */
    }
    .avatar.avatar-icon {
      background: none;
      border-color: transparent;
      box-shadow: none;
    }
    .avatar img {
      width: 28px;
      height: 28px;
      object-fit: contain;
    }
    .message-row.codex .avatar img,
    .message-row.copilot .avatar img {
      filter: invert(1) grayscale(1) brightness(1.35) !important;
    }
    .message-row.user .avatar { color: var(--user-accent); }
    .message-row.claude .avatar { color: var(--claude-accent); }
    .message-row.codex .avatar { color: var(--codex-accent); }
    .message-row.gemini .avatar { color: var(--gemini-accent); }
    .message-row.copilot .avatar { color: var(--copilot-accent); }
    .message-row.system .avatar { color: var(--system-accent); }
    .message-wrap {
      display: flex;
      align-items: flex-start;
      gap: 6px;
      max-width: min(760px, calc(100% - 46px));
      min-width: 0;
      width: 100%;
    }
    .message {
      position: relative;
      flex: 1;
      min-width: 0;
      max-width: 100%;
      border-radius: 20px;
      padding: 12px 16px 16px;
      border: 1px solid rgba(255,255,255,0.035);
      background: rgba(20, 24, 30, 0.65);
      box-shadow: 0 10px 24px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.05);
      backdrop-filter: blur(24px) saturate(150%);
      -webkit-backdrop-filter: blur(24px) saturate(150%);
    }
    .message.user {
      padding: 0;
      background: transparent;
      border-color: transparent;
      box-shadow: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      color: #f7f9fc;
    }
    .message.user .md-body {
      display: block;
      width: 100%;
      max-width: 100%;
      padding: 12px 16px 13px 16px;
      border-radius: 12px;
      background: rgb(20, 20, 19);
      color: rgb(250, 249, 245) !important;
      border: none;
      box-shadow: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
    }
    .message.user .md-body p,
    .message.user .md-body li,
    .message.user .md-body h1,
    .message.user .md-body h2,
    .message.user .md-body h3,
    .message.user .md-body h4 {
      color: rgb(250, 249, 245) !important;
    }
    .message-body-row {
      display: flex;
      align-items: flex-start;
      gap: 6px;
      min-width: 0;
    }
    .message.user .message-body-row {
      display: block;
      width: fit-content;
      max-width: 100%;
      margin-left: auto;
    }
    .message.user .message-body-row.has-wide-block {
      width: 100%;
    }
    .message.user .message-body-row.has-structured-block {
      width: 100%;
    }
    .message.user .message-body-row {
      position: relative;
    }
    .message.user .message-body-row.is-collapsed {
      overflow: hidden;
      max-height: var(--user-collapse-max-height, 245px);
    }
    .message.user .message-body-row.is-collapsed::after {
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: 44px;
      pointer-events: none;
      border-bottom-left-radius: 12px;
      border-bottom-right-radius: 12px;
      background: linear-gradient(180deg, rgba(20, 20, 19, 0) 0%, rgb(20, 20, 19) 78%);
    }
    .message.user .user-collapse-toggle {
      display: none;
      position: absolute;
      right: 12px;
      bottom: 10px;
      z-index: 2;
      padding: 0;
      border: none;
      background: transparent;
      color: rgb(156, 154, 147);
      font: 600 12px/1 "SF Pro Text","Segoe UI",sans-serif;
      letter-spacing: 0.01em;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }
    .message.user .user-collapse-toggle.is-visible {
      display: block;
    }
    .has-hover .message.user .user-collapse-toggle:hover {
      color: rgb(250, 249, 245);
    }
    .message-time-below {
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
      text-align: left;
      opacity: 0.75;
    }
    .message-meta-below {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    .message-meta-below .meta-agent {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: inherit;
      white-space: nowrap;
    }
    .message-meta-below .meta-agent.icon-right .meta-agent-icon {
      order: 2;
    }
    .message-meta-below .meta-agent-icon {
      width: 17px;
      height: 17px;
      flex: 0 0 17px;
      display: block;
      background-color: currentColor;
      -webkit-mask: var(--agent-icon-mask) center / contain no-repeat;
      mask: var(--agent-icon-mask) center / contain no-repeat;
      opacity: 1;
    }
    .message-meta-below .meta-agent-sep {
      color: inherit;
      margin: 0 2px 0 1px;
    }
    .message-meta-below .copy-btn {
      margin-top: 0;
      margin-right: 2px;
      align-self: center;
    }
    .message-meta-below .sender,
    .message-meta-below .arrow,
    .message-meta-below .targets,
    .message-meta-below time {
      opacity: 1;
    }
    .message-meta-below .reply-btn,
    .message-meta-below .reply-target-jump-btn {
      margin-top: 0;
      margin-right: 4px;
      align-self: center;
    }
    .message:not(.user) .message-meta-below {
      margin-top: 12px;
      gap: 7px;
      font-size: 13px;
    }
    .message:not(.user) .message-meta-below .copy-btn,
    .message:not(.user) .message-meta-below .reply-btn,
    .message:not(.user) .message-meta-below .reply-target-jump-btn {
      padding: 5px;
    }
    .message:not(.user) .message-meta-below .copy-btn {
      margin-right: 0;
    }
    .message:not(.user) .message-meta-below .reply-btn,
    .message:not(.user) .message-meta-below .reply-target-jump-btn {
      margin-right: 0;
    }
    .message:not(.user) .message-meta-below .copy-btn svg,
    .message:not(.user) .message-meta-below .reply-btn svg,
    .message:not(.user) .message-meta-below .reply-target-jump-btn svg {
      width: 17px;
      height: 17px;
    }
    .message:not(.user) .message-meta-below .copy-btn svg * {
      stroke-width: 1.45;
    }
    .message:not(.user) .message-meta-below .reply-btn svg *,
    .message:not(.user) .message-meta-below .reply-target-jump-btn svg * {
      stroke-width: 1.8;
    }
    .message.user .user-message-meta {
      width: fit-content;
      margin-top: 8px;
      margin-left: auto;
      gap: 7px;
      font-size: 13px;
      justify-content: flex-end;
    }
    .message.user .user-message-meta time {
      color: var(--chrome-muted) !important;
      white-space: nowrap;
    }
    .message.user .user-message-meta .copy-btn {
      margin-right: 0;
      padding: 5px;
    }
    .message.user .user-message-meta .reply-target-jump-btn {
      margin-right: 0;
      padding: 5px;
    }
    .message.user .user-message-meta .copy-btn svg {
      width: 17px;
      height: 17px;
    }
    .message.user .user-message-meta .reply-target-jump-btn svg {
      width: 17px;
      height: 17px;
    }
    .message.user .user-message-meta .copy-btn svg * {
      stroke-width: 1.45;
    }
    .message.user .user-message-meta .reply-target-jump-btn svg * {
      stroke-width: 1.8;
    }
    @media (min-width: 360px) and (hover: hover) and (pointer: fine) {
      .message.user .user-message-meta,
      .message:not(.user) .message-meta-below {
        opacity: 0;
        pointer-events: none;
        transition: opacity 120ms ease;
      }
      .message-row.user:hover .user-message-meta,
      .message-row.user:focus-within .user-message-meta,
      .message-row:not(.user):hover .message-meta-below,
      .message-row:not(.user):focus-within .message-meta-below {
        opacity: 1;
        pointer-events: auto;
      }
    }
    .message-row.user .message-wrap {
      order: 1;
      flex-direction: row-reverse;
      padding-left: 24px;
      margin-right: -16px;
      gap: 8px;
      max-width: 100%;
    }
    .message.claude,
    .message.codex,
    .message.gemini,
    .message.copilot {
      background: rgba(0, 0, 0, 0.68);
      border-color: rgba(255, 255, 255, 0.12);
      box-shadow: 0 10px 24px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255, 255, 255, 0.12);
    }
    .message-row.claude,
    .message-row.codex,
    .message-row.gemini,
    .message-row.copilot {
      gap: 8px;
    }
    .message-row.claude .avatar,
    .message-row.codex .avatar,
    .message-row.gemini .avatar,
    .message-row.copilot .avatar {
      display: grid;
      width: 24px;
      height: 24px;
      flex: 0 0 24px;
      align-self: flex-start;
      border: none;
      background: transparent;
      box-shadow: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      margin-top: 1px;
    }
    .message-row.claude .avatar img,
    .message-row.codex .avatar img,
    .message-row.gemini .avatar img,
    .message-row.copilot .avatar img {
      width: 22px;
      height: 22px;
    }
    .message-row.claude .message-wrap,
    .message-row.codex .message-wrap,
    .message-row.gemini .message-wrap,
    .message-row.copilot .message-wrap {
      max-width: 100%;
    }
    .message-row.claude .message,
    .message-row.codex .message,
    .message-row.gemini .message,
    .message-row.copilot .message {
      width: 100%;
      padding: 0 0 10px;
      border: none;
      border-radius: 0;
      background: transparent;
      box-shadow: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
    }
    .message-row.claude .meta,
    .message-row.codex .meta,
    .message-row.gemini .meta,
    .message-row.copilot .meta {
      margin-bottom: 4px;
    }
    .message.system {
      background: rgba(255,255,255,0.03);
      border-color: rgba(106, 112, 120, 0.1);
    }
    .message-row.system .message,
    .message-row.system .message::after {
      background: rgba(255,255,255,0.03);
    }
    .sysmsg-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      padding: 4px 0;
      color: var(--chrome-muted);
      font-size: 12px;
      letter-spacing: 0.02em;
    }
    .sysmsg-text {
      display: block;
      min-width: 0;
    }
    .sysmsg-row::before, .sysmsg-row::after {
      content: "";
      flex: 1;
      height: 1px;
      background: rgba(255,255,255,0.15);
    }
    .message-thinking-row {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 20px 6px 54px;
      color: var(--chrome-muted);
      font-size: 16px;
      line-height: 1.45;
      cursor: pointer;
    }
    .thinking-expand-btn {
      background: none;
      border: none;
      padding: 2px;
      margin: 0;
      cursor: pointer;
      color: inherit;
      opacity: 0.55;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: transform 220ms ease, opacity 150ms ease;
    }
    .thinking-expand-btn svg {
      display: block;
      width: 16px;
      height: 16px;
    }
    .message-thinking-row.pane-open .thinking-expand-btn {
      transform: rotate(90deg);
      opacity: 0.85;
    }
    .message-thinking-pane {
      margin: 2px 20px 10px 54px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 18px;
      background: rgb(20, 20, 19);
      backdrop-filter: blur(16px) saturate(140%);
      -webkit-backdrop-filter: blur(16px) saturate(140%);
      box-shadow: none;
      animation: paneReveal 220ms cubic-bezier(0.22, 1, 0.36, 1) forwards;
      max-height: 320px;
      overflow: auto;
    }
    .message-thinking-pane-body {
      padding: 11px 12px;
      font-family: "SF Mono", "Cascadia Mono", "Menlo", "Monaco", "anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", monospace, sans-serif;
      font-size: 10px;
      font-weight: 580;
      font-synthesis-weight: none;
      font-variation-settings: "wght" 580;
      line-height: 1.2;
      color: rgb(161, 168, 179);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: normal;
      font-kerning: none;
    }
    .message-thinking-icons {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }
    .message-thinking-icon-wrap {
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .message-thinking-glow {
      position: absolute;
      inset: 0;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(250,249,245,0.65) 0%, rgba(250,249,245,0) 70%);
      pointer-events: none;
      animation: thinking-glow-follow 1s ease-in-out infinite;
    }
    .message-thinking-glow--claude  { animation-delay: 0s; }
    .message-thinking-glow--codex   { animation-delay: -0.25s; }
    .message-thinking-glow--gemini  { animation-delay: -0.5s; }
    .message-thinking-glow--copilot { animation-delay: -0.75s; }
    @keyframes thinking-glow-follow {
      0%   { transform: scale(0.5); opacity: 0; }
      50%  { transform: scale(1.4); opacity: 0.12; }
      100% { transform: scale(0.5); opacity: 0; }
    }
    .message-thinking-icon {
      width: 1.55em;
      height: 1.55em;
      object-fit: contain;
      position: relative;
      animation: thinking-icon-heartbeat 1s ease-in-out infinite;
    }
    .message-thinking-icon--claude  { animation-delay: 0s; }
    .message-thinking-icon--codex   { animation-delay: -0.25s; }
    .message-thinking-icon--gemini  { animation-delay: -0.5s; }
    .message-thinking-icon--copilot { animation-delay: -0.75s; }
    @keyframes thinking-icon-heartbeat {
      0%   { transform: translateY(0);    filter: brightness(0) invert(0.61); }
      50%  { transform: translateY(-1px); filter: brightness(0) invert(0.75); }
      100% { transform: translateY(0);    filter: brightness(0) invert(0.61); }
    }
    .message-thinking-label {
      display: inline-flex;
      align-items: baseline;
      white-space: nowrap;
      font-size: 1em;
    }
    .thinking-char {
      color: rgba(250, 249, 245, 0.42);
      animation: thinking-char-pulse 1.5s linear infinite;
      animation-delay: calc(var(--char-i) * 0.18s);
    }
    @keyframes thinking-char-pulse {
      0%   { color: rgba(250, 249, 245, 0.62); }
      10%  { color: rgba(250, 249, 245, 0.82); }
      22%  { color: rgba(250, 249, 245, 0.62); }
      34%  { color: rgba(250, 249, 245, 0.42); }
      88%  { color: rgba(250, 249, 245, 0.42); }
      100% { color: rgba(250, 249, 245, 0.62); }
    }
    @media (prefers-reduced-motion: reduce) {
      .message-thinking-icon { animation: none; filter: brightness(0) invert(0.75); }
      .message-thinking-glow { animation: none; display: none; }
      .thinking-char { animation: none; color: rgba(250, 249, 245, 0.6); }
    }
    .meta {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }
    .message-row.user .meta {
      justify-content: flex-end;
    }
    .sender {
      padding: 2px 0;
      color: var(--muted) !important;
      font-weight: 700;
      text-transform: capitalize;
      background: transparent;
      border: none;
    }
    .arrow { color: rgb(156, 154, 147) !important; }
    .targets { color: rgb(156, 154, 147) !important; }
    .reply-jump-inline {
      all: unset;
      display: inline-flex;
      align-items: center;
      cursor: pointer;
      color: rgb(156, 154, 147) !important;
      opacity: 1;
      border-radius: 6px;
      -webkit-tap-highlight-color: transparent;
      transition: all 120ms ease;
    }
    .has-hover .reply-jump-inline:hover {
      color: var(--text) !important;
      opacity: 1;
      text-shadow: 0 0 8px rgba(255,255,255,0.15);
    }
    @media (max-width: 430px) {
      .message-thinking-row {
        padding: 8px 14px 6px 20px;
      }
      .message-thinking-pane {
        margin: 2px 2px 10px 4px;
        border: none;
        border-radius: 18px;
        background: rgb(20, 20, 19);
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
      }
      .message-thinking-pane {
        max-height: min(240px, 45vh);
      }
      .message-thinking-pane-body {
        padding: 6px 8px;
        font-size: 7px;
        line-height: 1.1;
        color: rgba(214, 221, 232, 0.9);
        word-break: break-all;
      }
    }
    @media (min-width: 701px) {
      #fileDropdown { border-radius: 16px 16px 0 0; z-index: 15; }
      .message-thinking-row {
        gap: 14px;
        padding: 8px 20px 6px 20px;
        font-size: 15px;
      }
      .message-thinking-icons {
        margin-left: -4px;
      }
      .message-thinking-pane {
        align-self: center;
        width: 100%;
        max-width: calc(100vw - 20px);
        margin: 2px auto 10px;
        background: rgb(20, 20, 19);
        min-height: 300px;
        max-height: min(560px, 58vh);
      }
    }
    .reply-jump-inline:active {
      background: rgba(255, 255, 255, 0.08);
    }
    @keyframes inline-flash {
      0% { color: #fff !important; text-shadow: 0 0 12px rgba(255,255,255,0.8); }
      100% { color: rgb(156, 154, 147) !important; text-shadow: none; }
    }
    .reply-jump-inline.click-flash {
      animation: inline-flash 250ms ease-out;
    }
    .reply-jump-inline .target-name {
      color: inherit !important;
      font-weight: normal;
    }
    .target-name {
      font-weight: normal;
      text-transform: capitalize;
      color: rgb(156, 154, 147) !important;
    }
    .message-meta-below .meta-agent .sender-label,
    .message-meta-below .meta-agent .target-name {
      color: inherit !important;
    }
    .message:not(.user) .message-meta-below .meta-agent,
    .message:not(.user) .message-meta-below .meta-agent-sep,
    .message:not(.user) .message-meta-below .reply-jump-inline {
      color: var(--chrome-muted) !important;
    }
    .message:not(.user) .message-meta-below .meta-agent-icon {
      background-color: var(--chrome-muted);
    }
    @media (max-width: 430px) {
      .message-meta-below .meta-agent-icon {
        display: none;
      }
    }
    time { opacity: 1; color: var(--muted) !important; }
    @media (max-width: 359px) {
      html { width: 100vw; max-width: 100vw; height: 100%; overflow-x: hidden; overflow-y: hidden; background: var(--bg); }
      body { width: 100vw; max-width: 100vw; height: 100%; overflow-x: hidden; overflow-y: hidden; align-items: stretch; min-height: unset; background: var(--bg); }
      .shell {
        width: 100%;
        max-width: 100%;
        height: 100svh;
        margin: 0;
        border-radius: 0;
        border: none;
        box-shadow: none;
        background: var(--bg);
      }
      header {
        padding: max(10px, calc(env(safe-area-inset-top) + 6px)) 10px 10px;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
        flex-wrap: wrap;
        border: none;
        border-radius: 0;
        box-shadow: none;
      }
      main {
        padding: 90px 8px 150px;
      }
      .filter-chip .filter-icon {
        width: 16px;
        height: 16px;
      }
      .filter-chip .filter-label {
        display: none;
      }
      .filter-chip[data-agent="all"] .filter-label {
        display: inline;
      }
      .filter-chip[data-agent="user"] .filter-label {
        display: inline;
      }
      .filter-chip[data-agent="all"] .filter-icon {
        display: none;
      }
      .eyebrow { display: none; }
      .header-main {
        width: 100%; display: flex; flex-direction: column; gap: 6px; border-radius: 20px; padding: 12px;
        align-items: stretch;
        background: transparent;
        border: none;
        box-shadow: none;
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
      }
      .title-row { display: flex; justify-content: flex-start; align-items: center; width: 100%; gap: 8px; }
      h1 { font-size: 22px; line-height: 1.2; margin-bottom: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .sub { display: none; }
      .pill { font-size: 10px; padding: 3px 7px; white-space: nowrap; }
      #source, #mode, #state, #filter, .search-input, .search-count, .agent-filter-chips { display: none; }
      .sub #count { display: none; }
      .sub #autoModeBtn,
      .sub #caffeinateBtn,
      .sub #soundBtn,
      .sub #ttsBtn,
      .sub #killBtn {
        display: none;
      }
      .header-plus-menu {
        position: relative;
        display: block;
        width: 48px;
        height: 48px;
        z-index: 10010;
      }
      .header-plus-menu::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 176px;
        height: 256px;
        border-radius: 20px;
        border: 1px solid rgba(255,255,255,0.16);
        background: rgba(0, 0, 0, 0.88);
        backdrop-filter: blur(12px) saturate(110%);
        -webkit-backdrop-filter: blur(12px) saturate(110%);
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,0.08),
          0 12px 32px rgba(0,0,0,0.45);
        opacity: 0;
        transform: scale(0.25, 0.171875);
        transform-origin: 24px 24px;
        transition:
          opacity 160ms ease,
          transform 250ms cubic-bezier(0.16, 1, 0.3, 1),
          box-shadow 200ms ease,
          background 200ms ease;
        pointer-events: none;
      }
      .header-plus-menu[open]::before {
        opacity: 1;
        transform: scale(1);
      }
      @keyframes headerPopSmall {
        0% { transform: scale(1); background: rgba(20, 20, 19, 0.48); }
        40% { transform: scale(1.25); background: rgba(24, 24, 23, 0.85); border-color: rgba(255, 255, 255, 0.25); }
        100% { transform: scale(1); background: rgba(20, 20, 19, 0.48); border-color: rgba(255, 255, 255, 0.18); }
      }
      .header-plus-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 48px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.18);
        background: rgba(20, 20, 19, 0.48);
        backdrop-filter: blur(20px) saturate(160%);
        -webkit-backdrop-filter: blur(20px) saturate(160%);
        color: rgba(255, 255, 255, 0.95);
        box-shadow: none !important;
        list-style: none;
        cursor: pointer;
        padding: 0;
        text-indent: 0;
        position: relative;
        z-index: 2;
        transition: transform 200ms ease, background 200ms ease;
        -webkit-tap-highlight-color: transparent;
        outline: none !important;
      }
      .header-plus-toggle.animating {
        animation: headerPopSmall 500ms cubic-bezier(0.25, 0.1, 0.25, 1) forwards;
        z-index: 10011;
      }
      .header-plus-toggle:focus {
        outline: none !important;
      }
      .header-plus-toggle:active {
        outline: none !important;
        background: rgba(24, 24, 23, 0.85) !important;
        transform: scale(1.15);
        transition: transform 100ms ease;
      }
      .header-plus-toggle::-webkit-details-marker {
        display: none;
      }
      .header-plus-toggle svg {
        width: 22px;
        height: 22px;
        stroke: currentColor;
      }
      .header-plus-menu[open] .header-plus-toggle {
        transform: none !important;
        background: rgba(20, 20, 19, 0.48) !important;
        border-color: rgba(255, 255, 255, 0.18) !important;
        color: rgba(255, 255, 255, 0.95) !important;
        box-shadow: none !important;
      }
      .header-plus-menu:not([open]) .header-plus-toggle:active {
        transform: scale(1.15) !important;
        background: rgba(24, 24, 23, 0.85) !important;
        border-color: rgba(255, 255, 255, 0.25) !important;
        box-shadow: none !important;
      }
      .header-plus-toggle::-webkit-details-marker {
        display: none;
      }
      .header-plus-toggle svg {
        width: 22px;
        height: 22px;
        stroke: currentColor;
      }
      .header-plus-menu[open] .header-plus-toggle {
        transform: none !important;
        background: rgba(20, 20, 19, 0.48) !important;
        border-color: rgba(255, 255, 255, 0.18) !important;
        color: rgba(255, 255, 255, 0.95) !important;
        box-shadow: none !important;
      }
      .header-plus-menu:not([open]) .header-plus-toggle:active {
        transform: none !important;
        background: rgba(255, 255, 255, 0.12) !important;
        border-color: rgba(255, 255, 255, 0.25) !important;
        box-shadow: none !important;
      }
      .header-plus-panel {
        display: flex;
        position: absolute;
        left: 0;
        top: 0;
        min-width: 176px;
        width: 176px;
        max-width: calc(100vw - 24px);
        padding: 8px;
        flex-direction: column;
        gap: 2px;
        z-index: 30;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(38, 38, 36, 0.72);
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
        box-shadow: none;
        opacity: 0;
        visibility: hidden;
        transform: translateY(-12px) scale(0.97);
        transform-origin: top left;
        pointer-events: none;
        transition:
          opacity 200ms ease-in,
          transform 200ms ease-in,
          visibility 0s linear 200ms;
      }
      .header-plus-menu[open] .header-plus-panel {
        opacity: 1;
        visibility: visible;
        transform: translateY(0) scale(1);
        pointer-events: auto;
        transition:
          opacity 250ms cubic-bezier(0.16, 1, 0.3, 1),
          transform 250ms cubic-bezier(0.16, 1, 0.3, 1),
          visibility 0s;
      }
      .header-plus-title {
        display: block;
        padding: 4px 12px 10px;
        font: 400 11px/1.4 "SF Pro Text","Segoe UI",sans-serif;
        color: var(--chrome-muted);
        letter-spacing: 0.02em;
      }
      .title-row h1 {
        display: none;
      }
      .header-plus-panel .quick-action {
        all: unset;
        box-sizing: border-box;
        width: 100%;
        justify-content: flex-start;
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
        font-size: 14px;
        font-weight: 700;
        border-radius: 0;
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        color: rgba(182, 188, 198, 0.9);
        position: relative;
        outline: none;
      }
      .header-plus-panel .quick-action + .quick-action {
        background-image: linear-gradient(
          to right,
          rgba(255,255,255,0.08),
          rgba(255,255,255,0.08)
        ) !important;
        background-repeat: no-repeat !important;
        background-size: calc(100% - 24px) 1px !important;
        background-position: 12px 0 !important;
      }
      .has-hover .header-plus-panel .quick-action:hover:not(:disabled),
      .header-plus-panel .quick-action:active {
        background-color: transparent !important;
        border-color: transparent !important;
        box-shadow: none !important;
        transform: none !important;
      }
      .header-plus-panel .quick-action.toggle-flash {
        color: #f8fbff;
        transform: none;
        text-shadow: 0 0 10px rgba(255,255,255,0.14);
      }
      .header-plus-panel .quick-action.toggle-flash::before {
        content: "";
        position: absolute;
        inset: 2px 4px;
        border-radius: 10px;
        background: rgba(255,255,255,0.05);
        box-shadow: 0 0 12px rgba(255,255,255,0.05);
        pointer-events: none;
      }
      .header-plus-panel .quick-action.toggle-flash::after {
        transform: scale(1.35);
        box-shadow: 0 0 10px rgba(255,255,255,0.18);
      }
      .title-row .header-plus-menu {
        order: -1;
        margin: -10px 0 0 -6px;
      }
      .trace-tooltip {
        padding: 6px 8px;
        font-size: 7px;
        line-height: 1.1;
        border-radius: 18px;
        border: none;
        background: rgb(20, 20, 19);
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
        box-shadow: none;
        max-height: min(240px, 45vh);
        color: rgba(214, 221, 232, 0.9);
        overflow-y: auto;
        word-break: break-all;
        white-space: pre-wrap;
      }
      .trace-tooltip::before {
        content: "";
        position: absolute;
        bottom: 100%;
        left: var(--tail-x, 50%);
        transform: translateX(-50%);
        border: 8px solid transparent;
        border-bottom-color: transparent;
        pointer-events: none;
      }
      .trace-tooltip::after {
        content: "";
        position: absolute;
        bottom: 100%;
        left: var(--tail-x, 50%);
        transform: translateX(-50%);
        border: 7px solid transparent;
        border-bottom-color: rgba(0, 0, 0, 0.95);
        margin-bottom: -1px;
        pointer-events: none;
      }
      .filter-chip {
        flex: 0 0 auto;
        scroll-snap-align: start;
      }
      .composer {
        grid-template-columns: 1fr;
        gap: 1.5px;
        margin: 0;
        width: 100%;
        padding: 14px 12px 0;
        padding-bottom: max(6px, env(safe-area-inset-bottom, 0px));
        border: none;
        border-radius: 0;
        background: transparent;
        box-shadow: none;
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
        overflow: visible;
      }
      .target-picker,
      .composer-main-shell,
      .composer-stack,
      .quick-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .composer-main-shell {
        display: contents;
      }
      .target-picker {
        order: 1;
      }
      .composer-stack {
        order: 3;
        display: flex;
        align-items: flex-start;
        gap: 4px;
        padding: 0;
        background: transparent;
        border: none;
        border-radius: 0;
        box-shadow: none;
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
      }
      .target-picker {
        justify-content: flex-start;
        gap: 10px;
        margin-bottom: 6px;
      }
      .quick-actions {
        display: none;
      }
      .quick-more {
        position: relative;
        display: block;
        margin-left: 0;
      }
      .quick-more > summary {
        display: inline-flex;
        list-style: none;
      }
      .quick-more > summary::-webkit-details-marker {
        display: none;
      }
      .quick-more-menu {
        display: none;
        position: absolute;
        right: 0;
        bottom: calc(100% + 8px);
        min-width: 124px;
        padding: 6px;
        border: 1px solid rgba(255,255,255,0.14);
        border-radius: 16px;
        background: rgba(0, 0, 0, 0.92);
        box-shadow: 0 14px 28px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.08);
        backdrop-filter: blur(12px) saturate(120%);
        -webkit-backdrop-filter: blur(12px) saturate(120%);
        flex-direction: column;
        gap: 4px;
        z-index: 30;
      }
      .quick-more[open] .quick-more-menu {
        display: flex;
      }
      .quick-more-menu .quick-action {
        width: 100%;
        justify-content: flex-start;
        margin-left: 0;
      }
      .quick-more-toggle {
        padding-inline: 12px;
      }
      .composer-shell {
        position: relative;
        flex: 1 1 auto;
        margin-bottom: 0;
        min-width: 0;
      }
      .composer-stack.has-reply .composer-plus-menu {
        margin-top: 48px;
      }
      .composer-stack.has-reply .composer-plus-menu::before,
      .composer-stack.has-reply .composer-plus-panel {
        bottom: calc(100% + 110px);
      }
      .composer-shell.has-reply {
        margin-top: 48px;
      }
      .composer-field {
        display: flex;
        align-items: flex-start; /* Changed from center */
        gap: 4px;
        min-height: 46px;
        box-sizing: border-box;
        border-radius: 24px;
        background: transparent;
        border: none;
        overflow: visible;
        box-shadow: none;
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
        transition: border-color 140ms ease, background-color 140ms ease;
      }
      body:not(.keyboard-locked) .composer-field:not(:focus-within) {
        background: transparent;
        border-color: transparent;
        box-shadow: none;
        backdrop-filter: none;
        -webkit-backdrop-filter: none;
      }
      .target-chip:not(.active)::before,
      .target-chip:not(.active):active::before,
      .target-chip:not(.active):focus::before,
      .target-chip:not(.active):focus-visible::before {
        content: none !important;
        background: transparent;
        border-color: transparent;
        box-shadow: none;
      }
      .target-chip.active::before {
        background: rgb(20, 20, 19) !important;
        border-color: transparent !important;
        box-shadow: none !important;
      }
      .composer-field:focus-within {
        background: transparent;
        border-color: transparent;
      }
      .composer-plus-menu {
        position: relative;
        display: block;
        flex: 0 0 auto;
        width: 38px;
        height: 38px;
        z-index: 10010;
        margin: 0 0 4px 12px;
      }
      .composer-plus-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        height: 38px;
        padding: 0;
        border: none !important;
        background: transparent !important;
        color: rgb(156, 154, 147);
        box-shadow: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        border-radius: 10px;
        transition: background 150ms ease, color 150ms ease;
        -webkit-tap-highlight-color: transparent;
        outline: none !important;
      }
      .composer-plus-toggle svg {
        width: 20px;
        height: 20px;
      }
      .composer-plus-panel {
        backdrop-filter: blur(24px) saturate(160%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
      }
      .composer-plus-menu[open] .composer-plus-toggle {
        background: rgb(20, 20, 19) !important;
        color: rgb(235, 235, 230);
        transform: none;
      }
      .composer-plus-menu:not([open]) .composer-plus-toggle:active {
        background: rgb(20, 20, 19) !important;
        color: rgb(235, 235, 230);
        transform: none;
      }
      .composer-plus-panel {
        display: flex;
        position: absolute;
        left: 0;
        bottom: calc(100% + 62px);
        min-width: 160px;
        width: 160px;
        max-width: calc(100vw - 24px);
        padding: 8px;
        flex-direction: column;
        gap: 2px;
        z-index: 30;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(38, 38, 36, 0.72);
        backdrop-filter: blur(24px) saturate(160%);
        -webkit-backdrop-filter: blur(24px) saturate(160%);
        box-shadow: none;
        opacity: 0;
        visibility: hidden;
        transform: translateY(12px) scale(0.97);
        transform-origin: bottom left;
        pointer-events: none;
        transition:
          opacity 200ms ease-in,
          transform 200ms ease-in,
          visibility 0s linear 200ms;
      }
      .composer-plus-menu[open] .composer-plus-panel,
      .composer-plus-menu.closing .composer-plus-panel {
        opacity: 1;
        visibility: visible;
        transform: translateY(0) scale(1);
        pointer-events: auto;
        transition:
          opacity 250ms cubic-bezier(0.16, 1, 0.3, 1),
          transform 250ms cubic-bezier(0.16, 1, 0.3, 1),
          visibility 0s;
      }
      .composer-plus-menu.closing .composer-plus-panel {
        opacity: 0;
        transform: translateY(12px) scale(0.97);
        pointer-events: none;
        transition:
          opacity 150ms ease-in,
          transform 150ms ease-in;
      }
      .composer-plus-panel .quick-action {
        all: unset;
        box-sizing: border-box;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 8px;
        padding: 10px 12px;
        font-family: "anthropicSans", sans-serif;
        font-style: normal;
        font-size: 14px;
        line-height: 20px;
        font-weight: 400;
        color: rgb(250, 249, 245);
        position: relative;
        cursor: pointer;
        transition: color 150ms ease;
      }
      .has-hover .composer-plus-panel .quick-action:hover {
        background: transparent !important;
        color: #fff;
      }
      .composer-plus-panel .quick-action[data-forward-action="interrupt"] {
        color: rgba(245, 201, 96, 0.95);
      }
      .composer-plus-panel .quick-action[data-forward-action="killBtn"] {
        color: rgba(248, 113, 113, 0.96);
      }
      .composer-plus-panel .quick-action.divider-after {
        border-bottom: 1px solid rgba(255,255,255,0.06);
      }
      .has-hover .composer-plus-panel .quick-action:hover:not(:disabled),
      .composer-plus-panel .quick-action:active {
        background: transparent;
        box-shadow: none;
        transform: none;
      }
      .composer-plus-panel .quick-action.toggle-flash {
        color: #f8fbff;
        transform: none;
        text-shadow: 0 0 10px rgba(255,255,255,0.14);
      }
      .composer-plus-panel .quick-action.toggle-flash::before {
        content: "";
        position: absolute;
        inset: 2px 4px;
        border-radius: 10px;
        background: rgba(255,255,255,0.05);
        box-shadow: 0 0 12px rgba(255,255,255,0.05);
        pointer-events: none;
      }
      .copy-btn,
      .copy-btn:hover,
      .copy-btn:active,
      .copy-btn:focus,
      .copy-btn:focus-visible,
      .reply-btn,
      .reply-btn:hover,
      .reply-btn:active,
      .reply-btn:focus,
      .reply-btn:focus-visible {
        background: none !important;
        box-shadow: none !important;
        outline: none !important;
      }
      .reply-banner {
        margin-bottom: 0;
      }
      .target-chip {
        flex: 0 0 auto;
        appearance: none;
        -webkit-appearance: none;
        width: 46px;
        height: 46px;
        justify-content: center;
        padding: 0;
        border-radius: 999px;
        border: none;
        background: transparent;
        background-image: none !important;
        box-shadow: none;
        -webkit-box-shadow: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        color: rgba(255, 255, 255, 0.95);
        font-size: 13px;
        gap: 0;
        transition: none;
        -webkit-tap-highlight-color: transparent;
      }
      .target-chip::before {
        content: "";
        position: absolute;
        inset: 6px;
        border-radius: inherit;
        border: 1px solid rgba(255,255,255,0.18);
        background: rgb(25, 25, 25);
        box-shadow:
          0 0 8px rgba(255,255,255,0.05),
          inset 0 1px 0 rgba(255,255,255,0.06),
          0 6px 18px rgba(0,0,0,0.1);
        backdrop-filter: blur(12px) saturate(110%);
        -webkit-backdrop-filter: blur(12px) saturate(110%);
        transition: none;
        pointer-events: none;
      }
      .target-chip .target-icon {
        position: relative;
        z-index: 1;
        width: 22px;
        height: 22px;
      }
      .target-chip .target-label {
        display: none;
      }
      .target-chip:active:not(.active) {
        transform: none;
      }
      .target-chip:active:not(.active)::before {
        inset: 6px;
        background: rgb(25, 25, 25);
        border-color: rgba(255,255,255,0.18);
        box-shadow:
          0 0 8px rgba(255,255,255,0.05),
          inset 0 1px 0 rgba(255,255,255,0.06),
          0 6px 18px rgba(0,0,0,0.1);
      }
      .target-chip.active {
        background: transparent !important;
        border-color: transparent !important;
        color: rgba(255, 255, 255, 0.95) !important;
        transform: none;
        box-shadow: none;
      }
      .target-chip.active::before {
        inset: 6px;
        background: rgb(25, 25, 25) !important;
        border-color: var(--chip-border-mobile-active) !important;
        box-shadow:
          0 0 8px rgba(255,255,255,0.05),
          inset 0 1px 0 rgba(255,255,255,0.06),
          0 6px 18px rgba(0,0,0,0.1);
      }
      .target-chip.active .target-icon {
        filter: brightness(0) invert(0.61) !important;
      }
      .quick-action {
        min-width: 0;
        padding: 7px 11px;
        font-size: 11px;
        gap: 4px;
      }
      .quick-action .action-label {
        display: none;
      }
      .quick-action .action-emoji {
        display: inline;
      }
      .quick-action .action-mobile {
        display: inline;
      }
      .composer textarea {
        flex: 1 1 auto;
        appearance: none;
        -webkit-appearance: none;
        font-size: 16px !important;
        font-weight: 500;
        min-height: 46px;
        height: 46px;
        max-height: 200px;
        padding: 8px 10px;
        line-height: 1.5;

        border: none;
        border-radius: 0;
        background: transparent;
        background-color: transparent !important;
        background-image: none !important;
        box-shadow: none !important;
        -webkit-box-shadow: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        resize: none;
        overflow-y: hidden;
        outline: none;
        box-sizing: border-box;
      }
      .composer textarea:focus {
        appearance: none;
        -webkit-appearance: none;
        background: transparent;
        background-color: transparent !important;
        background-image: none !important;
        border: none;
        box-shadow: none !important;
        -webkit-box-shadow: none !important;
        outline: none;
      }
      .send-btn {
        display: none;
      }
      .reply-banner {
        position: absolute;
        left: 0;
        right: 0;
        bottom: calc(100% + 4px); /* Closer to input, further from chips */
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
        margin-bottom: 0;
        z-index: 2;
      }
      .reply-banner-arrow {
        display: none;
      }
      .reply-banner-text {
        font-weight: 400;
      }
      #scrollToBottomBtn {
        left: auto;
        right: 16px;
        bottom: 150px;
        transform: none;
      }
      #scrollToBottomBtn:active {
        transform: none;
      }
      .statusline {
        order: 2;
        margin-top: 0;
        padding-bottom: 0;
        min-height: 1.15em;
      }
      .md-body { font: 12px/1.5 "SF Pro Text","Segoe UI",sans-serif; }
      .message-body-row {
        display: block !important;
        width: 100% !important;
      }
      .message.user .message-body-row {
        width: fit-content !important;
        max-width: 100% !important;
        margin-left: auto !important;
      }
      .message.user .message-body-row.has-wide-block,
      .message.user .message-body-row.has-structured-block {
        width: 100% !important;
      }
      .md-body ul,
      .md-body ol,
      .md-body li,
      .md-body li > p,
      .md-body blockquote,
      .md-body blockquote > p {
        display: block !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
        word-break: normal !important;
      }
      .md-body li {
        display: list-item !important;
        padding-left: 0.2em;
      }
      .md-body ul,
      .md-body ol {
        padding-left: 1.2em !important;
        margin: 0.5em 0 !important;
      }
      .table-scroll { width: calc(100% + 24px); margin-left: -12px; margin-right: -12px; }
      .md-body pre { font-size: 11px; padding: 30px 12px 10px; background-position: 10px 10px; width: calc(100% + 24px); margin-left: -12px; margin-right: -12px; border-left: none; border-right: none; border-radius: 0; }
      .md-body code { font-size: 16px; }
      .message-plain { font-size: 12px; }
      .message-row.user {
        padding-left: var(--mobile-user-row-gutter);
        padding-right: var(--mobile-message-inline-pad);
        margin-bottom: 14px;
      }
      .message-row:not(.user) {
        padding-left: var(--mobile-message-inline-pad);
        padding-right: 12px;
      }
      .message-row.user .message-wrap {
        padding-left: 12px;
        margin-right: 0;
      }
      .message-row.claude,
      .message-row.codex,
      .message-row.gemini,
      .message-row.copilot {
        padding-right: 12px;
      }
      .send-btn { display: none !important; }
      main { padding: 180px 8px calc(200px + env(safe-area-inset-bottom, 0px)); }
      .message-wrap { max-width: calc(100% - 42px); }
      .avatar { width: 28px; height: 28px; flex-basis: 28px; font-size: 11px; }
      
      .composer-overlay {
        position: fixed;
        inset: 0;
        background: linear-gradient(180deg, rgba(var(--bg-rgb), 1) 0%, rgba(var(--bg-rgb), 1) 40%, rgba(var(--bg-rgb), 0.42) 100%);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        z-index: 10;
        opacity: 0;
        pointer-events: none;
        transition: opacity 300ms ease;
      }
      body.composing .composer-overlay {
        opacity: 1;
        pointer-events: auto;
      }
      body.composing .composer {
        z-index: 21;
      }
      /* Ensure header is below overlay when composing */
      body.composing header {
        z-index: 5;
      }
    }
    .md-body { font: 15px/1.65 "SF Pro Text","Segoe UI",sans-serif; color: rgb(250, 249, 245); }
    @media (min-width: 360px) {
      .message.user .md-body {
        font-family: "anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif;
        font-size: 16px;
        line-height: 22px;
        font-style: normal;
        font-weight: 400;
        letter-spacing: -0.01em;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        font-synthesis-weight: none;
        font-synthesis-style: none;
        font-optical-sizing: auto;
        font-variation-settings: "wght" 400, "opsz" 16;
      }
      .message.user .md-body h1,
      .message.user .md-body h2,
      .message.user .md-body h3,
      .message.user .md-body h4 {
        font-weight: 600;
        font-variation-settings: "wght" 530, "opsz" 16;
        font-synthesis: weight;
      }
      .message.user .md-body blockquote {
        font-weight: 400;
        font-variation-settings: "wght" 400, "opsz" 16;
      }
      .message.claude .md-body,
      .message.codex .md-body,
      .message.gemini .md-body,
      .message.copilot .md-body {
        font-family: "anthropicSerif", "anthropicSerif Fallback", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, "Times New Roman", Times, serif;
        font-style: normal;
        font-size: 16px;
        line-height: 24px;
        font-weight: 360;
        color: rgb(250, 249, 245);
        font-synthesis-weight: none;
        font-synthesis-style: none;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        font-optical-sizing: auto;
        font-variation-settings: "wght" 360;
      }
      .message.claude .md-body p,
      .message.claude .md-body li,
      .message.claude .md-body h1,
      .message.claude .md-body h2,
      .message.claude .md-body h3,
      .message.claude .md-body h4,
      .message.codex .md-body h1,
      .message.codex .md-body h2,
      .message.codex .md-body h3,
      .message.codex .md-body h4,
      .message.gemini .md-body h1,
      .message.gemini .md-body h2,
      .message.gemini .md-body h3,
      .message.gemini .md-body h4,
      .message.copilot .md-body h1,
      .message.copilot .md-body h2,
      .message.copilot .md-body h3,
      .message.copilot .md-body h4 {
        font-weight: 600;
        font-variation-settings: "wght" 530;
        font-synthesis: weight;
      }
      .message.claude .md-body p,
      .message.claude .md-body li,
      .message.claude .md-body blockquote,
      .message.codex .md-body p,
      .message.codex .md-body li,
      .message.codex .md-body blockquote,
      .message.gemini .md-body p,
      .message.gemini .md-body li,
      .message.gemini .md-body blockquote,
      .message.copilot .md-body p,
      .message.copilot .md-body li,
      .message.copilot .md-body blockquote {
        font-weight: 360;
        font-variation-settings: "wght" 360;
      }
      .message.claude .md-body li,
      .message.codex .md-body li,
      .message.gemini .md-body li,
      .message.copilot .md-body li {
        line-height: 26px;
      }
      html[data-agent-font-mode="gothic"] .message.claude .md-body,
      html[data-agent-font-mode="gothic"] .message.codex .md-body,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body {
        font-family: "anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif;
        font-size: 16px;
        line-height: 22px;
        font-style: normal;
        font-weight: 360;
        letter-spacing: -0.01em;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        font-synthesis-weight: none;
        font-synthesis-style: none;
        font-optical-sizing: auto;
        font-variation-settings: "wght" 360, "opsz" 16;
      }
      html[data-agent-font-mode="gothic"] .message.claude .md-body p,
      html[data-agent-font-mode="gothic"] .message.claude .md-body li,
      html[data-agent-font-mode="gothic"] .message.claude .md-body h1,
      html[data-agent-font-mode="gothic"] .message.claude .md-body h2,
      html[data-agent-font-mode="gothic"] .message.claude .md-body h3,
      html[data-agent-font-mode="gothic"] .message.claude .md-body h4,
      html[data-agent-font-mode="gothic"] .message.claude .md-body blockquote,
      html[data-agent-font-mode="gothic"] .message.codex .md-body p,
      html[data-agent-font-mode="gothic"] .message.codex .md-body li,
      html[data-agent-font-mode="gothic"] .message.codex .md-body h1,
      html[data-agent-font-mode="gothic"] .message.codex .md-body h2,
      html[data-agent-font-mode="gothic"] .message.codex .md-body h3,
      html[data-agent-font-mode="gothic"] .message.codex .md-body h4,
      html[data-agent-font-mode="gothic"] .message.codex .md-body blockquote,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body p,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body li,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body h1,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body h2,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body h3,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body h4,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body blockquote,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body p,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body li,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body h1,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body h2,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body h3,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body h4,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body blockquote {
        font-weight: 360;
        font-variation-settings: "wght" 360, "opsz" 16;
      }
      html[data-agent-font-mode="gothic"] .message.claude .md-body li,
      html[data-agent-font-mode="gothic"] .message.codex .md-body li,
      html[data-agent-font-mode="gothic"] .message.gemini .md-body li,
      html[data-agent-font-mode="gothic"] .message.copilot .md-body li {
        line-height: 22px;
      }
    }
    @media (min-width: 701px) {
      .header-main {
        transform: translateY(-5px);
      }
      .composer-plus-panel {
        left: -15px;
      }
      .file-item {
        font-size: 16px;
        line-height: 24px;
      }
      .target-picker {
        padding-left: 10px;
      }
      .composer-main-shell {
        row-gap: 10px;
        column-gap: 10px;
        padding: 10px 12px 12px;
        border-radius: 24px;
      }
      .composer textarea {
        padding: 11px 52px 11px 16px;
        border-radius: 22px;
      }
    }
    @media (max-width: 430px) {
      .mobile-top-frost,
      .mobile-bottom-frost {
        display: none !important;
      }
      header::before {
        display: block !important;
        content: "" !important;
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        height: auto !important;
        background: linear-gradient(180deg,
          rgba(var(--bg-rgb), 1.00) 0%,
          rgba(var(--bg-rgb), 0.78) 18%,
          rgba(var(--bg-rgb), 0.58) 34%,
          rgba(var(--bg-rgb), 0.38) 50%,
          rgba(var(--bg-rgb), 0.22) 66%,
          rgba(var(--bg-rgb), 0.12) 80%,
          rgba(var(--bg-rgb), 0.06) 92%,
          transparent 100%
        ) !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        mask-image: none !important;
        -webkit-mask-image: none !important;
        z-index: -1;
        pointer-events: none !important;
      }
      header::after {
        display: block !important;
        content: "" !important;
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        height: auto !important;
        background: rgba(var(--bg-rgb), 0.12) !important;
        backdrop-filter: blur(44px) saturate(165%) !important;
        -webkit-backdrop-filter: blur(44px) saturate(165%) !important;
        mask-image: linear-gradient(180deg,
          rgba(0,0,0,1.00) 0%,
          rgba(0,0,0,0.82) 22%,
          rgba(0,0,0,0.64) 40%,
          rgba(0,0,0,0.46) 58%,
          rgba(0,0,0,0.28) 74%,
          rgba(0,0,0,0.14) 86%,
          rgba(0,0,0,0.07) 95%,
          rgba(0,0,0,0.00) 100%
        ) !important;
        -webkit-mask-image: linear-gradient(180deg,
          rgba(0,0,0,1.00) 0%,
          rgba(0,0,0,0.82) 22%,
          rgba(0,0,0,0.64) 40%,
          rgba(0,0,0,0.46) 58%,
          rgba(0,0,0,0.28) 74%,
          rgba(0,0,0,0.14) 86%,
          rgba(0,0,0,0.07) 95%,
          rgba(0,0,0,0.00) 100%
        ) !important;
        z-index: -2;
        pointer-events: none !important;
      }
      .composer::before {
        display: block !important;
        top: auto;
        right: 0;
        bottom: 0;
        left: 0;
        height: calc(68px + env(safe-area-inset-bottom, 0px));
        background: linear-gradient(0deg,
          rgba(var(--bg-rgb), 1) 0,
          rgba(var(--bg-rgb), 1) calc(env(safe-area-inset-bottom, 0px) + 8px),
          rgba(var(--bg-rgb), 0.88) calc(env(safe-area-inset-bottom, 0px) + 26px),
          rgba(var(--bg-rgb), 0.52) calc(env(safe-area-inset-bottom, 0px) + 52px),
          transparent 100%
        ) !important;
        mask-image: none !important;
        -webkit-mask-image: none !important;
      }
      header {
        padding-top: env(safe-area-inset-top, 0px) !important;
        padding-right: calc(env(safe-area-inset-right, 0px) + 10px) !important;
        padding-bottom: 0 !important;
        padding-left: calc(env(safe-area-inset-left, 0px) + 10px) !important;
      }
      .header-main {
        padding: 0 !important;
        border-radius: 0 !important;
      }
      .title-row .header-plus-menu {
        margin: 6px 0 0 !important;
      }
      .right-menu {
        margin-top: 6px !important;
        margin-right: 4px !important;
      }
      .reply-banner-arrow {
        display: none !important;
      }
      .header-plus-panel {
        backdrop-filter: blur(16px) saturate(140%) !important;
        -webkit-backdrop-filter: blur(16px) saturate(140%) !important;
      }
      .composer-plus-panel {
        left: -10px !important;
        min-width: 160px !important;
        width: auto !important;
        max-width: calc(100vw - 24px) !important;
        display: flex !important;
        flex-direction: column !important;
        padding: 8px !important;
        gap: 2px !important;
        border-radius: 10px !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        background: rgb(20, 20, 19) !important;
        box-shadow: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        opacity: 0 !important;
        visibility: hidden !important;
        z-index: 10011 !important;
        transform: translateY(4px) scale(0.98) !important;
        transform-origin: bottom left !important;
        pointer-events: none !important;
        transition: opacity 140ms ease, transform 180ms ease, visibility 0s linear 180ms !important;
      }
      .composer-plus-menu[open] .composer-plus-panel {
        opacity: 1 !important;
        visibility: visible !important;
        transform: translateY(0) scale(1) !important;
        pointer-events: auto !important;
        transition: opacity 140ms ease, transform 180ms ease, visibility 0s !important;
      }
      .composer-plus-panel .quick-action {
        all: unset !important;
        box-sizing: border-box !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        width: 100% !important;
        padding: 9px 12px !important;
        font-family: "anthropicSans", sans-serif !important;
        font-style: normal !important;
        font-size: 14px !important;
        font-weight: 400 !important;
        line-height: 20px !important;
        color: rgb(250, 249, 245) !important;
        position: relative !important;
        cursor: pointer !important;
        border-radius: 10px !important;
        background: transparent !important;
        transition: color 150ms ease !important;
      }
      .has-hover .composer-plus-panel .quick-action:hover {
        color: #fff !important;
      }
      .composer-plus-panel .quick-action[data-forward-action="interrupt"] {
        color: rgba(245, 201, 96, 0.95) !important;
      }
      .composer-plus-panel .quick-action[data-forward-action="killBtn"] {
        color: rgb(250, 249, 245) !important;
      }
      .composer-plus-panel .quick-action.divider-after {
        border-bottom: none !important;
        background-image: linear-gradient(to right, rgba(255,255,255,0.08), rgba(255,255,255,0.08)) !important;
        background-repeat: no-repeat !important;
        background-size: calc(100% - 24px) 1px !important;
        background-position: 12px 100% !important;
      }
      .has-hover .composer-plus-panel .quick-action:hover:not(:disabled),
      .composer-plus-panel .quick-action:active {
        background: transparent !important;
        box-shadow: none !important;
        transform: none !important;
      }
      .statusline {
        position: fixed !important;
        right: 12px !important;
        bottom: -4px !important;
        order: initial !important;
        margin-top: 0 !important;
        padding: 4px 8px !important;
        min-height: 0 !important;
        font-size: 11px !important;
        color: var(--chrome-muted) !important;
        text-align: right !important;
        z-index: 1000 !important;
        pointer-events: none !important;
        background: transparent !important;
      }
      .composer-main-shell,
      .composer-field {
        margin-right: 6px !important;
        margin-left: 6px !important;
      }
      .composer {
        padding-top: 0 !important;
        padding-right: env(safe-area-inset-right, 0px) !important;
        padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 22px) !important;
        padding-left: env(safe-area-inset-left, 0px) !important;
      }
      .composer-plus-menu {
        z-index: 10010 !important;
      }
      .sysmsg-row[data-kind="git-commit"] .sysmsg-text {
        flex: 1 1 auto;
        width: 0;
        max-width: calc(100vw - 64px);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .sysmsg-row[data-kind="git-commit"]::before,
      .sysmsg-row[data-kind="git-commit"]::after {
        flex: 0 0 10px;
      }
    }
    @media (max-width: 430px) {
      html,
      body {
        min-height: 100%;
        height: auto !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
      }
      body {
        display: block !important;
        padding: 0 !important;
      }
      .shell {
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        min-height: 0 !important;
        height: auto !important;
        overflow: visible !important;
        background: transparent !important;
      }
      header {
        grid-area: auto !important;
        position: static !important;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        min-width: 0 !important;
        overflow: visible !important;
        pointer-events: none !important;
        z-index: auto !important;
      }
      header::before,
      header::after {
        display: none !important;
      }
      .header-main {
        display: contents !important;
      }
      .header-left,
      .header-right,
      .title-row {
        display: contents !important;
      }
      .eyebrow,
      #title,
      .sub {
        display: none !important;
      }
      /* Hide TTS on mobile */
      #ttsBtn, [data-forward-action="ttsBtn"] {
        display: none !important;
      }
      .title-row .header-plus-menu {
        position: fixed !important;        top: 6px !important;
        left: 10px !important;
        margin: 0 !important;
        z-index: 35 !important;
        pointer-events: auto !important;
      }
      .right-menu {
        position: fixed !important;
        top: 6px !important;
        right: 10px !important;
        margin: 0 !important;
        z-index: 35 !important;
        pointer-events: auto !important;
      }
      #fileDropdown { border-radius: 16px 16px 0 0; z-index: 20; }
      #attachedFilesMenu {
        position: fixed !important;
        top: 6px !important;
        right: 66px !important;
        margin: 0 !important;
        z-index: 35 !important;
        pointer-events: auto !important;
      }
      #attachedFilesMenu .header-plus-panel {
        left: auto !important;
        right: 0 !important;
        transform-origin: top right !important;
        min-width: 160px !important;
        max-width: 200px !important;
      }
      main {
        grid-area: auto !important;
        min-height: 0 !important;
        padding: 0 8px calc(var(--mobile-composer-reserve, 0px) + var(--mobile-latest-anchor-gap, 220px)) !important;
        overflow: visible !important;
        overscroll-behavior: auto !important;
      }
      .message-row.user {
        padding-right: 12px !important;
      }
      .message-row.user .message-wrap {
        box-sizing: border-box !important;
        padding-right: 8px !important;
      }
      .composer {
        position: static !important;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        pointer-events: none !important;
        z-index: auto !important;
      }
      .composer::before {
        display: none !important;
      }
      .composer-main-shell {
        position: fixed !important;
        right: 6px !important;
        bottom: calc(6px + var(--mobile-keyboard-offset, 0px)) !important;
        left: 6px !important;
        z-index: 25 !important;
        pointer-events: auto !important;
        will-change: bottom !important;
        transition:
          bottom var(--mobile-keyboard-transition-duration, 260ms) cubic-bezier(0.22, 1, 0.36, 1),
          border-color 140ms ease,
          background 140ms ease,
          box-shadow 180ms ease !important;
      }
      .statusline {
        position: fixed !important;
        right: 12px !important;
        bottom: -4px !important;
        display: block !important;
        width: auto !important;
        margin: 0 !important;
        padding: 4px 8px !important;
        text-align: right !important;
        pointer-events: none !important;
      }
      #scrollToBottomBtn {
        position: fixed !important;
        right: 16px !important;
        bottom: 116px !important;
        left: auto !important;
        transform: none !important;
      }
      #scrollToBottomBtn:active {
        transform: none !important;
      }
    }
    .md-body > *:first-child { margin-top: 0; }
    .md-body > *:last-child { margin-bottom: 0; }
    .md-body,
    .md-body p,
    .md-body li,
    .md-body li p,
    .md-body blockquote,
    .md-body blockquote p {
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: normal;
    }
    .md-body p { margin: 0 0 0.6em; }
    .md-body h1, .md-body h2, .md-body h3, .md-body h4 { margin: 0.8em 0 0.3em; font-weight: 600; font-variation-settings: "wght" 530; font-synthesis: weight; line-height: 1.2; }
    .md-body h1 { font-size: 22px; }
    .md-body h2 { font-size: 18px; }
    .md-body h3 { font-size: 1.05em; }
    .md-body ul, .md-body ol { margin: 0.4em 0 0.6em; padding-left: 1.5em; }
    .md-body li { margin: 0.15em 0; }
    .md-body li p { margin: 0; }
    .md-body code {
      font-family: "JetBrains Mono", monospace !important;
      font-style: normal;
      font-size: 16px;
      font-weight: 360;
      font-synthesis-weight: none;
      font-stretch: normal;
      font-variation-settings: "wght" 360;
      color: rgb(254, 129, 129);
      line-height: 26px;
      background: rgb(46, 46, 43);
      border: 0.5px solid rgb(73, 73, 68);
      border-radius: 4px;
      padding: 3px 5px;
    }
    .katex {
      font-family: KaTeX_Main, Times New Roman, serif;
      font-size: 19px;
      font-weight: 400;
      line-height: 23px;
    }
    .viewport-centered-block {
      position: relative;
      width: min(100%, var(--viewport-centered-width, 100%));
      max-width: calc(100vw - (var(--viewport-center-gutter) * 2));
      transform: translateX(var(--viewport-centered-shift, 0px));
      transform-origin: center center;
    }
    .table-scroll {
      display: block;
      width: calc(100vw - 60px) !important;
      max-width: calc(100vw - 60px) !important;
      position: relative;
      left: 50%;
      transform: translateX(calc(-50% + 2px));
      margin-top: 0.5em;
      margin-bottom: 0.5em;
      overflow-x: auto;
      overflow-y: hidden;
      -webkit-overflow-scrolling: touch;
    }
    @media (max-width: 430px) {
      .table-scroll {
        width: calc(100vw - 34px) !important;
        max-width: calc(100vw - 34px) !important;
        transform: translateX(calc(-50% + 6px));
      }
    }
    .katex-display {
      display: block;
      margin: 1.2em 0;
      width: min(100%, var(--viewport-centered-width, 100%));
      max-width: calc(100vw - (var(--viewport-center-gutter) * 2));
      padding-inline: 0;
      overflow-x: auto;
      overflow-y: hidden;
      scrollbar-width: none;
      -ms-overflow-style: none;
      text-align: left;
      transform: translateX(var(--viewport-centered-shift, 0px));
      -webkit-overflow-scrolling: touch;
    }
    .katex-display::-webkit-scrollbar {
      width: 0;
      height: 0;
      display: none;
    }
    .katex-display > .katex {
      display: table;
      width: max-content;
      max-width: none;
      margin: 0 auto;
    }
    .md-body pre {
      display: block;
      width: calc(100vw - 60px) !important;
      max-width: calc(100vw - 60px) !important;
      position: relative;
      left: 50%;
      transform: translateX(calc(-50% + 2px));
      box-sizing: border-box;
      background: rgb(43, 43, 41);
      border: 0.5px solid rgb(73, 73, 68);
      border-radius: 10px;
      padding: 12px 16px;
      margin: 12px 0;
      overflow-x: hidden;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: normal;
      box-shadow: none;
    }
    .md-body pre code {
      font-family: "jetbrainsMono", "JetBrains Mono", monospace !important;
      font-style: normal;
      font-size: 16px;
      font-weight: 360;
      font-synthesis-weight: none;
      font-variation-settings: "wght" 360;
      line-height: 23px;
      color: rgb(234, 236, 240);
      background: none;
      border: none;
      padding: 0;
      border-radius: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .md-body blockquote { border-left: 3px solid rgba(255,255,255,0.2); margin: 0.5em 0; padding: 0.3em 0.8em; opacity: 0.85; }
    .md-body hr { border: none; border-top: 1px solid var(--line); margin: 0.8em 0; }
    .md-body table { border-collapse: collapse; width: 100%; margin: 0; font-size: 14px; line-height: 24px; }
    .md-body th, .md-body td { border-top: 1.5px solid rgba(255,255,255,0.12); border-bottom: 1.5px solid rgba(255,255,255,0.12); border-left: none; border-right: none; padding: 7.5px 1px !important; text-align: left; font-size: 14px; line-height: 24px; }
    .md-body th { background: transparent; font-weight: 530; border-top: none; border-bottom-color: rgba(255,255,255,0.28); }
    .md-body td { font-weight: 360; }
    .md-body a { color: var(--codex-accent); text-decoration: none; }
    .has-hover .md-body a:hover { text-decoration: underline; }
    .md-body strong { font-weight: 530; }
    .md-body em { font-style: italic; }
    .file-card { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 5px 10px; margin: 4px 0; border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; background: rgb(25, 24, 23); cursor: pointer; color: var(--text); text-align: left; max-width: 100%; font-family: "anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Meiryo", sans-serif; font-style: normal; font-size: 14px; font-weight: 400; line-height: 23px; }
    .has-hover .file-card:hover { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.2); }
    .file-card-icon { font-size: 0.9em; flex-shrink: 0; }
    .file-card-name { font-size: inherit; font-weight: inherit; line-height: inherit; flex-shrink: 0; }
    .file-card-path { order: 3; flex: 0 0 100%; display: block; margin-top: -2px; padding-left: calc(0.9em + 6px); max-width: 100%; color: var(--dim); font-family: inherit; font-size: inherit; font-weight: inherit; line-height: inherit; white-space: normal; overflow: visible; text-overflow: clip; overflow-wrap: anywhere; word-break: normal; }
    .file-card-open { order: 2; margin-left: auto; font-size: inherit; font-weight: inherit; line-height: inherit; color: var(--dim); flex-shrink: 0; }
    @media (min-width: 701px) {
      .file-card {
        gap: 7px;
        padding: 5px 10px;
        margin: 4px 0;
        background: rgba(0,0,0,0.18);
        border-color: rgba(255,255,255,0.10);
        font-size: 17px;
        line-height: 24px;
      }
      .has-hover .file-card:hover {
        background: rgba(255,255,255,0.04);
        border-color: rgba(255,255,255,0.14);
      }
    }
    body.file-modal-open {
      overflow: hidden;
    }
    @keyframes modalFadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes modalFadeOut {
      from { opacity: 1; }
      to { opacity: 0; }
    }
    @keyframes modalScaleIn {
      from {
        opacity: 0;
        transform: translate(var(--file-modal-enter-x, 0px), var(--file-modal-enter-y, 18px)) scale(0.92);
        filter: blur(8px);
      }
      to {
        opacity: 1;
        transform: translate(0, 0) scale(1);
        filter: blur(0);
      }
    }
    @keyframes modalScaleOut {
      from {
        opacity: 1;
        transform: translate(0, 0) scale(1);
        filter: blur(0);
      }
      to {
        opacity: 0;
        transform: translate(calc(var(--file-modal-enter-x, 0px) * 0.72), calc(var(--file-modal-enter-y, 18px) * 0.72)) scale(0.88);
        filter: blur(10px);
      }
    }
    .file-modal {
      position: fixed;
      inset: 0;
      z-index: 10020;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px 28px;
      color-scheme: dark;
    }
    .file-modal.visible, .file-modal.closing {
      display: flex;
    }
    .file-modal.visible .file-modal-backdrop {
      animation: modalFadeIn 300ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
    .file-modal.visible .file-modal-dialog {
      animation: modalScaleIn 400ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    .file-modal.closing .file-modal-backdrop {
      animation: modalFadeOut 260ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
    .file-modal.closing .file-modal-dialog {
      animation: modalScaleOut 300ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
    .file-modal-backdrop {
      position: absolute;
      inset: 0;
      background: rgba(20, 20, 19, 0.18);
      backdrop-filter: blur(10px) saturate(108%);
      -webkit-backdrop-filter: blur(10px) saturate(108%);
    }
    .file-modal-dialog {
      position: relative;
      width: min(1180px, calc(100vw - 56px));
      height: min(860px, calc(100vh - 40px));
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      border-radius: 18px;
      overflow: hidden;
      border: 0.5px solid rgba(255,255,255,0.16);
      background: rgba(20, 20, 19, 0.24);
      backdrop-filter: blur(12px) saturate(110%);
      -webkit-backdrop-filter: blur(12px) saturate(110%);
      box-shadow:
        0 24px 56px rgba(0,0,0,0.34),
        inset 0 1px 0 rgba(255,255,255,0.06);
      will-change: transform, opacity, filter;
      --file-modal-enter-x: 0px;
      --file-modal-enter-y: 18px;
    }
    .file-modal-header {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 12px;
      min-width: 0;
      padding: 12px 14px;
      border-bottom: 0.5px solid rgba(255,255,255,0.05);
      background: rgba(20, 20, 19, 0.18);
    }
    .file-modal-meta {
      display: flex;
      align-items: center;
      gap: 14px;
      flex: 1 1 auto;
      min-width: 0;
    }
    .file-modal-icon {
      width: 32px;
      height: 32px;
      border-radius: 10px;
      display: grid;
      place-items: center;
      background: rgba(255,255,255,0.06);
      font-size: 16px;
      flex-shrink: 0;
    }
    .file-modal-text {
      min-width: 0;
    }
    .file-modal-title {
      font: 700 14px/1.2 "SF Pro Text","Segoe UI",sans-serif;
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .file-modal-path {
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font: 12px/1.35 "SF Mono","Fira Code",monospace;
      white-space: pre-wrap;
      overflow: visible;
      text-overflow: clip;
      overflow-wrap: anywhere;
      word-break: normal;
    }
    .file-modal-close {
      appearance: none;
      width: 34px;
      height: 34px;
      border-radius: 10px;
      border: none;
      background: rgba(255,255,255,0.06);
      color: rgba(255,255,255,0.85);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      flex: 0 0 auto;
      cursor: pointer;
      font: 400 18px/1 sans-serif;
      transition: background 150ms ease, transform 100ms ease;
    }
    .has-hover .file-modal-close:hover {
      background: rgba(255,255,255,0.12);
    }
    .file-modal-close:active {
      transform: scale(0.94);
    }
    .file-modal-body {
      position: relative;
      min-height: 0;
      background: transparent;
    }
    .file-modal-frame {
      width: 100%;
      height: 100%;
      border: 0;
      display: block;
      background: transparent;
    }
    .copy-btn {
      flex-shrink: 0;
      align-self: flex-start;
      margin-top: 2px;
      background: rgba(20, 20, 19, 0); /* Transparent by default */
      border: none;
      padding: 4px;
      cursor: pointer;
      color: rgb(156, 154, 147);
      line-height: 1;
      border-radius: 4px;
      transition: color 150ms ease, background 250ms ease, transform 100ms ease;
      -webkit-tap-highlight-color: transparent;
    }
    .has-hover .copy-btn:hover { color: #e5e5e5; background: rgb(20, 20, 19); }
    .copy-btn.copied { color: #e5e5e5; }
    .reply-btn,
    .reply-target-jump-btn {
      flex-shrink: 0;
      align-self: flex-start;
      margin-top: 4px;
      background: rgba(20, 20, 19, 0); /* Transparent by default */
      border: none;
      padding: 4px;
      cursor: pointer;
      color: rgb(156, 154, 147);
      line-height: 1;
      border-radius: 4px;
      transition: color 150ms ease, background 250ms ease, transform 100ms ease;
    }
    .has-hover .reply-btn:hover,
    .has-hover .reply-target-jump-btn:hover { color: #e5e5e5; background: rgb(20, 20, 19); }
    .reply-btn.active { color: #e5e5e5; }
    .message-actions {
      display: flex;
      flex-direction: column;
      gap: 2px;
      align-items: flex-start;
    }
    @keyframes replyBannerIn {
      from { opacity: 0; transform: translateY(10px) scale(0.98); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .reply-banner {
      display: none;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 12px;
      background: rgb(20, 20, 19);
      border: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      box-shadow: none;
      font-size: 13px;
      color: rgb(156, 154, 147);
      font-family: "anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", sans-serif;
      font-style: normal;
      font-weight: 400;
      letter-spacing: -0.01em;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      font-synthesis-weight: none;
      font-optical-sizing: auto;
      font-variation-settings: "wght" 400, "opsz" 16;
      margin-bottom: 8px;
      transform-origin: bottom center;
      will-change: transform, opacity;
    }
    .reply-banner.visible {
      display: flex;
      animation: replyBannerIn 250ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    .reply-banner-arrow { opacity: 1; font-size: 13px; color: rgb(156, 154, 147); }
    .reply-banner-text { flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-weight: 400; }
    .reply-banner-sender { font-weight: 400; text-transform: capitalize; margin-right: 2px; color: rgb(156, 154, 147); }
    .reply-cancel-btn {
      cursor: pointer; background: none; border: none; color: rgb(156, 154, 147);
      padding: 2px 4px; border-radius: 4px; font-size: 13px; line-height: 1;
      transition: color 120ms ease, transform 100ms ease;
    }
    .has-hover .reply-cancel-btn:hover { color: rgb(156, 154, 147); }
    .thread-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .thread-replies {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding-left: 46px;
      border-left: 2px solid rgba(255,255,255,0.08);
      margin-left: 17px;
    }
    .reply-preview-block {
      display: flex;
      align-items: center;
      gap: 4px;
      width: fit-content;
      max-width: 100%;
      min-width: 0;
      padding: 4px 8px;
      margin-top: 4px;
      margin-bottom: 4px;
      margin-right: auto;
      border-radius: 8px;
      background: rgba(0,0,0,0.22);
      font-size: 12px;
      color: var(--muted);
      font-family: "anthropicSans", "Anthropic Sans", "SF Pro Text", "Segoe UI", sans-serif;
      font-style: normal;
      font-weight: 400;
      letter-spacing: -0.01em;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      font-synthesis-weight: none;
      font-optical-sizing: auto;
      font-variation-settings: "wght" 400, "opsz" 16;
      line-height: 1.4;
      overflow: hidden;
      cursor: pointer;
      transition: background 120ms ease;
    }
    .has-hover .reply-preview-block:hover {
      background: rgba(0,0,0,0.32);
    }
    @keyframes msg-highlight {
      0%   { box-shadow: 0 0 0 2px rgba(255,255,255,0.35); }
      100% { box-shadow: 0 0 0 2px rgba(255,255,255,0); }
    }
    .msg-highlight {
      animation: msg-highlight 1.2s ease-out forwards;
      border-radius: 20px;
    }
    .reply-preview-block .reply-arrow {
      font-size: 16px;
      opacity: 0.85;
      flex-shrink: 0;
    }
    .reply-preview-block .reply-preview-text {
      flex: 1;
      min-width: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .message.user .reply-preview-block {
      width: fit-content;
      margin-left: auto;
      margin-right: 0;
      max-width: 100%;
      min-width: 50%;
    }
    .search-input {
      height: 26px;
      padding: 0 9px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(0,0,0,0.2);
      color: var(--text);
      font: 12px/1 "SF Pro Text","Segoe UI",sans-serif;
      outline: none;
      width: 140px;
      box-shadow: inset 0 1px 3px rgba(0,0,0,0.3);
      transition: border-color 150ms ease, background 150ms ease, width 250ms cubic-bezier(0.4, 0, 0.2, 1), box-shadow 150ms ease;
    }
    .search-input::placeholder { color: var(--muted); }
    .search-input:focus {
      border-color: rgba(255,255,255,0.28);
      background: rgba(255,255,255,0.04);
      box-shadow: 0 0 12px rgba(255,255,255,0.08), inset 0 1px 2px rgba(0,0,0,0.1);
      width: 200px;
    }
    .agent-filter-chips { display: none; gap: 5px; flex-wrap: wrap; }
    .agent-filter-chips::-webkit-scrollbar { display: none; }
    .filter-chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 9px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.04);
      color: var(--muted);
      font: 600 11px/1.2 "SF Pro Text","Segoe UI",sans-serif;
      cursor: pointer;
      text-transform: capitalize;
      transition: all 150ms ease;
    }
    .has-hover .filter-chip:hover:not(.active) {
      background: rgba(255,255,255,0.08);
      color: var(--text);
      border-color: rgba(255,255,255,0.25);
    }
    .filter-chip.active {
      color: #fff;
      background: rgba(255,255,255,0.14);
      border-color: rgba(255,255,255,0.3);
      box-shadow: 0 0 10px rgba(255,255,255,0.08), inset 0 1px 1px rgba(255,255,255,0.1);
    }
    #messages article.message-row.filtered-out { display: none; }
    .search-count {
      font-size: 11px;
      color: var(--muted);
      white-space: nowrap;
      opacity: 0.8;
      align-self: center;
    }
    .search-count:empty { display: none; }
    @media (min-width: 360px) and (max-width: 430px) {
      .file-modal {
        padding: 18px 16px;
      }
      .file-modal-dialog {
        width: calc(100vw - 32px);
        height: calc(100svh - 132px);
        height: calc(100dvh - 132px);
        border-radius: 14px;
      }
      .file-modal-header {
        padding: 10px 11px;
      }
      .file-modal-icon {
        width: 28px;
        height: 28px;
        border-radius: 8px;
        font-size: 14px;
      }
      .file-modal-title {
        font-size: 13px;
      }
      .file-modal-path {
        font-size: 11px;
      }
      .file-modal-close {
        width: 30px;
        height: 30px;
      }
    }
    @media (max-width: 359px) {
      body {
        min-height: 100svh;
        min-height: 100dvh;
      }
      .shell {
        height: 100svh;
        height: 100dvh;
      }
      .file-modal {
        padding: 18px 16px;
      }
      .file-modal-dialog {
        width: calc(100vw - 32px);
        height: calc(100svh - 132px);
        height: calc(100dvh - 132px);
        border-radius: 14px;
      }
      .file-modal-header {
        padding: 10px 11px;
      }
      .file-modal-icon {
        width: 28px;
        height: 28px;
        border-radius: 8px;
        font-size: 14px;
      }
      .file-modal-title {
        font-size: 13px;
      }
      .file-modal-path {
        font-size: 11px;
      }
      .file-modal-close {
        width: 30px;
        height: 30px;
      }
    }
__AGENT_FONT_MODE_INLINE_STYLE__
  </style>
</head>
<body>
  <div id="traceTooltip" class="trace-tooltip"></div>
  <div id="fileDropdown"></div>
  <div class="composer-overlay" id="composerOverlay"></div>
  <div id="fileModal" class="file-modal" hidden>
    <div class="file-modal-backdrop" data-close-file-modal></div>
    <div class="file-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="fileModalTitle">
      <div class="file-modal-header">
        <div class="file-modal-meta">
          <span id="fileModalIcon" class="file-modal-icon">📄</span>
          <div class="file-modal-text">
            <div id="fileModalTitle" class="file-modal-title">Preview</div>
            <code id="fileModalPath" class="file-modal-path"></code>
          </div>
        </div>
        <button type="button" class="file-modal-close" aria-label="Close file preview" data-close-file-modal>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="file-modal-body">
        <iframe id="fileModalFrame" class="file-modal-frame" title="File preview"></iframe>
      </div>
    </div>
  </div>
  <section class="shell">
    <header>
      <div class="header-main">
        <div class="header-left">
          <div class="eyebrow">Multiagent Chat View</div>
          <div class="title-row">
            <details class="header-plus-menu" id="headerPlusMenu">
              <summary class="header-plus-toggle" aria-label="Open header controls">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
              </summary>
              <div class="header-plus-panel">
                <div class="header-plus-title" id="headerPanelTitle">agent-index</div>
                <button type="button" class="quick-action" data-forward-action="autoModeBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4"></path><path d="M12 17v4"></path><path d="m5.6 5.6 2.8 2.8"></path><path d="m15.6 15.6 2.8 2.8"></path><path d="M3 12h4"></path><path d="M17 12h4"></path><path d="m5.6 18.4 2.8-2.8"></path><path d="m15.6 8.4 2.8-2.8"></path><circle cx="12" cy="12" r="2.5"></circle></svg></span><span class="action-label">Auto</span><span class="action-mobile">Auto</span></button>
                <button type="button" class="quick-action" data-forward-action="caffeinateBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"></path><circle cx="12" cy="12" r="2.5"></circle></svg></span><span class="action-label">Awake</span><span class="action-mobile">Awake</span></button>
                <button type="button" class="quick-action" data-forward-action="soundBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 9 9 9 14 5 14 19 9 15 5 15 5 9"></polygon><path d="M18 9a5 5 0 0 1 0 6"></path></svg></span><span class="action-label">Sound</span><span class="action-mobile">Sound</span></button>
                <button type="button" class="quick-action" data-forward-action="ttsBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 18.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Z"></path><path d="M9.5 9.5h.01"></path><path d="M14.5 9.5h.01"></path><path d="M9 13.5s1 1.5 3 1.5 3-1.5 3-1.5"></path></svg></span><span class="action-label">Read</span><span class="action-mobile">Read</span></button>
              </div>
            </details>
            <h1 id="title">agent-index</h1>
            <div class="sub">
              <span class="pill" id="count">messages: 0</span>
              <span class="pill" id="filter">filter: all</span>
              <span class="pill" id="mode">mode: snapshot</span>
              <span class="pill" id="state">state: active</span>
              <span class="pill" id="source">source: -</span>
              <button id="autoModeBtn" type="button" title="Toggle auto-mode">Auto: off</button>
              <button id="caffeinateBtn" type="button" title="Toggle sleep prevention">Awake: off</button>
              <button id="soundBtn" type="button" title="Toggle sound notifications">Sound: off</button>
              <button id="ttsBtn" type="button" title="Toggle read-aloud (TTS)">Read: off</button>
              <input type="search" id="searchInput" class="search-input" placeholder="Search…" autocomplete="off" spellcheck="false">
              <span id="searchCount" class="search-count"></span>
              <div class="agent-filter-chips" id="agentFilterChips"></div>
            </div>
          </div>
        </div>
        <div class="header-right">

          <details class="header-plus-menu" id="attachedFilesMenu">
            <summary class="header-plus-toggle" title="Attached files" aria-label="Attached files">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            </summary>
            <div class="header-plus-panel" id="attachedFilesPanel"></div>
          </details>

          <details class="header-plus-menu right-menu" id="rightMenu">
            <summary class="header-plus-toggle" title="Menu">⋯</summary>
            <div class="header-plus-panel">
              <button type="button" class="quick-action" data-forward-action="openHub"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h16"></path><path d="M12 4v16"></path><circle cx="12" cy="12" r="8"></circle></svg></span><span class="action-label">Hub</span><span class="action-mobile">Hub</span></button>
              <button type="button" class="quick-action" data-forward-action="reloadChat"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 3v6h-6"></path><path d="M20 9a8 8 0 1 0 2 5.3"></path></svg></span><span class="action-label">Reload</span><span class="action-mobile">Reload</span></button>
              <button type="button" class="quick-action" data-forward-action="save"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h10l2 2v14H6z"></path><path d="M9 4v6h6V4"></path><path d="M9 16h6"></path></svg></span><span class="action-label">Save</span><span class="action-mobile">Save</span></button>
              <button type="button" class="quick-action" data-forward-action="exportBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg></span><span class="action-label">Export</span><span class="action-mobile">Export</span></button>
              <button type="button" class="quick-action" data-forward-action="killBtn" style="color: rgba(248, 113, 113, 0.96);"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"></circle><path d="m9 9 6 6"></path><path d="m15 9-6 6"></path></svg></span><span class="action-label">Kill</span><span class="action-mobile">Kill</span></button>
            </div>
          </details>
        </div>
      </div>
    </header>
    <main id="messages"></main>
    <button type="button" id="scrollToBottomBtn" title="Scroll to bottom" aria-label="Scroll to bottom"><svg viewBox="0 0 24 24" fill="none" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg></button>
    <form class="composer" id="composer">
      <div class="composer-main-shell">
        <div class="target-picker" id="targetPicker"></div>
        <div class="composer-stack">
          <details class="composer-plus-menu" id="composerPlusMenu">
            <summary class="composer-plus-toggle" aria-label="Open command menu">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            </summary>

            <div class="composer-plus-panel">
              <button type="button" class="quick-action divider-after" id="cameraBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg></span><span class="action-label">Camera</span><span class="action-mobile">Camera</span></button>
              <input type="file" id="cameraInput" multiple style="display:none">
              <button type="button" class="quick-action divider-after" data-forward-action="rawSendBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17 10 12 4 7"></path><path d="M12 17h8"></path></svg></span><span class="action-label">Raw</span><span class="action-mobile">Raw</span></button>
              <button type="button" class="quick-action" data-forward-action="briefBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"></circle><path d="m12 8 2.5 3.5L12 16l-2.5-4.5L12 8Z"></path></svg></span><span class="action-label">Brief</span><span class="action-mobile">Brief</span></button>
              <button type="button" class="quick-action" data-forward-action="readMemoryBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v11"></path><path d="m8 10 4 4 4-4"></path><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path></svg></span><span class="action-label">Load</span><span class="action-mobile">Load</span></button>
              <button type="button" class="quick-action divider-after" data-forward-action="memoryBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h10l2 2v14H6z"></path><path d="M9 4v6h6V4"></path><path d="M9 16h6"></path></svg></span><span class="action-label">Memory</span><span class="action-mobile">Memory</span></button>
              <button type="button" class="quick-action" data-forward-action="restart"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"></rect><path d="M15.5 10A4 4 0 1 0 16 15"></path><path d="M16 9v3h-3"></path></svg></span><span class="action-label">Restart</span><span class="action-mobile">Restart</span></button>
              <button type="button" class="quick-action" data-forward-action="resume"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v10"></path><path d="m8 11 4 4 4-4"></path><path d="M5 19h14"></path></svg></span><span class="action-label">Resume</span><span class="action-mobile">Resume</span></button>
              <button type="button" class="quick-action" data-forward-action="ctrlc"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"></rect><path d="M8 10h.01"></path><path d="M11 10h.01"></path><path d="M14 10h.01"></path><path d="M17 10h.01"></path><path d="M8 14h8"></path></svg></span><span class="action-label">Ctrl+C</span><span class="action-mobile">Ctrl+C</span></button>
              <button type="button" class="quick-action" data-forward-action="enter"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 10 4 15 9 20"></polyline><path d="M20 4v7a4 4 0 0 1-4 4H4"></path></svg></span><span class="action-label">Enter</span><span class="action-mobile">Enter</span></button>
              <button type="button" class="quick-action" data-forward-action="interrupt"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"></rect><path d="m9 10 6 6"></path><path d="m15 10-6 6"></path></svg></span><span class="action-label">Esc</span><span class="action-mobile">Esc</span></button>
            </div>
          </details>
          <div class="composer-shell">
            <div class="reply-banner" id="replyBanner">
              <span class="reply-banner-arrow">↩</span>
              <span class="reply-banner-text"><span class="reply-banner-sender" id="replyBannerSender"></span><span id="replyBannerPreview"></span></span>
              <button type="button" class="reply-cancel-btn" id="replyCancelBtn" title="返信キャンセル">✕</button>
            </div>
            <div id="attachPreviewRow" class="attach-preview-row" style="display:none"></div>
            <div class="composer-field">
              <textarea id="message" placeholder="Write a message"></textarea>
              <button type="button" id="micBtn" class="mic-btn" aria-label="Voice input">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
              </button>
              <button type="submit" class="send-btn" aria-label="Send">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
              </button>
            </div>
          </div>
          <div class="quick-actions">
            <button type="button" class="quick-action raw-send-btn" id="rawSendBtn" title="Send without [From: User] or msg-id"><span class="action-emoji">↪</span><span class="action-label">Raw Send</span><span class="action-mobile">Raw</span></button>
            <details class="quick-more">
              <summary class="quick-action quick-more-toggle"><span class="action-emoji">⋯</span><span class="action-label">Cmd</span><span class="action-mobile">Cmd</span></summary>
              <div class="quick-more-menu">
                <button type="button" class="quick-action brief-btn" id="briefBtn"><span class="action-emoji">🧭</span><span class="action-label">Send Brief</span><span class="action-mobile">Brief</span></button>
                <button type="button" class="quick-action read-btn" id="readMemoryBtn"><span class="action-emoji">📥</span><span class="action-label">Load Memory</span><span class="action-mobile">Load</span></button>
                <button type="button" class="quick-action memory-btn" id="memoryBtn"><span class="action-emoji">💾</span><span class="action-label">Save Memory</span><span class="action-mobile">Memory</span></button>
                <button type="button" class="quick-action" data-shortcut="save"><span class="action-emoji">📝</span><span class="action-label">Save Log</span><span class="action-mobile">Save</span></button>
                <button type="button" class="quick-action" data-shortcut="restart" title="Restart selected agent panes"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"></rect><path d="M15.5 10A4 4 0 1 0 16 15"></path><path d="M16 9v3h-3"></path></svg></span><span class="action-label">Restart</span><span class="action-mobile">Restart</span></button>
                <button type="button" class="quick-action" data-shortcut="resume" title="Resume selected agent panes"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v10"></path><path d="m8 11 4 4 4-4"></path><path d="M5 19h14"></path></svg></span><span class="action-label">Resume</span><span class="action-mobile">Resume</span></button>
                <button type="button" class="quick-action" data-shortcut="ctrlc" title="Send Ctrl+C to selected agents"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"></rect><path d="M8 10h.01"></path><path d="M11 10h.01"></path><path d="M14 10h.01"></path><path d="M17 10h.01"></path><path d="M8 14h8"></path></svg></span><span class="action-label">Ctrl+C</span><span class="action-mobile">Ctrl+C</span></button>
                <button type="button" class="quick-action" data-shortcut="enter" title="Send Enter to selected agents"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 10 4 15 9 20"></polyline><path d="M20 4v7a4 4 0 0 1-4 4H4"></path></svg></span><span class="action-label">Enter</span><span class="action-mobile">Enter</span></button>
                <button type="button" class="quick-action" data-shortcut="interrupt" title="Send Escape to selected agents"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"></rect><path d="m9 10 6 6"></path><path d="m15 10-6 6"></path></svg></span><span class="action-label">Interrupt</span><span class="action-mobile">Esc</span></button>
                <button type="button" class="quick-action kill-btn" id="killBtn" data-shortcut="kill" title="Kill process"><span class="action-emoji">🛑</span><span class="action-label">Kill</span><span class="action-mobile">Kill</span></button>
              </div>
            </details>
          </div>
        </div>
      </div>
      <div class="statusline" id="statusline"></div>
    </form>
  </section>
  <script>
    const renderMarkdown = (text) => {
      if (typeof marked !== "undefined") {
        try {
          const mathBlocks = [];
          let placeholderCount = 0;
          
          // Protection: replace math with spans that marked.js will ignore or pass through
          let processedText = text.replace(/(\$\$[\s\S]+?\$\$|\$[\s\S]+?\$)/g, (match) => {
            const id = `math-placeholder-${placeholderCount++}`;
            mathBlocks.push({ id, content: match });
            return `<span class="MATH_SAFE_BLOCK" data-id="${id}"></span>`;
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
          
          return injectFileCards(tempDiv.innerHTML);
        } catch (_) {}
      }
      // fallback: plain text
      return injectFileCards("<pre>" + escapeHtml(text) + "</pre>");
    };
    const FILE_ICONS = {
      png:"🖼️",jpg:"🖼️",jpeg:"🖼️",gif:"🖼️",webp:"🖼️",svg:"🖼️",ico:"🖼️",
      pdf:"📕",
      mp4:"🎬",mov:"🎬",webm:"🎬",avi:"🎬",mkv:"🎬",
      mp3:"🎵",wav:"🎵",ogg:"🎵",m4a:"🎵",flac:"🎵",
      zip:"📦",tar:"📦",gz:"📦",bz2:"📦",rar:"📦",
      md:"📝",txt:"📝",
      py:"🐍",js:"📜",ts:"📜",sh:"⚙️",json:"⚙️",yaml:"⚙️",yml:"⚙️",
      html:"🌐",css:"🎨",
    };
    const injectFileCards = (html) => {
      return html.replace(/\[Attached:\s*([^\]]+)\]/g, (match, rawPath) => {
        const path = rawPath.trim();
        const filename = path.split("/").pop();
        const pathDiffers = path !== filename;
        const ext = filename.includes(".") ? filename.split(".").pop().toLowerCase() : "";
        const icon = FILE_ICONS[ext] || "📄";
        return `<button type="button" class="file-card" data-filepath="${escapeHtml(path)}" data-ext="${escapeHtml(ext)}">` +
          `<span class="file-card-icon">${icon}</span>` +
          `<span class="file-card-name">${escapeHtml(filename)}</span>` +
          `<span class="file-card-open">↗</span>` +
          `</button>`;
      });
    };
    const followMode = new URLSearchParams(window.location.search).get("follow") === "1";
    const reconnectingStatusText = "reconnecting...";
    let messageRefreshFailures = 0;
    let reconnectStatusVisible = false;
    let refreshInFlight = false;
    let pendingRefreshOptions = null;
    let reloadInFlight = false;
    let traceFetchInFlight = false;
    const traceCache = new Map();
    let currentTraceTarget = null;
    let openThinkingPaneAgent = "";
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const AGENT_ICON_DATA = __ICON_DATA_URIS__;
    const SERVER_INSTANCE_SEED = "__SERVER_INSTANCE__";
    let currentServerInstance = SERVER_INSTANCE_SEED;
    const timeline = document.getElementById("messages");
    const useDocumentFlowMobile = () => window.matchMedia("(max-width: 430px)").matches;
    const getScrollMetrics = () => {
      if (useDocumentFlowMobile()) {
        const doc = document.documentElement;
        const body = document.body;
        return {
          scrollTop: window.scrollY || doc.scrollTop || body.scrollTop || 0,
          clientHeight: window.innerHeight || doc.clientHeight || 0,
          scrollHeight: Math.max(doc.scrollHeight, body.scrollHeight, timeline.scrollHeight),
        };
      }
      return {
        scrollTop: timeline.scrollTop,
        clientHeight: timeline.clientHeight,
        scrollHeight: timeline.scrollHeight,
      };
    };
    const scrollConversationToBottom = (behavior = "auto") => {
      const { scrollHeight } = getScrollMetrics();
      if (useDocumentFlowMobile()) {
        window.scrollTo({ top: scrollHeight, behavior });
        return;
      }
      timeline.scrollTo({ top: scrollHeight, behavior });
    };
    const scrollLatestMessageBottomToCenter = (behavior = "auto") => {
      const lastMessage = timeline.querySelector("article.message-row:last-of-type");
      if (!lastMessage) {
        scrollConversationToBottom(behavior);
        return;
      }
      if (useDocumentFlowMobile()) {
        const messageRect = lastMessage.getBoundingClientRect();
        const mobileBottomAnchorRatio = 0.45;
        const targetTop = Math.max(
          0,
          (window.scrollY || document.documentElement.scrollTop || 0) + messageRect.bottom - (window.innerHeight * mobileBottomAnchorRatio),
        );
        window.scrollTo({ top: targetTop, behavior });
        return;
      }
      const timelineRect = timeline.getBoundingClientRect();
      const messageRect = lastMessage.getBoundingClientRect();
      const desktopBottomAnchorRatio = 0.5;
      const targetTop = Math.max(
        0,
        timeline.scrollTop + (messageRect.bottom - timelineRect.top) - (timeline.clientHeight * desktopBottomAnchorRatio),
      );
      timeline.scrollTo({ top: targetTop, behavior });
    };
    const syncMobileKeyboardOffset = () => {
      if (!useDocumentFlowMobile()) {
        document.documentElement.style.setProperty("--mobile-keyboard-offset", "0px");
        document.documentElement.style.setProperty("--mobile-keyboard-transition-duration", "260ms");
        return;
      }
      const vv = window.visualViewport;
      if (!vv) {
        document.documentElement.style.setProperty("--mobile-keyboard-offset", "0px");
        document.documentElement.style.setProperty("--mobile-keyboard-transition-duration", "260ms");
        return;
      }
      const layoutViewportHeight = window.innerHeight || vv.height || 0;
      const keyboardOpen = vv.height < layoutViewportHeight * 0.9;
      const bottomOffset = keyboardOpen
        ? Math.max(0, Math.round(layoutViewportHeight - vv.height - vv.offsetTop))
        : 0;
      document.documentElement.style.setProperty("--mobile-keyboard-transition-duration", bottomOffset > 0 ? "260ms" : "180ms");
      document.documentElement.style.setProperty("--mobile-keyboard-offset", `${bottomOffset}px`);
    };
    const releaseMobileKeyboardOffset = () => {
      if (!useDocumentFlowMobile()) return;
      document.documentElement.style.setProperty("--mobile-keyboard-transition-duration", "180ms");
      document.documentElement.style.setProperty("--mobile-keyboard-offset", "0px");
    };
    const dismissMobileKeyboardImmediately = (inputEl = null) => {
      if (!useDocumentFlowMobile()) return;
      document.documentElement.style.setProperty("--mobile-keyboard-transition-duration", "0ms");
      document.documentElement.style.setProperty("--mobile-keyboard-offset", "0px");
      const activeEl = document.activeElement;
      if (inputEl) {
        inputEl.readOnly = true;
      }
      if (activeEl && typeof activeEl.blur === "function") {
        activeEl.blur();
      }
      if (inputEl && typeof inputEl.blur === "function") {
        inputEl.blur();
      }
      setTimeout(() => {
        if (inputEl) {
          inputEl.readOnly = false;
        }
        document.documentElement.style.setProperty("--mobile-keyboard-transition-duration", "180ms");
      }, 40);
    };
    const isMobileKeyboardOpen = () => {
      if (!useDocumentFlowMobile()) return false;
      const vv = window.visualViewport;
      if (!vv) return false;
      const layoutViewportHeight = window.innerHeight || vv.height || 0;
      return vv.height < layoutViewportHeight * 0.9;
    };
    let pendingMobileSendBottomScroll = false;
    let mobileSendTriggeredByButton = false;
    let pendingMobileTouchButtonSubmit = false;
    const focusMessageInputWithoutScroll = (selectionStart = null, selectionEnd = selectionStart) => {
      const anchorY = window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0;
      try {
        messageInput.focus({ preventScroll: true });
      } catch (_) {
        messageInput.focus();
      }
      if (selectionStart !== null && typeof messageInput.setSelectionRange === "function") {
        try {
          messageInput.setSelectionRange(selectionStart, selectionEnd ?? selectionStart);
        } catch (_) {}
      }
      if (useDocumentFlowMobile()) {
        requestAnimationFrame(() => window.scrollTo({ top: anchorY, behavior: "auto" }));
      }
    };
    const fileModal = document.getElementById("fileModal");
    const fileModalFrame = document.getElementById("fileModalFrame");
    const fileModalTitle = document.getElementById("fileModalTitle");
    const fileModalPath = document.getElementById("fileModalPath");
    const fileModalIcon = document.getElementById("fileModalIcon");
    let lastFocusedElement = null;
    const closeFileModal = () => {
      if (fileModal.hidden) return;
      fileModal.classList.remove("visible");
      fileModal.classList.add("closing");
      setTimeout(() => {
        fileModal.hidden = true;
        fileModal.classList.remove("closing");
        fileModalFrame.removeAttribute("src");
        document.body.classList.remove("file-modal-open");
        if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
          lastFocusedElement.focus({ preventScroll: true });
        }
        lastFocusedElement = null;
      }, 300);
    };
    const setFileModalEnterOffset = (sourceEl, triggerEvent) => {
      let originX = window.innerWidth / 2;
      let originY = window.innerHeight / 2;
      if (triggerEvent && typeof triggerEvent.clientX === "number" && typeof triggerEvent.clientY === "number") {
        originX = triggerEvent.clientX;
        originY = triggerEvent.clientY;
      } else if (sourceEl && typeof sourceEl.getBoundingClientRect === "function") {
        const rect = sourceEl.getBoundingClientRect();
        originX = rect.left + rect.width / 2;
        originY = rect.top + rect.height / 2;
      }
      const offsetX = Math.round(originX - window.innerWidth / 2);
      const offsetY = Math.round(originY - window.innerHeight / 2);
      fileModal.style.setProperty("--file-modal-enter-x", `${offsetX}px`);
      fileModal.style.setProperty("--file-modal-enter-y", `${offsetY}px`);
    };
    const openFileModal = (path, ext, sourceEl, triggerEvent) => {
      const normalizedExt = (ext || "").toLowerCase();
      const filename = (path.split("/").pop() || path || "Preview").trim();
      const parentPath = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
      const viewerUrl = (normalizedExt === "html" || normalizedExt === "htm")
        ? `/file-raw?path=${encodeURIComponent(path)}`
        : `/file-view?path=${encodeURIComponent(path)}&embed=1`;
      if (normalizedExt === "pdf") {
        window.location.href = `/file-raw?path=${encodeURIComponent(path)}`;
        return;
      }
      fileModalTitle.textContent = filename;
      fileModalPath.textContent = parentPath;
      fileModalPath.style.display = parentPath ? "" : "none";
      fileModalIcon.textContent = FILE_ICONS[normalizedExt] || "📄";
      lastFocusedElement = sourceEl || document.activeElement;
      setFileModalEnterOffset(sourceEl, triggerEvent);
      
      // Prevent white flash by hiding iframe until it loads
      fileModalFrame.style.opacity = "0";
      fileModalFrame.onload = () => {
        fileModalFrame.style.transition = "opacity 200ms ease-out";
        fileModalFrame.style.opacity = "1";
      };
      fileModalFrame.src = viewerUrl;

      fileModal.hidden = false;
      fileModal.classList.add("visible");
      document.body.classList.add("file-modal-open");
    };
    fileModal.addEventListener("click", (event) => {
      if (event.target.closest("[data-close-file-modal]")) {
        closeFileModal();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !fileModal.hidden) {
        event.preventDefault();
        closeFileModal();
      }
    });
    const scrollToBottomBtn = document.getElementById("scrollToBottomBtn");
    scrollToBottomBtn.addEventListener("click", () => {
      scrollConversationToBottom("smooth");
    });
    const MOBILE_LATEST_MESSAGE_BOTTOM_RATIO = 0.45;
    const updateScrollBtnPos = () => {
      const shell = document.querySelector(".shell");
      const composer = document.getElementById("composer");
      const composerBox = document.querySelector(".composer-main-shell");
      const h = useDocumentFlowMobile() ? (composerBox?.offsetHeight || 0) : composer.offsetHeight;
      const mobileComposerReserve = Math.max(0, Math.ceil(h + 18));
      if (useDocumentFlowMobile()) {
        const vv = window.visualViewport;
        const layoutHeight = window.innerHeight || document.documentElement.clientHeight || 0;
        const keyboardOpen = !!(vv && layoutHeight > 0 && vv.height < layoutHeight * 0.9);
        if (!keyboardOpen && layoutHeight > 0) {
          const targetBottomReserve = Math.max(
            mobileComposerReserve,
            Math.round(layoutHeight * (1 - MOBILE_LATEST_MESSAGE_BOTTOM_RATIO)),
          );
          document.documentElement.style.setProperty(
            "--mobile-latest-anchor-gap",
            `${Math.max(0, targetBottomReserve - mobileComposerReserve)}px`,
          );
        }
      } else {
        document.documentElement.style.setProperty("--mobile-latest-anchor-gap", "0px");
      }
      document.documentElement.style.setProperty(
        "--mobile-composer-reserve",
        useDocumentFlowMobile() ? `${mobileComposerReserve}px` : "0px",
      );
      shell.style.setProperty("--scroll-btn-bottom", (h + 12) + "px");
      if (window.matchMedia("(max-width: 359px)").matches) {
        const picker = document.getElementById("targetPicker");
        const shellRect = shell.getBoundingClientRect();
        const pickerRect = picker.getBoundingClientRect();
        const btnSize = scrollToBottomBtn.offsetHeight || 44;
        const centerY = pickerRect.top + (pickerRect.height / 2);
        const bottom = Math.max(12, Math.round(shellRect.bottom - centerY - (btnSize / 2)));
        shell.style.setProperty("--scroll-btn-bottom-mobile", `${bottom}px`);
        return;
      }
      shell.style.removeProperty("--scroll-btn-bottom-mobile");
    };
    const mathRenderOptions = {
      delimiters: [
        {left: '$$', right: '$$', display: true},
        {left: '$', right: '$', display: false},
        {left: '\\[', right: '\\]', display: true}
      ],
      throwOnError: false
    };
    const renderMathInScope = (node) => {
      if (!node || typeof renderMathInElement === "undefined") return;
      renderMathInElement(node, mathRenderOptions);
    };
    const viewportCenterGutter = () => {
      const raw = getComputedStyle(document.documentElement).getPropertyValue("--viewport-center-gutter");
      const parsed = Number.parseFloat(raw);
      return Number.isFinite(parsed) ? parsed : 24;
    };
    const ensureWideTables = (scope = document) => {
      scope.querySelectorAll(".md-body table").forEach((table) => {
        if (table.closest(".table-scroll")) return;
        const parent = table.parentNode;
        if (!parent) return;
        const scroll = document.createElement("div");
        scroll.className = "table-scroll";
        parent.insertBefore(scroll, table);
        scroll.appendChild(table);
      });
    };
    const syncWideBlockRows = (scope = document) => {
      scope.querySelectorAll(".message-body-row").forEach((row) => {
        const body = row.querySelector(".md-body");
        const hasWideBlock = !!body?.querySelector("pre, .table-scroll");
        const hasStructuredBlock = !!body?.querySelector("ul, ol, blockquote");
        row.classList.toggle("has-wide-block", hasWideBlock);
        row.classList.toggle("has-structured-block", hasStructuredBlock);
      });
    };
    const updateViewportCenteredBlocks = (scope = document) => {
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
      if (!viewportWidth) return;
      const gutter = viewportCenterGutter();
      const maxWidth = Math.max(160, Math.floor(viewportWidth - (gutter * 2)));
      scope.querySelectorAll(".katex-display, .viewport-centered-block").forEach((block) => {
        const content = block.matches(".katex-display")
          ? block.querySelector(".katex")
          : block.querySelector("table");
        if (!content) return;
        block.style.removeProperty("--viewport-centered-width");
        block.style.removeProperty("--viewport-centered-shift");
        const rawWidth = Math.max(
          content.scrollWidth || 0,
          Math.ceil(content.getBoundingClientRect().width || 0),
        );
        const overflowCushion = block.matches(".katex-display") ? 2 : 0;
        const targetWidth = Math.min(maxWidth, Math.max(0, rawWidth + overflowCushion));
        if (targetWidth > 0) {
          block.style.setProperty("--viewport-centered-width", `${targetWidth}px`);
        }
        const rect = block.getBoundingClientRect();
        const shift = Math.round((viewportWidth / 2) - (rect.left + (rect.width / 2)));
        block.style.setProperty("--viewport-centered-shift", `${shift}px`);
      });
    };
    let viewportCenteredBlocksRaf = 0;
    const scheduleViewportCenteredBlocks = (scope = document) => {
      ensureWideTables(scope);
      syncWideBlockRows(scope);
      if (viewportCenteredBlocksRaf) cancelAnimationFrame(viewportCenteredBlocksRaf);
      viewportCenteredBlocksRaf = requestAnimationFrame(() => {
        viewportCenteredBlocksRaf = 0;
        updateViewportCenteredBlocks(scope);
      });
    };
    updateScrollBtnPos();
    new ResizeObserver(updateScrollBtnPos).observe(document.getElementById("composer"));
    new ResizeObserver(updateScrollBtnPos).observe(document.querySelector(".composer-main-shell"));
    new ResizeObserver(updateScrollBtnPos).observe(document.getElementById("targetPicker"));
    window.addEventListener("resize", updateScrollBtnPos);
    window.addEventListener("resize", () => scheduleViewportCenteredBlocks(document));
    if (document.fonts?.ready) {
      document.fonts.ready.then(() => scheduleViewportCenteredBlocks(document)).catch(() => {});
    }
    const roleClass = (sender) => {
      sender = (sender || "").toLowerCase();
      if (["user","claude","codex","gemini","copilot"].includes(sender)) return sender;
      return "system";
    };
    const senderBadge = (sender) => ((sender || "?").trim()[0] || "?").toUpperCase();
    const AGENT_ICON_NAMES = new Set(["claude", "codex", "gemini", "copilot"]);
    const agentIconSrc = (name) => {
      const s = (name || "").toLowerCase();
      return AGENT_ICON_DATA[s] || `/icon/${encodeURIComponent(s)}`;
    };
    const iconImg = (name, cls) => {
      const s = (name || "").toLowerCase();
      if (!AGENT_ICON_NAMES.has(s)) return "";
      return `<img class="${cls}" src="${escapeHtml(agentIconSrc(s))}" alt="${escapeHtml(s)}">`;
    };
    const thinkingIconImg = (name, cls) => {
      const s = (name || "").toLowerCase();
      if (!AGENT_ICON_NAMES.has(s)) return "";
      const src = s === "codex" ? "/icon/codex" : agentIconSrc(s);
      return `<img class="${cls}" src="${escapeHtml(src)}" alt="${escapeHtml(s)}">`;
    };
    const statusIcon = (name, cls) => {
      const s = (name || "").toLowerCase();
      if (!AGENT_ICON_NAMES.has(s)) return "";
      return `<span class="${cls}" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(s))}')"></span>`;
    };
    const metaAgentLabel = (name, textClass, iconSide = "right") => {
      const raw = (name || "").trim() || "unknown";
      const s = raw.toLowerCase();
      const icon = AGENT_ICON_NAMES.has(s)
        ? `<span class="meta-agent-icon" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(s))}')"></span>`
        : "";
      const sideClass = iconSide === "right" ? " icon-right" : "";
      return `<span class="meta-agent${sideClass}">${icon}<span class="${textClass}">${escapeHtml(raw)}</span></span>`;
    };
    const senderAvatar = (sender) => {
      const s = (sender || "").toLowerCase();
      if (AGENT_ICON_NAMES.has(s)) {
        return { cls: "avatar-icon", html: `<img src="${escapeHtml(agentIconSrc(s))}" alt="${escapeHtml(s)}" width="28" height="28">` };
      }
      return { cls: "", html: escapeHtml(senderBadge(sender)) };
    };
    const formatDayLabel = (value) => {
      const date = value ? new Date(value) : null;
      if (!date || Number.isNaN(date.getTime())) {
        return "Conversation";
      }
      return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    };
    let selectedTargets = [];
    let sendLocked = false;
    let lastSubmitAt = 0;
    let sessionActive = true;
    let pendingReplyTo = null;
    let pendingAttachments = []; // [{path, name}]
    let rawSendEnabled = false;
    let availableTargets = [];
    let filterKeyword = "";
    let filterAgents = new Set(); // empty = show all
    let _renderedIds = new Set(); // incremental render tracking
    const expandedUserMessages = new Set();
    const THINKING_AGENT_ORDER = ["claude", "codex", "gemini", "copilot"];
    const applyFilter = () => {
      const kw = filterKeyword.toLowerCase();
      const isFiltering = kw || filterAgents.size > 0;
      let visible = 0;
      document.querySelectorAll("#messages article.message-row").forEach(article => {
        const sender = (article.dataset.sender || "").toLowerCase();
        const raw = (article.querySelector(".message-wrap")?.dataset.raw || "").toLowerCase();
        const matchAgent = filterAgents.size === 0 || filterAgents.has(sender);
        const matchKeyword = !kw || sender.includes(kw) || raw.includes(kw);
        const ok = matchAgent && matchKeyword;
        article.classList.toggle("filtered-out", !ok);
        if (ok) visible++;
      });
      document.querySelectorAll("#messages .message-thinking-row").forEach((row) => {
        row.style.display = visible > 0 ? "" : "none";
      });
      const countEl = document.getElementById("searchCount");
      if (countEl) countEl.textContent = isFiltering ? `${visible} hits` : "";
    };
    const renderAgentFilterChips = (agents) => {
      const root = document.getElementById("agentFilterChips");
      if (!root) return;
      if (isCompactMobile()) {
        root.innerHTML = "";
        return;
      }
      root.innerHTML = ["all", "user", ...agents].map(a => {
        const active = (a === "all" ? filterAgents.size === 0 : filterAgents.has(a)) ? " active" : "";
        const icon = a === "user" ? "" : iconImg(a, "filter-icon");
        const label = `<span class="filter-label">${escapeHtml(a)}</span>`;
        return `<button type="button" class="filter-chip${active}" data-agent="${escapeHtml(a)}">${icon}${label}</button>`;
      }).join("");
      root.querySelectorAll(".filter-chip").forEach(btn => {
        btn.addEventListener("click", () => {
          const ag = btn.dataset.agent;
          if (ag === "all") {
            filterAgents.clear();
          } else if (filterAgents.has(ag)) {
            filterAgents.delete(ag);
          } else {
            filterAgents.add(ag);
          }
          renderAgentFilterChips(agents);
          applyFilter();
        });
      });
    };
    const escapeHtml = (value) => value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
    const emptyConversationHTML = () => {
      return `<div class="conversation-empty">
        <div class="daybreak">Conversation</div>
        <section class="conversation-empty-card" aria-label="Empty conversation">
          <h2 class="conversation-empty-title">New session</h2>
          <p class="conversation-empty-copy">This session has no messages yet. Send the first message when you are ready.</p>
        </section>
      </div>`;
    };
    const stripSenderPrefix = (value) => value.replace(/^\[From:\s*[^\]]+\]\s*/i, "");
    const shortcutName = (value) => {
      const normalized = (value || "").trim().toLowerCase();
      const mapped = {
        "brief": "brief",
        "interrupt": "interrupt",
        "esc": "interrupt",
        "kill": "kill",
        "save": "save",
        "restart": "restart",
        "resume": "resume",
        "ctrl+c": "ctrlc",
        "ctrlc": "ctrlc",
        "enter": "enter",
      }[normalized];
      return mapped || "";
    };
    const shortcutLabel = (value) => ({
      "brief": "Brief",
      "interrupt": "Esc",
      "kill": "Kill",
      "save": "Save",
      "restart": "Restart",
      "resume": "Resume",
      "ctrlc": "Ctrl+C",
      "enter": "Enter",
    }[(value || "").trim().toLowerCase()] || value);
    const renderTargetPicker = (targets) => {
      const root = document.getElementById("targetPicker");
      const selectedSet = new Set(selectedTargets);
      const targetsSig = JSON.stringify(targets);
      const selectionSig = JSON.stringify([...selectedSet].sort());
      const renderSig = `${targetsSig}|${selectionSig}`;
      if (root.dataset.renderSig === renderSig) return;
      if (root.dataset.targetsSig !== targetsSig) {
        root.dataset.targetsSig = targetsSig;
        root.innerHTML = targets.map((target) => {
          return `<button type="button" class="target-chip" data-target="${target}" title="${escapeHtml(target)}"><img class="target-icon" src="${escapeHtml(agentIconSrc(target))}" alt="${escapeHtml(target)}"><span class="target-label">${escapeHtml(target)}</span></button>`;
        }).join("");
        root.querySelectorAll(".target-chip").forEach((node) => {
          node.addEventListener("mousedown", (e) => e.preventDefault());
          node.addEventListener("click", () => {
            const target = node.dataset.target;
            if (selectedTargets.includes(target)) {
              selectedTargets = selectedTargets.filter((item) => item !== target);
            } else {
              selectedTargets = [...selectedTargets, target];
            }
            saveTargetSelection(document.getElementById("title").textContent, selectedTargets);
            renderTargetPicker(availableTargets);
          });
        });
      }
      root.querySelectorAll(".target-chip").forEach((node) => {
        node.classList.toggle("active", selectedSet.has(node.dataset.target));
      });
      root.dataset.renderSig = renderSig;
    };
    const setQuickActionsDisabled = (disabled) => {
      document.querySelectorAll(".quick-action").forEach((node) => {
        node.disabled = disabled;
      });
    };
    const isNearBottom = () => {
      const { scrollTop, clientHeight, scrollHeight } = getScrollMetrics();
      if (useDocumentFlowMobile()) {
        return scrollTop + clientHeight >= scrollHeight - 80;
      }
      // On desktop, we consider it "near bottom" if the scroll is within half a screen of the total height.
      // This is because we have large padding and a centered anchor.
      return scrollTop + clientHeight >= scrollHeight - (clientHeight * 1.5);
    };
    const updateScrollBtn = () => {
      scrollToBottomBtn.classList.toggle("visible", !isNearBottom());
    };
    const renderRawSendButton = () => {
      const button = document.getElementById("rawSendBtn");
      if (!button) return;
      const on = !!rawSendEnabled;
      button.classList.toggle("raw-on", on);
      button.classList.toggle("raw-off", !on);
      document.querySelectorAll('[data-forward-action="rawSendBtn"]').forEach(n => n.classList.toggle("raw-on", on));
      document.querySelectorAll('[data-forward-action="rawSendBtn"]').forEach(n => n.classList.toggle("raw-off", !on));
      button.setAttribute("aria-pressed", on ? "true" : "false");
      button.title = on
        ? "Raw send enabled: send without [From: User] or msg-id"
        : "Raw send disabled";
    };
    const flashHeaderToggle = (targetNode) => {
      const nodes = targetNode ? [targetNode] : document.querySelectorAll(`#headerPlusMenu summary, #rightMenu summary`);
      nodes.forEach((node) => {
        if (node.classList.contains("animating")) return;
        node.classList.add("animating");
        setTimeout(() => {
          node.classList.remove("animating");
        }, 500);
      });
    };
    const flashComposerAction = (action) => {
      document.querySelectorAll(`.composer-plus-panel [data-forward-action="${action}"]`).forEach((node) => {
        node.classList.remove("toggle-flash");
        void node.offsetWidth;
        node.classList.add("toggle-flash");
        setTimeout(() => node.classList.remove("toggle-flash"), 120);
      });
    };
    const targetSelectionStorageKey = (session) => `targetSelection:${session || "default"}`;
    const saveTargetSelection = (session, targets) => {
      if (!session) return;
      try {
        localStorage.setItem(targetSelectionStorageKey(session), JSON.stringify(targets || []));
      } catch (_) {}
    };
    const loadTargetSelection = (session, availableTargets = []) => {
      if (!session) return [];
      try {
        const raw = localStorage.getItem(targetSelectionStorageKey(session));
        const parsed = JSON.parse(raw || "[]");
        if (!Array.isArray(parsed)) return [];
        const allowed = new Set(availableTargets);
        return parsed.filter((item) => typeof item === "string" && allowed.has(item));
      } catch (_) {
        return [];
      }
    };
    timeline.addEventListener("scroll", updateScrollBtn, { passive: true });
    window.addEventListener("scroll", updateScrollBtn, { passive: true });
    let lastMessagesSig = "";
    let initialLoadDone = false;
    let lastNotifiedMsgId = "";
    let soundEnabled = (() => { try { return localStorage.getItem("soundEnabled") === "1"; } catch(_) { return false; } })();
    let _audioCtx = null;
    let _beepBuffer = null;
    let _audioPrimed = false;
    let _lastSoundAt = 0;
    const SOUND_COOLDOWN_MS = 700;
    const buildNotificationSamples = (sampleRate) => {
      const duration = 0.55;
      const frameCount = Math.floor(sampleRate * duration);
      const samples = new Float32Array(frameCount);
      // Two-note ascending chime: E5(659Hz) then G5(784Hz), bell-like decay
      const notes = [
        { freq: 659, start: 0.0,  amp: 0.17, decay: 8  },
        { freq: 784, start: 0.13, amp: 0.15, decay: 9  },
      ];
      for (let i = 0; i < frameCount; i++) {
        const t = i / sampleRate;
        let s = 0;
        for (const n of notes) {
          const dt = t - n.start;
          if (dt < 0) continue;
          const env = Math.min(dt * 250, 1) * Math.exp(-dt * n.decay);
          s += n.amp * env * Math.sin(2 * Math.PI * n.freq * t);
        }
        samples[i] = s;
      }
      return samples;
    };
    // iOS audio unlock: must call during user gesture
    const primeSound = async () => {
      try {
        if (!_audioCtx) {
          _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (_audioCtx.state === "suspended") {
          await _audioCtx.resume();
        }
        if (!_audioPrimed) {
          // Play a silent 1-sample buffer to unlock AudioContext on iOS
          const silentBuf = _audioCtx.createBuffer(1, 1, _audioCtx.sampleRate);
          const src = _audioCtx.createBufferSource();
          src.buffer = silentBuf;
          src.connect(_audioCtx.destination);
          src.start();
          _audioPrimed = true;
        }
        if (!_beepBuffer) {
          const sr = _audioCtx.sampleRate;
          _beepBuffer = _audioCtx.createBuffer(1, Math.floor(sr * 0.55), sr);
          _beepBuffer.getChannelData(0).set(buildNotificationSamples(sr));
        }
      } catch(e) { console.error("Audio prime failed", e); }
    };
    const playNotificationSound = () => {
      if (!soundEnabled || !_audioPrimed || !_audioCtx || !_beepBuffer) return;
      const now = Date.now();
      if (now - _lastSoundAt < SOUND_COOLDOWN_MS) return;
      _lastSoundAt = now;
      try {
        if (_audioCtx.state === "suspended") { _audioCtx.resume().catch(() => {}); return; }
        const s = _audioCtx.createBufferSource();
        s.buffer = _beepBuffer;
        s.connect(_audioCtx.destination);
        s.start();
      } catch(_) {}
    };
    // Resume AudioContext when page comes back to foreground
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && _audioCtx && _audioCtx.state === "suspended") {
        _audioCtx.resume().catch(() => {});
      }
    });
    const render = (data, { forceScroll = false } = {}) => {
      const mobileKeyboardOpen = isMobileKeyboardOpen();
      const suppressMobileSendScroll = mobileKeyboardOpen && pendingMobileSendBottomScroll;
      const shouldStickToBottom = (forceScroll && !suppressMobileSendScroll) || (!mobileKeyboardOpen && (isNearBottom() || (!useDocumentFlowMobile() && document.body.classList.contains("keyboard-locked"))));
      document.getElementById("title").textContent = data.session;
      const headerPanelTitle = document.getElementById("headerPanelTitle");
      if (headerPanelTitle) headerPanelTitle.textContent = data.session;
      loadThinkingTime(data.session);
      const displayEntries = window.matchMedia("(max-width: 430px)").matches
        ? data.entries.slice(-__MOBILE_MESSAGE_LIMIT__)
        : data.entries.slice(-__DESKTOP_MESSAGE_LIMIT__);
      document.getElementById("count").textContent = `messages: ${displayEntries.length}`;
      document.getElementById("filter").textContent = `filter: ${data.filter}`;
      document.getElementById("mode").textContent = `mode: ${followMode ? "follow" : "snapshot"}`;
      document.getElementById("state").textContent = `state: ${data.active ? "active" : "archived"}`;
      document.getElementById("source").textContent = `source: ${data.source}`;
      sessionActive = !!data.active;
      const picker = document.getElementById("targetPicker");
      if (!picker.dataset.loaded) {
        const restoredTargets = loadTargetSelection(data.session, data.targets);
        selectedTargets = restoredTargets.length
          ? restoredTargets
          : [];
        picker.dataset.loaded = "1";
        renderAgentStatus(Object.fromEntries(data.targets.map((t) => [t, "idle"])));
        renderAgentFilterChips(data.targets);
      }
      availableTargets = sessionActive ? data.targets : [];
      selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
      if (!selectedTargets.length && availableTargets.length) {
        const restoredTargets = loadTargetSelection(data.session, availableTargets);
        selectedTargets = restoredTargets.length
          ? restoredTargets
          : [];
      }
      saveTargetSelection(data.session, selectedTargets);
      renderTargetPicker(availableTargets);
      document.getElementById("message").disabled = !sessionActive;
      setQuickActionsDisabled(!sessionActive);
      if (!sessionActive) {
        setStatus("archived session is read-only");
      }
      const sig = `${displayEntries.length}:${displayEntries.at(-1)?.timestamp ?? ""}`;
      if (!forceScroll && sig === lastMessagesSig) return;
      lastMessagesSig = sig;
      if (initialLoadDone && (soundEnabled || ttsEnabled)) {
        const lastSeenIndex = lastNotifiedMsgId
          ? displayEntries.findIndex((e) => e.msg_id === lastNotifiedMsgId)
          : -1;
        const newEntries = lastSeenIndex >= 0
          ? displayEntries.slice(lastSeenIndex + 1)
          : (lastNotifiedMsgId ? displayEntries.slice(-1) : []);
        const agentEntries = newEntries.filter((e) => e.sender !== "user" && e.sender !== "system");
        if (agentEntries.length > 0) {
          if (soundEnabled) playNotificationSound();
          if (ttsEnabled) speakEntry(agentEntries[agentEntries.length - 1]);
        }
      }
      lastNotifiedMsgId = displayEntries.at(-1)?.msg_id || lastNotifiedMsgId;
      initialLoadDone = true;
      updateAttachedFilesPanel(data.entries);
      const root = document.getElementById("messages");
      if (!displayEntries.length) {
        _renderedIds.clear();
        root.innerHTML = emptyConversationHTML();
        renderThinkingIndicator();
        return;
      }
      const firstTimestamp = displayEntries[0]?.timestamp || "";
      const copyIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
      const checkIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`;
      const replyIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/></svg>`;
      const replyUpIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><polyline points="7 10 12 5 17 10"/></svg>`;
      const replyDownIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><polyline points="7 14 12 19 17 14"/></svg>`;
      const replyChildrenMap = new Map();
      displayEntries.forEach((entry) => {
        const parentId = (entry.reply_to || "").trim();
        const childId = (entry.msg_id || "").trim();
        if (!parentId || !childId || replyChildrenMap.has(parentId)) return;
        replyChildrenMap.set(parentId, childId);
      });
      const buildMsgHTML = (entry, replyPreviewHTML) => {
        if (entry.sender === "system") {
          const systemMessage = escapeHtml(entry.message || "");
          const systemTitle = systemMessage.replaceAll('"', "&quot;");
          return `<div class="sysmsg-row" data-msgid="${escapeHtml(entry.msg_id || "")}" data-sender="system" data-kind="${escapeHtml(entry.kind || "")}"><span class="sysmsg-text" title="${systemTitle}">${systemMessage}</span></div>`;
        }
        const cls = roleClass(entry.sender);
        const targetSpans = (entry.targets?.length > 0
          ? entry.targets.map(t => metaAgentLabel(t, "target-name", "right"))
          : [metaAgentLabel("no target", "target-name", "right")]).join(`<span class="meta-agent-sep">,</span>`);
        const body = stripSenderPrefix(entry.message || "");
        const rawAttr = escapeHtml(body).replaceAll('"', "&quot;");
        const previewAttr = escapeHtml(body.slice(0, 80)).replaceAll('"', "&quot;");
        const av = senderAvatar(entry.sender || "unknown");
        const msgId = escapeHtml(entry.msg_id || "");
        const replyToAttr = entry.reply_to ? escapeHtml(entry.reply_to).replaceAll('"', "&quot;") : "";
        const targetMeta = `<span class="targets">${targetSpans}</span>`;
        const replySourceJumpHtml = replyToAttr
          ? `<button class="reply-jump-inline reply-target-jump-btn" type="button" title="返信元へ移動" data-replyto="${replyToAttr}">${replyUpIcon}</button>`
          : "";
        const userTargetMeta = `<span class="targets">${targetSpans}</span>`;
        const sender = escapeHtml(entry.sender || "unknown");
        const isActive = pendingReplyTo?.msgId === entry.msg_id;
        const timestamp = escapeHtml(entry.timestamp || "");
        const isUser = cls === "user";
        const userTimestampHtml = timestamp ? `<time>${timestamp}</time>` : "";
        const copyButtonHtml = `<button class="copy-btn" type="button" title="コピー" data-copy-icon="${escapeHtml(copyIcon).replaceAll('"', "&quot;")}" data-check-icon="${escapeHtml(checkIcon).replaceAll('"', "&quot;")}">${copyIcon}</button>`;
        const firstReplyId = msgId ? replyChildrenMap.get(entry.msg_id || "") || "" : "";
        const replyTargetJumpHtml = firstReplyId
          ? `<button class="reply-target-jump-btn" type="button" title="返信先へ移動" data-replytarget="${escapeHtml(firstReplyId).replaceAll('"', "&quot;")}">${replyDownIcon}</button>`
          : "";
        const senderHtml = metaAgentLabel(entry.sender || "unknown", "sender-label", "right");

        return `<article class="message-row ${cls}" data-msgid="${msgId}" data-sender="${sender}">
          ${isUser ? `<div class="avatar${av.cls ? ` ${av.cls}` : ""}">${av.html}</div>` : ""}
          <div class="message-wrap" data-raw="${rawAttr}" data-preview="${previewAttr}">
          <div class="message ${cls}">
          ${replyPreviewHTML}
          <div class="message-body-row">
            <div class="md-body">${renderMarkdown(body)}</div>
            ${isUser ? `<button class="user-collapse-toggle" type="button" hidden>More</button>` : ""}
          </div>
          ${isUser ? `<div class="message-meta-below user-message-meta"><span class="arrow">to</span>${userTargetMeta}${userTimestampHtml}${replyTargetJumpHtml}${copyButtonHtml}</div>` : `<div class="message-meta-below">${copyButtonHtml}${replyTargetJumpHtml}${msgId ? `<button class="reply-btn${isActive ? ' active' : ''}" type="button" title="返信" data-msgid="${msgId}" data-sender="${sender}" data-preview="${previewAttr}">${replyIcon}</button>` : ""}${senderHtml}<span class="arrow">to</span>${targetMeta}${replySourceJumpHtml}</div>`}
          </div>
          </div>
        </article>`;
      };
      // Build msg_id map for reply preview lookups
      const msgMap = new Map();
      displayEntries.forEach(e => { if (e.msg_id) msgMap.set(e.msg_id, e); });
      const buildReplyPreviewHTML = (entry) => {
        return "";
      };
      // Incremental rendering: only append new messages to avoid re-animating existing ones
      const displayIdSet = new Set(displayEntries.map(e => e.msg_id));
      const newEntriesToRender = displayEntries.filter(e => !_renderedIds.has(e.msg_id));
      const hasRemovals = _renderedIds.size > 0 && [..._renderedIds].some(id => !displayIdSet.has(id));
      if (!hasRemovals && _renderedIds.size > 0 && newEntriesToRender.length > 0) {
        if (useDocumentFlowMobile() && shouldStickToBottom) {
          scrollConversationToBottom("auto");
        }
        // Append only new messages and animate them
        const frag = document.createDocumentFragment();
        const appendedRows = [];
        for (const entry of newEntriesToRender) {
          const tmpl = document.createElement("template");
          tmpl.innerHTML = buildMsgHTML(entry, buildReplyPreviewHTML(entry));
          const row = tmpl.content.firstElementChild;
          if (row) row.classList.add("animate-in");
          if (row) appendedRows.push(row);
          frag.appendChild(tmpl.content);
          _renderedIds.add(entry.msg_id);
        }
        root.appendChild(frag);
        appendedRows.forEach((row) => renderMathInScope(row));
        scheduleViewportCenteredBlocks(root);
      } else {
        // Full re-render: do not animate existing messages
        root.innerHTML = `<div class="daybreak">${escapeHtml(formatDayLabel(firstTimestamp))}</div>` + displayEntries.map(entry =>
          buildMsgHTML(entry, buildReplyPreviewHTML(entry))
        ).join("");
        _renderedIds = new Set(displayEntries.map(e => e.msg_id));
        renderMathInScope(root);
        scheduleViewportCenteredBlocks(root);
      }
      renderThinkingIndicator();
      applyFilter();
      syncUserMessageCollapse(root);
      if (shouldStickToBottom) {
        const scrollBehavior = "auto";
        scrollLatestMessageBottomToCenter(scrollBehavior);
      }
      updateScrollBtn();
      if (typeof updateSendBtnVisibility === "function") updateSendBtnVisibility();
    };
    const setStatus = (text, isError = false) => {
      const node = document.getElementById("statusline");
      node.textContent = text;
      node.style.color = isError ? "#fda4af" : "";
    };
    const setReconnectStatus = (active) => {
      const node = document.getElementById("statusline");
      const current = node.textContent || "";
      if (active) {
        if (reconnectStatusVisible || !current || current === reconnectingStatusText) {
          setStatus(reconnectingStatusText);
          reconnectStatusVisible = true;
        }
        return;
      }
      if (reconnectStatusVisible || current === reconnectingStatusText) {
        setStatus("");
      }
      reconnectStatusVisible = false;
    };
    const fetchWithTimeout = async (url, options = {}, timeoutMs = 1500) => {
      let timer = null;
      const controller = typeof AbortController === "function" ? new AbortController() : null;
      try {
        if (controller && timeoutMs > 0) {
          timer = setTimeout(() => controller.abort(), timeoutMs);
        }
        return await fetch(url, {
          cache: "no-store",
          ...options,
          signal: controller ? controller.signal : options.signal,
        });
      } finally {
        if (timer) clearTimeout(timer);
      }
    };
    const waitForChatReady = async (timeoutMs = 15000, expectedPreviousInstance = "") => {
      const deadline = Date.now() + timeoutMs;
      let sawDisconnect = false;
      while (Date.now() < deadline) {
        try {
          const res = await fetchWithTimeout(`/messages?ts=${Date.now()}`, {}, 1200);
          if (res.ok) {
            const data = await res.json();
            const instance = data?.server_instance || "";
            if (!expectedPreviousInstance || (instance && instance !== expectedPreviousInstance) || sawDisconnect) {
              if (instance) currentServerInstance = instance;
              return true;
            }
          }
        } catch (_) {
          sawDisconnect = true;
        }
        await sleep(200);
      }
      return false;
    };
    const navigateToFreshChat = () => {
      const params = new URLSearchParams(window.location.search);
      params.set("follow", followMode ? "1" : "0");
      params.set("ts", String(Date.now()));
      window.location.replace(`${window.location.pathname}?${params.toString()}`);
    };
    const mergeRefreshOptions = (current = {}, next = {}) => {
      const currentOptions = current || {};
      const nextOptions = next || {};
      return {
        forceScroll: !!(currentOptions.forceScroll || nextOptions.forceScroll),
      };
    };
    const refresh = async (options = {}) => {
      if (window.__STATIC_EXPORT__) { render(window.__EXPORT_PAYLOAD__, options); return; }
      if (refreshInFlight) {
        pendingRefreshOptions = mergeRefreshOptions(pendingRefreshOptions, options);
        return;
      }
      refreshInFlight = true;
      try {
        const res = await fetchWithTimeout(`/messages?ts=${Date.now()}`);
        if (!res.ok) throw new Error("messages unavailable");
        const data = await res.json();
        if (data?.server_instance) currentServerInstance = data.server_instance;
        messageRefreshFailures = 0;
        setReconnectStatus(false);
        render(data, options);
      } catch (_) {
        messageRefreshFailures += 1;
        if (followMode && messageRefreshFailures >= 3) {
          setReconnectStatus(true);
        }
      } finally {
        refreshInFlight = false;
        if (pendingRefreshOptions) {
          const nextOptions = pendingRefreshOptions;
          pendingRefreshOptions = null;
          queueMicrotask(() => refresh(nextOptions));
        }
      }
    };
    const logSystem = (message) => fetch("/log-system", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const submitMessage = async ({ overrideMessage = null, overrideTarget = null, raw = rawSendEnabled } = {}) => {
      if (sendLocked || Date.now() - lastSubmitAt < 500) {
        return false;
      }
      sendLocked = true;
      lastSubmitAt = Date.now();
      const message = document.getElementById("message");
      const payload = (overrideMessage ?? message.value).trim();
      const target = overrideTarget ?? selectedTargets.join(",");
      const shortcut = shortcutName(payload);
      const isShortcut = !!shortcut;
      if (!target && shortcut !== "save" && shortcut !== "kill") {
        setStatus("select at least one target", true);
        sendLocked = false;
        return false;
      }
      if (!payload) {
        setStatus("message is required", true);
        sendLocked = false;
        return false;
      }
      setQuickActionsDisabled(true);
      const shortcutDisplay = shortcutLabel(shortcut || payload);
      const shortcutScope = (shortcut === "brief" || shortcut === "interrupt" || shortcut === "restart" || shortcut === "resume" || shortcut === "ctrlc" || shortcut === "enter") && target ? ` for ${target}` : "";
      setStatus(
        isShortcut
          ? `running ${shortcutDisplay}${shortcutScope}...`
          : raw
            ? `sending raw to ${target}...`
            : `sending to ${target}...`
      );
      if (!overrideMessage && useDocumentFlowMobile()) {
        const keyboardWasOpen = isMobileKeyboardOpen();
        dismissMobileKeyboardImmediately(message);
        if (keyboardWasOpen && !mobileSendTriggeredByButton) {
          pendingMobileSendBottomScroll = true;
        } else {
          pendingMobileSendBottomScroll = false;
          scrollConversationToBottom("auto");
        }
      }
      try {
        const deferBottomScrollUntilKeyboardCloses =
          !overrideMessage && useDocumentFlowMobile() && pendingMobileSendBottomScroll;
        const res = await fetch("/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target,
            message: isShortcut ? shortcut : (payload + (!overrideMessage && pendingAttachments.length ? pendingAttachments.map(a => "\n[Attached: " + a.path + "]").join("") : "")),
            ...(raw ? { raw: true } : {}),
            ...((!isShortcut && pendingReplyTo) ? { reply_to: pendingReplyTo.msgId } : {}),
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "send failed");
        }
        if (!overrideMessage) {
          message.value = "";
          if (pendingAttachments.length) {
            pendingAttachments = [];
            const row = document.getElementById("attachPreviewRow");
            if (row) { row.innerHTML = ""; row.style.display = "none"; }
          }
          updateSendBtnVisibility();
          autoResizeTextarea();
          if (useDocumentFlowMobile()) {
            releaseMobileKeyboardOffset();
          } else if (isCompactMobile()) {
            message.blur();
          }
          if (!deferBottomScrollUntilKeyboardCloses) {
            if (useDocumentFlowMobile()) {
              scrollConversationToBottom("auto");
            }
          }
        }
        if (!isShortcut) setReplyTo(null, "", "");
        setStatus(
          isShortcut
            ? `${shortcutDisplay}${shortcutScope} completed`
            : raw
              ? `raw sent to ${target}`
              : `sent to ${target}`
        );
        if (shortcut === "save") {
          await logSystem("Save Log");
          setTimeout(() => setStatus(""), 2000);
        }
        await refresh({ forceScroll: !deferBottomScrollUntilKeyboardCloses });
        return true;
      } catch (error) {
        setStatus(error.message, true);
        return false;
      } finally {
        setQuickActionsDisabled(!sessionActive);
        sendLocked = false;
        mobileSendTriggeredByButton = false;
      }
    };
    document.getElementById("composer").addEventListener("submit", async (event) => {
      event.preventDefault();
      await submitMessage();
    });
    const quickMore = document.querySelector(".quick-more");
    const composerPlusMenu = document.getElementById("composerPlusMenu");
    const closePlusMenu = () => {
      if (composerPlusMenu && composerPlusMenu.open) {
        composerPlusMenu.classList.add("closing");
        setTimeout(() => {
          composerPlusMenu.open = false;
          composerPlusMenu.classList.remove("closing");
        }, 160);
      }
    };
    composerPlusMenu?.querySelector(".composer-plus-toggle")?.addEventListener("mousedown", (e) => e.preventDefault());
    composerPlusMenu?.addEventListener("toggle", () => {
      if (composerPlusMenu.open) closeDrop();
    });
    const headerPlusMenu = document.getElementById("headerPlusMenu");
    const rightMenu = document.getElementById("rightMenu");
    const attachedFilesMenu = document.getElementById("attachedFilesMenu");
    const attachedFilesPanel = document.getElementById("attachedFilesPanel");
    const updateAttachedFilesPanel = (entries) => {
      if (!attachedFilesPanel) return;
      const seen = new Set();
      const files = [];
      for (const entry of (entries || [])) {
        const msg = entry.message || "";
        for (const m of msg.matchAll(/\[Attached:\s*([^\]]+)\]/g)) {
          const path = m[1].trim();
          if (!seen.has(path)) { seen.add(path); files.push(path); }
        }
      }
      let badge = attachedFilesMenu?.querySelector(".attached-files-badge");
      if (attachedFilesMenu) {
        if (files.length > 0) {
          if (!badge) {
            badge = document.createElement("span");
            badge.className = "attached-files-badge";
            attachedFilesMenu.querySelector(".header-plus-toggle")?.appendChild(badge);
          }
          badge.textContent = files.length > 99 ? "99+" : String(files.length);
          badge.hidden = false;
        } else if (badge) {
          badge.hidden = true;
        }
      }
      attachedFilesPanel.innerHTML = "";
      if (!files.length) {
        const empty = document.createElement("div");
        empty.style.cssText = "padding:8px 12px;color:var(--dim);font-size:13px;";
        empty.textContent = "No attached files";
        attachedFilesPanel.appendChild(empty);
        return;
      }
      for (const path of files) {
        const filename = path.split("/").pop() || path;
        const ext = filename.includes(".") ? filename.split(".").pop().toLowerCase() : "";
        const icon = FILE_ICONS[ext] || "📄";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "quick-action";
        btn.title = path;
        btn.innerHTML = `<span class="file-item-icon" aria-hidden="true">${icon}</span><span class="file-item-path">${escapeHtml(filename)}</span>`;
        btn.addEventListener("mousedown", (e) => e.preventDefault());
        btn.addEventListener("click", (e) => {
          if (attachedFilesMenu) attachedFilesMenu.open = false;
          openFileModal(path, ext, btn, e);
        });
        attachedFilesPanel.appendChild(btn);
      }
    };
    let keepHeaderMenuThroughForwardClick = "";
    const closeQuickMore = () => {
      if (quickMore) quickMore.open = isCompactMobile() ? false : true;
      closePlusMenu();
      if (headerPlusMenu) headerPlusMenu.open = false;
      if (rightMenu) rightMenu.open = false;
      if (attachedFilesMenu) attachedFilesMenu.open = false;
    };
    document.addEventListener("click", (event) => {
      if (quickMore && isCompactMobile() && quickMore.open && !quickMore.contains(event.target)) {
        quickMore.open = false;
      }
      if (composerPlusMenu && composerPlusMenu.open && !composerPlusMenu.contains(event.target) && !event.target.closest(".target-chip")) {
        closePlusMenu();
      }
      if (headerPlusMenu && headerPlusMenu.open && !headerPlusMenu.contains(event.target)) {
        if (keepHeaderMenuThroughForwardClick && event.target?.id === keepHeaderMenuThroughForwardClick) {
          keepHeaderMenuThroughForwardClick = "";
          return;
        }
        headerPlusMenu.open = false;
      }
      if (rightMenu && rightMenu.open && !rightMenu.contains(event.target)) {
        rightMenu.open = false;
      }
      if (attachedFilesMenu && attachedFilesMenu.open && !attachedFilesMenu.contains(event.target)) {
        attachedFilesMenu.open = false;
      }
    });    document.querySelectorAll("[data-forward-action]").forEach((node) => {
      node.addEventListener("mousedown", (e) => e.preventDefault());
      node.addEventListener("click", async () => {
        const target = node.dataset.forwardAction || "";
        const keepComposerOpen = !!(composerPlusMenu && composerPlusMenu.contains(node));
        const keepHeaderOpen = !!((headerPlusMenu && headerPlusMenu.contains(node)) || (rightMenu && rightMenu.contains(node)));
        if (keepComposerOpen) flashComposerAction(target);
        if (target === "save" || target === "interrupt" || target === "restart" || target === "resume" || target === "ctrlc" || target === "enter") {
          if (!keepComposerOpen) closeQuickMore();
          await submitMessage({ overrideMessage: target });
          if (keepComposerOpen && composerPlusMenu) {
            requestAnimationFrame(() => { composerPlusMenu.open = true; });
          }
          return;
        }
        if (target === "rawSendBtn") {
          rawSendEnabled = !rawSendEnabled;
          renderRawSendButton();
          if (keepComposerOpen) flashComposerAction(target);
          if (keepHeaderOpen) flashHeaderToggle(target);
          const statusText = rawSendEnabled ? "raw send enabled" : "raw send disabled";
          setStatus(statusText);
          setTimeout(() => {
            if ((document.getElementById("statusline").textContent || "") === statusText) {
              setStatus("");
            }
          }, 1200);
          return;
        }
        if (target === "reloadChat") {
           if (reloadInFlight) return;
           reloadInFlight = true;
           const btn = node;
           btn.disabled = true;
           btn.classList.add("restarting");
           btn.textContent = "Restarting…";
           const previousInstance = currentServerInstance;
           try {
             await fetch("/new-chat", { method: "POST" });
           } catch (_) {}
           const ready = await waitForChatReady(3000, previousInstance);
           if (!ready) {
             navigateToFreshChat();
             return;
           }
           navigateToFreshChat();
           return;
         }
        if (target === "exportBtn") {
          const btn = node;
          const origLabel = btn.querySelector(".action-label")?.textContent;
          if (btn.dataset.exporting) return;
          const userLimit = window.prompt("How many recent chats to export? (0 for all)", "100");
          if (userLimit === null) return;
          const limit = parseInt(userLimit, 10);
          const limitParam = isNaN(limit) ? 100 : limit;
          btn.dataset.exporting = "1";
          if (btn.querySelector(".action-label")) btn.querySelector(".action-label").textContent = "Exporting…";
          try {
            const res = await fetch(`/export?limit=${limitParam}`);
            if (res.ok) {
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = res.headers.get("X-Export-Filename") || "export.html";
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
            } else {
              setStatus("export failed", true);
            }
          } catch (e) {
            setStatus("export error", true);
          } finally {
            delete btn.dataset.exporting;
            if (btn.querySelector(".action-label") && origLabel) btn.querySelector(".action-label").textContent = origLabel;
          }
          return;
        }
        if (target === "openHub") {
          const hubHost = window.location.hostname || "127.0.0.1";
          window.location.href = `${window.location.protocol}//${hubHost}:__HUB_PORT__/`;
          return;
        }
        if (target === "killBtn" && !keepComposerOpen) closeQuickMore();
        if (keepHeaderOpen) {
          keepHeaderMenuThroughForwardClick = target;
          setTimeout(() => {
            if (keepHeaderMenuThroughForwardClick === target) keepHeaderMenuThroughForwardClick = "";
          }, 0);
        }
        if (target !== "rawSendBtn") {
          document.getElementById(target)?.click();
        }
        if (keepComposerOpen && composerPlusMenu) {
          requestAnimationFrame(() => { composerPlusMenu.open = true; });
        }
        if (keepHeaderOpen && headerPlusMenu) {
          requestAnimationFrame(() => { headerPlusMenu.open = true; });
        }
      });
    });
    document.querySelectorAll(".quick-action:not(.memory-btn):not(.brief-btn):not(.raw-send-btn):not(.quick-more-toggle):not([data-forward-action]):not(#cameraBtn), .kill-btn").forEach((node) => {
      node.addEventListener("click", async () => {
        closeQuickMore();
        await submitMessage({ overrideMessage: node.dataset.shortcut || "" });
      });
    });
    document.getElementById("rawSendBtn").addEventListener("click", (e) => {
      if (e.detail > 0) closeQuickMore();
      rawSendEnabled = !rawSendEnabled;
      renderRawSendButton();
      const statusText = rawSendEnabled ? "raw send enabled" : "raw send disabled";
      setStatus(statusText);
      setTimeout(() => {
        if ((document.getElementById("statusline").textContent || "") === statusText) {
          setStatus("");
        }
      }, 1200);
    });
    // Brief button — runs asynchronously, not logged in chat
    document.getElementById("briefBtn").addEventListener("click", async () => {
      const target = selectedTargets.join(",");
      if (!target) {
        setStatus("select target(s) for brief", true);
        setTimeout(() => setStatus(""), 2000);
        return;
      }
      closePlusMenu();
      setStatus(`briefing ${target}...`);
      try {
        await fetch("/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target, message: "brief" }),
        });
        await logSystem(`Send Brief → ${target}`);
        await refresh({ forceScroll: true });
        setStatus("brief sent");
        setTimeout(() => setStatus(""), 2000);
      } catch (_) {
        setStatus("brief failed", true);
        setTimeout(() => setStatus(""), 3000);
      }
    });
    let composing = false;
    const messageInput = document.getElementById("message");
    const sendBtn = document.querySelector(".send-btn");
    const micBtn = document.getElementById("micBtn");

    // Web Speech API setup
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition && micBtn) {
      const recognition = new SpeechRecognition();
      recognition.lang = "ja-JP";
      recognition.continuous = false;
      recognition.interimResults = true;
      let isListening = false;
      let finalTranscript = "";

      micBtn.addEventListener("click", () => {
        if (isListening) {
          recognition.stop();
        } else {
          finalTranscript = messageInput.value;
          try { recognition.start(); } catch (_) {}
        }
      });
      micBtn.addEventListener("touchend", (e) => {
        e.preventDefault();
        micBtn.click();
      }, { passive: false });

      recognition.onstart = () => {
        isListening = true;
        micBtn.classList.add("listening");
      };
      recognition.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        messageInput.value = finalTranscript + interim;
        updateSendBtnVisibility();
        messageInput.dispatchEvent(new Event("input"));
      };
      recognition.onend = () => {
        isListening = false;
        micBtn.classList.remove("listening");
        messageInput.value = finalTranscript;
        updateSendBtnVisibility();
        if (finalTranscript.trim()) {
          setTimeout(() => submitMessage(), 100);
        }
      };
      recognition.onerror = () => {
        isListening = false;
        micBtn.classList.remove("listening");
      };
    } else if (micBtn) {
      micBtn.classList.add("no-speech");
    }

    // Camera / file attach
    const cameraBtn = document.getElementById("cameraBtn");
    const cameraInput = document.getElementById("cameraInput");
    const attachPreviewRow = document.getElementById("attachPreviewRow");
    if (cameraBtn && cameraInput && attachPreviewRow) {
      const addCard = (file, path) => {
        const card = document.createElement("div");
        card.className = "attach-card";
        card.dataset.path = path;
        if (file.type.startsWith("image/")) {
          const img = document.createElement("img");
          img.className = "attach-card-thumb";
          img.src = URL.createObjectURL(file);
          img.alt = file.name;
          card.appendChild(img);
        } else {
          const ext = document.createElement("div");
          ext.className = "attach-card-ext";
          ext.textContent = file.name.split(".").pop().slice(0, 5) || "FILE";
          card.appendChild(ext);
        }
        const rmBtn = document.createElement("button");
        rmBtn.type = "button";
        rmBtn.className = "attach-card-remove";
        rmBtn.setAttribute("aria-label", "Remove");
        rmBtn.textContent = "\u2715";
        rmBtn.addEventListener("click", () => {
          pendingAttachments = pendingAttachments.filter(a => a.path !== path);
          card.remove();
          if (!attachPreviewRow.children.length) attachPreviewRow.style.display = "none";
        });
        card.appendChild(rmBtn);
        attachPreviewRow.appendChild(card);
        attachPreviewRow.style.display = "flex";
      };
      cameraBtn.addEventListener("click", () => { closePlusMenu(); cameraInput.click(); });
      cameraInput.addEventListener("change", async () => {
        const files = Array.from(cameraInput.files);
        if (!files.length) return;
        cameraInput.value = "";
        setStatus(`uploading ${files.length > 1 ? files.length + " files" : files[0].name}...`);
        try {
          await Promise.all(files.map(async (file) => {
            const res = await fetch("/upload", {
              method: "POST",
              headers: { "Content-Type": file.type || "application/octet-stream", "X-Filename": file.name },
              body: file,
            });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.error || "upload failed");
            pendingAttachments.push({ path: data.path, name: file.name });
            addCard(file, data.path);
          }));
          setStatus("");
        } catch (err) {
          setStatus("upload failed: " + err.message, true);
          setTimeout(() => setStatus(""), 3000);
        }
      });
    }

    messageInput.addEventListener("touchstart", (event) => {
      if (!useDocumentFlowMobile() || document.activeElement === messageInput) return;
      event.preventDefault();
      const pos = messageInput.value.length;
      focusMessageInputWithoutScroll(pos, pos);
    }, { passive: false });
    messageInput.addEventListener("mousedown", (event) => {
      if (!useDocumentFlowMobile() || document.activeElement === messageInput) return;
      event.preventDefault();
      const pos = messageInput.value.length;
      focusMessageInputWithoutScroll(pos, pos);
    });
    const updateSendBtnVisibility = () => {
      const hasText = messageInput.value.trim().length > 0;
      if (sendBtn) sendBtn.classList.toggle("visible", hasText);
      if (micBtn) micBtn.classList.toggle("hidden", hasText);
    };
    sendBtn?.addEventListener("touchstart", (event) => {
      if (!useDocumentFlowMobile() || !isMobileKeyboardOpen()) return;
      event.preventDefault();
      mobileSendTriggeredByButton = true;
      pendingMobileSendBottomScroll = false;
      pendingMobileTouchButtonSubmit = true;
      dismissMobileKeyboardImmediately(messageInput);
      scrollConversationToBottom("auto");
    }, { passive: false });
    sendBtn?.addEventListener("mousedown", () => {
      if (!useDocumentFlowMobile() || !isMobileKeyboardOpen()) return;
      mobileSendTriggeredByButton = true;
      pendingMobileSendBottomScroll = false;
      dismissMobileKeyboardImmediately(messageInput);
      scrollConversationToBottom("auto");
    });
    sendBtn?.addEventListener("touchend", (event) => {
      if (!pendingMobileTouchButtonSubmit) return;
      event.preventDefault();
      pendingMobileTouchButtonSubmit = false;
      document.getElementById("composer").requestSubmit();
    }, { passive: false });
    sendBtn?.addEventListener("touchcancel", () => {
      pendingMobileTouchButtonSubmit = false;
    });
    messageInput.addEventListener("input", updateSendBtnVisibility);

    messageInput.addEventListener("keydown", async (event) => {
      if (event.key !== "Enter" || event.shiftKey || composing) {
        return;
      }
      event.preventDefault();
      await submitMessage();
    });
    messageInput.addEventListener("compositionstart", () => {
      composing = true;
    });
    messageInput.addEventListener("compositionend", () => {
      composing = false;
      setTimeout(updateFileAutocomplete, 10);
    });
    messageInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.shiftKey) {
        return;
      }
      if (composing || event.isComposing || event.keyCode === 229) {
        return;
      }
      event.preventDefault();
      document.getElementById("composer").requestSubmit();
    });
    // @-file autocomplete
    let _fileList = null;
    const loadFiles = async () => {
      if (_fileList) return _fileList;
      try {
        const r = await fetch("/files");
        _fileList = r.ok ? await r.json() : [];
      } catch (_) { _fileList = []; }
      return _fileList;
    };
    const fileDrop = document.getElementById("fileDropdown");
    let _dropActiveIdx = -1;
    let _ignoreGlobalClick = false;
    let _dropTimeout = null;
    const _dropItems = () => fileDrop.querySelectorAll(".file-item");
    const closeDrop = () => {
      if (fileDrop.classList.contains("visible")) {
        fileDrop.classList.remove("visible");
        fileDrop.classList.add("closing");
        if (_dropTimeout) clearTimeout(_dropTimeout);
        _dropTimeout = setTimeout(() => {
          if (fileDrop.classList.contains("closing")) {
            fileDrop.style.display = "none";
            fileDrop.classList.remove("closing");
          }
          _dropTimeout = null;
        }, 160);
      } else if (!fileDrop.classList.contains("closing")) {
        fileDrop.style.display = "none";
      }
      _dropActiveIdx = -1;
    };
    const setQuickActionText = (node, label) => {
      if (!node) return;
      const labelNode = node.querySelector(".action-label");
      const mobileNode = node.querySelector(".action-mobile");
      if (labelNode || mobileNode) {
        if (labelNode) labelNode.textContent = label;
        if (mobileNode) mobileNode.textContent = label;
        return;
      }
      node.textContent = label;
    };
    const basename = (path) => {
      const parts = String(path || "").split("/");
      return parts[parts.length - 1] || path;
    };
    const subsequenceScore = (text, query) => {
      let qi = 0;
      let spanStart = -1;
      let lastMatch = -1;
      let gaps = 0;
      for (let i = 0; i < text.length && qi < query.length; i++) {
        if (text[i] !== query[qi]) continue;
        if (spanStart === -1) spanStart = i;
        if (lastMatch !== -1) gaps += i - lastMatch - 1;
        lastMatch = i;
        qi += 1;
      }
      if (qi !== query.length) return null;
      const span = lastMatch - spanStart + 1;
      return { spanStart, span, gaps };
    };
    const scoreFileMatch = (path, rawQuery) => {
      const query = (rawQuery || "").trim().toLowerCase();
      if (!query) return null;
      const full = String(path || "").toLowerCase();
      const base = basename(full);
      const stem = base.replace(/\.[^.]+$/, "");
      const segments = full.split(/[\\/._\\-\\s]+/).filter(Boolean);
      if (base === query) return 1000;
      if (stem === query) return 980;
      if (base.startsWith(query)) return 900 - (base.length - query.length);
      if (stem.startsWith(query)) return 880 - (stem.length - query.length);
      if (segments.includes(query)) return 860;
      const baseIdx = base.indexOf(query);
      if (baseIdx !== -1) return 760 - baseIdx;
      const stemIdx = stem.indexOf(query);
      if (stemIdx !== -1) return 740 - stemIdx;
      const fullIdx = full.indexOf(query);
      if (fullIdx !== -1) return 640 - Math.min(fullIdx, 200);
      const stemSubseq = subsequenceScore(stem, query);
      if (stemSubseq) return 540 - stemSubseq.gaps * 3 - stemSubseq.spanStart * 2 - stemSubseq.span;
      const baseSubseq = subsequenceScore(base, query);
      if (baseSubseq) return 520 - baseSubseq.gaps * 3 - baseSubseq.spanStart * 2 - baseSubseq.span;
      const fullSubseq = subsequenceScore(full, query);
      if (fullSubseq) return 360 - fullSubseq.gaps * 2 - fullSubseq.spanStart - fullSubseq.span;
      return null;
    };
    const findFileMatches = (files, query) => files
      .map((path) => ({ path, score: scoreFileMatch(path, query) }))
      .filter((item) => item.score !== null)
      .sort((a, b) => b.score - a.score || a.path.length - b.path.length || a.path.localeCompare(b.path))
      .slice(0, 30)
      .map((item) => item.path);
    const selectFile = (path) => {
      const ta = messageInput;
      const pos = ta.selectionStart;
      const before = ta.value.slice(0, pos);
      const atIdx = before.lastIndexOf("@");
      if (atIdx === -1) return closeDrop();
      ta.value = ta.value.slice(0, atIdx) + "@" + path + ta.value.slice(pos);
      const newPos = atIdx + 1 + path.length;
      ta.setSelectionRange(newPos, newPos);
      focusMessageInputWithoutScroll(newPos, newPos);
      _ignoreGlobalClick = true; // Prevent global click listener from closing reply banner
      closeDrop();
    };
    fileDrop.addEventListener("click", (e) => e.stopPropagation());
    fileDrop.addEventListener("mousedown", (e) => {
      const item = e.target.closest(".file-item");
      if (item) { e.preventDefault(); selectFile(item.dataset.path); }
    });
    const autoResizeTextarea = () => {
      const baseHeight = 46;
      messageInput.style.height = baseHeight + "px"; // Reset to min-height to get correct scrollHeight
      const scrollH = messageInput.scrollHeight;
      if (scrollH > baseHeight) {
        messageInput.style.height = (scrollH + 2) + "px"; // +2px to avoid tiny scroll jumps
      }
    };
    messageInput.addEventListener("input", () => {
      autoResizeTextarea();
    });
    window.addEventListener("resize", autoResizeTextarea);
    if (window.visualViewport) {
      let viewportUpdateRaf = 0;
      const updateViewportScroll = () => {
        const vv = window.visualViewport;
        const compactMobile = useDocumentFlowMobile();
        const isKeyboardOpen = vv.height < window.innerHeight * 0.9;
        document.body.classList.toggle("keyboard-locked", !compactMobile && isKeyboardOpen);
        syncMobileKeyboardOffset();
        if (compactMobile && pendingMobileSendBottomScroll && !isKeyboardOpen) {
          pendingMobileSendBottomScroll = false;
          scrollConversationToBottom("auto");
        }
        if (isKeyboardOpen && !compactMobile) {
          scrollConversationToBottom("auto");
        }
      };
      const scheduleViewportScrollUpdate = () => {
        if (viewportUpdateRaf) return;
        viewportUpdateRaf = requestAnimationFrame(() => {
          viewportUpdateRaf = 0;
          updateViewportScroll();
        });
      };
      window.visualViewport.addEventListener("resize", scheduleViewportScrollUpdate);
      window.visualViewport.addEventListener("scroll", scheduleViewportScrollUpdate);
      updateViewportScroll();
    }
    // Prevent touch scroll when locked
    timeline.addEventListener("touchmove", (e) => {
      if (!useDocumentFlowMobile() && document.body.classList.contains("keyboard-locked")) {
        e.preventDefault();
      }
    }, { passive: false });

    const updateFileAutocomplete = async () => {
      const pos = messageInput.selectionEnd;
      const val = messageInput.value;
      const before = val.slice(0, pos);
      // Capture '@' followed by any word chars, dots, slashes or dashes until end
      const match = before.match(/@[\w.\/-]*$/);
      
      if (!match) {
        closeDrop();
        return;
      }
      
      const query = match[0].slice(1).toLowerCase();
      const files = await loadFiles();
      const matches = findFileMatches(files, query);
      
      if (!matches.length) {
        closeDrop();
        return;
      }
      
      fileDrop.innerHTML = matches.map(f => {
        const ext = f.split(".").pop().toLowerCase();
        const icon = FILE_ICONS[ext] || "📄";
        return `<div class="file-item" data-path="${escapeHtml(f)}">` +
          `<span class="file-item-icon">${icon}</span>` +
          `<span class="file-item-path">${escapeHtml(f)}</span>` +
          `</div>`;
      }).join("");
      
      _dropActiveIdx = -1;
      const taRect = messageInput.getBoundingClientRect();
      const compRect = document.getElementById("composer").getBoundingClientRect();
      const pickerRect = document.getElementById("targetPicker").getBoundingClientRect();
      const availableSpace = compRect.top - 20;
      
      fileDrop.style.maxHeight = Math.min(240, availableSpace) + "px";
      if (!fileDrop.classList.contains("visible")) {
        if (_dropTimeout) { clearTimeout(_dropTimeout); _dropTimeout = null; }
        fileDrop.classList.remove("closing");
        fileDrop.style.display = "block";
        fileDrop.classList.add("visible");
        closePlusMenu();
      }
      const isPC = window.innerWidth >= 701;
      const dropWidth = isPC ? Math.min(660, taRect.width) : taRect.width;
      fileDrop.style.left = (taRect.left + (taRect.width - dropWidth) / 2) + "px";
      fileDrop.style.bottom = (window.innerHeight - pickerRect.top + (isPC ? 64 : 48)) + "px";
      fileDrop.style.width = dropWidth + "px";
      fileDrop.style.minWidth = "0";
    };

    messageInput.addEventListener("input", updateFileAutocomplete);
    messageInput.addEventListener("click", () => setTimeout(updateFileAutocomplete, 10));
    messageInput.addEventListener("focus", () => {
      updateFileAutocomplete();
      if (isCompactMobile()) document.body.classList.add("composing");
    });
    messageInput.addEventListener("keydown", (e) => {
      if (fileDrop.style.display === "none") return;
      const items = _dropItems();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        items[_dropActiveIdx]?.classList.remove("active");
        _dropActiveIdx = Math.min(_dropActiveIdx + 1, items.length - 1);
        items[_dropActiveIdx]?.classList.add("active");
        items[_dropActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        items[_dropActiveIdx]?.classList.remove("active");
        _dropActiveIdx = Math.max(_dropActiveIdx - 1, 0);
        items[_dropActiveIdx]?.classList.add("active");
        items[_dropActiveIdx]?.scrollIntoView({ block: "nearest" });
      } else if ((e.key === "Enter" || e.key === "Tab") && _dropActiveIdx >= 0) {
        e.preventDefault();
        e.stopImmediatePropagation();
        selectFile(items[_dropActiveIdx].dataset.path);
      } else if (e.key === "Escape") {
        closeDrop();
      }
    }, true);
    messageInput.addEventListener("blur", () => {
      document.body.classList.remove("composing");
      closePlusMenu();
      releaseMobileKeyboardOffset();
      setTimeout(closeDrop, 150);
    });

    const setReplyTo = (msgId, sender, previewText) => {
      const banner = document.getElementById("replyBanner");
      const composerShell = document.querySelector(".composer-shell");
      const composerStack = document.querySelector(".composer-stack");
      if (msgId) {
        pendingReplyTo = { msgId, sender, previewText };
        document.getElementById("replyBannerSender").textContent = sender + ": ";
        document.getElementById("replyBannerPreview").textContent = previewText;
        banner.classList.remove("closing");
        banner.classList.add("visible");
        composerShell?.classList.add("has-reply");
        composerStack?.classList.add("has-reply");
        
        if (availableTargets.includes(sender)) {
          selectedTargets = [sender];
          renderTargetPicker(availableTargets);
        }
        focusMessageInputWithoutScroll();
      } else {
        banner.classList.remove("visible");
        banner.classList.remove("closing");
        pendingReplyTo = null;
        composerShell?.classList.remove("has-reply");
        composerStack?.classList.remove("has-reply");
        document.querySelectorAll(".reply-btn.active").forEach(b => b.classList.remove("active"));
      }
    };
    document.getElementById("replyCancelBtn").addEventListener("mousedown", (e) => e.preventDefault());
    document.getElementById("replyCancelBtn").addEventListener("click", () => {
      setReplyTo(null, "", "");
    });
    const doCopyText = (text) => {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text);
      }
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      try { document.execCommand("copy"); } catch(_) {}
      document.body.removeChild(ta);
      return Promise.resolve();
    };
    const markCopied = (btn) => {
      if (!btn) return;
      if (isCompactMobile() && navigator.vibrate) {
        try { navigator.vibrate(12); } catch (_) {}
      }
      const copyIcon = btn.dataset.copyIcon || btn.innerHTML;
      const checkIcon = btn.dataset.checkIcon || btn.innerHTML;
      const token = String(Date.now() + Math.random());
      btn.dataset.copyAnimToken = token;
      const swapIcon = (nextIcon, keyframes) => {
        const currentSvg = btn.querySelector("svg");
        if (currentSvg && currentSvg.animate) {
          currentSvg.animate(keyframes, { duration: nextIcon === checkIcon ? 70 : 140, easing: "ease", fill: "forwards" });
        }
        setTimeout(() => {
          if (btn.dataset.copyAnimToken !== token) return;
          btn.innerHTML = nextIcon;
          const nextSvg = btn.querySelector("svg");
          if (nextSvg && nextSvg.animate) {
            nextSvg.animate([
              { opacity: 0, transform: "scale(0.82)" },
              { opacity: 1, transform: "scale(1)" }
            ], { duration: nextIcon === checkIcon ? 90 : 160, easing: "cubic-bezier(0.2, 0.9, 0.2, 1)", fill: "forwards" });
          }
        }, nextIcon === checkIcon ? 55 : 120);
      };
      swapIcon(checkIcon, [
        { opacity: 1, transform: "scale(1)" },
        { opacity: 0, transform: "scale(0.82)" }
      ]);
      btn.classList.add("copied");
      setTimeout(() => {
        if (btn.dataset.copyAnimToken !== token) return;
        btn.classList.remove("copied");
        swapIcon(copyIcon, [
          { opacity: 1, transform: "scale(1)" },
          { opacity: 0, transform: "scale(1.08)" }
        ]);
      }, 1500);
    };
    const jumpToReplySource = (targetId) => {
      if (!targetId) return;
      const target = document.querySelector(`[data-msgid="${CSS.escape(targetId)}"]`);
      if (!target) return;
      const bodyTarget = target.querySelector(".md-body") || target.querySelector(".message") || target;
      bodyTarget.scrollIntoView({ behavior: "smooth", block: "center" });
      bodyTarget.classList.remove("msg-highlight");
      void bodyTarget.offsetWidth;
      bodyTarget.classList.add("msg-highlight");
      bodyTarget.addEventListener("animationend", () => bodyTarget.classList.remove("msg-highlight"), { once: true });
    };
    document.getElementById("messages").addEventListener("click", (e) => {
      const fileCard = e.target.closest(".file-card");
      if (fileCard) {
        e.stopPropagation();
        const path = fileCard.dataset.filepath;
        const ext = fileCard.dataset.ext || "";
        openFileModal(path, ext, fileCard, e);
        return;
      }
      const collapseToggle = e.target.closest(".user-collapse-toggle");
      if (collapseToggle) {
        const row = collapseToggle.closest("article.message-row.user");
        const msgId = row?.dataset.msgid || "";
        if (!row || !msgId) return;
        if (expandedUserMessages.has(msgId)) {
          expandedUserMessages.delete(msgId);
        } else {
          expandedUserMessages.add(msgId);
        }
        syncUserMessageCollapse(row);
        return;
      }
      const replyJumpInline = e.target.closest(".reply-jump-inline");
      if (replyJumpInline) {
        replyJumpInline.classList.add("click-flash");
        setTimeout(() => replyJumpInline.classList.remove("click-flash"), 250);
        jumpToReplySource(replyJumpInline.dataset.replyto);
        return;
      }
      const replyTargetJump = e.target.closest(".reply-target-jump-btn");
      if (replyTargetJump) {
        jumpToReplySource(replyTargetJump.dataset.replytarget);
        return;
      }
      const replyBlock = e.target.closest(".reply-preview-block");
      if (replyBlock) {
        return;
      }
      const replyBtn = e.target.closest(".reply-btn");
      if (replyBtn) {
        const msgId = replyBtn.dataset.msgid;
        const sender = replyBtn.dataset.sender;
        const preview = replyBtn.dataset.preview;
        if (pendingReplyTo?.msgId === msgId) {
          setReplyTo(null, "", "");
        } else {
          document.querySelectorAll(".reply-btn.active").forEach(b => b.classList.remove("active"));
          replyBtn.classList.add("active");
          setReplyTo(msgId, sender, preview);
        }
        return;
      }
      const btn = e.target.closest(".copy-btn");
      if (!btn) return;
      const raw = btn.closest(".message-wrap")?.dataset.raw ?? "";
      doCopyText(raw).then(() => {
        markCopied(btn);
      }).catch(() => {});
    });
    document.addEventListener("click", (event) => {
      if (!pendingReplyTo) return;
      if (_ignoreGlobalClick) {
        _ignoreGlobalClick = false;
        return;
      }
      const target = event.target;
      if (
        target.closest(".reply-btn") ||
        target.closest(".reply-banner") ||
        target.closest("#composer") ||
        target.closest("#fileDropdown")
      ) {
        return;
      }
      setReplyTo(null, "", "");
    });
    let currentAgentStatuses = {};
    let agentStatusSince = {};
    let agentTotalThinkingTime = {};
    let thinkingTimeSession = "";
    let lastThinkingSyncAt = 0;
    let lastThinkingSyncPayload = "";
    const collectThinkingTimeTotals = () => {
      const totals = { ...agentTotalThinkingTime };
      const now = Date.now();
      Object.entries(currentAgentStatuses).forEach(([agent, status]) => {
        if (status === "running" && agentStatusSince[agent]) {
          totals[agent] = (totals[agent] || 0) + Math.floor((now - agentStatusSince[agent]) / 1000);
        }
      });
      return totals;
    };
    const syncThinkingTimeToServer = (force = false) => {
      if (!thinkingTimeSession) return;
      const totals = collectThinkingTimeTotals();
      const body = JSON.stringify({ totals });
      const now = Date.now();
      if (!force) {
        if (body === lastThinkingSyncPayload && now - lastThinkingSyncAt < 15000) return;
        if (now - lastThinkingSyncAt < 5000) return;
      }
      lastThinkingSyncPayload = body;
      lastThinkingSyncAt = now;
      if (force && navigator.sendBeacon) {
        try {
          const blob = new Blob([body], { type: "application/json" });
          navigator.sendBeacon("/thinking-time", blob);
          return;
        } catch (_) {}
      }
      fetch("/thinking-time", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      }).catch(() => {});
    };
    const loadThinkingTime = (session) => {
      if (!session || thinkingTimeSession === session) return;
      thinkingTimeSession = session;
      lastThinkingSyncAt = 0;
      lastThinkingSyncPayload = "";
      try {
        const saved = localStorage.getItem(`thinkingTime:${session}`);
        if (saved) agentTotalThinkingTime = JSON.parse(saved);
      } catch(_) {}
      syncThinkingTimeToServer(true);
    };
    const saveThinkingTime = () => {
      if (!thinkingTimeSession) return;
      try {
        const toSave = collectThinkingTimeTotals();
        localStorage.setItem(`thinkingTime:${thinkingTimeSession}`, JSON.stringify(toSave));
      } catch(_) {}
      syncThinkingTimeToServer();
    };
    const formatAgentElapsed = (seconds, short = false) => {
      if (!Number.isFinite(seconds) || seconds < 0) return "";
      if (seconds < 60) return `${seconds}s`;
      const mins = Math.floor(seconds / 60);
      if (short) return `${mins}m`;
      const secs = seconds % 60;
      return `${mins}m ${String(secs).padStart(2, "0")}s`;
    };
    const renderThinkingIndicator = () => {
      const root = document.getElementById("messages");
      if (!root) return;
      const runningAgents = THINKING_AGENT_ORDER.filter((agent) => currentAgentStatuses[agent] === "running");
      const existingRows = Array.from(root.querySelectorAll(".message-thinking-row"));
      if (!root.querySelector("article.message-row") || !runningAgents.length) {
        existingRows.forEach((row) => row.remove());
        document.querySelectorAll(".message-thinking-pane").forEach((node) => node.remove());
        openThinkingPaneAgent = "";
        root.dataset.thinkingAgents = "";
        return;
      }
      const nextThinkingAgents = runningAgents.join(",");
      if (root.dataset.thinkingAgents === nextThinkingAgents && existingRows.length === runningAgents.length) {
        return;
      }
      document.querySelectorAll(".message-thinking-pane").forEach((node) => node.remove());
      existingRows.forEach((row) => row.remove());
      const frag = document.createDocumentFragment();
      const THINKING_TEXT = "thinking...";
      const charSpans = [...THINKING_TEXT].map((ch, i) =>
        `<span class="thinking-char" style="--char-i:${i}">${ch}</span>`
      ).join("");
      runningAgents.forEach((agent) => {
        const row = document.createElement("div");
        row.className = "message-thinking-row";
        row.dataset.agent = agent;
        row.innerHTML = `
          <span class="message-thinking-icons">
            <span class="message-thinking-icon-wrap">
              <span class="message-thinking-glow message-thinking-glow--${agent}"></span>
              ${thinkingIconImg(agent, `message-thinking-icon message-thinking-icon--${agent}`)}
            </span>
          </span>
          <span class="message-thinking-label">${charSpans}</span>
          <button class="thinking-expand-btn" type="button" aria-label="ペインを開く" tabindex="-1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
        `;
        frag.appendChild(row);
      });
      root.appendChild(frag);
      root.dataset.thinkingAgents = nextThinkingAgents;
      if (openThinkingPaneAgent && runningAgents.includes(openThinkingPaneAgent)) {
        const activeRow = root.querySelector(`.message-thinking-row[data-agent="${CSS.escape(openThinkingPaneAgent)}"]`);
        if (activeRow) {
          activeRow.classList.add("pane-open");
          const paneBody = mountThinkingTracePane(activeRow, openThinkingPaneAgent);
          currentTraceTarget = paneBody;
          currentHoverAgent = openThinkingPaneAgent;
          const cached = traceCache.get(openThinkingPaneAgent);
          if (cached) {
            renderTraceContent(cached);
          } else {
            renderTraceContent("Loading trace...");
            fetchAndRenderTrace(openThinkingPaneAgent);
          }
        }
      }
    };
    const syncUserMessageCollapse = (scope = document) => {
      const rows = scope?.matches?.("article.message-row.user")
        ? [scope]
        : Array.from(scope.querySelectorAll("article.message-row.user"));
      rows.forEach((row) => {
        const bodyRow = row.querySelector(".message-body-row");
        const body = row.querySelector(".md-body");
        const toggle = row.querySelector(".user-collapse-toggle");
        if (!bodyRow || !body || !toggle) return;
        const style = getComputedStyle(body);
        const lineHeight = Number.parseFloat(style.lineHeight);
        const paddingTop = Number.parseFloat(style.paddingTop) || 0;
        const paddingBottom = Number.parseFloat(style.paddingBottom) || 0;
        const maxHeight = Number.isFinite(lineHeight)
          ? Math.ceil((lineHeight * 10) + paddingTop + paddingBottom)
          : 245;
        bodyRow.style.setProperty("--user-collapse-max-height", `${maxHeight}px`);
        const shouldCollapse = body.scrollHeight > (maxHeight + 4);
        const msgId = row.dataset.msgid || "";
        const isExpanded = shouldCollapse && msgId && expandedUserMessages.has(msgId);
        row.classList.toggle("is-collapsible", shouldCollapse);
        bodyRow.classList.toggle("is-collapsed", shouldCollapse && !isExpanded);
        toggle.classList.toggle("is-visible", shouldCollapse);
        toggle.hidden = !shouldCollapse;
        toggle.textContent = isExpanded ? "Less" : "More";
      });
    };
    const renderAgentStatus = (statuses) => {
      const now = Date.now();
      Object.entries(statuses).forEach(([agent, status]) => {
        const prev = currentAgentStatuses[agent];
        if (prev !== status) {
          if (prev === "running" && agentStatusSince[agent]) {
            agentTotalThinkingTime[agent] = (agentTotalThinkingTime[agent] || 0) +
              Math.floor((now - agentStatusSince[agent]) / 1000);
            saveThinkingTime();
          }
          agentStatusSince[agent] = now;
        }
      });
      currentAgentStatuses = { ...statuses };
      renderThinkingIndicator();
    };
    const refreshAgentStatus = async () => {
      try {
        const res = await fetch(`/agents?ts=${Date.now()}`, { cache: "no-store" });
        if (res.ok) renderAgentStatus(await res.json());
      } catch (_) {}
    };
    const traceTooltip = document.getElementById("traceTooltip");
    let currentHoverAgent = null;
    let traceOpenedByThinkingRow = false;
    let ansiUp = null;
    try { ansiUp = new AnsiUp(); } catch(e) {}
    const isCompactMobile = () => window.matchMedia("(max-width: 359px)").matches;
    const hoverCapabilityMedia = window.matchMedia("(hover: hover) and (pointer: fine)");
    const canUseHoverInteractions = () => hoverCapabilityMedia.matches;
    const touchBlurSelector = [
      ".quick-action",
      ".header-plus-toggle",
      ".composer-plus-toggle",
      ".target-chip",
      ".copy-btn",
      ".reply-btn",
      ".reply-cancel-btn",
      ".reply-jump-inline",
      ".file-card",
      ".file-modal-close",
      ".filter-chip",
      ".send-btn",
      "#scrollToBottomBtn"
    ].join(", ");
    const syncHoverCapabilityClass = () => {
      document.documentElement.classList.toggle("has-hover", canUseHoverInteractions());
    };
    const blurTouchControlAfterTap = (event) => {
      if (canUseHoverInteractions()) return;
      const control = event.target?.closest?.(touchBlurSelector);
      if (!control) return;
      setTimeout(() => {
        if (typeof control.blur === "function") control.blur();
        const active = document.activeElement;
        if (active && active.matches?.(touchBlurSelector) && typeof active.blur === "function") {
          active.blur();
        }
      }, 0);
    };
    syncHoverCapabilityClass();
    if (hoverCapabilityMedia.addEventListener) {
      hoverCapabilityMedia.addEventListener("change", syncHoverCapabilityClass);
    } else if (hoverCapabilityMedia.addListener) {
      hoverCapabilityMedia.addListener(syncHoverCapabilityClass);
    }
    // On PC, force quick-more open so buttons are always visible (details UA hides children when closed)
    if (!isCompactMobile() && quickMore) {
      quickMore.open = true;
      const qmSummary = quickMore.querySelector("summary");
      if (qmSummary) qmSummary.addEventListener("click", (e) => { if (!isCompactMobile()) e.preventDefault(); });
    }
    if (isCompactMobile()) {
      const sub = document.querySelector(".sub");
      const kill = document.getElementById("killBtn");
      if (sub && kill) {
        sub.appendChild(kill); // ensure kill is last child
        kill.style.marginLeft = "auto";
        kill.style.flexShrink = "0";
      }
    }
    const soundBtn = document.getElementById("soundBtn");
    const setSoundBtn = (on, flash = false) => {
      soundEnabled = on;
      try { localStorage.setItem("soundEnabled", on ? "1" : "0"); } catch(_) {}
      const txt = isCompactMobile() ? (on ? "♪on" : "♪off") : (on ? "Sound: on" : "Sound: off");
      soundBtn.textContent = txt;
      soundBtn.classList.toggle("sound-on", on);
      soundBtn.classList.toggle("sound-off", !on);
      document.querySelectorAll('[data-forward-action="soundBtn"]').forEach(n => {
        n.classList.toggle("sound-on", on);
        n.classList.toggle("sound-off", !on);
        setQuickActionText(n, "Sound");
      });
      if (flash) flashHeaderToggle("soundBtn");
    };
    setSoundBtn(soundEnabled);
    soundBtn.addEventListener("click", async () => {
      const newState = !soundEnabled;
      setSoundBtn(newState, true);
      await primeSound(); // always prime on click (iOS unlock)
    });
    // TTS (Read Aloud)
    const ttsBtn = document.getElementById("ttsBtn");
    let ttsEnabled = (() => { try { return localStorage.getItem("ttsEnabled") === "1"; } catch(_) { return false; } })();
    const hasTTS = typeof window.speechSynthesis !== "undefined";
    const setTtsBtn = (on, flash = false) => {
      ttsEnabled = on;
      try { localStorage.setItem("ttsEnabled", on ? "1" : "0"); } catch(_) {}
      const txt = isCompactMobile() ? (on ? "Read:on" : "Read:off") : (on ? "Read: on" : "Read: off");
      ttsBtn.textContent = txt;
      ttsBtn.classList.toggle("tts-on", on);
      ttsBtn.classList.toggle("tts-off", !on);
      document.querySelectorAll('[data-forward-action="ttsBtn"]').forEach(n => {
        n.classList.toggle("tts-on", on);
        n.classList.toggle("tts-off", !on);
        setQuickActionText(n, "Read");
      });
      if (flash) flashHeaderToggle("ttsBtn");
    };
    if (!hasTTS && ttsBtn) ttsBtn.style.display = "none";
    // TTS queue — iOS Safari only allows speak() from user-gesture or utterance.onend chains
    let _ttsQueue = [];
    let _ttsSpeaking = false;
    let _ttsLastSpokenLenMap = new Map(); // msg_id -> last spoken length
    let _ttsHeartbeatTimer = null;

    const _ttsGetBestVoice = () => {
      const voices = window.speechSynthesis.getVoices();
      return voices.find(v => v.lang.startsWith("ja") && (v.name.includes("Siri") || v.name.includes("Kyoko")))
             || voices.find(v => v.lang.startsWith("ja")) 
             || null;
    };

    const _ttsNext = () => {
      if (!hasTTS || !ttsEnabled) { 
        _ttsSpeaking = false; 
        if (_ttsHeartbeatTimer) clearTimeout(_ttsHeartbeatTimer);
        return; 
      }
      if (_ttsQueue.length === 0) {
        _ttsSpeaking = false;
        // Keep the chain "warm" on iOS by speaking a tiny silence every few seconds
        // This is hacky but helps prevent the activation from expiring too quickly.
        if (_ttsHeartbeatTimer) clearTimeout(_ttsHeartbeatTimer);
        _ttsHeartbeatTimer = setTimeout(() => {
          if (ttsEnabled && !_ttsSpeaking && _ttsQueue.length === 0) {
            const heartbeat = new SpeechSynthesisUtterance(" ");
            heartbeat.volume = 0;
            heartbeat.voice = _ttsGetBestVoice();
            heartbeat.onend = () => _ttsNext();
            heartbeat.onerror = () => { _ttsSpeaking = false; };
            _ttsSpeaking = true;
            window.speechSynthesis.speak(heartbeat);
          }
        }, 5000);
        return;
      }
      if (_ttsHeartbeatTimer) clearTimeout(_ttsHeartbeatTimer);
      const text = _ttsQueue.shift();
      _ttsSpeaking = true;
      const utt = new SpeechSynthesisUtterance(text);
      utt.lang = "ja-JP";
      utt.rate = 1.5;
      utt.pitch = 1.3;
      utt.voice = _ttsGetBestVoice();
      utt.onend = () => _ttsNext();
      utt.onerror = () => { _ttsSpeaking = false; _ttsNext(); };
      window.speechSynthesis.speak(utt);
    };
    if (hasTTS) {
      setTtsBtn(ttsEnabled);
      ttsBtn.addEventListener("click", () => {
        const newState = !ttsEnabled;
        setTtsBtn(newState, true);
        if (newState) {
          // Prime TTS chain from user gesture (iOS Safari requirement)
          _ttsQueue = [];
          _ttsSpeaking = true;
          const primer = new SpeechSynthesisUtterance("読み上げを有効にしました");
          primer.lang = "ja-JP";
          primer.rate = 1.5;
          primer.pitch = 1.3;
          primer.voice = _ttsGetBestVoice();
          primer.onend = () => _ttsNext();          primer.onerror = () => { _ttsSpeaking = false; };
          window.speechSynthesis.speak(primer);
        } else {
          window.speechSynthesis.cancel();
          _ttsQueue = [];
          _ttsSpeaking = false;
          if (_ttsHeartbeatTimer) clearTimeout(_ttsHeartbeatTimer);
        }
      });
    }
    const speakEntry = (entry) => {
      if (!hasTTS || !ttsEnabled) return;
      if (entry.sender === "user" || entry.sender === "system") return;
      const msgId = entry.msg_id;
      if (!msgId) return;
      
      const raw = (entry.message || "").replace(/\[Attached:[^\]]*\]/g, "").trim();
      if (!raw) return;
      
      const lastLen = _ttsLastSpokenLenMap.get(msgId) || 0;
      if (raw.length <= lastLen) return;
      
      // Get the new part of the message
      const newPart = raw.substring(lastLen).trim();
      if (newPart) {
        _ttsQueue.push(newPart.slice(0, 500));
        _ttsLastSpokenLenMap.set(msgId, raw.length);
        if (!_ttsSpeaking) _ttsNext();
      }
    };

    // Auto-prime on first user gesture if sound is on
    const primeSoundOnGesture = async () => {
      if (!soundEnabled || _audioPrimed) return;
      await primeSound();
    };
    document.addEventListener("pointerdown", (e) => {
      const toggle = e.target.closest(".header-plus-toggle, .composer-plus-toggle, .quick-action");
      if (toggle) {
        if (toggle.classList.contains("animating")) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        flashHeaderToggle(toggle);
      }
    });
    document.addEventListener("touchstart", primeSoundOnGesture, { passive: true });
    document.addEventListener("click", primeSoundOnGesture);
    document.addEventListener("click", blurTouchControlAfterTap, true);
    const setActiveAgentRow = (row) => {
      document.querySelectorAll(".agent-row.active").forEach((node) => node.classList.remove("active"));
      if (row) row.classList.add("active");
    };
    const normalizeTraceAnsi = (value) => value
      .replace(/\u001b\[2m/g, "\u001b[38;2;98;101;109m")
      .replace(/\u001b\[(?:0;)?37m/g, "\u001b[38;2;138;142;148m")
      .replace(/\u001b\[(?:0;)?97m/g, "\u001b[38;2;162;166;172m")
      .replace(/\u001b\[(?:0;)?22m/g, "\u001b[39m");
    const normalizeTraceHtmlColors = (target) => {
      if (!target) return;
      const nodes = [target, ...target.querySelectorAll("*")];
      nodes.forEach((node) => {
        const color = window.getComputedStyle(node).color || "";
        const match = color.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
        if (!match) return;
        const [r, g, b] = match.slice(1).map((value) => Number.parseInt(value, 10));
        const luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b);
        if (Number.isFinite(luminance) && luminance >= 150) {
          node.style.color = "rgb(136, 140, 146)";
        }
      });
    };

    const renderTraceContentInto = (target, content) => {
      if (!target) return;
      if (ansiUp) {
        target.innerHTML = ansiUp.ansi_to_html(content);
        normalizeTraceHtmlColors(target);
      } else {
        target.textContent = content;
      }
    };
    const renderTraceContent = (content) => {
      renderTraceContentInto(currentTraceTarget || traceTooltip, content);
    };
    const fetchAndRenderTrace = async (agent) => {
      if (traceFetchInFlight || currentHoverAgent !== agent) return;
      traceFetchInFlight = true;
      try {
        const res = await fetch(`/trace?agent=${encodeURIComponent(agent)}&ts=${Date.now()}`);
        if (!res.ok) throw new Error("fetch failed");
        const data = await res.json();
        if (currentHoverAgent !== agent) return;
        const content = normalizeTraceAnsi(data.content || "No output");
        traceCache.set(agent, content);
        renderTraceContent(content);
      } catch (err) {
        if (currentHoverAgent === agent) {
          const cached = traceCache.get(agent);
          if (cached) {
            renderTraceContent(cached);
          } else {
            renderTraceContent("Trace unavailable");
          }
        }
      } finally {
        traceFetchInFlight = false;
      }
    };

    const showTraceTooltip = (agent, rect) => {
      currentHoverAgent = agent;
      currentTraceTarget = traceTooltip;
      traceTooltip.style.display = "block";
      const cached = traceCache.get(agent);
      if (cached) {
        renderTraceContent(cached);
      } else {
        traceTooltip.textContent = "Loading trace...";
      }
      if (isCompactMobile()) {
        const left = 8;
        const centerX = rect.left + rect.width / 2;
        traceTooltip.style.left = left + "px";
        traceTooltip.style.right = "8px";
        traceTooltip.style.width = "calc(100vw - 16px)";
        traceTooltip.style.maxWidth = "calc(100vw - 16px)";
        traceTooltip.style.top = Math.min(window.innerHeight - 250, rect.bottom + 20) + "px";
        traceTooltip.style.setProperty("--tail-x", (centerX - left) + "px");
      } else {
        traceTooltip.style.left = "50%";
        traceTooltip.style.right = "";
        traceTooltip.style.width = "auto";
        traceTooltip.style.maxWidth = "min(1000px, calc(100vw - 32px))";
        traceTooltip.style.top = Math.min(window.innerHeight - 250, rect.bottom + 20) + "px";
        traceTooltip.style.transform = "translateX(-50%)";
        traceTooltip.style.setProperty("--tail-x", "50%");
      }
      fetchAndRenderTrace(agent);
    };

  const hideTraceTooltip = () => {
    currentHoverAgent = null;
    traceOpenedByThinkingRow = false;
    openThinkingPaneAgent = "";
    currentTraceTarget = null;
    document.querySelectorAll(".message-thinking-row.pane-open").forEach(r => r.classList.remove("pane-open"));
    document.querySelectorAll(".message-thinking-pane").forEach((node) => node.remove());
    traceTooltip.style.display = "none";
    traceTooltip.innerHTML = "";
    traceTooltip.style.left = "";
    traceTooltip.style.right = "";
    traceTooltip.style.width = "";
    traceTooltip.style.top = "";
    traceTooltip.style.bottom = "";
    traceTooltip.style.background = "";
    traceTooltip.style.maxWidth = "";
    traceTooltip.style.maxHeight = "";
    traceTooltip.style.overflow = "";
    traceTooltip.style.pointerEvents = "";
    traceTooltip.style.transform = "";
    setActiveAgentRow(null);
  };

    setInterval(() => {
      if (currentHoverAgent) {
        fetchAndRenderTrace(currentHoverAgent);
      }
    }, 1000);

    document.addEventListener("click", (e) => {
      if (!currentHoverAgent) return;
      if (e.target.closest(".message-thinking-row") || e.target.closest(".message-thinking-pane") || e.target.closest("#traceTooltip")) return;
      hideTraceTooltip();
    });

    const clearThinkingPaneOpen = () => {
      document.querySelectorAll(".message-thinking-row.pane-open").forEach(r => r.classList.remove("pane-open"));
      document.querySelectorAll(".message-thinking-pane").forEach((node) => node.remove());
      openThinkingPaneAgent = "";
    };
    const mountThinkingTracePane = (row, agent) => {
      if (!row || !agent) return null;
      const pane = document.createElement("div");
      pane.className = "message-thinking-pane";
      pane.dataset.agent = agent;
      pane.innerHTML = `<div class="message-thinking-pane-body">Loading trace...</div>`;
      row.insertAdjacentElement("afterend", pane);
      return pane.querySelector(".message-thinking-pane-body");
    };
    const showThinkingTrace = (agent, row) => {
      clearThinkingPaneOpen();
      if (row) row.classList.add("pane-open");
      traceOpenedByThinkingRow = true;
      currentHoverAgent = agent;
      openThinkingPaneAgent = agent;
      traceTooltip.style.display = "none";
      const paneBody = mountThinkingTracePane(row, agent);
      currentTraceTarget = paneBody;
      const cached = traceCache.get(agent);
      if (cached) {
        renderTraceContent(cached);
      } else {
        renderTraceContent("Loading trace...");
      }
      fetchAndRenderTrace(agent);
    };

    document.getElementById("messages").addEventListener("click", (e) => {
      const row = e.target.closest(".message-thinking-row");
      if (!row) return;
      const agent = row.dataset.agent;
      if (!agent) return;
      if (traceOpenedByThinkingRow && currentHoverAgent === agent) {
        clearThinkingPaneOpen();
        hideTraceTooltip();
        return;
      }
      showThinkingTrace(agent, row);
    });

    refreshAgentStatus();
    setInterval(refreshAgentStatus, 1500);
    setInterval(() => {
      if (Object.keys(currentAgentStatuses).length) {
        renderAgentStatus(currentAgentStatuses);
        if (THINKING_AGENT_ORDER.some((agent) => currentAgentStatuses[agent] === "running") || Object.keys(agentTotalThinkingTime).length) {
          saveThinkingTime();
        }
      }
    }, 1000);
    window.addEventListener("pagehide", () => {
      if (Object.keys(agentTotalThinkingTime).length || Object.keys(currentAgentStatuses).length) {
        saveThinkingTime();
        syncThinkingTimeToServer(true);
      }
    });

    // Auto-mode button
    const autoBtn = document.getElementById("autoModeBtn");
    const setAutoBtn = (active, flash = false) => {
      const txt = isCompactMobile() ? "Auto" : (active ? "Auto: on" : "Auto: off");
      autoBtn.textContent = txt;
      autoBtn.classList.toggle("auto-on", active);
      autoBtn.classList.toggle("auto-off", !active);
      document.querySelectorAll('[data-forward-action="autoModeBtn"]').forEach(n => {
        n.classList.toggle("auto-on", active);
        n.classList.toggle("auto-off", !active);
        setQuickActionText(n, "Auto");
      });
      if (flash) flashHeaderToggle("autoModeBtn");
    };
    let lastApprovalTs = 0;
    const showAutoApprovalNotice = (agent) => {
      const chip = agent
        ? document.querySelector(`.target-chip[data-target="${CSS.escape(agent)}"]`)
        : null;
      if (!chip) return;
      document.querySelectorAll(".target-chip.auto-approval-notice").forEach((node) => {
        if (node._autoApprovalNoticeHideTimer) clearTimeout(node._autoApprovalNoticeHideTimer);
        if (node._autoApprovalNoticeCleanupTimer) clearTimeout(node._autoApprovalNoticeCleanupTimer);
        node.classList.remove("auto-approval-notice-visible");
        node.classList.remove("auto-approval-notice");
      });
      chip.classList.add("auto-approval-notice");
      void chip.offsetWidth;
      chip.classList.add("auto-approval-notice-visible");
      chip._autoApprovalNoticeHideTimer = setTimeout(() => {
        chip.classList.remove("auto-approval-notice-visible");
        chip._autoApprovalNoticeCleanupTimer = setTimeout(() => {
          chip.classList.remove("auto-approval-notice");
          chip._autoApprovalNoticeCleanupTimer = null;
          chip._autoApprovalNoticeHideTimer = null;
        }, 220);
      }, 1600);
    };
    const refreshAutoMode = async () => {
      try {
        const res = await fetch("/auto-mode", { cache: "no-store" });
        if (!res.ok) return;
        const d = await res.json();
        setAutoBtn(d.active);
        if (d.last_approval && d.last_approval !== lastApprovalTs) {
          if (lastApprovalTs !== 0) showAutoApprovalNotice(d.last_approval_agent || "");
          lastApprovalTs = d.last_approval;
        }
      } catch (_) {}
    };
    autoBtn.addEventListener("click", async () => {
      try {
        const res = await fetch("/auto-mode", { method: "POST" });
        if (res.ok) { const d = await res.json(); setAutoBtn(d.active, true); }
      } catch (_) {}
    });
    refreshAutoMode();
    setInterval(refreshAutoMode, 3000);

    const caffeinateBtn = document.getElementById("caffeinateBtn");
    const setCaffeinateBtn = (active, flash = false) => {
      const txt = isCompactMobile() ? "Awake" : (active ? "Awake: on" : "Awake: off");
      caffeinateBtn.textContent = txt;
      caffeinateBtn.classList.toggle("awake-on", active);
      caffeinateBtn.classList.toggle("awake-off", !active);
      document.querySelectorAll('[data-forward-action="caffeinateBtn"]').forEach(n => {
        n.classList.toggle("awake-on", active);
        n.classList.toggle("awake-off", !active);
        setQuickActionText(n, "Awake");
      });
      if (flash) flashHeaderToggle("caffeinateBtn");
    };
    const refreshCaffeinate = async () => {
      try {
        const res = await fetch("/caffeinate", { cache: "no-store" });
        if (res.ok) { const d = await res.json(); setCaffeinateBtn(d.active); }
      } catch (_) {}
    };
    caffeinateBtn.addEventListener("click", async () => {
      try {
        const res = await fetch("/caffeinate", { method: "POST" });
        if (res.ok) { const d = await res.json(); setCaffeinateBtn(d.active, true); }
      } catch (_) {}
    });
    refreshCaffeinate();
    setInterval(refreshCaffeinate, 5000);

    // Memory button — sends silently (not logged in chat)
    document.getElementById("memoryBtn").addEventListener("click", async () => {
      closeQuickMore();
      const targets = selectedTargets.length > 0 ? selectedTargets : [];
      if (!targets.length) {
        setStatus("select at least one target", true);
        setTimeout(() => setStatus(""), 2000);
        return;
      }
      setStatus(`sending memory instruction to ${targets.join(",")}...`);
      try {
        for (const target of targets) {
          const res = await fetch(`/memory-path?agent=${encodeURIComponent(target)}`);
          if (!res.ok) continue;
          const { path } = await res.json();
          const instruction = `Please update your session memory file at: ${path}\n\nDo not ask for clarification. Read the existing content if the file exists, rewrite it with key context from this conversation: important facts, user preferences, decisions made, and work in progress. Max 100 lines. Do NOT save memory on your own — only save when explicitly instructed by the user (i.e. when this message is sent).\nAfter saving, run: printf '%s' 'Memory saved' | agent-send --stdin user`;
          await fetch("/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target, message: instruction, silent: true }),
          });
          await new Promise(r => setTimeout(r, 600));
        }
        await logSystem(`Save Memory → ${targets.join(",")}`);
        await refresh({ forceScroll: true });
        setStatus("memory instruction sent");
        setTimeout(() => setStatus(""), 3000);
      } catch (_) {
        setStatus("memory instruction failed", true);
        setTimeout(() => setStatus(""), 3000);
      }
    });

    // Read Memory button — sends memory content to agent silently
    document.getElementById("readMemoryBtn").addEventListener("click", async () => {
      closeQuickMore();
      const targets = selectedTargets.length > 0 ? selectedTargets : [];
      if (!targets.length) {
        setStatus("select at least one target", true);
        setTimeout(() => setStatus(""), 2000);
        return;
      }
      setStatus(`sending memory to ${targets.join(",")}...`);
      try {
        for (const target of targets) {
          const res = await fetch(`/memory-path?agent=${encodeURIComponent(target)}`);
          if (!res.ok) continue;
          const { path, content } = await res.json();
          if (!content) {
            setStatus(`no memory file for ${target}`, true);
            setTimeout(() => setStatus(""), 3000);
            continue;
          }
          const instruction = `Please read your session memory below and internalize it.\n\nFile: ${path}\n\n${content}\n\nAfter reading, run: printf '%s' 'Memory loaded' | agent-send --stdin user`;
          await fetch("/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target, message: instruction, silent: true }),
          });
          await new Promise(r => setTimeout(r, 600));
        }
        await logSystem(`Load Memory → ${targets.join(",")}`);
        await refresh({ forceScroll: true });
        setStatus("memory sent to agent");
        setTimeout(() => setStatus(""), 3000);
      } catch (_) {
        setStatus("read memory failed", true);
        setTimeout(() => setStatus(""), 3000);
      }
    });

    document.getElementById("searchInput").addEventListener("input", e => {
      filterKeyword = e.target.value;
      applyFilter();
    });

    renderRawSendButton();
    if (window.__STATIC_EXPORT__) {
      const comp = document.getElementById("composer");
      if (comp) comp.style.display = "none";
      document.querySelector("header")?.querySelectorAll("button, details")?.forEach(el => { el.disabled = true; el.style.pointerEvents = "none"; });
    }
    refresh({ forceScroll: true });
    if (followMode && !window.__STATIC_EXPORT__) {
      setInterval(refresh, 250);
    }
  </script>
</body>
</html>
"""


def render_chat_html(*, icon_data_uris, server_instance, hub_port, chat_settings, agent_font_mode_inline_style, follow):
    return (
        CHAT_HTML
        .replace("__ICON_DATA_URIS__", json.dumps(icon_data_uris, ensure_ascii=True))
        .replace("__SERVER_INSTANCE__", server_instance)
        .replace("__HUB_PORT__", str(hub_port))
        .replace("__CHAT_THEME__", chat_settings["theme"])
        .replace("__AGENT_FONT_MODE__", chat_settings["agent_font_mode"])
        .replace("__AGENT_FONT_MODE_INLINE_STYLE__", agent_font_mode_inline_style(chat_settings["agent_font_mode"]))
        .replace("__MOBILE_MESSAGE_LIMIT__", str(chat_settings["mobile_message_limit"]))
        .replace("__DESKTOP_MESSAGE_LIMIT__", str(chat_settings["desktop_message_limit"]))
        .replace("mode: snapshot", f"mode: {'follow' if follow == '1' else 'snapshot'}")
    )
