from __future__ import annotations

import json

from .hub_header_assets import HUB_PAGE_HEADER_CSS, render_hub_page_header

CHAT_HTML = r"""<!doctype html>
<html lang="en" data-theme="__CHAT_THEME__"__STARFIELD_ATTR__>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="rgb(38, 38, 36)">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="agent-index chat">
  <link rel="manifest" href="__CHAT_BASE_PATH__/app.webmanifest">
  <title>agent-index chat</title>
  <script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/ansi_up@5.1.0/ansi_up.min.js"></script>
  <style>
    @font-face {
      font-family: "anthropicSerif";
      src: url("__CHAT_BASE_PATH__/font/anthropic-serif-roman.ttf") format("truetype");
      font-style: normal;
      font-weight: 300 800;
      font-display: swap;
    }
    @font-face {
      font-family: "anthropicSerif";
      src: url("__CHAT_BASE_PATH__/font/anthropic-serif-italic.ttf") format("truetype");
      font-style: italic;
      font-weight: 300 800;
      font-display: swap;
    }
    @font-face {
      font-family: "anthropicSans";
      src: url("__CHAT_BASE_PATH__/font/anthropic-sans-roman.ttf") format("truetype");
      font-style: normal;
      font-weight: 300 800;
      font-display: swap;
    }
    @font-face {
      font-family: "anthropicSans";
      src: url("__CHAT_BASE_PATH__/font/anthropic-sans-italic.ttf") format("truetype");
      font-style: italic;
      font-weight: 300 800;
      font-display: swap;
    }
    @font-face {
      font-family: "jetbrainsMono";
      src: local("JetBrains Mono"),
           local("JetBrainsMono-Regular"),
           url("__CHAT_BASE_PATH__/font/jetbrains-mono.ttf") format("truetype-variations"),
           url("__CHAT_BASE_PATH__/font/jetbrains-mono.ttf") format("truetype");
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
      background: rgba(var(--bg-rgb), 0.69);
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
      max-height: min(360px, 45vh);
      overflow-y: auto;
      animation: paneReveal 450ms cubic-bezier(0.175, 0.885, 0.32, 1.2) forwards;
      transform-origin: top center;
      will-change: opacity, filter;
    }
    :root, [data-theme="default"], [data-theme="claude"] {
      color-scheme: dark;
      --bg-rgb: 38, 38, 36;
      --bg: rgb(var(--bg-rgb));
      --panel: rgba(0, 0, 0, 0.96);
      --panel-strong: rgba(0, 0, 0, 0.98);
      --line: rgba(255, 255, 255, 0.08);
      --line-strong: rgba(255, 255, 255, 0.13);
      --text: #d7dde5;
      --muted: #88919b;
      --chrome-muted: rgb(158, 158, 158);
      --chip-border-idle: rgba(255, 255, 255, 0.12);
      --chip-border-active: rgba(255, 255, 255, 0.18);
      --chip-border-pressed: rgba(255, 255, 255, 0.24);
      --math-display-inline-pad: 2px;
      --viewport-center-gutter: clamp(12px, 3vw, 28px);
      --user-accent: #b7c2d0;
      --claude-accent: #b7c2d0;
      --codex-accent: #b7c2d0;
      --gemini-accent: #b7c2d0;
      --copilot-accent: #b7c2d0;
      --system-accent: #6a7078;
      --inline-code-fg: rgb(254, 129, 129);
      --inline-code-bg: rgb(46, 46, 43);
      --inline-code-border: rgb(73, 73, 68);
      --inline-code-radius: 4px;
      --inline-code-pad-y: 3px;
      --inline-code-pad-x: 5px;
      --latest-message-offset: 34vh;
    }
    .shell > .hub-page-header {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      z-index: 100;
      overflow: visible;
      background: rgba(var(--bg-rgb, 38, 38, 36), 0.42);
      backdrop-filter: blur(28px) saturate(190%);
      -webkit-backdrop-filter: blur(28px) saturate(190%);
    }
    .shell > .hub-page-header > .hub-page-menu-panel {
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      z-index: 140;
      max-height: 0;
      overflow: hidden;
      border-top: 0.5px solid transparent;
      background: rgb(var(--bg-rgb));
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      opacity: 0;
      transform: translateY(-6px);
      pointer-events: none;
      transition:
        max-height 300ms cubic-bezier(0.2, 0.8, 0.2, 1),
        opacity 180ms ease,
        transform 180ms ease;
    }
    .shell > .hub-page-header > .hub-page-menu-panel.open {
      max-height: 400px;
      border-top-color: rgba(255,255,255,0.05);
      border-bottom: 0.5px solid rgba(255, 255, 255, 0.1);
      box-shadow: 0 8px 32px rgba(0,0,0,0.32);
      opacity: 1;
      transform: translateY(0);
      pointer-events: auto;
    }
    .shell > .hub-page-header > #attachedFilesPanel.open {
      max-height: min(360px, 50vh);
      border-bottom: 0.5px solid rgba(255, 255, 255, 0.1);
      box-shadow: 0 8px 32px rgba(0,0,0,0.32);
      overflow-y: auto;
      overflow-x: hidden;
    }
    [data-theme="black-hole"] {
      color-scheme: dark;
      --bg-rgb: 10, 10, 10;
      --bg: rgb(var(--bg-rgb));
      --panel: rgba(20, 20, 20, 0.98);
      --panel-strong: rgba(15, 15, 15, 0.99);
      --line: rgba(255, 255, 255, 0.07);
      --line-strong: rgba(255, 255, 255, 0.12);
      --text: rgb(252, 252, 252);
      --muted: rgb(158, 158, 158);
      --chrome-muted: rgb(158, 158, 158);
      --chip-border-idle: rgba(255, 255, 255, 0.09);
      --chip-border-active: rgba(255, 255, 255, 0.15);
      --chip-border-pressed: rgba(255, 255, 255, 0.20);
      --math-display-inline-pad: 2px;
      --viewport-center-gutter: clamp(12px, 3vw, 28px);
      --user-accent: #b0b8c0;
      --claude-accent: #b0b8c0;
      --codex-accent: #b0b8c0;
      --gemini-accent: #b0b8c0;
      --copilot-accent: #b0b8c0;
      --system-accent: #5a6068;
      --inline-code-fg: rgb(255, 255, 255);
      --inline-code-bg: rgb(31, 31, 31);
      --inline-code-border: rgb(64, 64, 64);
      --inline-code-radius: 4px;
      --inline-code-pad-y: 1px;
      --inline-code-pad-x: 5px;
    }
    #starfield {
      position: fixed;
      top: 0;
      left: 0;
      z-index: 1;
      width: 100%;
      height: 100%;
      display: none;
      pointer-events: none;
    }
    [data-theme="black-hole"]:not([data-starfield="off"]) #starfield {
      display: block;
    }
    [data-theme="black-hole"]:not([data-starfield="off"]) body {
      background: transparent !important;
    }
    [data-theme="black-hole"]:not([data-starfield="off"]) html {
      background: rgb(10, 10, 10) !important;
    }
    [data-theme="black-hole"]:not([data-starfield="off"]) #messages,
    [data-theme="black-hole"]:not([data-starfield="off"]) #composer,
    [data-theme="black-hole"]:not([data-starfield="off"]) .shell {
      position: relative;
      z-index: 2;
    }
    [data-theme="black-hole"]:not([data-starfield="off"]) .shell,
    [data-theme="black-hole"]:not([data-starfield="off"]) .composer {
      background: transparent !important;
    }
    [data-theme="black-hole"]:not([data-starfield="off"]) main {
      background: rgb(10, 10, 10) !important;
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
      overflow-x: hidden;
      display: flex;
      align-items: stretch;
      justify-content: center;
      font-family: "SF Pro Display", "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .shell {
      position: relative;
      width: 100%;
      max-width: 760px;
      height: 100vh;
      height: 100svh;
      height: 100dvh;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      border: none;
      border-radius: 0;
      overflow-x: hidden;
      overflow-y: hidden;
      background: var(--bg);
      box-shadow: none;
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
      background-color: rgb(158, 158, 158);
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
        color: rgb(252, 252, 252);
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
      color: rgb(252, 252, 252);
      cursor: pointer;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      transition: background 120ms ease, color 120ms ease;
    }
    .file-item-icon {
      width: 14px;
      height: 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      opacity: 0.85;
      flex-shrink: 0;
    }
    .file-item-icon svg {
      width: 100%;
      height: 100%;
      stroke-width: 2.5px;
    }
    .file-item-path {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .file-menu-section {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 20px 6px;
      color: rgba(255,255,255,0.5);
      font: 600 11px/1.2 "anthropicSans", "SF Pro Text", "Segoe UI", sans-serif;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .file-menu-section-icon {
      width: 12px;
      height: 12px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      opacity: 0.72;
      flex: 0 0 auto;
    }
    .file-menu-section-icon svg {
      width: 100%;
      height: 100%;
      stroke-width: 2.2px;
    }
    .file-menu-row {
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
      min-width: 0;
    }
    .file-menu-row .file-item-path {
      min-width: 0;
    }
    .attached-files-badge {
      position: absolute;
      top: 7px;
      right: 7px;
      min-width: 16px;
      height: 16px;
      padding: 0 4px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: rgba(255,255,255,0.92);
      color: rgb(18, 18, 17);
      font: 700 10px/1 "anthropicSans", "SF Pro Text", "Segoe UI", sans-serif;
      letter-spacing: 0;
      pointer-events: none;
    }
    #attachedFilesMenuBtn {
      position: relative;
    }
    .hub-page-menu-item.danger {
      color: rgba(248, 113, 113, 0.96);
    }
    .hub-page-menu-item.danger:hover,
    .hub-page-menu-item.danger:active {
      color: rgba(252, 165, 165, 1);
    }
    .hub-page-menu-item .action-mobile {
      display: none;
    }
    .hub-page-menu-item .action-icon {
      width: 18px;
      height: 18px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      color: currentColor;
    }
    .hub-page-menu-item .action-icon svg {
      width: 100%;
      height: 100%;
      display: block;
      stroke: currentColor;
      fill: none;
    }
    .file-item:not(:last-child) {
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .has-hover .file-item:hover, .file-item.active {
      background: rgb(20, 20, 19);
      color: rgb(252, 252, 252);
    }
    .pill {
      padding: 5px 9px;
      border-radius: 999px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
    }
    .composer {
      position: fixed;
      right: 0;
      bottom: 0;
      left: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      justify-items: center;
      gap: 10px;
      padding: 0;
      border-top: none;
      background: transparent;
      z-index: 20;
    }
    .composer::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(0deg,
        rgba(var(--bg-rgb),1.0) 0%,
        rgba(var(--bg-rgb),0.88) 18%,
        rgba(var(--bg-rgb),0.58) 42%,
        rgba(var(--bg-rgb),0.18) 68%,
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
    .composer-main-shell {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: 46px minmax(0, 1fr);
      grid-template-areas:
        "input input"
        "plus targets";
      row-gap: 0;
      column-gap: 4px;
      width: 100%;
      max-width: 760px;
      min-width: 0;
      margin: 0 auto;
      padding: 8px 7px 10px 7px;
      border-radius: 20px 20px 0 0;
      border: 1px solid rgba(255,255,255,0.12);
      border-bottom: none;
      background: rgba(20, 20, 19, 0.12);
      box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.06),
        0 10px 28px rgba(0,0,0,0.12);
      backdrop-filter: blur(14px) saturate(125%);
      -webkit-backdrop-filter: blur(14px) saturate(125%);
      transition: border-color 0.4s ease;
      position: relative;
    }
    .has-hover .composer-main-shell:hover {
      border-color: rgba(255, 255, 255, 0.16) !important;
    }
    .target-picker {
      grid-area: targets;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      width: 100%;
      min-width: 0;
      position: relative;
      z-index: 6;
      overflow: visible;
      margin: 2px 0 0;
      padding-left: 14px;
      justify-self: start;
      align-self: center;
      justify-content: flex-start;
    }
    .composer-stack {
      display: contents;
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
      grid-area: plus;
      justify-self: start;
      align-self: center;
      width: 42px;
      height: 42px;
      flex: 0 0 auto;
      z-index: 100;
      margin: 0 0 1px 2px;
    }
    .composer-plus-toggle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 42px;
      height: 42px;
      padding: 0;
      border-radius: 10px;
      border: none;
      background: transparent;
      color: rgb(158, 158, 158);
      box-shadow: none;
      cursor: pointer;
      list-style: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
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
      width: 22px;
      height: 22px;
      display: block;
      stroke-width: 1.7;
    }
    .composer-plus-menu[open] .composer-plus-toggle {
      transform: none;
      border: none;
      background: rgb(20, 20, 19);
      color: rgb(235, 235, 230);
    }
    .composer-plus-panel {
      position: absolute;
      left: 0;
      bottom: calc(100% + 8px);
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 160px;
      padding: 8px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgb(var(--bg-rgb));
      box-shadow: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
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
      color: rgb(252, 252, 252);
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
    .plus-submenu { display: block; position: relative; }
    .plus-submenu > summary { list-style: none; }
    .plus-submenu > summary::-webkit-details-marker { display: none; }
    .plus-submenu.divider-after {
      background-image: linear-gradient(to right, rgba(255,255,255,0.08), rgba(255,255,255,0.08));
      background-repeat: no-repeat;
      background-size: calc(100% - 24px) 1px;
      background-position: 12px 100%;
    }
    .submenu-chevron {
      margin-left: auto;
      width: 14px;
      height: 14px;
      display: flex;
      align-items: center;
      flex-shrink: 0;
      opacity: 0.45;
      transition: opacity 140ms ease;
    }
    .submenu-chevron svg { width: 14px; height: 14px; }
    .plus-submenu[open] .submenu-chevron { opacity: 0.9; }
    .plus-submenu-panel {
      position: absolute;
      left: calc(100% + 14px);
      top: 50%;
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 160px;
      padding: 8px;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgb(var(--bg-rgb));
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      z-index: 200;
      opacity: 0;
      visibility: hidden;
      transform: translateY(-50%) translateX(-6px) scale(0.98);
      transform-origin: left center;
      pointer-events: none;
      transition: opacity 140ms ease, transform 180ms ease, visibility 0s linear 180ms;
    }
    .plus-submenu[open] .plus-submenu-panel {
      opacity: 1;
      visibility: visible;
      transform: translateY(-50%) translateX(0) scale(1);
      pointer-events: auto;
      transition: opacity 140ms ease, transform 180ms ease, visibility 0s;
    }
    .target-chip {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0;
      position: relative;
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid transparent;
      background: transparent;
      color: rgb(158, 158, 158);
      font-size: 14px;
      line-height: 1.2;
      letter-spacing: 0.01em;
      cursor: pointer;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      transition: none;
    }
    .target-chip .target-icon {
      width: 16px;
      height: 16px;
      flex-shrink: 0;
      display: block;
      filter: brightness(0) invert(0.61) !important;
      opacity: 1;
    }
    .target-chip[data-base-agent="codex"] .target-icon,
    .target-chip[data-base-agent="copilot"] .target-icon,
    .filter-chip[data-base-agent="codex"] .filter-icon,
    .filter-chip[data-base-agent="copilot"] .filter-icon {
      filter: invert(1) grayscale(1) brightness(1.35);
    }
    .target-chip.active[data-base-agent="codex"] .target-icon,
    .target-chip.active[data-base-agent="copilot"] .target-icon {
      filter: none;
    }
    .avatar-icon img[alt="codex"],
    .avatar-icon img[alt="copilot"] {
      filter: invert(1) grayscale(1) brightness(1.35);
    }
    .target-chip .target-label {
      display: none;
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
    .quick-action .raw-switch {
      margin-left: auto;
      position: relative;
      width: 30px;
      height: 18px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.16);
      flex: 0 0 auto;
      transition: background 150ms ease, border-color 150ms ease;
    }
    .quick-action .raw-switch::after {
      content: "";
      position: absolute;
      top: 1px;
      left: 1px;
      width: 14px;
      height: 14px;
      border-radius: 999px;
      background: rgba(252, 252, 252, 0.92);
      transition: transform 150ms ease, background 150ms ease;
    }
    .quick-action.raw-on .raw-switch,
    .quick-action[data-forward-action="rawSendBtn"].raw-on .raw-switch {
      background: rgba(252, 252, 252, 0.3);
      border-color: rgba(252, 252, 252, 0.42);
    }
    .quick-action.raw-on .raw-switch::after,
    .quick-action[data-forward-action="rawSendBtn"].raw-on .raw-switch::after {
      transform: translateX(12px);
      background: rgb(252, 252, 252);
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
    .kill-btn {
      color: #ef4444;
    }
    .has-hover .kill-btn:hover {
      color: #f87171;
    }
    /* Tactile button animations */
    .target-chip:active:not(:disabled),
    .quick-action:active:not(:disabled),
    .copy-btn:active,
    .reply-btn:active,
    .reply-cancel-btn:active,
    .composer-plus-toggle:active {
      transform: none;
    }
    #scrollToBottomBtn:active {
      transform: translateX(-50%) scale(0.92);
    }
    
    @media (hover: hover) and (pointer: fine) {
      .target-chip:hover:not(.active),
      .target-chip:active:not(.active) {
        background: transparent;
        border-color: transparent;
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
        background: rgba(255,255,255,0.96) !important;
        color: rgb(18, 18, 17) !important;
        cursor: default;
      }
    }
    .target-chip:active:not(.active) {
      background: transparent;
      border-color: transparent;
      color: rgb(215, 215, 210);
      box-shadow: none;
    }
    .target-chip.active {
      color: rgb(18, 18, 17) !important;
      background: rgba(255,255,255,0.96) !important;
      border-color: rgba(255,255,255,0.96) !important;
      transform: none !important;
      box-shadow: 0 1px 8px rgba(0,0,0,0.12) !important;
    }
    .target-chip.active .target-icon {
      filter: brightness(0) invert(0) !important;
      opacity: 1 !important;
    }
    .composer-shell {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      grid-area: input;
      min-width: 0;
      align-self: stretch;
    }
    .composer-field {
      position: relative;
      border-radius: 24px;
    }
    .send-btn {
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
      box-shadow: none;
      opacity: 0;
      pointer-events: none;
      transform: scale(0.95);
      transition: transform 120ms ease, filter 150ms ease, background 150ms ease, opacity 150ms ease;
    }
    .send-btn.visible {
      opacity: 1;
      pointer-events: auto;
      transform: scale(1);
    }
    .has-hover .send-btn:hover {
      filter: brightness(1.03);
      box-shadow: none;
    }
    .send-btn:active {
      transform: translateY(1px) scale(0.98);
      background:
        linear-gradient(180deg, rgba(210, 218, 230, 0.98) 0%, rgba(175, 188, 206, 0.98) 100%);
      box-shadow: none;
    }
    .send-btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
      box-shadow: none;
      filter: none;
    }
    .static-export-composer {
      opacity: 0.92;
    }
    .static-export-composer .composer-main-shell {
      filter: saturate(0.8);
    }
    .static-export-composer textarea {
      cursor: default;
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
      box-shadow: none;
      transition: transform 120ms ease, filter 150ms ease, opacity 150ms ease;
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
      background: linear-gradient(135deg, rgba(200, 60, 80, 0.92) 0%, rgba(150, 30, 55, 0.95) 100%);
      color: #fff;
      border-color: rgba(255, 120, 130, 0.25);
      animation: none;
    }
    .mic-btn.no-speech { display: none !important; }
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
      background: var(--bg);
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
      color: rgb(252, 252, 252);
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
      background: transparent;
      color: var(--text);
      border-radius: 22px;
      min-height: 54px;
      height: 54px;
      max-height: 200px;
      resize: none;
      padding: 12px 42px 12px 10px;
      font: 400 16px/1.5 "SF Pro Text","Segoe UI",sans-serif;
      box-shadow: none;
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
      transition: background-color 200ms ease;
      overflow-y: auto;
      box-sizing: border-box;
    }
    .composer textarea:focus {
      outline: none;
      background: transparent;
      box-shadow: none;
    }
    .composer textarea::placeholder {
      color: var(--chrome-muted);
    }
    .statusline {
      position: absolute;
      left: 50%;
      bottom: 2px;
      width: min(760px, calc(100vw - 16px));
      padding: 0 10px 2px;
      min-height: 1.3em;
      color: var(--chrome-muted);
      font-size: 11px;
      text-align: right;
      pointer-events: none;
      transform: translateX(-50%);
      z-index: 2;
      background: transparent;
      box-sizing: border-box;
    }
    main {
      grid-area: 1 / 1;
      padding: calc(56px + env(safe-area-inset-top)) 14px calc(var(--composer-height, 96px) + var(--latest-message-offset, 34vh));
      display: flex;
      flex: 1;
      flex-direction: column;
      gap: 12px;
      width: 100%;
      min-width: 0;
      overflow-y: auto;
      overflow-x: hidden;
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
      background: rgba(var(--bg-rgb), 0.72);
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
      color: rgb(252, 252, 252);
      font: 400 18px/1.25 "anthropicSans", sans-serif;
      letter-spacing: -0.02em;
    }
    .conversation-empty-copy {
      margin: 0;
      color: var(--chrome-muted);
      font: 400 14px/1.6 "anthropicSans", sans-serif;
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
    .message-row.grok .avatar { color: var(--copilot-accent); }
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
      color: rgb(252, 252, 252) !important;
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
      color: rgb(252, 252, 252) !important;
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
      color: rgb(158, 158, 158);
      font: 600 12px/1 "SF Pro Text","Segoe UI",sans-serif;
      letter-spacing: 0.01em;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }
    .message.user .user-collapse-toggle.is-visible {
      display: block;
    }
    .has-hover .message.user .user-collapse-toggle:hover {
      color: rgb(252, 252, 252);
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
    @media (hover: hover) and (pointer: fine) {
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
    .message.copilot,
    .message.grok {
      background: rgba(0, 0, 0, 0.68);
      border-color: rgba(255, 255, 255, 0.12);
      box-shadow: 0 10px 24px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255, 255, 255, 0.12);
    }
    .message-row.claude,
    .message-row.codex,
    .message-row.gemini,
    .message-row.copilot,
    .message-row.grok {
      gap: 8px;
    }
    .message-row.claude .avatar,
    .message-row.codex .avatar,
    .message-row.gemini .avatar,
    .message-row.copilot .avatar,
    .message-row.grok .avatar {
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
    .message-row.copilot .avatar img,
    .message-row.grok .avatar img {
      width: 22px;
      height: 22px;
    }
    .message-row.claude .message-wrap,
    .message-row.codex .message-wrap,
    .message-row.gemini .message-wrap,
    .message-row.copilot .message-wrap,
    .message-row.grok .message-wrap {
      max-width: 100%;
    }
    .message-row.claude .message,
    .message-row.codex .message,
    .message-row.gemini .message,
    .message-row.copilot .message,
    .message-row.grok .message {
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
    .message-row.copilot .meta,
    .message-row.grok .meta {
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
      padding: 8px 20px 6px 10px;
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
      margin: -5px 4px 10px 4px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 18px;
      background: rgb(20, 20, 19);
      backdrop-filter: blur(16px) saturate(140%);
      -webkit-backdrop-filter: blur(16px) saturate(140%);
      box-shadow: none;
      animation: paneReveal 220ms cubic-bezier(0.22, 1, 0.36, 1) forwards;
      max-height: min(240px, 32vh);
      min-height: 120px;
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
      color: rgba(252, 252, 252, 0.42);
      animation: thinking-char-pulse 1.5s linear infinite;
      animation-delay: calc(var(--char-i) * 0.18s);
    }
    @keyframes thinking-char-pulse {
      0%   { color: rgba(252, 252, 252, 0.62); }
      10%  { color: rgba(252, 252, 252, 0.82); }
      22%  { color: rgba(252, 252, 252, 0.62); }
      34%  { color: rgba(252, 252, 252, 0.42); }
      88%  { color: rgba(252, 252, 252, 0.42); }
      100% { color: rgba(252, 252, 252, 0.62); }
    }
    @media (prefers-reduced-motion: reduce) {
      .message-thinking-icon { animation: none; filter: brightness(0) invert(0.75); }
      .message-thinking-glow { animation: none; display: none; }
      .thinking-char { animation: none; color: rgba(252, 252, 252, 0.6); }
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
    .arrow { color: rgb(158, 158, 158) !important; }
    .targets { color: rgb(158, 158, 158) !important; }
    .reply-jump-inline {
      all: unset;
      display: inline-flex;
      align-items: center;
      cursor: pointer;
      color: rgb(158, 158, 158) !important;
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
    .reply-jump-inline:active {
      background: rgba(255, 255, 255, 0.08);
    }
    @keyframes inline-flash {
      0% { color: #fff !important; text-shadow: 0 0 12px rgba(255,255,255,0.8); }
      100% { color: rgb(158, 158, 158) !important; text-shadow: none; }
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
      color: rgb(158, 158, 158) !important;
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
    time { opacity: 1; color: var(--muted) !important; }
    .md-body { font: 15px/1.65 "SF Pro Text","Segoe UI",sans-serif; color: rgb(252, 252, 252); }
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
    .message.copilot .md-body,
    .message.grok .md-body {
      font-family: "anthropicSerif", "anthropicSerif Fallback", "Anthropic Serif", "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "Noto Serif JP", Georgia, "Times New Roman", Times, serif;
      font-style: normal;
      font-size: 16px;
      line-height: 24px;
      font-weight: 360;
      color: rgb(252, 252, 252);
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
    .message.copilot .md-body h4,
    .message.grok .md-body h1,
    .message.grok .md-body h2,
    .message.grok .md-body h3,
    .message.grok .md-body h4 {
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
    .message.copilot .md-body blockquote,
    .message.grok .md-body p,
    .message.grok .md-body li,
    .message.grok .md-body blockquote {
      font-weight: 360;
      font-variation-settings: "wght" 360;
    }
    .message.claude .md-body li,
    .message.codex .md-body li,
    .message.gemini .md-body li,
    .message.copilot .md-body li,
    .message.grok .md-body li {
      line-height: 26px;
    }
    html[data-agent-font-mode="gothic"] .message.claude .md-body,
    html[data-agent-font-mode="gothic"] .message.codex .md-body,
    html[data-agent-font-mode="gothic"] .message.gemini .md-body,
    html[data-agent-font-mode="gothic"] .message.copilot .md-body,
    html[data-agent-font-mode="gothic"] .message.grok .md-body {
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
    html[data-agent-font-mode="gothic"] .message.copilot .md-body blockquote,
    html[data-agent-font-mode="gothic"] .message.grok .md-body p,
    html[data-agent-font-mode="gothic"] .message.grok .md-body li,
    html[data-agent-font-mode="gothic"] .message.grok .md-body h1,
    html[data-agent-font-mode="gothic"] .message.grok .md-body h2,
    html[data-agent-font-mode="gothic"] .message.grok .md-body h3,
    html[data-agent-font-mode="gothic"] .message.grok .md-body h4,
    html[data-agent-font-mode="gothic"] .message.grok .md-body blockquote {
      font-weight: 360;
      font-variation-settings: "wght" 360, "opsz" 16;
    }
    html[data-agent-font-mode="gothic"] .message.claude .md-body li,
    html[data-agent-font-mode="gothic"] .message.codex .md-body li,
    html[data-agent-font-mode="gothic"] .message.gemini .md-body li,
    html[data-agent-font-mode="gothic"] .message.copilot .md-body li,
    html[data-agent-font-mode="gothic"] .message.grok .md-body li {
      line-height: 22px;
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
      font-family: "jetbrainsMono", "JetBrains Mono", monospace !important;
      font-style: normal;
      font-size: 16px;
      font-weight: 240;
      font-synthesis-weight: none;
      font-stretch: normal;
      font-variation-settings: "wght" 240;
      color: var(--inline-code-fg);
      line-height: 26px;
      background: var(--inline-code-bg);
      border: 0.5px solid var(--inline-code-border);
      border-radius: var(--inline-code-radius);
      padding: var(--inline-code-pad-y) var(--inline-code-pad-x);
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
      font-weight: 240;
      font-synthesis-weight: none;
      font-variation-settings: "wght" 240;
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
    .file-card-icon {
      width: 1.1em;
      height: 1.1em;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      color: var(--muted);
    }
    .file-card-icon svg {
      width: 100%;
      height: 100%;
      stroke-width: 2.2px;
    }
    .file-card-name { font-size: inherit; font-weight: inherit; line-height: inherit; flex-shrink: 0; }
    .file-card-path { order: 3; flex: 0 0 100%; display: block; margin-top: -2px; padding-left: calc(0.9em + 6px); max-width: 100%; color: var(--dim); font-family: inherit; font-size: inherit; font-weight: inherit; line-height: inherit; white-space: normal; overflow: visible; text-overflow: clip; overflow-wrap: anywhere; word-break: normal; }
    .file-card-open { order: 2; margin-left: auto; font-size: inherit; font-weight: inherit; line-height: inherit; color: var(--dim); flex-shrink: 0; }
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
      align-items: flex-start;
      justify-content: center;
      padding: 44px 28px 20px;
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
      background: rgba(5, 5, 5, 0.92);
    }
    .file-modal-dialog {
      position: relative;
      width: min(1180px, calc(100vw - 56px));
      height: min(820px, calc(100vh - 72px));
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      border-radius: 18px;
      overflow: hidden;
      border: 0.5px solid rgba(255,255,255,0.16);
      background: rgb(10, 10, 10);
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
      background: rgb(10, 10, 10);
    }
    .file-modal-meta {
      display: flex;
      align-items: center;
      gap: 14px;
      flex: 1 1 auto;
      min-width: 0;
    }
    .file-modal-actions {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      flex: 0 0 auto;
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
      color: rgb(252, 252, 252);
    }
    .file-modal-title {
      font: 700 14px/1.2 "SF Pro Text","Segoe UI",sans-serif;
      color: rgb(252, 252, 252);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .file-modal-path {
      display: block;
      margin-top: 3px;
      color: rgb(252, 252, 252);
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
      color: rgb(252, 252, 252);
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
    .file-modal-open-editor {
      appearance: none;
      min-width: 0;
      height: 34px;
      padding: 0 12px;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.06);
      color: rgb(252, 252, 252);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      cursor: pointer;
      font: 600 12px/1 "SF Pro Text","Segoe UI",sans-serif;
      letter-spacing: 0.01em;
      transition: background 150ms ease, transform 100ms ease, border-color 150ms ease;
    }
    .has-hover .file-modal-open-editor:hover {
      background: rgba(255,255,255,0.12);
      border-color: rgba(255,255,255,0.16);
    }
    .file-modal-open-editor:active {
      transform: scale(0.97);
    }
    .file-modal-open-editor[hidden] {
      display: none;
    }
    .file-modal-body {
      position: relative;
      min-height: 0;
      background: rgb(10, 10, 10);
    }
    .file-modal-frame {
      width: 100%;
      height: 100%;
      border: 0;
      display: block;
      background: rgb(10, 10, 10);
    }
    .copy-btn {
      flex-shrink: 0;
      align-self: flex-start;
      margin-top: 2px;
      background: rgba(20, 20, 19, 0); /* Transparent by default */
      border: none;
      padding: 4px;
      cursor: pointer;
      color: rgb(158, 158, 158);
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
      color: rgb(158, 158, 158);
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
      color: rgb(158, 158, 158);
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
    .reply-banner-arrow { opacity: 1; font-size: 13px; color: rgb(158, 158, 158); }
    .reply-banner-text { flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-weight: 400; }
    .reply-banner-sender { font-weight: 400; text-transform: capitalize; margin-right: 2px; color: rgb(158, 158, 158); }
    .reply-cancel-btn {
      cursor: pointer; background: none; border: none; color: rgb(158, 158, 158);
      padding: 2px 4px; border-radius: 4px; font-size: 13px; line-height: 1;
      transition: color 120ms ease, transform 100ms ease;
    }
    .has-hover .reply-cancel-btn:hover { color: rgb(158, 158, 158); }
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
    /* ── Black Hole theme overrides ─────────────────────────────────────── */
    /* composer-main-shell: all states */
    [data-theme="black-hole"] .composer-main-shell,
    [data-theme="black-hole"] .composer-main-shell:focus-within {
      background: rgba(20, 20, 20, 0.16) !important;
      backdrop-filter: blur(14px) saturate(125%) !important;
      -webkit-backdrop-filter: blur(14px) saturate(125%) !important;
    }
    /* user message box */
    [data-theme="black-hole"] .message.user .md-body {
      background: rgb(20, 20, 20);
      background-image: none !important;
      border: none;
      color: var(--user-message-blackhole-color, rgb(252, 252, 252)) !important;
    }
    [data-theme="black-hole"] .message.user .md-body::before,
    [data-theme="black-hole"] .message.user .md-body::after,
    [data-theme="black-hole"] .message.user .message-body-row::before,
    [data-theme="black-hole"] .message.user .message-body-row::after {
      background-image: none !important;
      content: none !important;
      box-shadow: none !important;
      filter: none !important;
    }
    [data-theme="black-hole"] .message.user .md-body p,
    [data-theme="black-hole"] .message.user .md-body li,
    [data-theme="black-hole"] .message.user .md-body h1,
    [data-theme="black-hole"] .message.user .md-body h2,
    [data-theme="black-hole"] .message.user .md-body h3,
    [data-theme="black-hole"] .message.user .md-body h4 {
      color: var(--user-message-blackhole-color, rgb(252, 252, 252)) !important;
    }
    /* user message collapse gradient */
    [data-theme="black-hole"] .message.user .message-body-row.is-collapsed::after {
      background: linear-gradient(180deg, rgba(20,20,20,0) 0%, rgb(20,20,20) 78%);
    }
    [data-theme="black-hole"] .md-body :not(pre) > code,
    [data-theme="black-hole"] .message.user .md-body :not(pre) > code {
      color: var(--inline-code-fg);
      background: var(--inline-code-bg);
      border-color: var(--inline-code-border);
      border-radius: var(--inline-code-radius);
      padding: var(--inline-code-pad-y) var(--inline-code-pad-x);
      letter-spacing: 0;
    }
    /* input box */
    [data-theme="black-hole"] .mic-btn,
    [data-theme="black-hole"] .send-btn {
      background: rgb(252, 252, 252) !important;
      color: rgb(20, 20, 20) !important;
    }
    /* thinking pane background */
    [data-theme="black-hole"] .message-thinking-pane {
      background: transparent !important;
      border: none !important;
    }
    /* tap / hover interactive color */
    [data-theme="black-hole"] .has-hover .quick-action:hover:not(:disabled),
    [data-theme="black-hole"] #fileDropdown,
    [data-theme="black-hole"] .file-item:hover,
    [data-theme="black-hole"] .has-hover .composer-plus-toggle:hover,
    [data-theme="black-hole"] .daybreak,
    [data-theme="black-hole"] .has-hover .copy-btn:hover,
    [data-theme="black-hole"] .has-hover .reply-target-jump-btn:hover,
    [data-theme="black-hole"] #scrollToBottomBtn:active,
    [data-theme="black-hole"] .attach-card-remove {
      background: rgb(25, 25, 25) !important;
    }
    [data-theme="black-hole"] .trace-tooltip {
      background: rgba(var(--bg-rgb), 0.92);
    }
    [data-theme="black-hole"] .conversation-empty-card {
      background: rgba(20, 20, 20, 0.9);
    }
    [data-theme="black-hole"] .attach-card-ext,
    [data-theme="black-hole"] .file-card {
      background: rgb(20, 20, 20);
    }
    [data-theme="black-hole"] .md-body pre {
      background: rgb(15, 15, 15);
    }
    /* scroll button */
    [data-theme="black-hole"] #scrollToBottomBtn {
      background: rgba(var(--bg-rgb), 0.72);
    }
    [data-theme="black-hole"] .has-hover #scrollToBottomBtn:hover {
      background: rgba(25, 25, 25, 0.88);
    }
    /* mobile target chip ::before (mobile modal chips) */
    /* filter chips */
    [data-theme="black-hole"] .filter-chip {
      background: rgba(255,255,255,0.02);
    }
    [data-theme="black-hole"] .filter-chip.active {
      background: rgba(255,255,255,0.07);
    }
    /* selected / open states */
    [data-theme="black-hole"] .composer-plus-menu[open] .composer-plus-toggle,
    [data-theme="black-hole"] .composer-plus-menu:not([open]) .composer-plus-toggle:active {
      background: rgb(10, 10, 10) !important;
    }
__HUB_HEADER_CSS__
  </style>
  <style id="chatFontSettingsStyle">
__AGENT_FONT_MODE_INLINE_STYLE__
  </style>
</head>
<body>
  <canvas id="starfield"></canvas>
  <div id="traceTooltip" class="trace-tooltip"></div>
  <div id="fileDropdown"></div>
  <div class="composer-overlay" id="composerOverlay"></div>
  <div id="fileModal" class="file-modal" hidden>
    <div class="file-modal-backdrop" data-close-file-modal></div>
    <div class="file-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="fileModalTitle">
      <div class="file-modal-header">
        <div class="file-modal-meta">
          <span id="fileModalIcon" class="file-modal-icon"></span>
          <div class="file-modal-text">
            <div id="fileModalTitle" class="file-modal-title">Preview</div>
            <code id="fileModalPath" class="file-modal-path"></code>
          </div>
        </div>
        <div class="file-modal-actions">
          <button type="button" id="fileModalOpenEditorBtn" class="file-modal-open-editor" hidden>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.12 2.12 0 1 1 3 3L7 19l-4 1 1-4Z"></path></svg>
            <span>Open in Editor</span>
          </button>
          <button type="button" class="file-modal-close" aria-label="Close file preview" data-close-file-modal>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
      </div>
      <div class="file-modal-body">
        <iframe id="fileModalFrame" class="file-modal-frame" title="File preview"></iframe>
      </div>
    </div>
  </div>
  <section class="shell">
    __CHAT_HEADER_HTML__
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
              <button type="button" class="quick-action divider-after" id="cameraBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg></span><span class="action-label">Import</span><span class="action-mobile">Import</span></button>
              <input type="file" id="cameraInput" multiple style="display:none">
              <button type="button" class="quick-action divider-after" data-forward-action="rawSendBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17 10 12 4 7"></path><path d="M12 17h8"></path></svg></span><span class="action-label">Raw</span><span class="action-mobile">Raw</span><span class="raw-switch" aria-hidden="true"></span></button>
              <details class="plus-submenu divider-after">
                <summary class="quick-action plus-submenu-toggle"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"></circle><path d="M6 20v-2a6 6 0 0 1 12 0v2"></path></svg></span><span class="action-label">Agent</span><span class="action-mobile">Agent</span><span class="submenu-chevron" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg></span></summary>
                <div class="plus-submenu-panel">
                  <button type="button" class="quick-action" data-forward-action="briefBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"></circle><path d="m12 8 2.5 3.5L12 16l-2.5-4.5L12 8Z"></path></svg></span><span class="action-label">Brief</span><span class="action-mobile">Brief</span></button>
                  <button type="button" class="quick-action" data-forward-action="readMemoryBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v11"></path><path d="m8 10 4 4 4-4"></path><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path></svg></span><span class="action-label">Load</span><span class="action-mobile">Load</span></button>
                  <button type="button" class="quick-action" data-forward-action="memoryBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h10l2 2v14H6z"></path><path d="M9 4v6h6V4"></path><path d="M9 16h6"></path></svg></span><span class="action-label">Memory</span><span class="action-mobile">Memory</span></button>
                </div>
              </details>
              <details class="plus-submenu divider-after">
                <summary class="quick-action plus-submenu-toggle"><span class="action-emoji" aria-hidden="true">⌘</span><span class="action-label">Command</span><span class="action-mobile">Command</span><span class="submenu-chevron" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg></span></summary>
                <div class="plus-submenu-panel">
                  <button type="button" class="quick-action" data-forward-action="restart"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"></rect><path d="M15.5 10A4 4 0 1 0 16 15"></path><path d="M16 9v3h-3"></path></svg></span><span class="action-label">Restart</span><span class="action-mobile">Restart</span></button>
                  <button type="button" class="quick-action" data-forward-action="resume"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v10"></path><path d="m8 11 4 4 4-4"></path><path d="M5 19h14"></path></svg></span><span class="action-label">Resume</span><span class="action-mobile">Resume</span></button>
                  <button type="button" class="quick-action" data-forward-action="ctrlc"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"></rect><path d="M8 10h.01"></path><path d="M11 10h.01"></path><path d="M14 10h.01"></path><path d="M17 10h.01"></path><path d="M8 14h8"></path></svg></span><span class="action-label">Ctrl+C</span><span class="action-mobile">Ctrl+C</span></button>
                  <button type="button" class="quick-action" data-forward-action="enter"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 10 4 15 9 20"></polyline><path d="M20 4v7a4 4 0 0 1-4 4H4"></path></svg></span><span class="action-label">Enter</span><span class="action-mobile">Enter</span></button>
                </div>
              </details>
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
    const CHAT_BASE_PATH = "__CHAT_BASE_PATH__";
    const CHAT_ASSET_BASE = CHAT_BASE_PATH || "";
    const withChatBase = (path) => {
      const raw = String(path || "");
      if (!CHAT_BASE_PATH || !raw.startsWith("/") || raw.startsWith("//")) return raw;
      return `${CHAT_BASE_PATH}${raw}`;
    };
    if (CHAT_BASE_PATH) {
      const __origFetch = window.fetch.bind(window);
      window.fetch = (input, init) => {
        if (typeof input === "string" && input.startsWith("/") && !input.startsWith("//")) {
          return __origFetch(`${CHAT_BASE_PATH}${input}`, init);
        }
        if (input instanceof Request) {
          const url = input.url || "";
          if (url.startsWith(window.location.origin + "/")) {
            const nextUrl = `${window.location.origin}${CHAT_BASE_PATH}${url.slice(window.location.origin.length)}`;
            return __origFetch(new Request(nextUrl, input), init);
          }
        }
        return __origFetch(input, init);
      };
    }
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
    const wrapFileIcon = (path) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
    const FILE_SVG_ICONS = {
      image: wrapFileIcon('<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>'),
      video: wrapFileIcon('<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>'),
      audio: wrapFileIcon('<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>'),
      file: wrapFileIcon('<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>'),
      code: wrapFileIcon('<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>'),
      archive: wrapFileIcon('<path d="M21 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v3"/><path d="m3 8 9 6 9-6"/><path d="M3 18v-8"/><path d="M21 18v-8"/><path d="M3 18a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2"/>'),
      web: wrapFileIcon('<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>')
    };
    const FILE_ICONS = {
      png: FILE_SVG_ICONS.image, jpg: FILE_SVG_ICONS.image, jpeg: FILE_SVG_ICONS.image, gif: FILE_SVG_ICONS.image, webp: FILE_SVG_ICONS.image, svg: FILE_SVG_ICONS.image, ico: FILE_SVG_ICONS.image,
      pdf: FILE_SVG_ICONS.file,
      mp4: FILE_SVG_ICONS.video, mov: FILE_SVG_ICONS.video, webm: FILE_SVG_ICONS.video, avi: FILE_SVG_ICONS.video, mkv: FILE_SVG_ICONS.video,
      mp3: FILE_SVG_ICONS.audio, wav: FILE_SVG_ICONS.audio, ogg: FILE_SVG_ICONS.audio, m4a: FILE_SVG_ICONS.audio, flac: FILE_SVG_ICONS.audio,
      zip: FILE_SVG_ICONS.archive, tar: FILE_SVG_ICONS.archive, gz: FILE_SVG_ICONS.archive, bz2: FILE_SVG_ICONS.archive, rar: FILE_SVG_ICONS.archive,
      md: FILE_SVG_ICONS.file, txt: FILE_SVG_ICONS.file,
      py: FILE_SVG_ICONS.code, js: FILE_SVG_ICONS.code, ts: FILE_SVG_ICONS.code, sh: FILE_SVG_ICONS.code, json: FILE_SVG_ICONS.code, yaml: FILE_SVG_ICONS.code, yml: FILE_SVG_ICONS.code,
      html: FILE_SVG_ICONS.web, css: FILE_SVG_ICONS.web,
    };
    const buildFileCardMarkup = (path) => {
      const filename = path.split("/").pop() || path;
      const ext = filename.includes(".") ? filename.split(".").pop().toLowerCase() : "";
      const icon = FILE_ICONS[ext] || FILE_SVG_ICONS.file;
      return `<button type="button" class="file-card" data-filepath="${escapeHtml(path)}" data-ext="${escapeHtml(ext)}">` +
        `<span class="file-card-icon">${icon}</span>` +
        `<span class="file-card-name">${escapeHtml(filename)}</span>` +
        `<span class="file-card-open">↗</span>` +
        `</button>`;
    };
    const injectFileCards = (html) => {
      return html
        .replace(/\[Attached:\s*([^\]]+)\]/g, (match, rawPath) => buildFileCardMarkup(rawPath.trim()))
        .replace(/(^|[\s>(])@((?:[A-Za-z0-9._-]+\/)+[A-Za-z0-9._-]+(?:\.[A-Za-z0-9._-]+)?)/g, (match, prefix, rawPath) => {
          return `${prefix}${buildFileCardMarkup(rawPath)}`;
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
    const getScrollMetrics = () => {
      return {
        scrollTop: timeline.scrollTop,
        clientHeight: timeline.clientHeight,
        scrollHeight: timeline.scrollHeight,
      };
    };
    const scrollConversationToBottom = (behavior = "auto") => {
      const { scrollHeight } = getScrollMetrics();
      timeline.scrollTo({ top: scrollHeight, behavior });
    };
    const scrollLatestMessageBottomToCenter = (behavior = "auto") => {
      const lastMessage = timeline.querySelector("article.message-row:last-of-type");
      if (!lastMessage) {
        scrollConversationToBottom(behavior);
        return;
      }
      const timelineRect = timeline.getBoundingClientRect();
      const messageRect = lastMessage.getBoundingClientRect();
      const anchorRatio = 0.5;
      const targetTop = Math.max(
        0,
        timeline.scrollTop + (messageRect.bottom - timelineRect.top) - (timeline.clientHeight * anchorRatio),
      );
      timeline.scrollTo({ top: targetTop, behavior });
    };
    const focusMessageInputWithoutScroll = (selectionStart = null, selectionEnd = selectionStart) => {
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
    };
    const fileModal = document.getElementById("fileModal");
    const fileModalFrame = document.getElementById("fileModalFrame");
    const fileModalTitle = document.getElementById("fileModalTitle");
    const fileModalPath = document.getElementById("fileModalPath");
    const fileModalIcon = document.getElementById("fileModalIcon");
    const fileModalOpenEditorBtn = document.getElementById("fileModalOpenEditorBtn");
    let fileModalCurrentPath = "";
    let lastFocusedElement = null;
    const closeFileModal = () => {
      if (fileModal.hidden) return;
      fileModal.classList.remove("visible");
      fileModal.classList.add("closing");
      setTimeout(() => {
        fileModal.hidden = true;
        fileModal.classList.remove("closing");
        fileModalFrame.removeAttribute("src");
        fileModalCurrentPath = "";
        if (fileModalOpenEditorBtn) fileModalOpenEditorBtn.hidden = true;
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
        ? withChatBase(`/file-raw?path=${encodeURIComponent(path)}`)
        : withChatBase(`/file-view?path=${encodeURIComponent(path)}&embed=1`);
      fileModalCurrentPath = path;
      fileModalTitle.textContent = filename;
      fileModalPath.textContent = parentPath;
      fileModalPath.style.display = parentPath ? "" : "none";
      fileModalIcon.innerHTML = FILE_ICONS[normalizedExt] || FILE_SVG_ICONS.file;
      lastFocusedElement = sourceEl || document.activeElement;
      setFileModalEnterOffset(sourceEl, triggerEvent);
      if (fileModalOpenEditorBtn) {
        fileModalOpenEditorBtn.hidden = true;
        fetch(withChatBase(`/file-openability?path=${encodeURIComponent(path)}`))
          .then((res) => res.ok ? res.json() : null)
          .then((data) => {
            if (fileModalCurrentPath !== path || !fileModalOpenEditorBtn) return;
            fileModalOpenEditorBtn.hidden = !(data && data.editable);
          })
          .catch(() => {});
      }
      
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
    const shouldPreferExternalEditor = () => {
      try {
        const ua = navigator.userAgent || "";
        const isMobileUa = /Android|iPhone|iPad|iPod|Mobile/i.test(ua);
        if (isMobileUa) return false;
        return true;
      } catch (_) {
        return true;
      }
    };
    const tryOpenFileInEditor = async (path) => {
      if (!shouldPreferExternalEditor()) return false;
      try {
        const res = await fetch(withChatBase("/open-file-in-editor"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path }),
        });
        return res.ok;
      } catch (_) {
        return false;
      }
    };
    const extFromPath = (path) => {
      const cleanPath = String(path || "").split(/[?#]/, 1)[0];
      const filename = cleanPath.split("/").pop() || "";
      if (!filename.includes(".")) return "";
      return filename.split(".").pop().toLowerCase();
    };
    const pathFromLocalHref = (href) => {
      const rawHref = String(href || "").trim();
      if (!rawHref || rawHref.startsWith("#") || rawHref.startsWith("//")) return "";
      try {
        const url = new URL(rawHref, window.location.href);
        if (url.origin === window.location.origin && ((CHAT_BASE_PATH && (url.pathname === `${CHAT_BASE_PATH}/file-raw` || url.pathname === `${CHAT_BASE_PATH}/file-view`)) || url.pathname === "/file-raw" || url.pathname === "/file-view")) {
          return url.searchParams.get("path") || "";
        }
      } catch (_) {}
      if (/^[a-z][a-z0-9+.-]*:/i.test(rawHref)) return "";
      if (rawHref.startsWith("/")) {
        if (/^\/(Users|private|var|tmp)\//.test(rawHref)) return rawHref.split(/[?#]/, 1)[0];
        return "";
      }
      const cleanHref = rawHref.split(/[?#]/, 1)[0];
      if (!cleanHref.includes("/")) return "";
      return cleanHref;
    };
    const openFileSurface = async (path, ext, sourceEl, triggerEvent) => {
      const normalizedExt = (ext || "").toLowerCase();
      if (!shouldPreferExternalEditor() && ["html", "htm", "pdf"].includes(normalizedExt)) {
        const href = withChatBase(`/file-raw?path=${encodeURIComponent(path)}`);
        const link = document.createElement("a");
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        return;
      }
      if (await tryOpenFileInEditor(path)) return;
      openFileModal(path, ext, sourceEl, triggerEvent);
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
    fileModalOpenEditorBtn?.addEventListener("click", async () => {
      if (!fileModalCurrentPath) return;
      try {
        const res = await fetch(withChatBase("/open-file-in-editor"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: fileModalCurrentPath }),
        });
        if (!res.ok) {
          let detail = "Failed to open file in editor.";
          try {
            const data = await res.json();
            if (data && data.error) detail = data.error;
          } catch (_) {}
          throw new Error(detail);
        }
      } catch (err) {
        alert(err?.message || "Failed to open file in editor.");
      }
    });
    const scrollToBottomBtn = document.getElementById("scrollToBottomBtn");
    scrollToBottomBtn.addEventListener("click", () => {
      scrollConversationToBottom("smooth");
    });
    const updateScrollBtnPos = () => {
      const shell = document.querySelector(".shell");
      const composer = document.getElementById("composer");
      const h = composer.offsetHeight;
      shell.style.setProperty("--scroll-btn-bottom", (h + 12) + "px");
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
    const AGENT_ICON_NAMES = new Set(["claude", "codex", "gemini", "copilot", "grok"]);
    const agentBaseName = (name) => (name || "").toLowerCase().replace(/-\d+$/, "");
    const roleClass = (sender) => {
      const base = agentBaseName(sender);
      if (["user","claude","codex","gemini","copilot","grok"].includes(base)) return base;
      return "system";
    };
    const senderBadge = (sender) => ((sender || "?").trim()[0] || "?").toUpperCase();
    const agentIconSrc = (name) => {
      const s = agentBaseName(name);
      return AGENT_ICON_DATA[s] || `${CHAT_ASSET_BASE}/icon/${encodeURIComponent(s)}`;
    };
    const iconImg = (name, cls) => {
      const base = agentBaseName(name);
      if (!AGENT_ICON_NAMES.has(base)) return "";
      return `<img class="${cls}" src="${escapeHtml(agentIconSrc(name))}" alt="${escapeHtml(base)}">`;
    };
    const thinkingIconImg = (name, cls) => {
      const base = agentBaseName(name);
      if (!AGENT_ICON_NAMES.has(base)) return "";
      const src = base === "codex" ? `${CHAT_ASSET_BASE}/icon/codex` : agentIconSrc(name);
      return `<img class="${cls}" src="${escapeHtml(src)}" alt="${escapeHtml(base)}">`;
    };
    const statusIcon = (name, cls) => {
      const base = agentBaseName(name);
      if (!AGENT_ICON_NAMES.has(base)) return "";
      return `<span class="${cls}" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(name))}')"></span>`;
    };
    const metaAgentLabel = (name, textClass, iconSide = "right") => {
      const raw = (name || "").trim() || "unknown";
      const base = agentBaseName(raw);
      const icon = AGENT_ICON_NAMES.has(base)
        ? `<span class="meta-agent-icon" aria-hidden="true" style="--agent-icon-mask:url('${escapeHtml(agentIconSrc(raw))}')"></span>`
        : "";
      const sideClass = iconSide === "right" ? " icon-right" : "";
      return `<span class="meta-agent${sideClass}">${icon}<span class="${textClass}">${escapeHtml(raw)}</span></span>`;
    };
    const senderAvatar = (sender) => {
      const base = agentBaseName(sender);
      if (AGENT_ICON_NAMES.has(base)) {
        return { cls: "avatar-icon", html: `<img src="${escapeHtml(agentIconSrc(sender))}" alt="${escapeHtml(base)}" width="28" height="28">` };
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
    let currentSessionName = "";
    let _renderedIds = new Set(); // incremental render tracking
    const expandedUserMessages = new Set();
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
      root.innerHTML = ["all", "user", ...agents].map(a => {
        const active = (a === "all" ? filterAgents.size === 0 : filterAgents.has(a)) ? " active" : "";
        const icon = a === "user" ? "" : iconImg(a, "filter-icon");
        const label = `<span class="filter-label">${escapeHtml(a)}</span>`;
        return `<button type="button" class="filter-chip${active}" data-agent="${escapeHtml(a)}" data-base-agent="${agentBaseName(a)}">${icon}${label}</button>`;
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
          return `<button type="button" class="target-chip" data-target="${target}" data-base-agent="${agentBaseName(target)}" title="${escapeHtml(target)}"><img class="target-icon" src="${escapeHtml(agentIconSrc(target))}" alt="${escapeHtml(agentBaseName(target))}"><span class="target-label">${escapeHtml(target)}</span></button>`;
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
            saveTargetSelection(currentSessionName, selectedTargets);
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
      const nodes = targetNode ? [targetNode] : document.querySelectorAll("#attachedFilesMenuBtn, #rightMenuBtn");
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
    let lastMessagesSig = "";
    let initialLoadDone = false;
    let lastNotifiedMsgId = "";
    let soundEnabled = __CHAT_SOUND_ENABLED__;
    let _audioCtx = null;
    let _beepBuffer = null;
    let _notificationBuffers = [];
    let _notificationManifest = [];
    let _notificationManifestPromise = null;
    let _notificationBufferPromise = null;
    let _audioPrimed = false;
    let _lastSoundAt = 0;
    const SOUND_COOLDOWN_MS = 700;
    const NOTIFICATION_SOUNDS_URL = "/notify-sounds";
    const notificationSoundUrl = (name) => `/notify-sound?name=${encodeURIComponent(name)}`;
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
    const ensureNotificationManifest = async () => {
      if (_notificationManifest.length) return _notificationManifest;
      if (_notificationManifestPromise) return _notificationManifestPromise;
      _notificationManifestPromise = fetch(NOTIFICATION_SOUNDS_URL)
        .then((res) => {
          if (!res.ok) throw new Error(`notify manifest http ${res.status}`);
          return res.json();
        })
        .then((items) => {
          _notificationManifest = Array.isArray(items) ? items.filter((item) => typeof item === "string" && item) : [];
          return _notificationManifest;
        })
        .catch((err) => {
          console.warn("notify manifest fallback", err);
          _notificationManifest = [];
          return _notificationManifest;
        })
        .finally(() => {
          _notificationManifestPromise = null;
        });
      return _notificationManifestPromise;
    };
    const ensureNotificationBuffer = async () => {
      if (_notificationBuffers.length || !_audioCtx) return _notificationBuffers;
      if (_notificationBufferPromise) return _notificationBufferPromise;
      _notificationBufferPromise = Promise.resolve()
        .then(async () => {
          const names = await ensureNotificationManifest();
          if (!names.length) return [];
          const decoded = [];
          for (const name of names) {
            try {
              const res = await fetch(notificationSoundUrl(name));
              if (!res.ok) continue;
              const buf = await res.arrayBuffer();
              decoded.push(await _audioCtx.decodeAudioData(buf.slice(0)));
            } catch (_) {}
          }
          _notificationBuffers = decoded;
          return decoded;
        })
        .catch((err) => {
          console.warn("notify sound fallback", err);
          return [];
        })
        .finally(() => {
          _notificationBufferPromise = null;
        });
      return _notificationBufferPromise;
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
        await ensureNotificationBuffer();
      } catch(e) { console.error("Audio prime failed", e); }
    };
    const playNotificationSound = () => {
      if (!soundEnabled || !_audioPrimed || !_audioCtx) return;
      const now = Date.now();
      if (now - _lastSoundAt < SOUND_COOLDOWN_MS) return;
      _lastSoundAt = now;
      try {
        if (_audioCtx.state === "suspended") { _audioCtx.resume().catch(() => {}); return; }
        const s = _audioCtx.createBufferSource();
        const choice = _notificationBuffers.length
          ? _notificationBuffers[Math.floor(Math.random() * _notificationBuffers.length)]
          : null;
        s.buffer = choice || _beepBuffer;
        if (!s.buffer) return;
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
      const shouldStickToBottom = forceScroll || isNearBottom();
      currentSessionName = data.session || "";
      attachedFilesSession = currentSessionName;
      loadThinkingTime(currentSessionName);
      const displayEntries = data.entries.slice(-__MESSAGE_LIMIT__);
      sessionActive = !!data.active;
      const picker = document.getElementById("targetPicker");
      if (!picker.dataset.loaded) {
        const restoredTargets = loadTargetSelection(currentSessionName, data.targets);
        selectedTargets = restoredTargets.length
          ? restoredTargets
          : [];
        picker.dataset.loaded = "1";
        renderAgentStatus(Object.fromEntries(data.targets.map((t) => [t, "idle"])));
        renderAgentFilterChips(data.targets);
      }
      availableTargets = sessionActive ? data.targets : [];
      selectedTargets = selectedTargets.filter((target) => availableTargets.includes(target));
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
        if (shouldStickToBottom) {
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
      if (shouldStickToBottom && !traceOpenedByThinkingRow) {
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
      try {
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
          scrollConversationToBottom("auto");
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
        await refresh({ forceScroll: true });
        return true;
      } catch (error) {
        setStatus(error.message, true);
        return false;
      } finally {
        setQuickActionsDisabled(!sessionActive);
        sendLocked = false;
      }
    };
    document.getElementById("composer").addEventListener("submit", async (event) => {
      event.preventDefault();
      await submitMessage();
    });
    const quickMore = document.querySelector(".quick-more");
    const composerPlusMenu = document.getElementById("composerPlusMenu");
    const hubBtn = document.getElementById("hubPageTitleLink");
    let keepComposerPlusMenuOnBlur = false;
    hubBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      if (window.self !== window.top) {
        window.parent.postMessage("hub_close_chat", "*");
      } else {
        const hubHost = window.location.hostname || "127.0.0.1";
        window.location.href = `${window.location.protocol}//${hubHost}:__HUB_PORT__/`;
      }
    });
    composerPlusMenu && composerPlusMenu.addEventListener("toggle", () => {
      if (!composerPlusMenu.open) {
        composerPlusMenu.querySelectorAll(".plus-submenu").forEach(sub => { sub.open = false; });
      }
    });
    composerPlusMenu?.addEventListener("pointerdown", () => {
      keepComposerPlusMenuOnBlur = true;
      setTimeout(() => { keepComposerPlusMenuOnBlur = false; }, 240);
    });
    composerPlusMenu?.addEventListener("touchstart", () => {
      keepComposerPlusMenuOnBlur = true;
      setTimeout(() => { keepComposerPlusMenuOnBlur = false; }, 240);
    }, { passive: true });
    composerPlusMenu?.addEventListener("click", (event) => {
      const keepFocusTarget = event.target.closest(".plus-submenu-toggle, .composer-plus-panel .quick-action");
      if (!keepFocusTarget) return;
      requestAnimationFrame(() => {
        if (document.activeElement !== messageInput) {
          focusMessageInputWithoutScroll();
        }
      });
    });
    composerPlusMenu && composerPlusMenu.querySelectorAll(".plus-submenu").forEach(sub => {
      sub.addEventListener("toggle", () => {
        if (sub.open) {
          composerPlusMenu.querySelectorAll(".plus-submenu").forEach(other => {
            if (other !== sub) other.open = false;
          });
        }
      });
    });
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
    const rightMenuBtn = document.getElementById("hubPageMenuBtn");
    const rightMenuPanel = document.getElementById("hubPageMenuPanel");
    const attachedFilesMenuBtn = document.getElementById("attachedFilesMenuBtn");
    const attachedFilesPanel = document.getElementById("attachedFilesPanel");
    let attachedFilesSession = "";
    const fileMenuSectionForExt = (ext) => {
      if (["png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "mp4", "mov", "webm", "avi", "mkv", "mp3", "wav", "ogg", "m4a", "flac"].includes(ext)) return "Media";
      if (["html", "htm", "pdf"].includes(ext)) return "Web";
      if (["json", "yaml", "yml", "csv", "sql", "toml", "ini", "cfg", "conf"].includes(ext)) return "Data";
      if (["md", "txt", "log", "tex", "rst"].includes(ext)) return "Documents";
      if (["py", "js", "ts", "tsx", "jsx", "sh", "css"].includes(ext)) return "Code";
      return "Other";
    };
    const buildFileMenuRow = (path, ext) => {
      const filename = path.split("/").pop() || path;
      const icon = FILE_ICONS[ext] || FILE_SVG_ICONS.file;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hub-page-menu-item";
      btn.title = path;
      const row = document.createElement("span");
      row.className = "file-menu-row";
      const iconSpan = document.createElement("span");
      iconSpan.className = "file-item-icon";
      iconSpan.setAttribute("aria-hidden", "true");
      iconSpan.innerHTML = icon;
      const pathSpan = document.createElement("span");
      pathSpan.className = "file-item-path";
      pathSpan.textContent = filename;
      row.append(iconSpan, pathSpan);
      btn.appendChild(row);
      btn.addEventListener("mousedown", (e) => e.preventDefault());
      btn.addEventListener("click", async (e) => {
        if (attachedFilesPanel) {
          attachedFilesPanel.hidden = true;
          attachedFilesPanel.classList.remove("open");
        }
        attachedFilesMenuBtn?.classList.remove("open");
        await openFileSurface(path, ext, btn, e);
      });
      return btn;
    };
    const updateAttachedFilesPanel = async (entries) => {
      if (!attachedFilesPanel) return;
      document.querySelectorAll(".hub-page-menu-btn .attached-files-badge").forEach((node) => {
        if (node.parentElement !== attachedFilesMenuBtn) node.remove();
      });
      const seen = new Set();
      const allFiles = [];
      for (const entry of (entries || [])) {
        const msg = entry.message || "";
        for (const m of msg.matchAll(/\[Attached:\s*([^\]]+)\]/g)) {
          const path = m[1].trim();
          if (!seen.has(path)) { seen.add(path); allFiles.push(path); }
        }
      }
      // Check which files actually exist on disk
      let files = allFiles;
      if (allFiles.length > 0) {
        try {
          const res = await fetch("/files-exist", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paths: allFiles }),
          });
          if (res.ok) {
            const exists = await res.json();
            files = allFiles.filter(p => exists[p]);
          }
        } catch (_) {}
      }
      let badge = attachedFilesMenuBtn?.querySelector(".attached-files-badge");
      if (attachedFilesMenuBtn) {
        if (files.length > 0) {
          if (!badge) {
            badge = document.createElement("span");
            badge.className = "attached-files-badge";
            attachedFilesMenuBtn.appendChild(badge);
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
        empty.className = "hub-page-menu-item";
        empty.style.cursor = "default";
        empty.style.opacity = "0.72";
        empty.textContent = "No attached files";
        attachedFilesPanel.appendChild(empty);
        return;
      }
      const orderedSections = ["Documents", "Code", "Web", "Media", "Data", "Other"];
      const grouped = Object.fromEntries(orderedSections.map((name) => [name, []]));
      for (const path of files) {
        const filename = path.split("/").pop() || path;
        const ext = filename.includes(".") ? filename.split(".").pop().toLowerCase() : "";
        grouped[fileMenuSectionForExt(ext)].push({ path, ext });
      }
      for (const sectionName of orderedSections) {
        const items = grouped[sectionName] || [];
        if (!items.length) continue;
        const section = document.createElement("div");
        section.className = "file-menu-section";
        section.innerHTML = `<span class="file-menu-section-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h7l2 2h9"></path><path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2"></path></svg></span><span>${escapeHtml(sectionName)}</span>`;
        attachedFilesPanel.appendChild(section);
        for (const item of items) {
          attachedFilesPanel.appendChild(buildFileMenuRow(item.path, item.ext));
        }
      }
    };
    const closeHeaderMenus = () => {
      rightMenuPanel?.classList.remove("open");
      attachedFilesPanel?.classList.remove("open");
      if (rightMenuPanel) rightMenuPanel.hidden = true;
      if (attachedFilesPanel) attachedFilesPanel.hidden = true;
      rightMenuBtn?.classList.remove("open");
      attachedFilesMenuBtn?.classList.remove("open");
    };
    const toggleHeaderMenu = (panel, button, otherPanel, otherButton) => {
      if (!panel || !button) return;
      const nextOpen = panel.hidden || !panel.classList.contains("open");
      if (otherPanel) {
        otherPanel.hidden = true;
        otherPanel.classList.remove("open");
      }
      otherButton?.classList.remove("open");
      panel.hidden = !nextOpen;
      panel.classList.toggle("open", nextOpen);
      button.classList.toggle("open", nextOpen);
    };
    rightMenuBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleHeaderMenu(rightMenuPanel, rightMenuBtn, attachedFilesPanel, attachedFilesMenuBtn);
    });
    attachedFilesMenuBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleHeaderMenu(attachedFilesPanel, attachedFilesMenuBtn, rightMenuPanel, rightMenuBtn);
    });
    const closeQuickMore = () => {
      if (quickMore) quickMore.open = false;
      closePlusMenu();
      closeHeaderMenus();
    };
    document.addEventListener("click", (event) => {
      if (quickMore && quickMore.open && !quickMore.contains(event.target)) {
        quickMore.open = false;
      }
      if (composerPlusMenu && composerPlusMenu.open && !composerPlusMenu.contains(event.target) && !event.target.closest(".target-chip")) {
        closePlusMenu();
      }
      const inRightMenu = rightMenuBtn?.contains(event.target) || rightMenuPanel?.contains(event.target);
      const inFilesMenu = attachedFilesMenuBtn?.contains(event.target) || attachedFilesPanel?.contains(event.target);
      if (!inRightMenu && !inFilesMenu) {
        closeHeaderMenus();
      }
    });    document.querySelectorAll("[data-forward-action]").forEach((node) => {
      node.addEventListener("mousedown", (e) => e.preventDefault());
      node.addEventListener("click", async () => {
        const target = node.dataset.forwardAction || "";
        const keepComposerOpen = !!(composerPlusMenu && composerPlusMenu.contains(node));
        const keepHeaderOpen = !!(rightMenuPanel && rightMenuPanel.contains(node));
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
        if (target === "openTerminal") {
          closeQuickMore();
          fetch("/open-terminal", { method: "POST" }).catch(() => {});
          return;
        }
        if (target === "killBtn" && !keepComposerOpen) closeQuickMore();
        if (target !== "rawSendBtn") {
          document.getElementById(target)?.click();
        }
        if (keepComposerOpen && composerPlusMenu) {
          requestAnimationFrame(() => { composerPlusMenu.open = true; });
        }
        if (keepHeaderOpen && rightMenuPanel && rightMenuBtn) {
          requestAnimationFrame(() => {
            rightMenuPanel.hidden = false;
            rightMenuPanel.classList.add("open");
            rightMenuBtn.classList.add("open");
          });
        }
      });
    });
    document.querySelectorAll(".quick-action:not(.memory-btn):not(.brief-btn):not(.raw-send-btn):not(.quick-more-toggle):not(.plus-submenu-toggle):not([data-forward-action]):not(#cameraBtn), .kill-btn").forEach((node) => {
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
      const targets = selectedTargets.length > 0 ? selectedTargets : [];
      if (!targets.length) {
        setStatus("select target(s) for brief", true);
        setTimeout(() => setStatus(""), 2000);
        return;
      }
      closePlusMenu();
      setStatus(`briefing ${targets.join(",")}...`);
      try {
        for (const target of targets) {
          const instruction = `Multiagent session note for ${target}:
- You are running inside a tmux-based multiagent session. agent-send targets panes in this session.
- To message other agents or the human inbox, prefer stdin. Example: printf '%s' '[From: ${target}] hello' | agent-send --stdin user
- Legacy inline form still works temporarily for simple text, but stdin is the standard path going forward.
- To inspect message history, use: agent-index or agent-index --agent <name>. Do NOT run agent-index --follow — it blocks forever and will hang your pane.
- IMPORTANT: Always use --reply when responding to a specific message. Every message you receive includes a msg-id in its header: [From: sender | msg-id: xxxxxxxxxxxx]. Use that ID like this: printf '%s' '[From: ${target}] ...' | agent-send --reply <msg-id> --stdin <target>. This keeps conversations threaded and readable. Only omit --reply when broadcasting a new topic to multiple agents.
- agent-send user writes to the human inbox in agent-index/chat view. It does not inject text into the terminal pane.
- Messages sent via agent-send are displayed in the chat UI (agent-index --chat) with Markdown rendering. You may use Markdown in your messages: **bold**, \`inline code\`, \`\`\`code blocks\`\`\`, headers, lists, tables, etc.
- The chat UI also renders LaTeX math via KaTeX. Use $...$ for inline math and $$...$$ for display (block) math. Standard LaTeX commands and environments such as cases, pmatrix, bmatrix, align, aligned, and array are generally supported. stdin/heredoc is safe for these messages; legacy inline form is risky for shell-sensitive content.
- To attach a file reference in your message, include [Attached: path/to/file] anywhere in the text. The chat UI will render it as a clickable file card. Example: printf '%s' '[From: ${target}] Here is the result [Attached: src/main.py]' | agent-send --stdin user
- After this briefing, when another agent asks you to reply, you must reply with agent-send. Do not reply only in this pane.
- Every normal reply sent with agent-send must start with [From: ${target}] so the sender is explicit.
- Normal replies must contain actual content. Do not reply with only a single word unless explicitly asked.
- Do not start greeting loops or casual chatter unless explicitly instructed.
- For normal replies, identify the sender and use stdin with agent-send, e.g. printf '%s' '[From: ${target}] ...' | agent-send --stdin <sender>
- To confirm you have read this briefing, run now: printf '%s' '[From: ${target}] Briefing received.' | agent-send --stdin user`;
          const res = await fetch("/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target, message: instruction, silent: true }),
          });
          if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.error || `brief failed for ${target}`);
          }
          await new Promise((r) => setTimeout(r, 600));
        }
        await logSystem(`Send Brief → ${targets.join(",")}`);
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

      const toggleRecognition = () => {
        if (isListening) {
          recognition.stop();
          return;
        }
        finalTranscript = messageInput.value;
        // Check permission state for diagnostics
        if (navigator.permissions && navigator.permissions.query) {
          navigator.permissions.query({ name: "microphone" }).then(result => {
            console.log("[mic] permission state:", result.state);
            if (result.state === "denied") {
              setStatus("マイクがブロックされています。アドレスバー左のアイコン → サイトの設定 → マイクを「許可」に変更してください");
              setTimeout(() => setStatus(""), 8000);
            }
          }).catch(() => {});
        }
        try {
          recognition.start();
        } catch (err) {
          console.error("[mic] recognition.start() threw:", err);
          setStatus("音声認識の開始に失敗: " + err.message);
          setTimeout(() => setStatus(""), 5000);
        }
      };
      micBtn.addEventListener("click", toggleRecognition);
      micBtn.addEventListener("touchend", (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleRecognition();
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
      recognition.onerror = (e) => {
        console.error("[mic] recognition error:", e.error, e);
        isListening = false;
        micBtn.classList.remove("listening");
        if (e.error === "not-allowed") {
          setStatus("マイクのアクセスが拒否されています。設定 > プライバシー > マイクで許可してください。");
        } else if (e.error === "service-not-allowed") {
          setStatus("このモード（ホーム画面アプリ）では音声認識が使えません。Safariで開いてください。");
        } else if (e.error === "network") {
          setStatus("音声認識サービスに接続できません（ネットワークエラー）");
        } else if (e.error === "aborted") {
          setStatus("音声認識が中断されました");
        } else {
          setStatus("音声認識エラー: " + (e.error || "unknown"));
        }
        setTimeout(() => setStatus(""), 5000);
      };
    } else if (micBtn) {
      micBtn.classList.add("no-speech");
    }

    // Import / file attach
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

    const updateSendBtnVisibility = () => {
      const hasText = messageInput.value.trim().length > 0;
      if (sendBtn) sendBtn.classList.toggle("visible", hasText);
      if (micBtn) micBtn.classList.toggle("hidden", hasText);
    };
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
        const icon = FILE_ICONS[ext] || FILE_SVG_ICONS.file;
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
      const dropWidth = Math.min(660, taRect.width);
      fileDrop.style.left = (taRect.left + (taRect.width - dropWidth) / 2) + "px";
      fileDrop.style.bottom = (window.innerHeight - pickerRect.top + 64) + "px";
      fileDrop.style.width = dropWidth + "px";
      fileDrop.style.minWidth = "0";
    };

    messageInput.addEventListener("input", updateFileAutocomplete);
    messageInput.addEventListener("click", () => setTimeout(updateFileAutocomplete, 10));
    messageInput.addEventListener("focus", () => {
      updateFileAutocomplete();
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
    messageInput.addEventListener("blur", (event) => {
      document.body.classList.remove("composing");
      const nextTarget = event.relatedTarget;
      const keepPlusMenuOpen = keepComposerPlusMenuOnBlur
        || !!(nextTarget && composerPlusMenu && composerPlusMenu.contains(nextTarget));
      if (!keepPlusMenuOpen) closePlusMenu();
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
    const doCopyFallback = (text) => {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      try { document.execCommand("copy"); } catch(_) {}
      document.body.removeChild(ta);
      return Promise.resolve();
    };
    const doCopyText = (text) => {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).catch(() => doCopyFallback(text));
      }
      return doCopyFallback(text);
    };
    const markCopied = (btn) => {
      if (!btn) return;
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
      const fileLink = e.target.closest("a[href]");
      if (fileLink) {
        const path = pathFromLocalHref(fileLink.getAttribute("href"));
        if (path) {
          e.preventDefault();
          e.stopPropagation();
          void openFileSurface(path, extFromPath(path), fileLink, e);
          return;
        }
      }
      const fileCard = e.target.closest(".file-card");
      if (fileCard) {
        e.stopPropagation();
        const path = fileCard.dataset.filepath;
        const ext = fileCard.dataset.ext || "";
        void openFileSurface(path, ext, fileCard, e);
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
    const collectThinkingTimeTotals = () => {
      const raw = { ...agentTotalThinkingTime };
      const now = Date.now();
      Object.entries(currentAgentStatuses).forEach(([agent, status]) => {
        if (status === "running" && agentStatusSince[agent]) {
          raw[agent] = (raw[agent] || 0) + Math.floor((now - agentStatusSince[agent]) / 1000);
        }
      });
      // Aggregate by base agent name (e.g. claude-1 + claude-2 → claude)
      const totals = {};
      Object.entries(raw).forEach(([agent, secs]) => {
        const base = agentBaseName(agent);
        totals[base] = (totals[base] || 0) + secs;
      });
      return totals;
    };
    const loadThinkingTime = (session) => {
      if (!session || thinkingTimeSession === session) return;
      thinkingTimeSession = session;
      agentTotalThinkingTime = {};
      fetch("/thinking-time", { cache: "no-store" })
        .then((res) => res.ok ? res.json() : null)
        .then((data) => {
          if (!data || typeof data !== "object" || !data.totals || typeof data.totals !== "object") return;
          agentTotalThinkingTime = data.totals;
          renderThinkingIndicator();
        })
        .catch(() => {});
    };
    const saveThinkingTime = () => {};
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
      const runningAgents = Object.keys(currentAgentStatuses).filter((agent) => currentAgentStatuses[agent] === "running");
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
              <span class="message-thinking-glow message-thinking-glow--${agentBaseName(agent)}"></span>
              ${thinkingIconImg(agent, `message-thinking-icon message-thinking-icon--${agentBaseName(agent)}`)}
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
    const hoverCapabilityMedia = window.matchMedia("(hover: hover) and (pointer: fine)");
    const canUseHoverInteractions = () => hoverCapabilityMedia.matches;
    const touchBlurSelector = [
      ".quick-action",
      ".hub-page-menu-btn",
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
    // Sound
    const setSoundBtn = (on) => {
      soundEnabled = !!on;
    };
    setSoundBtn(soundEnabled);
    // TTS (Read Aloud)
    let ttsEnabled = __CHAT_TTS_ENABLED__;
    const hasTTS = typeof window.speechSynthesis !== "undefined";
    const setTtsBtn = (on) => {
      ttsEnabled = !!on;
    };
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
    }
    const syncChatNotificationDefaults = async () => {
      try {
        const res = await fetch("/hub-settings", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (typeof data?.theme === "string" && data.theme) {
          document.documentElement.dataset.theme = data.theme;
        }
        if (typeof data?.starfield === "boolean") {
          if (data.starfield) {
            delete document.documentElement.dataset.starfield;
          } else {
            document.documentElement.dataset.starfield = "off";
          }
        }
        if (typeof data?.agent_font_mode === "string" && data.agent_font_mode) {
          document.documentElement.dataset.agentFontMode = data.agent_font_mode;
        }
        if (typeof data?.chat_font_settings_css === "string") {
          const styleNode = document.getElementById("chatFontSettingsStyle");
          if (styleNode && styleNode.textContent !== data.chat_font_settings_css) {
            styleNode.textContent = data.chat_font_settings_css;
          }
        }
        if (typeof data?.chat_sound === "boolean") {
          setSoundBtn(data.chat_sound);
        }
        if (typeof data?.chat_tts === "boolean" && hasTTS) {
          setTtsBtn(data.chat_tts);
        }
      } catch (_) {}
    };
    syncChatNotificationDefaults();
    setInterval(syncChatNotificationDefaults, 30000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) syncChatNotificationDefaults();
    });
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
      if (_audioPrimed) return;
      await primeSound();
    };
    document.addEventListener("pointerdown", (e) => {
      const toggle = e.target.closest(".hub-page-menu-btn, .composer-plus-toggle, .quick-action");
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
      traceTooltip.style.left = "50%";
      traceTooltip.style.right = "";
      traceTooltip.style.width = "auto";
      traceTooltip.style.maxWidth = "min(1000px, calc(100vw - 32px))";
      traceTooltip.style.top = Math.min(window.innerHeight - 250, rect.bottom + 20) + "px";
      traceTooltip.style.transform = "translateX(-50%)";
      traceTooltip.style.setProperty("--tail-x", "50%");
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
      requestAnimationFrame(() => {
        pane.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
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
        if (Object.values(currentAgentStatuses).includes("running") || Object.keys(agentTotalThinkingTime).length) {
          saveThinkingTime();
        }
      }
    }, 1000);
    window.addEventListener("pagehide", () => {
      if (Object.keys(agentTotalThinkingTime).length || Object.keys(currentAgentStatuses).length) {
        saveThinkingTime();
      }
    });

    const setAutoBtn = () => {};
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
    refreshAutoMode();
    setInterval(refreshAutoMode, 3000);

    const setCaffeinateBtn = () => {};
    const refreshCaffeinate = async () => {
      try {
        const res = await fetch("/caffeinate", { cache: "no-store" });
        if (res.ok) { const d = await res.json(); setCaffeinateBtn(d.active); }
      } catch (_) {}
    };
    refreshCaffeinate();
    setInterval(refreshCaffeinate, 5000);

    // Auto-save every 5 minutes silently (same as Save button but silent=true)
    setInterval(() => {
      fetch("/send", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: "others", message: "save", silent: true }) }).catch(() => {});
    }, 5 * 60 * 1000);

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

    renderRawSendButton();
    if (window.__STATIC_EXPORT__) {
      const comp = document.getElementById("composer");
      const message = document.getElementById("message");
      if (message) {
        message.readOnly = true;
        message.value = "";
        message.placeholder = "Static export preview";
      }
      if (comp) {
        comp.classList.add("static-export-composer");
        comp.querySelectorAll("button, input, textarea, summary, details").forEach((el) => {
          if (el.tagName === "TEXTAREA") return;
          el.disabled = true;
          el.style.pointerEvents = "none";
        });
      }
      document.querySelector(".hub-page-header")?.querySelectorAll("button, details, summary")?.forEach(el => { el.disabled = true; el.style.pointerEvents = "none"; });
      const status = document.getElementById("statusline");
      if (status) status.textContent = "Static export";
    }
    refresh({ forceScroll: true });
    if (followMode && !window.__STATIC_EXPORT__) {
      setInterval(refresh, 250);
    }

    // --- Starfield Animation ---
    const starCanvas = document.getElementById("starfield");
    const starCtx = starCanvas.getContext("2d");
    let stars = [];
    let shootingStars = [];
    const numStars = 360;
    let starAnimationId;
    let isStarAnimationRunning = false;

    function resizeStarCanvas() {
      starCanvas.width = window.innerWidth;
      starCanvas.height = window.innerHeight;
      initStars();
    }
    function initStars() {
      const diagonal = Math.sqrt(starCanvas.width ** 2 + starCanvas.height ** 2);
      stars = Array.from({ length: numStars }, () => ({
        angle: Math.random() * Math.PI * 2,
        radius: Math.random() * diagonal,
        speed: Math.random() * 0.0003 + 0.00015,
        size: Math.random() * 1.2 + 0.5,
      }));
    }
    function spawnShootingStar() {
      if (shootingStars.length === 0 && Math.random() < 0.01) {
        shootingStars.push({
          x: Math.random() * starCanvas.width * 0.5,
          y: Math.random() * starCanvas.height * 0.5,
          vx: 3 + Math.random() * 2,
          vy: 1 + Math.random() * 1.5,
          life: 80,
          initialLife: 80,
        });
      }
    }
    function animateStars() {
      if (!isStarAnimationRunning) return;
      const centerX = starCanvas.width;
      const centerY = starCanvas.height;
      starCtx.fillStyle = "rgb(10, 10, 10)";
      starCtx.fillRect(0, 0, starCanvas.width, starCanvas.height);
      stars.forEach((star, i) => {
        star.angle += star.speed;
        const x = centerX + star.radius * Math.cos(star.angle);
        const y = centerY + star.radius * Math.sin(star.angle);
        const flicker = 0.4 + Math.abs(Math.sin(Date.now() * 0.0015 + i)) * 0.5;
        starCtx.beginPath();
        starCtx.fillStyle = `rgba(255, 255, 255, ${flicker})`;
        starCtx.arc(x, y, star.size, 0, Math.PI * 2);
        starCtx.fill();
      });
      spawnShootingStar();
      for (let i = shootingStars.length - 1; i >= 0; i--) {
        const s = shootingStars[i];
        const opacity = s.life / s.initialLife;
        const grad = starCtx.createLinearGradient(s.x, s.y, s.x - s.vx * 35, s.y - s.vy * 35);
        grad.addColorStop(0, `rgba(255, 255, 255, ${opacity})`);
        grad.addColorStop(1, `rgba(255, 255, 255, 0)`);
        starCtx.strokeStyle = grad;
        starCtx.lineWidth = 2;
        starCtx.beginPath();
        starCtx.moveTo(s.x, s.y);
        starCtx.lineTo(s.x - s.vx * 18, s.y - s.vy * 18);
        starCtx.stroke();
        s.x += s.vx; s.y += s.vy; s.life -= 1;
        if (s.life <= 0) shootingStars.splice(i, 1);
      }
      starAnimationId = requestAnimationFrame(animateStars);
    }
    const updateStarAnimationState = () => {
      const shouldRun = document.documentElement.dataset.theme === "black-hole"
        && document.documentElement.dataset.starfield !== "off";
      if (shouldRun && !isStarAnimationRunning) {
        isStarAnimationRunning = true;
        resizeStarCanvas();
        animateStars();
      } else if (!shouldRun && isStarAnimationRunning) {
        isStarAnimationRunning = false;
        cancelAnimationFrame(starAnimationId);
      }
    };
    window.addEventListener("resize", () => { if (isStarAnimationRunning) resizeStarCanvas(); });
    updateStarAnimationState();
  </script>
</body>
</html>
"""

