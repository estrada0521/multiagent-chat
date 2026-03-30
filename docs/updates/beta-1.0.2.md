# multiagent-chat beta 1.0.2

Japanese version: [beta-1.0.2.ja.md](beta-1.0.2.ja.md)

Released: 2026-03-31

This note covers changes after commit `595bf9a` on 2026-03-29, which published the beta 1.0.1 release notes.

## Highlights

### Installable Hub and background notifications

- Hub and chat now ship installable manifests plus a shared service worker, so HTTPS deployments can be added to the Home Screen or browser app shelf.
- Hub Settings gained an `App Install & Notifications` block with install guidance, notification permission controls, and a test-notification path.
- Browser notifications were consolidated at the Hub level, so one installed Hub can receive background agent replies from all active sessions.
- Apple Web Push delivery was fixed by switching VAPID subject handling to a real host and by using a CA bundle path that works with Safari / WebKit subscriptions.

### Chat motion, scrolling, and Pane Trace polish

- Agent replies now use a tighter streaming-reveal path, followed by multiple scroll-lock and anchor fixes so incoming messages no longer yank the viewport around.
- Embedded and popup Pane Trace layouts were tuned repeatedly for desktop and mobile, including overflow tabs, font sizing, narrow-width fitting, gray mobile backgrounds, and badge/icon alignment.
- Agent instance icons now reuse the base agent icon with numeric subscripts, and several message-spacing, gutter, and thinking-indicator details were cleaned up.
- Hub and chat now include a `Bold mode` setting for users who prefer heavier text rendering.

### Reliability, security, and internal cleanup

- `agent-send` now flocks JSONL writes and records only successful deliveries.
- Pane reset detection was hardened with content hashing, and reload-safe external chat bundles were restored after the app-bundle refactor.
- Inline Python command-injection risk was closed, and several bash / Python paths received stricter error handling.
- The chat HTML template was extracted from the generated asset blob, which makes front-end iteration and recovery work easier.

### Setup, CLI coverage, and docs

- Quickstart now covers Kimi CLI installation, while the README keeps the required one-time `kimi login` step explicit.
- README gained update / removal guidance and a larger robustness section.
- Technical details, release notes, and implementation-facing docs were expanded so the current Hub / chat / tmux recovery model is easier to follow.

## Other notable additions

- `.cursor/` is now ignored by default.
- Unused UI remnants and empty overview files were cleaned up.
- Header / action-surface polish continued alongside the broader mobile / desktop refinement pass.
