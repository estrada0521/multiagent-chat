#!/usr/bin/env bash

set -euo pipefail

if [[ -n "${AGENT_INDEX_BROWSER_SH:-}" ]]; then
  return 0
fi
AGENT_INDEX_BROWSER_SH=1

open_url_in_safari_front_window_tab() {
  local chat_url="$1"
  [[ "$(uname -s)" == "Darwin" ]] || return 1
  command -v osascript >/dev/null 2>&1 || return 1
  /usr/bin/osascript - "$chat_url" <<'OSA' >/dev/null 2>&1
on run argv
  set targetURL to item 1 of argv as text
  tell application "Safari"
    if not running then launch
    delay 0.2
    activate
    if (count of windows) is 0 then
      make new document
      set URL of current tab of front window to targetURL
    else
      tell front window
        set current tab to (make new tab with properties {URL:targetURL})
      end tell
    end if
  end tell
end run
OSA
}

open_chat_window() {
  local chat_url="$1"
  if [[ "${MULTIAGENT_OPEN_WITH_CHROME:-0}" == "1" ]]; then
    local chrome_app="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if [[ "${MULTIAGENT_OPEN_CHAT_REUSE:-1}" != "0" && "$(uname -s)" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
      if pgrep -qf "Google Chrome\\.app" >/dev/null 2>&1; then
        open -a "Google Chrome" "$chat_url" >/dev/null 2>&1 && return 0
      fi
    fi
    if [[ -x "$chrome_app" ]]; then
      nohup "$chrome_app" --app="$chat_url" --window-size=720,920 >/dev/null 2>&1 </dev/null &
      disown || true
      return 0
    fi
  fi

  if command -v open >/dev/null 2>&1; then
    if [[ "$(uname -s)" == "Darwin" && "${MULTIAGENT_OPEN_WITH_SAFARI:-1}" != "0" && -d "/Applications/Safari.app" ]]; then
      if open_url_in_safari_front_window_tab "$chat_url"; then
        return 0
      fi
      printf '%s\n' "agent-index: Safari で URL を開けませんでした。システム設定 → プライバシーとセキュリティ → 自動化 で、この端末（または Cursor）から Safari を許可するか、次を手で開いてください: $chat_url" >&2
      return 1
    fi
    open "$chat_url" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$chat_url" >/dev/null 2>&1 || true
    return 0
  fi

  return 1
}
