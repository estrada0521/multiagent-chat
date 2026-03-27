# multiagent-chat Technical Details

Japanese version: [docs/technical-details.md](technical-details.md)

This document follows the flow of [README.en.md](../README.en.md), but explains the implementation side instead of the user-facing workflow. The focus here is how sessions, messages, logs, files, and UI state move through `bin/` and `lib/agent_index/`.

## 0. Code Map

The main responsibilities are split across session creation, message delivery, Hub / chat serving, and file / log / export support.

| File | Role |
|------|------|
| `bin/multiagent` | create tmux sessions, place agent panes, add / remove agents, save pane logs |
| `bin/agent-send` | deliver messages to `user`, agents, or `others`; inject sender header; retain `msg_id` / `reply-to` metadata; append JSONL |
| `bin/agent-index` | Hub, chat UI, Stats, Settings, and HTTP endpoints such as upload / trace / export |
| `lib/agent_index/chat_core.py` | chat-server runtime, message payload, pane status, trace, save log |
| `lib/agent_index/chat_assets.py` | chat UI HTML / CSS / JavaScript, composer, brief / memory, Pane Trace |
| `lib/agent_index/hub_core.py` | active / archived session discovery, Hub preview, Stats aggregation |
| `lib/agent_index/file_core.py` | file preview, raw file serving, external-editor handoff |
| `lib/agent_index/export_core.py` | standalone HTML export builder |
| `lib/agent_index/state_core.py` | persistence for Hub settings, chat ports, and thinking totals |
| `lib/agent_index/agent_registry.py` | supported agent CLIs, launch / resume flags, icon metadata |

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

`bin/multiagent` creates the tmux session, writes `MULTIAGENT_*` variables into it, and records workspace, log directory, tmux socket, pane IDs, and the active agent list. When the same base agent appears more than once, it generates suffixed instance names such as `claude-1` and `claude-2` so each pane variable stays unique. `multiagent add-agent` and `multiagent remove-agent` live at this layer as well.

The per-session chat UI is served by `bin/agent-index`. `ChatRuntime.payload()` returns JSON containing `session`, `workspace`, `port`, `targets`, and `entries`. The front-end in `chat_assets.py` turns that payload into bubbles, target chips, reply banners, and rich rendering. KaTeX and Mermaid are both rendered in the same front-end layer.

### `agent-send`

`agent-send` is the message transport for this environment. It does more than paste text into panes. It also writes the same message into `.agent-index.jsonl`, which makes user-to-agent, agent-to-user, and agent-to-agent traffic share one structured log.

Session resolution is ordered as `MULTIAGENT_SESSION`, current tmux session, a unique active session for the current workspace, and finally the startup state file. Targets can be `user`, `others`, a base agent name, a specific instance name, or a comma-separated fan-out. Sending to `claude` means all `claude-*` instances in the session, while `claude-1` means only that instance.

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

### `/send` and the raw path

Normal sends from the chat UI go through `POST /send`, and `ChatRuntime.send_message()` then calls `agent-send`. Raw or silent sends take a different route. They bypass `agent-send` and paste directly into tmux panes with a temporary tmux buffer. This is what powers the `Raw Send` button and `/raw`: a one-shot paste without the normal `[From: User]` header or `msg-id`.

## 1.5. Thinking / Pane Trace

`ChatRuntime.agent_statuses()` captures the last 20 lines of each pane and compares them with the previous snapshot to derive `running`, `idle`, `dead`, or `offline`. A short grace period keeps a pane in `running` immediately after a change, then it falls back to `idle` if output stops changing. The resulting statuses are passed into `state_core.update_thinking_totals_from_statuses()` so session- and agent-level thinking time can accumulate.

Pane Trace comes from `GET /trace?agent=<name>&lines=<n>`. `trace_content()` uses `tmux capture-pane -p -e` and either returns a tail window or a much larger scrollback. The front-end polls only the currently visible tab: every 100ms on local / LAN hosts, every 1.5 seconds on public hosts.

Thinking rows and Pane Trace are related but not identical. The thinking row is a status summary. Pane Trace is the pane-side text snapshot. The first is lightweight state; the second is actual pane content.

## 2. Composer / Input Modes

The composer is implemented as an overlay in `chat_assets.py`. It stays closed by default, opens from the `O` button on mobile, and from the same button or middle click on desktop. The lower action row holds send, mic, raw send, brief, memory, save log, and pane-control actions.

### Slash commands

Slash commands are defined in the front-end `SLASH_COMMANDS` array. Their backends are split between dedicated front-end handlers and the `/send` endpoint.

| Command | Technical behavior |
|------|------|
| `/memo [text]` | self-send to `user`; Import attachments are enough even without body text |
| `/raw <text>` | `POST /send` with `silent=true`, then direct tmux paste |
| `/brief` | open the `default` brief editor modal |
| `/brief set <name>` | open `brief_<name>.md` |
| `/model` | send `model` to the target pane |
| `/up [count]` | send up-navigation to the target pane |
| `/down [count]` | send down-navigation to the target pane |
| `/restart` | call `ChatRuntime.restart_agent_pane()` |
| `/resume` | resume the pane using the agent registry resume flag |
| `/interrupt` | send `Escape` to the target pane |
| `/enter` | send `Enter` to the target pane |

### `@` and Import

`@` insertion is the workspace-side file-reference path. The front-end inserts relative file paths into the conversation, and `/files-exist` validates them when needed. Import is a different pipeline. `POST /upload` stores the file body under `logs/<session>/uploads/<timestamp>_<hex>.<ext>`. The server returns the workspace-relative path, and the chat UI turns it into an attachment card.

