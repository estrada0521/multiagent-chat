# multiagent-chat beta 1.0.1

Japanese version: [README_jp.md](README_jp.md)

Latest update notes: [docs/updates/README.md](docs/updates/README.md) / [beta 1.0.1](docs/updates/beta-1.0.1.md)

`multiagent-chat` is a local tmux-based workbench for running multiple AI agents side by side inside one session and controlling that session from a Hub plus chat UI. `bin/multiagent` creates tmux sessions where window 0 is reserved for the human terminal and each agent instance gets its own tmux window, `bin/agent-index` serves the Hub / chat UI / log viewer, and `bin/agent-send` moves structured messages between the user, agents, and other agents.

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
| Backend | Auto mode, Awake, Sound notifications, Read aloud, optional public exposure with a ready-to-use Cloudflare path |

The current agent registry includes `claude`, `codex`, `gemini`, `copilot`, `cursor`, `grok`, `opencode`, `qwen`, and `aider`. The same base agent can be started more than once, and duplicate instances receive names such as `claude-1` and `claude-2`.

### 1. New Session / Message Body

<p align="center">
  <img src="screenshot/new_session-portrait.png" alt="Create new session" width="320">
  <img src="screenshot/message_body-portrait.png" alt="Chat message body" width="320">
</p>

New sessions are created from the Hub. The workspace path is entered from the UI and can also be typed from mobile. Each new session keeps the operator terminal in tmux window 0 and gives every agent instance its own tmux window. Duplicate agent launches are supported, so the same base CLI can back multiple agent windows inside one session. Instance suffixes are added automatically when needed.

If the workspace does not already contain `docs/AGENT.md`, session creation copies the repo version into `workspace/docs/AGENT.md`. The intended first step after opening a new session is to send that `docs/AGENT.md` to the agents so they receive the operating rules for communication and command usage inside this environment.

The message body shows not only user-to-agent requests, but also agent-to-agent traffic in the same timeline. Each message carries sender, targets, `msg-id`, and optional `reply-to` metadata. The UI exposes copy, reply start, jump-to-reply-source, jump-to-reply-target, and navigation into attached or referenced files.

The renderer supports headings, paragraphs, lists, blockquotes, inline code, fenced code blocks, tables, KaTeX / LaTeX math, and Mermaid diagrams. Messages sent through `agent-send` share the same structured log regardless of whether they are user-to-agent, agent-to-user, or agent-to-agent messages. Multi-target sends also preserve their `targets` and `reply-to` linkage in JSONL, so the session history does not depend only on pane output.

### 1.5. Thinking / Pane Trace

<p align="center">
  <img src="screenshot/thinking.png" alt="Thinking state" width="320">
  <img src="screenshot/Pane_trace-portrait.png" alt="Pane trace" width="320">
  <img src="screenshot/pane_trace_pc.png" alt="Pane trace desktop window" width="420">
</p>

Thinking rows appear while agents are running. On mobile, tapping a thinking row opens the embedded Pane Trace viewer. On desktop, the same click opens the selected agent's Pane Trace in a popup window. Pane Trace is a lightweight viewer for the pane side of the session. It refreshes every 100ms on local / LAN access and every 1.5 seconds on public access. If the JSONL log is the structured message history, Pane Trace is the live pane-side tail.

Compared with the main tmux terminal window, the desktop Pane Trace popup is optimized as a browser-side viewer: scrollback is smoother, switching between agents is easier, and text selection or copy is more straightforward.

On desktop, the `Terminal` action opens the real terminal window attached to the tmux session, with window 0 as the operator terminal and the agent windows available through normal tmux window switching. On mobile, the same action opens Pane Trace instead, so pane activity can still be monitored from a phone.

### 2. Composer / Input Modes

<p align="center">
  <img src="screenshot/slash_command-portrait.png" alt="Slash commands" width="180">
  <img src="screenshot/atamrk_command-portrait.png" alt="@ command autocomplete" width="180">
  <img src="screenshot/import-portrait.png" alt="Import attachments" width="180">
  <img src="screenshot/brief-portrait.png" alt="Brief workflow" width="180">
</p>

