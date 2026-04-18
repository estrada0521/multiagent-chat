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
    canonical.touch()
PYEOF
}

ensure_session_index_mirrors() {
  local session="$1"
  _ensure_canonical_index_healthy "$session"
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
