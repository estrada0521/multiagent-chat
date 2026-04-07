#!/usr/bin/env bash

_session_log_dir() {
  local session="$1" base_dir="$2"
  local created_epoch created_at updated_at old_dir session_dir
  created_epoch="$(tmux display-message -p -t "$session" '#{session_created}' 2>/dev/null || true)"
  if [[ -n "$created_epoch" ]]; then
    created_at="$(date -r "$created_epoch" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date '+%Y-%m-%d %H:%M:%S')"
  else
    created_at="$(date '+%Y-%m-%d %H:%M:%S')"
  fi
  updated_at="$(date '+%Y-%m-%d %H:%M:%S')"
  mkdir -p "$base_dir"
  session_dir="${base_dir}/${session}"
  if [[ ! -d "$session_dir" ]]; then
    old_dir="$(find "$base_dir" -maxdepth 1 -type d -name "${session}_*" 2>/dev/null | sort | tail -n 1)"
    if [[ -n "$old_dir" ]] && [[ "$old_dir" != "$session_dir" ]]; then
      mv "$old_dir" "$session_dir"
    else
      mkdir -p "$session_dir"
    fi
  else
    mkdir -p "$session_dir"
  fi
  printf '%s\t%s\t%s\n' "$session_dir" "$created_at" "$updated_at"
}

_canonical_session_log_dir() {
  local session="$1"
  printf '%s/%s\n' "$CENTRAL_LOG_DIR" "$session"
}

_canonical_session_index_path() {
  local session="$1"
  printf '%s/.agent-index.jsonl\n' "$(_canonical_session_log_dir "$session")"
}

_ensure_canonical_index_healthy() {
  local session="$1" canonical_index
  canonical_index="$(_canonical_session_index_path "$session")"
  python3 - "$canonical_index" <<'PYEOF'
import os
import shutil
import sys
from pathlib import Path

canonical = Path(sys.argv[1])
canonical.parent.mkdir(parents=True, exist_ok=True)
canonical_abs = canonical.resolve().as_posix() if canonical.exists() else canonical.absolute().as_posix()

def _target_abs(path: Path) -> str:
    target = os.readlink(path)
    if os.path.isabs(target):
        return os.path.abspath(target)
    return os.path.abspath(path.parent / target)

if canonical.is_symlink():
    try:
        if _target_abs(canonical) == os.path.abspath(canonical):
            canonical.unlink()
    except Exception:
        try:
            canonical.unlink()
        except Exception:
            pass

if not canonical.exists():
    backups = sorted(
        canonical.parent.glob(".agent-index.jsonl.backup.*"),
        key=lambda p: p.stat().st_mtime,
    )
    if backups:
        shutil.copy2(backups[-1], canonical)
    else:
        bak = canonical.parent / ".agent-index.jsonl.bak"
        if bak.exists():
            shutil.copy2(bak, canonical)
        else:
            canonical.touch()
PYEOF
}

_merge_index_jsonl_into_canonical() {
  local canonical_path="$1" source_path="$2"
  python3 - "$canonical_path" "$source_path" <<'PYEOF'
import fcntl
import json
import os
import sys

canonical_path, source_path = sys.argv[1:3]
if not os.path.isfile(source_path):
    raise SystemExit(0)

os.makedirs(os.path.dirname(canonical_path), exist_ok=True)
with open(canonical_path, "a+", encoding="utf-8") as canonical:
    fcntl.flock(canonical.fileno(), fcntl.LOCK_EX)
    canonical.seek(0)
    existing_lines = canonical.read().splitlines()
    seen_ids = set()
    seen_raw = set()
    for line in existing_lines:
        raw = line.strip()
        if not raw:
            continue
        seen_raw.add(raw)
        try:
            msg_id = str((json.loads(raw) or {}).get("msg_id") or "").strip()
        except Exception:
            msg_id = ""
        if msg_id:
            seen_ids.add(msg_id)

    appended = []
    with open(source_path, "r", encoding="utf-8", errors="replace") as source:
        for line in source:
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except Exception:
                if raw in seen_raw:
                    continue
                seen_raw.add(raw)
                appended.append(raw)
                continue
            msg_id = str((item or {}).get("msg_id") or "").strip()
            if msg_id:
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
            elif raw in seen_raw:
                continue
            seen_raw.add(raw)
            appended.append(raw)

    if appended:
        canonical.seek(0, os.SEEK_END)
        for raw in appended:
            canonical.write(raw + "\n")
        canonical.flush()
    fcntl.flock(canonical.fileno(), fcntl.LOCK_UN)
PYEOF
}

