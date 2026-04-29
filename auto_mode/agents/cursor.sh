AUTO_MODE_APPROVAL_KEY="y"

auto_mode_agent_needs_approval() {
  local content="${1:-}"
  printf '%s\n' "$content" | grep -qF "Run this command?" && return 0
  printf '%s\n' "$content" | grep -qF "Run (once) (y)" && return 0
  printf '%s\n' "$content" | grep -qF "Run Everything" && return 0
  printf '%s\n' "$content" | grep -qF "Allow this web fetch?" && return 0
  printf '%s\n' "$content" | grep -qF "Fetch (y)"
  printf '%s\n' "$content" | grep -qF "Delete (y)"
}
