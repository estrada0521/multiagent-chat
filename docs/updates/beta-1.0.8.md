# multiagent-chat v1.0.8

Japanese version: [beta-1.0.8.ja.md](beta-1.0.8.ja.md)

Released: 2026-04-08

This release is the first one built around the new workbench shell. It removes a large amount of older Hub surface area and turns session startup into a draft-first flow.

## Highlights

### Hub and chat now behave like one workbench

- Desktop now keeps the session list in a sidebar and the selected chat embedded on the same page.
- Mobile no longer tries to mirror the desktop split view; opening the session list takes over the screen instead.
- Session switching stays inside the same shell, and kill/delete actions no longer flash through a full-page whiteout.

### New Session now starts from workspace choice, not from a form

- Pressing `New Session` opens the workspace picker immediately.
- Choosing a workspace opens a draft chat right away, using the workspace directory name as the session name.
- tmux is not started yet at that point. The first message and the currently selected initial agents decide which panes actually launch.

### Older Hub features were physically removed

- Cron, Stats, and the old Resume Sessions page are gone.
- Settings were slimmed down around the black-hole baseline, fixed desktop width, and the remaining chat/runtime controls.
- The legacy standalone Hub error page was replaced with a redirect-back flow so failures return to the workbench.

### Chat polish and sync stability improved

- Code/file preview typography was aligned more closely with the main chat body, including HTML text/web preview switching.
- Thinking rows were tightened, Codex runtime labels became more descriptive, and local file links render correctly inside agent output.
- Sync cursor matching was hardened for cloud-backed workspaces, and draft-launch behavior was stabilized for Claude/Qwen/Codex flows.
