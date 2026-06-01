#!/usr/bin/env bash

wait_for_agent_ready() {
  local pane_id="$1" agent_name="$2" max_attempts=120 attempt current_command pane_text ready_pattern
  local _base="${agent_name%%-[0-9]*}"
  ready_pattern="$(agent_var AGENT_READY_PATTERN "$_base")"
  for (( attempt=0; attempt<max_attempts; attempt++ )); do
    current_command="$(tmux display-message -p -t "$pane_id" '#{pane_current_command}' 2>/dev/null || true)"
    pane_text="$(tmux capture-pane -p -S -40 -t "$pane_id" 2>/dev/null || true)"
    if [[ -n "$ready_pattern" ]] && printf '%s\n' "$pane_text" | grep -Eq "$ready_pattern"; then
      return 0
    fi
    case "$current_command" in
      bash|zsh|sh|login) sleep 0.5 ;;
      "") sleep 0.5 ;;
      *) sleep 0.5 ;;
    esac
  done
  return 0
}

start_user_pane() {
  local pane_id="$1" launch_cmd
  local index_path
  index_path="$(_canonical_session_index_path "$SESSION_NAME")"
  launch_cmd="$(python3 - "$REPO_ROOT" "$SCRIPT_DIR" "$SESSION_NAME" "$WORKSPACE" "$TMUX_SOCKET_NAME" "$index_path" <<'PYEOF'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
script_dir = sys.argv[2]
session_name = sys.argv[3]
workspace = sys.argv[4]
tmux_socket = sys.argv[5]
index_path = sys.argv[6]
sys.path.insert(0, str(repo_root / "bin"))
from multiagent_lib.launch import build_env_exports, build_user_launch_command

env_exports = build_env_exports(
    script_dir=script_dir,
    session_name=session_name,
    workspace=workspace,
    tmux_socket=tmux_socket,
    index_path=index_path,
)
print(build_user_launch_command(env_exports=env_exports, script_dir=script_dir))
PYEOF
  )"
  tmux select-pane -t "$pane_id" -T "terminal"
  tmux send-keys -t "$pane_id" C-c
  tmux send-keys -t "$pane_id" "$launch_cmd" Enter
}
