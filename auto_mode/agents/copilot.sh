AUTO_MODE_APPROVAL_KEY="Enter"

auto_mode_agent_needs_approval() {
  local content="${1:-}"
  printf '%s\n' "$content" | grep -qF "Allow directory access" && return 0
  printf '%s\n' "$content" | grep -qF "Do you want to allow this?" && return 0
  printf '%s\n' "$content" | grep -qF "Yes, and add these directories to the allowed list"
}
