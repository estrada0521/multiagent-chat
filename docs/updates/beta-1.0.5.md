# multiagent-chat beta 1.0.5

Japanese version: [beta-1.0.5.ja.md](beta-1.0.5.ja.md)

Released: 2026-04-04

This note covers changes after commit `cbe21cf` on 2026-04-02, which prepared the beta 1.0.4 release.

## Highlights

### Camera mode became a first-class mobile chat surface

- Chat now includes a dedicated `Camera` action aimed at mobile use instead of treating image capture as a side effect of the normal composer.
- The overlay keeps a live camera feed, one selected target agent, recent agent replies, and an immediate shutter path in the same surface.
- Captures are resized before upload and then sent through the normal structured message path, so camera sends still end up in `.agent-index.jsonl` and the regular file / export flow.
- Camera mode also gained in-overlay voice input, with a hybrid waveform design: real Web Audio-driven motion when the browser allows parallel microphone analysis, and a looped fallback animation when it does not.
- A large part of the release was spent aligning spacing, divider rules, message animation, chip sizing, and overlay hierarchy with the main chat renderer rather than shipping a separate visual language.

### Direct provider paths expanded beyond Gemini

- The composer now exposes `/gemma` in addition to `/gemini`, backed by a new Ollama direct runner and normalized event plumbing.
- This path is intentionally separate from pane-driven CLI agents. It returns direct-provider results into the same timeline, but it does not imply pane-local memory, file mutation tools, or CLI session state.
- The release therefore adds local-model plumbing without pretending that a direct API path is the same thing as a full coding agent pane.

### Preview, Pane Trace, and runtime hints kept getting tighter

- Markdown preview was darkened again, its header visibility was corrected, and the file-preview chrome was aligned more closely across local and public routes.
- Pane Trace polling and compact runtime indicators were refined again so long-running sessions stay easier to watch without heavy browser overhead.
- Runtime-hint extraction was widened across supported providers, so compact lines such as `Ran`, `Edited`, `ReadFile`, `Grepped`, `Searching`, and similar pane-side tool summaries appear more consistently under thinking rows.

### Documentation was brought back in line with the real UI

- README, command references, and technical notes were updated to match the current slash-command set, direct-provider commands, and mobile camera workflow.
- This release also cleans up older documentation drift around removed raw-send behavior, so the public-facing docs better match what the product actually does today.

## Other notable additions

- Copilot auto mode learned to handle boxed directory-access approval prompts with the same minimal auto-confirm approach already used for other agents.
- Icon instance badges and message-width controls were tuned again so mobile and desktop surfaces stay more consistent.
