#!/usr/bin/env bash

set -euo pipefail

if [[ -n "${AGENT_INDEX_SESSION_SH:-}" ]]; then
  return 0
fi
AGENT_INDEX_SESSION_SH=1

agent_index_session_log_dir() {
  local session="$1"
  printf '%s/%s\n' "$AGENT_WINDOW_LOG_DIR" "$session"
}

agent_index_ensure_session_index_mirrors() {
  local session="$1" session_dir index_path link_dir link_path
  session_dir="$(agent_index_session_log_dir "$session")"
  index_path="${session_dir}/.agent-index.jsonl"
  mkdir -p "$session_dir"
  [[ -e "$index_path" ]] || : > "$index_path"
  [[ -n "${SESSION_WORKSPACE:-}" ]] || return 0
  link_dir="${SESSION_WORKSPACE}/logs/${session}"
  link_path="${link_dir}/.agent-index.jsonl"
  mkdir -p "$link_dir"
  [[ -e "$link_path" || -L "$link_path" ]] && rm -f "$link_path"
  ln -s "$index_path" "$link_path"
}

repo_log_roots() {
  printf '%s\n' "$AGENT_WINDOW_LOG_DIR"
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
  printf '\n'
}

resolve_session_log_dir() {
  local session_dir
  if [[ "${SESSION_IS_ACTIVE:-0}" == "1" && -n "$SESSION_NAME" ]]; then
    agent_index_ensure_session_index_mirrors "$SESSION_NAME"
    printf '%s\n' "$(agent_index_session_log_dir "$SESSION_NAME")"
    return
  fi
  session_dir="$(agent_index_session_log_dir "$SESSION_NAME")"
  mkdir -p "$session_dir"
  printf '%s\n' "$session_dir"
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
