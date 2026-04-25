multiagent_dispatch_prelaunch_modes() {
  if [[ "$MODE" == "status" ]]; then
    command -v tmux >/dev/null 2>&1 || { echo "tmux is required." >&2; exit 1; }
    if [[ "$ALL_SESSIONS" -eq 1 ]]; then
      found=0
      while IFS= read -r session; do
        [[ -z "$session" ]] && continue
        show_status "$session"
        echo
        found=1
      done < <(repo_sessions)
      [[ "$found" -eq 1 ]] || echo "No sessions found for this multiagent install"
      exit 0
    fi
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      SESSION_NAME="$(resolve_target_session_name)" || exit 1
    fi
    if [[ -z "$SESSION_NAME" ]]; then
      echo "Session does not exist" >&2
      exit 1
    fi
    show_status "$SESSION_NAME"
    exit 0
  fi

  if [[ "$MODE" == "context" ]]; then
    command -v tmux >/dev/null 2>&1 || { echo "tmux is required." >&2; exit 1; }
    resolved_note=""
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      if [[ -n "${MULTIAGENT_SESSION:-}" ]]; then
        SESSION_NAME="$MULTIAGENT_SESSION"
      elif [[ -n "${MULTIAGENT_SESSION_NAME:-}" ]]; then
        SESSION_NAME="$MULTIAGENT_SESSION_NAME"
      fi
    fi
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      if [[ -n "${TMUX:-}" ]]; then
        SESSION_NAME="$(tmux display-message -p '#{session_name}' 2>/dev/null || true)"
      fi
    fi
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      SESSION_NAME="$(resolve_target_session_name)" || exit 1
    fi
    if [[ -z "$SESSION_NAME" ]]; then
      echo "Session does not exist or could not be resolved (set MULTIAGENT_SESSION or run inside tmux)." >&2
      exit 1
    fi
    if ! tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
      echo "tmux session not found: $SESSION_NAME" >&2
      exit 1
    fi
    if [[ "$SESSION_NAME_EXPLICIT" -eq 1 ]]; then
      resolved_note="--session"
    elif [[ -n "${MULTIAGENT_SESSION:-}" && "$SESSION_NAME" == "${MULTIAGENT_SESSION}" ]]; then
      resolved_note="MULTIAGENT_SESSION"
    elif [[ -n "${MULTIAGENT_SESSION_NAME:-}" && "$SESSION_NAME" == "${MULTIAGENT_SESSION_NAME}" ]]; then
      resolved_note="MULTIAGENT_SESSION_NAME"
    elif [[ -n "${TMUX:-}" ]]; then
      resolved_note="tmux client (#{session_name})"
    else
      resolved_note="resolve_target_session_name"
    fi
    print_agent_context "$SESSION_NAME" "$resolved_note"
    exit 0
  fi

  if [[ "$MODE" == "list" ]]; then
    command -v tmux >/dev/null 2>&1 || { echo "tmux is required." >&2; exit 1; }
    list_sessions
    exit 0
  fi

  if [[ "$MODE" == "resume" ]]; then
    command -v tmux >/dev/null 2>&1 || { echo "tmux is required." >&2; exit 1; }
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      SESSION_NAME="$(resolve_target_session_name)" || exit 1
    fi
    if [[ -z "$SESSION_NAME" ]]; then
      echo "Session does not exist" >&2
      exit 1
    fi
    if ! tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
      echo "Session does not exist: $SESSION_NAME" >&2
      exit 1
    fi
    # Restart auto-mode monitor if it was on but the process has died
    _auto_val="$(tmux show-environment -t "$SESSION_NAME" MULTIAGENT_AUTO_MODE 2>/dev/null | sed 's/^[^=]*=//' || echo "0")"
    if [[ "$_auto_val" == "1" ]]; then
      _pid_file="/tmp/multiagent_auto_${SESSION_NAME}.pid"
      _pid="$(cat "$_pid_file" 2>/dev/null || true)"
      if [[ -z "$_pid" ]] || ! kill -0 "$_pid" 2>/dev/null; then
        "$SCRIPT_DIR/multiagent-auto-mode" on --session "$SESSION_NAME" >&2 || true
      fi
    fi
    [[ "$DETACH" -eq 1 ]] && { echo "Session exists: $SESSION_NAME"; exit 0; }
    open_chat_in_user_pane "$(primary_user_pane_id "$SESSION_NAME")"
    exec_tmux attach-session -t "$SESSION_NAME"
  fi

  if [[ "$MODE" == "kill" ]]; then
    command -v tmux >/dev/null 2>&1 || { echo "tmux is required." >&2; exit 1; }
    if [[ "$ALL_SESSIONS" -eq 1 ]]; then
      killed=0
      while IFS= read -r session; do
        [[ -z "$session" ]] && continue
        if ! stop_session_chat_server "$session"; then
          echo "[multiagent] warning: failed to stop chat server for $session" >&2
        fi
        rm -f "/tmp/multiagent_save_${session}.sh" 2>/dev/null || true
        rm -f "$(multiagent_panes_state_path)" 2>/dev/null || true
        tmux kill-session -t "$session"
        echo "Killed tmux session: $session"
        killed=1
      done < <(repo_sessions)
      [[ "$killed" -eq 1 ]] || { echo "No sessions found for this multiagent install"; exit 1; }
      exit 0
    fi
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      SESSION_NAME="$(resolve_target_session_name)" || exit 1
    fi
    if [[ -z "$SESSION_NAME" ]]; then
      echo "Session does not exist" >&2
      exit 1
    fi
    if ! tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
      echo "Session does not exist: $SESSION_NAME" >&2
      exit 1
    fi
    if ! stop_session_chat_server "$SESSION_NAME"; then
      echo "[multiagent] warning: failed to stop chat server for $SESSION_NAME" >&2
    fi
    rm -f "/tmp/multiagent_save_${SESSION_NAME}.sh" 2>/dev/null || true
    rm -f "$(multiagent_panes_state_path)" 2>/dev/null || true
    tmux kill-session -t "$SESSION_NAME"
    echo "Killed tmux session: $SESSION_NAME"
    exit 0
  fi

  if [[ "$MODE" == "rename" ]]; then
    command -v tmux >/dev/null 2>&1 || { echo "tmux is required." >&2; exit 1; }
    [[ -n "$RENAME_TO" ]] || { echo "rename requires --to NEW_NAME" >&2; exit 1; }
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      SESSION_NAME="$(resolve_target_session_name)" || exit 1
    fi
    if [[ -z "$SESSION_NAME" ]]; then
      echo "Session does not exist" >&2
      exit 1
    fi
    if ! tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
      echo "Session does not exist: $SESSION_NAME" >&2
      exit 1
    fi
    if tmux has-session -t "=$RENAME_TO" 2>/dev/null; then
      echo "Session already exists: $RENAME_TO" >&2
      exit 1
    fi
    tmux rename-session -t "$SESSION_NAME" "$RENAME_TO"
    echo "Renamed tmux session: $SESSION_NAME -> $RENAME_TO"
    exit 0
  fi
}

