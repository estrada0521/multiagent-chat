# Providers

Provider-specific CLI adapters will live here.

This directory is intentionally separate from `src/multiagent_chat/agents/`:

- `src/multiagent_chat/agents/` is for app-facing agent abstractions.
- `providers/` is for Claude, Codex, Gemini, Cursor, and other external CLI
  quirks, native log parsing, display rules, and launch details.

The initial top-level migration leaves existing provider code in place until it
can be extracted behind compatibility-preserving boundaries.
