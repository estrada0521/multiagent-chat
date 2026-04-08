# multiagent-chat v1.0.8

Japanese version: [README_jp.md](README_jp.md)

Latest update notes: [docs/updates/README.md](docs/updates/README.md) / [v1.0.8](docs/updates/beta-1.0.8.md)

Website: [https://okadaharuto.com/multiagent-chat/](https://okadaharuto.com/multiagent-chat/) / [Japanese site](https://okadaharuto.com/multiagent-chat/ja/)

`multiagent-chat` is a local tmux-based workbench for running multiple AI agents side by side inside one session and controlling that session from a Hub plus chat UI. `bin/multiagent` creates tmux sessions where window 0 is reserved for the human terminal and each agent instance gets its own tmux window, `bin/agent-index` serves the Hub / chat UI / log viewer, and `bin/agent-send` routes structured messages between agents.

Conversation history is stored in `.agent-index.jsonl`, while pane output is stored separately as `.log` and `.ans`. The Hub handles session creation, resume, stats, and settings. The chat UI handles target selection, file references, memory, pane actions, and export. The same Hub and chat UI can also be opened from a phone on the same LAN.

The design assumes that a session may be stopped and resumed later, and that long-lived context should be split by role instead of collapsed into a single mutable note. Permanent rules, per-agent summaries, structured chat logs, and direct pane captures are stored separately so they remain easier to revisit over time.

The same Hub and chat UI can be opened from a desktop browser or a phone browser. A session can be started on the Mac and then viewed from the same Hub / chat paths on both desktop and mobile.

## What It Can Do


| Area    | Contents                                                                                                                                                                                                 |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hub     | sidebar session list, draft-first New Session flow, archived revive, embedded chat switching, and Settings                                                                                                                         |
| Chat UI | user-to-agent and agent-to-agent conversation, attachments, file references, memory, pane actions, live runtime hints, and a mobile-first camera mode for instant photo / voice input |
| Logs    | structured `.agent-index.jsonl` message log, pane captures in `.log` / `.ans`, static HTML export                                                                                                                            |
| Backend | Auto mode, Awake, sound and browser notifications, local desktop/mobile workbench routing, and optional local HTTPS for secure browser features |


The current agent registry includes `claude`, `codex`, `gemini`, `kimi`, `copilot`, `cursor`, `grok`, `opencode`, `qwen`, and `aider`. The same base agent can be started more than once, and duplicate instances receive names such as `claude-1` and `claude-2`. Agent-to-agent handoff uses `agent-send` and is appended to `.agent-index.jsonl`. Human-side sends are recorded from chat events, and agent replies are indexed from native event logs, so the full multi-party conversation is preserved in one timeline.

### 1. New Session / Message Body



New sessions now start from the Hub sidebar. On desktop, pressing `New Session` opens the workspace picker immediately and then jumps straight into a draft chat. The session name is taken from the selected workspace directory, the composer opens right away, and tmux has not launched yet. The first message, together with the currently selected initial agents, decides which panes are actually created.

Once that first send happens, the session falls back to the normal tmux layout: operator terminal in window 0 and one tmux window per launched agent instance. Duplicate launches are still supported, so the same base CLI can back multiple agent windows inside one session and receive automatic suffixes such as `claude-1` and `claude-2`.

If the workspace does not already contain `docs/AGENT.md`, session creation copies the repo version into `workspace/docs/AGENT.md`. The intended first step after opening a new session is to send that `docs/AGENT.md` to the agents so they receive the operating rules for communication and command usage inside this environment. Once they are running, they can also use `agent-help` for a short command-first cheatsheet.

The message body shows not only user-to-agent requests, but also agent-to-agent traffic in the same timeline. Each message carries sender, targets, and `msg-id` metadata. The UI exposes copy and navigation into attached or referenced files.

The renderer supports headings, paragraphs, lists, blockquotes, inline code, fenced code blocks, tables, KaTeX / LaTeX math, and Mermaid diagrams. Agent-to-agent messages sent through `agent-send` and human/assistant exchanges indexed from event logs share the same structured JSONL timeline, so session history does not depend only on pane output.

### 1.5. Thinking / Pane Trace



Thinking rows appear while agents are running. On mobile, tapping a thinking row opens the embedded Pane Trace viewer. On desktop, the same click opens the selected agent's Pane Trace in a popup window. Pane Trace is a lightweight viewer for the pane side of the session. On desktop, the popup supports split views so multiple agents can be watched simultaneously, and agents can be switched or rearranged by tab or drag-and-drop.

Compared with the main tmux terminal window, the desktop Pane Trace popup is optimized as a browser-side viewer: scrollback is smoother, switching between agents is easier, and text selection or copy is more straightforward.

When a provider adapter or pane parser can recognize tool activity, the thinking row also shows a compact runtime hint under the live status, for example `Ran`, `Edited`, `ReadFile`, or `Grepped`. These hints are intentionally lightweight UI state rather than part of the canonical `.agent-index.jsonl` history.

On desktop, the `Terminal` action opens the real terminal window attached to the tmux session, with window 0 as the operator terminal and the agent windows available through normal tmux window switching. On mobile, the same action opens Pane Trace instead, so pane activity can still be monitored from a phone.

### 2. Composer / Input Modes



The composer opens as an overlay. On mobile it opens from the round `O` button. On desktop it opens from the same button or with a middle click. This keeps the message area larger while the composer is closed.

Slash commands are the entry point for send-mode and pane actions. The current commands are:

- `/memo`: a self memo; it can be sent with only Import attachments (and if no target is selected, normal sends also default to self)
- `/load`: send the current `memory.md` to the selected agent
- `/memory`: ask the selected agent to refresh its `memory.md`
- `/model`: send `model` to the selected pane
- `/up [count]` / `/down [count]`: send repeated up/down navigation to the selected pane
- `/restart` / `/resume` / `/ctrlc` / `/interrupt` / `/enter`: act on the currently selected agent panes

The fuller command and quick-action list lives in [docs/chat-commands.en.md](docs/chat-commands.en.md). README keeps only the overview.

`@` provides file-path autocomplete inside the workspace, so a relative path can be inserted directly into the conversation. Import is not a workspace lookup. It uploads files from the local device into the session uploads area. On mobile this includes photos or files stored on the phone. On desktop it also supports drag and drop. Images appear as thumbnails and other files appear as extension cards. Inline code file references (for example `` `lib/agent_index/chat_core.py` ``) are also linkified to the same file preview when they can be resolved.

The same quick-action row also exposes `Load` and `Save Memory`. Memory keeps the current per-agent state in `logs/<session>/memory/<agent>/memory.md`, while pre-update states accumulate in `memory.jsonl` snapshots.

### 2.5. Camera Mode

On mobile, the header menu exposes `Camera`, which opens a dedicated live-camera overlay instead of sending you into the normal composer first. The same surface is also available on desktop for testing. The overlay keeps one selected target agent, a live camera feed, overlaid recent agent replies, and a direct shutter action for instant photo sends.

Captured images are resized before upload and then sent through the normal uploads plus structured message path, so the conversation still lands back in `.agent-index.jsonl` like ordinary chat. Voice input also works inside the same overlay. When Web Audio access is available, the waveform reflects live microphone energy; when mobile browser policy blocks parallel audio analysis, the UI falls back to a looped waveform instead of appearing frozen.

### 3. Header

On desktop, the header menu also now exposes direct `Finder` and `Pane Trace` actions, so session navigation does not depend entirely on reopening the main terminal window.

#### 3-1. Branch Menu



The branch menu shows the current branch, git state, recent commits, and diffs. Current uncommitted changes are shown at the top of the menu, above the commit history and diff navigation. Each changed file can be opened in the editor, committed individually, or restored to `HEAD`, and there is also an `All` action for a whole-worktree commit. File names inside the diff are also links into the external editor, so a file mentioned by the conversation or shown in the diff can be opened without leaving the session flow.

#### 3-2. File Menu



The file menu collects files referenced inside the session. It supports previews for Markdown, code, images, audio, and other referenced files, plus `Open in Editor` for external-editor handoff. Files are grouped by category with counts and size labels, and the right-side arrow jumps back to the source message that referenced the file.

The Markdown preview uses typography close to the chat renderer, follows the configured agent font, and resolves local relative image references such as `![...](path)`. Markdown preview can also switch between dark and light themes from inside the preview itself, while code-oriented files open in a plain viewer and sound files have a dedicated preview. This makes the file menu the read-side counterpart to the file references that appear in the chat body.

#### 3-3. Add / Remove Agent



Agents can be added or removed from the header menu. These actions change the tmux window set for the session without deleting the existing `.agent-index.jsonl` history. Adding an agent creates a new agent window, removing an agent removes only that instance's window, and duplicate base agents are also handled here. After a layout change, a `Reload` is recommended so the visible targets and UI state are refreshed together.

The same substrate is also available from inside agent panes. An agent can run `multiagent add-agent --agent <base>` or `multiagent remove-agent --agent <instance>` directly, using the current pane's `MULTIAGENT_SESSION` / `MULTIAGENT_TMUX_SOCKET`. Topology changes are appended to `.agent-index.jsonl` as `system` entries, so UI-triggered and agent-triggered changes share the same timeline.

Topology changes are serialized per session. If multiple panes or the UI try to add or remove agents at the same time, instance naming and tmux state updates are applied one at a time instead of racing. Before each topology change, stale `MULTIAGENT_AGENTS` / `MULTIAGENT_PANE_*` state is also reconciled against the actual tmux windows, so orphaned or already-removed instances are pruned before the next add/remove runs.

### 4. Hub / Settings



The Hub is now a single workbench surface rather than a separate landing page plus chat page. On desktop, the session list stays in a left sidebar and the selected chat stays embedded on the right. On phones, opening the session list takes over the screen instead of squeezing chat and navigation together.

`Kill` applies to active sessions. It stops the tmux session and chat server, but keeps the saved logs and workspace metadata. That is why a killed session moves into the archived side and can later be brought back with `Revive` using the same session name, workspace, and agent set. `Delete` applies only to archived sessions and removes the stored log directory together with related thinking-time data, so a deleted session cannot be revived afterward. The distinction exists so that “stop for now” and “erase the stored history” are treated as different operations.

Settings centralizes the default Hub and chat behavior, but it is intentionally slimmer now. The visual baseline is fixed to the black-hole theme and desktop message width stays fixed at 900px. Auto mode is not autonomous task execution. It is the mode that automatically approves command-permission prompts from agents. On first startup, Auto mode, Awake, Sound notifications, and Browser notifications are off, so only the needed ones should be turned on from Settings.


| Setting                        | Meaning                                                                     |
| ------------------------------ | --------------------------------------------------------------------------- |
| User Messages / Agent Messages | choose fonts independently for user and agent bubbles                       |
| Message Text Size              | applies to message bodies, file cards, inline code, code blocks, and tables |
| Auto mode                      | auto-approve mode for agent command-permission prompts                      |
| Awake (prevent sleep)          | keep the machine awake                                                      |
| Sound notifications            | play OGG notification sounds from `sounds/`                                 |
| Browser notifications          | Hub-owned web push for background agent replies across all sessions         |
| Bold mode                      | set separate message-weight toggles for narrow and wide viewports           |
| Reopen behavior                | reopen with the newest 50 messages and progressively load older rows        |


Notification sounds are loaded directly from OGG files in `sounds/`. Regular chat notifications use random `notify_*.ogg` files, while `commit.ogg`, `awake.ogg`, and `mictest.ogg` are handled by name. See [sounds/README.en.md](sounds/README.en.md) for the file naming rules and replacement workflow.

When served over HTTPS, the Hub exposes an `App Install & Notifications` block in Settings. The intended flow is to install the Hub itself to the Home Screen or browser app shelf, allow browser notifications there, and use that single Hub install as the notification endpoint for all sessions. Individual session chats do not need to be installed separately for background agent replies. Notification taps can deep-link back into the source session, and supported installed-app environments can expose shortcuts such as New Session directly from the app icon.

### 5. Logs / Export

This repo keeps long-term consistency and history lookup in separate layers. Permanent repo- and environment-level rules live in `docs/AGENT.md`, per-agent summaries live in memory, the conversation itself lives in `.agent-index.jsonl`, and pane-side output lives in `*.ans` and `*.log`. In practice that means `docs/AGENT.md` is static, memory is an evolving summary, JSONL is the structured message log, and pane capture is the direct terminal record.

Messages sent through `agent-send` are appended to `.agent-index.jsonl` with `sender`, `targets`, and `msg-id`. Pane-side captures are stored as `*.ans` and `*.log`, with a `.meta` file tracking update timestamps and overwrite history.

The chat server autosaves pane logs roughly every two minutes for active sessions, and the `Save Log` action can force an immediate snapshot from the UI. That makes Pane Trace the live tail, while `.log` / `.ans` remain the stored snapshots. The autosave interval is server-side and does not depend on whether a browser tab is open or in the foreground.

Git commits made during the session are also logged. Each commit that touches the workspace is recorded with its hash and message, so the conversation log and the code history can be cross-referenced after the fact.

The `Export` action in the header menu downloads a static HTML snapshot of the recent chat history. The prompt controls how many recent messages are included, including the option to export all available messages. The exported HTML is self-contained and can be opened offline without the chat server running, and recent fixes keep its standalone layout much closer to the live chat view so attachment-heavy exports remain readable on desktop and mobile.

### 6. Robustness and Recovery

Sessions in this environment are designed to survive interruptions. The system distinguishes between a session that was stopped intentionally, a tmux server that is temporarily unresponsive, and a session that no longer exists. Each case is handled differently so that recovery does not cause more damage than the original problem.

#### Pane log protection

The chat server autosaves pane captures roughly every two minutes. Before each save, the new capture is written to a temporary file and its size is compared against the existing snapshot. If the old file is larger than 1 KB and the new capture is less than half that size, the system treats this as a pane reset: the old `.ans` and `.log` files are copied to timestamped `.protected.ans` / `.protected.log` files before the new content overwrites them. This means that if a tmux pane is unexpectedly cleared or an agent process restarts, the pre-reset terminal output is preserved for later inspection rather than silently replaced by the smaller post-reset buffer.

#### tmux health awareness

All tmux commands issued by the Hub and chat server go through a wrapper that enforces a timeout and captures whether the command succeeded, failed, or timed out. A timed-out tmux command is reported as `unhealthy` rather than `missing`. This distinction prevents the system from concluding that a session does not exist when tmux is merely slow or overloaded. When an unhealthy state is detected, destructive actions such as automatic session revival are blocked, and the Hub returns a 503 status instead of a 404 so the UI can show the correct state.

#### Session lifecycle: Kill, Revive, Delete

`Kill` stops a running session's tmux windows and chat server but keeps all saved logs, workspace metadata, and the `.meta` file intact. The session moves to the archived list and can later be brought back with `Revive`, which re-creates the tmux session using the stored workspace path and agent set. Before reviving, the system checks tmux health, confirms the workspace directory still exists, and polls for up to twelve seconds to verify the session actually came up. If tmux becomes unresponsive during this window, the revive is aborted with an error rather than left in an ambiguous state.

`Delete` applies only to archived sessions. It removes the stored log directory and associated thinking-time data. Paths are validated against a whitelist of allowed roots before deletion, so path-traversal attempts are refused. A deleted session cannot be revived.

#### Autosave and metadata

Every pane log save, whether triggered by the two-minute autosave, a manual `Save Log` from the UI, or a session kill, is recorded in the session's `.meta` file. This JSON file tracks the session name, workspace path, creation timestamp, last-updated timestamp, agent list, and an array of overwrite entries with their timestamps and reasons. The overwrite history makes it possible to tell when a session was last saved and why.

#### Layered storage

The separation between `.agent-index.jsonl` (structured message log), `.ans` / `.log` (pane captures), `.meta` (save history), and `memory` (per-agent summaries) means that losing one layer does not destroy the others. A corrupted pane capture does not affect the conversation log, and a cleared JSONL does not erase the terminal recordings. This layered approach is intentional: each artifact serves a different recovery or review purpose, and they are stored independently so partial failures remain partial.

## Quickstart

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

`./bin/quickstart` checks for `python3` and `tmux`, offers dependency guidance when needed, interactively checks and installs available agent CLIs, and asks once whether local HTTPS should be enabled. If needed it uses an existing `mkcert` or installs it before placing `multiagent`, `agent-index`, and `agent-send` into `~/.local/bin` and starting the Hub. It does not create an agent session yet. When a New Session is created later, missing CLIs for the selected agents are checked again.

That interactive CLI install path now also covers Kimi. Installing the binary is not the whole setup, though: before Kimi can actually answer in a pane, it still needs one login on this Mac via `kimi login` or `/login` inside the Kimi CLI.

After startup the terminal prints both `Hub:` and `Hub (LAN / phone):` URLs. On desktop, bookmark the `Hub:` URL so the entry page is easy to reopen. On a phone on the same Wi-Fi, open the `Hub (LAN / phone):` URL to use the same session list and chat UI. Mobile can create new sessions, enter workspace paths, and resume existing sessions as well.

Local HTTPS is optional. The quickstart branch works like this.

- `no`: start in plain HTTP. This is enough for same-Wi-Fi Safari / browser use.
- `yes`: start in HTTPS. Use this when you want Home Screen web-app behavior, Hub-based browser notifications, microphone access, or other secure browser features on iPhone / iPad.

When you choose `yes`, the Mac trusts the local CA automatically, and on macOS quickstart reveals `rootCA.pem` in Finder for you. Send that `rootCA.pem` file to the iPhone / iPad via AirDrop, Files, or Mail, install the certificate profile on the device, and then enable trust in `Settings > General > About > Certificate Trust Settings`. Never share `rootCA-key.pem`.

The `mkcert` local CA is different on each Mac. If you want to open `https://192.168...` from another Mac on the same iPhone / iPad, that Mac's `rootCA.pem` must also be installed and trusted separately.

Once local HTTPS is trusted on the device, open Hub Settings, use `Install This App`, and allow browser notifications there. The current notification model is Hub-centric: one installed Hub app can receive background agent replies from any active session.

After creating the first session, send the workspace copy of `docs/AGENT.md` to each agent so it learns the expected message path: human-facing messages are normal assistant output, and `agent-send` is reserved for agent-to-agent routing.

Auto mode, Awake, Sound notifications, and Browser notifications are off on the first launch. Turn on only the ones you want from Hub Settings.

## Updating / Removing

To update an existing install, pull the repo and rerun quickstart:

```bash
cd ~/multiagent-chat
git pull --ff-only
./bin/quickstart
```

This refreshes the repo files, reruns dependency / CLI / local HTTPS checks, and rewrites the `~/.local/bin` symlinks if needed. Existing sessions, logs, and archived history under `logs/` are kept.

To remove only the globally available commands, delete the symlinks quickstart installed:

```bash
rm -f ~/.local/bin/multiagent ~/.local/bin/agent-index ~/.local/bin/agent-send
```

If you want to remove the local install entirely, stop active sessions first before deleting the repo:

```bash
cd ~/multiagent-chat
bin/multiagent kill --all
rm -f ~/.local/bin/multiagent ~/.local/bin/agent-index ~/.local/bin/agent-send
cd ~
rm -rf ~/multiagent-chat
```

If you want to keep your saved logs or archived sessions, remove only the symlinks and keep the repo directory.

## Requirements

- `python3`
- `tmux`
- macOS or Linux

Homebrew is the easiest path on macOS.

## Main Commands


| Command                       | Purpose                                                       |
| ----------------------------- | ------------------------------------------------------------- |
| `./bin/quickstart`            | start the Hub with dependency checks                          |
| `./bin/multiagent`            | create, resume, list, save, and reconfigure sessions          |
| `./bin/agent-index`           | Hub sidebar shell, chat UI, Settings, and log/view endpoints  |
| `./bin/agent-send`            | send structured messages between agents                        |
| `./bin/agent-help`            | compact cheatsheet for agents running inside this environment |
| `./bin/multiagent-release`    | publish GitHub Releases from `docs/updates/beta-*.md`         |


## Docs

- [docs/updates/README.md](docs/updates/README.md): milestone update notes and release summaries
- [docs/updates/beta-1.0.8.md](docs/updates/beta-1.0.8.md): changes shipped in `v1.0.8`
- [docs/AGENT.md](docs/AGENT.md): operating guide for agents running inside this environment
- [docs/chat-commands.en.md](docs/chat-commands.en.md): chat UI commands, Pane Trace behavior, and quick actions
- [docs/design-philosophy.en.md](docs/design-philosophy.en.md): why tmux, chat, mobile access, and layered logs are combined this way
- [docs/technical-details.en.md](docs/technical-details.en.md): technical layout of sessions, message transport, logs, export, and state
- [docs/event-log-sync.en.md](docs/event-log-sync.en.md): provider-native event-log sync, cursor/claim control, and attribution safeguards
- [docs/http-api.en.md](docs/http-api.en.md): Hub/Chat HTTP route list with request/response shapes
- [docs/developer-guide.en.md](docs/developer-guide.en.md): contributor onboarding, module map, and test workflow
- [sounds/README.en.md](sounds/README.en.md): notification-sound file names and replacement rules
