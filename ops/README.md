# Ops

Operational implementation code lives here. The `bin/` directory should stay as
the stable command layer: small wrappers that resolve the repository root and
delegate to these implementation scripts.

Current areas:

- `hub/` - `agent-index` shell entry implementation
- `multiagent/` - tmux session orchestration and helper shell modules
- `setup/` - first-time dependency and local HTTPS setup
- `desktop/` - Tauri quickstart and rebuild helpers
- `tools/` - local maintenance tools
