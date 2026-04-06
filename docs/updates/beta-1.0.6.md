# multiagent-chat beta 1.0.6

Japanese version: [beta-1.0.6.ja.md](beta-1.0.6.ja.md)

Released: 2026-04-06

This release covers changes after `beta 1.0.5` and includes a fundamental message-routing policy shift.

## Highlights

### `agent-send user` was removed

- `agent-send` now targets **agents only** (`others`, base names, instance names, fan-out).
- Calling `agent-send user` now fails with an explicit guidance error.
- Session briefing, `agent-help`, and agent guide docs were rewritten to match this policy.

### Human-facing chat now follows event-log-first indexing

- Human-facing replies are expected as normal assistant output in panes, then indexed from native event logs.
- Chat `/send` now delivers user prompts directly to target panes and appends user-origin entries to JSONL without relying on `agent-send user`.
- `/memo` is preserved as a self-log flow by writing a `targets=["user"]` entry directly into JSONL.

### Canonical session log path was standardized and hardened

- Session JSONL is centralized through `MULTIAGENT_INDEX_PATH` with canonical path preference.
- Workspace-side paths are mirrored via symlink with merge-on-migrate behavior.
- Added guards and recovery for broken/self-referential index symlinks, including backup restore fallback.

### Hub preview and sync reliability were tightened

- Session preview now prefers the canonical index for consistent latest-message display.
- Native log binding now persists claims earlier, refreshes claims with heartbeat, and invalidates pane-path cache on restart/resume.
- Cursor transcript fallback also considers git-root slug paths for nested workspace scenarios.

### Documentation moved to `beta 1.0.6`

- README/site/full-readme/technical docs were updated to reflect the new routing model.
- Release index now points to this 1.0.6 note as the latest update.
