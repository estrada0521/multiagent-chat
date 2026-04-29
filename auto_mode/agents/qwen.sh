AUTO_MODE_APPROVAL_KEY="Enter"

auto_mode_agent_needs_approval() {
  local content="${1:-}"
  printf '%s\n' "$content" | grep -qiF "Allow execution of:" && return 0
  printf '%s\n' "$content" | grep -qiF "yes, allow once" && return 0
  printf '%s\n' "$content" | grep -qiF "Waiting for user confirmation"
}
