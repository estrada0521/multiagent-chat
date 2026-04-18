#!/usr/bin/env bash

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
