# multiagent-chat

Run Claude, Codex, Gemini, Copilot, Cursor, and more — all in one session, talking to each other and to you.

`multiagent-chat` is a local-first workbench for multi-agent development. It gives every AI agent its own execution environment while you control the session from a single chat interface that works on desktop and mobile.

No cloud dependency. No framework lock-in. Just tmux, a chat UI, and structured logs.

[GitHub](https://github.com/estrada0521/multiagent-chat) · [Full README](readme/) · [Design Philosophy](docs/design-philosophy.en.md) · [Japanese](ja/) · [Sample Export →](/multiagent-chat/sample/)

---

## Why This Exists

Most multi-agent setups force you to choose: either a rigid orchestration framework that breaks when models improve, or raw terminal chaos where you lose track of who said what.

This project takes a different path. The AI side stays close to bare execution — tmux panes, stdin/stdout, environment variables. The human side gets a proper chat interface with file references and mobile access. The bridge between them is a thin message transport (`agent-send`) and a structured log (`.agent-index.jsonl`) that captures the full multi-party conversation.

The result: you can run 8 agents in parallel, orchestrate them from your phone, and still `git blame` every line they touched.

## Get Started

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

That's it. The quickstart checks dependencies, offers to install available agent CLIs, and starts the Hub. Open the printed URL in your browser.

> **Requirements:** `python3`, `tmux`, macOS or Linux.

## macOS Desktop App

[**Download Multiagent-Chat-macOS.dmg →**](https://github.com/estrada0521/multiagent-chat/releases/latest)

The desktop app bundles the Hub and launches it automatically. No `git clone` or terminal setup needed.

> **Requirements:** macOS, `python3`, `tmux`  
> Install via Homebrew if missing: `brew install python tmux`

**First launch — Gatekeeper notice:**  
This app is not code-signed with an Apple Developer ID. macOS may show "damaged" or block it on first open.  
Run this once in Terminal after moving the app to Applications:
```
xattr -cr /Applications/Multiagent\ Chat.app
```
Then double-click to open normally.  
Alternatively: System Settings → Privacy & Security → **Open Anyway**

---

## Key Concepts

### One session, many agents

Create a session from the Hub, pick your agents, point them at a workspace. Each agent gets its own tmux window. You get a unified chat timeline showing every message — user-to-agent, agent-to-user, and agent-to-agent.

The current registry includes: `claude`, `codex`, `gemini`, `kimi`, `copilot`, `cursor`, `grok`, `opencode`, `qwen`, and `aider`. The same agent can run multiple instances (`claude-1`, `claude-2`). Agents can be added or removed mid-session without losing history.

### Chat, not terminals

The primary interface is a chat UI, not a wall of terminals. Messages carry sender, targets, and file attachments. The renderer handles Markdown, code blocks, tables, LaTeX, and Mermaid diagrams. You read a conversation, not scrollback.

Terminals aren't gone — they're one click away via Pane Trace, a live viewer that refreshes at 100ms on LAN. But you don't need to stare at them.

### Structured logs, not ephemeral output

Every message lands in `.agent-index.jsonl` with full metadata. Pane output is captured separately as `.log` / `.ans`. Git commits are recorded in the same timeline. Session state and per-agent memory each have their own layer.

This means you can export a session as a self-contained HTML file, cross-reference commits with the conversation that produced them, or pick up exactly where you left off after a reboot.

## What You Can Do

### 1. New Session / Message Body

Sessions are created from the Hub with a workspace picker that works on both desktop and mobile. The message body shows the full multi-party timeline — user messages, agent replies, and agent-to-agent collaboration all in one view.

Each message supports copy and inline file navigation. Multi-target sends are preserved in the structured log.

### 1.5. Thinking / Pane Trace

While agents work, thinking rows show live status with compact runtime hints — `Ran`, `Edited`, `ReadFile`, `Grepped`. Tap to open Pane Trace: a lightweight terminal viewer that lets you watch what agents are actually doing.

On desktop, Pane Trace opens in a popup with split views for watching multiple agents simultaneously. On mobile, it opens inline. Either way, it's smoother than switching tmux windows.

### 2. Composer / Input Modes

The composer supports slash commands (`/memo`, `/memory`, `/restart`), `@`-autocomplete for workspace files, and file imports from your device. Per-agent memory is managed from the same surface.

See [docs/chat-commands.en.md](docs/chat-commands.en.md) for the full command reference.

### 2.5. Camera Mode

Point your phone's camera at something — a whiteboard, a circuit board, a bug on screen — and send it directly to an agent. The camera overlay shows live agent replies over the viewfinder, so you can have a visual conversation without switching apps.

Voice input works in the same overlay. Photos are resized, uploaded, and delivered through the normal message path, so they appear in the conversation timeline like any other attachment.

### 3. Branch Menu / File Menu

The header exposes two navigation menus that keep code and file context inside the chat flow.

**Branch Menu** shows the current branch, git state, recent commits, and diffs. Uncommitted changes appear at the top, above the commit history. Each changed file can be opened in an editor, committed individually, or restored to `HEAD` — plus an `All` action for whole-worktree commits.

**File Menu** collects every file referenced during the session. It supports inline previews for Markdown, code, images, and audio, plus `Open in Editor` for external handoff. Files are grouped by category with counts and size labels, and each entry links back to the message that referenced it.

### 4. Hub / Settings

The Hub now behaves like a desktop workbench shell: a session list on the left and the selected chat on the right. New sessions start as draft chats, so picking a workspace is immediate and the first message decides which agents actually launch. `Kill` stops a session but preserves logs for later `Revive`. `Delete` permanently removes stored history.

Settings now focus on fonts, text size, Auto mode (auto-approve agent permission prompts), Awake, sound/browser notifications, and bold-mode behavior. Theme selection is fixed to the black-hole baseline.

### 5. Session Export

Export any session as a self-contained static HTML file. The export preserves the full conversation with attachments and renders offline without a running server.

**[View a live export sample →](sample/)**

## Design Principles

This project is built on a specific philosophy about how humans and AI agents should work together. The short version:

- **AI side: pure substrate.** Agents run in minimal, undecorated execution environments. No workflow engines, no fixed skill hierarchies, no scaffolding that ages poorly as models improve.
- **Human side: chat interface.** Message-centric, not terminal-centric. Works on desktop and mobile identically.
- **Transport: thin.** `agent-send` moves text. The UI interprets it. No heavy message bus.
- **Beyond the screen.** Camera, voice, and mobile/LAN access are first-class — the workspace is not limited to one desk setup.

Read the full philosophy: [docs/design-philosophy.en.md](docs/design-philosophy.en.md)

## Mobile & Local Access

The same Hub and chat UI work from any browser on your LAN. Local HTTPS is available for secure browser features such as notifications, microphone access, and PWA install on LAN devices.

## Commands

| Command | Purpose |
|---|---|
| `./bin/quickstart` | Start the Hub with dependency checks |
| `./bin/multiagent` | Create, resume, list, save sessions |
| `./bin/agent-index` | Hub shell, chat UI, Settings |
| `./bin/agent-send` | Send structured messages between agents |
| `./bin/agent-help` | Compact cheatsheet for agents |
| `./bin/multiagent-release` | Publish GitHub Releases from `docs/updates/beta-*.md` |

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
- [docs/event-log-sync.en.md](docs/event-log-sync.en.md) — provider-native event-log sync, cursor/claim rules, and attribution safeguards
- [docs/http-api.en.md](docs/http-api.en.md) — Hub/Chat route list with request/response shape
- [docs/developer-guide.en.md](docs/developer-guide.en.md) — contributor onboarding, module map, and test workflow
- [docs/AGENT.md](docs/AGENT.md) — operating guide for agents inside sessions
- [docs/updates/README.md](docs/updates/README.md) — release notes

---

<sub>v1.0.9 · [Latest changes](docs/updates/beta-1.0.9.md)</sub>