### Brief and Memory

Brief is managed by `/briefs`, `GET /brief-content`, and `POST /brief-content` in `bin/agent-index`. Names are normalized into `brief_<name>.md` under `logs/<session>/brief/`. The Brief button first fetches the stored list, then reads the selected brief body, then sends it sequentially to the selected targets with `silent=true`.

Memory is stored per agent in `logs/<session>/memory/<agent>/memory.md`, with historical snapshots in `memory.jsonl`. When the Memory button is pressed, `POST /memory-snapshot` runs first and appends the current `memory.md` into `memory.jsonl`. Only after that does the front-end send the rewrite instruction to the target agent. Load is the reverse direction: read the current `memory.md` and send it back into the conversation.

## 3. Header

### Branch Menu

The branch menu is driven by git-overview and diff endpoints from the chat server. Current branch, dirty state, commit list, and diff chunks are fetched as JSON and rendered into the panel / carousel UI. `ChatRuntime.ensure_commit_announcements()` also compares the current `git log -1` result with the previously recorded commit state. When a new commit appears, it appends a `kind="git-commit"` system entry into JSONL. Stats later uses those system entries as the source of commit counts.

### File Menu

The file menu is powered by `FileRuntime`. Raw file delivery uses `/file-raw`, text content uses `/file`, and external-editor handoff uses `/open-file-in-editor`. `FileRuntime` picks preview mode from file extension and file content, switching among Markdown, image, PDF, video, audio, and plain text.

For Markdown previews, the renderer first turns Markdown into HTML, then rewrites relative `img src` paths so they resolve against the Markdown file and are served from `/file-raw?path=...`. `Open in Editor` first honors `MULTIAGENT_EXTERNAL_EDITOR` when provided, and otherwise falls back to CotEditor, VS Code, or a system opener depending on platform and file type.

### Add / Remove Agent

The add / remove agent modals are front-end controls. The actual layout change is delegated to `multiagent add-agent` and `multiagent remove-agent`. What changes here is the tmux pane layout and `MULTIAGENT_AGENTS`; the existing `.agent-index.jsonl` stays intact. The UI recommends `Reload` afterward because the visible target list and pane state need to be refreshed together.

## 4. Hub / Stats / Settings

`HubRuntime` reads both active tmux sessions and archived log directories. The active side comes from tmux session state plus `MULTIAGENT_*` environment, while the archived side comes from log directories, `.meta`, and `.agent-index.jsonl`. The Hub preview message is built by `latest_message_preview()`, which strips `[From: ...]` headers and `[Attached: ...]` markers before truncating the text.

Stats are built by `HubRuntime.build_stats_payload()`. Messages are deduplicated by `msg_id` when possible, then counted by sender and by session. Commits are deduplicated by `commit_hash` from `git-commit` system entries. Thinking time is loaded from `state_core.py`, and instance names are collapsed back to base agent names before display.

Settings flow through `state_core.load_hub_settings()` and `save_hub_settings()`. Shared Hub / chat settings are intentionally not stored in the repo tree. They live in the local state directory instead. Chat port overrides are saved in `.chat-ports.json`, Hub settings in `.hub-settings.json`, and thinking aggregates in `.thinking-time.json` plus `.thinking-runtime.json`.

## 5. Logs / Export

`multiagent save` captures each pane with `tmux capture-pane -p -e`, writes the raw ANSI version to `.ans`, writes a stripped text-only version to `.log`, and updates `.meta` with created / updated timestamps and overwrite history. The chat server runs a background autosave thread and calls `runtime.save_logs(reason="autosave")` roughly every 120 seconds for active sessions.

`.agent-index.jsonl` and pane logs serve different purposes. JSONL is the canonical routing log. Pane logs are terminal snapshots. Hub preview, Stats, reply preview, and reconstruction of agent-to-agent traffic all use JSONL. Pane Trace and `.log` / `.ans` exist for the pane-side text view.

`ExportRuntime` builds a standalone HTML file around the chat payload. It embeds payload data, icons, and fonts when available, plus CDN fallbacks for scripts and CSS. Fetches such as `/messages` and `/trace` are replaced with export-local shims, so the downloaded HTML can be opened as a static viewer without a live server.

## 6. LAN / Public Access

`bin/agent-index` serves both the chat server and the Hub server. When certificate paths are available it listens with HTTPS. On startup it prints both local and LAN URLs, and session URLs follow `/session/<name>/`.

Optional public access is handled by `bin/multiagent-cloudflare`. Quick Tunnel manages temporary public URLs. Named tunnel manages a fixed hostname and DNS. `access-enable` / `access-disable` update Cloudflare Access metadata and config. `daemon-install` adds a watchdog for keeping the public edge alive after login. All of these paths preserve the same local Hub / chat URL structure and place a public hostname in front of it.

## Related Docs

- [README.en.md](../README.en.md): public-facing feature overview
- [docs/design-philosophy.en.md](design-philosophy.en.md): why the system is shaped this way
- [docs/AGENT.md](AGENT.md): operating guide for agents inside this environment
- [docs/cloudflare-quick-tunnel.md](cloudflare-quick-tunnel.md): Quick Tunnel / named tunnel
- [docs/cloudflare-access.md](cloudflare-access.md): public Hub with Cloudflare Access
- [docs/cloudflare-daemon.md](cloudflare-daemon.md): public daemon mode