The composer opens as an overlay. On mobile it opens from the round `O` button. On desktop it opens from the same button or with a middle click. This keeps the message area larger while the composer is closed.

Slash commands are the entry point for send-mode and pane actions. The current commands are:

- `/memo`: a self memo; it can be sent with only Import attachments
- `/raw <text>`: a raw one-shot send without the normal header
- `/brief`: open the `default` brief
- `/brief set <name>`: open `brief_<name>.md`
- `/model`: send `model` to the selected pane
- `/up [count]` / `/down [count]`: send repeated up/down navigation to the selected pane
- `/restart` / `/resume` / `/interrupt` / `/enter`: act on the currently selected agent panes

The fuller command and quick-action list lives in [docs/chat-commands.en.md](docs/chat-commands.en.md). README keeps only the overview.

`@` provides file-path autocomplete inside the workspace, so a relative path can be inserted directly into the conversation. Import is not a workspace lookup. It uploads files from the local device into the session uploads area. On mobile this includes photos or files stored on the phone. On desktop it also supports drag and drop. Images appear as thumbnails and other files appear as extension cards.

Brief is the reusable session-local template layer. It is different from `docs/AGENT.md`, which holds permanent repo- or environment-level rules. Briefs are stored under `logs/<session>/brief/brief_<name>.md`, can be edited through `/brief` or `/brief set <name>`, and can be sent to the selected targets from the Brief button. `docs/AGENT.md` is the durable operating guide; brief is the session-specific working context.

The same quick-action row also exposes `Load` and `Save Memory`. Memory keeps the current per-agent state in `logs/<session>/memory/<agent>/memory.md`, while pre-update states accumulate in `memory.jsonl` snapshots. Brief is the shared session-local instruction layer; memory is the per-agent summary layer.

### 3. Header

#### 3-1. Branch Menu

<p align="center">
  <img src="screenshot/branch_menu.png" alt="Branch menu" width="300">
  <img src="screenshot/Git_diff-portrait.png" alt="Git diff view" width="300">
</p>

The branch menu shows the current branch, git state, recent commits, and diffs. Current uncommitted changes are shown at the top of the menu, above the commit history and diff navigation. File names inside the diff are also links into the external editor, so a file mentioned by the conversation or shown in the diff can be opened without leaving the session flow.

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

Agents can be added or removed from the header menu. These actions change the tmux window set for the session without deleting the existing `.agent-index.jsonl` history. Adding an agent creates a new agent window, removing an agent removes only that instance's window, and duplicate base agents are also handled here. After a layout change, a `Reload` is recommended so the visible targets and UI state are refreshed together.

### 4. Hub / Stats / Settings

<p align="center">
  <img src="screenshot/Hub_Top-portrait.png" alt="Hub top" width="240">
  <img src="screenshot/Stats-portrait.png" alt="Stats page" width="240">
  <img src="screenshot/settings-portrait.png" alt="Settings" width="240">
</p>

The Hub is the entry point for active and archived sessions. Active sessions show workspace path, agent set, chat count, and chat port. Archived sessions stay visible in a separate list and can be revived when their stored state is reusable. The Hub also links to New Session, Resume Sessions, Stats, and Settings.

`Kill` applies to active sessions. It stops the tmux session and chat server, but keeps the saved logs and workspace metadata. That is why a killed session moves into the archived side and can later be brought back with `Revive` using the same session name, workspace, and agent set. `Delete` applies only to archived sessions and removes the stored log directory together with related thinking-time data, so a deleted session cannot be revived afterward. The distinction exists so that “stop for now” and “erase the stored history” are treated as different operations.

Stats shows four top-level cards: Messages, Thinking Time, Activated Agents, and Commits. Messages are broken down by sender and by session. Thinking Time is broken down by agent and by session. Commits are broken down by session. In addition, the page renders daily grids for `Messages per day` and `Thinking time per day`.

Settings centralizes the default Hub and chat behavior. Auto mode is not autonomous task execution. It is the mode that automatically approves command-permission prompts from agents. On first startup, Auto mode, Awake, Sound notifications, and Read aloud (TTS) are off, so only the needed ones should be turned on from Settings.