multiagent_dispatch_agent_mutation_modes() {
  if [[ "$MODE" == "add-agent" ]]; then
    command -v tmux >/dev/null 2>&1 || { echo "tmux is required." >&2; exit 1; }
    [[ -n "$AGENTS_ARG" ]] || { echo "--agent is required for add-agent" >&2; exit 1; }
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      SESSION_NAME="$(resolve_target_session_name)" || exit 1
    fi
    if [[ -z "$SESSION_NAME" ]]; then
      echo "Session does not exist" >&2
      exit 1
    fi
    if ! tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
      echo "Session does not exist: $SESSION_NAME" >&2
      exit 1
    fi

    base_agent="${AGENTS_ARG%%-[0-9]*}"
    if ! agent_in_registry "$base_agent"; then
      echo "Unknown agent: $AGENTS_ARG" >&2
      exit 1
    fi

    load_session_runtime_context "$SESSION_NAME"
    tmux set-environment -t "$SESSION_NAME" MULTIAGENT_INDEX_PATH "$(_canonical_session_index_path "$SESSION_NAME")"
    ensure_session_index_mirrors "$SESSION_NAME"

    acquire_session_topology_lock "$SESSION_NAME" || exit 1
    trap 'release_session_topology_lock' EXIT
    reconcile_session_agent_registry "$SESSION_NAME" >/dev/null

    renumber_existing_exact_instance "$SESSION_NAME" "$base_agent"
    instance_name="$(next_instance_name "$SESSION_NAME" "$base_agent")"
    upper_instance="$(printf '%s' "$instance_name" | tr '[:lower:]-' '[:upper:]_')"
    existing_pane_line="$(tmux show-environment -t "$SESSION_NAME" "MULTIAGENT_PANE_${upper_instance}" 2>/dev/null || true)"
    existing_pane="$(printf '%s' "$existing_pane_line" | sed 's/^[^=]*=//')"
    if [[ -n "$existing_pane" ]]; then
      echo "Agent instance already exists: $instance_name (bug: please report)" >&2
      exit 1
    fi

    required_cmd="$(resolve_agent_executable "$base_agent")" || {
      required_cmd="$(agent_var AGENT_EXECUTABLE "$base_agent")"
      [[ -n "$required_cmd" ]] || required_cmd="$base_agent"
      echo "Required command not found for $base_agent: $required_cmd" >&2
      exit 1
    }

    # Note: ensure_*_agent_send_rules are defined later in the startup flow
    # and not available here. Rules are already configured at session creation
    # time, so we skip them for add-agent.

    if session_uses_per_window_layout "$SESSION_NAME"; then
      new_pane="$(create_agent_window "$SESSION_NAME" "$instance_name")"
      [[ -n "$new_pane" ]] || { echo "Failed to create agent window" >&2; exit 1; }
    else
      target_pane="$(primary_agent_pane_id "$SESSION_NAME")"
      [[ -n "$target_pane" ]] || { echo "No agent pane found in session: $SESSION_NAME" >&2; exit 1; }
      new_pane="$(split_agent_pane "$target_pane" "$WORKSPACE")"
      [[ -n "$new_pane" ]] || { echo "Failed to create pane" >&2; exit 1; }
      configure_agent_pane_defaults "$new_pane"
      user_panes_csv="$(session_user_pane_value "$SESSION_NAME")"
      retile_session_preserving_user_panes "$SESSION_NAME" "$user_panes_csv"
    fi

    current_agents="$(session_agents_value "$SESSION_NAME")"
    updated_agents="$(python3 - "$REPO_ROOT" "$current_agents" "$instance_name" <<'PYEOF'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
agents_csv = sys.argv[2]
instance_name = sys.argv[3]
sys.path.insert(0, str(repo_root / "src"))
from multiagent_chat.multiagent.agents import agents_to_csv, append_instance, parse_agents_csv

print(agents_to_csv(append_instance(parse_agents_csv(agents_csv), instance_name)))
PYEOF
    )"
    tmux set-environment -t "$SESSION_NAME" "MULTIAGENT_PANE_${upper_instance}" "$new_pane"
    tmux set-environment -t "$SESSION_NAME" MULTIAGENT_AGENTS "$updated_agents"
    write_session_state_file "$SESSION_NAME"

    start_agent "$new_pane" "$base_agent" "$instance_name"
    initiator_name="${MULTIAGENT_AGENT_NAME:-user}"
    append_session_system_entry "$SESSION_NAME" "$(format_session_topology_message "add-agent" "$instance_name" "$initiator_name")" "session-topology" "add-agent" "$instance_name" "$initiator_name"

    echo "Added agent $instance_name to session: $SESSION_NAME"
    release_session_topology_lock
    trap - EXIT
    exit 0
  fi

  if [[ "$MODE" == "remove-agent" ]]; then
    command -v tmux >/dev/null 2>&1 || { echo "tmux is required." >&2; exit 1; }
    [[ -n "$AGENTS_ARG" ]] || { echo "--agent is required for remove-agent" >&2; exit 1; }
    if [[ -z "$SESSION_NAME" ]] && [[ "$SESSION_NAME_EXPLICIT" -eq 0 ]]; then
      SESSION_NAME="$(resolve_target_session_name)" || exit 1
    fi
    if [[ -z "$SESSION_NAME" ]]; then
      echo "Session does not exist" >&2
      exit 1
    fi
    if ! tmux has-session -t "=$SESSION_NAME" 2>/dev/null; then
      echo "Session does not exist: $SESSION_NAME" >&2
      exit 1
    fi

    instance_name="$(printf '%s' "$AGENTS_ARG" | tr '[:upper:]' '[:lower:]')"
    load_session_runtime_context "$SESSION_NAME"
    tmux set-environment -t "$SESSION_NAME" MULTIAGENT_INDEX_PATH "$(_canonical_session_index_path "$SESSION_NAME")"
    ensure_session_index_mirrors "$SESSION_NAME"

    acquire_session_topology_lock "$SESSION_NAME" || exit 1
    trap 'release_session_topology_lock' EXIT
    reconcile_session_agent_registry "$SESSION_NAME" >/dev/null

    current_agents="$(session_agents_value "$SESSION_NAME")"
    remove_plan="$(python3 - "$REPO_ROOT" "$current_agents" "$instance_name" <<'PYEOF'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
