# multiagent-chat

`multiagent-chat` is a local tmux-based workbench for running multiple AI agents side by side inside one session and controlling that session from a Hub plus chat UI. `bin/multiagent` creates tmux sessions and panes, `bin/agent-index` serves the Hub / chat UI / log viewer, and `bin/agent-send` moves structured messages between the user, agents, and other agents.

Conversation history is stored in `.agent-index.jsonl`, while pane output is stored separately as `.log` and `.ans`. The Hub handles session creation, resume, stats, and settings. The chat UI handles target selection, replies, file references, briefs, memory, pane actions, and export. The same Hub and chat UI can also be opened from a phone on the same LAN.

The design assumes that a session may be stopped and resumed later, and that long-lived context should be split by role instead of collapsed into a single mutable note. Permanent rules, session-local instructions, per-agent summaries, structured chat logs, and direct pane captures are stored separately so they remain easier to revisit over time.

<table align="center">
  <tr>
    <td align="center" valign="middle">
      <img src="mac.png" alt="multiagent-chat on Mac" width="420">
    </td>
    <td align="center" valign="middle">
      <img src="iPhone.png" alt="multiagent-chat on iPhone" width="210">
    </td>
  </tr>
</table>

The same Hub and chat UI can be opened from a desktop browser or a phone browser. A session can be started on the Mac and then viewed from the same Hub / chat paths on both desktop and mobile.

## What It Can Do

| Area | Contents |
|------|------|
| Hub | active / archived session lists, New Session, Resume, Stats, Settings |
| Chat UI | user-to-agent and agent-to-agent conversation, replies, attachments, file references, brief / memory, pane actions |
| Logs | structured `.agent-index.jsonl` message log, pane captures in `.log` / `.ans`, static HTML export |
| Backend | Auto mode, Awake, Sound notifications, Read aloud, optional Cloudflare-based exposure |

The current agent registry includes `claude`, `codex`, `gemini`, `copilot`, `cursor`, `grok`, `opencode`, `qwen`, and `aider`. The same base agent can be started more than once, and duplicate instances receive names such as `claude-1` and `claude-2`.

### 1. New Session / Message Body

<p align="center">
  <img src="screenshot/new_session-portrait.png" alt="Create new session" width="320">
  <img src="screenshot/message_body-portrait.png" alt="Chat message body" width="320">
</p>

New sessions are created from the Hub. The workspace path is entered from the UI and can also be typed from mobile. Duplicate agent launches are supported, so the same base CLI can back multiple panes inside one session. Instance suffixes are added automatically when needed.

If the workspace does not already contain `docs/AGENT.md`, session creation copies the repo version into `workspace/docs/AGENT.md`. The intended first step after opening a new session is to send that `docs/AGENT.md` to the agents so they receive the operating rules for communication and command usage inside this environment.

The message body shows not only user-to-agent requests, but also agent-to-agent traffic in the same timeline. Each message carries sender, targets, `msg-id`, and optional `reply-to` metadata. The UI exposes copy, reply start, jump-to-reply-source, jump-to-reply-target, and navigation into attached or referenced files.

The renderer supports headings, paragraphs, lists, blockquotes, inline code, fenced code blocks, tables, KaTeX / LaTeX math, and Mermaid diagrams. Messages sent through `agent-send` share the same structured log regardless of whether they are user-to-agent, agent-to-user, or agent-to-agent messages. Multi-target sends also preserve their `targets` and `reply-to` linkage in JSONL, so the session history does not depend only on pane output.

### 1.5. Thinking / Pane Trace

<p align="center">
  <img src="screenshot/thinking.png" alt="Thinking state" width="320">
  <img src="screenshot/Pane_trace-portrait.png" alt="Pane trace" width="320">
</p>

Thinking rows appear while agents are running. On mobile, tapping a thinking row opens Pane Trace. Pane Trace is a lightweight viewer for the pane side of the session. It refreshes every 100ms on local / LAN access and every 1.5 seconds on public access. If the JSONL log is the structured message history, Pane Trace is the live pane-side tail.

On desktop, the `Terminal` action opens the real terminal window. On mobile, the same action opens Pane Trace instead, so pane activity can still be monitored from a phone.

### 2. Composer / Input Modes

<p align="center">
  <img src="screenshot/slash_command-portrait.png" alt="Slash commands" width="180">
  <img src="screenshot/atamrk_command-portrait.png" alt="@ command autocomplete" width="180">
  <img src="screenshot/import-portrait.png" alt="Import attachments" width="180">
  <img src="screenshot/brief-portrait.png" alt="Brief workflow" width="180">
</p>

The composer opens as an overlay. On mobile it opens from the round `O` button. On desktop it opens from the same button or with a middle click. This keeps the message area larger while the composer is closed.

