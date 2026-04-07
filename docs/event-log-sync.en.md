# Event Log Sync Internals

Japanese version: [docs/event-log-sync.md](event-log-sync.md)

This document explains how provider-native logs are ingested into `logs/<session>/.agent-index.jsonl`, and why sync ownership can move between instances.

## 1. Sync loop at a glance

The chat server runs a dedicated JSONL sync thread (`_periodic_jsonl_sync`) on a fixed interval (~1 second). The loop:

1. Skips inactive sessions.
2. Takes a per-session non-blocking flock (`.agent-index-sync.lock`) so only one process syncs a session tick.
3. Loads active agents and primes per-agent `first_seen` timestamps.
4. Prunes stale claims for removed agents and applies recent targeted handoff hints.
5. Resolves each agent's native log path (or SQLite session for OpenCode) and calls the provider-specific sync method.
6. Heartbeats `.agent-index-sync-state.json` periodically so claims stay fresh.

The JSONL sync pipeline is independent from browser polling, so indexing continues even when no chat tab is open.

## 2. Cursor and claim model

`ChatRuntime` persists sync ownership in `logs/<session>/.agent-index-sync-state.json`:

- `NativeLogCursor(path, offset)` for file-based providers.
- `OpenCodeCursor(session_id, last_msg_id)` for OpenCode's SQLite history.
- `agent_first_seen_ts` per agent instance.

Core rules:

- **Path-bound cursoring:** when an agent binds to a different file/session, the cursor is re-anchored to avoid re-reading full history.
- **First-seen mtime gate:** candidate logs older than `first_seen - grace` are normally ignored to avoid stealing stale files on fresh bind.
- **Bind backfill windows:** on new bindings, providers scan a short recent window (`~45s`) to avoid dropping replies written right before/after bind.
- **Cross-session global claim guard:** active sessions publish claims; other sessions skip already-claimed paths (TTL-based freshness).
- **Inode-aware identity:** claims compare by file identity when possible, not raw path strings, so alias paths do not double-claim.
- **Message dedup preload:** synced `msg_id`s are preloaded from JSONL on startup, preventing duplicate append after restart.

## 3. Provider adapters

| Provider | Source | Sync notes |
| --- | --- | --- |
| Claude | `~/.claude/projects/-<slug>/*.jsonl` | Workspace hint + slug variants, cautious git-root fallback, bind backfill window |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl` | `session_meta.cwd` workspace match, reasoning/event ingestion, bind backfill |
| Cursor | `~/.cursor/projects/.../*.jsonl` and `~/.cursor/chats/<workspace-md5>/*/store.db` | JSONL + SQLite modes, store.db baseline seeding to avoid first-bind flood |
| Copilot | `events.jsonl` from active Copilot state dir | `assistant.message` entries only |
| Qwen | `~/.qwen/projects/-<slug>/chats/*.jsonl` | Thought-part aware parsing, strict first-bind mode for same-base peers |
| Gemini | `~/.gemini/tmp/<workspace>/chats/session-*.json` | Whole-file reparse on change (file rewrites), thought/planning classification |
| OpenCode | `~/.local/share/opencode/opencode.db` | Session-level claims in SQLite (`session/message/part`) |

### Claude specifics

- Uses pane workspace hint when available.
- Supports slug variants (raw, underscore->hyphen, sanitized).
- Git-root fallback is delayed and gated so parent-dir misbinding is less likely.
- Keeps a short bind backfill deadline to recover first replies during startup races.

### Codex specifics

- Uses rollout JSONL and appends from `response_item` / `event_msg`.
- `response_item.payload.type=reasoning` and `event_msg.payload.type=agent_reasoning` are indexed as `kind="agent-thinking"`.
- Error events are also indexed when present.

### Cursor specifics

- Prefers existing claimed cursor when same-base peers are present (stability over churn).
- Supports transcript JSONL and `store.db`.
- On first bind to `store.db`, existing messages are marked as already-synced baseline instead of being appended all at once.

### Copilot specifics

- Parses only `assistant.message`.
- Uses `messageId`/event id for dedup when present.

### Qwen specifics

- Extracts assistant `message.parts`.
- If only `thought=true` parts exist, entry is indexed as `kind="agent-thinking"`.
- Uses strict first-bind behavior for same-base multi-instance cases.

### Gemini specifics

- Gemini session files are rewritten; offset is used as change detector, then full JSON is reparsed.
- Empty placeholders are ignored until content arrives.
- `kind="agent-thinking"` is assigned when thought parts exist or when short planning-style text patterns match.

### OpenCode specifics

- Chooses the most recently updated matching workspace session that is not claimed by another OpenCode instance.
- Tracks by `session_id` + `last_msg_id` instead of file offsets.
- On session switch, uses first-seen/backfill time floor to avoid replaying full legacy history.

## 4. Handoff and stale-claim correction

Two periodic safeguards run before provider sync:

1. **`prune_sync_claims_to_active_agents(...)`** removes claims for removed instances and migrates base-name alias transitions (`claude` <-> `claude-1`) when topology changes.
2. **`apply_recent_targeted_claim_handoffs(...)`** inspects recent single-target sends and can transfer shared same-base claims to the explicitly targeted instance.

This is what keeps add/remove/restart flows from drifting attribution across same-base instances.

## 5. Thinking-kind indexing

Thinking messages can enter JSONL in two ways:

- Provider-native typed events (`reasoning`, `thought=true`, etc.) are written with `kind="agent-thinking"` at sync time.
- Read-time inference can assign `agent-thinking` for planning-style lines (for existing entries without explicit `kind`), without rewriting old JSONL lines.

## 6. Troubleshooting checklist

When Sync Status is empty or mismatched:

1. Confirm the session is active and the chat server is running for that session.
2. Inspect `logs/<session>/.agent-index-sync-state.json` for cursor ownership and `agent_first_seen_ts`.
3. Check whether another active session currently claims the same native path.
4. Verify pane-local workspace hints (especially Claude/Cursor/Qwen/Gemini path discovery cases).
5. Confirm recent single-target sends if attribution should hand off to a specific instance.

Useful artifacts:

- `logs/<session>/.agent-index.jsonl`
- `logs/<session>/.agent-index-sync-state.json`
- `logs/<session>/.agent-index-sync.lock`

## 7. Adding a new provider

To add a provider reliably:

1. Add a `sync_<provider>_assistant_messages(...)` adapter in `chat_sync_providers_core.py`, then wire a thin `_sync_<provider>_assistant_messages(...)` wrapper in `chat_core.py`.
2. Define claim/cursor semantics (file cursor vs logical cursor).
3. Wire the provider in `_periodic_jsonl_sync` path resolution dispatch (`chat_server.py`).
4. Add regression tests in `tests/test_sync_cursors.py` (bind, rebind, stale-claim, dedup, backfill).
5. Add runtime-hint parsing only if it can be kept lightweight and non-blocking.
