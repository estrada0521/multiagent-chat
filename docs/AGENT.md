# Multiagent Environment: Agent Guide

This document is an operational reference for **agents running inside a tmux-based multiagent session** in this repository.

> **Priority:** If there is a conflict between chat instructions, project-specific instructions, editor-level instructions, and system instructions, always follow those over this document.

---

## 1. First Things to Know

In this environment each agent typically runs in its own tmux pane.
Replies to the user or other agents must be sent via **`agent-send`**, not printed directly into the pane.

Start by checking the basics:

```bash
env | rg '^MULTIAGENT|^TMUX'
```

If you receive this document (or the workspace-side `docs/AGENT.md`) from the user, **report back once** that you have read and understood it. Use `agent-send` for the report as well.

Example:

```bash
printf '%s' 'I have read docs/AGENT.md. I understand the reply routing, attachments, and log conventions in this environment.' | agent-send user
```

Key environment variables:

| Variable | Meaning |
|----------|---------|
| `MULTIAGENT_SESSION` | Current session name |
| `MULTIAGENT_AGENT_NAME` | Your agent name |
| `MULTIAGENT_AGENTS` | List of participating agents |
| `MULTIAGENT_WORKSPACE` | Workspace path |
| `MULTIAGENT_LOG_DIR` | Log directory |
| `MULTIAGENT_TMUX_SOCKET` | tmux socket |
| `MULTIAGENT_PANE_*` | Pane IDs for each agent and user |
| `TMUX_PANE` | Your own pane ID |

To inspect the current session layout programmatically:

```bash
multiagent context --json
```

If `multiagent context` fails, `MULTIAGENT_SESSION` may be stale. Pass `--session <name>` explicitly or check your environment variables.

---

## 2. Communication Rules

### Must follow

| Rule | Details |
|------|---------|
| **Reply routing** | **Always send replies to `user` or other agents via `agent-send`**. Never print user-facing text directly into the pane |
| **Message body** | Pass the body via **stdin** to avoid breaking special characters and newlines |
| **Attachments** | Include **`[Attached: relative/path]`** in the message body |
| **Words containing `$`** | Shell variables, paths, and other words containing `$` **must be wrapped in inline code (`` ` ``)**. Otherwise the Hub renders them as math. Examples: `` `$HOME` ``, `` `$PATH` `` |

### Basic form

```bash
printf '%s' 'message body' | agent-send <target>
```

Target examples:

- `user`
- `claude`
- `codex`
- `gemini`
- `claude,codex`

---

## 3. Using `agent-send`

### Send to `user`

```bash
printf '%s' 'Confirmed.' | agent-send user
```

### Send to another agent

```bash
printf '%s' 'The relevant section is here.' | agent-send gemini
```

### Send as a new topic

```bash
printf '%s' 'Starting additional investigation.' | agent-send user
```

### When `agent-send` is not in PATH

The `[Attached: ...]` syntax and the `agent-send` command path are separate concerns. If the command is simply not found, **use its absolute path**.

```bash
printf '%s' 'hello' | /path/to/repo/bin/agent-send user
```

## 4. Attaching Files

### Principle

`agent-send` has no `--attach` flag. The correct way is to **write `[Attached: path]` in the message body**.

### Guidelines

| Guideline | Details |
|-----------|---------|
| **Relative paths** | **Use workspace-relative paths**. Absolute paths may not resolve correctly |
| **Own line** | `[Attached: docs/AGENT.md]` works best on its own line |
| **Inside the body** | Just writing "Attached" is not enough. The exact **`[Attached: ...]` syntax** is required |

Good example:

```bash
printf '%s' 'Changes applied.

[Attached: docs/AGENT.md]' | agent-send user
```

Bad example:

```bash
printf '%s' 'Changes applied.

[Attached: /absolute/path/to/docs/AGENT.md]' | agent-send user
```

---

## 5. Viewing Logs with `agent-index`

### View conversation history

```bash
agent-index
```

Filter by agent:

```bash
agent-index --agent codex
```

To read the raw `jsonl`, the default location is:

```text
<MULTIAGENT_LOG_DIR>/<MULTIAGENT_SESSION>/.agent-index.jsonl
```

### Important note

```bash
agent-index --follow
```

This **blocks and never returns**, so do not use it casually. Running it inside a pane will lock that pane.

---

## 6. Session Brief

This environment supports **session-specific briefs** in addition to `docs/AGENT.md`.

Role comparison:

| File type | Role |
|-----------|------|
| `docs/AGENT.md` | **Permanent rules** for the repo / multiagent environment |
| session brief | **Additional instructions / templates** scoped to a single session |

Session briefs are reusable templates that can be sent to multiple agents, rather than per-agent configuration.

### Storage location

Briefs are typically saved under:

```text
<log directory>/<session name>/brief/brief_<name>.md
```

Examples:

```text
logs/multiagent/brief/brief_default.md
logs/multiagent/brief/brief_strict.md
logs/multiagent/brief/brief_research.md
```

### Guidelines

- Briefs are **session-scoped**. Push permanent rules into `docs/AGENT.md` whenever possible
- Briefs are **reusable templates**. Send them to multiple agents as needed
- Briefs can be created or updated by humans or agents
- Avoid accumulating repo-wide permanent rules inside briefs

### UI and commands

- `/brief` or `/brief set <name>` in the chat UI opens saved briefs for viewing and editing
- The Brief button sends a saved brief to the currently selected target
- Viewing, editing, and sending all reference the same brief source

---

## 7. Session, tmux, and Logs

| Item | Details |
|------|---------|
| Default session name | Usually `multiagent` |
| Override session | `MULTIAGENT_SESSION` or `agent-send --session <name>` |
| Socket | `MULTIAGENT_TMUX_SOCKET` |
| Log location | Usually `<log directory>/<session name>/.agent-index.jsonl` |
| Workspace | `MULTIAGENT_WORKSPACE` |

When working across tmux sessions or multiple clones, watch out for **socket** and **workspace** mismatches.

---

## 8. Agent Topology Changes

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

## 9. Minimum Operational Flow

1. Run `env | rg '^MULTIAGENT|^TMUX'` to confirm your session
2. Send messages to user or other agents via `agent-send`
3. To share files, include `[Attached: relative/path]` in the body
4. Check history with `agent-index` or `.agent-index.jsonl`

---

## 10. Related Documents

| Path | Description |
|------|-------------|
| `README.md` | Public overview and quickstart |
| `docs/cloudflare-quick-tunnel.md` | Cloudflare quick tunnel setup |
| `docs/cloudflare-access.md` | Protecting the public Hub with Cloudflare Access |
| `docs/cloudflare-daemon.md` | Running the public tunnel as a daemon |

Internal notes and editor/agent-specific instruction files should be managed separately. Do not casually reference them from public-facing permanent docs.