CHAT_HEADER_ACTIONS_HTML = """
<button type="button" class="hub-page-menu-btn" id="attachedFilesMenuBtn" title="Attached files" aria-label="Attached files">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
</button>
<button type="button" class="hub-page-menu-btn" id="hubPageMenuBtn" title="Menu" aria-label="Menu">
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"><line x1="3" y1="8" x2="21" y2="8"/><line x1="6" y1="16" x2="21" y2="16"/></svg>
</button>
"""

CHAT_HEADER_PANELS_HTML = """
<div class="hub-page-menu-panel" id="attachedFilesPanel" hidden></div>
<div class="hub-page-menu-panel" id="hubPageMenuPanel" hidden>
  <button type="button" class="hub-page-menu-item" data-forward-action="reloadChat"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 3v6h-6"></path><path d="M20 9a8 8 0 1 0 2 5.3"></path></svg></span><span class="action-label">Reload</span><span class="action-mobile">Reload</span></button>
  <button type="button" class="hub-page-menu-item" data-forward-action="openTerminal"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg></span><span class="action-label">Terminal</span><span class="action-mobile">Terminal</span></button>
  <button type="button" class="hub-page-menu-item" data-forward-action="exportBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg></span><span class="action-label">Export</span><span class="action-mobile">Export</span></button>
  <button type="button" class="hub-page-menu-item danger" data-forward-action="killBtn"><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"></circle><path d="m9 9 6 6"></path><path d="m15 9-6 6"></path></svg></span><span class="action-label">Kill</span><span class="action-mobile">Kill</span></button>
</div>
"""


