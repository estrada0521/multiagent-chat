#!/usr/bin/env bash

send_text_to_pane() {
  local pane_id="$1" payload="$2"
  tmux set-buffer -- "$payload"
  tmux paste-buffer -d -t "$pane_id"
  sleep 0.3
  tmux send-keys -t "$pane_id" "" Enter
}

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

wait_for_user_pane_ready() {
  local pane_id="$1" max_attempts="${2:-80}" attempt current_command pane_text
  for (( attempt=0; attempt<max_attempts; attempt++ )); do
    current_command="$(tmux display-message -p -t "$pane_id" '#{pane_current_command}' 2>/dev/null)" || return 1
    pane_text="$(tmux capture-pane -p -S -20 -t "$pane_id" 2>/dev/null)" || return 1
    if [[ "$current_command" =~ ^(bash|zsh|sh|login)$ ]] && printf '%s\n' "$pane_text" | grep -Fq '[multiagent] shortcuts:'; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

open_chat_in_user_pane() {
  local pane_id="$1"
  [[ -n "$pane_id" ]] || return 0
  [[ "${MULTIAGENT_SKIP_USER_CHAT:-0}" == "1" ]] && return 0
  wait_for_user_pane_ready "$pane_id" || return 1
  send_text_to_pane "$pane_id" "follow --chat"
}

start_user_pane() {
  local pane_id="$1" launch_cmd
  local index_path log_dir_mode log_dir_value
  index_path="$(_canonical_session_index_path "$SESSION_NAME")"
  if [[ -z "${LOG_DIR+x}" ]]; then
    log_dir_mode="unset"
    log_dir_value=""
  else
    log_dir_mode="set"
    log_dir_value="$LOG_DIR"
  fi
  launch_cmd="$(python3 - "$REPO_ROOT" "$SCRIPT_DIR" "$SESSION_NAME" "$WORKSPACE" "$TMUX_SOCKET_NAME" "$index_path" "$log_dir_mode" "$log_dir_value" <<'PYEOF'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
script_dir = sys.argv[2]
session_name = sys.argv[3]
workspace = sys.argv[4]
tmux_socket = sys.argv[5]
index_path = sys.argv[6]
log_dir_mode = sys.argv[7]
log_dir_value = sys.argv[8]
log_dir = None if log_dir_mode == "unset" else log_dir_value
sys.path.insert(0, str(repo_root / "lib"))
from agent_index.multiagent_launch_core import build_env_exports, build_user_launch_command

env_exports = build_env_exports(
    script_dir=script_dir,
    session_name=session_name,
    workspace=workspace,
    tmux_socket=tmux_socket,
    index_path=index_path,
    log_dir=log_dir,
)
print(build_user_launch_command(env_exports=env_exports, script_dir=script_dir))
PYEOF
  )"
  tmux select-pane -t "$pane_id" -T "terminal"
  tmux send-keys -t "$pane_id" C-c
  tmux send-keys -t "$pane_id" "$launch_cmd" Enter
}
