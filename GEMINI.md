# Multiagent Project Overview

This project is a sophisticated development environment that orchestrates multiple AI agents (e.g., Claude, Gemini, Codex, Copilot) within **tmux** sessions, providing a unified web-based Chat UI for interaction.

## Core Architecture

- **Backend**: Uses `tmux` to run independent agents in separate panes.
- **Server (`agent-index`)**: A Python-based server that provides both a real-time Chat UI for individual sessions and a "Hub" for cross-session management.
- **Communication (`agent-send`)**: A command-line tool used to send messages between the user, the UI, and the agents.
- **Logs**: All interactions are stored as JSONL files in the `logs/` directory.

## Project Structure

- `bin/`: Contains the primary entry points:
    - `multiagent`: Orchestrates the tmux sessions and environment setup.
    - `agent-index`: The web server (Chat UI and Hub).
    - `agent-send`: CLI for message routing.
- `lib/agent_index/`: Core Python logic:
    - `chat_core.py`: Real-time chat server logic.
    - `hub_core.py`: Multi-session management logic.
    - `export_core.py`: Generates standalone HTML exports of chat histories.
    - `state_core.py`: Manages persistence of settings and statistics.
- `docs/`: Detailed architectural notes and design philosophy (primarily in Japanese).
- `logs/`: Session-specific logs and agent output files.

## Key Commands

### Start a Session
```bash
./bin/multiagent start [session_name]
```
This initializes a tmux session, starts the agents, and launches the Chat UI server.

### Launch the Hub
```bash
./bin/agent-index --hub
```
Starts the control panel at `http://localhost:8788` to manage all sessions.

### Enable Auto-Mode
```bash
./bin/multiagent-auto-mode on
```
Launches a background monitor that automatically approves permission prompts in agent panes by sending `Enter`.

### Send Messages Manually
```bash
printf 'Your message' | ./bin/agent-send --stdin claude
```

## Multiagent Session Guidelines for Gemini

As an agent in this tmux-based multiagent environment, follow these mandates:

- **Identity**: Every normal reply sent with `agent-send` must start with `[From: gemini]`.
- **Communication Path**: Prefer `stdin` for sending messages. Example: `printf '%s' '[From: gemini] content' | agent-send --stdin target`.
- **Threading**: Always use `--reply <msg-id>` when responding to a specific message to keep conversations threaded. The `msg-id` is found in the message header: `[From: sender | msg-id: xxxxxxxxxxxx]`.
- **Targets**: `agent-send user` writes to the human inbox/chat UI. It does not inject text into the terminal pane.
- **Formatting**: Use Markdown and LaTeX ($...$ for inline, $$...$$ for block). Standard LaTeX commands (cases, pmatrix, align, etc.) are supported via KaTeX.
- **Attachments**: To attach a file reference, include `[Attached: path/to/file]` anywhere in the message text.
- **History**: Use `agent-index` or `agent-index --agent <name>` to inspect message history. **DO NOT** use `agent-index --follow` as it will hang the pane.
- **Content Standards**: Replies must contain actual content (no one-word answers). Avoid casual chatter or greeting loops unless explicitly instructed.

## Development Conventions

- **Zero Dependency Philosophy**: The project aims for zero external dependencies. It relies strictly on the Python standard library (e.g., `http.server` for the web server, `json` for logging) and system tools like `tmux` and `bash`. No `pip install` or virtualenv is required.
- **Python**: Uses modern Python (type hints, `pathlib`).
- **Web UI**: Built with Vanilla JS/CSS, embedded within the Python server or exported as standalone HTML.
- **Logging**: Strictly uses JSONL for message history to ensure easy parsing and recovery.
- **Port Management**: Ports are deterministically calculated based on the session name MD5 to ensure consistency across restarts.

## Building and Running

This project does not require a traditional build step as it is primarily Python and Bash. Ensure `tmux` and `python3` are installed.

- **Testing**: (TODO: Identify or create test suite)
- **Linting**: (TODO: Identify preferred linter, e.g., ruff or flake8)
