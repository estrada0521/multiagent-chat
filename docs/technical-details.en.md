# multiagent-chat Technical Details

Japanese version: [docs/technical-details.md](technical-details.md)

This document follows the flow of [README.md](../README.md), but explains the implementation side instead of the user-facing workflow. The focus here is how sessions, messages, logs, files, and UI state move through `bin/` and `lib/agent_index/`.

## 0. Code Map

The main responsibilities are split across session creation, message delivery, Hub / chat serving, and file / log / export support.

| File | Role |
|------|------|
| `bin/multiagent` | create tmux sessions, place agent panes, add / remove agents, save pane logs |
| `bin/agent-send` | thin CLI launcher that forwards to the Python routing core |
| `lib/agent_index/agent_send_core.py` | session / target resolution, pane delivery, canonical JSONL append, and reply preview generation |
| `lib/agent_index/session_path_core.py` | shared tmux socket-derived state/log path helpers used by routing and session management scripts |
| `lib/agent_index/multiagent_topology_core.py` | parser for user-pane topology specs used by `multiagent` |
| `lib/agent_index/multiagent_state_core.py` | topology lock handling and session state file generation helpers |
| `lib/agent_index/multiagent_session_core.py` | session context parsing from tmux environment for lifecycle operations |
| `lib/agent_index/multiagent_agent_core.py` | add/remove lifecycle helpers for instance naming and agent-list transitions |
| `bin/agent-index` | Hub, chat UI, Stats, Settings, and HTTP endpoints such as upload / trace / export |
| `lib/agent_index/chat_core.py` | chat-server runtime, message payload, pane status, trace, save log |
| `lib/agent_index/chat_payload_core.py` | backend payload document shaping and light-entry summarization separated from HTML rendering |
| `lib/agent_index/chat_assets.py` | chat UI HTML / CSS / JavaScript, composer, brief / memory, Pane Trace |
| `lib/agent_index/hub_core.py` | active / archived session discovery, Hub preview, Stats aggregation |
| `lib/agent_index/file_core.py` | file preview, raw file serving, external-editor handoff |
| `lib/agent_index/export_core.py` | standalone HTML export builder |
| `lib/agent_index/push_core.py` | VAPID key management, browser-push subscriptions, and Hub / session notification monitors |
| `lib/agent_index/state_core.py` | persistence for Hub settings, chat ports, and thinking totals |
| `lib/agent_index/agent_registry.py` | supported agent CLIs, launch / resume flags, icon metadata |
| `lib/agent_index/static/pwa/` | service worker, manifest, and install assets for Hub / chat PWA surfaces |
| `bin/multiagent-public-edge` | Cloudflare-facing reverse proxy for public session access |

The current per-session storage layout is:

```text
logs/<session>/
  .agent-index.jsonl
  .agent-index-commit-state.json
  .meta
  *.ans
  *.log
  uploads/
  brief/
    brief_<name>.md
  memory/
    <agent>/
      memory.md
      memory.jsonl
```

State that is intentionally not shared through the repo is stored in the local state directory. On macOS that is `~/Library/Application Support/multiagent/<repo-hash>/`; on Linux it is `$XDG_STATE_HOME/multiagent/<repo-hash>/`.

## 1. New Session / Message Body

`bin/multiagent` creates the tmux session, writes `MULTIAGENT_*` variables into it, and records workspace, log directory, tmux socket, pane IDs, and the active agent list. When the same base agent appears more than once, it generates suffixed instance names such as `claude-1` and `claude-2` so each pane variable stays unique. `multiagent add-agent` and `multiagent remove-agent` live at this layer as well. The pane-spec parsing (`--user-pane`), topology lock / state-file updates, session-context parsing from tmux environment, and agent-list transition logic for add/remove are delegated to `multiagent_topology_core.py`, `multiagent_state_core.py`, `multiagent_session_core.py`, and `multiagent_agent_core.py` so those behaviors are testable outside the shell script.

The per-session chat UI is served by `bin/agent-index`. `ChatRuntime.payload()` now delegates JSON document shaping to `chat_payload_core.py`, and returns payload data containing `session`, `workspace`, `port`, `targets`, and `entries`. The front-end in `chat_assets.py` turns that payload into bubbles, target chips, reply banners, and rich rendering. KaTeX and Mermaid are both rendered in the same front-end layer.

### `agent-send`

`agent-send` is the agent-to-agent transport for this environment. The shell entrypoint (`bin/agent-send`) is now intentionally thin; the routing implementation lives in `lib/agent_index/agent_send_core.py`. It does more than paste text into panes. It also writes the same message into `.agent-index.jsonl` with `msg_id`, `targets`, and optional `reply_to`.

