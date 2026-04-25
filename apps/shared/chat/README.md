# Chat Frontend Fragments

The chat UI is assembled from app-surface fragments by
`multiagent_chat.web.chat.template_loader`.

Variant directories live at `apps/desktop/web/chat/` and `apps/mobile/chat/`.
Each contains:

- `shell.html`: page structure and long-lived DOM containers.
- `shell.css`: small shell-only style block that remains inline.
- `main.css`: ordered CSS entry point, with `__CHAT_INCLUDE:...__` fragments.
- `app.js`: ordered JavaScript entry point, with `__CHAT_INCLUDE:...__` fragments.
- `composer.html`: composer DOM.
- `composer-overlay.css`, `composer-input.css`, `composer-overlay.js`: composer
  slices extracted from the old monolithic template.
- `attachments/`, `composer/`, `modals/`, `panes/`, `runtime/`, and
  `transcript/`: JavaScript slices assembled in order from `app.js`.

This directory contains shared JavaScript fragments included by both variants.

The loader expands all fragments back into the same HTML shape expected by the
existing render and asset externalization pipeline. Keep extractions ordered and
verify assembled desktop/mobile HTML against a known-good baseline when moving
more code.
