ensure_codex_agent_send_rules() {
  local rules_file="${CODEX_HOME:-$HOME/.codex}/rules/default.rules"
  mkdir -p "$(dirname "$rules_file")"
  touch "$rules_file"
  local tool_rule
  printf -v tool_rule 'prefix_rule(pattern=["%s/agent-send", "--session", "%s"], decision="allow")' "$SCRIPT_DIR" "$SESSION_NAME"
  for rule in 'prefix_rule(pattern=["agent-send"], decision="allow")' \
              'prefix_rule(pattern=["./bin/agent-send"], decision="allow")' \
              "$tool_rule"; do
    grep -Fqx "$rule" "$rules_file" || printf '%s\n' "$rule" >> "$rules_file"
  done
}

ensure_gemini_agent_send_rules() {
  local settings_file="$WORKSPACE/.gemini/settings.json"
  mkdir -p "$(dirname "$settings_file")"
  [[ -f "$settings_file" ]] || echo '{}' > "$settings_file"
  python3 - "$settings_file" "$SCRIPT_DIR" <<'PYEOF'
import json, sys
settings_file, script_dir = sys.argv[1], sys.argv[2]
with open(settings_file, 'r') as f: data = json.load(f)
data.setdefault('tools', {}).setdefault('allowed', [])
for r in [f'run_shell_command({script_dir}/agent-send)', 'run_shell_command(agent-send)']:
    if r not in data['tools']['allowed']:
        data['tools']['allowed'].append(r)
with open(settings_file, 'w') as f: json.dump(data, f, indent=2)
PYEOF
}

ensure_qwen_agent_send_rules() {
  local settings_file="$WORKSPACE/.qwen/settings.json"
  mkdir -p "$(dirname "$settings_file")"
  [[ -f "$settings_file" ]] || echo '{}' > "$settings_file"
  python3 - "$settings_file" "$SCRIPT_DIR" <<'PYEOF'
import json, sys
settings_file, script_dir = sys.argv[1], sys.argv[2]
with open(settings_file, 'r') as f: data = json.load(f)
data.setdefault('tools', {}).setdefault('allowed', [])
for r in [f'run_shell_command({script_dir}/agent-send)', 'run_shell_command(agent-send)']:
    if r not in data['tools']['allowed']:
        data['tools']['allowed'].append(r)
with open(settings_file, 'w') as f: json.dump(data, f, indent=2)
PYEOF
}

ensure_claude_agent_send_rules() {
  local settings_file="$WORKSPACE/.claude/settings.local.json"
  local rules=(
    "Bash($SCRIPT_DIR/*)"
    "Bash(agent-send *)"
    "Bash(tmux *)"
    "Bash(printf \\\\033c*)"
    "Bash(clear*)"
  )
  mkdir -p "$(dirname "$settings_file")"
  [[ -f "$settings_file" ]] || echo '{"permissions": {"allow": []}}' > "$settings_file"
  local rules_json
  rules_json="$(printf '"%s", ' "${rules[@]}" | sed 's/, $//')"
  python3 - "$settings_file" <<PYEOF
import json, sys
path = sys.argv[1]
with open(path, 'r') as f: data = json.load(f)
data.setdefault('permissions', {}).setdefault('allow', [])
for r in [$rules_json]:
    if r not in data['permissions']['allow']:
        data['permissions']['allow'].append(r)
with open(path, 'w') as f: json.dump(data, f, indent=2)
PYEOF
}

ensure_copilot_agent_send_rules() {
  local config_file="${HOME}/.copilot/config.json"
  mkdir -p "$(dirname "$config_file")"
  [[ -f "$config_file" ]] || echo '{"trusted_folders": []}' > "$config_file"
  python3 - "$config_file" "$WORKSPACE" <<'PYEOF'
import json, sys
path, folder = sys.argv[1], sys.argv[2]
with open(path, 'r') as f: data = json.load(f)
data.setdefault('trusted_folders', [])
if folder not in data['trusted_folders']:
    data['trusted_folders'].append(folder)
with open(path, 'w') as f: json.dump(data, f, indent=2)
PYEOF

  local instructions_dir="$WORKSPACE/.github"
  local instructions_file="$instructions_dir/copilot-instructions.md"
  mkdir -p "$instructions_dir"
  cat > "$instructions_file" << INSTREOF
# Multiagent 環境

あなたは **tmux セッション** 上で Claude・Codex・Gemini・Copilot・Cursor・Grok・OpenCode・Qwen・Aider などと並行して動作しています。
セッション名: \`${SESSION_NAME}\`（環境変数 \`MULTIAGENT_SESSION\` でも確認可能）

## 他のエージェントにメッセージを送る

\`agent-send\` コマンドを使います。このコマンドはすでに PATH に追加済みです。本文は stdin で渡します。

\`\`\`bash
printf '%s' 'メッセージ' | agent-send <claude|codex|gemini|kimi|copilot|cursor|grok|opencode|qwen|aider|others|claude,codex>
\`\`\`

本文は stdin で渡します。複数行でも agent-send の基本形に寄せてください。

もし \`agent-send\` が見つからない場合は絶対パスで実行できます：

\`\`\`bash
printf '%s' 'メッセージ' | "${SCRIPT_DIR}/agent-send" <target>
\`\`\`
INSTREOF
}

ensure_agent_send_rules_for_selected_agents() {
  local agent
  for agent in "${SELECTED_AGENTS[@]}"; do
    case "$agent" in
      codex)   ensure_codex_agent_send_rules ;;
      gemini)  ensure_gemini_agent_send_rules ;;
      qwen)    ensure_qwen_agent_send_rules ;;
      claude)  ensure_claude_agent_send_rules ;;
      copilot) ensure_copilot_agent_send_rules ;;
    esac
  done
}
