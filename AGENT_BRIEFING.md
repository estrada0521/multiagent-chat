# Agent Briefing

- You are running inside a tmux-based multiagent session.
- `agent-send` targets panes in this session.
- To message other agents, use:
  `agent-send <claude|codex|gemini|copilot|others|claude,codex> "message"`
- To inspect message history, use:
  `agent-index`
  `agent-index --follow`
  `agent-index --agent <name>`
- For this briefing only, reply in this pane with: `OK`
- After this briefing, when another agent asks you to reply, you must reply with `agent-send`. Do not reply only in this pane.
- Every normal reply sent with `agent-send` must start with `[From: <your-agent-name>] ` so the sender is explicit.
- Normal replies must contain actual content. Do not reply with only `OK` unless the other agent explicitly asked for that.
- Do not start greeting loops or casual chatter unless explicitly instructed.
- For normal replies, identify the sender and use:
  `agent-send <sender> "[From: <your-agent-name>] ..."`
