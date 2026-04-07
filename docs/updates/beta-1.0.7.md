# multiagent-chat beta 1.0.7

Japanese version: [beta-1.0.7.ja.md](beta-1.0.7.ja.md)

Released: 2026-04-07

This release covers changes after `beta 1.0.6` and focuses on chat stability plus thinking/runtime visibility.

## Highlights

### Thinking classification now works across providers and existing logs

- Existing `.agent-index.jsonl` entries are now read with kind inference, so planning-style agent messages (for example, `I will ...`) can render as `agent-thinking` without rewriting old logs.
- Gemini thinking is classified from both thought-flagged content parts and short planning-style prefixes.
- Qwen thought-only assistant parts are now indexed as `kind="agent-thinking"` instead of being dropped.
- Codex reasoning payloads are now indexed as `kind="agent-thinking"` (`response_item.reasoning` and `event_msg.agent_reasoning`).

### Chat rendering for thinking was simplified and hardened

- The experimental client-side thinking-group merge was removed from UI rendering.
- `agent-thinking` rows are now rendered as normal rows with compact typography and tighter line spacing.
- When the same agent emits consecutive `agent-thinking` messages, the metadata row is hidden from the 2nd item onward to reduce visual noise.
- Added defensive render fallback paths to avoid blank chat timelines on unexpected row-render errors.

### Runtime and system-event visibility improved

- Copilot `apply_patch` runtime notes are now expanded into file-level operations such as `Edit(path)`, `Create(path)`, and `Delete(path)` when patch headers are available.
- `/restart` and `/resume` are now appended to chat history as system entries (`kind="agent-control"`), matching other pane-control actions.

### Link styling was clarified

- Real external URLs now use a dedicated red link color.
- Inline file-reference links keep their file-link styling.
