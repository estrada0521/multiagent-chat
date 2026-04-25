# Refactor Top-Level Layout

This repository is being moved toward a domain-oriented layout while preserving
existing command names and runtime behavior.

## Target Layout

```text
multiagent-local/
├── apps/
├── src/
├── providers/
├── ops/
├── assets/
├── docs/
└── bin/
```

## Current Migration State

- `apps/desktop/` contains the Tauri desktop shell.
- `src/multiagent_chat/` contains the Python implementation.
- `src/multiagent_chat/` is now the canonical Python package; the old
  `lib/agent_index/` compatibility package has been removed.
- `assets/icons/agents/`, `assets/sounds/`, and `assets/logos/` contain shared
  assets.
- `ops/` now owns the shell-heavy command implementations; `bin/` remains the
  stable command layer for existing workflows.

## Boundaries

- `apps/` should stay thin and user-facing.
- `src/` owns core Python behavior.
- `providers/` is reserved for provider-specific CLI adapters and parsers.
- `ops/` is reserved for setup, launch, certificates, tunnels, and maintenance
  implementation code.
- `bin/` should keep stable command names and delegate inward.

Do not mix file moves with behavior changes unless a compatibility issue forces
the change.
