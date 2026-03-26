# multiagent-chat

A local tmux-based multi-agent chat/workbench. It runs multiple AI agents side by side and exposes a Hub plus chat UI for messaging, routing, and session log inspection.

## What It Can Do

### 0. Overview / Remote Control

This environment is not limited to desktop use. The same Hub and chat UI model is meant to work from a phone as well, so remote control is part of the design rather than an afterthought. You can inspect existing sessions, create new ones, resend brief context, and keep track of progress from mobile without switching to a separate reduced interface.

The Hub is the overview layer and the chat UI is the per-session work surface. Keeping those two ideas separate makes the system easier to reason about, especially when multiple sessions are active. The same mental model carries over between desktop and phone, which is why remote use feels natural instead of bolted on.

### 1. New Session / Body

<p align="center">
  <img src="screenshot/new_session-portrait.png" alt="Create new session" width="320">
  <img src="screenshot/message_body-portrait.png" alt="Chat message body" width="320">
</p>

Getting started is straightforward: create a new session from the Hub and drop directly into the chat UI. Session creation is exposed as a first-class UI action instead of being hidden behind CLI-only setup, which makes the whole environment easier to approach.

The chat body is where the ongoing conversation lives. It preserves reply structure through `msg-id`, keeps attachments traceable, and makes the session readable later rather than only during the live exchange. Most importantly, this is not just user-to-agent chat. Agents can communicate with each other through `agent-send`, which means the environment supports real agent-to-agent handoff, not only a human broadcasting instructions one by one.

### 1.5. Thinking / Pane Trace

<p align="center">
  <img src="screenshot/thinking.png" alt="Thinking state" width="320">
  <img src="screenshot/Pane_trace-portrait.png" alt="Pane trace" width="320">
</p>

The thinking state gives immediate visibility into whether an agent is still working. In multi-agent sessions, waiting is part of the workflow, so even lightweight status visibility matters.

Pane Trace goes further by exposing what happened inside the pane itself. This is the operational counterpart to the structured chat log: the chat shows meaning and routing, while Pane Trace shows behavior and execution. Together they make debugging and post-hoc review much easier than in a plain chat transcript.

### 2. Input Modes

The input area is best understood through four main entry points: slash commands, `@` commands, Import, and Brief. Each of them changes not only what gets sent, but also what context is carried into the session.

Slash commands shape session behavior before the next message is sent. They expose tools such as memo and brief handling directly in the composer, so operational context stays close to the message flow.

`@` commands connect the local filesystem to the conversation. File path autocomplete makes concrete files part of the chat surface, which is critical when agents need exact source files, documents, or configs rather than vague summaries.

Import adds files into the conversation history itself. That means a file is not just temporarily uploaded; it becomes part of the traceable record of the session.

Brief is the reusable instruction layer. Instead of rewriting framing, roles, or constraints over and over, you can store them and resend them when needed, including to multiple agents.

<p align="center">
  <img src="screenshot/slash_command-portrait.png" alt="Slash commands" width="180">
  <img src="screenshot/atamrk_command-portrait.png" alt="@ command autocomplete" width="180">
  <img src="screenshot/import-portrait.png" alt="Import attachments" width="180">
  <img src="screenshot/brief-portrait.png" alt="Brief workflow" width="180">
</p>

### 3. Header

The header is not decoration. It is where repository context, file access, and session-level controls stay available without leaving the conversation.

#### 3-1. Branch Menu

<p align="center">
  <img src="screenshot/branch_menu.png" alt="Branch menu" width="300">
  <img src="screenshot/Git_diff-portrait.png" alt="Git diff view" width="300">
</p>

The branch menu exposes repository-side context such as commit history and diffs from the same place where the conversation happens. File names inside the diff view can be clicked to jump to an external editor, so inspecting a change and opening the underlying file is a continuous flow rather than a context switch.

#### 3-2. File Menu

<p align="center">
  <img src="screenshot/file_menu.png" alt="File menu" width="240">
  <img src="screenshot/file_preview-portrait.png" alt="Markdown preview" width="240">
  <img src="screenshot/sound.png" alt="Sound file preview" width="240">
</p>

The file menu is the gateway for opening referenced files inside the environment. It supports Markdown, source code, and additional formats such as sound-related files, which means the environment is not locked to a single narrow document type. When preview is not enough, the same flow still leads naturally into an external editor.

#### 3-3. Add / Remove Agent

<p align="center">
  <img src="screenshot/Add_agent-portrait.png" alt="Add agent" width="320">
  <img src="screenshot/remove_agent-portrait.png" alt="Remove agent" width="320">
</p>

Agents can be added or removed as the session evolves. That matters because multi-agent work is rarely static. You may start with one or two agents and then introduce a dedicated reviewer or implementer later, or remove an agent once its role is finished to keep the session manageable.

### 4. HubTop / Stats / Settings

<p align="center">
  <img src="screenshot/Hub_Top-portrait.png" alt="Hub top" width="240">
  <img src="screenshot/Stats-portrait.png" alt="Stats page" width="240">
  <img src="screenshot/settings-portrait.png" alt="Settings" width="240">
</p>

HubTop is the overview page for the whole environment. It shows session lists, recent activity, and entry points into active work. This is where the system stops feeling like a collection of panes and starts feeling like a persistent workspace.

Stats gives a higher-level view of the environment. Instead of focusing on one thread, it shows the broader shape of activity across sessions and messages.

Settings is where backend and runtime features become visible and controllable. Auto-mode, awake mode, sound behavior, and related operational features can be turned on or off there, which matters because long-running multi-agent sessions are as much about environment stability as about chat UX.

### 5. Logging

The logging system is one of the strongest parts of the project. `.agent-index.jsonl` stores structured chat messages, including routing and reply structure, while pane-side logs such as `*.log` and `*.ans` preserve what actually appeared in terminals.

That split is valuable because meaning and execution are not the same thing. The structured chat log tells you what was said and who it was sent to. The pane-side logs tell you what agents were actually doing. Together they make archived sessions, debugging, exports, and historical review much more reliable.

### 6. Access From Outside

The system is local-first, but it is clearly built with remote access in mind. Phone-based monitoring and control already fit naturally into the main UX, and Cloudflare-based exposure paths exist for cases where the Hub needs to be accessed from outside the local machine.

The important point is that remote access is not a separate toy interface. It extends the same Hub and chat UI model, which helps preserve context when moving between desktop and phone or when checking a running session from outside the main workstation.

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