Slash commands are the entry point for send-mode and pane actions. The current commands are `/memo`, `/silent`, `/brief`, `/restart`, `/resume`, `/interrupt`, and `/enter`. `/memo` is a self memo and can be sent with only Import attachments. `/silent` performs a raw one-shot send without the normal header. `/brief` opens the `default` brief, while `/brief set <name>` opens `brief_<name>.md`. `/restart`, `/resume`, `/interrupt`, and `/enter` act on the currently selected agent panes.

`@` provides file-path autocomplete inside the workspace, so a relative path can be inserted directly into the conversation. Import is not a workspace lookup. It uploads files from the local device into the session uploads area. On mobile this includes photos or files stored on the phone. On desktop it also supports drag and drop. Images appear as thumbnails and other files appear as extension cards.

Brief is the reusable session-local template layer. It is different from `docs/AGENT.md`, which holds permanent repo- or environment-level rules. Briefs are stored under `logs/<session>/brief/brief_<name>.md`, can be edited through `/brief` or `/brief set <name>`, and can be sent to the selected targets from the Brief button. `docs/AGENT.md` is the durable operating guide; brief is the session-specific working context.

The same quick-action row also exposes `Load` and `Save Memory`. Memory keeps the current per-agent state in `logs/<session>/memory/<agent>/memory.md`, while pre-update states accumulate in `memory.jsonl` snapshots. Brief is the shared session-local instruction layer; memory is the per-agent summary layer.

### 3. Header

#### 3-1. Branch Menu

<p align="center">
  <img src="screenshot/branch_menu.png" alt="Branch menu" width="300">
  <img src="screenshot/Git_diff-portrait.png" alt="Git diff view" width="300">
</p>

The branch menu shows the current branch, git state, recent commits, and diffs. File names inside the diff are also links into the external editor, so a file mentioned by the conversation or shown in the diff can be opened without leaving the session flow.

#### 3-2. File Menu

<p align="center">
  <img src="screenshot/file_menu.png" alt="File menu" width="240">
  <img src="screenshot/file_preview-portrait.png" alt="Markdown preview" width="240">
  <img src="screenshot/sound.png" alt="Sound file preview" width="240">
</p>

The file menu collects files referenced inside the session. It supports previews for Markdown, code, images, audio, and other referenced files, plus `Open in Editor` for external-editor handoff. The right-side arrow jumps back to the source message that referenced the file.

The Markdown preview uses typography close to the chat renderer and resolves local relative image references such as `![...](path)`. Code-oriented files open in a plain viewer, and sound files have a dedicated preview. This makes the file menu the read-side counterpart to the file references that appear in the chat body.

#### 3-3. Add / Remove Agent

<p align="center">
  <img src="screenshot/Add_agent-portrait.png" alt="Add agent" width="320">
  <img src="screenshot/remove_agent-portrait.png" alt="Remove agent" width="320">
</p>

Agents can be added or removed from the header menu. These actions change the pane layout without deleting the existing `.agent-index.jsonl` history. Duplicate base agents are also handled here. After a layout change, a `Reload` is recommended so the visible targets and UI state are refreshed together.

### 4. Hub / Stats / Settings

<p align="center">
  <img src="screenshot/Hub_Top-portrait.png" alt="Hub top" width="240">
  <img src="screenshot/Stats-portrait.png" alt="Stats page" width="240">
  <img src="screenshot/settings-portrait.png" alt="Settings" width="240">
</p>

The Hub is the entry point for active and archived sessions. Active sessions show workspace path, agent set, chat count, and chat port. Archived sessions stay visible in a separate list and can be revived when their stored state is reusable. The Hub also links to New Session, Resume Sessions, Stats, and Settings.

`Kill` applies to active sessions. It stops the tmux session and chat server, but keeps the saved logs and workspace metadata. That is why a killed session moves into the archived side and can later be brought back with `Revive` using the same session name, workspace, and agent set. `Delete` applies only to archived sessions and removes the stored log directory together with related thinking-time data, so a deleted session cannot be revived afterward. The distinction exists so that “stop for now” and “erase the stored history” are treated as different operations.

Stats shows four top-level cards: Messages, Thinking Time, Activated Agents, and Commits. Messages are broken down by sender and by session. Thinking Time is broken down by agent and by session. Commits are broken down by session. In addition, the page renders daily grids for `Messages per day` and `Thinking time per day`.

Settings centralizes the default Hub and chat behavior.

| Setting | Meaning |
|------|------|
| Theme | switch Hub / chat theme |
| User Messages / Agent Messages | choose fonts independently for user and agent bubbles |
| Message Text Size | applies to message bodies, file cards, inline code, code blocks, and tables |
| Default Message Count | initial reopen count when a chat is loaded |
| Auto mode | default auto-mode state when a chat opens |
| Awake (prevent sleep) | keep the machine awake |
| Sound notifications | play notification sounds |
| Read aloud (TTS) | browser-based speech output |
| Starfield background | animated background for the Black Hole theme |
| Black Hole Text Opacity | separate opacity controls for user and agent text in the Black Hole theme |

