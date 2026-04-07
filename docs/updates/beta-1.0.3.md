# multiagent-chat beta 1.0.3

Japanese version: [beta-1.0.3.ja.md](beta-1.0.3.ja.md)

Released: 2026-04-01

This note covers changes after commit `55220dd` on 2026-03-31, which prepared the beta 1.0.2 release.

## Highlights

### Hub-centric PWA flow became practical

- Installed Hub notifications now support deep links back into the source session instead of stopping at a generic inbox-level banner.
- The local HTTPS path was cleaned up for iPhone and iPad use, including refreshed local PWA icons and route handling that keeps external-editor handoff working on LAN installs.
- The installed Hub can remain the single notification endpoint for all active sessions, while session chats stay normal deep-link destinations instead of requiring separate installs.

### Agents can now reconfigure session topology themselves

- Agents can run `multiagent add-agent` and `multiagent remove-agent` directly from inside their panes, using the current session and tmux socket automatically.
- Topology changes are serialized per session so concurrent UI-side and agent-side add/remove requests no longer race instance naming or tmux state updates.
- Agent-facing helper docs were added so newly spawned instances can discover `agent-send`, topology commands, and message-format workflows quickly.

### Chat surfaces gained stronger operational controls

- The header menu now includes direct Finder and Pane Trace entry points, making desktop navigation less dependent on the main terminal window.
- The branch/worktree surface gained per-file actions plus a whole-worktree commit path, and commit system-entry attribution was corrected so commit records point to the right agent.
- File references are now easier to scan through category tabs, counts, sizes, and better file-menu / tab-strip behavior.
- The slash-command picker was flattened again after the experimental category split, so command lookup stays fast and visually lighter.
- Auto-mode handling and worktree-side UI flows received follow-up fixes, including safer approval-trigger behavior and cleaner commit-action feedback.

### Direct Gemini bridging and live runtime hints

- A direct Gemini chat bridge was added, along with a probe path and subsequent refinement passes, so Gemini can be used from the chat UI without going through a tmux pane.
- Thinking rows can now surface lightweight runtime hints extracted from Codex, Gemini, and Cursor pane output, such as `Ran`, `Edited`, `ReadFile`, or `Grepped`.
- The slash-command surface was simplified again, and the runtime hint line now highlights tool keywords more clearly during live updates.

### Operator docs and agent-facing guidance expanded

- `docs/gemini-direct-api.*` was added to explain the direct runner, runtime JSONL sidecars, and the current limits of the Gemini bridge.
- `docs/AGENT.md`, the technical details guide, and the design philosophy docs were updated so the environment's message routing, notification model, and topology controls are documented from both operator and agent perspectives.
- `bin/agent-help` was added as a command-first cheatsheet for agents that have just joined a session and need the local workflow in a compact form.

## Other notable additions

- Local PWA and app-bundle reload behavior was repaired again after LAN / installed-app edge cases.
- Worktree actions, auto-mode handling, and branch attribution received several smaller fixes.
- README, design philosophy, and technical docs were expanded so the Hub-centric notification model and session-topology controls are easier to understand.
