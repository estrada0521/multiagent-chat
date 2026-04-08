# Multiagent Environment: Agent Guide

This document is an operational reference for **agents running inside a tmux-based multiagent session** in this repository.

> **Priority:** If there is a conflict between chat instructions, project-specific instructions, editor-level instructions, and system instructions, always follow those over this document.

---

## 1. First Things to Know

In this environment each agent typically runs in its own tmux pane.
Replies intended for the human should be written as your normal assistant output in the pane (native event logs are indexed directly). Use **`agent-send`** only when routing messages to other agents.

Start by checking the basics:

```bash
env | rg '^MULTIAGENT|^TMUX'
```

If you receive this document (or the workspace-side `docs/AGENT.md`) from the user, **report back once** that you have read and understood it as a normal assistant reply.

If you only need a compact command cheatsheet later, run:

```bash
agent-help
```

Example:

`I have read docs/AGENT.md. I understand message routing and log conventions in this environment.`

Key environment variables:


| Variable                 | Meaning                          |
| ------------------------ | -------------------------------- |
| `MULTIAGENT_SESSION`     | Current session name             |
| `MULTIAGENT_AGENT_NAME`  | Your agent name                  |
| `MULTIAGENT_AGENTS`      | List of participating agents     |
| `MULTIAGENT_WORKSPACE`   | Workspace path                   |
| `MULTIAGENT_LOG_DIR`     | Log directory                    |
| `MULTIAGENT_TMUX_SOCKET` | tmux socket                      |
| `MULTIAGENT_PANE_*`      | Pane IDs for each agent and user |
| `TMUX_PANE`              | Your own pane ID                 |


To inspect the current session layout programmatically:

```bash
multiagent context --json
```

If `multiagent context` fails, `MULTIAGENT_SESSION` may be stale. Pass `--session <name>` explicitly or check your environment variables.

---

## 2. Communication Rules

### Must follow


| Rule                     | Details                                                                                                                                                             |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hub-visible delivery** | Human-facing replies should be normal assistant output in the pane. Use **`agent-send` only for agent-to-agent routing**                                                |
| **Message body**         | Pass the body via **stdin** to avoid breaking special characters and newlines                                                                                       |
| **Words containing `$`** | Shell variables, paths, and other words containing `$` **must be wrapped in inline code using backticks**. Otherwise the Hub renders them as math. Examples: `` `$HOME` ``, `` `$PATH` `` |


### Basic form

```bash
printf '%s' 'message body' | agent-send <target>
```

Target examples:

- `claude`
- `codex`
- `gemini`
- `claude,codex`

---

## 3. Using `agent-send` (agent-to-agent only)

### Human-facing reply

Use your normal assistant output in the pane. Do **not** run `agent-send user`.

### Send to another agent

```bash
printf '%s' 'The relevant section is here.' | agent-send gemini
```

### When `agent-send` is not in PATH

If the command is simply not found, **use its absolute path**.

```bash
printf '%s' 'hello' | /path/to/repo/bin/agent-send gemini
```

## 4. Viewing Logs with `agent-index`

### View conversation history

```bash
agent-index
```

Filter by agent:

```bash
agent-index --agent codex
```

To read the raw `jsonl`, prefer:

```text
<MULTIAGENT_INDEX_PATH>
```

### Important note

```bash
agent-index --follow
```

This **blocks and never returns**, so do not use it casually. Running it inside a pane will lock that pane.

---

## 5. Session, tmux, and Logs


| Item                 | Details                                                     |
| -------------------- | ----------------------------------------------------------- |
| Default session name | Usually `multiagent`                                        |
| Override session     | `MULTIAGENT_SESSION` or `agent-send --session <name>`       |
| Socket               | `MULTIAGENT_TMUX_SOCKET`                                    |
| Log location         | Canonical path in `MULTIAGENT_INDEX_PATH` (workspace mirror may be a symlink) |
| Workspace            | `MULTIAGENT_WORKSPACE`                                      |


When working across tmux sessions or multiple clones, watch out for **socket** and **workspace** mismatches.

---

## 6. Agent Topology Changes

Agents inside a session may also change the current agent set directly. Use the existing `multiagent` subcommands rather than inventing a chat-side protocol.

Add a new agent instance:

```bash
multiagent add-agent --agent claude
```

Remove a specific running instance:

```bash
multiagent remove-agent --agent claude-2
```

Notes:

- `add-agent` takes a **base agent name** such as `claude`, `codex`, or `gemini`
- `remove-agent` takes an **instance name** such as `claude`, `claude-2`, or `codex-3`
- Inside an active pane, `--session` is optional because `MULTIAGENT_SESSION` and `MULTIAGENT_TMUX_SOCKET` are already present
- The last remaining agent cannot be removed
- Removing your own instance will close your pane immediately after the command succeeds
- These changes append a `system` entry to `.agent-index.jsonl`, so the chat timeline records the topology change as well

---

## 7. Minimum Operational Flow

1. Run `env | rg '^MULTIAGENT|^TMUX'` to confirm your session
2. Reply to humans in normal assistant output; use `agent-send` only for other agents
3. Wrap words containing `$` in inline code when sending shell paths or variables
4. Check history with `agent-index` or `.agent-index.jsonl`

---

## 8. Related Documents


| Path                              | Description                                      |
| --------------------------------- | ------------------------------------------------ |
| `README.md`                       | Local-first overview and quickstart              |
| `docs/design-philosophy.en.md`    | Why the workbench is shaped this way             |
| `docs/technical-details.en.md`    | Internal structure, routing, and storage details |


Internal notes and editor/agent-specific instruction files should be managed separately. Do not casually reference them from public-facing permanent docs.
