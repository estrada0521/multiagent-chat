# multiagent-chat

A local tmux-based multi-agent chat/workbench. It runs multiple AI agents side by side and exposes a Hub plus chat UI for messaging, routing, and session log inspection.

<p align="center">
  <img src="screenshot/Hub_Top-portrait.png" alt="Hub overview" width="250">
  <img src="screenshot/message_body-portrait.png" alt="Chat UI" width="250">
  <img src="screenshot/new_session-portrait.png" alt="New session from mobile" width="250">
</p>

## What It Can Do

### Chat

The center of the system is the chat UI. From a user perspective, it is easiest to think of it as three parts: the message area, the composer, and the header.

It is not just a messenger window. It is a working surface for multi-agent sessions, where routing, file handoff, and session-level controls are kept close to the conversation itself.

<p align="center">
  <img src="screenshot/atamrk_command-portrait.png" alt="@ command autocomplete" width="230">
  <img src="screenshot/slash_command-portrait.png" alt="Slash commands" width="230">
  <img src="screenshot/import-portrait.png" alt="Import attachments" width="230">
</p>

In the message area, you can:

- follow user/agent conversation in order
- work with replies tied to `msg-id`
- follow file references embedded as `[Attached: ...]`
- preserve the structured chat log directly

The message area is designed for revisiting work later, not only for live conversation. Replies remain tied to `msg-id`, attached files stay traceable, and the chat itself becomes durable session history instead of disposable terminal output.

The composer can be understood as four main pieces.

1. Slash commands
Commands such as `/memo`, `/silent`, and `/brief` expose session tools directly from the input area.

<p align="center">
  <img src="screenshot/brief-portrait.png" alt="Brief workflow" width="230">
  <img src="screenshot/file_preview-portrait.png" alt="File preview" width="230">
  <img src="screenshot/Git_diff-portrait.png" alt="Git diff" width="230">
</p>

2. `@` commands
`@`-based path autocomplete turns local files into first-class chat references, which is important when you want agents to operate on a concrete file instead of vague descriptions.

3. Import
Import adds files directly into the conversation flow. Those files remain part of the session history rather than acting as a temporary upload detached from the chat.

4. Brief
Brief lets you keep reusable session-specific instructions and send them again without rewriting the same context every time.

Around those four pieces, the composer also contains target selection, raw send, voice input, and the ability to preview attached files. In practice, it works more like a control surface for preparing messages than a plain text box.

The header is easier to understand if you split it into two parts.

1. Header-level context tools
This includes commit history and the file menu. These are the places where you check repository-side state and open referenced content without leaving the chat.

2. Header-level session controls
This includes add-agent and remove-agent actions, which let you change the session structure from the same screen.

<p align="center">
  <img src="screenshot/Add_agent-portrait.png" alt="Add agent" width="230">
  <img src="screenshot/remove_agent-portrait.png" alt="Remove agent" width="230">
</p>

The header is the operational layer of the session rather than decoration. The mechanism behind all of this is `agent-send`, which makes user-to-agent and agent-to-agent communication explicit instead of leaving it as loose terminal output.

### Hub

The Hub is the entry point for session-level navigation.

If the chat UI is the workspace for one session, the Hub is the place where you orient yourself across all sessions. It is where you decide what to resume, archive, create, or inspect next.

<p align="center">
  <img src="screenshot/Stats-portrait.png" alt="Stats page" width="230">
</p>

- active / archived session list
- session overview with latest previews
- links into each session chat UI
- new session creation
- settings
- statistics page

It also works as the main control surface when accessed from mobile or public routes. In practice, this makes the system feel less like a single terminal trick and more like a persistent local environment for ongoing agent work.

### Logs

There are two main logging layers.

<p align="center">
  <img src="screenshot/Pane_trace-portrait.png" alt="Pane trace" width="250">
</p>

- `.agent-index.jsonl`
  structured chat-message logs
- `*.log` / `*.ans`
  pane-capture logs from the terminal side

Together they let you keep:

- the chat flow itself
- what happened inside agent panes
- archived sessions for later review
- the source material for exports

So the system keeps both conversation history and pane-side traces. `.agent-index.jsonl` is useful when you want the semantic flow of the conversation, while pane traces are useful when you need to understand what an agent was actually doing in its terminal.

### Backend / runtime features

There are also runtime features that support longer multi-agent sessions.

<p align="center">
  <img src="screenshot/settings-portrait.png" alt="Runtime settings" width="230">
</p>

- Auto-mode
  helper mode that detects permission prompts and auto-approves them
- Awake mode
  uses `caffeinate` to keep the machine awake
- Sound notifications
  notification sounds, commit sounds, and scheduled sounds
- mobile / public access
  remote control from a phone and public Hub operation
- export
  standalone HTML export of sessions

This layer matters because multi-agent work is often long-running and interruption-prone. Auto-approval helpers, awake mode, sounds, export, and mobile/public access are all there to make sessions survivable over longer stretches, not only convenient during the first five minutes.

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
