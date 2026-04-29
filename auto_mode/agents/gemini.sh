AUTO_MODE_APPROVAL_KEY="Enter"

auto_mode_agent_needs_approval() {
  local content="${1:-}"
  printf '%s\n' "$content" | grep -qF "Action Required" && return 0
  printf '%s\n' "$content" | grep -qF "Allow once"
}
