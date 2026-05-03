AUTO_MODE_APPROVAL_KEY="y"

auto_mode_agent_needs_approval() {
  local content="${1:-}"
  
  if printf '%s\n' "$content" | grep -qiE "hit your usage limit|limit reached"; then
    local safe_pane="${pane_id//%/_}"
    > "/tmp/multiagent_cursor_usage_limit_${safe_pane}"
    return 1
  fi

  printf '%s\n' "$content" | grep -qF "Run this command?" && return 0
  printf '%s\n' "$content" | grep -qF "Run (once) (y)" && return 0
  printf '%s\n' "$content" | grep -qF "Run Everything" && return 0
  printf '%s\n' "$content" | grep -qF "Allow this web fetch?" && return 0
  printf '%s\n' "$content" | grep -qF "Fetch (y)" && return 0
  printf '%s\n' "$content" | grep -qF "Delete (y)" && return 0
}
