# Shared App Surfaces

`apps/shared/` contains app-surface code and assets used by more than one
human-facing UI.

- `chat/` contains browser Chat fragments shared by desktop and mobile.
- `hub/` contains server-rendered Hub templates shared by desktop and mobile.
- `pwa/` contains static PWA assets served by both Hub and Chat.

This directory is intentionally part of `apps/`, not backend runtime core.