agents_csv = sys.argv[2]
instance_name = sys.argv[3]
sys.path.insert(0, str(repo_root / "src"))
from multiagent_chat.multiagent.agents import agents_to_csv, parse_agents_csv, remove_instance, resolve_canonical_instance

agents = parse_agents_csv(agents_csv)
canonical = resolve_canonical_instance(agents, instance_name)
if not canonical:
    raise SystemExit(2)
remaining_agents = remove_instance(agents, canonical)
print(canonical)
print(len(remaining_agents))
print(agents_to_csv(remaining_agents))
PYEOF
    )"
    remove_plan_status=$?
    if [[ "$remove_plan_status" -eq 2 ]]; then
      echo "Agent instance not in this session: $AGENTS_ARG (current: ${current_agents:-none})" >&2
      exit 1
    fi
    [[ "$remove_plan_status" -eq 0 ]] || exit "$remove_plan_status"
    canonical="$(printf '%s\n' "$remove_plan" | sed -n '1p')"
    remaining="$(printf '%s\n' "$remove_plan" | sed -n '2p')"
    updated_agents="$(printf '%s\n' "$remove_plan" | sed -n '3p')"
    if [[ "$remaining" -lt 1 ]]; then
      echo "Cannot remove the last agent pane" >&2
      exit 1
    fi

    upper_instance="$(printf '%s' "$canonical" | tr '[:lower:]-' '[:upper:]_')"
    pane_line="$(tmux show-environment -t "$SESSION_NAME" "MULTIAGENT_PANE_${upper_instance}" 2>/dev/null)" || {
      echo "Failed to query tmux pane state for $canonical" >&2
      exit 1
    }
    pane_id="$(printf '%s' "$pane_line" | sed 's/^[^=]*=//')"
    if [[ -z "$pane_id" ]]; then
      echo "No tmux pane recorded for instance: $canonical" >&2
      exit 1
    fi
    user_panes_csv="$(session_user_pane_value "$SESSION_NAME")"
    if [[ -n "$user_panes_csv" ]]; then
      IFS=',' read -ra _up_ids <<< "$user_panes_csv"
      for _up in "${_up_ids[@]}"; do
        [[ -n "$_up" && "$_up" == "$pane_id" ]] && { echo "Refusing to remove a user/terminal pane" >&2; exit 1; }
      done
    fi

    if [[ "${TMUX_PANE:-}" == "$pane_id" ]] && [[ "${MULTIAGENT_REMOVE_HELPER:-0}" != "1" ]]; then
      if command -v nohup >/dev/null 2>&1; then
        nohup env \
          MULTIAGENT_REMOVE_HELPER=1 \
          MULTIAGENT_SKIP_DEPS_CHECK=1 \
          MULTIAGENT_SESSION="$SESSION_NAME" \
          MULTIAGENT_TMUX_SOCKET="$TMUX_SOCKET_NAME" \
          "$SCRIPT_DIR/multiagent" remove-agent --session "$SESSION_NAME" --agent "$canonical" \
          >/dev/null 2>&1 </dev/null &
      else
        env \
          MULTIAGENT_REMOVE_HELPER=1 \
          MULTIAGENT_SKIP_DEPS_CHECK=1 \
          MULTIAGENT_SESSION="$SESSION_NAME" \
          MULTIAGENT_TMUX_SOCKET="$TMUX_SOCKET_NAME" \
          "$SCRIPT_DIR/multiagent" remove-agent --session "$SESSION_NAME" --agent "$canonical" \
          >/dev/null 2>&1 </dev/null &
      fi
      disown >/dev/null 2>&1 || true
      echo "Scheduled removal of agent $canonical from session: $SESSION_NAME"
      exit 0
    fi

    if session_uses_per_window_layout "$SESSION_NAME"; then
      window_target="$(window_target_for_pane "$pane_id")"
      [[ -n "$window_target" ]] || { echo "No tmux window recorded for instance: $canonical" >&2; exit 1; }
      if ! kill_window_target "$window_target"; then
        echo "tmux kill-window failed for $window_target" >&2
        exit 1
      fi
    else
      if ! kill_pane_target "$pane_id"; then
        echo "tmux kill-pane failed for $pane_id" >&2
        exit 1
      fi
    fi

    tmux set-environment -t "$SESSION_NAME" -u "MULTIAGENT_PANE_${upper_instance}" 2>/dev/null || true
    tmux set-environment -t "$SESSION_NAME" MULTIAGENT_AGENTS "$updated_agents"

    if ! session_uses_per_window_layout "$SESSION_NAME"; then
      user_panes_csv="$(session_user_pane_value "$SESSION_NAME")"
      retile_session_preserving_user_panes "$SESSION_NAME" "$user_panes_csv"
    fi

    write_session_state_file "$SESSION_NAME"
    initiator_name="${MULTIAGENT_AGENT_NAME:-user}"
    append_session_system_entry "$SESSION_NAME" "$(format_session_topology_message "remove-agent" "$canonical" "$initiator_name")" "session-topology" "remove-agent" "$canonical" "$initiator_name"
    echo "Removed agent $canonical from session: $SESSION_NAME"
    release_session_topology_lock
    trap - EXIT
    exit 0
  fi
}
