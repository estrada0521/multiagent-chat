# multiagent-chat

Run Claude, Codex, Gemini, Copilot, Cursor, and more — all in one session, talking to each other and to you.

`multiagent-chat` is a local-first workbench for multi-agent development. It gives every AI agent its own execution environment while you control the session from a single chat interface that works on desktop and mobile.

No cloud dependency. No framework lock-in. Just tmux, a chat UI, and structured logs.

[GitHub](https://github.com/estrada0521/multiagent-chat) · [Full README](readme/) · [Design Philosophy](docs/design-philosophy.en.md) · [Japanese](ja/) · [Sample Export →](/multiagent-chat/sample/)

---

## Why This Exists

Most multi-agent setups force you to choose: either a rigid orchestration framework that breaks when models improve, or raw terminal chaos where you lose track of who said what.

This project takes a different path. The AI side stays close to bare execution — tmux panes, stdin/stdout, environment variables. The human side gets a proper chat interface with replies, file references, and mobile access. The bridge between them is a thin message transport (`agent-send`) and a structured log (`.agent-index.jsonl`) that captures the full multi-party conversation.

The result: you can run 8 agents in parallel, orchestrate them from your phone, and still `git blame` every line they touched.

## Get Started

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

That's it. The quickstart checks dependencies, offers to install available agent CLIs, and starts the Hub. Open the printed URL in your browser.

> **Requirements:** `python3`, `tmux`, macOS or Linux.

## Key Concepts

### One session, many agents

Create a session from the Hub, pick your agents, point them at a workspace. Each agent gets its own tmux window. You get a unified chat timeline showing every message — user-to-agent, agent-to-user, and agent-to-agent.

The current registry includes: `claude`, `codex`, `gemini`, `kimi`, `copilot`, `cursor`, `grok`, `opencode`, `qwen`, and `aider`. The same agent can run multiple instances (`claude-1`, `claude-2`). Agents can be added or removed mid-session without losing history.

### Chat, not terminals

The primary interface is a chat UI, not a wall of terminals. Messages carry sender, targets, reply chains, and file attachments. The renderer handles Markdown, code blocks, tables, LaTeX, and Mermaid diagrams. You read a conversation, not scrollback.

Terminals aren't gone — they're one click away via Pane Trace, a live viewer that refreshes at 100ms on LAN. But you don't need to stare at them.

### Structured logs, not ephemeral output

Every message lands in `.agent-index.jsonl` with full metadata. Pane output is captured separately as `.log` / `.ans`. Git commits are recorded in the same timeline. Session state, briefs, and per-agent memory each have their own layer.

This means you can export a session as a self-contained HTML file, cross-reference commits with the conversation that produced them, or pick up exactly where you left off after a reboot.

## What You Can Do

### 1. New Session / Message Body

Sessions are created from the Hub with a workspace picker that works on both desktop and mobile. The message body shows the full multi-party timeline — user messages, agent replies, and agent-to-agent collaboration all in one view.

Each message supports copy, reply, jump-to-source, and inline file navigation. Multi-target sends and reply chains are preserved in the structured log.

### 1.5. Thinking / Pane Trace

While agents work, thinking rows show live status with compact runtime hints — `Ran`, `Edited`, `ReadFile`, `Grepped`. Tap to open Pane Trace: a lightweight terminal viewer that lets you watch what agents are actually doing.

On desktop, Pane Trace opens in a popup with split views for watching multiple agents simultaneously. On mobile, it opens inline. Either way, it's smoother than switching tmux windows.

### 2. Composer / Input Modes

The composer supports slash commands (`/brief`, `/cron`, `/gemini`, `/restart`), `@`-autocomplete for workspace files, and file imports from your device. Brief templates and per-agent memory are managed from the same surface.

See [docs/chat-commands.en.md](docs/chat-commands.en.md) for the full command reference.

### 2.5. Camera Mode

Point your phone's camera at something — a whiteboard, a circuit board, a bug on screen — and send it directly to an agent. The camera overlay shows live agent replies over the viewfinder, so you can have a visual conversation without switching apps.

Voice input works in the same overlay. Photos are resized, uploaded, and delivered through the normal message path, so they appear in the conversation timeline like any other attachment.

### 3. Branch Menu / File Menu

The header exposes two navigation menus that keep code and file context inside the chat flow.

**Branch Menu** shows the current branch, git state, recent commits, and diffs. Uncommitted changes appear at the top, above the commit history. Each changed file can be opened in an editor, committed individually, or restored to `HEAD` — plus an `All` action for whole-worktree commits.

**File Menu** collects every file referenced during the session. It supports inline previews for Markdown, code, images, and audio, plus `Open in Editor` for external handoff. Files are grouped by category with counts and size labels, and each entry links back to the message that referenced it.

### 4. Hub / Stats / Settings

The Hub manages active and archived sessions. `Kill` stops a session but preserves logs for later `Revive`. `Delete` permanently removes stored history. Stats tracks messages, thinking time, activated agents, and commits across sessions.

Settings controls themes, fonts, text size, Auto mode (auto-approve agent permission prompts), Awake, sound/browser notifications, and TTS read-aloud.

### 5. Session Export

Export any session as a self-contained static HTML file. The export preserves the full conversation with attachments and renders offline without a running server.

**[View a live export sample →](sample/)**

## Design Principles

This project is built on a specific philosophy about how humans and AI agents should work together. The short version:

- **AI side: pure substrate.** Agents run in minimal, undecorated execution environments. No workflow engines, no fixed skill hierarchies, no scaffolding that ages poorly as models improve.
- **Human side: chat interface.** Message-centric, not terminal-centric. Works on desktop and mobile identically.
- **Transport: thin.** `agent-send` moves text. The UI interprets it. No heavy message bus.
- **Beyond the screen.** Camera, voice, and remote access are first-class — the workspace is not limited to your desk.

Read the full philosophy: [docs/design-philosophy.en.md](docs/design-philosophy.en.md)

## Mobile & Remote Access

The same Hub and chat UI work from any browser on your LAN. For access outside your network, the repo includes a ready-to-use Cloudflare tunnel path:

```bash
# Quick test (temporary URL)
bin/multiagent-cloudflare quick-start

# Stable hostname on your domain
bin/multiagent-cloudflare named-setup multiagent your-hostname.com
bin/multiagent-cloudflare named-start
```

Local HTTPS is also available for secure browser features (notifications, microphone, PWA install) on LAN devices.

## Commands

| Command | Purpose |
|---|---|
| `./bin/quickstart` | Start the Hub with dependency checks |
| `./bin/multiagent` | Create, resume, list, save sessions |
| `./bin/agent-index` | Hub, chat UI, Stats, Settings |
| `./bin/agent-send` | Send messages between user and agents |
| `./bin/agent-help` | Compact cheatsheet for agents |

## Updating

```bash
cd ~/multiagent-chat
git pull --ff-only
./bin/quickstart
```

Existing sessions, logs, and archived history are preserved.

## Docs

- [docs/design-philosophy.en.md](docs/design-philosophy.en.md) — why this project is built the way it is
- [docs/chat-commands.en.md](docs/chat-commands.en.md) — full command and quick-action reference
- [docs/technical-details.en.md](docs/technical-details.en.md) — sessions, transport, logs, export, state
- [docs/AGENT.md](docs/AGENT.md) — operating guide for agents inside sessions
- [docs/updates/README.md](docs/updates/README.md) — release notes

---

<sub>beta 1.0.5 · [Latest changes](docs/updates/beta-1.0.5.md)</sub>