def render_chat_html(*, icon_data_uris, logo_data_uri, server_instance, hub_port, chat_settings, agent_font_mode_inline_style, follow, chat_base_path=""):
    base_path = chat_base_path.rstrip("/")
    logo_src = f"{base_path}/hub-logo" if base_path else logo_data_uri
    chat_header_html = render_hub_page_header(
        logo_data_uri=logo_src,
        title_href="/",
        title_id="hubPageTitleLink",
        title_aria_label="Hub",
        title_alt="Hub",
        actions_html=CHAT_HEADER_ACTIONS_HTML,
        panels_html=CHAT_HEADER_PANELS_HTML,
    )
    html = CHAT_HTML
    if "__CHAT_HEADER_HTML__" in html:
        html = html.replace("__CHAT_HEADER_HTML__", chat_header_html)
    else:
        html = html.replace('<section class="shell">', f'<section class="shell">{chat_header_html}', 1)
    return (
        html
        .replace("__ICON_DATA_URIS__", json.dumps(icon_data_uris, ensure_ascii=True))
        .replace("__HUB_LOGO_DATA_URI__", logo_src)
        .replace("__CHAT_BASE_PATH__", base_path)
        .replace("__SERVER_INSTANCE__", server_instance)
        .replace("__HUB_PORT__", str(hub_port))
        .replace("__CHAT_THEME__", chat_settings["theme"])
        .replace("__STARFIELD_ATTR__", "" if chat_settings.get("starfield", True) else ' data-starfield="off"')
        .replace("__CHAT_SOUND_ENABLED__", "true" if chat_settings.get("chat_sound", False) else "false")
        .replace("__CHAT_TTS_ENABLED__", "true" if chat_settings.get("chat_tts", False) else "false")
        .replace("__AGENT_FONT_MODE__", chat_settings["agent_font_mode"])
        .replace("__AGENT_FONT_MODE_INLINE_STYLE__", agent_font_mode_inline_style(chat_settings))
        .replace("__HUB_HEADER_CSS__", HUB_PAGE_HEADER_CSS)
        .replace("__MESSAGE_LIMIT__", str(chat_settings["message_limit"]))
        .replace("mode: snapshot", f"mode: {'follow' if follow == '1' else 'snapshot'}")
    )
