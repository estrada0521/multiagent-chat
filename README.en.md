# multiagent-chat

A local tmux-based multi-agent chat/workbench. It runs multiple AI agents side by side and exposes a Hub plus chat UI for messaging, routing, and session log inspection.

## What It Can Do

### 0. Overview / Remote Control

The first remote-control case is LAN access.

- The Hub and chat UI can be opened from a phone on the same LAN.
- The model stays the same on desktop and phone: `Hub = session overview`, `chat UI = one session workspace`.

The public / custom-domain path exists later, but the first thing users encounter is same-LAN phone access.

### 1. New Session / Body

The main facts at this stage are:

- New sessions are created from the Hub.
- Workspace paths can be entered from the UI, including from mobile.
- The same base agent can be summoned more than once; duplicate instances get suffixes such as `-1` and `-2`.
- The message body is not limited to user-to-agent traffic. Agent-to-agent conversation is also supported.
- The message renderer supports multiple Markdown-oriented formats.

Supported body formats include:

| Type | Examples |
|------|------|
| Basic Markdown | headings, paragraphs, lists, blockquotes |
| Code | inline code, fenced code blocks |
| Tables | table rendering |
| Math | KaTeX / LaTeX math |
| Diagrams | Mermaid blocks |

<p align="center">
  <img src="screenshot/new_session-portrait.png" alt="Create new session" width="320">
  <img src="screenshot/message_body-portrait.png" alt="Chat message body" width="320">
</p>

The message body also exposes navigation and utility controls:

- copy button
- reply button
- jump to reply source
- jump to reply target
- open attached or referenced files

The important point is that agent-to-agent traffic is a first-class part of the session, not an afterthought.

### 1.5. Thinking / Pane Trace

Important implementation details:

- thinking rows are shown while agents are running
- Pane Trace refreshes every 100ms on LAN / local access
- public access falls back to 1.5s polling
- on desktop, `Terminal` opens the actual terminal window

<p align="center">
  <img src="screenshot/thinking.png" alt="Thinking state" width="320">
  <img src="screenshot/Pane_trace-portrait.png" alt="Pane trace" width="320">
</p>

Pane Trace is the pane-side counterpart to the structured chat log.

### 2. Input Modes

Opening the composer is slightly unusual by design.

- On mobile, it opens from the round `O` button.
- On desktop, it also opens via middle-mouse click.
- This keeps the message area larger while the composer is closed.

The four main input paths are slash commands, `@` commands, Import, and Brief.

#### Slash commands

Current slash commands:

| Command | Behavior |
|------|------|
| `/memo [text]` | self memo; body may be omitted when Import attachments exist |
| `/silent <text>` | one-shot raw send without the normal header |
| `/brief` / `/brief set <name>` | show or edit a brief |

#### `@` commands

`@` uses file path autocomplete inside the workspace.

#### Import

Import uploads files from the local device into the workspace.

- On mobile, this includes photos or other files stored on the phone.
- On desktop, drag and drop is also supported.
- Images get thumbnail cards; other files get extension cards.

#### Brief

Brief is the reusable session-local template layer.

<p align="center">
  <img src="screenshot/slash_command-portrait.png" alt="Slash commands" width="180">
  <img src="screenshot/atamrk_command-portrait.png" alt="@ command autocomplete" width="180">
  <img src="screenshot/import-portrait.png" alt="Import attachments" width="180">
  <img src="screenshot/brief-portrait.png" alt="Brief workflow" width="180">
</p>

### 3. Header

The header groups three categories of controls:

- branch menu
- file menu
- add / remove agent

#### 3-1. Branch Menu

Branch menu facts:

- current git state
- commit history
- diffs
- file-name click opens the external editor

<p align="center">
  <img src="screenshot/branch_menu.png" alt="Branch menu" width="300">
  <img src="screenshot/Git_diff-portrait.png" alt="Git diff view" width="300">
</p>

This keeps repository-side state visible from the chat surface.

#### 3-2. File Menu

The file menu supports:

- referenced-file listing
- Markdown, code, and sound-oriented previews
- external editor handoff
- jumping back to the source message from the right-side arrow

<p align="center">
  <img src="screenshot/file_menu.png" alt="File menu" width="240">
  <img src="screenshot/file_preview-portrait.png" alt="Markdown preview" width="240">
  <img src="screenshot/sound.png" alt="Sound file preview" width="240">
</p>

