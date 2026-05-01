from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime as dt_datetime
from pathlib import Path

from backend_core.agents.ensure_clis import agent_launch_readiness
from backend_core.agents.names import expected_instance_names
from backend_core.agents.names import agent_base_name as _agent_base_name


def pending_launch_preflight(workspace: str, delivery_targets: list[str]) -> tuple[bool, dict]:
    if not delivery_targets:
        return False, {"ok": False, "error": "target is required"}
    readiness_failures = []
    seen_bases: set[str] = set()
    for agent in delivery_targets:
        base = _agent_base_name(agent)
        if not base or base in seen_bases:
            continue
        seen_bases.add(base)
        readiness = agent_launch_readiness(Path(workspace), base)
        if readiness.get("status") != "ok":
            readiness_failures.append(readiness)
    if not readiness_failures:
        return True, {"ok": True}
    first = readiness_failures[0]
    return False, {
        "ok": False,
        "error": first.get("error") or "Selected agent is not ready to launch.",
        "reason": first.get("status") or "preflight_failed",
        "agent": first.get("agent") or "",
        "problems": readiness_failures,
    }


def wait_for_session_instances(runtime, base_agents: list[str], timeout_seconds: float = 12.0) -> bool:
    instances = expected_instance_names(base_agents)
    deadline = time.time() + max(0.5, float(timeout_seconds))
    while time.time() < deadline:
        has_session = subprocess.run(
            [*runtime.tmux_prefix, "has-session", "-t", f"={runtime.session_name}"],
            capture_output=True, text=True, check=False,
        )
        if has_session.returncode == 0:
            if all(runtime.pane_id_for_agent(agent) for agent in instances):
                return True
        time.sleep(0.08)
    return False


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
    ready, payload = pending_launch_preflight(runtime.workspace, delivery_targets)
    if not ready:
        return False, payload
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
    if not wait_for_session_instances(runtime, delivery_targets):
        return False, {"ok": False, "error": "session panes did not become ready"}
    time.sleep(0.5)
    for agent in delivery_targets:
        pane_id = runtime.pane_id_for_agent(agent)
        if pane_id:
            subprocess.run(
                [*runtime.tmux_prefix, "send-keys", "-t", pane_id, "", "Enter"],
                capture_output=True, check=False,
            )
    time.sleep(0.3)
    mark_session_launched(runtime, delivery_targets)
    return True, {"ok": True, "activated": True, "targets": list(delivery_targets)}
