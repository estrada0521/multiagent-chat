from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path


def collect_global_native_log_claims(
    runtime,
    *,
    global_log_claim_refresh_seconds: float,
    global_log_claim_ttl_seconds: float,
    subprocess_module=subprocess,
    time_module=time,
    path_class=Path,
) -> dict[str, tuple[str, str]]:
    now = time_module.time()
    if now - runtime._global_log_claims_fetched_at < float(global_log_claim_refresh_seconds):
        return runtime._global_log_claims

    claims: dict[str, tuple[str, str]] = {}
    base = path_class(runtime.log_dir)
    if not base.exists():
        runtime._global_log_claims = claims
        runtime._global_log_claims_fetched_at = now
        return claims

    active_sessions: set[str] | None = None
    try:
        sessions_res = subprocess_module.run(
            [*runtime.tmux_prefix, "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if sessions_res.returncode == 0:
            active_sessions = {
                line.strip()
                for line in (sessions_res.stdout or "").splitlines()
                if line.strip()
            }
    except Exception:
        active_sessions = None

    cursor_paths = (
        ("codex_cursors", "codex"),
        ("cursor_cursors", "cursor"),
        ("copilot_cursors", "copilot"),
        ("qwen_cursors", "qwen"),
        ("claude_cursors", "claude"),
        ("gemini_cursors", "gemini"),
    )
    for state_path in base.glob("*/.agent-index-sync-state.json"):
        try:
            session_name = state_path.parent.name
            if session_name == runtime.session_name:
                continue
            if active_sessions is not None and session_name not in active_sessions:
                continue
            if now - state_path.stat().st_mtime > float(global_log_claim_ttl_seconds):
                continue
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.warning("Skipping unreadable sync state %s: %s", state_path, exc)
            continue
        except OSError:
            continue

        if not isinstance(raw, dict):
            continue
        for key, _type in cursor_paths:
            value = raw.get(key)
            if not isinstance(value, dict):
                continue
            for claimant_agent, cursor in value.items():
                if not isinstance(claimant_agent, str):
                    continue
                cursor_path = cursor[0] if isinstance(cursor, (list, tuple)) else ""
                if not isinstance(cursor_path, str) or not cursor_path:
                    continue
                claims[str(path_class(cursor_path))] = (session_name, claimant_agent)

    runtime._global_log_claims = claims
    runtime._global_log_claims_fetched_at = now
    return claims