Session resolution is ordered as `MULTIAGENT_SESSION`, current tmux session, a unique active session for the current workspace, and finally the startup state file. Targets can be `others`, a base agent name, a specific instance name, or a comma-separated fan-out. Sending to `claude` means all `claude-*` instances in the session, while `claude-1` means only that instance.

Each send generates a fresh `msg_id`. On the normal path, `agent-send` auto-adds a `[From: ...]` transport header based on the sending pane. `msg_id` and `reply_to` stay in JSONL/chat metadata rather than the pane text, and `agent-send` uses `reply_to` to look up the original message and build a `reply_preview`. A typical entry looks like this:

```json
{
  "timestamp": "2026-03-26 14:20:16",
  "session": "multiagent",
  "sender": "codex",
  "targets": ["claude-1", "claude-2"],
  "message": "[From: codex] Sharing this now.",
  "msg_id": "4dc1d8a6c0f2",
  "reply_to": "afe4a1c21f2e",
  "reply_preview": "user: Please read docs/AGENT.md..."
}
```

`agent-send` now logs only deliveries that actually succeed. If a tmux paste fails for a target, that failed target is omitted from JSONL; partial success logs only the successful subset.

### `/send` and direct-provider paths

Normal sends from the chat UI go through `POST /send`. `ChatRuntime.send_message()` delivers the payload directly to target panes and appends a `sender="user"` JSONL entry; `/memo` records a self-targeted user entry without pane delivery. Direct-provider commands such as `/gemini` and `/gemma` do not target a tmux pane. Instead they launch a provider runner (`multiagent-gemini-direct-run` or `multiagent-ollama-direct-run`) and stream normalized provider events back into the same chat timeline.

## 1.5. Thinking / Pane Trace

`ChatRuntime.agent_statuses()` captures the last 20 lines of each pane and compares them with the previous snapshot to derive `running`, `idle`, `dead`, or `offline`. A short grace period keeps a pane in `running` immediately after a change, then it falls back to `idle` if output stops changing. The resulting statuses are passed into `state_core.update_thinking_totals_from_statuses()` so session- and agent-level thinking time can accumulate.

Pane Trace comes from `GET /trace?agent=<name>&lines=<n>`. `trace_content()` uses `tmux capture-pane -p -e` and either returns a tail window or a much larger scrollback. The front-end polls only the currently visible tab: every 100ms on local / LAN hosts, every 1.5 seconds on public hosts.

On desktop, the Pane Trace popup supports multiple layout modes: single pane, horizontal split, vertical split, three-pane arrangements, and a four-pane grid. Each slot polls its assigned agent independently. Agents can be reassigned per slot through tab clicks or drag-and-drop of agent icons onto pane slots. Extra polling intervals are created for each additional pane beyond the first and cleaned up when the layout changes.

Polling updates do not auto-scroll. Only the initial load and explicit agent switches scroll to the bottom. When the user scrolls away from the bottom of a pane (more than 48px from the end), DOM updates are paused entirely so that text selection and copy are not disrupted by incoming refreshes. Updates resume automatically when the user scrolls back to the bottom.

ANSI escape sequences in pane output are converted to styled HTML using the `AnsiUp` library. The conversion runs client-side in both mobile and desktop views. Special characters such as the trace dot (`●`) are wrapped in a dedicated `<span>` for consistent rendering across platforms, particularly iOS where emoji-variant rendering can differ.

Thinking rows and Pane Trace are related but not identical. The thinking row is a status summary. Pane Trace is the pane-side text snapshot. The first is lightweight state; the second is actual pane content.

## 2. Composer / Input Modes

The composer is implemented as an overlay in `chat_assets.py`. It stays closed by default, opens from the `O` button on mobile, and from the same button or middle click on desktop. The lower action row holds send, mic, Import, brief, memory, save log, and pane-control actions.

### Slash commands

Slash commands are defined in the front-end `SLASH_COMMANDS` array. Their backends are split between dedicated front-end handlers and the `/send` endpoint.

