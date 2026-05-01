#!/usr/bin/env bash

set -euo pipefail

if [[ -n "${AGENT_INDEX_SESSION_SH:-}" ]]; then
  return 0
fi
AGENT_INDEX_SESSION_SH=1

active_repo_log_roots() {
  local session workspace log_dir bin_dir
  while IFS= read -r session; do
    [[ -n "$session" ]] || continue
    bin_dir="$(session_bin_dir_value "$session")"
    [[ -n "$bin_dir" ]] || continue
    bin_dir="$(realpath_or_echo "$bin_dir")"
    [[ "$bin_dir" == "$SCRIPT_DIR" ]] || continue
    log_dir="$(session_log_dir_value "$session")"
    [[ -n "$log_dir" ]] && printf '%s\n' "$log_dir"
    workspace="$(session_workspace_value "$session")"
    [[ -n "$workspace" ]] && printf '%s\n' "${workspace}/logs"
  done < <(tmux list-sessions -F '#S' 2>/dev/null || true)
}

repo_log_roots() {
  local roots=() candidate resolved existing
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    resolved="$(realpath_or_echo "$candidate")"
    existing=0
    for candidate in "${roots[@]:-}"; do
      if [[ "$candidate" == "$resolved" ]]; then
        existing=1
        break
      fi
    done
    [[ "$existing" -eq 1 ]] || roots+=("$resolved")
  done < <(active_repo_log_roots)
  for candidate in \
    "${MULTIAGENT_LOG_DIR:-}" \
    "${MULTIAGENT_WORKSPACE:-}/logs" \
    "${REPO_ROOT}/logs"
  do
    [[ -n "$candidate" ]] || continue
    resolved="$(realpath_or_echo "$candidate")"
    existing=0
    for candidate in "${roots[@]:-}"; do
      if [[ "$candidate" == "$resolved" ]]; then
        existing=1
        break
      fi
    done
    [[ "$existing" -eq 1 ]] || roots+=("$resolved")
  done
  printf '%s\n' "${roots[@]}"
}

find_archived_index_files() {
  local session_filter="${1:-}" root
  while IFS= read -r root; do
    [[ -d "$root" ]] || continue
    if [[ -n "$session_filter" ]]; then
      find "$root" -maxdepth 2 -type f -path "*/${session_filter}_*/.agent-index.jsonl" 2>/dev/null
    else
      find "$root" -maxdepth 2 -type f -name '.agent-index.jsonl' 2>/dev/null
    fi
  done < <(repo_log_roots)
}

latest_archived_index_file() {
  local session_filter="${1:-}"
  find_archived_index_files "$session_filter" | sort | tail -n 1
}

matching_archived_sessions() {
  local index_file dir base session
  while IFS= read -r index_file; do
    [[ -n "$index_file" ]] || continue
    dir="$(basename "$(dirname "$index_file")")"
    base="${dir%_*}"
    session="${base%_*}"
    [[ -n "$session" ]] && printf '%s\n' "$session"
  done < <(find_archived_index_files)
}

session_workspace_value() {
  local session="$1"
  tmux show-environment -t "$session" MULTIAGENT_WORKSPACE 2>/dev/null | sed 's/^[^=]*=//' || true
}

session_log_dir_value() {
  local session="$1"
  tmux show-environment -t "$session" MULTIAGENT_LOG_DIR 2>/dev/null | sed 's/^[^=]*=//' || true
}

session_index_path_value() {
  local session="$1"
  tmux show-environment -t "$session" MULTIAGENT_INDEX_PATH 2>/dev/null | sed 's/^[^=]*=//' || true
}

session_bin_dir_value() {
  local session="$1"
  tmux show-environment -t "$session" MULTIAGENT_BIN_DIR 2>/dev/null | sed 's/^[^=]*=//' || true
}

matching_repo_sessions() {
  local session bin_dir
  while IFS= read -r session; do
    [[ -n "$session" ]] || continue
    bin_dir="$(session_bin_dir_value "$session")"
    [[ -n "$bin_dir" ]] || continue
    bin_dir="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$bin_dir" 2>/dev/null || printf '%s' "$bin_dir")"
    [[ "$bin_dir" == "$SCRIPT_DIR" ]] || continue
    printf '%s\n' "$session"
  done < <(tmux list-sessions -F '#S' 2>/dev/null || true)
}