ensure_session_index_mirror_at_base() {
  local session="$1" base_dir="$2"
  local canonical_index canonical_real canonical_abs alias_dir alias_index alias_abs alias_backup alias_target base_real central_real
  [[ -n "$base_dir" ]] || return 0
  canonical_index="$(_canonical_session_index_path "$session")"
  _ensure_canonical_index_healthy "$session"
  mkdir -p "$(dirname "$canonical_index")"
  touch "$canonical_index"
  canonical_real="$(realpath_or_echo "$canonical_index")"
  canonical_abs="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$canonical_index" 2>/dev/null || printf '%s' "$canonical_index")"
  base_real="$(realpath_or_echo "$base_dir")"
  central_real="$(realpath_or_echo "$CENTRAL_LOG_DIR")"
  [[ "$base_real" == "$central_real" ]] && return 0

  alias_dir="${base_dir}/${session}"
  alias_index="${alias_dir}/.agent-index.jsonl"
  alias_abs="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$alias_index" 2>/dev/null || printf '%s' "$alias_index")"
  [[ "$alias_abs" == "$canonical_abs" ]] && return 0
  mkdir -p "$alias_dir"

  if [[ -L "$alias_index" ]]; then
    alias_target="$(realpath_or_echo "$alias_index")"
    if [[ "$alias_target" == "$canonical_real" ]]; then
      return 0
    fi
    rm -f "$alias_index"
  elif [[ -f "$alias_index" ]]; then
    _merge_index_jsonl_into_canonical "$canonical_index" "$alias_index" || true
    alias_backup="${alias_index}.backup.$(date +%Y%m%d_%H%M%S)"
    mv "$alias_index" "$alias_backup" 2>/dev/null || rm -f "$alias_index"
  elif [[ -e "$alias_index" ]]; then
    return 0
  fi

  ln -s "$canonical_index" "$alias_index" 2>/dev/null || true
}

ensure_session_index_mirrors() {
  local session="$1"
  local canonical_index
  canonical_index="$(_canonical_session_index_path "$session")"
  mkdir -p "$(dirname "$canonical_index")"
  touch "$canonical_index"
  if [[ -z "${LOG_DIR+x}" ]]; then
    ensure_session_index_mirror_at_base "$session" "${WORKSPACE}/logs"
  elif [[ -n "$LOG_DIR" ]]; then
    ensure_session_index_mirror_at_base "$session" "$LOG_DIR"
  fi
}

_update_session_meta() {
  local session_dir="$1" session="$2" workspace="$3" created_at="$4" updated_at="$5" reason="${6:-manual}" agents_csv="${7:-}"
  local meta_file="${session_dir}/.meta"
  python3 - "$meta_file" "$session" "$workspace" "$created_at" "$updated_at" "$reason" "$agents_csv" <<'PYEOF'
import json, os, sys

path, session, workspace, created_at, updated_at, reason, agents_csv = sys.argv[1:8]
if os.path.exists(path):
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        try:
            with open(path, "r") as f:
                data, _ = json.JSONDecoder().raw_decode(f.read())
        except Exception:
            data = {"session": session, "workspace": workspace, "created_at": created_at, "updated_at": updated_at, "overwrite_count": 0, "overwrites": []}
else:
    data = {"session": session, "workspace": workspace, "created_at": created_at, "updated_at": updated_at, "overwrite_count": 0, "overwrites": []}

data["session"] = session
data["workspace"] = workspace
data["created_at"] = data.get("created_at", created_at)
data["updated_at"] = updated_at
overwrites = data.setdefault("overwrites", [])
overwrites.append({"timestamp": updated_at, "reason": reason})
data["overwrite_count"] = len(overwrites)
if agents_csv.strip():
    data["agents"] = [a.strip() for a in agents_csv.split(",") if a.strip()]

with open(path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=True)
    f.write("\n")
PYEOF
}