| Command | Technical behavior |
|------|------|
| `/memo [text]` | self-send to `user`; Import attachments are enough even without body text |
| `/cron` | open the quick-create Cron flow for the current session / target |
| `/gemini <text>` | launch the direct Gemini runner and stream provider events into chat |
| `/gemma <text>` | launch the Ollama runner; `/gemma:model` overrides the configured model name |
| `/brief` | open the `default` brief editor modal |
| `/brief set <name>` | open `brief_<name>.md` |
| `/load` | send the current `memory.md` to the selected agent |
| `/memory` | trigger a memory refresh request for the selected agent |
| `/model` | send `model` to the target pane |
| `/up [count]` | send up-navigation to the target pane |
| `/down [count]` | send down-navigation to the target pane |
| `/restart` | call `ChatRuntime.restart_agent_pane()` |
| `/resume` | resume the pane using the agent registry resume flag |
| `/ctrlc` | send `Ctrl+C` to the target pane |
| `/interrupt` | send `Escape` to the target pane |
| `/enter` | send `Enter` to the target pane |

### `@` and Import

`@` insertion is the workspace-side file-reference path. The front-end inserts relative file paths into the conversation, and `/files-exist` validates them when needed. Import is a different pipeline. `POST /upload` stores the file body under `logs/<session>/uploads/<timestamp>_<hex>.<ext>`. The server returns the workspace-relative path, and the chat UI turns it into an attachment card.

Attachment cards support renaming before send. Tapping a card opens a popup where the user can enter a label. On send, `POST /rename-upload` renames the file on disk to the chosen label (preserving the extension), and the sent message references the new filename. The label is sanitized server-side: control characters, path separators, and non-word characters are stripped or replaced, and the result is truncated to 80 characters. Collisions are resolved by appending a short random suffix.

### Camera mode

Camera mode is a separate mobile-first overlay opened from the header menu's `Camera` action. `openCameraMode()` primes a target agent, opens a full-screen `getUserMedia()` surface, and keeps recent agent replies rendered over the same live camera feed.

Captures are not sent as raw blobs. `captureCameraModeFrameBlob()` draws the current video frame into a canvas, `resizeCameraModeBlob()` scales it down (currently max side 1280px, JPEG quality 0.7), `POST /upload` stores it under `logs/<session>/uploads/`, and then `POST /send` delivers a normal `[Attached: ...]` message to the selected target. Voice input inside the same overlay uses Web Speech API plus a hybrid waveform: when a second audio stream can be opened, bars switch into live Web Audio-driven motion; otherwise the CSS fallback animation remains active so the UI still shows listening state.

### Brief and Memory

Brief is managed by `/briefs`, `GET /brief-content`, and `POST /brief-content` in `bin/agent-index`. Names are normalized into `brief_<name>.md` under `logs/<session>/brief/`. The Brief button first fetches the stored list, then reads the selected brief body, then sends it sequentially to the selected targets with `silent=true`.

Memory is stored per agent in `logs/<session>/memory/<agent>/memory.md`, with historical snapshots in `memory.jsonl`. When the Memory button is pressed, `POST /memory-snapshot` runs first and appends the current `memory.md` into `memory.jsonl`. Only after that does the front-end send the rewrite instruction to the target agent. Load is the reverse direction: read the current `memory.md` and send it back into the conversation.

## 3. Header

### Branch Menu

The branch menu is driven by git-overview and diff endpoints from the chat server. Current branch, dirty state, commit list, and diff chunks are fetched as JSON and rendered into the panel / carousel UI. The commit list is paginated: `/git-branch-overview` accepts `offset` and `limit` parameters and returns commits in batches (default 50). The front-end uses an `IntersectionObserver` on a sentinel element at the bottom of the list to trigger loading the next page, or the user can tap a `Load more` button. This avoids running `git log --stat` across the entire history on initial load.

Uncommitted changes are shown at the top of the branch menu, above the commit history. The diff is generated from `git diff HEAD` and `git diff --cached` and rendered inline.

`ChatRuntime.ensure_commit_announcements()` also compares the current `git log -1` result with the previously recorded commit state. When a new commit appears, it appends a `kind="git-commit"` system entry into JSONL. Stats later uses those system entries as the source of commit counts.

### File Menu

The file menu is powered by `FileRuntime`. Raw file delivery uses `/file-raw`, text content uses `/file`, and external-editor handoff uses `/open-file-in-editor`. `FileRuntime` picks preview mode from file extension and file content, switching among Markdown, image, PDF, video, audio, and plain text.

For Markdown previews, the renderer first turns Markdown into HTML, then rewrites relative `img src` paths so they resolve against the Markdown file and are served from `/file-raw?path=...`. `Open in Editor` first honors `MULTIAGENT_EXTERNAL_EDITOR` when provided, and otherwise falls back to CotEditor, VS Code, or a system opener depending on platform and file type.

