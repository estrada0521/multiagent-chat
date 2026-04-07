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
    current_command="$(tmux display-message -p -t "$pane_id" '#{pane_current_command}' 2>/dev/null || true)"
    pane_text="$(tmux capture-pane -p -S -20 -t "$pane_id" 2>/dev/null || true)"
    if [[ "$current_command" =~ ^(bash|zsh|sh|login)$ ]] && printf '%s\n' "$pane_text" | grep -Fq '[multiagent] shortcuts:'; then
      return 0
    fi
    sleep 0.25
  done
  return 0
}

open_chat_in_user_pane() {
  local pane_id="$1"
  [[ -n "$pane_id" ]] || return 0
  [[ "${MULTIAGENT_SKIP_USER_CHAT:-0}" == "1" ]] && return 0
  wait_for_user_pane_ready "$pane_id"
  send_text_to_pane "$pane_id" "follow --chat"
}

send_agent_capability_briefing() {
  local pane_id="$1" agent_name="$2" briefing
  printf -v briefing '%s\n' \
    "Multiagent session note for ${agent_name}:" \
    "- You are running inside a tmux-based multiagent session. agent-send targets other agent panes in this session." \
    "- agent-send is for agent-to-agent communication only. Send the body on stdin. Example: printf '%s' 'hello' | agent-send claude" \
    "- To inspect message history, use: agent-index or agent-index --agent <name>. Do NOT run agent-index --follow — it blocks forever and will hang your pane." \
    "- For messages to the human/chat, respond in your normal assistant output in this pane. Native event logs are indexed directly." \
    "- Messages sent via agent-send are displayed in the chat UI (agent-index --chat) with Markdown rendering. You may use Markdown in your messages: **bold**, \`inline code\`, \`\`\`code blocks\`\`\`, headers, lists, tables, etc." \
    "- The chat UI also renders LaTeX math via KaTeX. Use \$...\$ for inline math and \$\$...\$\$ for display (block) math. Standard LaTeX commands and environments such as cases, pmatrix, bmatrix, align, aligned, and array are generally supported." \
    "- The chat UI renders Mermaid diagrams. Use \`\`\`mermaid code blocks to create flowcharts, sequence diagrams, class diagrams, state diagrams, ER diagrams, Gantt charts, etc. They are rendered as interactive SVG graphics. Example: \`\`\`mermaid\\ngraph TD\\n    A[Start] --> B[End]\\n\`\`\`" \
    "- If you mention a repo file path in inline code (for example \`lib/agent_index/chat_core.py\`), the chat UI can resolve it as a preview link when the file exists." \
    "- For agent-to-agent collaboration, use agent-send so the handoff is visible in chat history." \
    "- Agent-to-agent messages must contain actual content. Do not send a single-word message unless explicitly asked." \
    "- Do not start greeting loops or casual chatter unless explicitly instructed." \
    "- For normal chat messages to the human, do not run agent-send; answer directly in your assistant output." \
    "- To confirm you have read this briefing, respond in your normal assistant output with exactly: Briefing received."
  send_text_to_pane "$pane_id" "$briefing"
}

brief_session_agents() {
  local session="$1" requested_agents="${2:-}" agent base_agent upper pane_id
  local selected_agents=()
  if [[ -n "$requested_agents" ]]; then
    IFS=',' read -r -a selected_agents <<< "$requested_agents"
  else
    # Read MULTIAGENT_AGENTS; fall back to default set
    local agents_str
    agents_str="$(tmux show-environment -t "$session" MULTIAGENT_AGENTS 2>/dev/null | sed 's/^[^=]*=//' || true)"
    if [[ -n "$agents_str" ]]; then
      IFS=',' read -r -a selected_agents <<< "$agents_str"
    else
      selected_agents=("${ALL_AGENTS[@]}")
    fi
  fi
  for agent in "${selected_agents[@]}"; do
    # Strip instance suffix to get base agent name for validation
    base_agent="${agent%%-[0-9]*}"
    if ! agent_in_registry "$base_agent"; then
      echo "Unknown agent for brief: $agent" >&2
      return 1
    fi
    upper="$(printf '%s' "$agent" | tr '[:lower:]-' '[:upper:]_')"
    pane_id="$(tmux show-environment -t "$session" "MULTIAGENT_PANE_${upper}" 2>/dev/null | sed 's/^[^=]*=//' || true)"
    [[ -n "$pane_id" ]] || continue
    send_agent_capability_briefing "$pane_id" "$agent"
  done
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
