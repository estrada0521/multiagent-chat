# multiagent-chat beta 1.0.1

Japanese version: [beta-1.0.1.ja.md](beta-1.0.1.ja.md)

Released: 2026-03-29

This note covers changes after commit `941ce5b` on 2026-03-26, which is the point where the README first labeled the project as `beta 1.0`.

## Highlights

### Pane Trace and session viewing

- Desktop thinking rows can now open Pane Trace in a dedicated popup instead of staying inside the main chat flow.
- The popup evolved into a wider, tabbed, split-capable viewer with better per-window session handling.
- Mobile Pane Trace was brought closer to the desktop look, including the gray background used by the popup.
- Exact tmux session matching and Pane Trace agent switching were tightened to reduce cross-session confusion.
- iOS dot rendering and several popup display details were corrected.

### Chat performance and reload stability

- Chat rendering moved away from one-shot full loads toward incremental message loading, with a 2000-message working set.
- Shared chat CSS and JS were externalized, optional vendors were lazy-loaded, and local/public paths now share the same incremental loading logic to reduce initial page weight.
- Public reload behavior no longer interferes with local Hub or chat state.
- Branch overview loading is now paginated instead of trying to load everything at once.

### Composer, attachments, and message UX

- Import cards can now be labeled or renamed from a popup before sending.
- Renamed uploads keep the chosen label in the chat and drop the old timestamp-prefix naming pattern.
- Message reveal behavior and mobile scroll pinning were reworked to reduce jumpiness.
- Code blocks gained copy buttons, safer scrollbar layout, and more robust math rendering around shell variables and fenced code.
- Hidden files reappeared in attach autocomplete, and 3D file preview support was restored.

### Reliability and setup

- tmux timeout handling now distinguishes an unhealthy tmux server from a truly missing session, which prevents aggressive auto-revive mistakes.
- Pane log autosave was hardened so shrinking captures do not erase previously saved content.
- New sessions now refresh `workspace/docs/AGENT.md` from the current repo copy, so the latest guide is propagated directly.
- Duplicate agent instances, older Python environments, Grok readiness/auth checks, and tmux socket recovery all received compatibility fixes.

### Local HTTPS, public access, and docs

- Quickstart and the Hub gained local HTTPS onboarding, including `mkcert` guidance and extra SAN support.
- Public access docs, chat command docs, design philosophy docs, and technical details docs were expanded.
- README became English-first, a Japanese README was added alongside it, and cross-links between the two were clarified.

## Other notable additions

- Direct pane composer commands were added for common pane-side control flows.
- The branch menu now includes an uncommitted-change summary.
- Session and Pane Trace screenshots were refreshed to better match the current UI.
