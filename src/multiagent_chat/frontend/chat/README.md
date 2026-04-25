# Chat Frontend Fragments

The chat UI is assembled from per-variant fragments by
`multiagent_chat.chat_template_loader`.

Each variant directory (`desktop/`, `mobile/`) contains:

- `shell.html`: page structure and long-lived DOM containers.
- `shell.css`: small shell-only style block that remains inline.
- `main.css`: ordered CSS entry point, with `__CHAT_INCLUDE:...__` fragments.
- `app.js`: ordered JavaScript entry point, with `__CHAT_INCLUDE:...__` fragments.
- `composer.html`: composer DOM.
- `composer-overlay.css`, `composer-input.css`, `composer-overlay.js`: first
  composer slices extracted from the old monolithic template.

The loader expands all fragments back into the same HTML shape expected by the
existing render and asset externalization pipeline. Keep extractions ordered and
verify assembled desktop/mobile HTML against a known-good baseline when moving
more code.