_save_pane_logs_to_dir() {
  local session="$1" base_dir="$2" reason="${3:-manual}"
  local resolved session_dir created_at updated_at
  resolved="$(_session_log_dir "$session" "$base_dir")"
  IFS=$'\t' read -r session_dir created_at updated_at <<< "$resolved"
  local agents_str saved=0
  agents_str="$(tmux show-environment -t "$session" MULTIAGENT_AGENTS 2>/dev/null | sed 's/^[^=]*=//' || true)"
  [[ -z "$agents_str" ]] && agents_str="$ALL_AGENTS_CSV"
  IFS=',' read -ra _save_agents <<< "$agents_str"
  for instance in "${_save_agents[@]}"; do
    local upper pane_id ans_file txt_file
    upper="$(echo "$instance" | tr '[:lower:]-' '[:upper:]_')"
    pane_id="$(tmux show-environment -t "$session" "MULTIAGENT_PANE_${upper}" 2>/dev/null | cut -d= -f2 || true)"
    [[ -z "$pane_id" ]] && continue
    ans_file="${session_dir}/${instance}.ans"
    txt_file="${session_dir}/${instance}.log"
    # Capture to a temp file first so we can compare sizes before overwriting
    local tmp_ans="${ans_file}.tmp.$$"
    tmux capture-pane -p -e -S - -t "$pane_id" 2>/dev/null > "$tmp_ans" || true
    # Protect old capture when a pane reset is detected.
    # Primary trigger: new capture is less than half the old size (>1KB).
    # Secondary trigger: sizes are comparable but content hash differs completely
    # and the old file is non-trivial.  This catches agent restarts that produce
    # similar-length but entirely different output.
    if [[ -f "$ans_file" ]]; then
      local old_size new_size
      old_size="$(wc -c < "$ans_file" 2>/dev/null)" || old_size=0
      new_size="$(wc -c < "$tmp_ans" 2>/dev/null)" || new_size=0
      local _do_protect=0 _protect_reason="size"
      # Primary: significant size shrink
      if [[ "$old_size" -gt 1024 && "$new_size" -gt 0 && $((new_size * 2)) -lt "$old_size" ]]; then
        _do_protect=1
      # Secondary: similar size but completely different content
      elif [[ "$old_size" -gt 1024 && "$new_size" -gt 0 && $((new_size * 2)) -ge "$old_size" ]]; then
        local old_hash new_hash
        old_hash="$(head -c 4096 "$ans_file" | shasum -a 256 | cut -d' ' -f1 2>/dev/null)" || old_hash=""
        new_hash="$(head -c 4096 "$tmp_ans" | shasum -a 256 | cut -d' ' -f1 2>/dev/null)" || new_hash=""
        if [[ -n "$old_hash" && -n "$new_hash" && "$old_hash" != "$new_hash" ]]; then
          # Also check the tail to distinguish append-only growth from reset
          local old_tail new_tail
          old_tail="$(tail -c 1024 "$ans_file" | shasum -a 256 | cut -d' ' -f1 2>/dev/null)" || old_tail=""
          new_tail="$(tail -c 1024 "$tmp_ans" | shasum -a 256 | cut -d' ' -f1 2>/dev/null)" || new_tail=""
          if [[ -n "$old_tail" && -n "$new_tail" && "$old_tail" != "$new_tail" ]]; then
            _do_protect=1
            _protect_reason="hash"
          fi
        fi
      fi
      if [[ "$_do_protect" -eq 1 ]]; then
        local ts protect_ans protect_txt
        ts="$(date +%Y%m%d_%H%M%S)"
        protect_ans="${session_dir}/${instance}.${ts}.protected.ans"
        protect_txt="${session_dir}/${instance}.${ts}.protected.log"
        cp "$ans_file" "$protect_ans" 2>/dev/null || true
        [[ -f "$txt_file" ]] && cp "$txt_file" "$protect_txt" 2>/dev/null || true
        echo "[multiagent] Pane content changed (${old_size}->${new_size} bytes, ${_protect_reason}). Protected: $protect_ans" >&2
      fi
    fi
    mv "$tmp_ans" "$ans_file"
    perl -pe 's/\x1b\[[0-9;?]*[a-zA-Z]//g; s/\x1b\][^\x07]*\x07//g; s/\x1b[(){][AB012]//g; s/\x1b[=>]//g; s/\r//g' < "$ans_file" > "$txt_file" || true
    echo "[multiagent] Updated: $ans_file / $txt_file" >&2
    saved=1
  done
  if [[ "$saved" -eq 1 ]]; then
    _update_session_meta "$session_dir" "$session" "$WORKSPACE" "$created_at" "$updated_at" "$reason" "$agents_str"
    echo "[multiagent] Session log dir: $session_dir" >&2
  fi
}

save_session_logs() {
  local session="$1" reason="${2:-manual}"

  # Logging disabled only when --log-dir '' was explicitly given
  if [[ -z "${LOG_DIR+x}" ]]; then
    local workspace_log_dir="${WORKSPACE}/logs"
  elif [[ -z "$LOG_DIR" ]]; then
    return 0                              # explicitly empty → disabled
  else
    local workspace_log_dir="$LOG_DIR"
  fi

  _save_pane_logs_to_dir "$session" "$workspace_log_dir" "$reason"

  if [[ "${workspace_log_dir}" != "${CENTRAL_LOG_DIR}" ]]; then
    _save_pane_logs_to_dir "$session" "$CENTRAL_LOG_DIR" "$reason"
  fi
}

append_session_system_entry() {
  local session="$1" message="$2" kind="${3:-session-topology}" action="${4:-}" subject="${5:-}" initiator="${6:-}"
  local index_path
  index_path="$(_canonical_session_index_path "$session")"
  ensure_session_index_mirrors "$session"
  python3 - "$index_path" "$session" "$message" "$kind" "$action" "$subject" "$initiator" <<'PYEOF'
import fcntl
import json
import os
import sys
import uuid
from datetime import datetime

path, session, message, kind, action, subject, initiator = sys.argv[1:8]
entry = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "session": session,
    "sender": "system",
    "targets": [],
    "message": message,
    "msg_id": uuid.uuid4().hex[:12],
    "kind": kind,
}
if action:
    entry["topology_action"] = action
if subject:
    entry["agent_instance"] = subject
if initiator:
    entry["initiator"] = initiator
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "a", encoding="utf-8") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
PYEOF
}

format_session_topology_message() {
  local action="$1" subject="$2" initiator="$3"
  local actor="${initiator:-user}"
  case "$action" in
    add-agent) printf 'Add Agent: %s -> %s\n' "$actor" "$subject" ;;
    remove-agent) printf 'Remove Agent: %s -> %s\n' "$actor" "$subject" ;;
    *) printf 'Session Topology: %s -> %s (%s)\n' "$actor" "$subject" "$action" ;;
  esac
}
