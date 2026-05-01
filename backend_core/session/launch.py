from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime as dt_datetime
from pathlib import Path


def mark_session_launched(runtime, launched_agents: list[str]) -> None:
    session_dir = runtime.index_path.parent
    meta_path = session_dir / ".meta"
    updated_at = dt_datetime.now().strftime("%Y-%m-%d %H:%M")
    meta: dict = {}
    if meta_path.is_file():
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                meta = raw
        except Exception:
            meta = {}
    if "created_at" not in meta or not str(meta.get("created_at") or "").strip():
        meta["created_at"] = updated_at
    meta["updated_at"] = updated_at
    meta["session"] = runtime.session_name
    meta["workspace"] = runtime.workspace
    meta["agents"] = list(launched_agents or [])
    try:
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    runtime.targets = list(launched_agents or [])
    runtime.mark_session_activated()


def launch_session(runtime, delivery_targets: list[str]) -> tuple[bool, dict]:
    env = os.environ.copy()
    env["MULTIAGENT_SESSION"] = runtime.session_name
    env["MULTIAGENT_WORKSPACE"] = runtime.workspace
    env["MULTIAGENT_LOG_DIR"] = runtime.log_dir
    env["MULTIAGENT_INDEX_PATH"] = str(runtime.index_path)
    env["MULTIAGENT_BIN_DIR"] = str(Path(runtime.agent_send_path).parent)
    env["MULTIAGENT_TMUX_SOCKET"] = runtime.tmux_socket
    env["MULTIAGENT_SKIP_USER_CHAT"] = "1"
    env.pop("TMUX", None)
    env.pop("TMUX_PANE", None)
    env["MULTIAGENT_AGENT_NAME"] = "user"
    multiagent_bin = Path(runtime.agent_send_path).parent / "multiagent"
    try:
        subprocess.Popen(
            [str(multiagent_bin), "--detach", "--session", runtime.session_name,
             "--workspace", runtime.workspace, "--agents", ",".join(delivery_targets)],
            cwd=runtime.workspace or None,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logging.error("Unexpected error: %s", exc, exc_info=True)
        return False, {"ok": False, "error": str(exc)}
    mark_session_launched(runtime, delivery_targets)
    return True, {"ok": True, "activated": True, "targets": list(delivery_targets)}
