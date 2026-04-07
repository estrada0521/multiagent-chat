# Developer Guide

This guide is for contributors working on `multiagent-chat` internals.

## 1. Repository layout (high-level)

| Area | Main files |
|---|---|
| Session lifecycle CLI | `bin/multiagent`, `bin/lib/multiagent_*_core.sh`, `lib/agent_index/multiagent_*_core.py` |
| Agent-to-agent transport | `bin/agent-send`, `lib/agent_index/agent_send_core.py` |
| Hub backend/UI | `lib/agent_index/hub_server.py`, `hub_core.py`, `hub_session_query_core.py`, `hub_stats_core.py`, `hub_chat_supervisor_core.py`, `hub_settings_crons_view_core.py`, `hub_header_assets.py` |
| Chat backend/UI | `lib/agent_index/chat_server.py`, `chat_core.py`, `chat_*_core.py`, `chat_assets.py`, `chat_assets_script_core.py`, `chat_template.html` |
| File/preview APIs | `lib/agent_index/file_core.py`, `file_preview_3d.py` |
| Cron runtime | `lib/agent_index/cron_core.py` |
| Shared state/log helpers | `state_core.py`, `jsonl_append.py`, `instance_core.py` |
| Tests | `tests/test_*.py` |

## 2. Local setup

1. Install Python 3 and tmux.
2. Run quickstart:
   ```bash
   ./bin/quickstart
   ```
3. Start a sample session:
   ```bash
   ./bin/multiagent --session demo --workspace "$(pwd)" --agents claude,codex
   ```

## 3. Running tests

Canonical suite (same shape as CI):

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Coverage run:

```bash
python3 -m pip install coverage
coverage run -m unittest discover -s tests -p 'test_*.py'
coverage report -m
```

CI workflow: `.github/workflows/python-tests.yml` (includes coverage XML artifact upload).

## 4. Adding a new agent

1. Add an `AgentDef` entry in `lib/agent_index/agent_registry.py`.
2. Add the icon SVG into `agent_icons/` (name aligned with registry entry).
3. Wire any provider-specific sync/runtime parsing if needed:
   - `chat_core.py` + related `chat_*_core.py` helpers.
4. Add/adjust tests in `tests/` (registry, sync, routing, UI assets as needed).

## 5. Working on Hub/Chat HTTP APIs

- Hub routes are in `hub_server.py` route dispatch tables (`_GET_ROUTE_HANDLERS` / `_POST_ROUTE_HANDLERS`) and the corresponding `_get_*` / `_post_*` handlers.
- Chat routes are in `chat_server.py` (`do_GET` / `do_POST`).
- Reference docs:
  - `docs/http-api.en.md`
  - `docs/http-api.md`

When adding routes:

1. Keep response shapes explicit (`ok`, `error`, stable keys).
2. Reuse existing helper modules where possible.
3. Add tests around parsing/dispatch/edge cases.
4. Consider Hub proxy path behavior (`/session/<name>/...`).

## 6. Refactor policy used in this repository

- Prefer extracting cohesive logic into `*_core.py` modules.
- Keep shell wrappers thin and move durable logic to Python core modules.
- Preserve behavior and error semantics during refactors.
- Add regression tests for every refactor that touches routing/sync/state.

## 7. Release flow

Update notes live in `docs/updates/`.

Publish release from notes:

```bash
./bin/multiagent-release --tag vX.Y.Z --notes docs/updates/beta-X.Y.Z.md
```

Tag/manual workflows are defined in `.github/workflows/publish-release.yml`.
