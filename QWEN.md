# Multiagent Project Overview

This project is a tmux-based development environment that runs multiple AI agents in parallel and exposes a shared Chat UI for interaction.

## Core Architecture

- **Backend**: `tmux` sessions with one pane per agent.
- **Server (`agent-index`)**: Provides both the per-session Chat UI and the multi-session Hub.
- **Communication (`agent-send`)**: CLI used to route messages between agents, the UI, and the user inbox.
- **Logs**: Session history is stored as JSONL under `logs/`.

## Key Commands

### Start a Session
```bash
./bin/multiagent --session my-session
```

### Launch the Hub
```bash
./bin/agent-index --hub
```

### Send Messages Manually
```bash
printf '%s' '[From: qwen] message' | ./bin/agent-send --stdin claude
```

## Multiagent Session Guidelines for Qwen

As an agent in this tmux-based multiagent environment, follow these rules:

- **Identity**: Every normal reply sent with `agent-send` should start with `[From: qwen]`.
- **Communication Path**: Prefer `stdin` when sending messages. Example: `printf '%s' '[From: qwen] content' | agent-send --stdin target`
- **Threading**: Use `--reply <msg-id>` when responding to a specific user message so the conversation stays threaded.
- **Targets**: `agent-send user` writes to the human inbox/chat UI, not to another terminal pane.
- **History**: Use `agent-index` to inspect history when needed. Avoid `agent-index --follow` because it will block the pane.
- **Content Standards**: Send real content, not placeholder acknowledgements or greeting loops.

## Development Conventions

- Keep dependencies minimal.
- Use the existing Python/Bash/Vanilla JS patterns in this repository.
- Prefer repo-local commands such as `./bin/agent-send`, `./bin/multiagent`, and `./bin/agent-index` when relevant.