| Setting | Meaning |
|------|------|
| Theme | switch Hub / chat theme |
| User Messages / Agent Messages | choose fonts independently for user and agent bubbles |
| Message Text Size | applies to message bodies, file cards, inline code, code blocks, and tables |
| Default Message Count | initial reopen count when a chat is loaded |
| Auto mode | auto-approve mode for agent command-permission prompts |
| Awake (prevent sleep) | keep the machine awake |
| Sound notifications | play OGG notification sounds from `sounds/` |
| Read aloud (TTS) | browser-based speech output |
| Starfield background | animated background for the Black Hole theme |
| Black Hole Text Opacity | separate opacity controls for user and agent text in the Black Hole theme |

Notification sounds are loaded directly from OGG files in `sounds/`. Regular chat notifications use random `notify_*.ogg` files, while `commit.ogg`, `awake.ogg`, `mictest.ogg`, and scheduled `HH-MM.ogg` files are handled by name. See [sounds/README.en.md](sounds/README.en.md) for the file naming rules and replacement workflow.

### 5. Logs / Export

This repo keeps long-term consistency and history lookup in separate layers. Permanent repo- and environment-level rules live in `docs/AGENT.md`, session-local reusable instructions live in brief files, per-agent summaries live in memory, the conversation itself lives in `.agent-index.jsonl`, and pane-side output lives in `*.ans` and `*.log`. In practice that means `docs/AGENT.md` is static, brief is semi-static, memory is an evolving summary, JSONL is the structured message log, and pane capture is the direct terminal record.

Messages sent through `agent-send` are appended to `.agent-index.jsonl` with `sender`, `targets`, `msg-id`, and `reply-to`. Pane-side captures are stored as `*.ans` and `*.log`, with a `.meta` file tracking update timestamps and overwrite history.

The chat server autosaves pane logs roughly every two minutes for active sessions, and the `Save Log` action can force an immediate snapshot from the UI. That makes Pane Trace the live tail, while `.log` / `.ans` remain the stored snapshots.

The `Export` action in the header menu downloads a static HTML snapshot of the recent chat history. The prompt controls how many recent messages are included, including the option to export all available messages.

## Quickstart

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

`./bin/quickstart` checks for `python3` and `tmux`, offers dependency guidance when needed, interactively checks and installs available agent CLIs, and asks once whether local HTTPS should be enabled. If needed it uses an existing `mkcert` or installs it before placing `multiagent`, `agent-index`, and `agent-send` into `~/.local/bin` and starting the Hub. It does not create an agent session yet. When a New Session is created later, missing CLIs for the selected agents are checked again.

After startup the terminal prints both `Hub:` and `Hub (LAN / phone):` URLs. On desktop, bookmark the `Hub:` URL so the entry page is easy to reopen. On a phone on the same Wi-Fi, open the `Hub (LAN / phone):` URL to use the same session list and chat UI. Mobile can create new sessions, enter workspace paths, and resume existing sessions as well.

Local HTTPS is optional. The quickstart branch works like this.
- `no`: start in plain HTTP. This is enough for same-Wi-Fi Safari / browser use.
- `yes`: start in HTTPS. Use this when you want Home Screen web-app behavior, microphone access, or other secure browser features on iPhone / iPad.

When you choose `yes`, the Mac trusts the local CA automatically, and on macOS quickstart reveals `rootCA.pem` in Finder for you. Send that `rootCA.pem` file to the iPhone / iPad via AirDrop, Files, or Mail, install the certificate profile on the device, and then enable trust in `Settings > General > About > Certificate Trust Settings`. Never share `rootCA-key.pem`.

The `mkcert` local CA is different on each Mac. If you want to open `https://192.168...` from another Mac on the same iPhone / iPad, that Mac's `rootCA.pem` must also be installed and trusted separately.

After creating the first session, send the workspace copy of `docs/AGENT.md` to each agent so it learns the expected reply path and the `agent-send` conventions used in this environment.

Auto mode, Awake, Sound notifications, and Read aloud (TTS) start off on the first launch. Turn on only the ones you want from Hub Settings.

## Public Access (Optional)

<p align="center">
  <img src="cloudflare-color.svg" alt="Cloudflare" width="84">
</p>