available_agents() {
  local agents_str
  agents_str="$(tmux show-environment -t "$SESSION_NAME" MULTIAGENT_AGENTS 2>/dev/null | sed 's/^[^=]*=//' || true)"
  if [[ -n "$agents_str" ]]; then
    printf '%s\n' "$agents_str"
    return
  fi
  local agents=() agent upper pane
  for agent in "${_ALL_AGENTS_ARR[@]}"; do
    upper="$(printf '%s' "$agent" | tr '[:lower:]' '[:upper:]')"
    pane="$(tmux show-environment -t "$SESSION_NAME" "MULTIAGENT_PANE_${upper}" 2>/dev/null | sed 's/^[^=]*=//' || true)"
    if [[ -n "$pane" ]]; then
      agents+=("$agent")
    fi
  done
  printf '%s\n' "$(IFS=,; echo "${agents[*]}")"
}

resolve_session_log_dir() {
  local log_dir="${MULTIAGENT_LOG_DIR:-}"
  local index_path="${MULTIAGENT_INDEX_PATH:-}"
  local existing_dir session_dir dir jsonl
  local repo_session_dir="${REPO_ROOT}/logs/${SESSION_NAME}"
  if [[ -z "$index_path" && -n "$SESSION_NAME" ]]; then
    index_path="$(session_index_path_value "$SESSION_NAME")"
  fi
  if [[ -n "$index_path" ]]; then
    mkdir -p "$(dirname "$index_path")"
    printf '%s\n' "$(dirname "$index_path")"
    return
  fi
  if [[ -z "$log_dir" && -n "$SESSION_NAME" ]]; then
    log_dir="$(session_log_dir_value "$SESSION_NAME")"
  fi
  if [[ -d "$repo_session_dir" ]]; then
    printf '%s\n' "$repo_session_dir"
    return
  fi
  if [[ -z "$log_dir" ]]; then
    log_dir="${SESSION_WORKSPACE:-${MULTIAGENT_WORKSPACE:-}}/logs"
  fi
  if [[ "$log_dir" == "/logs" || -z "$log_dir" ]]; then
    log_dir="${REPO_ROOT}/logs"
  fi
  session_dir="${log_dir}/${SESSION_NAME}"
  if [[ -d "$session_dir" ]]; then
    printf '%s\n' "$session_dir"
    return
  fi
  existing_dir=""
  while IFS= read -r jsonl; do
    [[ -f "$jsonl" ]] || continue
    dir="$(dirname "$jsonl")"
    if [[ -z "$existing_dir" ]]; then
      existing_dir="$dir"
    else
      [[ $(wc -c < "$jsonl") -gt $(wc -c < "${existing_dir}/.agent-index.jsonl") ]] && existing_dir="$dir"
    fi
  done < <(find "$log_dir" -maxdepth 2 -name ".agent-index.jsonl" -path "*/${SESSION_NAME}_*" 2>/dev/null)
  if [[ -z "$existing_dir" ]]; then
    existing_dir="$(find "$log_dir" -maxdepth 1 -type d -name "${SESSION_NAME}_*" 2>/dev/null | sort | tail -n 1)"
  fi
  if [[ -z "$existing_dir" ]]; then
    existing_dir="$(find "${MULTIAGENT_WORKSPACE:-$PWD}" -maxdepth 3 -type d -name "${SESSION_NAME}_*" 2>/dev/null | sort | tail -n 1)"
  fi
  if [[ -n "$existing_dir" ]]; then
    printf '%s\n' "$existing_dir"
  else
    printf '%s\n' "$session_dir"
  fi
}

resolve_session_name() {
  local matched=()
  if [[ -n "$SESSION_NAME" ]]; then
    printf '%s\n' "$SESSION_NAME"
    return 0
  fi

  if [[ -n "${TMUX:-}" ]]; then
    SESSION_NAME="$(tmux display-message -p '#{session_name}' 2>/dev/null || true)"
    if [[ -n "$SESSION_NAME" ]]; then
      printf '%s\n' "$SESSION_NAME"
      return 0
    fi
  fi

  while IFS= read -r session; do
    [[ -n "$session" ]] && matched+=("$session")
  done < <(matching_repo_sessions)

  if [[ ${#matched[@]} -eq 1 ]]; then
    printf '%s\n' "${matched[0]}"
    return 0
  fi

  if [[ ${#matched[@]} -gt 1 ]]; then
    echo "Multiple active multiagent sessions exist; specify --session." >&2
    return 1
  fi

  matched=()
  while IFS= read -r session; do
    [[ -n "$session" ]] && matched+=("$session")
  done < <(matching_archived_sessions | sort -u)

  if [[ ${#matched[@]} -eq 1 ]]; then
    printf '%s\n' "${matched[0]}"
    return 0
  fi

  if [[ ${#matched[@]} -gt 1 ]]; then
    echo "Multiple archived multiagent sessions exist; specify --session." >&2
    return 1
  fi

  echo "No active or archived multiagent session found for this workspace." >&2
  return 1
}