### Add / Remove Agent

The add / remove agent modals are front-end controls. The actual layout change is delegated to `multiagent add-agent` and `multiagent remove-agent`. The same commands are also available to agents already running inside the session, because pane startup exports `MULTIAGENT_SESSION` and `MULTIAGENT_TMUX_SOCKET`.

What changes here is the tmux pane layout and `MULTIAGENT_AGENTS`; the existing `.agent-index.jsonl` stays intact. Each successful topology change also appends a `kind="session-topology"` system entry into JSONL, so UI-triggered and agent-triggered changes share the same chat-visible history. For self-removal, `multiagent remove-agent` first hands the operation off to a detached helper process so the pane can disappear without aborting the later environment updates.

The UI recommends `Reload` afterward because the visible target list and pane state need to be refreshed together.

## 4. Hub / Stats / Settings

`HubRuntime` reads both active tmux sessions and archived log directories. The active side comes from tmux session state plus `MULTIAGENT_*` environment, while the archived side comes from log directories, `.meta`, and `.agent-index.jsonl`. The Hub preview message is built by `latest_message_preview()`, which strips `[From: ...]` headers and `[Attached: ...]` markers before truncating the text.

Stats are built by `HubRuntime.build_stats_payload()`. Messages are deduplicated by `msg_id` when possible, then counted by sender and by session. Commits are deduplicated by `commit_hash` from `git-commit` system entries. Thinking time is loaded from `state_core.py`, and instance names are collapsed back to base agent names before display.

Settings flow through `state_core.load_hub_settings()` and `save_hub_settings()`. Shared Hub / chat settings are intentionally not stored in the repo tree. They live in the local state directory instead. Chat port overrides are saved in `.chat-ports.json`, Hub settings in `.hub-settings.json`, and thinking aggregates in `.thinking-time.json` plus `.thinking-runtime.json`.

Install prompts and browser notifications now hang off the Hub itself. `bin/agent-index` serves `hub.webmanifest`, `app.webmanifest`, `service-worker.js`, and the Settings-side install / permission controls. Push subscriptions are stored through `push_core.py` under the local state directory, using one Hub-owned subscription set rather than per-chat installs. `HubPushMonitor` tails each active session's `.agent-index.jsonl`, filters out `user` / `system` senders, and emits a notification whose deep link targets `/session/<name>/?follow=1`.

This Hub-centric model matters because HTTPS origin scope decides which service worker and notification permission a browser trusts. In practice, installing the Hub once and subscribing there is enough; active session chats do not need their own installation to contribute background agent replies. Session-side push monitors stand down when Hub subscriptions exist, so the Hub becomes the single notification endpoint for the whole repo.

## 5. Logs / Export

`multiagent save` captures each pane with `tmux capture-pane -p -e`, writes the raw ANSI version to `.ans`, writes a stripped text-only version to `.log`, and updates `.meta` with created / updated timestamps and overwrite history. The chat server runs a background autosave thread and calls `runtime.save_logs(reason="autosave")` roughly every 120 seconds for active sessions.

`.agent-index.jsonl` and pane logs serve different purposes. JSONL is the canonical routing log. Pane logs are terminal snapshots. Hub preview, Stats, reply preview, and reconstruction of agent-to-agent traffic all use JSONL. Pane Trace and `.log` / `.ans` exist for the pane-side text view.

`ExportRuntime` builds a standalone HTML file around the chat payload. It embeds payload data, icons, and fonts when available, plus CDN fallbacks for scripts and CSS. Fetches such as `/messages` and `/trace` are replaced with export-local shims, so the downloaded HTML can be opened as a static viewer without a live server.

## 6. Robustness and Recovery

### tmux command wrapper

All tmux subprocess calls from `hub_core.py` go through `tmux_run()`, which returns a `TmuxRunResult` dataclass carrying `args`, `returncode`, `stdout`, `stderr`, and a `timed_out` flag. The default timeout is 2 seconds for read operations and 4 seconds for destructive operations like `kill-session`. When a subprocess exceeds its timeout, `TmuxRunResult.timed_out` is set to `True` and `returncode` is set to 124 (the conventional timeout exit code). This result object is duck-type-compatible with `subprocess.CompletedProcess`, so existing callers that check `.returncode` and `.stdout` continue to work without changes.

### Unhealthy vs missing