By the time `./bin/quickstart` is done, local or same-LAN use is already set up. Public exposure is an extra layer you add afterward. Once a public URL is added, the same Hub and chat UI can be opened from outside your LAN in a normal browser. Public exposure does not have to use Cloudflare, but this repo already ships a ready-to-use Cloudflare path with commands and docs. The flow below is the shortest route if you choose Cloudflare.

What a public URL enables:
- open the Hub from outside the LAN at `https://<your-hostname>/`
- keep each chat under `/session/<name>/...`
- do the same phone-based session browsing, creation, workspace-path entry, and chat operations from outside the LAN
- keep this separate from local HTTPS / `mkcert`; a public URL does not require installing the local CA on iPhone

What you need to prepare for the Cloudflare path:
- `cloudflared` on the Mac
- for a stable hostname, your own domain already managed as a Cloudflare zone
- Cloudflare Zero Trust / Access settings so the public hostname is restricted
- a setup that keeps the Mac awake while you want outside access

The practical Cloudflare flow is:

1. Try temporary public access first
```sh
bin/multiagent-cloudflare quick-start
```
- this gives you a temporary `https://...trycloudflare.com` URL through Quick Tunnel
- use `bin/multiagent-cloudflare quick-stop` to return to local-only mode
- this is for short-lived testing only; it is not the recommended way to keep a Mac reachable from outside

2. Move to a stable hostname on your own domain
```sh
bin/multiagent-cloudflare named-login
bin/multiagent-cloudflare named-setup multiagent <your-hostname>
bin/multiagent-cloudflare named-start
```
- `named-login` runs the Cloudflare browser login and installs the origin cert
- `named-setup` creates or reuses the tunnel, routes DNS, and writes the config
- after `named-start`, the Hub lives at `https://<your-hostname>/`

3. Put Cloudflare Access in front of it
```sh
bin/multiagent-cloudflare access-enable <team-name> <aud-tag>
```
- this keeps the public Hub limited to your own or other allowed identities
- since this ultimately reaches your Mac, Access should be the default recommendation unless you have a specific reason not to use it

4. Install the daemon if you want it to stay up continuously
```sh
bin/multiagent-cloudflare daemon-install
```
- this keeps the named tunnel recovered in the background after login

5. Keep the Mac awake
- once the Mac goes to sleep, the public URL stops being reachable
- if you want stable long-lived access, keep the Mac on power and prevent sleep while the tunnel is meant to stay available
- one practical setup is to leave the Mac connected to a power-delivering external display and let only the screen go dark while the Mac itself stays awake

Typical usage pattern:
- use `./bin/quickstart` for local / same-LAN work
- add Cloudflare only when you want to reach the same Hub from outside
- use Quick Tunnel only for short tests
- use named tunnel + your own domain + Cloudflare Access for real public access
- keep the Mac awake while you expect outside access to work

If you prefer another reverse proxy or tunnel, the conceptual model is the same: put a public hostname in front of the local/LAN Hub and add access control in front when needed. See [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md), [docs/cloudflare-access.md](docs/cloudflare-access.md), and [docs/cloudflare-daemon.md](docs/cloudflare-daemon.md) for the detailed Cloudflare steps.

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

- [docs/updates/README.md](docs/updates/README.md): milestone update notes and release summaries
- [docs/updates/beta-1.0.1.md](docs/updates/beta-1.0.1.md): changes shipped since the first `beta 1.0` README
- [docs/AGENT.md](docs/AGENT.md): operating guide for agents running inside this environment
- [docs/chat-commands.en.md](docs/chat-commands.en.md): chat UI commands, Pane Trace behavior, and quick actions
- [docs/design-philosophy.en.md](docs/design-philosophy.en.md): why tmux, chat, mobile access, and layered logs are combined this way
- [docs/technical-details.en.md](docs/technical-details.en.md): technical layout of sessions, message transport, logs, export, and state
- [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md): Cloudflare Quick Tunnel / named tunnel setup
- [docs/cloudflare-access.md](docs/cloudflare-access.md): protect the public Hub with Cloudflare Access
- [docs/cloudflare-daemon.md](docs/cloudflare-daemon.md): keep the public tunnel alive as a daemon
- [sounds/README.en.md](sounds/README.en.md): notification-sound file names and replacement rules