The file menu is a preview layer, not a replacement for the editor. When needed, it hands off cleanly to the external editor.

#### 3-3. Add / Remove Agent

Operational note:

- After add / remove agent, a `Reload` is recommended.

<p align="center">
  <img src="screenshot/Add_agent-portrait.png" alt="Add agent" width="320">
  <img src="screenshot/remove_agent-portrait.png" alt="Remove agent" width="320">
</p>

Duplicate base agents are supported through suffixed instance names.

### 4. HubTop / Stats / Settings

This section is where Hub-level and backend-facing features become visible.

<p align="center">
  <img src="screenshot/Hub_Top-portrait.png" alt="Hub top" width="240">
  <img src="screenshot/Stats-portrait.png" alt="Stats page" width="240">
  <img src="screenshot/settings-portrait.png" alt="Settings" width="240">
</p>

#### HubTop

- active / archived session lists
- recent previews
- entry points into chats
- New Session
- Stats
- Settings

#### Stats

| Card | Contents |
|------|------|
| Messages | total messages, by sender, by session |
| Thinking Time | total thinking time, by agent, by session |
| Activated Agents | agents above the message threshold |
| Commits | total commits, by session |

Daily grids:

- Messages per day
- Thinking time per day

#### Settings

| Group | Items |
|------|------|
| Theme | Theme |
| Chat Fonts | User Messages, Agent Messages |
| Text | Message Text Size |
| Reopen default | Default Message Count |
| Chat Defaults | Auto mode, Awake, Sound notifications, Read aloud (TTS) |
| Visual Effects | Starfield background |
| Black Hole Text Opacity | User Messages, Agent Messages |

### 5. Logging

Logging has two layers.

| File | Role |
|------|------|
| `.agent-index.jsonl` | structured chat log |
| `*.log` / `*.ans` | pane-side logs |

The first captures message routing and reply structure. The second captures terminal-side behavior.

### 6. Access From Outside

The first access mode to think about is LAN use:

- open the Hub from a phone on the same Wi-Fi / LAN
- create sessions and use the chat UI from the phone

After that, there is a separate path for custom-domain / Cloudflare-based exposure when extra setup is in place.

## Typical Flow

1. Start the Hub with `./bin/quickstart`
2. Open a session from the Hub
3. Pick target agents in the chat UI and send instructions
4. Use Brief / Memory when you want to stabilize context or reusable instructions
5. Leave the session and logs in place so the work can be resumed later

## Typical Use Cases

- delegate research or implementation to multiple agents in parallel
- keep user/agent/agent-to-agent conversation in one session
- periodically stabilize context with Brief / Memory
- monitor or resume work from a phone
- preserve results as logs or exported HTML

## Main Concepts

### Session-Based

The main unit of work is a tmux session. Each agent runs in its own pane, and the Hub treats active and archived sessions as first-class objects.

### Chat UI and Logs

The chat UI is more than a message box: it combines target selection, message history, session state, quick actions, and attachment flows. Logs are stored in `.agent-index.jsonl`, so they can be searched and revisited later.

### Brief and Memory

- Brief: reusable session-specific instruction templates
- Memory: per-agent summarized state

Briefs can be sent to selected targets. Memory is split into the current `memory.md` and historical snapshots in `memory.jsonl`.

### Local-First, Public When Needed

The default mode is local use. If needed, the Hub can be exposed through Cloudflare without turning the whole system into a public-first service.

## Quickstart

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

`./bin/quickstart` will:

- verify that `python3` and `tmux` exist
- guide or interactively install missing dependencies when possible
- check agent CLIs
- set up a multiagent session
- launch the Hub / chat UI

## Requirements

- `python3`
- `tmux`
- macOS or Linux

Homebrew is the easiest path on macOS.

## Main Commands

- `./bin/quickstart`: start the Hub with dependency checks
- `./bin/multiagent`: create, resume, and control sessions
- `./bin/agent-index`: browse sessions, open chat UI, inspect logs
- `./bin/agent-send`: send messages to the user inbox or other agents

## Docs

- [docs/AGENT.md](docs/AGENT.md): operating guide for agents running inside this environment
- [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md): Cloudflare Quick Tunnel / named tunnel setup
- [docs/cloudflare-access.md](docs/cloudflare-access.md): protect the public Hub with Cloudflare Access
- [docs/cloudflare-daemon.md](docs/cloudflare-daemon.md): keep the public tunnel alive as a daemon
