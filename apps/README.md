# Apps

User-facing shells live here.

- `desktop/web/` contains the desktop browser-facing Hub/Chat surfaces.
- `desktop/src-tauri/` contains the Tauri desktop application shell.
- `mobile/` contains the mobile/PWA browser-facing surfaces.
- `shared/` contains UI fragments and server-rendered templates shared by
  multiple app surfaces.
- `shared/pwa/` contains static PWA assets served by both Hub and Chat.

`apps/shared/` is shared app-surface code, not backend core. It should only hold
HTML/CSS/browser JavaScript/templates/static assets that are reused by multiple
human-facing surfaces.

Core Hub, chat, runtime, sync, and storage behavior should stay in
`src/multiagent_chat/`, not in app shells.
