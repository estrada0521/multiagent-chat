#!/usr/bin/env bash

set -euo pipefail

if [[ -n "${AGENT_INDEX_BOOTSTRAP_SH:-}" ]]; then
  return 0
fi
AGENT_INDEX_BOOTSTRAP_SH=1

SCRIPT_DIR="$REPO_ROOT/bin"
AGENT_INDEX_PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if [[ "${MULTIAGENT_SKIP_DEPS_CHECK:-}" != "1" ]]; then
  if ! command -v python3 >/dev/null 2>&1 || ! command -v tmux >/dev/null 2>&1; then
    bash "$SCRIPT_DIR/ensure-multiagent-deps" || exit 1
  fi
fi

_ALL_AGENTS="$(PYTHONPATH="$AGENT_INDEX_PYTHONPATH" python3 -c "from backend_core.agents.registry import ALL_AGENT_NAMES; print(' '.join(ALL_AGENT_NAMES))" 2>/dev/null || echo "claude codex gemini kimi copilot cursor opencode qwen")"
read -ra _ALL_AGENTS_ARR <<< "$_ALL_AGENTS"

default_tmux_socket_name() {
  python3 - "$REPO_ROOT" <<'PYEOF'
import hashlib
import os
import sys

root = os.path.realpath(sys.argv[1])
digest = hashlib.sha1(root.encode("utf-8")).hexdigest()[:12]
print(f"multiagent-{digest}")
PYEOF
}

TMUX_SOCKET_NAME="${MULTIAGENT_TMUX_SOCKET:-$(default_tmux_socket_name)}"

tmux() {
  if [[ "$TMUX_SOCKET_NAME" == */* ]]; then
    command tmux -S "$TMUX_SOCKET_NAME" "$@"
  else
    command tmux -L "$TMUX_SOCKET_NAME" "$@"
  fi
}

usage() {
  cat <<'EOF'
Usage: agent-index [--session NAME] [--limit N] [--follow] [--json] [--chat] [--hub] [--hub-port N]

Shows indexed chat/event messages for the current or archived session.
EOF
}

realpath_or_echo() {
  python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1" 2>/dev/null || printf '%s\n' "$1"
}