Session queries (`repo_sessions_query()`, `active_session_records()`) return a `RepoSessionsQueryResult` with a `state` field that is either `"ok"` or `"unhealthy"`, plus an optional `detail` string. The `"unhealthy"` state is set only when a tmux command timed out, never when it returned a non-zero exit code for normal reasons such as a session not existing. This distinction prevents the Hub from treating a slow tmux server as evidence that all sessions are gone. When the state is `"unhealthy"`, the Hub returns HTTP 503 instead of 404, and the UI shows a temporary-failure message rather than an empty session list.

### Session revive guards

`revive_archived_session()` runs a sequence of pre-checks before launching a session:

1. Query tmux health. If `"unhealthy"`, abort immediately with a descriptive error.
2. Check whether the session is already active. If so, return success without relaunching.
3. Look up the archived record to retrieve the stored workspace path and agent set.
4. Verify the workspace directory still exists and is accessible.

After launching, the system polls up to 80 times at 150ms intervals (roughly 12 seconds total). Between polls it re-checks tmux health; if tmux becomes unresponsive during startup, the revive is aborted rather than left waiting indefinitely.

### Pane log protection

`_save_pane_logs_to_dir()` in `bin/multiagent` writes each pane capture to a temporary file (`${ans_file}.tmp.$$`) before comparing it against the existing snapshot. The protection trigger fires when the old file exceeds 1 KB and the new capture is less than half that size. When triggered, the old `.ans` and `.log` are copied to `${instance}.${timestamp}.protected.ans` and `.protected.log` before the new content overwrites them. The warning is also logged to stderr with old and new byte counts.

This mechanism detects pane resets caused by agent process restarts, tmux pane clears, or session re-creation. Without it, the two-minute autosave cycle would silently replace a full terminal history with a near-empty buffer.

### Delete path validation

`delete_session()` in `hub_core.py` resolves the target path and checks it against a whitelist of allowed roots: the central log directory, the legacy log directory, and the local state workspace directory. If the resolved path falls outside all allowed roots, the delete is refused. This prevents path-traversal attacks or accidental deletion of unrelated directories through crafted session names.

### `.meta` structure

Each session directory contains a `.meta` JSON file maintained by `_update_session_meta()`:

```json
{
  "session": "multiagent",
  "workspace": "/path/to/workspace",
  "created_at": "2026-03-29 10:15:32",
  "updated_at": "2026-03-29 12:30:00",
  "overwrite_count": 5,
  "agents": ["claude", "codex", "gemini"],
  "overwrites": [
    {"timestamp": "2026-03-29 10:15:32", "reason": "initial"},
    {"timestamp": "2026-03-29 10:17:22", "reason": "autosave"},
    {"timestamp": "2026-03-29 12:30:00", "reason": "manual"}
  ]
}
```

`created_at` is preserved across saves. `updated_at` and the `overwrites` array are appended on every save. The `reason` field distinguishes `"initial"`, `"autosave"`, `"manual"`, `"kill"`, and other lifecycle events, making it possible to reconstruct when and why each snapshot was taken.

## 7. LAN / Public Access

`bin/agent-index` serves both the chat server and the Hub server. When certificate paths are available it listens with HTTPS. On startup it prints both local and LAN URLs, and session URLs follow `/session/<name>/`.

Optional public access is handled by `bin/multiagent-cloudflare` and `bin/multiagent-public-edge`. The public edge is a lightweight reverse proxy that sits between Cloudflare and the local Hub / chat servers. It forwards requests to the appropriate local port based on the session name in the URL path, and shares the same incremental message loading logic as the local chat server through `lib/agent_index/file_core.py`.

Quick Tunnel manages temporary public URLs. Named tunnel manages a fixed hostname and DNS. `access-enable` / `access-disable` update Cloudflare Access metadata and config. `daemon-install` adds a watchdog for keeping the public edge alive after login. All of these paths preserve the same local Hub / chat URL structure and place a public hostname in front of it.

The public edge applies the same tmux health awareness as the local Hub. When tmux is unresponsive, session pages return 503 rather than attempting to revive or returning stale data. Session revive through the public edge also checks tmux health before proceeding.

## Related Docs

- [README.en.md](../README.en.md): public-facing feature overview
- [docs/design-philosophy.en.md](design-philosophy.en.md): why the system is shaped this way
- [docs/AGENT.md](AGENT.md): operating guide for agents inside this environment
- [docs/cloudflare-quick-tunnel.md](cloudflare-quick-tunnel.md): Quick Tunnel / named tunnel
- [docs/cloudflare-access.md](cloudflare-access.md): public Hub with Cloudflare Access
- [docs/cloudflare-daemon.md](cloudflare-daemon.md): public daemon mode