### 5. Logs / Export

This repo keeps long-term consistency and history lookup in separate layers. Permanent repo- and environment-level rules live in `docs/AGENT.md`, session-local reusable instructions live in brief files, per-agent summaries live in memory, the conversation itself lives in `.agent-index.jsonl`, and pane-side output lives in `*.ans` and `*.log`. In practice that means `docs/AGENT.md` is static, brief is semi-static, memory is an evolving summary, JSONL is the structured message log, and pane capture is the direct terminal record.

Messages sent through `agent-send` are appended to `.agent-index.jsonl` with `sender`, `targets`, `msg-id`, and `reply-to`. Pane-side captures are stored as `*.ans` and `*.log`, with a `.meta` file tracking update timestamps and overwrite history.

The chat server autosaves pane logs roughly every two minutes for active sessions, and the `Save Log` action can force an immediate snapshot from the UI. That makes Pane Trace the live tail, while `.log` / `.ans` remain the stored snapshots.

The `Export` action in the header menu downloads a static HTML snapshot of the recent chat history. The prompt controls how many recent messages are included, including the option to export all available messages.

### 6. LAN / Public Access

<p align="center">
  <img src="cloudflare-color.svg" alt="Cloudflare" width="84">
</p>

The default mode is local or same-LAN use. When the Hub starts it also prints a LAN URL, so the same Hub and chat UI can be opened from a phone on the same Wi-Fi. Session browsing, new-session creation, workspace-path entry, and chat interaction are all available there.

Public exposure is optional. For temporary access, `bin/multiagent-cloudflare quick-start` uses a Quick Tunnel. For stable access on your own domain, run `bin/multiagent-cloudflare named-login`, `bin/multiagent-cloudflare named-setup multiagent <your-hostname>`, and `bin/multiagent-cloudflare named-start`. The Hub then stays at `https://<your-hostname>/`, and each chat stays under `/session/<name>/...`.

If needed, `bin/multiagent-cloudflare access-enable <team-name> <aud-tag>` adds Cloudflare Access in front of that public hostname. This keeps the same Hub and chat paths while requiring Access at the edge. Once that is configured, the same browser-based workflow can be used outside the LAN as well. A phone alone can open the public hostname, browse existing sessions, create new sessions, enter workspace paths, and operate the chat UI in the same way.

For always-on public access, `bin/multiagent-cloudflare daemon-install` can keep the named tunnel recovered in the background. See `docs/cloudflare-quick-tunnel.md`, `docs/cloudflare-access.md`, and `docs/cloudflare-daemon.md` for the detailed flow.

## Quickstart

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

`./bin/quickstart` checks for `python3` and `tmux`, offers dependency guidance when needed, interactively checks and installs available agent CLIs, installs `multiagent`, `agent-index`, and `agent-send` into `~/.local/bin`, and then starts the Hub. It does not create an agent session yet. When a New Session is created later, missing CLIs for the selected agents are checked again.

After startup the terminal prints both `Hub:` and `Hub (LAN / phone):` URLs. On desktop, bookmark the `Hub:` URL so the entry page is easy to reopen. On a phone on the same Wi-Fi, open the `Hub (LAN / phone):` URL to use the same session list and chat UI. Mobile can create new sessions, enter workspace paths, and resume existing sessions as well.

After creating the first session, send the workspace copy of `docs/AGENT.md` to each agent so it learns the expected reply path and the `agent-send` conventions used in this environment.

## Requirements

- `python3`
- `tmux`
- macOS or Linux

Homebrew is the easiest path on macOS.

## Main Commands

| Command | Purpose |
|------|------|
| `./bin/quickstart` | start the Hub with dependency checks |
| `./bin/multiagent` | create, resume, list, save, and reconfigure sessions |
| `./bin/agent-index` | Hub, chat UI, Stats, Settings, log viewer |
| `./bin/agent-send` | send messages to the user inbox or other agents |
| `./bin/multiagent-cloudflare` | optional public-access workflow |

## Docs

- [docs/AGENT.md](docs/AGENT.md): operating guide for agents running inside this environment
- [docs/technical-details.en.md](docs/technical-details.en.md): technical layout of sessions, message transport, logs, export, and state
- [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md): Cloudflare Quick Tunnel / named tunnel setup
- [docs/cloudflare-access.md](docs/cloudflare-access.md): protect the public Hub with Cloudflare Access
- [docs/cloudflare-daemon.md](docs/cloudflare-daemon.md): keep the public tunnel alive as a daemon
