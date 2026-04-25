# Providers

`providers/` owns provider-specific native CLI adapters and parsers.

These modules handle external CLI quirks for Claude, Codex, Gemini, Cursor,
Copilot, OpenCode, Qwen, and similar providers. They may depend on
`src/multiagent_chat/` runtime helpers, but core Chat runtime code should import
provider behavior from this package rather than growing provider-specific logic
inline.
