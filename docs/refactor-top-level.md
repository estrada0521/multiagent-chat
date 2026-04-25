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

- `apps/desktop/` contains the Tauri desktop shell and desktop web surface.
- `apps/mobile/` contains the mobile/PWA web surface.
- `apps/shared/` contains shared app-surface fragments, Hub templates, and PWA
  static assets.
- `src/multiagent_chat/` contains the Python implementation.
- `src/multiagent_chat/` is now the canonical Python package; the old
  `lib/agent_index/` compatibility package has been removed.
- `src/multiagent_chat/web/` has been retired. Remaining core-side web boundary
  concerns now live under `presentation/` and `transport/`.
- `assets/icons/agents/`, `assets/sounds/`, and `assets/logos/` contain shared
  assets.
- `ops/` now owns the shell-heavy command implementations; `bin/` remains the
  stable command layer for existing workflows.

## Boundaries

- `apps/` owns concrete human-facing surfaces: HTML, CSS, browser JavaScript,
  and static PWA assets.
- `src/` owns runtime truth, storage/sync behavior, transport boundaries, and
  UI-independent presentation assembly.
- `src/multiagent_chat/presentation/` prepares Hub/Chat presentation output from
  app fragments and runtime settings.
- `src/multiagent_chat/transport/` owns HTTP request boundary helpers such as
  forwarded base path and view variant resolution.
- `providers/` is reserved for provider-specific CLI adapters and parsers.
- `ops/` is reserved for setup, launch, certificates, tunnels, and maintenance
  implementation code.
- `bin/` should keep stable command names and delegate inward.

## Root Files

Root-level files are intentionally limited to repository entry documents and
local setup guardrails:

- `README.md` and `README.ja.md` are the public entry points.
- `.gitignore` keeps local runtime, certificate, IDE, and export artifacts out of
  source control.

Local files such as `.DS_Store` and `mkcert-rootCA.pem` may appear on a
developer machine, but they are ignored and should not be committed.

Do not mix file moves with behavior changes unless a compatibility issue forces
the change.
